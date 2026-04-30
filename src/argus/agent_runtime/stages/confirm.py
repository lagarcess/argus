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
    summary = _plain_language_strategy_summary(strategy)
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


def _plain_language_strategy_summary(strategy: dict[str, Any]) -> str:
    assets = _format_value(strategy.get("asset_universe"))
    entry_logic = _format_value(strategy.get("entry_logic"))
    exit_logic = _format_value(strategy.get("exit_logic"))
    date_range = _format_value(strategy.get("date_range"))
    return (
        "Argus is about to run a backtest for "
        f"{assets}, entering on {entry_logic}, exiting on {exit_logic}, "
        f"over {date_range}."
    )


def _format_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "none provided"
    if value is None or value == "":
        return "none provided"
    return str(value)
