from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

import pytest
from argus.api.main import app
from argus.api.schemas import BacktestRun, Message, OnboardingState, User
from faker import Faker
from fastapi.testclient import TestClient

FULL_LAUNCH_PAYLOAD_HASH = (
    "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
)
MATCHING_IDENTITY_HASH = (
    "sha256:bb4f6bca954472872955f0338d433c17e9e04f616451d8c6b134f74d36909bfc"
)


class _ByActionGateway:
    def __init__(
        self,
        *,
        reservation_exists: bool = True,
        identity_hash: str = MATCHING_IDENTITY_HASH,
        artifact_issue: Literal[
            "none",
            "missing",
            "foreign_conversation",
            "non_assistant",
            "missing_confirmation_id",
            "short_launch_hash",
        ] = "none",
        run_exists: bool = True,
    ) -> None:
        fake = Faker()
        self.user = User(
            id="user-1",
            email=fake.email(),
            username=None,
            display_name="Mock Developer",
            language="en",
            locale="en-US",
            theme="dark",
            is_admin=True,
            onboarding=OnboardingState(completed=True, stage="completed"),
            created_at=datetime(2026, 7, 24, tzinfo=timezone.utc),
            updated_at=datetime(2026, 7, 24, tzinfo=timezone.utc),
        )
        self.reservation_exists = reservation_exists
        self.artifact_issue = artifact_issue
        self.run_exists = run_exists
        self.reservation_calls: list[dict[str, str]] = []
        self.message_calls: list[dict[str, str]] = []
        self.run = _run()
        self.job: dict[str, object] = {
            "id": "job-by-action-1",
            "user_id": self.user.id,
            "conversation_id": "conversation-1",
            "request_message_id": "request-message-1",
            "confirmation_message_id": "confirmation-message-1",
            "operation_scope": "chat.run_backtest",
            "idempotency_key": "confirmation-1",
            "identity_hash": identity_hash,
            "payload_hash": FULL_LAUNCH_PAYLOAD_HASH,
            "status": "succeeded",
            "result_run_id": self.run.id,
            "failure_code": None,
            "failure_detail": None,
            "retryable": False,
            "queued_at": "2026-07-24T12:00:00+00:00",
            "started_at": "2026-07-24T12:00:01+00:00",
            "finished_at": "2026-07-24T12:00:04+00:00",
            "created_at": "2026-07-24T12:00:00+00:00",
            "updated_at": "2026-07-24T12:00:04+00:00",
            "execution_metadata": {
                "workflow_backtest": {
                    "result_readout": "**Quick take**\n\nOne canonical result.",
                    "result_readout_source": "llm_explain_stage",
                    "result_readout_fallback_used": False,
                }
            },
        }

    def get_or_create_mock_user(self) -> User:
        return self.user

    def get_backtest_job_reservation(
        self,
        *,
        user_id: str,
        operation_scope: str,
        idempotency_key: str,
    ) -> dict[str, object] | None:
        self.reservation_calls.append(
            {
                "user_id": user_id,
                "operation_scope": operation_scope,
                "idempotency_key": idempotency_key,
            }
        )
        return dict(self.job) if self.reservation_exists else None

    def get_message(
        self,
        *,
        user_id: str,
        conversation_id: str,
        message_id: str,
    ) -> Message | None:
        self.message_calls.append(
            {
                "user_id": user_id,
                "conversation_id": conversation_id,
                "message_id": message_id,
            }
        )
        if self.artifact_issue == "missing":
            return None
        card = {
            "confirmation_id": "confirmation-1",
            "launch_payload_hash": FULL_LAUNCH_PAYLOAD_HASH,
        }
        if self.artifact_issue == "missing_confirmation_id":
            card.pop("confirmation_id")
        if self.artifact_issue == "short_launch_hash":
            card["launch_payload_hash"] = "aaaaaaaaaaaaaaaa"
        return Message(
            id="confirmation-message-1",
            conversation_id=(
                "conversation-2"
                if self.artifact_issue == "foreign_conversation"
                else conversation_id
            ),
            role="user" if self.artifact_issue == "non_assistant" else "assistant",
            content="Ready to run.",
            metadata={"confirmation_card": card},
            created_at=datetime(2026, 7, 24, tzinfo=timezone.utc),
        )

    def get_backtest_run(
        self,
        *,
        user_id: str,
        run_id: str,
    ) -> BacktestRun | None:
        if not self.run_exists:
            return None
        if user_id == self.user.id and run_id == self.run.id:
            return self.run
        return None


