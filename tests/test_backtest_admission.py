"""#230 — canonical identity and the atomic admission decision order."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from argus.domain import backtest_admission as admission
from argus.domain.store import AlphaStore


def test_canonical_json_is_sorted_compact_unicode_and_null_preserving() -> None:
    rendered = admission.canonical_json(
        {"b": None, "a": {"z": 1, "y": [2, 1]}, "s": "acción"}
    )
    assert rendered == '{"a":{"y":[2,1],"z":1},"b":null,"s":"acción"}'


def test_canonical_json_lowercases_uuids_and_serializes_dates() -> None:
    value = uuid.UUID("A1B2C3D4-0000-0000-0000-000000000001")
    rendered = admission.canonical_json({"id": value, "day": datetime(2024, 1, 2)})
    assert '"a1b2c3d4-0000-0000-0000-000000000001"' in rendered
    assert '"2024-01-02T00:00:00"' in rendered


def test_canonical_json_rejects_non_finite_numbers() -> None:
    with pytest.raises(admission.CanonicalJSONError):
        admission.canonical_json({"value": float("nan")})


def test_canonical_hash_uses_full_sha256_form() -> None:
    digest = admission.canonical_hash({"a": 1})
    assert digest.startswith("sha256:")
    assert len(digest) == len("sha256:") + 64
    assert digest == admission.canonical_hash({"a": 1})


@pytest.mark.parametrize(
    ("raw", "expected_state"),
    [
        (None, "missing"),
        ("", "missing"),
        ("   ", "missing"),
        ("\t", "missing"),
        ("run once", "invalid"),
        (" padded", "invalid"),
        ("x" * 129, "invalid"),
        ("héllo", "invalid"),
        ("run-1", "ok"),
        ("x" * 128, "ok"),
    ],
)
def test_idempotency_key_validation_matrix(raw: str | None, expected_state) -> None:
    state, key = admission.validate_idempotency_key(raw)
    assert state == expected_state
    if expected_state == "ok":
        assert key == raw
    else:
        assert key is None


def test_identity_hashes_differ_by_any_component() -> None:
    base = admission.chat_run_identity_hash(
        conversation_id="c1",
        confirmation_id="k1",
        launch_payload_hash="sha256:" + "0" * 64,
    )
    assert base != admission.chat_run_identity_hash(
        conversation_id="c2",
        confirmation_id="k1",
        launch_payload_hash="sha256:" + "0" * 64,
    )
    assert base != admission.chat_run_identity_hash(
        conversation_id="c1",
        confirmation_id="k2",
        launch_payload_hash="sha256:" + "0" * 64,
    )


def _admit(
    store: AlphaStore,
    *,
    user_id: str = "user-1",
    key: str = "key-1",
    identity: str = "sha256:" + "a" * 64,
    scope: str = admission.CHAT_RUN_SCOPE,
    initial_status: str = "queued",
    limits: admission.AdmissionLimits | None = None,
    allowance: int | None = None,
) -> admission.AdmissionOutcome:
    return admission.admit_backtest_job_memory(
        store,
        user_id=user_id,
        operation_scope=scope,
        idempotency_key=key,
        identity_hash=identity,
        payload_hash="sha256:" + "b" * 64,
        launch_payload={"kind": "test"},
        initial_status=initial_status,  # type: ignore[arg-type]
        conversation_id="conv-1",
        limits=limits
        or admission.AdmissionLimits(
            user_running=1, user_queued=2, global_running=5, global_queued=10
        ),
        simulation_allowance_limit=allowance,
    )


def test_exact_replay_returns_same_job_and_charges_once() -> None:
    store = AlphaStore()
    first = _admit(store)
    replay = _admit(store)

    assert first.kind == "admitted"
    assert replay.kind == "replay"
    assert replay.job is not None and first.job is not None
    assert replay.job["id"] == first.job["id"]
    assert store.simulation_admissions["user-1"] == 1


def test_replay_resolves_before_capacity_and_allowance() -> None:
    store = AlphaStore()
    first = _admit(store)
    assert first.kind == "admitted"

    # Saturate every boundary; the exact replay must still resolve first.
    tight = admission.AdmissionLimits(
        user_running=0, user_queued=0, global_running=0, global_queued=0
    )
    replay = _admit(store, limits=tight, allowance=0)
    assert replay.kind == "replay"


def test_conflict_returns_no_state_and_consumes_nothing() -> None:
    store = AlphaStore()
    _admit(store)
    conflict = _admit(store, identity="sha256:" + "f" * 64)

    assert conflict.kind == "conflict"
    assert conflict.job is None
    assert store.simulation_admissions["user-1"] == 1
    assert len(store.backtest_jobs) == 1


def test_allowance_exhaustion_resolves_before_capacity() -> None:
    store = AlphaStore()
    outcome = _admit(store, allowance=0)
    assert outcome.kind == "allowance_exhausted"
    assert store.simulation_admissions.get("user-1", 0) == 0
    assert not store.backtest_jobs


def test_per_user_capacity_resolves_before_global() -> None:
    store = AlphaStore()
    tight = admission.AdmissionLimits(
        user_running=0, user_queued=0, global_running=0, global_queued=0
    )
    outcome = _admit(store, limits=tight)
    assert outcome.kind == "per_user_capacity"
    assert outcome.retry_after_seconds == 15


def test_global_capacity_rejects_after_user_boundary_clears() -> None:
    store = AlphaStore()
    for index in range(2):
        result = _admit(
            store,
            user_id=f"other-{index}",
            key=f"other-key-{index}",
            identity=f"sha256:{index}" + "c" * 63,
            limits=admission.AdmissionLimits(
                user_running=1, user_queued=2, global_running=5, global_queued=2
            ),
        )
        assert result.kind == "admitted"

    outcome = _admit(
        store,
        limits=admission.AdmissionLimits(
            user_running=1, user_queued=2, global_running=5, global_queued=2
        ),
    )
    assert outcome.kind == "global_capacity"
    assert outcome.retry_after_seconds == 15


def test_capacity_rejection_creates_no_job_and_charges_nothing() -> None:
    store = AlphaStore()
    tight = admission.AdmissionLimits(
        user_running=1, user_queued=0, global_running=5, global_queued=10
    )
    outcome = _admit(store, limits=tight)
    assert outcome.kind == "per_user_capacity"
    assert not store.backtest_jobs
    assert store.simulation_admissions.get("user-1", 0) == 0


def test_direct_admission_requires_both_ceilings_and_claims_running() -> None:
    store = AlphaStore()
    queued = _admit(store, key="queued-key", identity="sha256:" + "d" * 64)
    assert queued.kind == "admitted"

    blocked = _admit(
        store,
        key="direct-key",
        identity="sha256:" + "e" * 64,
        scope=admission.DIRECT_RUN_SCOPE,
        initial_status="running",
        limits=admission.AdmissionLimits(
            user_running=1, user_queued=1, global_running=5, global_queued=10
        ),
    )
    assert blocked.kind == "per_user_capacity"

    allowed = _admit(
        store,
        key="direct-key",
        identity="sha256:" + "e" * 64,
        scope=admission.DIRECT_RUN_SCOPE,
        initial_status="running",
        limits=admission.AdmissionLimits(
            user_running=1, user_queued=2, global_running=5, global_queued=10
        ),
    )
    assert allowed.kind == "admitted"
    assert allowed.job is not None
    assert allowed.job["status"] == "running"
    assert allowed.job["started_at"] is not None


def test_barriered_concurrency_admits_at_most_one_with_limit_one() -> None:
    store = AlphaStore()
    limits = admission.AdmissionLimits(
        user_running=5, user_queued=1, global_running=5, global_queued=10
    )
    barrier = threading.Barrier(10)
    outcomes: list[admission.AdmissionOutcome] = []
    lock = threading.Lock()

    def worker(index: int) -> None:
        barrier.wait()
        outcome = _admit(
            store,
            key=f"key-{index}",
            identity=f"sha256:{index:064d}"[:71],
            limits=limits,
        )
        with lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    admitted = [outcome for outcome in outcomes if outcome.kind == "admitted"]
    rejected = [outcome for outcome in outcomes if outcome.kind == "per_user_capacity"]
    assert len(admitted) == 1
    assert len(rejected) == 9
    assert len(store.backtest_jobs) == 1
    assert store.simulation_admissions["user-1"] == 1


def test_stale_direct_jobs_reconcile_before_new_direct_admission() -> None:
    store = AlphaStore()
    stale = _admit(
        store,
        key="stale-key",
        identity="sha256:" + "1" * 64,
        scope=admission.DIRECT_RUN_SCOPE,
        initial_status="running",
    )
    assert stale.kind == "admitted" and stale.job is not None
    job = store.backtest_jobs[stale.job["id"]]
    job["started_at"] = (datetime.now(timezone.utc) - timedelta(minutes=16)).isoformat()

    fresh = _admit(
        store,
        key="fresh-key",
        identity="sha256:" + "2" * 64,
        scope=admission.DIRECT_RUN_SCOPE,
        initial_status="running",
    )
    assert fresh.kind == "admitted"

    reconciled = store.backtest_jobs[stale.job["id"]]
    assert reconciled["status"] == "failed"
    assert reconciled["failure_code"] == "direct_execution_abandoned"
    assert reconciled["failure_detail"] == "execution_interrupted"
    assert reconciled["retryable"] is True


def _finalize_tuple_for(store: AlphaStore, *, user_id: str, idempotency_key: str) -> str:
    """Record the durable finalized Run/evidence tuple the reconciler must
    honor: the stable job-derived Run plus the finalization marker."""

    from argus.domain.backtest_finalization import stable_backtest_run_id

    execution_identity = admission.direct_execution_identity(idempotency_key)
    run_id = stable_backtest_run_id(user_id, execution_identity)
    store.backtest_runs[run_id] = {"id": run_id, "status": "completed"}
    store.backtest_run_owners[run_id] = user_id
    store.backtest_finalizations[(user_id, execution_identity)] = run_id
    return run_id


def test_stale_direct_job_with_finalized_tuple_reconciles_to_succeeded() -> None:
    store = AlphaStore()
    stale = _admit(
        store,
        key="finalized-key",
        identity="sha256:" + "6" * 64,
        scope=admission.DIRECT_RUN_SCOPE,
        initial_status="running",
    )
    assert stale.job is not None
    store.backtest_jobs[stale.job["id"]]["started_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=16)
    ).isoformat()
    run_id = _finalize_tuple_for(store, user_id="user-1", idempotency_key="finalized-key")

    fresh = _admit(
        store,
        key="another-key",
        identity="sha256:" + "7" * 64,
        scope=admission.DIRECT_RUN_SCOPE,
        initial_status="running",
    )
    assert fresh.kind == "admitted"

    reconciled = store.backtest_jobs[stale.job["id"]]
    assert reconciled["status"] == "succeeded"
    assert reconciled["result_run_id"] == run_id
    assert reconciled["failure_code"] is None
    assert reconciled["failure_detail"] is None
    assert reconciled["retryable"] is False


def test_stale_replay_with_finalized_tuple_returns_succeeded_state() -> None:
    store = AlphaStore()
    stale = _admit(
        store,
        key="replay-finalized",
        identity="sha256:" + "8" * 64,
        scope=admission.DIRECT_RUN_SCOPE,
        initial_status="running",
    )
    assert stale.job is not None
    store.backtest_jobs[stale.job["id"]]["started_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=16)
    ).isoformat()
    run_id = _finalize_tuple_for(
        store, user_id="user-1", idempotency_key="replay-finalized"
    )

    replay = _admit(
        store,
        key="replay-finalized",
        identity="sha256:" + "8" * 64,
        scope=admission.DIRECT_RUN_SCOPE,
        initial_status="running",
    )
    assert replay.kind == "replay"
    assert replay.job is not None
    assert replay.job["status"] == "succeeded"
    assert replay.job["result_run_id"] == run_id


def test_late_finalizer_cannot_supersede_terminal_reconciliation() -> None:
    store = AlphaStore()
    stale = _admit(
        store,
        key="late-success",
        identity="sha256:" + "9" * 64,
        scope=admission.DIRECT_RUN_SCOPE,
        initial_status="running",
    )
    assert stale.job is not None
    job_id = stale.job["id"]
    store.backtest_jobs[job_id]["started_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=16)
    ).isoformat()

    reconciled = admission.reconcile_stale_direct_jobs_memory(store)
    assert reconciled == 1
    assert store.backtest_jobs[job_id]["status"] == "failed"

    late = admission.finalize_direct_job_memory(
        store,
        job_id=job_id,
        status="succeeded",
        result_run_id="late-run",
    )
    assert late is not None
    assert late["status"] == "failed"
    assert store.backtest_jobs[job_id]["status"] == "failed"
    assert store.backtest_jobs[job_id]["result_run_id"] is None


def test_stale_replay_reconciles_only_that_row() -> None:
    store = AlphaStore()
    stale = _admit(
        store,
        key="stale-key",
        identity="sha256:" + "3" * 64,
        scope=admission.DIRECT_RUN_SCOPE,
        initial_status="running",
    )
    assert stale.job is not None
    store.backtest_jobs[stale.job["id"]]["started_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=16)
    ).isoformat()

    replay = _admit(
        store,
        key="stale-key",
        identity="sha256:" + "3" * 64,
        scope=admission.DIRECT_RUN_SCOPE,
        initial_status="running",
    )
    assert replay.kind == "replay"
    assert replay.job is not None
    assert replay.job["status"] == "failed"
    assert replay.job["failure_code"] == "direct_execution_abandoned"
