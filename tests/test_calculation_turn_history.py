"""Stored calculation cards, not remembered prose, own follow-up facts."""

import json
from types import SimpleNamespace

import pytest
from argus.api import state as api_state
from argus.api.message_store import load_runtime_thread_history
from argus.domain.calculations.debt_to_income import get_debt_to_income_declaration
from argus.domain.tool_contracts import ToolCall
from faker import Faker

fake = Faker()


def payment_card():
    declaration = get_debt_to_income_declaration()
    call = ToolCall(
        tool_name=declaration.name,
        call_id=fake.uuid4(),
        arguments={
            "currency": "USD",
            "monthly_debt_payments": 1129,
            "monthly_income": None,
            "ratio_pct": 10,
            "sources": {
                "monthly_debt_payments": {
                    "kind": "page",
                    "title": "Lease quote",
                    "url": "https://example.com/lease",
                    "date": "2026-09-01",
                }
            },
        },
    )
    return declaration.result_card(
        call=call,
        outcome=declaration.invoke_sync(call.arguments),
        artifact_id=fake.uuid4(),
    )


@pytest.mark.parametrize("backend", ["memory", "gateway"])
def test_history_carries_canonical_inputs_results_and_sources(monkeypatch, backend):
    card = payment_card()
    conversation_id = fake.uuid4()
    messages = [
        SimpleNamespace(
            role="assistant",
            content="The payment is unavailable.",
            metadata={
                "tool_result_cards": [card.model_dump(mode="json")],
                "answer_text_template": {"cards": {"lease": card.artifact_id}},
            },
        )
    ]
    monkeypatch.setattr(
        api_state,
        "supabase_gateway",
        SimpleNamespace(list_messages=lambda **_: messages)
        if backend == "gateway"
        else None,
    )
    monkeypatch.setitem(api_state.store.messages, conversation_id, messages)
    history = load_runtime_thread_history(
        user_id=fake.uuid4(), conversation_id=conversation_id
    )
    document = json.loads(history[0].content)
    facts = document["calculation_cards"][0]
    assert facts["artifact_id"] == card.artifact_id
    assert facts["name"] == "lease"
    assert facts["arguments"]["monthly_debt_payments"] == 1129
    assert facts["arguments"]["sources"]["monthly_debt_payments"]["kind"] == "page"
    assert facts["result"]["monthly_income"] == pytest.approx(11290)
    assert "visual" not in facts


def test_invalid_cards_do_not_replace_ordinary_history(monkeypatch):
    conversation_id = fake.uuid4()
    content = fake.sentence()
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    monkeypatch.setitem(
        api_state.store.messages,
        conversation_id,
        [
            SimpleNamespace(
                role="assistant",
                content=content,
                metadata={"tool_result_cards": [{"tool_name": "time_value"}]},
            )
        ],
    )
    assert (
        load_runtime_thread_history(
            user_id=fake.uuid4(), conversation_id=conversation_id
        )[0].content
        == content
    )


def test_failed_lookup_does_not_hide_a_completed_calculation(monkeypatch):
    card = payment_card()
    conversation_id = fake.uuid4()
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    monkeypatch.setitem(
        api_state.store.messages,
        conversation_id,
        [
            SimpleNamespace(
                role="assistant",
                content="The lookup failed but this calculation completed.",
                metadata={
                    "research": {"degraded": {"code": "research_not_grounded"}},
                    "tool_result_cards": [card.model_dump(mode="json")],
                },
            )
        ],
    )
    history = load_runtime_thread_history(
        user_id=fake.uuid4(), conversation_id=conversation_id, drop_failed_lookups=True
    )
    assert len(history) == 1
    assert (
        json.loads(history[0].content)["calculation_cards"][0]["arguments"]
        == card.arguments
    )
