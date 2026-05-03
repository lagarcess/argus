from __future__ import annotations

from typing import Any

from argus.agent_runtime.capabilities.contract import CapabilityContract
from argus.agent_runtime.stages.interpret import StageResult
from argus.agent_runtime.state.models import RunState, StrategySummary


def confirm_stage(*, state: RunState, contract: CapabilityContract) -> StageResult:
    strategy = _strategy_payload(state.candidate_strategy_draft)
    missing_required_fields = _missing_required_fields(strategy=strategy, contract=contract)
    if missing_required_fields:
        return StageResult(
            outcome="needs_clarification",
            stage_patch={
                "assistant_prompt": None,
                "missing_required_fields": missing_required_fields,
            },
        )

    optional_parameters = _resolve_optional_parameters(
        contract=contract,
        optional_parameter_status=state.optional_parameter_status,
    )
    confirmation_payload = {
        "strategy": strategy,
        "optional_parameters": optional_parameters,
    }

    return StageResult(
        outcome="await_approval",
        stage_patch={
            "confirmation_payload": confirmation_payload,
            "assistant_prompt": _build_confirmation_prompt(
                contract=contract,
                strategy=strategy,
                optional_parameters=optional_parameters,
            ),
        },
    )


def _strategy_payload(strategy: StrategySummary | dict[str, Any]) -> dict[str, Any]:
    if isinstance(strategy, StrategySummary):
        return strategy.model_dump(mode="python")
    return dict(strategy)


def _missing_required_fields(
    *,
    strategy: dict[str, Any],
    contract: CapabilityContract,
) -> list[str]:
    missing_fields: list[str] = []
    for field_name in contract.required_fields:
        value = strategy.get(field_name)
        if isinstance(value, list):
            if not value:
                missing_fields.append(field_name)
            continue
        if value is None or value == "":
            missing_fields.append(field_name)
    return missing_fields


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


def _build_confirmation_prompt(
    *,
    contract: CapabilityContract,
    strategy: dict[str, Any],
    optional_parameters: dict[str, dict[str, Any]],
) -> str:
    strategy_type = _resolve_strategy_type(strategy, optional_parameters)
    summary = _plain_language_strategy_summary(
        strategy=strategy,
        optional_parameters=optional_parameters,
        strategy_type=strategy_type,
    )
    required_lines = []
    for field_name in contract.required_fields:
        field_description = contract.describe_field(field_name)
        label = (
            field_description.label
            if field_description is not None
            else field_name.replace("_", " ").title()
        )
        required_lines.append(f"{label}: {_format_value(strategy.get(field_name))}")

    user_selected_lines = []
    defaulted_lines = []
    for field_name, parameter in optional_parameters.items():
        entry = (
            f"{parameter.get('label')}: {_format_value(parameter.get('value'))} "
            f"({parameter.get('source')}; {parameter.get('description')})"
        )
        if parameter.get("source") == "user":
            user_selected_lines.append(entry)
        else:
            defaulted_lines.append(entry)

    required_summary = "; ".join(required_lines)
    user_selected_summary = (
        ", ".join(user_selected_lines) if user_selected_lines else "none"
    )
    defaulted_summary = ", ".join(defaulted_lines) if defaulted_lines else "none"
    return (
        "Please confirm this backtest.\n"
        f"{summary}\n"
        f"Required inputs: {required_summary}\n"
        f"User-selected optional parameters: {user_selected_summary}\n"
        f"Default assumptions: {defaulted_summary}"
    )


def _plain_language_strategy_summary(
    *,
    strategy: dict[str, Any],
    optional_parameters: dict[str, dict[str, Any]],
    strategy_type: str,
) -> str:
    assets = _asset_label(strategy.get("asset_universe"))
    date_range = _format_value(strategy.get("date_range"))
    strategy_type_label = _strategy_type_label(strategy_type)

    if strategy_type == "buy_and_hold":
        return (
            f"Argus is about to run a backtest for {assets} "
            f"as a {strategy_type_label} strategy over {date_range}."
        )

    if strategy_type == "dca_accumulation":
        cadence = _resolved_cadence(strategy, optional_parameters)
        cadence_phrase = f" on a {cadence} cadence" if cadence is not None else ""
        return (
            f"Argus is about to run a backtest for {assets} "
            f"as a {strategy_type_label} strategy{cadence_phrase} over {date_range}."
        )

    entry_logic = _format_value(strategy.get("entry_logic"))
    exit_logic = _format_value(strategy.get("exit_logic"))
    return (
        f"Argus is about to run a backtest for {assets} "
        f"as an {strategy_type_label} strategy, entering on {entry_logic}, exiting on {exit_logic}, "
        f"over {date_range}."
    )


def _resolve_strategy_type(
    strategy: dict[str, Any],
    optional_parameters: dict[str, dict[str, Any]],
) -> str:
    explicit_strategy_type = strategy.get("strategy_type")
    if isinstance(explicit_strategy_type, str) and explicit_strategy_type:
        return explicit_strategy_type

    extra_parameters = strategy.get("extra_parameters")
    if isinstance(extra_parameters, dict):
        nested_strategy_type = extra_parameters.get("strategy_type")
        if isinstance(nested_strategy_type, str) and nested_strategy_type:
            return nested_strategy_type
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


def _strategy_type_label(strategy_type: str) -> str:
    labels = {
        "buy_and_hold": "buy-and-hold",
        "dca_accumulation": "DCA accumulation",
        "indicator_threshold": "indicator threshold",
    }
    return labels.get(strategy_type, strategy_type.replace("_", " "))


def _asset_label(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "the selected asset"
    if value is None or value == "":
        return "the selected asset"
    return str(value)


def _format_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "none provided"
    if value is None or value == "":
        return "none provided"
    return str(value)
