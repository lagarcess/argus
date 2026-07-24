from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

from argus.api.guest_access import (
    AccountContext,
    guest_capabilities,
    registered_account_context,
)
from argus.domain.backtest_admission_gateway import admit_backtest_job
from argus.domain.store import utcnow
from argus.domain.usage_limits import (
    GUEST_FEEDBACK_ALLOWANCE,
    GUEST_MESSAGE_ALLOWANCE,
    GUEST_SIMULATION_ALLOWANCE,
    allowance_windows,
    message_usage_settlement,
)


def _guest_context() -> AccountContext:
    return AccountContext(
        kind="guest",
        user_id="00000000-0000-0000-0000-000000000051",
        expires_at=utcnow() + timedelta(days=7),
        capabilities=guest_capabilities(),
    )


def test_guest_lifetime_windows_use_fixed_workspace_bounds() -> None:
    account = _guest_context()
    assert account.expires_at is not None
    expected_start = account.expires_at - timedelta(days=7)

    assert allowance_windows(account, "chat_messages") == [
        {
            "period": "guest_session",
            "limit": GUEST_MESSAGE_ALLOWANCE,
            "period_start": expected_start,
            "period_end": account.expires_at,
        }
    ]
    assert allowance_windows(account, "backtest_runs")[0]["limit"] == (
        GUEST_SIMULATION_ALLOWANCE
    )
    assert allowance_windows(account, "feedback")[0]["limit"] == (
        GUEST_FEEDBACK_ALLOWANCE
    )


def test_registered_allowance_windows_remain_hour_and_day() -> None:
    account = registered_account_context("00000000-0000-0000-0000-000000000052")

    assert allowance_windows(account, "chat_messages") == [
        {"period": "hour", "limit": 60},
        {"period": "day", "limit": 200},
    ]
    assert allowance_windows(account, "backtest_runs") == [
        {"period": "hour", "limit": 10},
        {"period": "day", "limit": 50},
    ]


def test_terminal_message_settlement_uses_the_account_policy_window() -> None:
    settlement = message_usage_settlement(_guest_context())

    assert settlement["resource"] == "chat_messages"
    assert settlement["limits"][0]["period"] == "guest_session"
    assert settlement["limits"][0]["limit"] == 10


def test_backtest_gateway_passes_guest_window_to_existing_atomic_owner() -> None:
    client = MagicMock()
    client.rpc.return_value.execute.return_value.data = {
        "decision": "conversion_required"
    }
    windows = allowance_windows(_guest_context(), "backtest_runs")

    outcome = admit_backtest_job(
        client,
        user_id="00000000-0000-0000-0000-000000000051",
        operation_scope="chat.run_backtest",
        idempotency_key="guest-simulation",
        identity_hash=f"sha256:{'a' * 64}",
        payload_hash=f"sha256:{'b' * 64}",
        launch_payload={"kind": "proof"},
        initial_status="queued",
        allowance_limits=windows,
    )

    assert outcome == {"decision": "conversion_required"}
    assert client.rpc.call_args.args[0] == "admit_backtest_job"
    assert client.rpc.call_args.args[1]["p_allowance_limits"] == [
        {
            "period": "guest_session",
            "limit": 1,
            "period_start": windows[0]["period_start"].isoformat(),
            "period_end": windows[0]["period_end"].isoformat(),
        }
    ]
