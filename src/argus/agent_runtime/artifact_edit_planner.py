from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any, Literal, get_args

from pydantic import BaseModel, Field

from argus.agent_runtime.artifacts.asset_edits import (
    AssetUniverseOperation,
    normalized_asset_symbols,
    normalized_asset_universe_operation,
    same_asset_universe,
)
from argus.agent_runtime.interpreter.execution_cost_fidelity import (
    supported_cost_rate_value,
)
from argus.agent_runtime.llm_interpreter_types import LLMDateRangeIntent
from argus.agent_runtime.rule_specs import opposite_moving_average_crossover_rule
from argus.domain.backtesting.rules import (
    rule_spec_from_moving_average_crossover_rules,
)
from argus.domain.capability_registry import RegisteredStrategyTemplate
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
        "indicator_entry_threshold",
        "indicator_exit_threshold",
        "indicator_period",
        "strategy_family",
    ]
    symbols: list[str] = Field(default_factory=list)
    value: str | None = None
    number: float | None = None
    date_window: LLMDateRangeIntent | None = None
    strategy_template: RegisteredStrategyTemplate | None = None
    entry_rule: dict[str, Any] | None = None
    exit_rule: dict[str, Any] | None = None


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
    required_targets: set[str] | None = None,
    materialized_targets_for_plan: Callable[[ArtifactAssumptionEditPlan], set[str] | None]
    | None = None,
) -> ArtifactAssumptionEditPlan | None:
    if not current_user_message.strip():
        return None
    if prior_strategy is None and active_confirmation is None:
        return None

    required_target_set = set(required_targets or ())
    supported_targets = set(get_args(EditOperation.model_fields["target"].annotation))
    if not required_target_set <= supported_targets:
        return None
    messages = _artifact_assumption_edit_messages(
        current_user_message=current_user_message,
        prior_strategy=prior_strategy,
        active_confirmation=active_confirmation,
        language=language,
        required_targets=required_target_set,
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
        if plan.outcome == "ready_to_confirm" and not _covers_required_targets(
            plan,
            required_targets=required_target_set,
            materialized_targets_for_plan=materialized_targets_for_plan,
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
    required_targets: set[str] | None = None,
) -> list[dict[str, str]]:
    language_line = (
        f"Write assistant_response in the user's language ({language})."
        if language
        else "Write assistant_response in the user's language."
    )
    required_targets_line = (
        "Required typed targets for this turn: "
        f"{', '.join(sorted(required_targets))}. "
        "A ready_to_confirm operation list must cover every required target.\n\n"
        if required_targets
        else ""
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
                f"{required_targets_line}"
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
                "12 months' use kind=rolling_window with count, unit, anchor=today; "
                "a stated fractional quantity stays exact ('last 8.5 months' means "
                "count=8.5, never 8 or 5). "
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
                "fractions when explicitly supplied.\n"
                "- indicator_entry_threshold and indicator_exit_threshold (use "
                "number): set tunable RSI buy/entry and sell/exit thresholds on "
                "an existing RSI confirmation. Use indicator_period for a tunable "
                "RSI lookback period.\n"
                "- strategy_family: replace an active strategy with the already "
                "supported moving_average_crossover template. Set "
                "strategy_template=moving_average_crossover and provide typed "
                "entry_rule and exit_rule objects. Each rule must use "
                "type=moving_average_crossover, fast_indicator and slow_indicator "
                "(sma or ema), positive fast_period and slow_period, and direction "
                "(bullish for entry, bearish for exit). Keep assets, capital, dates, "
                "daily timeframe, benchmark, fees, and slippage out of operations "
                "unless the user explicitly changes them in the same turn.\n\n"
                "Execution limits the system enforces (do not propose operations "
                "that break them): one asset class per run (equities and crypto "
                "cannot mix), at most 5 traded symbols, long-only, and the "
                "benchmark must match the traded asset class. If the user's edit "
                "would break a limit, return needs_clarification, explain the limit "
                "plainly, and offer the closest in-limit alternative (for example "
                "switching the whole run to that asset class). Do not invent a new "
                "strategy family or map unsupported logic into strategy_family. "
                "Only the explicitly supported moving_average_crossover transition "
                "and the listed tunable RSI parameters are strategy-definition "
                "edits here.\n\n"
                "Return outcome=ready_to_confirm when operations contains at least "
                "one applicable change. If the user asks what is currently set, "
                "return needs_clarification with a concise assistant_response "
                "instead of inventing operations. If the user asks for something "
                "outside the targets above, return unsupported or "
                "needs_clarification and name what can be changed; do not invent "
                "an operation for it. When a "
                "single turn mixes a supported change with an unsupported one, apply "
                "the supported operations with outcome=ready_to_confirm and use "
                "assistant_response to briefly state, in the user's language, what "
                "you could not change and why. For mixed add and remove turns, use "
                "separate asset operations; do not collapse the removed asset into "
                "the final traded list. "
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


def _covers_required_targets(
    plan: ArtifactAssumptionEditPlan,
    *,
    required_targets: set[str],
    materialized_targets_for_plan: Callable[[ArtifactAssumptionEditPlan], set[str] | None]
    | None = None,
) -> bool:
    if materialized_targets_for_plan is not None:
        try:
            covered_targets = materialized_targets_for_plan(plan)
        except Exception:
            return False
        if covered_targets is None:
            return False
    elif required_targets:
        covered_targets = _materialized_legacy_flat_targets(plan)
    else:
        return True
    return required_targets.issubset(covered_targets)


def _materialized_legacy_flat_targets(
    plan: ArtifactAssumptionEditPlan,
) -> set[str]:
    """Name flat fields that the legacy application path really materializes.

    Typed operations need request context (date resolution, asset resolution,
    active strategy family) to prove applicability, so callers must supply the
    real materializer for them. Flat fields remain context-free compatibility
    inputs and can be checked here without pretending a carrier is a mutation.
    """

    if plan.operations:
        return set()
    targets: set[str] = set()
    if plan.asset_universe:
        targets.add("asset")
    if str(plan.comparison_baseline or "").strip():
        targets.add("benchmark")
    if plan.initial_capital is not None:
        targets.add("capital")
    if plan.recurring_contribution_amount is not None:
        targets.add("recurring_contribution")
    if str(plan.cadence or "").strip().casefold() in {
        "daily",
        "weekly",
        "biweekly",
        "monthly",
        "quarterly",
    }:
        targets.add("cadence")
    if plan.timeframe is not None:
        targets.add("timeframe")
    if (
        plan.fee_rate is not None
        and supported_cost_rate_value(plan.fee_rate, field_name="fee_rate") is not None
    ):
        targets.add("fees")
    if (
        plan.slippage is not None
        and supported_cost_rate_value(plan.slippage, field_name="slippage") is not None
    ):
        targets.add("slippage")
    return targets


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
        return resolved.has_changes() or any(
            _operation_has_supported_carrier(operation) for operation in plan.operations
        )
    asset_operation = normalized_asset_universe_operation(plan.asset_universe_operation)
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
        asset_universe_edit = plan.asset_universe if asset_operation is not None else None
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


def _operation_has_supported_carrier(operation: EditOperation) -> bool:
    target = operation.target
    op = operation.op
    if target == "asset":
        if op == "clear":
            return True
        return op in {"add", "remove", "replace"} and any(
            str(symbol or "").strip() for symbol in operation.symbols
        )
    if target == "benchmark":
        if op == "clear":
            return True
        return op in {"set", "replace"} and bool((operation.value or "").strip())
    if target == "date_window":
        return op in {"set", "replace"} and operation.date_window is not None
    if target == "strategy_family":
        return (
            op in {"set", "replace"}
            and _resolved_moving_average_crossover(operation) is not None
        )
    if target in _NUMBER_TARGETS or target in _INDICATOR_PARAMETER_TARGETS:
        return op in {"set", "replace"} and operation.number is not None
    if target in _TEXT_TARGETS:
        return op in {"set", "replace"} and bool((operation.value or "").strip())
    return False


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
_INDICATOR_PARAMETER_TARGETS = {
    "indicator_entry_threshold": "entry_threshold",
    "indicator_exit_threshold": "exit_threshold",
    "indicator_period": "indicator_period",
}
_TEXT_TARGETS = {"cadence", "timeframe"}


_DROPPED_COST_TARGETS = {"fee_rate": "fees", "slippage": "slippage"}


def typed_unapplied_operations(
    *,
    resolved_unsupported: list[str],
    dropped_cost_fields: list[str],
) -> list[dict[str, str]]:
    """Typed record of requested changes that did not land, with reasons."""
    unapplied: list[dict[str, str]] = []
    for entry in resolved_unsupported:
        op, _, target = str(entry).partition(".")
        if not target:
            op, target = "set", op
        unapplied.append(
            {"op": op, "target": target, "reason": "unsupported_operation"}
        )
    for field_name in dropped_cost_fields:
        unapplied.append(
            {
                "op": "set",
                "target": _DROPPED_COST_TARGETS.get(field_name, field_name),
                "reason": "cost_evidence_ungrounded",
            }
        )
    return unapplied


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
    indicator_parameters: dict[str, float | int] = Field(default_factory=dict)
    requested_strategy_template: RegisteredStrategyTemplate | None = None
    strategy_type: str | None = None
    entry_rule: dict[str, Any] | None = None
    exit_rule: dict[str, Any] | None = None
    rule_spec: dict[str, Any] | None = None
    applied: list[str] = Field(default_factory=list)
    unsupported: list[str] = Field(default_factory=list)

    def has_changes(self) -> bool:
        return bool(self.applied)


def apply_edit_operations(
    operations: list[EditOperation],
    *,
    current_asset_universe: Any = None,
    asset_symbol_resolver: Callable[[str], str | None] | None = None,
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
            patch = resolved_asset_operation_symbols(
                operation.symbols,
                asset_symbol_resolver=asset_symbol_resolver,
            )
            if op == "add":
                working_assets = normalized_asset_symbols([*working_assets, *patch])
            elif op == "remove":
                removal = set(patch)
                before_assets = list(working_assets)
                working_assets = [s for s in working_assets if s not in removal]
                if working_assets == before_assets:
                    resolved.unsupported.append(f"{op}.{target}")
                    continue
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

        if target == "strategy_family":
            crossover = (
                _resolved_moving_average_crossover(operation)
                if op in {"set", "replace"}
                else None
            )
            if crossover is None:
                resolved.unsupported.append(f"{op}.{target}")
                continue
            entry_rule, exit_rule, rule_spec = crossover
            resolved.requested_strategy_template = "moving_average_crossover"
            resolved.strategy_type = "signal_strategy"
            resolved.entry_rule = entry_rule
            resolved.exit_rule = exit_rule
            resolved.rule_spec = rule_spec
            resolved.applied.append(f"{op}.{target}")
            continue

        if target in _NUMBER_TARGETS:
            if op in {"set", "replace"} and operation.number is not None:
                amount = float(operation.number)
                if target == "capital":
                    resolved.initial_capital = amount
                elif target == "recurring_contribution":
                    resolved.recurring_contribution_amount = amount
                elif target == "fees":
                    fee_rate = supported_cost_rate_value(amount, field_name="fee_rate")
                    if fee_rate is None:
                        resolved.unsupported.append(f"{op}.{target}")
                        continue
                    resolved.fee_rate = fee_rate
                elif target == "slippage":
                    slippage = supported_cost_rate_value(amount, field_name="slippage")
                    if slippage is None:
                        resolved.unsupported.append(f"{op}.{target}")
                        continue
                    resolved.slippage = slippage
                resolved.applied.append(f"set.{target}")
            else:
                resolved.unsupported.append(f"{op}.{target}")
            continue

        if target in _INDICATOR_PARAMETER_TARGETS:
            if op in {"set", "replace"} and operation.number is not None:
                parameter_key = _INDICATOR_PARAMETER_TARGETS[target]
                value: float | int = float(operation.number)
                if parameter_key == "indicator_period":
                    value = int(value)
                    if value <= 0:
                        resolved.unsupported.append(f"{op}.{target}")
                        continue
                resolved.indicator_parameters[parameter_key] = value
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


def _resolved_moving_average_crossover(
    operation: EditOperation,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None:
    if operation.strategy_template != "moving_average_crossover":
        return None
    entry_rule = _validated_moving_average_crossover_rule(operation.entry_rule)
    if entry_rule is None:
        return None
    exit_candidate = operation.exit_rule or opposite_moving_average_crossover_rule(
        entry_rule
    )
    exit_rule = _validated_moving_average_crossover_rule(exit_candidate)
    if exit_rule is None or not _rules_form_opposite_crossover(
        entry_rule=entry_rule,
        exit_rule=exit_rule,
    ):
        return None
    try:
        rule_spec = rule_spec_from_moving_average_crossover_rules(
            entry_rule=entry_rule,
            exit_rule=exit_rule,
        )
    except (TypeError, ValueError):
        return None
    if rule_spec is None:
        return None
    return entry_rule, exit_rule, rule_spec


def _validated_moving_average_crossover_rule(
    value: Any,
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if value.get("type") != "moving_average_crossover":
        return None
    fast_indicator = str(value.get("fast_indicator") or "").strip().lower()
    slow_indicator = str(value.get("slow_indicator") or "").strip().lower()
    direction = str(value.get("direction") or "").strip().lower()
    if fast_indicator not in {"sma", "ema"} or slow_indicator not in {"sma", "ema"}:
        return None
    if direction not in {"bullish", "bearish"}:
        return None
    try:
        fast_period = int(value["fast_period"])
        slow_period = int(value["slow_period"])
    except (KeyError, TypeError, ValueError):
        return None
    if fast_period <= 0 or slow_period <= 0 or fast_period >= slow_period:
        return None
    return {
        "type": "moving_average_crossover",
        "fast_indicator": fast_indicator,
        "fast_period": fast_period,
        "slow_indicator": slow_indicator,
        "slow_period": slow_period,
        "direction": direction,
    }


def _rules_form_opposite_crossover(
    *,
    entry_rule: dict[str, Any],
    exit_rule: dict[str, Any],
) -> bool:
    shared_fields = {
        "fast_indicator",
        "fast_period",
        "slow_indicator",
        "slow_period",
    }
    if any(entry_rule.get(field) != exit_rule.get(field) for field in shared_fields):
        return False
    return (
        entry_rule.get("direction") == "bullish"
        and exit_rule.get("direction") == "bearish"
    )


def resolved_asset_operation_symbols(
    symbols: list[str],
    *,
    asset_symbol_resolver: Callable[[str], str | None] | None,
) -> list[str]:
    """Resolve asset-operation values through the materializer's symbol path."""

    resolved_symbols: list[str] = []
    for symbol in symbols:
        raw_symbol = str(symbol or "").strip()
        if not raw_symbol:
            continue
        matched = False
        for candidate in _operation_symbol_candidates(raw_symbol):
            try:
                resolved_symbol = (
                    asset_symbol_resolver(candidate) if asset_symbol_resolver else None
                )
            except Exception:
                resolved_symbol = None
            if resolved_symbol:
                resolved_symbols.extend(normalized_asset_symbols([resolved_symbol]))
                matched = True
                # A slash-delimited pair that resolves as a single asset
                # (e.g. BTC/USD) must not also be split into its legs.
                if candidate == raw_symbol:
                    break
        if not matched:
            resolved_symbols.extend(normalized_asset_symbols([raw_symbol]))
    return resolved_symbols


def _operation_symbol_candidates(raw_symbol: str) -> list[str]:
    if "/" in raw_symbol:
        candidates = [
            raw_symbol,
            *(part.strip() for part in raw_symbol.split("/") if part.strip()),
        ]
    else:
        candidates = [raw_symbol]
    return list(dict.fromkeys(candidates))
