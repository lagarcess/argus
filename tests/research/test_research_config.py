"""Configuration ladder locks (spec section 3) and the one probed deviation."""

from __future__ import annotations

from argus.domain.research.config import (
    RESEARCH_CONFIG_SPECS,
    capability_class_for_shape,
    research_rail_enabled,
)


def test_three_documented_configurations_are_locked() -> None:
    fast = RESEARCH_CONFIG_SPECS["fast"]
    balanced = RESEARCH_CONFIG_SPECS["balanced"]
    thorough = RESEARCH_CONFIG_SPECS["thorough"]

    # Documented as max_steps=1; probed 2026-08-07 to need 2 because the
    # finance skill load consumes the first step, and 2026-09-10 to need 4
    # when the ticker is not already resolved (a lookup, then the quote; see
    # config.py and docs/reports/evidence/open-the-gates/probes/). Everything
    # else matches the documentation verbatim.
    assert fast.max_steps == 4
    assert fast.max_output_tokens == 1024
    assert fast.tools == ("finance_search",)
    assert fast.model == "openai/gpt-5.6-sol"
    assert fast.background is False

    assert balanced.max_steps == 5
    assert balanced.max_output_tokens == 2048
    assert balanced.tools == ("web_search", "finance_search", "fetch_url")
    assert balanced.reasoning_effort == "low"
    assert balanced.background is False

    assert thorough.max_steps == 10
    assert thorough.max_output_tokens == 4096
    assert thorough.model == "anthropic/claude-opus-4-7"
    assert thorough.tools == ("web_search", "finance_search", "fetch_url")
    assert thorough.background is True


def test_capability_classes_cover_the_five_instrumented_kinds() -> None:
    assert capability_class_for_shape("fast", screening=False) == "fast_quote"
    assert capability_class_for_shape("balanced", screening=False) == "balanced_lookup"
    assert capability_class_for_shape("thorough", screening=False) == "thorough_research"
    assert capability_class_for_shape("thorough", screening=True) == "screening"


def test_flag_defaults_off(monkeypatch) -> None:
    monkeypatch.delenv("ARGUS_RESEARCH_RAIL_ENABLED", raising=False)
    assert research_rail_enabled() is False
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    assert research_rail_enabled() is True


def test_the_balanced_ceiling_leaves_room_for_a_scenario_answer() -> None:
    """Decision 10: a forward-looking answer builds scenarios from cited
    forecasts and targets. The probe took 122s on the balanced configuration
    and every such question timed out at the old 75s ceiling."""
    balanced = RESEARCH_CONFIG_SPECS["balanced"]
    assert balanced.timeout_seconds >= 150.0
