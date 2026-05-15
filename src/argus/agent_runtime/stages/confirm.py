from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from argus.agent_runtime.capabilities.contract import CapabilityContract
from argus.agent_runtime.confirmation_artifacts import (
    confirmation_artifact_reference,
    new_confirmation_id,
)
from argus.agent_runtime.rule_specs import executable_rule_spec_from_strategy
from argus.agent_runtime.stages.interpret import StageResult
from argus.agent_runtime.state.models import RunState, StrategySummary
from argus.agent_runtime.strategy_contract import (
    canonical_strategy_type,
    resolve_date_range,
)
from argus.domain.engine_launch.models import LaunchBacktestRequest
from argus.domain.engine_launch.strategies import validate_launch_supported


def confirm_stage(*, state: RunState, contract: CapabilityContract) -> StageResult:
    strategy = _strategy_payload(state.candidate_strategy_draft)
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
    date_limit_prompt = _date_limit_prompt(strategy)
    if date_limit_prompt is not None:
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "assistant_prompt": date_limit_prompt,
                "requested_field": "date_range",
                "missing_required_fields": ["date_range"],
            },
        )

    optional_parameters = _resolve_optional_parameters(
        contract=contract,
        optional_parameter_status=state.optional_parameter_status,
    )
    unsupported_assumption = _unsupported_execution_assumption(optional_parameters)
    if unsupported_assumption is not None:
        return StageResult(
            outcome="await_user_reply",
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
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "assistant_prompt": validation_result["assistant_prompt"],
                "missing_required_fields": validation_result["missing_required_fields"],
                "requested_field": validation_result["requested_field"],
            },
        )
    confirmation_payload["confirmation_id"] = confirmation_id
    confirmation_payload["artifact_id"] = confirmation_id
    confirmation_payload["launch_payload"] = validation_result["launch_payload"]
    confirmation_payload["validation"] = {
        "status": "ready_to_run",
        "executable": True,
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
            "assistant_prompt": _build_confirmation_prompt(
                contract=contract,
                strategy=strategy_with_assumptions,
                optional_parameters=optional_parameters,
            ),
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


def _launch_validation_failure(error_code: str) -> dict[str, Any]:
    if error_code == "indicator_data_insufficient":
        return {
            "outcome": "needs_clarification",
            "missing_required_fields": ["date_range"],
            "requested_field": "date_range",
            "assistant_prompt": (
                "That rule needs more historical bars than the selected window "
                "can provide. Choose a longer date range, or use a shorter "
                "indicator period so the backtest has enough data to evaluate "
                "the signal."
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
            "assistant_prompt": (
                "I understand the direction, but I need you to define the entry "
                "rule in executable terms before I can make this ready to run. "
                "For example: a percentage move, price above a moving average, "
                "a moving-average crossover, an RSI threshold, a MACD crossover, "
                "or a Bollinger Band touch."
            ),
        }
    return {
        "outcome": "needs_clarification",
        "missing_required_fields": [],
        "requested_field": None,
        "assistant_prompt": (
            "I understand the idea, but one part is not executable yet. Tell me "
            "which rule, asset, or date range you want to adjust and I will keep "
            "the draft intact."
        ),
    }


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
    if _resolve_strategy_type(strategy, {}) == "signal_strategy" and not _has_signal_rule(
        strategy
    ):
        for field_name in ("strategy_thesis", "asset_universe"):
            value = strategy.get(field_name)
            if isinstance(value, list):
                if not value:
                    missing_fields.append(field_name)
                continue
            if value is None or value == "":
                missing_fields.append(field_name)
        missing_fields.append("entry_logic")
        return list(dict.fromkeys(missing_fields))
    for field_name in _required_fields_for_strategy(strategy, contract):
        value = strategy.get(field_name)
        if isinstance(value, list):
            if not value:
                missing_fields.append(field_name)
            continue
        if value is None or value == "":
            missing_fields.append(field_name)
    if _resolve_strategy_type(strategy, {}) == "signal_strategy" and not _has_signal_rule(
        strategy
    ):
        missing_fields.append("entry_logic")
    return missing_fields


def _required_fields_for_strategy(
    strategy: dict[str, Any],
    contract: CapabilityContract,
) -> list[str]:
    strategy_type = _resolve_strategy_type(strategy, {})
    if strategy_type in {"buy_and_hold", "dca_accumulation"}:
        return [
            field_name
            for field_name in contract.required_fields
            if field_name not in {"entry_logic", "exit_logic"}
        ]
    if strategy_type == "signal_strategy":
        return [
            field_name
            for field_name in contract.required_fields
            if field_name != "exit_logic"
        ]
    return list(contract.required_fields)


def _has_signal_rule(strategy: dict[str, Any]) -> bool:
    return executable_rule_spec_from_strategy(strategy) is not None


def _date_limit_prompt(strategy: dict[str, Any]) -> str | None:
    raw_date_range = strategy.get("date_range")
    if raw_date_range in (None, ""):
        return None
    if _is_since_ipo_request(raw_date_range):
        return (
            "Since IPO is longer than the current backtest engine can run for most listed assets. "
            "Argus supports up to 3 years per simulation right now. Do you want to use the latest "
            "3-year window, or choose specific start and end dates?"
        )
    resolved = resolve_date_range(raw_date_range)
    if (resolved.end - resolved.start).days <= 365 * 3:
        return None
    suggested_start = resolved.end - timedelta(days=365 * 3)
    suggestion = (
        f"{_format_date(suggested_start)} - {_format_date(resolved.end)}"
        if suggested_start < resolved.end
        else "a shorter window"
    )
    return (
        "I understand the date range, but it is longer than the current backtest "
        "engine can run. Argus supports up to 3 years per simulation right now. "
        f"Do you want to use {suggestion}, or choose a different start and end date?"
    )


def _is_since_ipo_request(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    return normalized in {"since_ipo", "max_available", "maximum_available"}


def _format_date(value: date) -> str:
    return f"{value.strftime('%B')} {value.day}, {value.year}"


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
) -> dict[str, Any] | None:
    fees = _parameter_value(optional_parameters, "fees")
    if not _is_zero_assumption(fees):
        return {
            "assistant_prompt": (
                "I can show this with no-fee assumptions, but the current backtest "
                "engine does not apply custom trading fees yet. Should I keep no "
                "fees, or adjust another part of the strategy?"
            ),
            "requested_field": "fees",
            "missing_required_fields": ["fees"],
        }

    slippage = _parameter_value(optional_parameters, "slippage")
    if not _is_zero_assumption(slippage):
        return {
            "assistant_prompt": (
                "I can show this with no-slippage assumptions, but the current "
                "backtest engine does not simulate custom slippage yet. Should I "
                "keep no slippage, or adjust another part of the strategy?"
            ),
            "requested_field": "slippage",
            "missing_required_fields": ["slippage"],
        }

    engine_options = _parameter_value(optional_parameters, "engine_options")
    if isinstance(engine_options, dict) and engine_options:
        return {
            "assistant_prompt": (
                "Those engine options are not executable in the current backtest "
                "engine. Tell me the strategy rule, asset, or date range you want "
                "to adjust and I will keep the draft intact."
            ),
            "requested_field": "engine_options",
            "missing_required_fields": ["engine_options"],
        }
    return None


def _is_zero_assumption(value: Any) -> bool:
    if value in (None, "", 0, 0.0, "0", "0.0"):
        return True
    try:
        return float(value) == 0.0
    except (TypeError, ValueError):
        return False


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
    user_selected_lines = []
    assumption_lines = []
    for field_name, parameter in optional_parameters.items():
        entry = _format_optional_assumption(
            field_name=field_name,
            parameter=parameter,
            strategy=strategy,
            strategy_type=strategy_type,
        )
        if entry is None:
            continue
        if parameter.get("source") == "user":
            user_selected_lines.append(entry)
        else:
            assumption_lines.append(entry)

    assumptions = [*user_selected_lines, *assumption_lines]
    assumption_text = f" I will use {', '.join(assumptions)}." if assumptions else ""
    return (
        f"{summary}{assumption_text} Use the Run backtest button on the card "
        "when you are ready, or tell me what to change."
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
        return f"I read this as a {strategy_type_label} backtest for {assets} over {date_range}."

    if strategy_type == "dca_accumulation":
        cadence = _resolved_cadence(strategy, optional_parameters)
        cadence_phrase = f" on a {cadence} cadence" if cadence is not None else ""
        return f"I read this as a {strategy_type_label} backtest for {assets}{cadence_phrase} over {date_range}."

    entry_logic = _format_value(strategy.get("entry_logic"))
    exit_logic = _format_value(strategy.get("exit_logic"))
    article = _article_for(strategy_type_label)
    return (
        f"I read this as {article} {strategy_type_label} backtest for {assets}: "
        f"entry rule: {entry_logic}; exit rule: {exit_logic}; over {date_range}."
    )


def _format_optional_assumption(
    *,
    field_name: str,
    parameter: dict[str, Any],
    strategy: dict[str, Any],
    strategy_type: str,
) -> str | None:
    value = parameter.get("value")
    if field_name == "initial_capital" and isinstance(value, int | float):
        if strategy_type == "dca_accumulation":
            contribution = _strategy_capital_amount(strategy)
            if contribution is not None:
                return f"${contribution:,.0f} recurring contribution"
        return f"${float(value):,.0f} starting capital"
    if field_name == "timeframe" and value:
        return f"{value} bars"
    if field_name == "fees":
        return "no trading fees" if value in (0, 0.0, "0", "0.0") else f"{value} fees"
    if field_name == "slippage":
        return "no slippage" if value in (0, 0.0, "0", "0.0") else f"{value} slippage"
    if field_name == "engine_options":
        return None
    if field_name == "cadence" and strategy_type == "dca_accumulation":
        cadence = _resolved_cadence(strategy, {}) or value
        return f"{cadence} cadence" if cadence else None
    return None


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

    fees = _parameter_value(optional_parameters, "fees")
    if fees in (0, 0.0, "0", "0.0"):
        assumptions.append("No fees")

    slippage = _parameter_value(optional_parameters, "slippage")
    if slippage in (0, 0.0, "0", "0.0"):
        assumptions.append("No slippage")

    asset_class = strategy.get("asset_class")
    if asset_class == "crypto":
        assumptions.append("Benchmark: BTC")
    elif asset_class == "equity":
        assumptions.append("Benchmark: SPY")
    return assumptions


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


def _strategy_type_label(strategy_type: str) -> str:
    labels = {
        "buy_and_hold": "buy-and-hold",
        "dca_accumulation": "DCA accumulation",
        "indicator_threshold": "indicator threshold",
        "signal_strategy": "signal strategy",
    }
    return labels.get(strategy_type, strategy_type.replace("_", " "))


def _article_for(value: str) -> str:
    return "an" if value[:1].lower() in {"a", "e", "i", "o", "u"} else "a"


def _asset_label(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "the selected asset"
    if value is None or value == "":
        return "the selected asset"
    return str(value)


def _format_value(value: Any) -> str:
    if isinstance(value, dict):
        if {"start", "end"}.intersection(value) or {"from", "to"}.intersection(value):
            return resolve_date_range(value).display
        return ", ".join(f"{key}: {nested_value}" for key, nested_value in value.items())
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "none provided"
    if value is None or value == "":
        return "none provided"
    return str(value)
