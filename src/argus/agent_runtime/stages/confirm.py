from __future__ import annotations

from datetime import date
from typing import Any

from argus.agent_runtime.artifacts.patch_policy import (
    executable_artifact_patch_missing_fields,
)
from argus.agent_runtime.capabilities.contract import CapabilityContract
from argus.agent_runtime.confirmation_artifacts import (
    confirmation_artifact_reference,
    new_confirmation_id,
)
from argus.agent_runtime.coverage_recovery import coverage_recovery_stage_patch
from argus.agent_runtime.stages.interpret import StageResult
from argus.agent_runtime.stages.launch_validation_recovery import (  # noqa: F401
    _launch_validation_failure,
    _tagged_launch_validation_failure,
    _validate_launch_envelope,
    _with_unsupported_constraint,
)
from argus.agent_runtime.state.models import RunState, StrategySummary
from argus.agent_runtime.strategy_contract import (
    canonical_strategy_type,
    resolve_executable_date_range,
)
from argus.agent_runtime.strategy_requirements import (
    missing_required_fields_for_strategy,
)
from argus.domain.backtesting.config import _execution_realism_feature_enabled
from argus.domain.backtesting.confirmation_preflight import (
    materialize_confirmation_strategy,
    prepare_confirmation_launch,
)
from argus.domain.engine_launch.models import (
    LaunchBacktestRequest,
    launch_request_error_code,
)
from argus.domain.engine_launch.strategies import validate_launch_supported
from argus.domain.market_data.capabilities import (
    fetch_alpaca_market_clock,
    latest_complete_data_adjustment,
    market_data_window_violation,
)
from argus.nlp.natural_time import resolve_date_range_intent
from loguru import logger
from pydantic import ValidationError


