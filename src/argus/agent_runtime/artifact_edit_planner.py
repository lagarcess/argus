from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from argus.agent_runtime.artifacts.asset_edits import (
    AssetUniverseOperation,
    normalized_asset_universe_operation,
    same_asset_universe,
)
from argus.llm.openrouter import (
    invoke_openrouter_json_schema,
    openrouter_structured_model_candidates,
)


class ArtifactAssumptionEditPlan(BaseModel):
    outcome: Literal["ready_to_confirm", "needs_clarification", "unsupported"]
    user_goal_summary: str | None = None
    asset_universe: list[str] = Field(default_factory=list)
    asset_universe_operation: AssetUniverseOperation | None = None
    comparison_baseline: str | None = None
    initial_capital: float | None = None
    recurring_contribution_amount: float | None = None
    cadence: str | None = None
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
        if plan.outcome == "ready_to_confirm" and not _has_supported_edit(
            plan,
            prior_strategy=prior_strategy,
            active_confirmation=active_confirmation,
        ):
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
                "Supported visible artifact edits for this planner:\n"
                "- traded assets -> asset_universe as ticker/symbol values. Use "
                "asset_universe_operation=append when the user adds assets while "
                "keeping existing traded assets, and replace when the user swaps "
                "the traded assets. For append/add, include only the newly added "
                "assets in asset_universe.\n"
                "- benchmark / reference / comparison asset -> comparison_baseline "
                "as a ticker/symbol value. Do not put this asset in asset_universe "
                "unless the user explicitly says to buy, hold, or test it as a "
                "traded asset.\n"
                "- starting capital / initial capital -> initial_capital as a number\n"
                "- DCA or recurring-buy per-purchase contribution -> "
                "recurring_contribution_amount as a number; do not put it in "
                "initial_capital\n"
                "- DCA or recurring-buy cadence -> cadence as daily, weekly, "
                "biweekly, monthly, or quarterly\n"
                "- timeframe / bars -> timeframe as a compact value such as 1D or 1h\n"
                "- fees -> fee_rate as a decimal fraction when explicitly supplied\n"
                "- slippage -> slippage as a decimal fraction when explicitly supplied\n\n"
                "If the user asks what assumptions are currently visible, return "
                "needs_clarification with a concise assistant_response instead of "
                "inventing an edit. If the user asks for an unsupported assumption "
                "or unsupported strategy change, return unsupported or "
                "needs_clarification and name what can be changed. Return only JSON "
                "matching the schema."
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


def _has_supported_edit(
    plan: ArtifactAssumptionEditPlan,
    *,
    prior_strategy: dict[str, Any] | None = None,
    active_confirmation: dict[str, Any] | None = None,
) -> bool:
    asset_operation = normalized_asset_universe_operation(
        plan.asset_universe_operation
    )
    if plan.asset_universe and asset_operation is None:
        if not same_asset_universe(
            plan.asset_universe,
            _reference_asset_universe(
                prior_strategy=prior_strategy,
                active_confirmation=active_confirmation,
            ),
        ):
            return False
        asset_universe_edit = None
    else:
        asset_universe_edit = (
            plan.asset_universe
            if asset_operation is not None
            else None
        )
    return any(
        value is not None
        for value in (
            asset_universe_edit,
            plan.comparison_baseline,
            plan.initial_capital,
            plan.recurring_contribution_amount,
            plan.cadence,
            plan.timeframe,
            plan.fee_rate,
            plan.slippage,
        )
    )


def _reference_asset_universe(
    *,
    prior_strategy: dict[str, Any] | None,
    active_confirmation: dict[str, Any] | None,
) -> Any:
    if isinstance(prior_strategy, dict) and prior_strategy.get("asset_universe"):
        return prior_strategy.get("asset_universe")
    if isinstance(active_confirmation, dict):
        strategy = active_confirmation.get("strategy")
        if isinstance(strategy, dict) and strategy.get("asset_universe"):
            return strategy.get("asset_universe")
        if active_confirmation.get("asset_universe"):
            return active_confirmation.get("asset_universe")
    return []


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
