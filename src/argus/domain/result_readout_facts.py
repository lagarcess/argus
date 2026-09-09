"""Project executed plan facts for readers without rewriting retained records."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from argus.domain.dca_capital import DcaCapitalError, dca_capital_plan_from_config
from argus.domain.result_figures import with_result_figures


def engine_config_from_snapshot(config_snapshot: object) -> dict[str, Any]:
    """Unwrap the direct config or the agent's retained execution config.

    The direct path stores the engine config itself. The agent envelope carries
    it in resolved_parameters; the run builder also lifts that copy to the root.
    The retained engine config wins over the surrounding descriptive fields.
    """
    snapshot = _mapping(config_snapshot)
    resolved = _mapping(snapshot.get("resolved_parameters"))
    envelope = {**snapshot, **resolved}
    # Direct engine fields outrank descriptive parameters too. Otherwise the
    # normalized zero seed masks a legacy engine's contribution on a later read.
    return {**resolved, **snapshot, **_mapping(envelope.get("engine_config"))}


def result_readout_config(config_snapshot: Any) -> Any:
    """Derive the existing readout slots from the same plan the engine reads."""
    config = deepcopy(config_snapshot)
    if not isinstance(config, dict):
        return config
    engine = engine_config_from_snapshot(config)
    if engine.get("template") != "dca_accumulation":
        return config
    try:
        plan = dca_capital_plan_from_config(engine)
    except DcaCapitalError:
        # Historical records must remain readable. Publication separately uses
        # the same plan reader as a required completeness guard and refuses.
        return config
    config["resolved_parameters"] = {
        **_mapping(config.get("resolved_parameters")),
        "starting_capital": plan.starting_capital,
        "recurring_contribution": plan.contribution,
        "cadence": plan.period,
    }
    return config


def with_result_readout_facts(fact_bank: Any) -> Any:
    """Project a stored bank at the reader boundary, leaving its source intact."""
    if not isinstance(fact_bank, dict):
        return fact_bank
    public = dict(fact_bank)
    if "config_snapshot" in public:
        public["config_snapshot"] = result_readout_config(public["config_snapshot"])
    return with_result_figures(public)


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
