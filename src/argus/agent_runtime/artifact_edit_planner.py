from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

from argus.agent_runtime.artifacts.asset_edits import (
    AssetUniverseOperation,
    normalized_asset_symbols,
    normalized_asset_universe_operation,
    same_asset_universe,
)
from argus.agent_runtime.llm_interpreter_types import LLMDateRangeIntent
from argus.llm.openrouter import (
    invoke_openrouter_json_schema,
    openrouter_structured_model_candidates,
)


class EditOperation(BaseModel):
    """One typed edit a user expressed in a turn (via a chip or natural language).

    Both entry points produce the same operations so they cannot drift apart.
    """

    op: Literal["add", "remove", "replace", "set", "clear"]
    target: Literal[
        "asset",
        "benchmark",
        "date_window",
        "capital",
        "recurring_contribution",
        "cadence",
        "timeframe",
        "fees",
        "slippage",
    ]
    symbols: list[str] = Field(default_factory=list)
    value: str | None = None
    number: float | None = None
    date_window: LLMDateRangeIntent | None = None


class ArtifactAssumptionEditPlan(BaseModel):
    outcome: Literal["ready_to_confirm", "needs_clarification", "unsupported"]
    operations: list[EditOperation] = Field(default_factory=list)
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
    language: str | None = None,
) -> ArtifactAssumptionEditPlan | None:
    if not current_user_message.strip():
        return None
    if prior_strategy is None and active_confirmation is None:
        return None

    messages = _artifact_assumption_edit_messages(
        current_user_message=current_user_message,
        prior_strategy=prior_strategy,
        active_confirmation=active_confirmation,
        language=language,
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
    language: str | None = None,
) -> list[dict[str, str]]:
    language_line = (
        f"Write assistant_response in the user's language ({language})."
        if language
        else "Write assistant_response in the user's language."
    )
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's artifact edit planner. The user is editing a "
                "visible confirmation card. Interpret only the current user message "
                "against the current card. Do not execute a backtest. Do not infer "
                "hidden strategy changes.\n\n"
                "Express EVERY change the user asks for in this turn as an entry in "
                "operations. Never drop one. Each operation has op "
                "(add | remove | replace | set | clear) and target, plus the value "
                "carrier for that target. Resolve references such as 'that', 'it', "
                "or 'the second one' against the current card.\n\n"
                "Targets and their value carriers:\n"
                "- asset (traded tickers, use symbols): add new tickers, remove "
                "named tickers, replace the whole traded set, or clear. For add and "
                "remove, include only the affected tickers in symbols.\n"
                "- benchmark (use value as a ticker): set or clear the comparison "
                "asset. Do not also add it to traded assets unless the user says to "
                "buy, hold, or test it.\n"
                "- date_window (use date_window): change the traded date range as "
                "canonical intent (use the current date given below). For 'this "
                "year', 'year to date', or 'the beginning of this year' use "
                "kind=year_to_date (it resolves to January 1 of the current year "
                "through today) — use it even when the user says 'change the start "
                "to the beginning of this year'. For a named calendar year use "
                "kind=calendar_year with year. For a rolling lookback such as 'last "
                "12 months' use kind=rolling_window with count, unit, anchor=today. "
                "For an explicit concrete endpoint date while keeping the other "
                "endpoint, use kind=endpoint_patch with endpoint=start or end and a "
                "concrete ISO date in the start or end field (or the literal today); "
                "do not use anchor for endpoint_patch.\n"
                "- capital (use number): set starting capital.\n"
                "- recurring_contribution (use number) and cadence (use value as "
                "daily, weekly, biweekly, monthly, or quarterly): set the DCA "
                "per-purchase amount and cadence.\n"
                "- timeframe (use value, compact such as 1D or 1h): set the bar "
                "size.\n"
                "- fees (use number) and slippage (use number): set as decimal "
                "fractions when explicitly supplied.\n\n"
                "Execution limits the system enforces (do not propose operations "
                "that break them): one asset class per run (equities and crypto "
                "cannot mix), at most 5 traded symbols, long-only, and the "
                "benchmark must match the traded asset class. If the user's edit "
                "would break a limit, return needs_clarification, explain the limit "
                "plainly, and offer the closest in-limit alternative (for example "
                "switching the whole run to that asset class). The strategy type and "
                "its entry/exit rule parameters are not editable here.\n\n"
                "Return outcome=ready_to_confirm when operations contains at least "
                "one applicable change. If the user asks what is currently set, "
                "return needs_clarification with a concise assistant_response "
                "instead of inventing operations. If the user asks for something "
                "outside the targets above (for example a strategy or entry/exit "
                "rule change), return unsupported or needs_clarification and name "
                "what can be changed; do not invent an operation for it. When a "
                "single turn mixes a supported change with an unsupported one, apply "
                "the supported operations with outcome=ready_to_confirm and use "
                "assistant_response to briefly state, in the user's language, what "
                "you could not change and why. "
                f"Today is {date.today().isoformat()}. {language_line} Return only "
                "JSON matching the schema."
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
    if plan.operations:
        resolved = apply_edit_operations(
            plan.operations,
            current_asset_universe=_reference_asset_universe(
                prior_strategy=prior_strategy,
                active_confirmation=active_confirmation,
            ),
        )
        return resolved.has_changes()
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


