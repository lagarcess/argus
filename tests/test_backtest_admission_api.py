"""#230 — direct POST /backtests/run admission disposition (memory backend)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from argus.api import state as api_state
from argus.api.main import app
from argus.domain import backtest_admission as admission
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _memory_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "false")
    api_state.store.reset()


def _client() -> TestClient:
    return TestClient(app)


def _payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "template": "rsi_mean_reversion",
        "asset_class": "equity",
        "symbols": ["TSLA"],
    }
    payload.update(overrides)
    return payload


def test_whitespace_padded_key_is_invalid_not_trimmed() -> None:
    response = _client().post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": " padded "},
        json=_payload(),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_overlong_key_is_invalid() -> None:
    response = _client().post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": "x" * 129},
        json=_payload(),
    )
    assert response.status_code == 422


def test_admission_creates_durable_running_job_then_succeeds() -> None:
    client = _client()
    response = client.post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": "direct-1"},
        json=_payload(),
    )
    assert response.status_code == 200
    run = response.json()["run"]

    jobs = list(api_state.store.backtest_jobs.values())
    assert len(jobs) == 1
    job = jobs[0]
    assert job["operation_scope"] == "backtests.run"
    assert job["idempotency_key"] == "direct-1"
    assert job["status"] == "succeeded"
    assert job["result_run_id"] == run["id"]
    assert job["identity_hash"].startswith("sha256:")

    status = client.get(f"/api/v1/backtest-jobs/{job['id']}")
    assert status.status_code == 200
    assert status.json()["job"]["status"] == "succeeded"


def test_exact_replay_returns_same_run_and_charges_once() -> None:
    client = _client()
    first = client.post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": "direct-replay"},
        json=_payload(),
    )
    replay = client.post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": "direct-replay"},
        json=_payload(),
    )

    assert first.status_code == replay.status_code == 200
    assert first.json()["run"]["id"] == replay.json()["run"]["id"]
    assert len(api_state.store.backtest_jobs) == 1
    assert list(api_state.store.simulation_admissions.values()) == [1]


def test_same_key_different_identity_conflicts_without_disclosure() -> None:
    client = _client()
    first = client.post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": "shared-key"},
        json=_payload(),
    )
    assert first.status_code == 200

    conflict = client.post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": "shared-key"},
        json=_payload(symbols=["AAPL"]),
    )
    assert conflict.status_code == 409
    body = conflict.json()
    assert body["code"] == "idempotency_conflict"
    assert "job" not in body and "run" not in body
    assert list(api_state.store.simulation_admissions.values()) == [1]


def test_replay_while_running_returns_in_progress_with_job_id() -> None:
    client = _client()
    user_id = api_state.store.get_or_create_dev_user().id

    seeded = admission.admit_backtest_job_memory(
        api_state.store,
        user_id=user_id,
        operation_scope=admission.DIRECT_RUN_SCOPE,
        idempotency_key="in-flight",
        identity_hash="sha256:" + "9" * 64,
        payload_hash="sha256:" + "8" * 64,
        launch_payload={"kind": "seeded"},
        initial_status="running",
    )
    assert seeded.job is not None

    def fake_identity(**_kwargs: Any) -> str:
        return "sha256:" + "9" * 64

    original = admission.direct_run_identity_hash
    admission.direct_run_identity_hash = fake_identity  # type: ignore[assignment]
    try:
        response = client.post(
            "/api/v1/backtests/run",
            headers={"Idempotency-Key": "in-flight"},
            json=_payload(),
        )
    finally:
        admission.direct_run_identity_hash = original  # type: ignore[assignment]

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "idempotency_in_progress"
    assert body["context"]["backtest_job_id"] == seeded.job["id"]
    assert response.headers.get("Retry-After") == "1"


def test_per_user_capacity_rejects_with_retry_after_fifteen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client()
    user_id = api_state.store.get_or_create_dev_user().id

    seeded = admission.admit_backtest_job_memory(
        api_state.store,
        user_id=user_id,
        operation_scope=admission.DIRECT_RUN_SCOPE,
        idempotency_key="occupies-slot",
        identity_hash="sha256:" + "7" * 64,
        payload_hash="sha256:" + "6" * 64,
        launch_payload={"kind": "seeded"},
        initial_status="running",
    )
    assert seeded.kind == "admitted"

    response = client.post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": "new-work"},
        json=_payload(),
    )
    assert response.status_code == 429
    body = response.json()
    assert body["code"] == "backtest_capacity_exceeded"
    assert response.headers.get("Retry-After") == "15"
    assert api_state.store.simulation_admissions[user_id] == 1


def test_global_capacity_rejects_with_503(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    for index in range(5):
        outcome = admission.admit_backtest_job_memory(
            api_state.store,
            user_id=f"other-user-{index}",
            operation_scope=admission.DIRECT_RUN_SCOPE,
            idempotency_key=f"other-{index}",
            identity_hash=f"sha256:{index}" + "5" * 63,
            payload_hash="sha256:" + "4" * 64,
            launch_payload={"kind": "seeded"},
            initial_status="running",
        )
        assert outcome.kind == "admitted"

    response = client.post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": "wants-capacity"},
        json=_payload(),
    )
    assert response.status_code == 503
    assert response.json()["code"] == "backtest_capacity_exceeded"
    assert response.headers.get("Retry-After") == "15"


def test_replay_of_terminal_failure_returns_same_failure() -> None:
    client = _client()
    user_id = api_state.store.get_or_create_dev_user().id

    seeded = admission.admit_backtest_job_memory(
        api_state.store,
        user_id=user_id,
        operation_scope=admission.DIRECT_RUN_SCOPE,
        idempotency_key="failed-run",
        identity_hash="sha256:" + "3" * 64,
        payload_hash="sha256:" + "2" * 64,
        launch_payload={"kind": "seeded"},
        initial_status="running",
        execution_metadata={"failure_status": 422},
    )
    assert seeded.job is not None
    admission.finalize_direct_job_memory(
        api_state.store,
        job_id=seeded.job["id"],
        status="failed",
        failure_code="invalid_symbol",
        failure_detail="Symbol is not supported.",
        retryable=False,
    )

    def fake_identity(**_kwargs: Any) -> str:
        return "sha256:" + "3" * 64

    original = admission.direct_run_identity_hash
    admission.direct_run_identity_hash = fake_identity  # type: ignore[assignment]
    try:
        response = client.post(
            "/api/v1/backtests/run",
            headers={"Idempotency-Key": "failed-run"},
            json=_payload(),
        )
    finally:
        admission.direct_run_identity_hash = original  # type: ignore[assignment]

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_symbol"


def test_stale_reconciliation_win_blocks_late_run_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the stale reconciler abandons the job while execution is still in
    flight, late finalization must not create, expose, or return a Run."""

    from argus.api import backtest_service

    client = TestClient(app, raise_server_exceptions=False)
    user_id = api_state.store.get_or_create_dev_user().id

    original_create = backtest_service.create_run_from_payload

    def create_then_lose_to_reconciler(*args: Any, **kwargs: Any) -> Any:
        run = original_create(*args, **kwargs)
        # The reconciler wins mid-execution: the row goes stale and abandons.
        for job in api_state.store.backtest_jobs.values():
            if job.get("user_id") == user_id and job.get("status") == "running":
                job["started_at"] = (
                    datetime.now(timezone.utc) - timedelta(minutes=16)
                ).isoformat()
        admission.reconcile_stale_direct_jobs_memory(api_state.store)
        return run

    monkeypatch.setattr(
        backtest_service, "create_run_from_payload", create_then_lose_to_reconciler
    )
    monkeypatch.setattr(
        "argus.api.routers.backtest.create_run_from_payload",
        create_then_lose_to_reconciler,
        raising=False,
    )

    runs_before = set(api_state.store.backtest_runs)
    finalizations_before = dict(api_state.store.backtest_finalizations)

    response = client.post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": "loses-to-reconciler"},
        json=_payload(),
    )

    assert response.status_code != 200
    body = response.json()
    assert body["code"] == "direct_execution_abandoned"
    assert "run" not in body

    jobs = [
        job
        for job in api_state.store.backtest_jobs.values()
        if job.get("idempotency_key") == "loses-to-reconciler"
    ]
    assert len(jobs) == 1
    assert jobs[0]["status"] == "failed"
    assert jobs[0]["result_run_id"] is None
    # No durable Run/evidence tuple was created for the abandoned execution.
    assert set(api_state.store.backtest_runs) == runs_before
    assert api_state.store.backtest_finalizations == finalizations_before


