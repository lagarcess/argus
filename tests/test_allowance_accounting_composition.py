"""#247 x #230 x #251 — the joint simulation-accounting composition proofs.

One unit is consumed only by a successful unique durable admission; replays,
pre-admission rejections, and preflight consume nothing; direct and chat
launches follow the same rule; and the authenticated usage surface reports
exactly the charged truth.
"""

from __future__ import annotations

import threading

import pytest
from argus.api import state as api_state
from argus.api.main import app
from argus.domain import backtest_admission as admission
from argus.domain.store import AlphaStore
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _memory_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "false")
    api_state.store.reset()


def _admit(
    store: AlphaStore, *, key: str, identity: str, scope: str
) -> admission.AdmissionOutcome:
    return admission.admit_backtest_job_memory(
        store,
        user_id="user-1",
        operation_scope=scope,
        idempotency_key=key,
        identity_hash=identity,
        payload_hash="sha256:" + "b" * 64,
        launch_payload={"kind": "composition"},
        initial_status="queued" if scope == admission.CHAT_RUN_SCOPE else "running",
        conversation_id="conv-1",
    )


def test_first_durable_admission_increments_simulations_by_one() -> None:
    store = AlphaStore()
    outcome = _admit(
        store, key="k1", identity="sha256:" + "1" * 64, scope=admission.CHAT_RUN_SCOPE
    )
    assert outcome.kind == "admitted"
    assert store.simulation_admissions["user-1"] == 1


def test_ten_concurrent_same_identity_requests_admit_once_and_charge_once() -> None:
    store = AlphaStore()
    barrier = threading.Barrier(10)
    outcomes: list[admission.AdmissionOutcome] = []
    lock = threading.Lock()

    def worker() -> None:
        barrier.wait()
        outcome = _admit(
            store,
            key="same-key",
            identity="sha256:" + "2" * 64,
            scope=admission.CHAT_RUN_SCOPE,
        )
        with lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    kinds = sorted(outcome.kind for outcome in outcomes)
    assert kinds.count("admitted") == 1
    assert kinds.count("replay") == 9
    assert len(store.backtest_jobs) == 1
    assert store.simulation_admissions["user-1"] == 1


def test_replays_return_the_prior_admission_and_consume_zero() -> None:
    store = AlphaStore()
    first = _admit(
        store, key="k3", identity="sha256:" + "3" * 64, scope=admission.CHAT_RUN_SCOPE
    )
    replay = _admit(
        store, key="k3", identity="sha256:" + "3" * 64, scope=admission.CHAT_RUN_SCOPE
    )
    assert first.job is not None and replay.job is not None
    assert replay.kind == "replay"
    assert replay.job["id"] == first.job["id"]
    assert store.simulation_admissions["user-1"] == 1


def test_pre_admission_rejections_consume_zero_units() -> None:
    client = TestClient(app)
    responses = [
        client.post(
            "/api/v1/backtests/run",
            json={"template": "rsi_mean_reversion", "symbols": ["AAPL"]},
        ),
        client.post(
            "/api/v1/backtests/run",
            headers={"Idempotency-Key": " padded "},
            json={"template": "rsi_mean_reversion", "symbols": ["AAPL"]},
        ),
        client.post(
            "/api/v1/backtests/run",
            headers={"Idempotency-Key": "mixed-assets"},
            json={"template": "rsi_mean_reversion", "symbols": ["AAPL", "BTC"]},
        ),
    ]
    assert [response.status_code for response in responses] == [400, 422, 422]
    assert api_state.store.simulation_admissions == {}
    assert api_state.store.backtest_jobs == {}


def test_post_admission_execution_failure_leaves_exactly_one_unit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import backtest_service

    client = TestClient(app)
    user_id = api_state.store.get_or_create_dev_user().id

    def _explode(*args: object, **kwargs: object) -> object:
        raise RuntimeError("engine failure after admission")

    monkeypatch.setattr(backtest_service, "compute_alpha_metrics", _explode)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": "fails-after-admit"},
        json={"template": "rsi_mean_reversion", "symbols": ["TSLA"]},
    )

    assert response.status_code == 500
    assert api_state.store.simulation_admissions[user_id] == 1
    jobs = list(api_state.store.backtest_jobs.values())
    assert len(jobs) == 1
    assert jobs[0]["status"] == "failed"
    assert jobs[0]["retryable"] is True


def test_direct_and_chat_launches_share_one_accounting_rule() -> None:
    store = AlphaStore()
    chat = _admit(
        store, key="chat-1", identity="sha256:" + "4" * 64, scope=admission.CHAT_RUN_SCOPE
    )
    direct = _admit(
        store,
        key="direct-1",
        identity="sha256:" + "5" * 64,
        scope=admission.DIRECT_RUN_SCOPE,
    )
    assert chat.kind == direct.kind == "admitted"
    assert store.simulation_admissions["user-1"] == 2


def test_usage_endpoint_reports_the_charged_admission_truth() -> None:
    client = TestClient(app)
    run = client.post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": "usage-truth"},
        json={"template": "rsi_mean_reversion", "symbols": ["TSLA"]},
    )
    assert run.status_code == 200

    usage = client.get("/api/v1/me/usage")
    assert usage.status_code == 200
    backtests = usage.json()["allowances"]["backtests"]
    assert backtests["used"] == 1
    assert backtests["remaining"] == backtests["limit"] - 1

    replay = client.post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": "usage-truth"},
        json={"template": "rsi_mean_reversion", "symbols": ["TSLA"]},
    )
    assert replay.status_code == 200
    after_replay = client.get("/api/v1/me/usage").json()["allowances"]["backtests"]
    assert after_replay["used"] == 1
