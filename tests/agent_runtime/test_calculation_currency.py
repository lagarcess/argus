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


@pytest.mark.parametrize("retrieved", [True, False])
def test_explicit_page_currency_keeps_its_source_or_waits_for_evidence(retrieved):
    from argus.domain.research.contracts import ResearchSource

    page = ResearchSource(url="https://example.com/loan", source_date="2026-09-01")
    request = AnswerCalculation(
        kind="debt_to_income",
        solve_for="monthly_income",
        inputs=[
            {"name": "monthly_debt_payments", "value": 1129, "source": "user"},
            {"name": "ratio_pct", "value": 15, "source": "user"},
            {
                "name": "currency",
                "value": "USD",
                "source": "page",
                "source_url": page.url,
            },
        ],
    )
    result = ac.publish_calculations(
        [request],
        template="Income {{monthly_income}}.",
        language="en",
        catalog=get_tool_catalog(),
        retrieved=[page] if retrieved else [],
        currency="DOP",
        subject_symbol=None,
        market_close=lambda _: None,
        notes=[],
    )
    assert result is not None
    if not retrieved:
        assert result.not_looked_up == ("currency",)
        assert not result.patch
        return
    card = ac.card_in(result.patch)
    source = card.arguments["sources"]["currency"]
    assert source["kind"] == "page" and source["url"] == page.url
    assert source["date"] == page.source_date
    currency = next(fact for fact in card.presentation.inputs if fact.name == "currency")
    assert currency.source.kind == "page"
    assert not any(item["name"] == "currency" for item in result.assumptions)
