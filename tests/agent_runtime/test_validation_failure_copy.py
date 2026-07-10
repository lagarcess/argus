"""Issue #141: internal reason codes must never render in assistant prose.

The live conversation surfaced "invalid_chronological_date_range does not
define when to buy or sell for NVDA on its own." — a raw enum in user-facing
copy (Response Voice Contract violation) attached to strategy-rule options
for what is actually a date problem.
"""

from argus.agent_runtime.clarification_contract import _unsupported_recovery_fallback
from argus.agent_runtime.stages.confirm import _launch_validation_failure
from argus.agent_runtime.state.models import StrategySummary


def _response_intent_with_raw_value(raw_value: str) -> dict:
    return {
        "facts": {
            "unsupported_constraints": [
                {
                    "category": "launch_payload_not_executable",
                    "raw_value": raw_value,
                    "explanation": "One part of the draft is not executable.",
                }
            ]
        },
        "options": [
            {"label": "Adjust the strategy rule"},
            {"label": "Adjust the date range"},
        ],
    }


def test_internal_reason_code_never_renders_as_sentence_subject() -> None:
    prose = _unsupported_recovery_fallback(
        language="en",
        response_intent=_response_intent_with_raw_value(
            "invalid_chronological_date_range"
        ),
        strategy=StrategySummary(asset_universe=["NVDA"]),
    )

    assert prose is not None
    assert "invalid_chronological_date_range" not in prose
    assert "_" not in prose


def test_user_phrase_raw_value_still_renders_as_subject() -> None:
    prose = _unsupported_recovery_fallback(
        language="en",
        response_intent=_response_intent_with_raw_value("MACD golden cross"),
        strategy=StrategySummary(asset_universe=["NVDA"]),
    )

    assert prose is not None
    assert "MACD golden cross" in prose


def test_uppercase_underscore_symbol_still_renders_as_subject() -> None:
    """User-typed pair symbols such as BTC_USDT are their own words, not
    internal reason codes, and must keep rendering in the clarifier prose."""

    prose = _unsupported_recovery_fallback(
        language="en",
        response_intent=_response_intent_with_raw_value("BTC_USDT"),
        strategy=StrategySummary(asset_universe=["NVDA"]),
    )

    assert prose is not None
    assert "BTC_USDT" in prose


def test_chronological_validation_failure_reasks_dates_not_strategy_rule() -> None:
    failure = _launch_validation_failure("invalid_chronological_date_range")

    assert failure["requested_field"] == "date_range"
    assert failure["missing_required_fields"] == ["date_range"]
    constraints = failure["optional_parameter_status"]["unsupported_constraints"]
    assert constraints
    raw_value = constraints[0]["raw_value"]
    assert raw_value != "invalid_chronological_date_range"
    assert "_" not in str(raw_value)
