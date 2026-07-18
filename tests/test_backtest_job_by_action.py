"""#242 — durable by-action lookup for ambiguous Run reconciliation."""

from __future__ import annotations

import pytest
from argus.api import state as api_state
from argus.api.main import app
from argus.api.message_store import memory_conversation, memory_message
from argus.domain import backtest_admission as admission
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _memory_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    api_state.store.reset()


def _seed_chat_job(
    *,
    confirmation_id: str = "confirmation-1",
    with_artifact: bool = True,
    artifact_confirmation_id: str | None = None,
    status: str = "queued",
) -> dict:
    user_id = api_state.store.get_or_create_dev_user().id
    conversation = memory_conversation(
        user_id=user_id,
        title="Run lane",
        title_source="system_default",
        language="en",
    )
    conversation_id = conversation.id

    message_id = None
    if with_artifact:
        message = memory_message(
            conversation_id=conversation_id,
            role="assistant",
            content="Ready to run.",
            metadata={
                "confirmation_card": {
                    "confirmation_id": artifact_confirmation_id or confirmation_id,
                    "confirmation_state": "active",
                }
            },
        )
        message_id = message.id

    payload_hash = "sha256:" + "b" * 64
    identity = admission.chat_run_identity_hash(
        conversation_id=conversation_id,
        confirmation_id=confirmation_id,
        launch_payload_hash=payload_hash,
    )
    outcome = admission.admit_backtest_job_memory(
        api_state.store,
        user_id=user_id,
        operation_scope=admission.CHAT_RUN_SCOPE,
        idempotency_key=confirmation_id,
        identity_hash=identity,
        payload_hash=payload_hash,
        launch_payload={"kind": "run_backtest_job"},
        initial_status=status,  # type: ignore[arg-type]
        conversation_id=conversation_id,
        confirmation_message_id=message_id,
    )
    assert outcome.kind == "admitted" and outcome.job is not None
    if status != "queued":
        api_state.store.backtest_jobs[outcome.job["id"]]["status"] = status
    return dict(api_state.store.backtest_jobs[outcome.job["id"]])


def test_lookup_returns_existing_durable_job() -> None:
    job = _seed_chat_job()
    response = TestClient(app).get(
        "/api/v1/backtest-jobs/by-action/confirmation-1"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job"]["id"] == job["id"]
    assert payload["job"]["status"] == "queued"
    assert payload["run"] is None


def test_lookup_without_reservation_is_replayable_404() -> None:
    response = TestClient(app).get(
        "/api/v1/backtest-jobs/by-action/never-clicked"
    )
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_missing_confirmation_artifact_is_integrity_500() -> None:
    _seed_chat_job(with_artifact=False)
    response = TestClient(app).get(
        "/api/v1/backtest-jobs/by-action/confirmation-1"
    )
    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"


def test_mismatched_artifact_confirmation_is_integrity_500() -> None:
    _seed_chat_job(artifact_confirmation_id="confirmation-other")
    response = TestClient(app).get(
        "/api/v1/backtest-jobs/by-action/confirmation-1"
    )
    assert response.status_code == 500


def test_identity_mismatch_returns_conflict_without_job_details() -> None:
    job = _seed_chat_job()
    api_state.store.backtest_jobs[job["id"]]["identity_hash"] = "sha256:" + "f" * 64

    response = TestClient(app).get(
        "/api/v1/backtest-jobs/by-action/confirmation-1"
    )
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "idempotency_conflict"
    assert "job" not in body


def test_succeeded_job_hydrates_exactly_one_canonical_run() -> None:
    from datetime import datetime, timezone

    from argus.api.schemas import BacktestRun

    job = _seed_chat_job(status="succeeded")
    api_state.store.backtest_jobs[job["id"]]["result_run_id"] = "run-42"
    api_state.store.backtest_runs["run-42"] = BacktestRun(
        id="run-42",
        status="completed",
        asset_class="equity",
        symbols=["TSLA"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={},
        config_snapshot={},
        conversation_result_card={"title": "TSLA run"},
        created_at=datetime.now(timezone.utc),
    )

    response = TestClient(app).get(
        "/api/v1/backtest-jobs/by-action/confirmation-1"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["job"]["status"] == "succeeded"
    assert payload["run"]["id"] == "run-42"