def test_missing_direct_job_fails_closed_without_a_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#230: the admitted job row vanished before finalization — fail closed:
    no Run may be created, exposed, or returned."""

    from argus.api import backtest_service

    client = TestClient(app, raise_server_exceptions=False)
    api_state.store.get_or_create_dev_user()

    original_create = backtest_service.create_run_from_payload

    def create_then_lose_the_job(*args: Any, **kwargs: Any) -> Any:
        run = original_create(*args, **kwargs)
        api_state.store.backtest_jobs.clear()
        api_state.store.backtest_job_reservations.clear()
        return run

    monkeypatch.setattr(
        backtest_service, "create_run_from_payload", create_then_lose_the_job
    )
    monkeypatch.setattr(
        "argus.api.routers.backtest.create_run_from_payload",
        create_then_lose_the_job,
        raising=False,
    )

    runs_before = set(api_state.store.backtest_runs)
    finalizations_before = dict(api_state.store.backtest_finalizations)

    response = client.post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": "job-vanished"},
        json=_payload(),
    )

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "finalization_failed"
    assert "run" not in body
    assert set(api_state.store.backtest_runs) == runs_before
    assert api_state.store.backtest_finalizations == finalizations_before


def test_stale_running_direct_job_reconciles_on_poll() -> None:
    client = _client()
    user_id = api_state.store.get_or_create_dev_user().id

    seeded = admission.admit_backtest_job_memory(
        api_state.store,
        user_id=user_id,
        operation_scope=admission.DIRECT_RUN_SCOPE,
        idempotency_key="stale-poll",
        identity_hash="sha256:" + "1" * 64,
        payload_hash="sha256:" + "0" * 64,
        launch_payload={"kind": "seeded"},
        initial_status="running",
    )
    assert seeded.job is not None
    api_state.store.backtest_jobs[seeded.job["id"]]["started_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=16)
    ).isoformat()

    response = client.get(f"/api/v1/backtest-jobs/{seeded.job['id']}")
    assert response.status_code == 200
    job = response.json()["job"]
    assert job["status"] == "failed"
    assert job["failure_code"] == "direct_execution_abandoned"
    assert job["retryable"] is True


def test_shape_validation_rejects_before_admission_without_charge() -> None:
    client = _client()
    response = client.post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": "mixed"},
        json=_payload(symbols=["AAPL", "BTC"]),
    )
    assert response.status_code == 422
    assert not api_state.store.backtest_jobs
    assert not api_state.store.simulation_admissions
