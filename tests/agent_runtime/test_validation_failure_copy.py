"""Issue #141: internal reason codes must never render in assistant prose.

The live conversation surfaced "invalid_chronological_date_range does not
define when to buy or sell for NVDA on its own." — a raw enum in user-facing
copy (Response Voice Contract violation) attached to strategy-rule options
for what is actually a date problem.
"""

import pytest
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
        response_intent=_response_intent_with_raw_value(
            "invalid_chronological_date_range"
        ),
        strategy=StrategySummary(asset_universe=["NVDA"]),
    )

    assert prose is not None
    assert "invalid_chronological_date_range" not in prose
    assert "_" not in prose


@pytest.mark.parametrize(
    "raw_value",
    ["User wants to invest $500", "MACD golden cross", "BTC_USDT"],
)
def test_issue_453_generic_raw_value_never_renders_as_subject(
    raw_value: str,
) -> None:
    """This fallback is English compatibility prose and no longer takes a
    language, so there is no bilingual claim to make here.

    It used to be parametrized over `en` and `es-419` with the same English
    expectation in both rows, which read as Spanish coverage and proved nothing
    (#489). The real bilingual property, that the reader sees Spanish, is
    asserted at the seam in `test_workspace_language_prose.py` and at the
    presentation boundary in the frontend suite.
    """

    prose = _unsupported_recovery_fallback(
        response_intent=_response_intent_with_raw_value(raw_value),
        strategy=StrategySummary(asset_universe=["NVDA"]),
    )

    assert prose is not None
    assert raw_value not in prose
    assert "that rule" in prose


def test_uncategorized_constraint_asks_for_the_rule_not_a_capability_limit() -> None:
    """Spec §5 (issue observed as "Argus can't run Backtest WMT directly yet
    for WMT"): a constraint with no category means no rule was recognized, so
    the prose must ask what to test instead of naming the raw text as an
    unsupported capability."""

    intent = _response_intent_with_raw_value("Backtest WMT")
    for constraint in intent["facts"]["unsupported_constraints"]:
        del constraint["category"]

    prose = _unsupported_recovery_fallback(
        response_intent=intent,
        strategy=StrategySummary(asset_universe=["WMT"]),
    )

    assert prose == (
        "What rule should I test for WMT? Which supported direction should I "
        "use: Adjust the strategy rule or Adjust the date range?"
    )


def test_explanation_sentence_never_renders_as_subject() -> None:
    """Observed live: "Argus can't run The requested assumption change needs
    clarification. directly yet." An explanation sentence is internal text,
    not a name; sentence punctuation disqualifies a subject."""

    prose = _unsupported_recovery_fallback(
        response_intent=_response_intent_with_raw_value(
            "The requested assumption change needs clarification."
        ),
        strategy=StrategySummary(asset_universe=["NVDA"]),
    )

    assert prose is not None
    assert "needs clarification" not in prose
    assert "that rule" in prose


def test_chronological_validation_failure_reasks_dates_not_strategy_rule() -> None:
    failure = _launch_validation_failure("invalid_chronological_date_range")

    assert failure["requested_field"] == "date_range"
    assert failure["missing_required_fields"] == ["date_range"]
    constraints = failure["optional_parameter_status"]["unsupported_constraints"]
    assert constraints
    raw_value = constraints[0]["raw_value"]
    assert raw_value != "invalid_chronological_date_range"
    assert "_" not in str(raw_value)
