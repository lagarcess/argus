"""Canonical capability registry: truth, typed-field derivations, and containment.

Covers P2.1.a — every derived allow-list reads from the single registry, draft
strategies have no path, and the indicator computes-vs-reachable axes are explicit.
See docs/archive/private-alpha-next-p2.1a-capability-registry-impl.md.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import get_args

import pandas as pd
import pytest
from argus.agent_runtime.llm_interpreter_types import LLMStrategyDraft
from argus.api.chat.strategies import strategy_template_from_run
from argus.api.schemas import StrategyTemplate
from argus.domain import capability_registry as registry
from argus.domain.backtesting.config import ALLOWED_TEMPLATES, validate_backtest_config
from argus.domain.backtesting.signals import _build_signals
from argus.domain.engine_launch.models import LaunchStrategyType
from argus.domain.engine_launch.strategies import normalize_template_name
from argus.domain.indicators import EXECUTABLE_INDICATORS, search_indicators
from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES
from pydantic import TypeAdapter, ValidationError

DRAFT_STRATEGIES = {"momentum_breakout", "trend_follow"}
EXECUTABLE_FIVE = {
    "buy_and_hold",
    "buy_the_dip",
    "rsi_mean_reversion",
    "moving_average_crossover",
    "dca_accumulation",
}


# --- Strategy truth -------------------------------------------------------------------


def test_strategy_status_assignments_are_typed_and_explicit() -> None:
    statuses = {
        template: capability.status
        for template, capability in STRATEGY_CAPABILITIES.items()
    }
    assert {t for t, s in statuses.items() if s == "executable"} == EXECUTABLE_FIVE
    assert {t for t, s in statuses.items() if s == "draft"} == DRAFT_STRATEGIES


def test_buy_the_dip_recorded_as_fixed_parameter() -> None:
    assert STRATEGY_CAPABILITIES["buy_the_dip"].fixed_parameters is True
    # The tunable templates are not flagged fixed.
    assert STRATEGY_CAPABILITIES["rsi_mean_reversion"].fixed_parameters is False
    assert STRATEGY_CAPABILITIES["dca_accumulation"].fixed_parameters is False


def test_executable_and_draft_template_sets() -> None:
    assert registry.EXECUTABLE_TEMPLATES == EXECUTABLE_FIVE
    assert registry.EXECUTABLE_TEMPLATES.isdisjoint(DRAFT_STRATEGIES)


def test_supported_strategy_types_derived_from_executable_strategies() -> None:
    assert registry.SUPPORTED_STRATEGY_TYPES == {
        "buy_and_hold",
        "dca_accumulation",
        "indicator_threshold",
        "signal_strategy",
    }
    # Derivation invariant: exactly the execution types of executable strategies.
    assert registry.SUPPORTED_STRATEGY_TYPES == {
        capability.execution_strategy_type
        for capability in STRATEGY_CAPABILITIES.values()
        if capability.status == "executable" and capability.execution_strategy_type
    }


def test_llm_requested_strategy_template_enum_is_derived_from_registry() -> None:
    template_schema = LLMStrategyDraft.model_json_schema()["properties"].get(
        "requested_strategy_template"
    )
    assert template_schema is not None
    string_schema = next(
        item
        for item in template_schema.get("anyOf", [])
        if item.get("type") == "string"
    )
    assert string_schema.get("enum") == sorted(STRATEGY_CAPABILITIES)
    assert not hasattr(registry, "requested_strategy_template_capability_clause")


# --- Derived allow-lists all read from the registry -----------------------------------


def test_allowed_templates_derived_and_excludes_drafts() -> None:
    assert ALLOWED_TEMPLATES is registry.ALLOWED_TEMPLATES
    assert ALLOWED_TEMPLATES == registry.EXECUTABLE_TEMPLATES | {"signal_strategy"}
    assert DRAFT_STRATEGIES.isdisjoint(ALLOWED_TEMPLATES)


def test_api_strategy_template_is_single_sourced_from_registry() -> None:
    # StrategyTemplate validates against the registry's executable set and publishes its
    # OpenAPI enum from it — no hardcoded Literal to drift.
    adapter = TypeAdapter(StrategyTemplate)
    for template in registry.EXECUTABLE_TEMPLATES:
        assert adapter.validate_python(template) == template
    for template in DRAFT_STRATEGIES | {"totally_unknown"}:
        with pytest.raises(ValidationError):
            adapter.validate_python(template)
    assert adapter.json_schema().get("enum") == sorted(registry.EXECUTABLE_TEMPLATES)


def test_launch_strategy_type_enum_matches_supported_strategy_types() -> None:
    assert set(get_args(LaunchStrategyType)) == registry.SUPPORTED_STRATEGY_TYPES


def test_save_passthrough_uses_registry_executable_set() -> None:
    for template in registry.EXECUTABLE_TEMPLATES:
        run = SimpleNamespace(config_snapshot={"template": template})
        assert strategy_template_from_run(run) == template  # type: ignore[arg-type]
    # Draft / unknown templates fall back to buy_and_hold (never passed through).
    for template in DRAFT_STRATEGIES | {"totally_unknown"}:
        run = SimpleNamespace(config_snapshot={"template": template})
        assert strategy_template_from_run(run) == "buy_and_hold"  # type: ignore[arg-type]


# --- Indicator truth: computes vs reachable-via-template -------------------------------


def test_indicator_template_reflects_reachability() -> None:
    # Reachable via a named supported template.
    assert registry.indicator_template("rsi") == "rsi_mean_reversion"
    assert registry.indicator_template("sma") == "moving_average_crossover"
    # Computes but no named template consumes it (still usable inside a signal rule) -> None.
    assert registry.indicator_template("ema") is None
    assert registry.indicator_template("macd") is None
    assert registry.indicator_template("bbands") is None
    # Catalog-only / does not compute -> None.
    assert registry.indicator_template("atr") is None


def test_reachability_map_is_internally_consistent() -> None:
    for indicator_key, template in registry.INDICATOR_TEMPLATE_REACHABILITY.items():
        # Each reachable indicator must compute (have an execution spec), and its template
        # must be executable.
        assert indicator_key in EXECUTABLE_INDICATORS
        assert template in registry.EXECUTABLE_TEMPLATES
    # Tie the hand-maintained RSI entry to the strategy's actual indicator parameter so
    # the map cannot drift from the rsi_mean_reversion definition (the registry comment
    # claims this relationship; this enforces it).
    rsi_template = registry.INDICATOR_TEMPLATE_REACHABILITY["rsi"]
    indicator_param = STRATEGY_CAPABILITIES[rsi_template].parameters["indicator"]
    assert indicator_param.default == "rsi"
    assert indicator_param.allowed_values == ["rsi"]


def test_discovery_support_status_derived_from_execution_spec_membership() -> None:
    # Computing indicators surface as "executable" in the catalog; draft/discovery
    # indicators (no execution spec) stay "draft_only" -> filtered from the @ picker.
    atr = next(item for item in search_indicators("average true range") if item.key == "atr")
    assert atr.support_status == "draft_only"
    macd = next(item for item in search_indicators("macd") if item.key == "macd")
    assert macd.support_status == "executable"


# --- Containment: draft strategies have NO path ---------------------------------------


@pytest.mark.parametrize("template", sorted(DRAFT_STRATEGIES))
def test_draft_template_rejected_by_config_validation(template: str) -> None:
    with pytest.raises(ValueError, match="unsupported_template"):
        validate_backtest_config({"template": template})


@pytest.mark.parametrize("template", sorted(DRAFT_STRATEGIES))
def test_draft_template_has_no_signal_handler(template: str) -> None:
    data = pd.DataFrame({"close": [10.0, 11.0, 12.0, 11.5, 12.5]})
    with pytest.raises(ValueError, match="unsupported_template"):
        _build_signals({"template": template, "parameters": {}}, data)


@pytest.mark.parametrize("template", sorted(EXECUTABLE_FIVE - {"signal_strategy"}))
def test_executable_templates_pass_config_template_gate(template: str) -> None:
    # The template gate (first check) must accept every executable template. We assert
    # it does not raise unsupported_template specifically (later asset/date checks may
    # raise their own errors, which is fine — we only guard the template allow-list).
    try:
        validate_backtest_config({"template": template})
    except ValueError as exc:
        assert str(exc) != "unsupported_template"
    except KeyError:
        # Missing downstream config keys are expected for this minimal payload.
        pass


# --- Gap fix: explicit launch template normalization (no silent rewrite) ---------------


def test_normalize_template_name_maps_each_strategy_type_explicitly() -> None:
    assert normalize_template_name(SimpleNamespace(strategy_type="buy_and_hold")) == "buy_and_hold"
    assert (
        normalize_template_name(SimpleNamespace(strategy_type="dca_accumulation"))
        == "dca_accumulation"
    )
    assert (
        normalize_template_name(SimpleNamespace(strategy_type="signal_strategy"))
        == "signal_strategy"
    )
    assert (
        normalize_template_name(SimpleNamespace(strategy_type="indicator_threshold"))
        == "rsi_mean_reversion"
    )


def test_normalize_template_name_raises_instead_of_silent_rewrite() -> None:
    with pytest.raises(ValueError, match="unsupported_strategy_type"):
        normalize_template_name(SimpleNamespace(strategy_type="momentum_breakout"))