_NUMBER_TARGETS = {"capital", "recurring_contribution", "fees", "slippage"}
_TEXT_TARGETS = {"cadence", "timeframe"}


class ResolvedArtifactEdit(BaseModel):
    """Deterministic result of applying an operation list to the current card.

    ``applied`` and ``unsupported`` are the typed truth of what changed — the
    model-voiced reply is reconciled against them so Argus never silently drops an
    edit and never claims one it did not make.
    """

    asset_universe: list[str] | None = None
    asset_universe_operation: Literal["replace"] | None = None
    comparison_baseline: str | None = None
    date_window: LLMDateRangeIntent | None = None
    initial_capital: float | None = None
    recurring_contribution_amount: float | None = None
    cadence: str | None = None
    timeframe: str | None = None
    fee_rate: float | None = None
    slippage: float | None = None
    applied: list[str] = Field(default_factory=list)
    unsupported: list[str] = Field(default_factory=list)

    def has_changes(self) -> bool:
        return bool(self.applied)


def apply_edit_operations(
    operations: list[EditOperation],
    *,
    current_asset_universe: Any = None,
) -> ResolvedArtifactEdit:
    """Resolve a messy, multi-operation edit turn against the current card.

    Asset add/remove/replace/clear are resolved against the current traded set and
    emitted as a single ``replace`` of the final set, so existing downstream apply
    semantics are reused. Every recognized-but-inapplicable operation is recorded
    in ``unsupported`` rather than dropped.
    """

    resolved = ResolvedArtifactEdit()
    working_assets = normalized_asset_symbols(current_asset_universe)
    asset_touched = False

    for operation in operations:
        target = operation.target
        op = operation.op

        if target == "asset":
            patch = normalized_asset_symbols(operation.symbols)
            if op == "add":
                working_assets = normalized_asset_symbols([*working_assets, *patch])
            elif op == "remove":
                removal = set(patch)
                working_assets = [s for s in working_assets if s not in removal]
            elif op == "replace":
                working_assets = patch
            elif op == "clear":
                working_assets = []
            else:
                resolved.unsupported.append(f"{op}.{target}")
                continue
            asset_touched = True
            resolved.applied.append(f"{op}.{target}")
            continue

        if target == "benchmark":
            if op in {"set", "replace"}:
                benchmark = (operation.value or "").strip().upper()
                if not benchmark:
                    resolved.unsupported.append(f"{op}.{target}")
                    continue
                resolved.comparison_baseline = benchmark
            elif op == "clear":
                resolved.comparison_baseline = ""
            else:
                resolved.unsupported.append(f"{op}.{target}")
                continue
            resolved.applied.append(f"{op}.{target}")
            continue

        if target == "date_window":
            if op in {"set", "replace"} and operation.date_window is not None:
                resolved.date_window = operation.date_window
                resolved.applied.append(f"set.{target}")
            else:
                resolved.unsupported.append(f"{op}.{target}")
            continue

        if target in _NUMBER_TARGETS:
            if op in {"set", "replace"} and operation.number is not None:
                amount = float(operation.number)
                if target == "capital":
                    resolved.initial_capital = amount
                elif target == "recurring_contribution":
                    resolved.recurring_contribution_amount = amount
                elif target == "fees":
                    resolved.fee_rate = amount
                elif target == "slippage":
                    resolved.slippage = amount
                resolved.applied.append(f"set.{target}")
            else:
                resolved.unsupported.append(f"{op}.{target}")
            continue

        if target in _TEXT_TARGETS:
            if op in {"set", "replace"} and (operation.value or "").strip():
                cleaned = operation.value.strip()
                if target == "cadence":
                    resolved.cadence = cleaned
                else:
                    resolved.timeframe = cleaned
                resolved.applied.append(f"set.{target}")
            else:
                resolved.unsupported.append(f"{op}.{target}")
            continue

        resolved.unsupported.append(f"{op}.{target}")

    if asset_touched:
        resolved.asset_universe = working_assets
        resolved.asset_universe_operation = "replace"

    return resolved
