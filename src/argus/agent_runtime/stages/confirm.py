from __future__ import annotations

from datetime import date
from typing import Any

from argus.agent_runtime.capabilities.contract import CapabilityContract
from argus.agent_runtime.confirmation_artifacts import (
    confirmation_artifact_reference,
    new_confirmation_id,
)
from argus.agent_runtime.stages.interpret import StageResult
from argus.agent_runtime.state.models import RunState, StrategySummary
from argus.agent_runtime.strategy_contract import (
    canonical_strategy_type,
    resolve_date_range,
)
from argus.agent_runtime.strategy_requirements import (
    missing_required_fields_for_strategy,
)
from argus.domain.engine_launch.display import format_data_through_label
from argus.domain.engine_launch.models import LaunchBacktestRequest
from argus.domain.engine_launch.strategies import validate_launch_supported
from argus.domain.market_data.capabilities import (
    fetch_alpaca_market_clock,
    latest_complete_data_adjustment,
    market_data_window_violation,
)
from pydantic import ValidationError


def confirm_stage(*, state: RunState, contract: CapabilityContract) -> StageResult:
    strategy = _strategy_payload(state.candidate_strategy_draft)
    strategy = _strategy_with_latest_complete_data_adjustment(strategy)
    date_limit_recovery = _date_limit_recovery_patch(
        strategy=strategy,
        optional_parameter_status=state.optional_parameter_status,
    )
    if date_limit_recovery is not None:
        return StageResult(
            outcome="needs_clarification",
            stage_patch=date_limit_recovery,
        )

    missing_required_fields = _missing_required_fields(
        strategy=strategy, contract=contract
    )
    if missing_required_fields:
        return StageResult(
            outcome="needs_clarification",
            stage_patch={
                "assistant_prompt": None,
                "missing_required_fields": missing_required_fields,
            },
        )

    carried_unsupported_constraints = _carried_unsupported_constraints_patch(
        state.optional_parameter_status
    )
    if carried_unsupported_constraints is not None:
        return StageResult(
            outcome="needs_clarification",
            stage_patch=carried_unsupported_constraints,
        )

    optional_parameters = _resolve_optional_parameters(
        contract=contract,
        optional_parameter_status=state.optional_parameter_status,
    )
    unsupported_assumption = _unsupported_execution_assumption(
        optional_parameters,
        optional_parameter_status=state.optional_parameter_status,
    )
    if unsupported_assumption is not None:
        return StageResult(
            outcome="needs_clarification",
            stage_patch=unsupported_assumption,
        )
    card_assumptions = _visible_card_assumptions(
        strategy=strategy,
        optional_parameters=optional_parameters,
    )
    strategy_with_assumptions = {
        **strategy,
        "assumptions": card_assumptions,
    }
    confirmation_payload = {
        "strategy": strategy_with_assumptions,
        "optional_parameters": optional_parameters,
    }
    confirmation_id = new_confirmation_id()
    validation_result = _validated_launch_payload(
        state=state,
        confirmation_payload=confirmation_payload,
    )
    if validation_result["outcome"] != "ready_to_confirm":
        stage_patch = {
            key: value
            for key, value in validation_result.items()
            if key not in {"outcome", "launch_payload"}
        }
        return StageResult(
            outcome=str(validation_result["outcome"]),
            stage_patch=stage_patch,
        )
    confirmation_payload["confirmation_id"] = confirmation_id
    confirmation_payload["artifact_id"] = confirmation_id
    confirmation_payload["launch_payload"] = validation_result["launch_payload"]
    confirmation_payload["validation"] = {
        "status": "ready_to_run",
        "executable": True,
        "date_adjusted": _has_data_availability_adjustment(strategy_with_assumptions),
    }
    confirmation_reference = confirmation_artifact_reference(
        confirmation_id=confirmation_id,
        confirmation_payload=confirmation_payload,
    )

    return StageResult(
        outcome="await_approval",
        stage_patch={
            "candidate_strategy_draft": strategy_with_assumptions,
            "confirmation_payload": confirmation_payload,
            "artifact_references": [confirmation_reference.model_dump(mode="python")],
            "assistant_prompt": None,
            "requested_field": None,
            "missing_required_fields": [],
        },
    )


