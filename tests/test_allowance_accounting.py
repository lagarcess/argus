"""Issue #247 allowance-truth contracts.

Message allowance must settle exactly once at the durable terminal product
outcome, not at route entry. Simulation allowance must charge exactly once at
unique durable admission. ``GET /me/usage`` must return hourly and daily
backend truth, with backend-derived ``available_now`` and ``limiting_window``,
for both messages and simulations.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from argus.api import state as api_state
from argus.api.main import app
from argus.api.schemas import Conversation, Message, OnboardingState, User
from argus.domain.backtest_finalization import MemoryBacktestFinalizationGateway
from argus.domain.store import AlphaStore, utcnow
from argus.domain.supabase_gateway import SupabaseGateway
from fastapi.testclient import TestClient

client = TestClient(app)

USER_ID = "00000000-0000-0000-0000-000000000001"


def _profile() -> User:
    now = utcnow()
    return User(
        id=USER_ID,
        email="developer@argus.local",
        username="mock-developer",
        display_name="Mock Developer",
        language="en",
        locale="en-US",
        theme="dark",
        is_admin=True,
        onboarding=OnboardingState(
            completed=True,
            stage="ready",
            language_confirmed=True,
            primary_goal="test_stock_idea",
        ),
        created_at=now,
        updated_at=now,
    )


def _conversation(conversation_id: str = "conv-1") -> Conversation:
    now = utcnow()
    return Conversation(
        id=conversation_id,
        title="New conversation",
        title_source="system_default",
        language="en",
        pinned=False,
        archived=False,
        last_message_preview=None,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def mock_gateway():
    gateway = MagicMock(spec=SupabaseGateway)
    gateway.get_user.return_value = _profile()
    gateway.get_or_create_mock_user.return_value = _profile()
    gateway.get_auth_user_from_token.return_value = {
        "id": USER_ID,
        "email": "developer@argus.local",
    }
    gateway.private_alpha_email_allowed.return_value = True
    gateway.get_conversation.return_value = _conversation()
    gateway.list_messages.return_value = []
    gateway.count_completed_runs.return_value = 1
    gateway.get_latest_completed_run_for_conversation.return_value = None
    gateway.create_message.side_effect = lambda **kwargs: Message(
        id="msg-1",
        conversation_id=kwargs["conversation_id"],
        role=kwargs["role"],
        content=kwargs["content"],
        created_at=utcnow(),
        metadata=kwargs.get("metadata"),
    )
    gateway.get_backtest_job_reservation.return_value = None
    gateway.admit_backtest_job.return_value = {
        "decision": "admitted",
        "job": {"id": "job-admitted-1", "status": "running"},
    }
    gateway.finalize_direct_backtest_job.return_value = {
        "id": "job-admitted-1",
        "status": "succeeded",
    }
    gateway.get_backtest_job.return_value = None
    finalization_store = AlphaStore()
    gateway.finalize_backtest_completion.side_effect = (
        lambda *, finalization: MemoryBacktestFinalizationGateway(
            finalization_store
        ).finalize_backtest_completion(finalization=finalization)
    )
    gateway.finalize_direct_backtest_success.side_effect = (
        lambda *, job_id, finalization: MemoryBacktestFinalizationGateway(
            finalization_store
        ).finalize_backtest_completion(finalization=finalization)
    )
    gateway.get_evidence_capture_by_run.return_value = None
    gateway.create_backtest_evidence_capture.side_effect = (
        lambda *, user_id, captured: captured
    )
    gateway.create_idea.side_effect = lambda *, user_id, idea: idea
    gateway.create_idea_version.side_effect = lambda *, user_id, version: version
    gateway.create_evidence_artifact.side_effect = lambda *, user_id, artifact: artifact
    gateway.get_decision_note_by_artifact.return_value = None
    gateway.update_backtest_run_result_card.side_effect = (
        lambda *,
        user_id,
        run_id,
        conversation_result_card: api_state.store.backtest_runs[run_id].model_copy(
            update={"conversation_result_card": conversation_result_card}
        )
    )
    gateway.mark_result_card_decision_for_run.return_value = None
    with (
        patch("argus.api.state.supabase_gateway", gateway),
        patch("argus.api.dependencies.auth_session_is_active", return_value=True),
    ):
        yield gateway


def _assistant_settlements(gateway: MagicMock) -> list[dict[str, Any]]:
    settlements: list[dict[str, Any]] = []
    for call in gateway.create_message.call_args_list:
        if call.kwargs.get("role") != "assistant":
            continue
        settle = call.kwargs.get("settle_usage")
        if settle is not None:
            settlements.append(dict(settle))
    return settlements


def test_chat_entry_checks_but_never_consumes_message_allowance(mock_gateway):
    response = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": "conv-1", "message": "Test TSLA dip idea"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    mock_gateway.check_and_increment_usage_limits.assert_not_called()
    mock_gateway.check_usage_limits.assert_called_once_with(
        user_id=USER_ID,
        resource="chat_messages",
        limits=[("hour", 60), ("day", 200)],
    )


def test_completed_turn_settles_exactly_one_message_unit_at_terminal(mock_gateway):
    response = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": "conv-1", "message": "Test TSLA dip idea"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    settlements = _assistant_settlements(mock_gateway)
    assert len(settlements) == 1
    assert settlements[0]["resource"] == "chat_messages"
    assert settlements[0]["limits"] == [("hour", 60), ("day", 200)]


def test_runtime_failure_before_terminal_outcome_consumes_zero_message_units(
    monkeypatch: pytest.MonkeyPatch,
    mock_gateway,
):
    from argus.api.routers import agent as agent_router

    async def _failing_stream_agent_turn_events(**_: Any):
        raise RuntimeError("forced runtime infrastructure failure")
        yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr(
        agent_router,
        "stream_agent_turn_events",
        _failing_stream_agent_turn_events,
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": "conv-1", "message": "Test TSLA dip idea"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert "agent_runtime_failure" in response.text
    mock_gateway.check_and_increment_usage_limits.assert_not_called()
    assert _assistant_settlements(mock_gateway) == []


def test_message_quota_exhaustion_rejects_at_entry_without_charging(mock_gateway):
    from argus.domain.supabase_gateway import QuotaExceededError

    mock_gateway.check_usage_limits.side_effect = QuotaExceededError(
        "Quota exceeded for chat_messages (hour)"
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": "conv-1", "message": "hello"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 429
    assert response.json()["code"] == "too_many_requests"
    assert response.headers.get("Retry-After") == "60"
    mock_gateway.check_and_increment_usage_limits.assert_not_called()
    mock_gateway.create_message.assert_not_called()


def test_gateway_owns_an_atomic_admission_operation():
    assert hasattr(SupabaseGateway, "admit_backtest_job"), (
        "Simulation charging must compose with one database-owned admission "
        "operation; a count-then-insert sequence plus a separate usage "
        "increment is not conforming admission."
    )


def test_direct_run_admits_durably_and_never_uses_legacy_increment(
    monkeypatch: pytest.MonkeyPatch,
    mock_gateway,
):
    import pandas as pd
    from argus.domain import engine as domain_engine

    def _fetch(symbol: str, **_: object) -> pd.DataFrame:
        index = pd.to_datetime(
            ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"], utc=True
        )
        close = pd.Series(range(100, 100 + len(index)), index=index, dtype=float)
        return pd.DataFrame(
            {
                "open": close,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 1_000.0,
            },
            index=index,
        )

    monkeypatch.setattr(domain_engine, "fetch_ohlcv", _fetch)

    response = client.post(
        "/api/v1/backtests/run",
        json={
            "template": "buy_and_hold",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "start_date": "2024-01-02",
            "end_date": "2024-01-05",
        },
        headers={
            "Authorization": "Bearer test-token",
            "Idempotency-Key": "direct-admission-truth",
        },
    )

    assert response.status_code == 200
    mock_gateway.check_and_increment_usage_limits.assert_not_called()
    mock_gateway.admit_backtest_job.assert_called_once()
    admission = mock_gateway.admit_backtest_job.call_args.kwargs
    assert admission["operation_scope"] == "backtests.run"
    assert admission["idempotency_key"] == "direct-admission-truth"
    mock_gateway.finalize_direct_backtest_success.assert_called_once()
    success = mock_gateway.finalize_direct_backtest_success.call_args.kwargs
    assert success["job_id"] == "job-admitted-1"
    mock_gateway.finalize_direct_backtest_job.assert_not_called()


def _usage_row(
    resource: str,
    period: str,
    used: int,
    limit: int,
    period_end: str,
) -> dict[str, Any]:
    return {
        "resource": resource,
        "period": period,
        "limit_count": limit,
        "used_count": used,
        "period_end": period_end,
    }


def _mock_usage_rows(
    mock_gateway,
    *,
    hour_rows: list[dict[str, Any]],
    day_rows: list[dict[str, Any]],
) -> None:
    def _list(*, user_id: str, resources: tuple, period: str, at: Any):
        assert user_id == USER_ID
        assert set(resources) == {"chat_messages", "backtest_runs"}
        return hour_rows if period == "hour" else day_rows

    mock_gateway.list_current_usage_counters.side_effect = _list


def test_me_usage_returns_hourly_and_daily_truth_for_both_resources(mock_gateway):
    _mock_usage_rows(
        mock_gateway,
        hour_rows=[
            _usage_row("chat_messages", "hour", 3, 60, "2026-07-21T15:00:00Z"),
            _usage_row("backtest_runs", "hour", 1, 10, "2026-07-21T15:00:00Z"),
        ],
        day_rows=[
            _usage_row("chat_messages", "day", 12, 200, "2026-07-22T00:00:00Z"),
            _usage_row("backtest_runs", "day", 4, 50, "2026-07-22T00:00:00Z"),
        ],
    )

    response = client.get(
        "/api/v1/me/usage", headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 200
    allowances = response.json()["allowances"]
    messages = allowances["messages"]
    backtests = allowances["backtests"]

    assert messages["hour"] == {
        "limit": 60,
        "used": 3,
        "remaining": 57,
        "period_end": "2026-07-21T15:00:00Z",
    }
    assert messages["day"] == {
        "limit": 200,
        "used": 12,
        "remaining": 188,
        "period_end": "2026-07-22T00:00:00Z",
    }
    assert messages["available_now"] is True
    assert messages["limiting_window"] == "hour"

    assert backtests["hour"]["remaining"] == 9
    assert backtests["day"]["remaining"] == 46
    assert backtests["available_now"] is True
    assert backtests["limiting_window"] == "hour"


def test_me_usage_missing_rows_read_zero_without_creating_counters(mock_gateway):
    _mock_usage_rows(mock_gateway, hour_rows=[], day_rows=[])

    response = client.get(
        "/api/v1/me/usage", headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 200
    allowances = response.json()["allowances"]
    for resource_key, hour_limit, day_limit in (
        ("messages", 60, 200),
        ("backtests", 10, 50),
    ):
        allowance = allowances[resource_key]
        assert allowance["hour"]["used"] == 0
        assert allowance["hour"]["limit"] == hour_limit
        assert allowance["hour"]["remaining"] == hour_limit
        assert allowance["day"]["used"] == 0
        assert allowance["day"]["limit"] == day_limit
        assert allowance["day"]["remaining"] == day_limit
        assert allowance["available_now"] is True
        assert allowance["hour"]["period_end"] <= allowance["day"]["period_end"]
    mock_gateway.check_and_increment_usage_limits.assert_not_called()


def test_me_usage_hourly_limited_while_daily_available(mock_gateway):
    _mock_usage_rows(
        mock_gateway,
        hour_rows=[
            _usage_row("chat_messages", "hour", 60, 60, "2026-07-21T15:00:00Z"),
        ],
        day_rows=[
            _usage_row("chat_messages", "day", 90, 200, "2026-07-22T00:00:00Z"),
        ],
    )

    response = client.get(
        "/api/v1/me/usage", headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 200
    messages = response.json()["allowances"]["messages"]
    assert messages["hour"]["remaining"] == 0
    assert messages["day"]["remaining"] == 110
    assert messages["available_now"] is False
    assert messages["limiting_window"] == "hour"


def test_me_usage_daily_exhaustion_limits_across_fresh_hourly_window(mock_gateway):
    _mock_usage_rows(
        mock_gateway,
        hour_rows=[],
        day_rows=[
            _usage_row("chat_messages", "day", 200, 200, "2026-07-22T00:00:00Z"),
        ],
    )

    response = client.get(
        "/api/v1/me/usage", headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 200
    messages = response.json()["allowances"]["messages"]
    assert messages["hour"]["used"] == 0
    assert messages["day"]["remaining"] == 0
    assert messages["available_now"] is False
    assert messages["limiting_window"] == "day"


def test_me_usage_used_beyond_limit_clamps_remaining_to_zero(mock_gateway):
    _mock_usage_rows(
        mock_gateway,
        hour_rows=[],
        day_rows=[
            _usage_row("backtest_runs", "day", 53, 50, "2026-07-22T00:00:00Z"),
        ],
    )

    response = client.get(
        "/api/v1/me/usage", headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 200
    backtests = response.json()["allowances"]["backtests"]
    assert backtests["day"]["used"] == 53
    assert backtests["day"]["remaining"] == 0
    assert backtests["available_now"] is False


# ---------------------------------------------------------------------------
# Direct-run identity and terminal finalization.
# ---------------------------------------------------------------------------


def test_direct_identity_covers_every_execution_field():
    from argus.domain.backtest_admission import (
        direct_run_identity_hash,
        normalize_direct_launch_payload,
    )

    base = {
        "template": "buy_and_hold",
        "asset_class": "equity",
        "symbols": ["AAPL"],
        "start_date": "2024-01-02",
        "end_date": "2024-06-28",
    }

    def identity(payload):
        return direct_run_identity_hash(
            conversation_id=None,
            strategy_id=None,
            normalized_payload=normalize_direct_launch_payload(payload),
        )

    baseline = identity(base)
    for field, changed in (
        ("starting_capital", 250_000),
        ("side", "short"),
        ("allocation_method", "risk_parity"),
    ):
        assert identity({**base, field: changed}) != baseline, (
            f"{field} must participate in the direct-run identity; reusing a "
            "key with a changed execution field is a collision, not a replay."
        )


def test_direct_identity_treats_explicit_defaults_as_the_same_execution():
    from argus.domain.backtest_admission import (
        direct_run_identity_hash,
        normalize_direct_launch_payload,
    )

    base = {
        "template": "buy_and_hold",
        "asset_class": "equity",
        "symbols": ["AAPL"],
        "start_date": "2024-01-02",
        "end_date": "2024-06-28",
    }

    def identity(payload):
        return direct_run_identity_hash(
            conversation_id=None,
            strategy_id=None,
            normalized_payload=normalize_direct_launch_payload(payload),
        )

    baseline = identity(base)
    for field, explicit_default in (
        ("side", "long"),
        ("starting_capital", 1000),
        ("starting_capital", 1000.0),
        ("allocation_method", "equal_weight"),
        ("timeframe", "1D"),
        ("timeframe", "1d"),
    ):
        assert identity({**base, field: explicit_default}) == baseline, (
            f"Spelling out the executor default for {field} does not change "
            "what runs, so it must not mint a second chargeable identity."
        )
    assert identity({**base, "starting_capital": 2500}) == identity(
        {**base, "starting_capital": 2500.0}
    )


def test_late_direct_success_cannot_rewrite_reconciled_failure(
    monkeypatch: pytest.MonkeyPatch,
    mock_gateway,
):
    import pandas as pd
    from argus.domain import engine as domain_engine

    def _fetch(symbol: str, **_: object) -> pd.DataFrame:
        index = pd.to_datetime(
            ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"], utc=True
        )
        close = pd.Series(range(100, 100 + len(index)), index=index, dtype=float)
        return pd.DataFrame(
            {
                "open": close,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 1_000.0,
            },
            index=index,
        )

    monkeypatch.setattr(domain_engine, "fetch_ohlcv", _fetch)
    # The reconciler already settled this job while the slow execution was
    # still running: the serialized finalize finds no running row.
    mock_gateway.finalize_direct_backtest_success.side_effect = None
    mock_gateway.finalize_direct_backtest_success.return_value = None

    response = client.post(
        "/api/v1/backtests/run",
        json={
            "template": "buy_and_hold",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "start_date": "2024-01-02",
            "end_date": "2024-01-05",
        },
        headers={
            "Authorization": "Bearer test-token",
            "Idempotency-Key": "late-finalization-race",
        },
    )

    assert response.status_code == 503
    assert response.json()["code"] == "direct_execution_abandoned"
    assert "run" not in response.json()
    mock_gateway.finalize_direct_backtest_job.assert_not_called()


def test_memory_direct_finalization_requires_a_running_job():
    from argus.domain import backtest_admission

    store = AlphaStore()
    outcome = backtest_admission.admit_backtest_job_memory(
        store,
        user_id=USER_ID,
        operation_scope="backtests.run",
        idempotency_key="race-key",
        identity_hash=f"sha256:{'e' * 64}",
        payload_hash=f"sha256:{'f' * 64}",
        launch_payload={"kind": "proof"},
        initial_status="running",
        allowance_limits=[("hour", 10), ("day", 50)],
    )
    job_id = outcome.job["id"]
    store.backtest_jobs[job_id]["status"] = "failed"
    store.backtest_jobs[job_id]["failure_code"] = "direct_execution_abandoned"

    result = backtest_admission.finalize_direct_job_memory(
        store,
        job_id=job_id,
        status="succeeded",
        result_run_id="run-1",
    )

    assert result is None
    assert store.backtest_jobs[job_id]["status"] == "failed"
    assert store.backtest_jobs[job_id]["failure_code"] == "direct_execution_abandoned"


def test_unexpected_direct_failure_still_settles_the_job_terminally(
    monkeypatch: pytest.MonkeyPatch,
    mock_gateway,
):
    import pandas as pd
    from argus.api import backtest_service
    from argus.domain import engine as domain_engine

    def _fetch(symbol: str, **_: object) -> pd.DataFrame:
        index = pd.to_datetime(
            ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"], utc=True
        )
        close = pd.Series(range(100, 100 + len(index)), index=index, dtype=float)
        return pd.DataFrame(
            {
                "open": close,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 1_000.0,
            },
            index=index,
        )

    monkeypatch.setattr(domain_engine, "fetch_ohlcv", _fetch)

    def _explode(*args: object, **kwargs: object) -> object:
        raise RuntimeError("engine crashed mid-run")

    monkeypatch.setattr(backtest_service, "create_run_from_payload", _explode)

    with pytest.raises(RuntimeError, match="engine crashed mid-run"):
        client.post(
            "/api/v1/backtests/run",
            json={
                "template": "buy_and_hold",
                "asset_class": "equity",
                "symbols": ["AAPL"],
                "start_date": "2024-01-02",
                "end_date": "2024-01-05",
            },
            headers={
                "Authorization": "Bearer test-token",
                "Idempotency-Key": "unexpected-crash",
            },
        )

    mock_gateway.finalize_direct_backtest_job.assert_called_once()
    settled = mock_gateway.finalize_direct_backtest_job.call_args.kwargs
    assert settled["job_id"] == "job-admitted-1"
    assert settled["status"] == "failed"
    assert settled["failure_code"] == "execution_failed"
    assert settled["failure_detail"] == "unexpected_error"
    assert settled["retryable"] is False
    mock_gateway.finalize_direct_backtest_success.assert_not_called()


def test_backtest_job_contract_allows_direct_jobs_without_a_conversation(
    mock_gateway,
):
    mock_gateway.get_backtest_job.return_value = {
        "id": "9f0a3f31-6f57-49f8-b8f5-2ff8e6b0b0aa",
        "conversation_id": None,
        "status": "failed",
        "failure_code": "direct_execution_abandoned",
        "failure_detail": "direct_execution_abandoned",
        "retryable": True,
    }

    response = client.get(
        "/api/v1/backtest-jobs/9f0a3f31-6f57-49f8-b8f5-2ff8e6b0b0aa",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()["job"]
    assert body["conversation_id"] is None
    assert body["status"] == "failed"