def confirm_stage(
    *,
    state: RunState,
    contract: CapabilityContract,
    language: str | None = None,
) -> StageResult:
    logger.debug("Confirm stage started")
    strategy = _strategy_payload(state.candidate_strategy_draft)
    strategy = _strategy_with_runtime_language(strategy, language=language)
    strategy = _strategy_with_explicit_date_intent(strategy)
    strategy = _strategy_with_requested_date_range_provenance(strategy)
    strategy = _strategy_without_incompatible_rule_fields(strategy)
    strategy = _strategy_with_latest_complete_data_adjustment(strategy)
    strategy = _strategy_with_requested_date_range_for_preflight(strategy)
    logger.debug(
        "Confirm stage latest complete data adjustment checked",
        strategy_type=strategy.get("strategy_type"),
        asset_class=strategy.get("asset_class"),
    )
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
        strategy=strategy,
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
    confirmation_payload: dict[str, Any] = {
        "strategy": strategy,
        "optional_parameters": optional_parameters,
    }
    edit_disclosure = _popped_edit_disclosure(strategy)
    if edit_disclosure is not None:
        # §3.2: a change the edit turn could not apply is disclosed on the
        # card it produced. Single-use by construction: popped from the
        # persisted strategy so it cannot outlive this transition.
        confirmation_payload["edit_disclosure"] = edit_disclosure
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
            outcome="needs_clarification",
            stage_patch=stage_patch,
        )
    launch_payload = validation_result["launch_payload"]
    coverage_result = _coverage_preflight(
        launch_payload,
        optional_parameter_status=state.optional_parameter_status,
    )
    if coverage_result["outcome"] != "ready_to_confirm":
        return StageResult(
            outcome="needs_clarification",
            stage_patch={
                key: value
                for key, value in coverage_result.items()
                if key not in {"outcome", "launch_payload"}
            },
        )
    launch_payload = dict(coverage_result["launch_payload"])
    canonical_strategy = materialize_confirmation_strategy(
        strategy,
        launch_payload=launch_payload,
    )
    # `assumptions` stays as interpretation produced it: the confirmation card
    # builds its localizable strip from typed facts, never from this dict (#508).
    confirmation_payload["strategy"] = canonical_strategy
    confirmation_payload["confirmation_id"] = confirmation_id
    confirmation_payload["artifact_id"] = confirmation_id
    confirmation_payload["launch_payload"] = launch_payload
    confirmation_payload["validation"] = {
        "status": "ready_to_run",
        "executable": True,
        "date_adjusted": (
            _has_data_availability_adjustment(canonical_strategy)
            or _has_effective_window_adjustment(launch_payload)
        ),
    }
    confirmation_reference = confirmation_artifact_reference(
        confirmation_id=confirmation_id,
        confirmation_payload=confirmation_payload,
    )

    return StageResult(
        outcome="await_approval",
        stage_patch={
            "candidate_strategy_draft": canonical_strategy,
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
    launch_payload: dict[str, Any] = {}
    try:
        from argus.agent_runtime.stages.execute import _launch_payload

        launch_state = state.model_copy(
            update={"confirmation_payload": confirmation_payload}
        )
        launch_payload = _launch_payload(
            launch_state,
            language=_confirmation_payload_language(confirmation_payload),
        )
        request = LaunchBacktestRequest.model_validate(launch_payload)
        validate_launch_supported(request)
        _validate_launch_envelope(request)
    except ValidationError as exc:
        return _tagged_launch_validation_failure(_validation_error_code(exc))
    except ValueError as exc:
        error_code = str(exc)
        raw_value = (
            launch_payload.get("capital_amount")
            if error_code == "invalid_starting_capital"
            else launch_payload.get("timeframe")
        )
        return _tagged_launch_validation_failure(
            error_code,
            raw_value=raw_value,
            optional_parameter_status=state.optional_parameter_status,
            capital_role=(
                "recurring_contribution"
                if error_code == "invalid_starting_capital"
                and launch_payload.get("strategy_type") == "dca_accumulation"
                else None
            ),
        )
    except Exception:
        return _tagged_launch_validation_failure("missing_rule_group")
    return {
        "outcome": "ready_to_confirm",
        "launch_payload": launch_payload,
        "missing_required_fields": [],
        "requested_field": None,
        "assistant_prompt": None,
    }


def _coverage_preflight(
    launch_payload: dict[str, Any],
    *,
    optional_parameter_status: dict[str, Any],
) -> dict[str, Any]:
    preflight = prepare_confirmation_launch(launch_payload)
    if preflight.outcome == "coverage_failure":
        return coverage_recovery_stage_patch(
            error_code=preflight.error_code or "market_data_unavailable",
            launch_payload=launch_payload,
            optional_parameter_status=optional_parameter_status,
        )
    if preflight.outcome != "ready_to_confirm" or preflight.launch_payload is None:
        return _launch_validation_failure(preflight.error_code or "missing_rule_group")
    return {
        "outcome": "ready_to_confirm",
        "launch_payload": preflight.launch_payload,
    }


def _strategy_with_requested_date_range_for_preflight(
    strategy: dict[str, Any],
) -> dict[str, Any]:
    extra_parameters = strategy.get("extra_parameters")
    if not isinstance(extra_parameters, dict):
        return strategy
    requested = extra_parameters.get("requested_date_range")
    effective = extra_parameters.get("effective_date_range")
    current = strategy.get("date_range")
    if not all(
        _is_structured_date_range(value) for value in (requested, effective, current)
    ):
        return strategy
    artifact_patch = extra_parameters.get("artifact_patch")
    changed_fields = (
        artifact_patch.get("changed_fields") if isinstance(artifact_patch, dict) else []
    )
    if isinstance(changed_fields, list) and "date_range" in changed_fields:
        return strategy
    if current != effective:
        return strategy
    return {**strategy, "date_range": dict(requested)}


def _strategy_with_requested_date_range_provenance(
    strategy: dict[str, Any],
) -> dict[str, Any]:
    extra_parameters = dict(strategy.get("extra_parameters") or {})
    artifact_patch = extra_parameters.get("artifact_patch")
    changed_fields = (
        artifact_patch.get("changed_fields") if isinstance(artifact_patch, dict) else []
    )
    date_was_edited = isinstance(changed_fields, list) and (
        "date_range" in changed_fields
    )
    current = strategy.get("date_range")
    requested = extra_parameters.get("requested_date_range")
    effective = extra_parameters.get("effective_date_range")
    preserve_existing = (
        not date_was_edited
        and _is_structured_date_range(requested)
        and _is_structured_date_range(effective)
        and current == effective
    )
    if not preserve_existing:
        try:
            resolved = resolve_executable_date_range(
                current,
                extra_parameters=extra_parameters,
                today=_today(),
            )
        except (TypeError, ValueError):
            return strategy
        requested = resolved.payload
    extra_parameters["requested_date_range"] = dict(requested)
    if date_was_edited:
        extra_parameters.pop("effective_date_range", None)
    return {**strategy, "extra_parameters": extra_parameters}


def _is_structured_date_range(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("start"), str)
        and isinstance(value.get("end"), str)
    )


def _has_effective_window_adjustment(launch_payload: dict[str, Any]) -> bool:
    coverage = launch_payload.get("coverage_preflight")
    return isinstance(coverage, dict) and coverage.get("outcome") == ("adjusted_coverage")


def _confirmation_payload_language(confirmation_payload: dict[str, Any]) -> str:
    strategy = confirmation_payload.get("strategy")
    if not isinstance(strategy, dict):
        return "en"
    extra_parameters = strategy.get("extra_parameters")
    if not isinstance(extra_parameters, dict):
        return "en"
    language = str(extra_parameters.get("language") or "").strip()
    return language or "en"


def _validation_error_code(exc: ValidationError) -> str:
    return launch_request_error_code(exc)


def _strategy_payload(strategy: StrategySummary | dict[str, Any]) -> dict[str, Any]:
    if isinstance(strategy, StrategySummary):
        return strategy.model_dump(mode="python")
    return dict(strategy)


def _popped_edit_disclosure(strategy: dict[str, Any]) -> dict[str, Any] | None:
    extra_parameters = strategy.get("extra_parameters")
    if not isinstance(extra_parameters, dict):
        return None
    disclosure = extra_parameters.pop("edit_disclosure", None)
    if not isinstance(disclosure, dict):
        return None
    unapplied = disclosure.get("unapplied")
    note = str(disclosure.get("note") or "").strip()
    if not isinstance(unapplied, list):
        unapplied = []
    if not unapplied and not note:
        return None
    cleaned: dict[str, Any] = {
        "unapplied": [
            {
                "op": str(entry.get("op") or "set"),
                "target": str(entry.get("target") or ""),
                "reason": str(entry.get("reason") or "unsupported_operation"),
            }
            for entry in unapplied
            if isinstance(entry, dict) and str(entry.get("target") or "").strip()
        ],
    }
    if note:
        cleaned["note"] = note
    if not cleaned["unapplied"] and "note" not in cleaned:
        return None
    return cleaned


def _strategy_with_runtime_language(
    strategy: dict[str, Any],
    *,
    language: str | None,
) -> dict[str, Any]:
    normalized = str(language or "").strip()
    if not normalized:
        return strategy
    extra_parameters = dict(strategy.get("extra_parameters") or {})
    extra_parameters["language"] = normalized
    return {**strategy, "extra_parameters": extra_parameters}


def _strategy_with_explicit_date_intent(strategy: dict[str, Any]) -> dict[str, Any]:
    extra_parameters = _strategy_extra_parameters(strategy)
    if extra_parameters is None:
        return strategy
    intent = extra_parameters.get("date_range_intent")
    if not isinstance(intent, dict):
        return strategy
    if str(intent.get("kind") or "").strip() == "endpoint_patch":
        return strategy
    field_provenance = extra_parameters.get("field_provenance")
    if not isinstance(field_provenance, dict):
        return strategy
    provenance = str(field_provenance.get("date_range") or "").strip()
    if provenance not in {"explicit_user", "user"}:
        return strategy
    resolved = resolve_date_range_intent(intent, today=_today())
    if resolved is None:
        return strategy
    return {**strategy, "date_range": resolved.payload}


def _strategy_without_incompatible_rule_fields(
    strategy: dict[str, Any],
) -> dict[str, Any]:
    strategy_type = canonical_strategy_type(
        strategy.get("strategy_type"),
        entry_logic=strategy.get("entry_logic"),
        exit_logic=strategy.get("exit_logic"),
        cadence=strategy.get("cadence"),
    )
    if strategy_type != "indicator_threshold":
        return strategy
    cleaned = dict(strategy)
    for key in ("entry_rule", "exit_rule", "rule_spec"):
        cleaned.pop(key, None)
    return cleaned


def _strategy_extra_parameters(strategy: dict[str, Any]) -> dict[str, Any] | None:
    extra_parameters = strategy.get("extra_parameters")
    return extra_parameters if isinstance(extra_parameters, dict) else None


def _strategy_with_latest_complete_data_adjustment(
    strategy: dict[str, Any],
) -> dict[str, Any]:
    strategy = _strategy_without_data_availability_adjustment(strategy)
    asset_class = _strategy_asset_class(strategy)
    if asset_class is None:
        return strategy
    today = _today()
    try:
        resolved = resolve_executable_date_range(
            strategy.get("date_range"),
            extra_parameters=_strategy_extra_parameters(strategy),
            today=today,
        )
    except (TypeError, ValueError):
        logger.debug(
            "Confirm stage skipped latest data adjustment after date resolution error",
            asset_class=asset_class,
        )
        return strategy
    logger.debug(
        "Confirm stage latest data adjustment started",
        asset_class=asset_class,
        timeframe=_strategy_timeframe(strategy),
        end_date=resolved.end.isoformat(),
    )
    adjustment = latest_complete_data_adjustment(
        asset_class=asset_class,
        timeframe=_strategy_timeframe(strategy),
        end_date=resolved.end,
        today=today,
        clock=_market_clock_for_strategy(asset_class),
    )
    if adjustment is None:
        logger.debug(
            "Confirm stage latest data adjustment not needed",
            asset_class=asset_class,
            end_date=resolved.end.isoformat(),
        )
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
        logger.debug("Confirm stage market clock fetch started", asset_class=asset_class)
        clock = fetch_alpaca_market_clock()
        logger.debug(
            "Confirm stage market clock fetch completed", asset_class=asset_class
        )
        return clock
    except Exception:
        logger.opt(exception=True).debug(
            "Confirm stage market clock fetch failed",
            asset_class=asset_class,
        )
        return None


def _missing_required_fields(
    *,
    strategy: dict[str, Any],
    contract: CapabilityContract,
) -> list[str]:
    strategy_summary = StrategySummary.model_validate(strategy)
    missing_fields = missing_required_fields_for_strategy(
        strategy_summary,
        contract=contract,
    )
    return executable_artifact_patch_missing_fields(
        strategy=strategy_summary,
        missing_fields=missing_fields,
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
    resolved = resolve_executable_date_range(
        raw_date_range,
        extra_parameters=_strategy_extra_parameters(strategy),
    )
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
    strategy: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    resolved: dict[str, dict[str, Any]] = {}
    default_values = contract.optional_defaults
    for field_name in default_values:
        source = "default"
        value = default_values[field_name]
        strategy_owns_value, strategy_value = _strategy_cost_parameter(
            strategy,
            field_name,
        )
        if strategy_owns_value:
            value = strategy_value
            source = "user"
        elif field_name in optional_parameter_status:
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


def _strategy_cost_parameter(
    strategy: dict[str, Any],
    field_name: str,
) -> tuple[bool, Any]:
    if not _execution_realism_feature_enabled():
        return False, None
    key = {
        "fees": "fee_rate",
        "slippage": "slippage",
    }.get(field_name)
    if key is None:
        return False, None
    extra_parameters = strategy.get("extra_parameters")
    if not isinstance(extra_parameters, dict) or key not in extra_parameters:
        return False, None
    field_provenance = extra_parameters.get("field_provenance")
    if (
        not isinstance(field_provenance, dict)
        or field_provenance.get(key) != "explicit_user"
    ):
        return False, None
    return True, extra_parameters[key]


def _unsupported_execution_assumption(
    optional_parameters: dict[str, dict[str, Any]],
    *,
    optional_parameter_status: dict[str, Any],
) -> dict[str, Any] | None:
    # With execution realism enabled the engine applies fee and slippage
    # assumptions, so nonzero values are supported inputs rather than
    # unsupported constraints.
    execution_costs_supported = _execution_realism_feature_enabled()
    fees = _parameter_value(optional_parameters, "fees")
    if not execution_costs_supported and not _is_zero_assumption(fees):
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
    if not execution_costs_supported and not _is_zero_assumption(slippage):
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


def _is_zero_assumption(value: Any) -> bool:
    if value in (None, "", 0, 0.0, "0", "0.0"):
        return True
    try:
        return float(value) == 0.0
    except (TypeError, ValueError):
        return False


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


def _parameter_value(
    optional_parameters: dict[str, dict[str, Any]],
    field_name: str,
) -> Any:
    parameter = optional_parameters.get(field_name)
    if not isinstance(parameter, dict):
        return None
    return parameter.get("value")
