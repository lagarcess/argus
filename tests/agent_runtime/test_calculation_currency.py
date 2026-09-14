import pytest
from argus.agent_runtime import answer_calculation as ac
from argus.domain.calculations.answer_request import AnswerCalculation
from argus.domain.capability_registry import get_tool_catalog


@pytest.mark.parametrize("profile", ["DOP", "MXN", "USD"])
def test_unstated_currency_uses_profile_and_is_a_visible_assumption(profile):
    notes = []
    request = AnswerCalculation(
        kind="debt_to_income",
        solve_for="monthly_income",
        inputs=[
            {"name": "monthly_debt_payments", "value": 1129, "source": "user"},
            {"name": "ratio_pct", "value": 15, "source": "user"},
            {"name": "currency", "value": "USD", "source": "assumption"},
        ],
    )
    result = ac.publish_calculations(
        [request],
        template="Income {{monthly_income}}.",
        language="en",
        catalog=get_tool_catalog(),
        retrieved=[],
        currency=profile,
        subject_symbol=None,
        market_close=lambda _: None,
        notes=notes,
    )
    assert result is not None
    card = result.patch["final_response_payload"]["tool_result_cards"][0]
    assert card["arguments"]["currency"] == profile
    assert card["arguments"]["sources"]["currency"] == {"kind": "assumption"}
    fact = next(f for f in card["presentation"]["inputs"] if f["name"] == "currency")
    assert fact["value"] == profile and fact["source"]["kind"] == "assumption"
    assert {"artifact_id": card["artifact_id"], "name": "currency"} in result.assumptions
    assert ac.CURRENCY_DEFAULTED_REASON_CODE in notes
