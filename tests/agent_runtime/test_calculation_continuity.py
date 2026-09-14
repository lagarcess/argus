"""Explicit edits derive a new computation from the stored calculation."""

import pytest
from argus.agent_runtime import calculated_answer as ca
from argus.domain.calculation_turn_facts import (
    calculation_turn_facts,
    calculation_turn_history_text,
)
from argus.domain.calculations.answer_request import AnswerCalculation

from tests.agent_runtime.test_calculated_answer import LOAN, USER, _voice
from tests.test_calculation_turn_history import payment_card


def test_a_changed_share_reuses_the_stored_payment_and_its_page(monkeypatch):
    card = payment_card()
    metadata = {
        "tool_result_cards": [card.model_dump(mode="json")],
        "answer_text_template": {"cards": {"lease": card.artifact_id}},
    }
    history = [
        {
            "role": "assistant",
            "content": calculation_turn_history_text(
                calculation_turn_facts(metadata), "Prior calculation."
            ),
        }
    ]
    request = AnswerCalculation.model_validate(
        {
            "name": "lease",
            "kind": card.tool_name,
            "solve_for": "monthly_income",
            "prior_artifact_id": card.artifact_id,
            "updated_fields": ["ratio_pct"],
            "inputs": [{"name": "ratio_pct", "value": 15, "source": "user"}],
        }
    )
    _voice(
        monkeypatch,
        [
            ca.CalculatedVoicedAnswer(
                lead="Required income: {{monthly_income}}.", calculations=[request]
            )
        ],
    )
    result = ca.calculated_answer(
        message="Use 15%, keeping the same payment.",
        language="en",
        user=USER,
        notes=[],
        history=history,
    )
    assert result is not None and result.question_field is None
    updated = result.patch["final_response_payload"]["tool_result_cards"][0]
    assert (
        updated["arguments"]["monthly_debt_payments"]
        == card.arguments["monthly_debt_payments"]
    )
    assert (
        updated["arguments"]["sources"]["monthly_debt_payments"]
        == card.arguments["sources"]["monthly_debt_payments"]
    )
    assert updated["outcome"]["result"]["monthly_income"] == pytest.approx(1129 / 0.15)
    assert "7,526.67" in result.answer_text
    assert updated["artifact_id"] != card.artifact_id


def test_pending_reply_can_explicitly_change_a_known_input(monkeypatch):
    requests = [
        AnswerCalculation(
            kind="time_value",
            solve_for="payment",
            inputs=[*LOAN, {"name": "periods", "value": None, "source": "user"}],
        )
    ]
    pending = {
        "calculations": [r.model_dump(mode="json") for r in requests],
        "requested_fields": ["periods"],
    }
    reply = AnswerCalculation.model_validate(
        {
            "kind": "time_value",
            "solve_for": "payment",
            "updated_fields": ["present_value"],
            "inputs": [
                {"name": "present_value", "value": 150000, "source": "user"},
                {"name": "periods", "value": 48, "source": "user"},
            ],
        }
    )
    completed = ca.completed_pending(pending, [reply], [])
    values = {item.name: item.value for item in completed[0].inputs}
    assert values["present_value"] == 150000
    assert values["periods"] == 48
    assert values["annual_rate_pct"] == 14


def test_unknown_prior_artifact_never_computes_an_invented_replacement(monkeypatch):
    request = AnswerCalculation.model_validate(
        {
            "kind": "time_value",
            "prior_artifact_id": "missing",
            "solve_for": "payment",
            "inputs": [*LOAN, {"name": "periods", "value": 48, "source": "user"}],
        }
    )
    _voice(
        monkeypatch,
        [ca.CalculatedVoicedAnswer(lead="Payment {{payment}}", calculations=[request])],
    )
    result = ca.calculated_answer(
        message="Use 48 months", language="en", user=USER, notes=[], history=[]
    )
    assert result is None


def test_conversation_artifact_references_never_enter_shared_research_cache():
    from argus.agent_runtime.research_grounded import _cache_ttl
    from argus.domain.research.contracts import ResearchPacket, ResearchSource

    packet = ResearchPacket(
        answer_markdown="Use the earlier calculation.",
        sources=(ResearchSource(url="https://example.com/rate"),),
        calculations=({"kind": "debt_to_income", "prior_artifact_id": "private-card"},),
    )
    assert (
        _cache_ttl(
            packet, withheld=False, question_kind="current_external", closed_period=False
        )
        is None
    )


def test_recalculation_keeps_the_stored_asset_when_the_model_restates_another():
    from argus.agent_runtime.answer_calculation import resolve_calculation
    from argus.domain.capability_registry import get_tool_catalog

    request = AnswerCalculation(
        kind="price_multiple",
        solve_for="multiple",
        updated_fields=["price"],
        inputs=[
            {"name": "symbol", "value": "MSFT", "source": "user"},
            {"name": "price", "value": 150, "source": "user"},
        ],
    )
    result = resolve_calculation(
        request,
        catalog=get_tool_catalog(),
        retrieved=[],
        currency="DOP",
        subject_symbol="MSFT",
        market_close=lambda _: pytest.fail("stored inputs need no lookup"),
        notes=[],
        prior_arguments={
            "symbol": "AAPL",
            "price": 100,
            "per_share": 5,
            "currency": "USD",
        },
    )
    assert result.arguments["symbol"] == "AAPL"
    assert result.arguments["currency"] == "USD"
    assert result.arguments["price"] == 150
