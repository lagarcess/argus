"""The silent anti-abuse ceiling on guest compute turns.

Conversation is free and reports no limit; a guest's turns still count against
a visitor-keyed daily ceiling that is never rendered. These tests prove the
entry read, the terminal settlement, the silence in ``GET /me/usage``, and
that the refusal-log observer and the ceiling settlement fire on the same
terminal now that both lanes hook it.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from argus.api.chat import refusal_evidence
from argus.api.chat.guest_compute_ceiling import guest_compute_settlement
from argus.api.guest_access import (
    AccountContext,
    guest_capabilities,
    registered_account_context,
)
from argus.domain.store import utcnow
from argus.domain.usage_limits import (
    GUEST_COMPUTE_CEILING_RESOURCE,
    GUEST_COMPUTE_DAILY_CEILING,
)

from tests.test_allowance_accounting import (
    _assistant_settlements,
    _configure_guest_account,
    _FakeVisitorClient,
    client,
    mock_gateway,
)

__all__ = ["mock_gateway"]

GUEST_HEADERS = {"Authorization": "Bearer guest-token"}
TURN = {"conversation_id": "conv-1", "message": "Test TSLA dip idea"}


def _guest(mock_gateway, monkeypatch: pytest.MonkeyPatch, *, turns_today: int):
    monkeypatch.setenv("ARGUS_GUEST_ACCESS_ENABLED", "true")
    monkeypatch.setenv("NEXT_PUBLIC_GUEST_ACCESS_ENABLED", "true")
    monkeypatch.setenv("NEXT_PUBLIC_MOCK_AUTH", "false")
    monkeypatch.setenv("ARGUS_MOCK_AUTH", "false")
    workspace = _configure_guest_account(mock_gateway)
    mock_gateway.client = _FakeVisitorClient(
        {GUEST_COMPUTE_CEILING_RESOURCE: turns_today}
    )
    return workspace


def _terminal_message_ids(mock_gateway) -> set[str]:
    ids: set[str] = set()
    for call in mock_gateway.finalize_chat_turn.call_args_list:
        ids.add(call.kwargs["message"].id)
    for call in mock_gateway.create_message.call_args_list:
        if call.kwargs.get("role") == "assistant":
            ids.add("msg-1")
    return ids


def test_guest_turn_settles_one_ceiling_unit_on_the_visitor(
    mock_gateway, monkeypatch: pytest.MonkeyPatch
):
    _guest(mock_gateway, monkeypatch, turns_today=5)

    response = client.post("/api/v1/chat/stream", json=TURN, headers=GUEST_HEADERS)

    assert response.status_code == 200, response.text
    settlements = _assistant_settlements(mock_gateway)
    assert len(settlements) == 1
    assert settlements[0]["resource"] == GUEST_COMPUTE_CEILING_RESOURCE
    assert settlements[0]["limits"] == [("day", GUEST_COMPUTE_DAILY_CEILING)]
    assert settlements[0]["visitor_key"].startswith("visitor:")
    # No allowance meter is consulted: the ceiling is the only counter.
    mock_gateway.check_usage_limits.assert_not_called()


def test_guest_at_the_ceiling_is_refused_at_entry_without_charging(
    mock_gateway, monkeypatch: pytest.MonkeyPatch
):
    _guest(mock_gateway, monkeypatch, turns_today=GUEST_COMPUTE_DAILY_CEILING)

    response = client.post("/api/v1/chat/stream", json=TURN, headers=GUEST_HEADERS)

    assert response.status_code == 429
    assert response.json()["code"] == "too_many_requests"
    assert int(response.headers["Retry-After"]) >= 1
    mock_gateway.create_message.assert_not_called()
    assert _assistant_settlements(mock_gateway) == []


def test_ceiling_never_appears_in_usage(mock_gateway, monkeypatch: pytest.MonkeyPatch):
    _guest(mock_gateway, monkeypatch, turns_today=GUEST_COMPUTE_DAILY_CEILING - 1)
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")

    response = client.get("/api/v1/me/usage", headers=GUEST_HEADERS)

    assert response.status_code == 200
    assert GUEST_COMPUTE_CEILING_RESOURCE not in response.text
    compute = response.json()["allowances"]["compute"]
    assert compute["available_now"] is True
    assert compute["limiting_window"] is None


def test_registered_accounts_and_run_actions_settle_nothing_against_the_ceiling():
    registered = registered_account_context("00000000-0000-0000-0000-000000000052")
    guest = AccountContext(
        kind="guest",
        user_id="00000000-0000-0000-0000-000000000051",
        expires_at=utcnow() + timedelta(days=7),
        capabilities=guest_capabilities(),
    )

    assert (
        guest_compute_settlement(
            registered, is_run_backtest_turn=False, visitor_key="visitor:x"
        )
        is None
    )
    assert (
        guest_compute_settlement(
            guest, is_run_backtest_turn=True, visitor_key="visitor:x"
        )
        is None
    )
    assert guest_compute_settlement(
        guest, is_run_backtest_turn=False, visitor_key="visitor:x"
    ) == {
        "resource": GUEST_COMPUTE_CEILING_RESOURCE,
        "limits": [("day", GUEST_COMPUTE_DAILY_CEILING)],
        "visitor_key": "visitor:x",
    }


def test_refusal_observer_and_ceiling_settlement_fire_on_one_guest_terminal(
    mock_gateway, monkeypatch: pytest.MonkeyPatch
):
    # Two lanes hook the same terminal: the refusal log observes the pair
    # after complete() returns, and the ceiling unit rides the finalize call
    # inside it. One turn must show both, naming the same assistant message.
    observed: list[Any] = []
    monkeypatch.setattr(
        refusal_evidence,
        "persist_refusal_observation",
        lambda *, gateway, observation: observed.append(observation),
    )
    _guest(mock_gateway, monkeypatch, turns_today=0)

    response = client.post("/api/v1/chat/stream", json=TURN, headers=GUEST_HEADERS)

    assert response.status_code == 200, response.text
    settlements = _assistant_settlements(mock_gateway)
    assert [item["resource"] for item in settlements] == [GUEST_COMPUTE_CEILING_RESOURCE]
    assert len(observed) == 1
    assert observed[0].response_message_id in _terminal_message_ids(mock_gateway)
    assert observed[0].request_message_id != observed[0].response_message_id
