from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from argus.llm.openrouter import (
    invoke_openrouter_json_schema,
    openrouter_structured_model_candidates,
)


class ArtifactAssumptionEditPlan(BaseModel):
    outcome: Literal["ready_to_confirm", "needs_clarification", "unsupported"]
    user_goal_summary: str | None = None
    initial_capital: float | None = None
    timeframe: str | None = None
    fee_rate: float | None = None
    slippage: float | None = None
    missing_required_fields: list[str] = Field(default_factory=list)
    assistant_response: str | None = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


async def plan_artifact_assumption_edit(
    *,
    current_user_message: str,
    prior_strategy: dict[str, Any] | None,
    active_confirmation: dict[str, Any] | None,
    preferred_model: str,
) -> ArtifactAssumptionEditPlan | None:
    if not current_user_message.strip():
        return None
    if prior_strategy is None and active_confirmation is None:
        return None

    messages = _artifact_assumption_edit_messages(
        current_user_message=current_user_message,
        prior_strategy=prior_strategy,
        active_confirmation=active_confirmation,
    )
    for model_name in _unique_models(preferred_model):
        try:
            plan = await invoke_openrouter_json_schema(
                task="interpretation",
                messages=messages,
                schema_model=ArtifactAssumptionEditPlan,
                schema_name="ArtifactAssumptionEditPlan",
                model_name=model_name,
            )
        except Exception:
            continue
        if not isinstance(plan, ArtifactAssumptionEditPlan):
            continue
        if plan.outcome == "ready_to_confirm" and not _has_supported_edit(plan):
            continue
        if plan.outcome != "ready_to_confirm" and not plan.assistant_response:
            continue
        return plan
    return None


def _artifact_assumption_edit_messages(
    *,
    current_user_message: str,
    prior_strategy: dict[str, Any] | None,
    active_confirmation: dict[str, Any] | None,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's artifact assumption edit planner. The user is "
                "editing assumptions on a visible confirmation artifact. Interpret "
                "only the current user message against the prior artifact. Do not "
                "execute a backtest. Do not infer hidden strategy changes. Return "
                "ready_to_confirm only when the message clearly changes a supported "
                "assumption.\n\n"
                "Supported assumption edits for this planner:\n"
                "- starting capital / initial capital -> initial_capital as a number\n"
                "- timeframe / bars -> timeframe as a compact value such as 1D or 1h\n"
                "- fees -> fee_rate as a decimal fraction when explicitly supplied\n"
                "- slippage -> slippage as a decimal fraction when explicitly supplied\n\n"
                "If the user asks what assumptions are currently visible, return "
                "needs_clarification with a concise assistant_response instead of "
                "inventing an edit. If the user asks for an unsupported assumption "
                "or a strategy change, return unsupported or needs_clarification and "
                "name what can be changed. Return only JSON matching the schema."
            ),
        },
        {
            "role": "system",
            "content": (
                "Prior strategy JSON, if any: "
                f"{prior_strategy if prior_strategy else 'none'}\n"
                "Active confirmation reference JSON, if any: "
                f"{active_confirmation if active_confirmation else 'none'}"
            ),
        },
        {"role": "user", "content": current_user_message},
    ]


def _has_supported_edit(plan: ArtifactAssumptionEditPlan) -> bool:
    return any(
        value is not None
        for value in (
            plan.initial_capital,
            plan.timeframe,
            plan.fee_rate,
            plan.slippage,
        )
    )


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