def _validated_launch_payload(
    *,
    state: RunState,
    confirmation_payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        from argus.agent_runtime.stages.execute import _launch_payload

        launch_state = state.model_copy(
            update={"confirmation_payload": confirmation_payload}
        )
        launch_payload = _launch_payload(launch_state)
        request = LaunchBacktestRequest.model_validate(launch_payload)
        validate_launch_supported(request)
    except ValidationError as exc:
        return _launch_validation_failure(_validation_error_code(exc))
    except ValueError as exc:
        return _launch_validation_failure(str(exc))
    except Exception:
        return _launch_validation_failure("missing_rule_group")
    return {
        "outcome": "ready_to_confirm",
        "launch_payload": launch_payload,
        "missing_required_fields": [],
        "requested_field": None,
        "assistant_prompt": None,
    }


def _validation_error_code(exc: ValidationError) -> str:
    text = str(exc)
    for code in (
        "future_end_date",
        "invalid_chronological_date_range",
        "invalid_date_range",
        "capital_amount_required",
        "position_size_required",
    ):
        if code in text:
            return code
    return "missing_rule_group"


def _launch_validation_failure(error_code: str) -> dict[str, Any]:
    if error_code == "future_end_date":
        return {
            "outcome": "needs_clarification",
            "missing_required_fields": ["date_range"],
            "requested_field": "date_range",
            "assistant_prompt": None,
            "optional_parameter_status": _with_unsupported_constraint(
                {},
                {
                    "category": "future_date_window",
                    "raw_value": error_code,
                    "explanation": (
                        "The requested end date is after the latest available "
                        "data Argus can test."
                    ),
                    "simplification_options": [
                        {"label": "Use the latest available date"},
                        {"label": "Choose an earlier end date"},
                        {"label": "Change the date range"},
                    ],
                },
            ),
        }
    if error_code == "indicator_data_insufficient":
        return {
            "outcome": "needs_clarification",
            "missing_required_fields": ["date_range"],
            "requested_field": "date_range",
            "assistant_prompt": None,
            "optional_parameter_status": _with_unsupported_constraint(
                {},
                {
                    "category": "data_window_too_short_for_rule",
                    "raw_value": "selected date range",
                    "explanation": (
                        "The selected window does not provide enough bars for "
                        "the confirmed signal rule."
                    ),
                    "simplification_options": [
                        {"label": "Use a longer date range"},
                        {"label": "Use a shorter indicator period"},
                        {"label": "Choose a simpler supported rule"},
                    ],
                },
            ),
        }
    if error_code in {
        "missing_rule_group",
        "unsupported_rule_operator",
        "unsupported_indicator",
        "unsupported_indicator_threshold",
    }:
        return {
            "outcome": "needs_clarification",
            "missing_required_fields": ["entry_logic"],
            "requested_field": "entry_logic",
            "assistant_prompt": None,
            "optional_parameter_status": _with_unsupported_constraint(
                {},
                {
                    "category": "unsupported_indicator_rule",
                    "raw_value": error_code,
                    "explanation": (
                        "The strategy direction is understandable, but the "
                        "entry rule is not executable as structured."
                    ),
                    "simplification_options": [
                        {"label": "Use a supported RSI threshold rule"},
                        {"label": "Use a supported moving-average crossover"},
                        {"label": "Keep the full idea as a draft"},
                    ],
                },
            ),
        }
    return {
        "outcome": "needs_clarification",
        "missing_required_fields": [],
        "requested_field": None,
        "assistant_prompt": None,
        "optional_parameter_status": _with_unsupported_constraint(
            {},
            {
                "category": "launch_payload_not_executable",
                "raw_value": error_code,
                "explanation": (
                    "One part of the draft is not executable in the current "
                    "backtest engine."
                ),
                "simplification_options": [
                    {"label": "Adjust the strategy rule"},
                    {"label": "Adjust the asset"},
                    {"label": "Adjust the date range"},
                ],
            },
        ),
    }


def _strategy_payload(strategy: StrategySummary | dict[str, Any]) -> dict[str, Any]:
    if isinstance(strategy, StrategySummary):
        return strategy.model_dump(mode="python")
    return dict(strategy)


def _strategy_with_latest_complete_data_adjustment(
    strategy: dict[str, Any],
) -> dict[str, Any]:
    strategy = _strategy_without_data_availability_adjustment(strategy)
    asset_class = _strategy_asset_class(strategy)
    if asset_class is None:
        return strategy
    today = _today()
    try:
        resolved = resolve_date_range(strategy.get("date_range"), today=today)
    except (TypeError, ValueError):
        return strategy
    adjustment = latest_complete_data_adjustment(
        asset_class=asset_class,
        timeframe=_strategy_timeframe(strategy),
        end_date=resolved.end,
        today=today,
        clock=_market_clock_for_strategy(asset_class),
    )
    if adjustment is None:
        return strategy
    extra_parameters = dict(strategy.get("extra_parameters") or {})
    return {
        **strategy,
        "date_range": {
            "start": resolved.start.isoformat(),
            "end": adjustment.through.isoformat(),
        },
        "extra_parameters": {
            **extra_parameters,
            "data_availability_adjustment": adjustment.metadata,
        },
    }


def _strategy_without_data_availability_adjustment(
    strategy: dict[str, Any],
) -> dict[str, Any]:
    extra_parameters = strategy.get("extra_parameters")
    if not isinstance(extra_parameters, dict):
        return strategy
    if "data_availability_adjustment" not in extra_parameters:
        return strategy
    cleaned_extra_parameters = dict(extra_parameters)
    cleaned_extra_parameters.pop("data_availability_adjustment", None)
    return {**strategy, "extra_parameters": cleaned_extra_parameters}


def _today() -> date:
    return date.today()


def _market_clock_for_strategy(asset_class: str) -> Any:
    if asset_class != "equity":
        return None
    try:
        return fetch_alpaca_market_clock()
    except Exception:
        return None


def _missing_required_fields(
    *,
    strategy: dict[str, Any],
    contract: CapabilityContract,
) -> list[str]:
    return missing_required_fields_for_strategy(
        StrategySummary.model_validate(strategy),
        contract=contract,
    )


def _date_limit_recovery_patch(
    *,
    strategy: dict[str, Any],
    optional_parameter_status: dict[str, Any],
) -> dict[str, Any] | None:
    raw_date_range = strategy.get("date_range")
    if raw_date_range in (None, ""):
        return None
    if _is_since_ipo_request(raw_date_range):
        return _recoverable_constraint_patch(
            optional_parameter_status=optional_parameter_status,
            requested_field="date_range",
            missing_required_fields=["date_range"],
            constraint={
                "category": "data_window_unavailable",
                "raw_value": raw_date_range,
                "explanation": (
                    "The requested maximum-history window can reach earlier than "
                    "the launch path can currently test."
                ),
                "simplification_options": [
                    {"label": "Choose a specific start date"},
                    {"label": "Use the maximum available launch window"},
                    {"label": "Use a shorter recent window"},
                ],
            },
        )
    resolved = resolve_date_range(raw_date_range)
    asset_class = _strategy_asset_class(strategy)
    timeframe = _strategy_timeframe(strategy)
    if asset_class is None:
        return None
    violation = market_data_window_violation(
        asset_class=asset_class,
        timeframe=timeframe,
        start_date=resolved.start,
        end_date=resolved.end,
    )
    if violation is None:
        return None
    if violation.code == "provider_history_start_unavailable":
        return _recoverable_constraint_patch(
            optional_parameter_status=optional_parameter_status,
            requested_field="date_range",
            missing_required_fields=["date_range"],
            constraint={
                "category": "data_window_unavailable",
                "raw_value": raw_date_range,
                "explanation": (
                    "The requested start date is earlier than the available "
                    "equity launch window."
                ),
                "simplification_options": [
                    {"label": "Choose a start date in 2016 or later"},
                    {"label": "Use the maximum available launch window"},
                    {"label": "Use a shorter recent window"},
                ],
            },
        )
    if violation.code == "provider_timeframe_unavailable":
        return _recoverable_constraint_patch(
            optional_parameter_status=optional_parameter_status,
            requested_field="timeframe",
            missing_required_fields=["timeframe"],
            constraint={
                "category": "data_timeframe_unavailable",
                "raw_value": timeframe,
                "explanation": (
                    "The selected bar size is not available for this currency "
                    "test in the launch path."
                ),
                "simplification_options": [
                    {"label": "Use 1h bars"},
                    {"label": "Use 4h bars"},
                    {"label": "Use 1D bars"},
                ],
            },
        )
    if violation.code == "kraken_ohlc_window_exceeded":
        return _recoverable_constraint_patch(
            optional_parameter_status=optional_parameter_status,
            requested_field="date_range",
            missing_required_fields=["date_range"],
            constraint={
                "category": "data_window_unavailable",
                "raw_value": raw_date_range,
                "explanation": (
                    "The requested window is too wide for this currency test at "
                    "the selected bar size."
                ),
                "simplification_options": [
                    {"label": "Use a shorter window"},
                    {"label": "Use 4h bars"},
                    {"label": "Use 1D bars"},
                ],
            },
        )
    return None


def _strategy_asset_class(strategy: dict[str, Any]) -> str | None:
    asset_class = strategy.get("asset_class")
    if asset_class in {"equity", "crypto", "currency_pair"}:
        return str(asset_class)
    return None


def _strategy_timeframe(strategy: dict[str, Any]) -> str:
    raw_timeframe = str(strategy.get("timeframe") or "1D").strip()
    return "1D" if raw_timeframe.lower() == "1d" else raw_timeframe.lower()


def _is_since_ipo_request(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    return normalized in {"since_ipo", "max_available", "maximum_available"}


def _resolve_optional_parameters(
    *,
    contract: CapabilityContract,
    optional_parameter_status: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    resolved: dict[str, dict[str, Any]] = {}
    default_values = contract.optional_defaults
    for field_name in default_values:
        source = "default"
        value = default_values[field_name]
        if field_name in optional_parameter_status:
            value = optional_parameter_status[field_name]
            source = "user"
        field_description = contract.describe_field(field_name)
        resolved[field_name] = {
            "value": value,
            "source": source,
            "label": (
                field_description.label
                if field_description is not None
                else field_name.replace("_", " ").title()
            ),
            "description": (
                field_description.description
                if field_description is not None
                else field_name.replace("_", " ")
            ),
        }
    return resolved


def _unsupported_execution_assumption(
    optional_parameters: dict[str, dict[str, Any]],
    *,
    optional_parameter_status: dict[str, Any],
) -> dict[str, Any] | None:
    fees = _parameter_value(optional_parameters, "fees")
    if not _is_zero_assumption(fees):
        return _recoverable_constraint_patch(
            optional_parameter_status=optional_parameter_status,
            requested_field="fees",
            missing_required_fields=["fees"],
            constraint={
                "category": "unsupported_execution_assumption",
                "raw_value": "custom trading fees",
                "explanation": (
                    "The launch engine does not apply custom trading fees yet."
                ),
                "simplification_options": [
                    {"label": "Keep no-fee assumptions"},
                    {"label": "Adjust another strategy detail"},
                    {"label": "Keep the idea as a draft"},
                ],
            },
        )

    slippage = _parameter_value(optional_parameters, "slippage")
    if not _is_zero_assumption(slippage):
        return _recoverable_constraint_patch(
            optional_parameter_status=optional_parameter_status,
            requested_field="slippage",
            missing_required_fields=["slippage"],
            constraint={
                "category": "unsupported_execution_assumption",
                "raw_value": "custom slippage",
                "explanation": (
                    "The launch engine does not simulate custom slippage yet."
                ),
                "simplification_options": [
                    {"label": "Keep no-slippage assumptions"},
                    {"label": "Adjust another strategy detail"},
                    {"label": "Keep the idea as a draft"},
                ],
            },
        )

    engine_options = _parameter_value(optional_parameters, "engine_options")
    if isinstance(engine_options, dict) and engine_options:
        return _recoverable_constraint_patch(
            optional_parameter_status=optional_parameter_status,
            requested_field="engine_options",
            missing_required_fields=["engine_options"],
            constraint={
                "category": "unsupported_execution_assumption",
                "raw_value": "custom engine options",
                "explanation": (
                    "Those engine options are not executable in the current "
                    "launch backtest."
                ),
                "simplification_options": [
                    {"label": "Adjust the strategy rule"},
                    {"label": "Adjust the asset"},
                    {"label": "Adjust the date range"},
                ],
            },
        )
    return None


def _carried_unsupported_constraints_patch(
    optional_parameter_status: dict[str, Any],
) -> dict[str, Any] | None:
    unsupported_constraints = [
        value
        for value in optional_parameter_status.get("unsupported_constraints", [])
        if isinstance(value, dict) and isinstance(value.get("category"), str)
    ]
    if not unsupported_constraints:
        return None
    return {
        "assistant_prompt": None,
        "requested_field": "unsupported_constraints",
        "missing_required_fields": [],
        "optional_parameter_status": {
            **optional_parameter_status,
            "unsupported_constraints": unsupported_constraints,
        },
    }


def _recoverable_constraint_patch(
    *,
    optional_parameter_status: dict[str, Any],
    requested_field: str | None,
    missing_required_fields: list[str],
    constraint: dict[str, Any],
) -> dict[str, Any]:
    return {
        "assistant_prompt": None,
        "requested_field": requested_field,
        "missing_required_fields": missing_required_fields,
        "optional_parameter_status": _with_unsupported_constraint(
            optional_parameter_status,
            constraint,
        ),
    }


def _with_unsupported_constraint(
    optional_parameter_status: dict[str, Any],
    constraint: dict[str, Any],
) -> dict[str, Any]:
    unsupported_constraints = [
        item
        for item in optional_parameter_status.get("unsupported_constraints", [])
        if isinstance(item, dict)
    ]
    return {
        **optional_parameter_status,
        "unsupported_constraints": [*unsupported_constraints, constraint],
    }


def _is_zero_assumption(value: Any) -> bool:
    if value in (None, "", 0, 0.0, "0", "0.0"):
        return True
    try:
        return float(value) == 0.0
    except (TypeError, ValueError):
        return False


def _visible_card_assumptions(
    *,
    strategy: dict[str, Any],
    optional_parameters: dict[str, dict[str, Any]],
) -> list[str]:
    assumptions: list[str] = []
    strategy_type = _resolve_strategy_type(strategy, optional_parameters)
    strategy_capital = _strategy_capital_amount(strategy)
    if strategy_capital is not None:
        if strategy_type == "dca_accumulation":
            assumptions.append(f"${strategy_capital:,.0f} recurring contribution")
        else:
            assumptions.append(f"${strategy_capital:,.0f} starting capital")
    else:
        initial_capital = _parameter_value(optional_parameters, "initial_capital")
        if isinstance(initial_capital, int | float):
            assumptions.append(f"${float(initial_capital):,.0f} starting capital")

    timeframe = _parameter_value(optional_parameters, "timeframe")
    if timeframe:
        assumptions.append(f"{timeframe} bars")

    data_through_assumption = _data_through_assumption(strategy)
    if data_through_assumption:
        assumptions.append(data_through_assumption)

    fees = _parameter_value(optional_parameters, "fees")
    if fees in (0, 0.0, "0", "0.0"):
        assumptions.append("No fees")

    slippage = _parameter_value(optional_parameters, "slippage")
    if slippage in (0, 0.0, "0", "0.0"):
        assumptions.append("No slippage")

    benchmark_assumption = _visible_card_benchmark_assumption(
        strategy=strategy,
        optional_parameters=optional_parameters,
    )
    if benchmark_assumption:
        assumptions.append(benchmark_assumption)
    return assumptions


def _data_through_assumption(strategy: dict[str, Any]) -> str | None:
    adjustment = _data_availability_adjustment(strategy)
    if adjustment is None:
        return None
    return format_data_through_label(adjustment.get("through")) or None


def _has_data_availability_adjustment(strategy: dict[str, Any]) -> bool:
    return _data_availability_adjustment(strategy) is not None


def _data_availability_adjustment(strategy: dict[str, Any]) -> dict[str, Any] | None:
    extra_parameters = strategy.get("extra_parameters")
    if not isinstance(extra_parameters, dict):
        return None
    adjustment = extra_parameters.get("data_availability_adjustment")
    if not isinstance(adjustment, dict):
        return None
    if adjustment.get("kind") not in {
        "latest_complete_daily_data",
        "latest_complete_market_data",
    }:
        return None
    through = adjustment.get("through")
    if not isinstance(through, str):
        return None
    if not _data_adjustment_matches_strategy_end(strategy, through=through):
        return None
    return adjustment


def _data_adjustment_matches_strategy_end(
    strategy: dict[str, Any],
    *,
    through: str,
) -> bool:
    date_range = strategy.get("date_range")
    if not isinstance(date_range, dict):
        return True
    end = date_range.get("end") or date_range.get("to")
    return end in (None, "") or str(end) == through


def _visible_card_benchmark_assumption(
    *,
    strategy: dict[str, Any],
    optional_parameters: dict[str, dict[str, Any]],
) -> str | None:
    for value in (
        _parameter_value(optional_parameters, "benchmark_symbol"),
        strategy.get("comparison_baseline"),
        strategy.get("benchmark_symbol"),
    ):
        if isinstance(value, str) and value.strip():
            return f"Benchmark: {value.strip().upper()}"
    asset_class = strategy.get("asset_class")
    if asset_class == "crypto":
        return "Benchmark: BTC"
    if asset_class == "equity":
        return "Benchmark: SPY"
    return None


def _parameter_value(
    optional_parameters: dict[str, dict[str, Any]],
    field_name: str,
) -> Any:
    parameter = optional_parameters.get(field_name)
    if not isinstance(parameter, dict):
        return None
    return parameter.get("value")


def _strategy_capital_amount(strategy: dict[str, Any]) -> float | None:
    value = strategy.get("capital_amount")
    if isinstance(value, int | float):
        return float(value)
    extra_parameters = strategy.get("extra_parameters")
    if isinstance(extra_parameters, dict):
        for key in ("capital_amount", "recurring_amount", "contribution_amount"):
            nested_value = extra_parameters.get(key)
            if isinstance(nested_value, int | float):
                return float(nested_value)
    return None


def _resolve_strategy_type(
    strategy: dict[str, Any],
    optional_parameters: dict[str, dict[str, Any]],
) -> str:
    explicit_strategy_type = strategy.get("strategy_type")
    if isinstance(explicit_strategy_type, str) and explicit_strategy_type:
        return canonical_strategy_type(
            explicit_strategy_type,
            entry_logic=strategy.get("entry_logic"),
            exit_logic=strategy.get("exit_logic"),
            cadence=strategy.get("cadence"),
        )

    extra_parameters = strategy.get("extra_parameters")
    if isinstance(extra_parameters, dict):
        nested_strategy_type = extra_parameters.get("strategy_type")
        if isinstance(nested_strategy_type, str) and nested_strategy_type:
            return canonical_strategy_type(
                nested_strategy_type,
                entry_logic=strategy.get("entry_logic"),
                exit_logic=strategy.get("exit_logic"),
                cadence=strategy.get("cadence"),
            )
        if extra_parameters.get("cadence"):
            return "dca_accumulation"

    if strategy.get("cadence") or _resolved_cadence(strategy, optional_parameters):
        return "dca_accumulation"
    if strategy.get("entry_logic") or strategy.get("exit_logic"):
        return "indicator_threshold"
    return "buy_and_hold"


def _resolved_cadence(
    strategy: dict[str, Any],
    optional_parameters: dict[str, dict[str, Any]],
) -> str | None:
    cadence = strategy.get("cadence")
    if isinstance(cadence, str) and cadence:
        return cadence

    extra_parameters = strategy.get("extra_parameters")
    if isinstance(extra_parameters, dict):
        nested_cadence = extra_parameters.get("cadence")
        if isinstance(nested_cadence, str) and nested_cadence:
            return nested_cadence

    cadence_payload = optional_parameters.get("cadence")
    if isinstance(cadence_payload, dict):
        cadence_value = cadence_payload.get("value")
        if isinstance(cadence_value, str) and cadence_value:
            return cadence_value
    return None
