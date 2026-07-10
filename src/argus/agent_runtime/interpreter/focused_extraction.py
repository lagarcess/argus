"""Focused-strategy extraction message builders and repair-merge helpers.

Behavior-preserving relocation from llm_interpreter.py (issue #131)."""

from __future__ import annotations

from datetime import date

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)

from argus.agent_runtime.interpreter.shared import _llm_value_is_empty
from argus.agent_runtime.llm_interpreter_types import (
    FocusedStrategyExtraction,
    LLMInterpretationResponse,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.strategy_contract import canonical_strategy_type


def _focused_strategy_extraction_messages(
    request: InterpretationRequest,
) -> list[BaseMessage]:
    return [
        SystemMessage(
            content=(
                "Focused strategy extraction repair. The general interpreter under-filled "
                "a current user message that may contain a testable investing idea. "
                "Interpret only the current user message and return all fields needed "
                "to draft an executable backtest. Do not omit a field that appears in "
                "the message. Do not invent fees, slippage, position size, or provider "
                "details. If the current message semantically gives a supported "
                "strategy family, primary asset, benchmark/reference asset, relative "
                "window, capital amount, recurring contribution, or recurring cadence, "
                "returning null or empty for that field is an extraction failure. Do "
                "not ask the user to choose a supported strategy when the current "
                "message already selected one semantically. "
                "Evidence spans are provenance only. Never put a supported "
                "strategy, asset, benchmark, time window, or capital amount only "
                "inside evidence_spans; populate the matching canonical field too. "
                "date_range_intent is the canonical object field, not an "
                "evidence_spans key; if a time window is visible, populate "
                "date_range_raw_text with the exact bounded phrase and "
                "date_range_intent with the canonical intent. "
                "is_testable_strategy means the user is asking for a strategy "
                "or backtest idea; it does not mean Argus can execute every part. For "
                "clear sentiment, news, fundamental, external-data, or other draft-only "
                "strategy requests, set is_testable_strategy=true, preserve the asset, "
                "period, unsupported rule, and raw strategy_type, and let the runtime "
                "route it to unsupported recovery.\n\n"
                "Executable strategy_type values are buy_and_hold, dca_accumulation, "
                "indicator_threshold, and signal_strategy. Treat this as an execution "
                "contract, not a taxonomy for every creative idea. If the user asks for "
                "sentiment, news, fundamentals, custom external data, or any rule you "
                "cannot express with these structured executable fields, do not force "
                "it into signal_strategy or indicator_threshold. Preserve the idea in "
                "user_goal_summary/assistant_response and mark it as needing a supported "
                "executable simplification. Valuation/P/E language is financially valid "
                "context, but it is not an executable rule in the current engine; preserve "
                "the valuation meaning and route toward the closest supported proxy. "
                "Preserve user-stated asset names or symbols "
                "in asset_universe; the provider-backed resolver will validate and "
                "canonicalize assets after interpretation. When the user lists "
                "multiple company or asset names as things to buy, hold, test, or "
                "include, emit each stated traded asset in asset_universe; do not "
                "collapse a same-class basket to one name. Preserve user-stated "
                "benchmark/comparison assets such as QQQ, SPY, BTC, or IWM in "
                "comparison_baseline, not asset_universe. In any language, a request "
                "to buy, hold, or test one primary asset over a window with another "
                "asset as a benchmark, reference, baseline, or comparison target is "
                "an executable buy_and_hold setup with that other asset in "
                "comparison_baseline; it is not unsupported custom logic. Relative windows such as "
                "'last 8 months' or equivalent phrases in any language must become "
                "date_range_intent with kind=rolling_window, count, unit, "
                "anchor=today, confidence, and evidence. Current-year-to-current-date "
                "windows in any language must become date_range_intent with "
                "kind=year_to_date, confidence, and evidence. Do not ask for exact "
                "endpoint dates when the current message states a relative window. "
                "Use date_range_raw_text only as bounded evidence for the same "
                "window, not as the executable date contract. If the user gives a "
                "start date and says today, preserve the end as 'today' or "
                f"{date.today().isoformat()}, not a stale model date. If the user gives "
                "only a start or only an end, preserve only that endpoint and include "
                "date_range in missing_required_fields; do not infer today. Preserve "
                "language, date_range_raw_text, date_range_intent, and evidence_spans "
                "when available. Use date_range_intent for relative or semantic time "
                "windows so deterministic code receives canonical date math inputs "
                "instead of localized prose. Preserve "
                "user-stated timeframes such as 1 hour candles, hourly bars, 1h, "
                "4 hour candles, 4h, daily candles, or 1D as timeframe. Normalize "
                "one-hour/hourly to 1h, four-hour to 4h, and daily to 1D. Preserve "
                "user-stated capital amounts as capital_amount; "
                "do not silently widen the timeframe, shorten dates, or drop stated "
                "money amounts to make a request look runnable.\n\n"
                "For moving-average crossovers, set strategy_type to signal_strategy "
                "and set entry_rule to {'type':'moving_average_crossover', "
                "'fast_indicator':'sma' or 'ema', 'fast_period':number, "
                "'slow_indicator':'sma' or 'ema', 'slow_period':number, "
                "'direction':'bullish' for crosses above or 'bearish' for crosses "
                "below}. If the user does not state an exit, leave exit_rule null "
                "and set exit_logic to the opposite crossover default. Shorthand "
                "like 'the 50 crosses the 200' or '50/200 cross' is enough to set "
                "a bullish SMA 50/200 crossover unless the user says EMA or bearish.\n\n"
                "For RSI threshold ideas, set strategy_type to indicator_threshold, "
                "indicator to rsi, indicator_period only when supplied, and threshold "
                "overrides as numbers. If the user states only one threshold side, "
                "fill that side and leave only the unstated side null so the runtime "
                "can apply the supported default. Do not ask about RSI period; it has "
                "a supported default.\n\n"
                "A one-time historical acquisition or purchase plus holding through "
                "a period is normal user language for the supported buy_and_hold "
                "simulation, not unsupported manual trade replay. Preserve the asset, "
                "capital_amount, and date_range_intent when present. Do not ask the "
                "user to choose buy-and-hold again when the current message already "
                "semantically selected holding and did not state a separate entry or "
                "exit rule. A recurring fixed-amount purchase over a period is normal "
                "user language for the supported dca_accumulation simulation. Preserve "
                "the asset, recurring_contribution, cadence, capital_amount, and "
                "date_range_intent when present. Do not route recurring fixed-amount "
                "buys to unsupported recovery when those executable fields are stated."
            )
        ),
        HumanMessage(content=request.current_user_message),
    ]


def _comparison_baseline_provenance(
    comparison_baseline: str | None,
    *,
    current_message: str,
) -> dict[str, str]:
    del comparison_baseline, current_message
    return {}


def _focused_extraction_field_provenance(
    *,
    extraction: FocusedStrategyExtraction,
    current_message: str,
) -> dict[str, str]:
    provenance = _comparison_baseline_provenance(
        extraction.comparison_baseline,
        current_message=current_message,
    )
    evidence_spans = dict(extraction.evidence_spans or {})
    if (
        extraction.comparison_baseline
        and _llm_value_is_empty(provenance.get("comparison_baseline"))
        and not _llm_value_is_empty(evidence_spans.get("comparison_baseline"))
    ):
        provenance["comparison_baseline"] = "explicit_user"
    if extraction.recurring_contribution is not None:
        provenance["recurring_contribution"] = "explicit_user"
        provenance["capital_amount"] = "recurring_contribution"
    elif extraction.capital_amount is not None:
        if canonical_strategy_type(extraction.strategy_type) == "dca_accumulation":
            provenance["capital_amount"] = "recurring_contribution"
        else:
            provenance["capital_amount"] = "starting_capital"
    if extraction.cadence:
        provenance["cadence"] = "explicit_user"
    return provenance


def _merge_focused_repair_with_base(
    *,
    response: LLMInterpretationResponse,
    base_response: LLMInterpretationResponse | None,
) -> LLMInterpretationResponse:
    if base_response is None:
        return response
    repaired = response.model_copy(deep=True)
    draft = repaired.candidate_strategy_draft
    base = base_response.candidate_strategy_draft
    for field_name in (
        "raw_user_phrasing",
        "strategy_thesis",
        "asset_universe",
        "asset_class",
        "date_range",
        "date_range_intent",
        "timeframe",
        "cadence",
        "capital_amount",
        "position_size",
        "comparison_baseline",
    ):
        current_value = getattr(draft, field_name)
        base_value = getattr(base, field_name)
        if _llm_value_is_empty(current_value) and not _llm_value_is_empty(base_value):
            setattr(draft, field_name, base_value)
    if not repaired.user_goal_summary and base_response.user_goal_summary:
        repaired.user_goal_summary = base_response.user_goal_summary
    repaired.reason_codes = list(
        dict.fromkeys(
            [
                *base_response.reason_codes,
                *repaired.reason_codes,
                "focused_repair_preserved_structured_context",
                *(
                    ["focused_repair_from_unsupported_context"]
                    if _base_response_was_unsupported(base_response)
                    else []
                ),
            ]
        )
    )
    return repaired


def _base_response_was_unsupported(response: LLMInterpretationResponse) -> bool:
    return bool(
        response.intent == "unsupported_or_out_of_scope"
        or response.semantic_turn_act == "unsupported_request"
        or response.unsupported_constraints
    )


def _focused_artifact_edit_messages(
    request: InterpretationRequest,
) -> list[BaseMessage] | None:
    snapshot = request.latest_task_snapshot
    if snapshot is None:
        return None
    prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    if prior is None and snapshot.active_confirmation_reference is None:
        return None
    active_confirmation = (
        snapshot.active_confirmation_reference.model_dump(mode="json")
        if snapshot.active_confirmation_reference is not None
        else None
    )
    return [
        SystemMessage(
            content=(
                "Focused artifact edit planning. The previous interpretation replayed "
                "or under-filled the active artifact. Interpret only the current user "
                "message against the canonical prior artifact. The current user message "
                "is authoritative. Return a structured edit or answer; do not replay "
                "the prior artifact unchanged. If the user changes the asset, date "
                "range, indicator, thresholds, or assumptions, candidate_strategy_draft "
                "must include the changed field. Preserve unchanged executable context "
                "from the prior artifact only when it is needed for a runnable draft."
            )
        ),
        SystemMessage(
            content=(
                "Prior strategy JSON, if any: "
                f"{prior.model_dump(mode='json') if prior else 'none'}\n"
                "Active confirmation reference JSON, if any: "
                f"{active_confirmation if active_confirmation else 'none'}"
            )
        ),
        HumanMessage(content=request.current_user_message),
    ]


def _openrouter_wire_messages(messages: list[BaseMessage]) -> list[dict[str, str]]:
    wire_messages: list[dict[str, str]] = []
    for message in messages:
        role = "user"
        if isinstance(message, SystemMessage):
            role = "system"
        elif isinstance(message, AIMessage):
            role = "assistant"
        elif isinstance(message, HumanMessage):
            role = "user"
        content = message.content
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "".join(
                item
                if isinstance(item, str)
                else str(item.get("text") or "")
                if isinstance(item, dict)
                else str(item)
                for item in content
            )
        else:
            text = str(content)
        wire_messages.append({"role": role, "content": text})
    if wire_messages:
        wire_messages[0]["content"] = (
            wire_messages[0]["content"]
            + "\n\nReturn only valid JSON matching the supplied schema. "
            "Do not include reasoning, markdown, prose, or fields that are not "
            "defined by the supplied schema. Use the schema descriptions and the "
            "task-specific instructions above as the contract for canonical values."
        )
    return wire_messages