def _run() -> BacktestRun:
    return BacktestRun(
        id="run-by-action-1",
        conversation_id="conversation-1",
        strategy_id=None,
        status="completed",
        asset_class="equity",
        symbols=["AAPL"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={
            "aggregate": {"performance": {"total_return_pct": 12.4}},
            "by_symbol": {},
        },
        config_snapshot={"template": "buy_and_hold", "benchmark_symbol": "SPY"},
        conversation_result_card={
            "title": "AAPL buy and hold",
            "date_range": {
                "start": "2025-07-24",
                "end": "2026-07-24",
                "display": "July 24, 2025 to July 24, 2026",
            },
            "status_label": "Simulation Complete",
            "rows": [],
            "assumptions": ["Long-only", "Benchmark: SPY"],
            "actions": [],
        },
        created_at=datetime(2026, 7, 24, tzinfo=timezone.utc),
        chart=None,
        trades=[],
    )


@pytest.fixture(autouse=True)
def _mock_auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARGUS_MOCK_AUTH", "true")
    monkeypatch.setenv("ARGUS_DEV_MEMORY_FALLBACK", "false")


def test_by_action_lookup_returns_canonical_succeeded_job_without_render_reconcile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import state as api_state
    from argus.api.routers import backtest as backtest_router

    gateway = _ByActionGateway()
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    monkeypatch.setattr(
        backtest_router,
        "reconcile_terminal_render_task_run",
        lambda **_: (_ for _ in ()).throw(
            AssertionError("fresh by-action lookup must not call Render")
        ),
    )

    response = TestClient(app).get("/api/v1/backtest-jobs/by-action/confirmation-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["job"]["id"] == "job-by-action-1"
    assert payload["run"]["id"] == "run-by-action-1"
    assert payload["result_readout"] == "**Quick take**\n\nOne canonical result."
    assert gateway.reservation_calls == [
        {
            "user_id": "user-1",
            "operation_scope": "chat.run_backtest",
            "idempotency_key": "confirmation-1",
        }
    ]


def test_by_action_lookup_returns_404_for_missing_owner_scoped_reservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import state as api_state

    gateway = _ByActionGateway(reservation_exists=False)
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)

    response = TestClient(app).get("/api/v1/backtest-jobs/by-action/confirmation-1")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert "job-by-action-1" not in response.text
    assert gateway.message_calls == []
    assert gateway.reservation_calls[0]["operation_scope"] == "chat.run_backtest"


def test_by_action_lookup_returns_409_without_job_disclosure_on_identity_collision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import state as api_state

    gateway = _ByActionGateway(
        identity_hash=(
            "sha256:cccccccccccccccccccccccccccccccc" "cccccccccccccccccccccccccccccccc"
        )
    )
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)

    response = TestClient(app).get("/api/v1/backtest-jobs/by-action/confirmation-1")

    assert response.status_code == 409
    assert response.json()["code"] == "idempotency_conflict"
    assert "job-by-action-1" not in response.text
    assert "run-by-action-1" not in response.text


@pytest.mark.parametrize(
    "artifact_issue",
    [
        "missing",
        "foreign_conversation",
        "non_assistant",
        "missing_confirmation_id",
        "short_launch_hash",
    ],
)
def test_by_action_lookup_returns_safe_500_for_inconsistent_confirmation_artifact(
    monkeypatch: pytest.MonkeyPatch,
    artifact_issue: Literal[
        "missing",
        "foreign_conversation",
        "non_assistant",
        "missing_confirmation_id",
        "short_launch_hash",
    ],
) -> None:
    from argus.api import state as api_state

    gateway = _ByActionGateway(artifact_issue=artifact_issue)
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)

    response = TestClient(app).get("/api/v1/backtest-jobs/by-action/confirmation-1")

    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert "job-by-action-1" not in response.text
    assert "run-by-action-1" not in response.text


def test_by_action_lookup_returns_safe_500_when_succeeded_job_has_no_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import state as api_state

    gateway = _ByActionGateway(run_exists=False)
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)

    response = TestClient(app).get("/api/v1/backtest-jobs/by-action/confirmation-1")

    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert "job-by-action-1" not in response.text
    assert "run-by-action-1" not in response.text


@pytest.mark.parametrize("failing_read", ["reservation", "message"])
def test_by_action_lookup_shapes_persistence_read_failures_as_safe_500(
    monkeypatch: pytest.MonkeyPatch,
    failing_read: Literal["reservation", "message"],
) -> None:
    from argus.api import state as api_state

    gateway = _ByActionGateway()

    def fail_read(**_: object) -> None:
        raise RuntimeError("private persistence detail")

    if failing_read == "reservation":
        monkeypatch.setattr(gateway, "get_backtest_job_reservation", fail_read)
    else:
        monkeypatch.setattr(gateway, "get_message", fail_read)
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)

    response = TestClient(app, raise_server_exceptions=False).get(
        "/api/v1/backtest-jobs/by-action/confirmation-1"
    )

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["code"] == "internal_error"
    assert "private persistence detail" not in response.text
    assert "job-by-action-1" not in response.text


def test_by_action_lookup_shapes_malformed_durable_job_as_safe_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import state as api_state

    gateway = _ByActionGateway()
    gateway.job["status"] = "unknown"
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)

    response = TestClient(app, raise_server_exceptions=False).get(
        "/api/v1/backtest-jobs/by-action/confirmation-1"
    )

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["code"] == "internal_error"
    assert "job-by-action-1" not in response.text
