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
    with_artifact_hash: bool = True,
    artifact_confirmation_id: str | None = None,
    artifact_launch_hash: str | None = None,
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
    launch_hash = "sha256:" + "b" * 64
    if with_artifact:
        card = {
            "confirmation_id": artifact_confirmation_id or confirmation_id,
            "confirmation_state": "active",
        }
        if with_artifact_hash:
            card["launch_payload_hash_full"] = artifact_launch_hash or launch_hash
        message = memory_message(
            conversation_id=conversation_id,
            role="assistant",
            content="Ready to run.",
            metadata={"confirmation_card": card},
        )
        message_id = message.id

    # Admission identity binds to the artifact's full-width launch hash.
    identity = admission.chat_run_identity_hash(
        conversation_id=conversation_id,
        confirmation_id=confirmation_id,
        launch_payload_hash=launch_hash,
    )
    payload_hash = launch_hash
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
    response = TestClient(app).get("/api/v1/backtest-jobs/by-action/confirmation-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["job"]["id"] == job["id"]
    assert payload["job"]["status"] == "queued"
    assert payload["run"] is None


def test_lookup_without_reservation_is_replayable_404() -> None:
    response = TestClient(app).get("/api/v1/backtest-jobs/by-action/never-clicked")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_missing_confirmation_artifact_is_integrity_500() -> None:
    _seed_chat_job(with_artifact=False)
    response = TestClient(app).get("/api/v1/backtest-jobs/by-action/confirmation-1")
    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"


def test_mismatched_artifact_confirmation_is_integrity_500() -> None:
    _seed_chat_job(artifact_confirmation_id="confirmation-other")
    response = TestClient(app).get("/api/v1/backtest-jobs/by-action/confirmation-1")
    assert response.status_code == 500


def test_artifact_hash_mismatch_returns_conflict() -> None:
    """A card whose immutable launch hash disagrees with the reservation's
    identity must conflict — the artifact, not job fields, is authority."""

    _seed_chat_job(artifact_launch_hash="sha256:" + "e" * 64)

    response = TestClient(app).get("/api/v1/backtest-jobs/by-action/confirmation-1")
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "idempotency_conflict"
    assert "job" not in body


def test_card_without_full_launch_hash_is_integrity_500() -> None:
    _seed_chat_job(with_artifact_hash=False)

    response = TestClient(app).get("/api/v1/backtest-jobs/by-action/confirmation-1")
    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"


def test_cross_owner_confirmation_artifact_is_rejected() -> None:
    """The confirmation message must belong to the requesting user's
    conversation; a foreign owner is integrity 500, never a replay signal."""

    job = _seed_chat_job()
    api_state.store.conversation_owners[job["conversation_id"]] = (
        "11111111-1111-1111-1111-111111111111"
    )

    response = TestClient(app).get("/api/v1/backtest-jobs/by-action/confirmation-1")
    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"


@pytest.mark.parametrize(
    "bad_hash",
    [
        "sha256:XYZ",
        "sha256:" + "B" * 64,
        "sha256:" + "b" * 63,
        "sha256:" + "b" * 65,
        "md5:" + "b" * 64,
    ],
)
def test_malformed_artifact_hash_is_integrity_500(bad_hash: str) -> None:
    _seed_chat_job(artifact_launch_hash=bad_hash)

    response = TestClient(app).get("/api/v1/backtest-jobs/by-action/confirmation-1")
    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"


def test_missing_artifact_hash_cannot_create_a_reservation() -> None:
    """A run action without the artifact's full-width hash must terminate
    before durable admission — never admit a reservation the by-action lookup
    can never reproduce, and never fall through to execution."""

    from unittest.mock import MagicMock

    from argus.api.chat.backtest_admission_flow import (
        BacktestArtifactIdentityError,
        admit_durable_chat_job,
    )

    gateway = MagicMock()
    context = MagicMock()
    context.idempotency_key = "confirmation-legacy"
    context.user_id = "user-1"
    context.conversation_id = "conv-1"
    context.chat_action = {
        "type": "run_backtest",
        "payload": {"confirmation_id": "confirmation-legacy"},
    }

    with pytest.raises(BacktestArtifactIdentityError):
        admit_durable_chat_job(
            gateway=gateway,
            context=context,
            identity_hash="sha256:" + "0" * 64,
            payload_digest="sha256:" + "1" * 64,
            launch_payload={"kind": "legacy"},
            reconcile_blockers=lambda **kwargs: False,
            artifact_launch_hash=None,
        )

    gateway.admit_backtest_job.assert_not_called()


def test_gateway_confirmation_load_uses_owner_scoped_message_boundary() -> None:
    """#242: the confirmation artifact loads through the existing owner-scoped
    user_id + conversation_id + message_id boundary. A message another user
    owns can never qualify, even when an unscoped row lookup would find it."""

    from datetime import datetime, timezone
    from unittest.mock import MagicMock

    from argus.api.routers.backtest import _confirmation_artifact_identity
    from argus.api.schemas import User
    from fastapi import HTTPException
    from starlette.requests import Request

    now = datetime.now(timezone.utc)
    user = User(
        id="00000000-0000-0000-0000-000000000001",
        email="developer@argus.local",
        language="en",
        created_at=now,
        updated_at=now,
    )
    job = {
        "conversation_id": "22222222-2222-2222-2222-222222222222",
        "confirmation_message_id": "33333333-3333-3333-3333-333333333333",
    }
    gateway = MagicMock()
    # Owner-scoped boundary: the foreign-owned message is invisible.
    gateway.get_message.return_value = None
    # Unscoped legacy lookup would still surface the row; it must not be used.
    gateway.get_message_row.return_value = {
        "conversation_id": job["conversation_id"],
        "user_id": "99999999-9999-9999-9999-999999999999",
        "metadata": {
            "confirmation_card": {
                "confirmation_id": "confirmation-1",
                "launch_payload_hash_full": "sha256:" + "b" * 64,
            }
        },
    }
    api_state.supabase_gateway = gateway
    try:
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": [],
                "state": {"request_id": "test-request-1"},
            }
        )
        with pytest.raises(HTTPException) as exc_info:
            _confirmation_artifact_identity(
                request,
                user=user,
                job=job,
                confirmation_id="confirmation-1",
            )
    finally:
        api_state.supabase_gateway = None

    assert exc_info.value.status_code == 500
    gateway.get_message.assert_called_once_with(
        user_id=user.id,
        conversation_id=job["conversation_id"],
        message_id=job["confirmation_message_id"],
    )
    gateway.get_message_row.assert_not_called()


def test_identity_mismatch_returns_conflict_without_job_details() -> None:
    job = _seed_chat_job()
    api_state.store.backtest_jobs[job["id"]]["identity_hash"] = "sha256:" + "f" * 64

    response = TestClient(app).get("/api/v1/backtest-jobs/by-action/confirmation-1")
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

    response = TestClient(app).get("/api/v1/backtest-jobs/by-action/confirmation-1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["job"]["status"] == "succeeded"
    assert payload["run"]["id"] == "run-42"
