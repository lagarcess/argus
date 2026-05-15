from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from argus.domain.backtesting.rules import (
    explicit_signal_rule_intent_from_text,
    validate_rule_spec,
)
from argus.llm.openrouter import (
    invoke_openrouter_json_schema,
    openrouter_structured_model_candidates,
)


class SignalRulePlan(BaseModel):
    outcome: Literal["ready_to_confirm", "needs_clarification", "draft_only"]
    user_goal_summary: str | None = None
    strategy_thesis: str | None = None
    entry_logic: str | None = None
    exit_logic: str | None = None
    rule_spec: dict[str, Any] | None = None
    missing_required_fields: list[str] = Field(default_factory=list)
    assistant_response: str | None = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class SignalRuleGroundingAudit(BaseModel):
    outcome: Literal["grounded", "needs_clarification"]
    assistant_response: str | None = None
    missing_required_fields: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


async def repair_signal_rule_plan(
    *,
    current_user_message: str,
    candidate_strategy: dict[str, Any],
    prior_strategy: dict[str, Any] | None,
    preferred_model: str,
) -> SignalRulePlan | None:
    explicit_intent = explicit_signal_rule_intent_from_text(current_user_message)
    if explicit_intent is not None:
        return SignalRulePlan(
            outcome="ready_to_confirm",
            user_goal_summary=(
                explicit_intent.strategy_thesis
                if candidate_strategy.get("asset_universe")
                else "Test the explicit signal rule."
            ),
            strategy_thesis=explicit_intent.strategy_thesis,
            entry_logic=explicit_intent.entry_logic,
            exit_logic=explicit_intent.exit_logic,
            rule_spec=explicit_intent.rule_spec,
            confidence=explicit_intent.confidence,
        )

    messages = _signal_rule_plan_messages(
        current_user_message=current_user_message,
        candidate_strategy=candidate_strategy,
        prior_strategy=prior_strategy,
    )
    for model_name in _unique_models(preferred_model):
        try:
            plan = await invoke_openrouter_json_schema(
                task="interpretation",
                messages=messages,
                schema_model=SignalRulePlan,
                schema_name="SignalRulePlan",
                model_name=model_name,
            )
        except Exception:
            continue
        if not isinstance(plan, SignalRulePlan):
            continue
        if plan.rule_spec is not None:
            try:
                validate_rule_spec(plan.rule_spec)
            except ValueError:
                continue
        if plan.outcome == "ready_to_confirm" and plan.rule_spec is None:
            continue
        if plan.outcome == "ready_to_confirm" and (
            not plan.entry_logic or not plan.exit_logic
        ):
            continue
        if plan.outcome != "ready_to_confirm" and plan.rule_spec is not None:
            continue
        if plan.outcome != "ready_to_confirm" and not plan.assistant_response:
            continue
        return plan
    return None


async def audit_signal_rule_grounding(
    *,
    current_user_message: str,
    candidate_strategy: dict[str, Any],
    prior_strategy: dict[str, Any] | None,
    preferred_model: str,
) -> SignalRuleGroundingAudit | None:
    messages = _signal_rule_grounding_messages(
        current_user_message=current_user_message,
        candidate_strategy=candidate_strategy,
        prior_strategy=prior_strategy,
    )
    for model_name in _unique_models(preferred_model):
        try:
            audit = await invoke_openrouter_json_schema(
                task="interpretation",
                messages=messages,
                schema_model=SignalRuleGroundingAudit,
                schema_name="SignalRuleGroundingAudit",
                model_name=model_name,
            )
        except Exception:
            continue
        if not isinstance(audit, SignalRuleGroundingAudit):
            continue
        if audit.outcome == "needs_clarification" and not audit.assistant_response:
            continue
        return audit
    return None


