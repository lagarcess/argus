"""Deterministic Ready-to-run confirmation materialization for a stored run.

The retest action replays canonical run truth, so the confirmation artifact is
built from the reloaded setup alone: no LLM, research, discovery, or market-data
provider is consulted before the user approves the ordinary confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.confirmation_artifacts import (
    new_confirmation_id,
    validate_confirmation_execution_payload,
)
from argus.agent_runtime.presentation_i18n import confirmation_rule_display_value
from argus.agent_runtime.state.models import StrategySummary
from argus.agent_runtime.strategy_contract import strategy_can_be_approved
from argus.domain.backtesting.config import _execution_realism_feature_enabled
from argus.domain.retest_setup import RetestSetup

_INDICATOR_PARAMETER_KEYS = (
    "indicator",
    "indicator_period",
    "entry_threshold",
    "exit_threshold",
)
# Templates whose entry/exit rules the engine synthesizes for display: the
# executable contract rejects them as launch inputs.
_RULE_FREE_STRATEGY_TYPES = ("buy_and_hold", "dca_accumulation")


@dataclass(frozen=True)
class _RuleProjection:
    entry_rule: dict[str, Any] | None = None
    exit_rule: dict[str, Any] | None = None
    rule_spec: dict[str, Any] | None = None
    indicator_parameters: dict[str, Any] | None = None


def retest_confirmation_payload(
    setup: RetestSetup,
    *,
    language: str = "en",
    confirmation_id: str | None = None,
) -> dict[str, Any] | None:
    """Materialize an executable confirmation payload, or None when unsupported.

    Eligibility and admission call this same function, so an offered retest is
    always one the backend can actually confirm.
    """
    if _costs_the_engine_would_drop(setup):
        # The kill switch idealizes execution, so a costed source run cannot be
        # replayed faithfully; offering it would confirm costs the run ignores.
        return None
    rules = _rule_projection(setup)
    strategy = _strategy_payload(setup, rules=rules, language=language)
    optional_parameters = _optional_parameters(setup)
    launch_payload = _launch_payload(setup, rules=rules, language=language)
    payload: dict[str, Any] = {
        "strategy": strategy,
        "optional_parameters": optional_parameters,
        "launch_payload": launch_payload,
    }
    validation = validate_confirmation_execution_payload(payload)
    if not validation.executable or validation.launch_payload is None:
        return None
    try:
        pending_strategy = StrategySummary.model_validate(strategy)
    except ValueError:
        return None
    if not strategy_can_be_approved(pending_strategy):
        return None

    active_id = confirmation_id or new_confirmation_id()
    payload["launch_payload"] = validation.launch_payload
    payload["confirmation_id"] = active_id
    payload["artifact_id"] = active_id
    payload["validation"] = {
        "status": "ready_to_run",
        "executable": True,
        "date_adjusted": False,
    }
    return payload


def retest_runtime_result(
    confirmation_payload: dict[str, Any],
) -> dict[str, Any]:
    """Shape the payload the shipped confirmation-card projection expects."""
    return {
        "stage_outcome": "await_approval",
        "confirmation_payload": confirmation_payload,
    }


def _costs_the_engine_would_drop(setup: RetestSetup) -> bool:
    realism = setup.execution_realism
    if not isinstance(realism, dict) or not realism.get("enabled"):
        return False
    if _execution_realism_feature_enabled():
        return False
    return _rate(realism.get("fee_bps")) > 0.0 or _rate(realism.get("slippage_bps")) > 0.0


def _rule_projection(setup: RetestSetup) -> _RuleProjection:
    if setup.strategy_type in _RULE_FREE_STRATEGY_TYPES:
        return _RuleProjection()
    if setup.strategy_type == "signal_strategy":
        return _RuleProjection(
            entry_rule=setup.entry_rule,
            exit_rule=setup.exit_rule,
            rule_spec=setup.rule_spec,
        )
    indicator_parameters = {
        key: setup.parameters[key]
        for key in _INDICATOR_PARAMETER_KEYS
        if key in setup.parameters
    }
    if len(indicator_parameters) != len(_INDICATOR_PARAMETER_KEYS):
        # Without canonical indicator truth the rebuilt rules could differ from
        # the run that was actually executed, so the retest is not offered.
        return _RuleProjection()
    period = int(float(indicator_parameters["indicator_period"]))
    indicator = str(indicator_parameters["indicator"])
    return _RuleProjection(
        entry_rule={
            "indicator": indicator,
            "operator": "below",
            "period": period,
            "threshold": float(indicator_parameters["entry_threshold"]),
        },
        exit_rule={
            "indicator": indicator,
            "operator": "above",
            "period": period,
            "threshold": float(indicator_parameters["exit_threshold"]),
        },
        indicator_parameters=indicator_parameters,
    )


def _strategy_payload(
    setup: RetestSetup,
    *,
    rules: _RuleProjection,
    language: str,
) -> dict[str, Any]:
    strategy: dict[str, Any] = {
        "strategy_type": setup.strategy_type,
        "asset_universe": list(setup.symbols),
        "asset_class": setup.asset_class,
        "timeframe": setup.timeframe,
        "date_range": {
            "start": setup.start.isoformat(),
            "end": setup.end.isoformat(),
        },
        "sizing_mode": setup.sizing_mode,
        "capital_amount": setup.capital_amount,
        "position_size": setup.position_size,
        "cadence": setup.cadence,
        "comparison_baseline": setup.benchmark_symbol,
        "entry_rule": rules.entry_rule,
        "exit_rule": rules.exit_rule,
        "rule_spec": rules.rule_spec,
        "extra_parameters": _extra_parameters(setup, rules=rules),
    }
    strategy["entry_logic"] = confirmation_rule_display_value(
        strategy,
        side="entry",
        fallback_value=None,
        language=language,
    )
    strategy["exit_logic"] = confirmation_rule_display_value(
        strategy,
        side="exit",
        fallback_value=None,
        language=language,
    )
    return {key: value for key, value in strategy.items() if value is not None}


def _extra_parameters(
    setup: RetestSetup,
    *,
    rules: _RuleProjection,
) -> dict[str, Any]:
    extra: dict[str, Any] = {}
    if rules.indicator_parameters:
        extra["indicator_parameters"] = dict(rules.indicator_parameters)
    realism = setup.execution_realism
    if isinstance(realism, dict) and realism.get("enabled"):
        extra["fee_rate"] = _rate(realism.get("fee_bps"))
        extra["slippage"] = _rate(realism.get("slippage_bps"))
    return extra


def _optional_parameters(setup: RetestSetup) -> dict[str, dict[str, Any]]:
    contract = build_default_capability_contract()
    defaults = contract.optional_defaults
    overrides: dict[str, Any] = {"timeframe": setup.timeframe}
    if setup.capital_amount is not None:
        overrides["initial_capital"] = setup.capital_amount
    realism = setup.execution_realism
    if isinstance(realism, dict) and realism.get("enabled"):
        overrides["fees"] = _rate(realism.get("fee_bps"))
        overrides["slippage"] = _rate(realism.get("slippage_bps"))
    resolved: dict[str, dict[str, Any]] = {}
    for field_name, default_value in defaults.items():
        description = contract.describe_field(field_name)
        resolved[field_name] = {
            "value": overrides.get(field_name, default_value),
            "source": "user" if field_name in overrides else "default",
            "label": (
                description.label
                if description is not None
                else field_name.replace("_", " ").title()
            ),
            "description": (
                description.description
                if description is not None
                else field_name.replace("_", " ")
            ),
        }
    return resolved


def _launch_payload(
    setup: RetestSetup,
    *,
    rules: _RuleProjection,
    language: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "strategy_type": setup.strategy_type,
        "symbol": setup.symbols[0],
        "symbols": list(setup.symbols),
        "asset_class": setup.asset_class,
        "timeframe": setup.timeframe,
        "date_range": {
            "start": setup.start.isoformat(),
            "end": setup.end.isoformat(),
        },
        "entry_rule": rules.entry_rule,
        "exit_rule": rules.exit_rule,
        "rule_spec": rules.rule_spec,
        "sizing_mode": setup.sizing_mode,
        "capital_amount": setup.capital_amount,
        "position_size": setup.position_size,
        "cadence": setup.cadence,
        "parameters": dict(setup.parameters),
        "risk_rules": [],
        "benchmark_symbol": setup.benchmark_symbol,
        "language": language,
    }
    if setup.execution_realism is not None:
        payload["_execution_realism"] = dict(setup.execution_realism)
    return payload


def _rate(basis_points: Any) -> float:
    try:
        return float(basis_points) / 10000.0
    except (TypeError, ValueError):
        return 0.0