def _signal_rule_plan_messages(
    *,
    current_user_message: str,
    candidate_strategy: dict[str, Any],
    prior_strategy: dict[str, Any] | None,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's signal-rule planning layer. Convert a structured "
                "signal strategy draft into an executable rule_spec only when the "
                "user supplied enough meaning. Do not execute and do not invent "
                "unsupported conditions. Use the candidate strategy and prior "
                "strategy as context; the current user message is authoritative.\n\n"
                "Rule grammar: rule_spec has entry and exit groups. Each group has "
                "conditions with left/operator/right. Operators are lt, lte, gt, "
                "gte, cross_above, cross_below. Operands may be numbers or series "
                "refs: {'kind':'price','field':'close'}, {'kind':'volume','field':'volume'}, "
                "or {'kind':'indicator','key':..., 'period':..., 'output':..., "
                "'parameters':...}.\n\n"
                "Executable defaults:\n"
                "- MACD crossover means the MACD line crosses its signal line. Use "
                "parameters {'fast':12,'slow':26,'signal':9}; entry cross_above, "
                "exit cross_below. If the user supplies a MACD entry but no explicit "
                "exit, default the exit to the opposite MACD crossover and return "
                "ready_to_confirm. This is runnable when the user says MACD turns "
                "bullish, MACD crosses bullish, or MACD crossover only.\n"
                "- SMA/EMA crossovers are runnable when fast and slow periods are "
                "stated. Use indicator refs with key sma or ema and operator "
                "cross_above/cross_below. If the user supplies a crossover entry "
                "but no explicit exit, default the exit to the opposite crossover "
                "with the same indicators and periods and return ready_to_confirm; "
                "do not ask to run the entry rule only.\n"
                "- Bollinger Band touches are runnable when the touched band and exit "
                "meaning are supplied; defaults are length 20 and std 2.\n"
                "- Price above/below SMA, EMA, or Bollinger output is runnable when "
                "the side, indicator, period/output, and exit meaning are supplied.\n"
                "- Volume confirmation is runnable only when it is defined as a "
                "complete comparison, such as volume above a volume SMA period or a "
                "numeric threshold. A vague 'volume jumps' is not complete.\n\n"
                "If the user gives a compound idea and one part is incomplete, do "
                "not silently drop the incomplete part unless the current message "
                "asks to run a subset. Return needs_clarification with a specific "
                "assistant_response that names the runnable subset and the missing "
                "definition. If the user asks to run the subset, return ready_to_confirm "
                "for that subset. If the idea depends on data or execution concepts "
                "outside the rule grammar, such as news sentiment, analyst ratings, "
                "fundamentals, social signals, broker execution, stop losses, or "
                "portfolio risk controls, return draft_only with a product-language "
                "assistant_response. If no executable rule is clear but the idea could "
                "be expressed with the supported grammar, ask for the exact entry/exit "
                "definition. Return only JSON matching the schema."
            ),
        },
        {
            "role": "system",
            "content": (
                "Prior strategy JSON, if any: "
                f"{prior_strategy if prior_strategy else 'none'}\n"
                "Candidate strategy JSON: "
                f"{candidate_strategy}"
            ),
        },
        {"role": "user", "content": current_user_message},
    ]


def _signal_rule_grounding_messages(
    *,
    current_user_message: str,
    candidate_strategy: dict[str, Any],
    prior_strategy: dict[str, Any] | None,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's signal-rule grounding audit. Decide whether an "
                "executable signal rule in a structured draft is actually grounded "
                "in the user's current message or in an active prior strategy that "
                "the current message is clearly refining. Do not execute. Do not "
                "invent missing triggers.\n\n"
                "Return grounded only when the user or preserved prior strategy "
                "explicitly supplies the indicator, crossover, threshold, band, "
                "price/indicator comparison, or volume comparison represented by "
                "the candidate rule. A current-message edit like 'make it Nvidia' "
                "or 'use last month' may preserve a prior rule. Return "
                "needs_clarification when the candidate turned vague language such "
                "as starts rising, big drops, breakout, or looks strong into a "
                "specific executable rule that the user did not choose. In that "
                "case, write a concise assistant_response that asks for the exact "
                "trigger or offers executable families without choosing one."
            ),
        },
        {
            "role": "system",
            "content": (
                "Prior strategy JSON, if any: "
                f"{prior_strategy if prior_strategy else 'none'}\n"
                "Candidate strategy JSON: "
                f"{candidate_strategy}"
            ),
        },
        {"role": "user", "content": current_user_message},
    ]


def _unique_models(preferred_model: str) -> list[str]:
    candidates = [preferred_model, *openrouter_structured_model_candidates()]
    seen: set[str] = set()
    ordered: list[str] = []
    for model_name in candidates:
        if not model_name or model_name in seen:
            continue
        seen.add(model_name)
        ordered.append(model_name)
    return ordered
