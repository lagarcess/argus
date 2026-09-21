"""Cross-process admission, fenced recovery and bounded HTTP transport."""

import asyncio
import json
import logging
import multiprocessing
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from platform_identity_factory import identity_context
from pydantic import ValidationError
from server.platform import jobs_runtime as jobs
from server.platform import runtime
from server.platform.common import PlatformError
from server.platform.identity import Identity
from server.platform.identity_lifecycle import advance_household_generation
from server.store import Store


@pytest.fixture
def context(store):
    return identity_context(store)


@pytest.fixture
def store(tmp_path):
    value = Store(tmp_path / "runtime.sqlite")
    Identity(value).initialize()
    runtime.initialize(value)
    return value


def enqueue(store, context, key="first", **overrides):
    return jobs.enqueue_job(
        store,
        context,
        "deposit_load",
        {"scenario": "same_winner", "load_id": key, **overrides},
        key,
    )


def assert_error(code, function, *args, **kwargs):
    with pytest.raises(PlatformError) as error:
        function(*args, **kwargs)
    assert error.value.code == code


def test_replay_conflict_queue_limit_and_owned_status(store, context):
    first = enqueue(store, context)
    assert enqueue(store, context) == first
    assert_error("job_idempotency_conflict", enqueue, store, context, scenario="failure")
    enqueue(store, context, "second")
    assert_error("job_queue_full", enqueue, store, context, "third")
    assert enqueue(store, context) == first  # Replay remains possible when full.
    other = identity_context(store, household_id="other")
    assert_error("job_not_found", jobs.get_job, store, other, first["id"])
    assert not set(first) & {"payload", "household_id", "requested_by", "lease_owner"}
    viewer = identity_context(store, user_id="user-viewer", role="viewer")
    assert_error("owner_required", enqueue, store, viewer)
    assert_error(
        "invalid_job_payload", enqueue, store, context, "bad", scenario="network"
    )


def _process_claim(path, barrier, output):
    store = Store(path)
    barrier.wait(timeout=10)
    job = jobs.claim(store)
    output.put(job["id"] if job else None)


def test_independent_processes_cannot_double_claim(store, context):
    submitted = enqueue(store, context)
    pool = multiprocessing.get_context("spawn")
    barrier, output = pool.Barrier(3), pool.Queue()
    children = [
        pool.Process(target=_process_claim, args=(store.path, barrier, output))
        for _ in range(3)
    ]
    for child in children:
        child.start()
    received = [output.get(timeout=15) for _ in children]
    for child in children:
        child.join(15)
        assert child.exitcode == 0
    assert received.count(submitted["id"]) == 1
    assert received.count(None) == 2


def test_fair_claim_excludes_busy_households_and_reserves_market_slot(tmp_path):
    store = Store(tmp_path / "fair.sqlite")
    context = identity_context(store)
    quiet_context = identity_context(store, household_id="quiet")
    runtime.initialize(store, runtime.RuntimePolicy(market_slots=2))
    enqueue(store, context, "busy-one")
    first = jobs.claim(store)
    enqueue(store, context, "busy-two")
    quiet = enqueue(store, quiet_context, "quiet")
    assert jobs.claim(store)["id"] == quiet["id"]
    assert jobs.claim(store) is None
    scheduled = jobs.enqueue_job(
        store, None, "recurring_investments", {"date": "2026-09-20"}, "scheduled"
    )
    assert jobs.claim(store)["id"] == scheduled["id"]
    assert jobs.complete(store, first)
    assert jobs.claim(store)["payload"] == json.dumps(
        {"load_id": "busy-two", "scenario": "same_winner"}, separators=(",", ":")
    )


def test_recovery_fences_old_workers_and_exhausts_attempts(store, context, monkeypatch):
    now = [100.0]
    monkeypatch.setattr(jobs.time, "time", lambda: now[0])
    submitted = enqueue(store, context)
    first = jobs.claim(store)
    now[0] = first["lease_until"] + 1
    second = jobs.claim(store)
    assert second["id"] == first["id"]
    assert second["lease_owner"] != first["lease_owner"]
    assert second["attempt_count"] == 2
    assert not jobs.complete(store, first, "stale")
    assert not jobs.heartbeat(store, first)
    now[0] = second["lease_until"] + 1
    third = jobs.claim(store)
    now[0] = third["lease_until"] + 1
    assert jobs.claim(store) is None
    terminal = jobs.get_job(store, context, submitted["id"])
    assert terminal["error_code"] == "job_attempts_exhausted"
    assert terminal["status"] == "failed"


def test_heartbeat_extends_lease_and_terminal_writes_are_once(
    store, context, monkeypatch
):
    now = [100.0]
    monkeypatch.setattr(jobs.time, "time", lambda: now[0])
    enqueue(store, context)
    job = jobs.claim(store)
    now[0] += 20
    assert jobs.heartbeat(store, job)
    now[0] += 20
    assert jobs.complete(store, job, "receipt")
    assert not jobs.fail(store, job)
    assert jobs.get_job(store, context, job["id"])["result_ref"] == "receipt"


def test_nonreplayable_price_load_is_failed_after_worker_crash(
    store, context, monkeypatch
):
    jobs.enqueue_job(
        store, context, "fixture_price_load", {"outcome": "success"}, "prices"
    )
    job = jobs.claim(store)
    monkeypatch.setattr(jobs.time, "time", lambda: job["lease_until"] + 1)
    assert jobs.claim(store) is None
    assert (
        jobs.get_job(store, context, job["id"])["error_code"]
        == "interrupted_nonreplayable_job"
    )


@pytest.mark.parametrize(
    "kind,payload",
    [
        ("deposit_load", {"scenario": "failure", "load_id": "failed-load"}),
        ("fixture_price_load", {"outcome": "failure"}),
    ],
)
def test_failed_domain_load_keeps_last_good_data(store, context, kind, payload):
    from server.platform import market_data
    from server.service import PlacementService

    service = PlacementService(store)
    service.bootstrap()
    market_data.initialize(store)
    market_data.load_market_prices(store, market_data.FixtureMarketDataAdapter())
    with store.connection() as connection:
        before_datasets = connection.execute("SELECT COUNT(*) FROM datasets").fetchone()[
            0
        ]
        before_prices = connection.execute(
            "SELECT COUNT(*) FROM p_market_prices"
        ).fetchone()[0]
    jobs.enqueue_job(store, context, kind, payload, "failed")
    result = jobs.worker_tick(store)
    assert result["status"] == "failed"
    assert result["error_code"] == "domain_load_failed"
    with store.connection() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM datasets").fetchone()[0]
            == before_datasets
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM p_market_prices").fetchone()[0]
            == before_prices
        )


def test_successful_deposit_restart_reuses_domain_operation(store, context):
    from server.service import PlacementService

    PlacementService(store).bootstrap()
    first = enqueue(store, context)
    assert jobs.worker_tick(store)["status"] == "succeeded"
    reopened = Store(store.path)
    runtime.initialize(reopened)
    assert enqueue(reopened, context)["id"] == first["id"]
    assert jobs.worker_tick(reopened) is None
    with reopened.connection() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM load_attempts WHERE id='first'"
            ).fetchone()[0]
            == 1
        )


def test_model_concurrency_daily_caps_expiry_and_isolation(tmp_path, monkeypatch):
    store = Store(tmp_path / "model.sqlite")
    context = identity_context(store)
    other = identity_context(store, household_id="other")
    third_context = identity_context(store, household_id="third")
    runtime.initialize(
        store,
        runtime.RuntimePolicy(
            model_household_daily=2, model_global_daily=3, model_global_concurrent=2
        ),
    )
    first = runtime.acquire_model(store, context)
    assert_error(
        "model_concurrency_exceeded", runtime.acquire_model, Store(store.path), context
    )
    second = runtime.acquire_model(Store(store.path), other)
    assert_error(
        "model_concurrency_exceeded",
        runtime.acquire_model,
        store,
        third_context,
    )
    runtime.release_model(store, first, "failed")
    runtime.release_model(store, first, "completed")
    third = runtime.acquire_model(store, context)
    runtime.release_model(store, third)
    assert_error("model_daily_limit_exceeded", runtime.acquire_model, store, context)
    assert_error(
        "model_daily_limit_exceeded",
        runtime.acquire_model,
        store,
        third_context,
    )
    monkeypatch.setattr(runtime.time, "time", lambda: second.expires_at + 1)
    runtime.release_model(store, second)
    assert runtime.usage(store, context)["model"]["attempts"] == 2
    assert runtime.usage(store, context)["model"]["failed"] == 1
    assert runtime.usage(store, other)["model"]["expired"] == 1
    assert runtime.usage(store, other)["model"]["completed"] == 0


def test_parallel_model_admission_is_global_and_bounded(store):
    contexts = [
        identity_context(store, household_id=f"household-{index}") for index in range(12)
    ]
    independent_stores = [Store(store.path) for _ in contexts]

    def acquire(index):
        try:
            return runtime.acquire_model(independent_stores[index], contexts[index])
        except PlatformError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=len(contexts)) as pool:
        results = list(pool.map(acquire, range(len(contexts))))
    leases = [item for item in results if isinstance(item, runtime.ModelLease)]
    assert len(leases) == runtime.RuntimePolicy().model_global_concurrent
    assert results.count("model_concurrency_exceeded") == len(contexts) - len(leases)
    for lease in leases:
        runtime.release_model(store, lease)


def test_login_admission_is_shared_and_window_storage_is_bounded(tmp_path, monkeypatch):
    store = Store(tmp_path / "login.sqlite")
    runtime.initialize(
        store, runtime.RuntimePolicy(login_ip_per_minute=2, login_global_per_minute=3)
    )
    at = [6000.0]
    monkeypatch.setattr(runtime.time, "time", lambda: at[0])
    runtime.admit_login(store, "127.0.0.1")
    runtime.admit_login(Store(store.path), "127.0.0.1")
    assert_error("login_rate_exceeded", runtime.admit_login, store, "127.0.0.1")
    runtime.admit_login(store, "127.0.0.2")
    assert_error("login_rate_exceeded", runtime.admit_login, store, "127.0.0.3")
    at[0] += 60
    runtime.admit_login(store, "127.0.0.3")
    with store.connection() as connection:
        rows = connection.execute("SELECT * FROM p_runtime_login_windows").fetchall()
        assert len(rows) == 2
        assert "127.0.0" not in str([dict(row) for row in rows])


def app_with_runtime(store):
    app = FastAPI()
    app.state.store = store
    app.add_middleware(runtime.RuntimeMiddleware)

    @app.post("/api/echo/{record_id}")
    async def echo(record_id: str, request: Request):
        return {"body": await request.json()}

    @app.post("/api/platform/imports/preview")
    async def preview(request: Request):
        return {"bytes": len(await request.body())}

    return app


def test_correlation_route_template_logs_exclude_user_content(store, caplog):
    app = app_with_runtime(store)
    with caplog.at_level(logging.INFO, logger="clara.runtime"), TestClient(app) as client:
        response = client.post(
            "/api/echo/private-account?token=secret-query",
            json={"message": "private-question"},
            headers={"X-Request-ID": "untrusted", "Cookie": "secret-cookie"},
        )
    assert response.status_code == 200
    assert len(response.headers["x-request-id"]) == 32
    record = json.loads(caplog.records[-1].message)
    assert record["request_id"] == response.headers["x-request-id"]
    assert record["route"] == "/api/echo/{record_id}"
    assert record["duration_ms"] >= 0
    for secret in (
        "private-account",
        "secret-query",
        "private-question",
        "secret-cookie",
        "untrusted",
    ):
        assert secret not in caplog.text


def test_body_and_header_limits_apply_before_parsing_with_csv_exception(store):
    app = app_with_runtime(store)
    with TestClient(app) as client:
        too_big = "x" * (runtime.RuntimePolicy().request_body_bytes + 1)
        rejected = client.post("/api/echo/one", content=too_big)
        assert rejected.status_code == 413
        assert rejected.json() == {"code": "request_body_too_large"}
        assert len(rejected.headers["x-request-id"]) == 32
        assert (
            client.post("/api/platform/imports/preview", content=too_big).status_code
            == 200
        )
        assert (
            client.post(
                "/api/echo/one", content="{}", headers={"Large": "x" * 17000}
            ).status_code
            == 431
        )


def test_chunked_body_limit_without_content_length(store):
    async def run():
        async def chunks():
            for _ in range(3):
                yield b"x" * 32768

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_with_runtime(store)),
            base_url="http://testserver",
        ) as client:
            response = await client.post("/api/echo/chunked", content=chunks())
            assert response.status_code == 413

    asyncio.run(run())


def test_database_lock_exhaustion_maps_to_retryable_503(store):
    app = app_with_runtime(store)
    short_store = Store(store.path, busy_timeout_ms=20)

    @app.post("/api/write")
    def write():
        with short_store.connection(write=True) as connection:
            connection.execute(
                "INSERT INTO p_runtime_login_windows VALUES(1,'blocked',1)"
            )
        return {"ok": True}

    with TestClient(app) as client, store.connection(write=True):
        started = time.perf_counter()
        response = client.post("/api/write", content="{}")
        assert response.status_code == 503
        assert response.json() == {"code": "database_busy"}
        assert response.headers["retry-after"] == "1"
        assert time.perf_counter() - started < 0.5


def test_worker_runs_off_event_loop_and_drains_on_stop(store, context, monkeypatch):
    submitted = enqueue(store, context)
    finished = []

    def execute(_store, _job):
        time.sleep(0.12)
        finished.append(True)
        return "local-receipt", None

    monkeypatch.setattr(jobs, "execute_job", execute)

    async def run():
        stop = asyncio.Event()
        worker = asyncio.create_task(jobs.run_worker(store, stop))
        pulses = 0
        while not finished:
            await asyncio.sleep(0.01)
            pulses += 1
            if pulses > 100:
                pytest.fail("worker did not finish bounded local operation")
        stop.set()
        await asyncio.wait_for(worker, 2)
        assert pulses >= 5

    asyncio.run(run())
    assert jobs.get_job(store, context, submitted["id"])["status"] == "succeeded"


@pytest.mark.parametrize("entrypoint", ["worker_tick", "run_one", "cli"])
def test_single_job_entrypoints_renew_past_initial_lease(
    tmp_path, monkeypatch, entrypoint
):
    from server import jobs as cli

    monkeypatch.setenv("CLARA_RUNTIME_JOB_LEASE_SECONDS", "3")
    monkeypatch.setenv("CLARA_RUNTIME_JOB_MAX_ATTEMPTS", "1")
    store = Store(tmp_path / "renewed-cli.sqlite")
    runtime.initialize(store)
    submitted = jobs.enqueue_job(
        store,
        None,
        "deposit_load",
        {"scenario": "same_winner", "load_id": "long-load"},
        "long-load",
    )
    started, finish = Event(), Event()
    calls = []
    execute = jobs.execute_job

    def delayed_execute(selected, job):
        calls.append(job["id"])
        started.set()
        assert finish.wait(8), "test did not release controlled local work"
        return execute(selected, job)

    monkeypatch.setattr(jobs, "execute_job", delayed_execute)

    def invoke():
        if entrypoint == "cli":
            return cli.main(
                [
                    "--database",
                    str(store.path),
                    "load",
                    "--scenario",
                    "same_winner",
                    "--load-id",
                    "long-load",
                ]
            )
        if entrypoint == "run_one":
            return asyncio.run(jobs.run_one(store))
        return jobs.worker_tick(store)

    competitor = Store(store.path)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(invoke)
        try:
            assert started.wait(2)
            with store.connection() as connection:
                first_expiry = connection.execute(
                    "SELECT lease_until FROM p_runtime_jobs WHERE id=?",
                    (submitted["id"],),
                ).fetchone()[0]
            while time.time() <= first_expiry + 0.05:
                assert jobs.claim(competitor) is None
                finish.wait(0.025)
            assert not future.done()
            assert jobs.claim(competitor) is None
            with store.connection() as connection:
                live = connection.execute(
                    "SELECT status,attempt_count,lease_until FROM p_runtime_jobs WHERE id=?",
                    (submitted["id"],),
                ).fetchone()
                assert live["status"] == "running"
                assert live["attempt_count"] == 1
                assert live["lease_until"] > time.time()
        finally:
            finish.set()
        result = future.result(timeout=3)
    assert result == 0 if entrypoint == "cli" else result["status"] == "succeeded"
    assert calls == [submitted["id"]]
    terminal = jobs.get_job_internal(store, submitted["id"])
    assert terminal["status"] == "succeeded"
    assert terminal["attempt_count"] == 1
    assert jobs.claim(competitor) is None


def test_idle_worker_does_not_acquire_write_lock(store):
    reader = Store(store.path, busy_timeout_ms=0)
    with store.connection(write=True):
        assert jobs.claim(reader) is None


def test_policy_conflicts_fail_instead_of_splitting_shared_limits(store):
    assert_error(
        "runtime_configuration_mismatch",
        runtime.initialize,
        Store(store.path),
        runtime.RuntimePolicy(model_global_concurrent=8),
    )


def test_household_cleanup_does_not_delete_other_usage(store, context):
    other = identity_context(store, household_id="other")
    enqueue(store, context)
    untouched = enqueue(store, other, "other")
    runtime.acquire_model(store, context)
    runtime.acquire_model(store, other)
    with store.connection(write=True) as connection:
        jobs.clear_data(connection, context)
    assert jobs.list_jobs(store, context) == []
    assert jobs.get_job(store, other, untouched["id"])["id"] == untouched["id"]
    assert runtime.usage(store, context)["model"]["attempts"] == 1
    assert runtime.usage(store, other)["model"]["attempts"] == 1


def test_household_reset_neither_releases_live_model_nor_refunds_daily_attempt(
    tmp_path,
):
    store = Store(tmp_path / "reset-quota.sqlite")
    context = identity_context(store)
    runtime.initialize(
        store,
        runtime.RuntimePolicy(
            model_household_daily=1,
            model_global_daily=1,
            model_household_concurrent=1,
            model_global_concurrent=1,
        ),
    )
    lease = runtime.acquire_model(store, context)
    with store.connection(write=True) as connection:
        jobs.clear_data(connection, context)
        advance_household_generation(connection, context.household_id)
    current = identity_context(store)
    assert_error("model_concurrency_exceeded", runtime.acquire_model, store, current)
    assert runtime.usage(store, context)["model"]["active"] == 1
    assert runtime.usage(store, context)["model"]["attempts"] == 1
    runtime.release_model(store, lease)
    assert_error("model_daily_limit_exceeded", runtime.acquire_model, store, current)
    assert runtime.usage(store, context)["model"]["active"] == 0
    assert runtime.usage(store, context)["model"]["completed"] == 1


def test_model_whole_call_deadline_bounds_progressing_provider(tmp_path):
    store = Store(tmp_path / "deadline.sqlite")
    context = identity_context(store)
    runtime.initialize(store, runtime.RuntimePolicy(model_call_seconds=0.05))
    chunks = []

    async def progressing_provider(_request):
        # Frequent progress would keep a ten-second inactivity timeout alive.
        for index in range(100):
            await asyncio.sleep(0.005)
            chunks.append(index)
        return httpx.Response(200, json={"ok": True})

    async def run():
        with pytest.raises(httpx.ReadTimeout, match="model_call_deadline_exceeded"):
            async with runtime.model_admission(store, context):
                async with httpx.AsyncClient(
                    transport=httpx.MockTransport(progressing_provider), timeout=10
                ) as client:
                    await client.get("https://example.test/mock-only")

    started = time.monotonic()
    asyncio.run(run())
    assert time.monotonic() - started < 0.5
    assert 1 <= len(chunks) < 100
    measured = runtime.usage(store, context)["model"]
    assert measured["attempts"] == measured["timeout"] == 1
    assert measured["active"] == measured["cancelled"] == 0


@pytest.mark.parametrize("operation", ["enqueue", "acquire_model"])
def test_stale_context_cannot_admit_work_after_generation_change(
    store, context, operation
):
    with store.connection(write=True) as connection:
        advance_household_generation(connection, context.household_id)
    admit = enqueue if operation == "enqueue" else runtime.acquire_model
    assert_error("household_data_changed", admit, store, context)
    assert jobs.list_jobs(store, context) == []
    assert runtime.usage(store, context)["model"]["attempts"] == 0
    current = identity_context(store)
    assert current.data_generation > context.data_generation
    result = admit(store, current)
    if operation == "enqueue":
        assert result["status"] == "queued"
    else:
        runtime.release_model(store, result)


@pytest.mark.parametrize("deadline", [30, 31])
def test_model_deadline_cannot_reach_or_exceed_lease(deadline):
    with pytest.raises(ValidationError, match="shorter than"):
        runtime.RuntimePolicy(model_call_seconds=deadline, model_lease_seconds=30)


def test_revoked_owner_cannot_execute_already_queued_work(store, context):
    submitted = enqueue(store, context)
    with store.connection(write=True) as connection:
        connection.execute(
            "UPDATE p_memberships SET role='viewer' WHERE household_id=? AND user_id=?",
            (context.household_id, context.user_id),
        )
    completed = jobs.worker_tick(store)
    assert completed["id"] == submitted["id"]
    assert completed["error_code"] == "job_authorization_revoked"
    with store.connection() as connection:
        assert (
            connection.execute(
                "SELECT status FROM load_attempts WHERE id='first'"
            ).fetchone()[0]
            == "failed"
        )


def test_clear_after_claim_prevents_dispatch_and_finalizes_load(
    store, context, monkeypatch
):
    enqueue(store, context)
    claimed = jobs.claim(store)
    with store.connection(write=True) as connection:
        jobs.clear_data(connection, context)
    monkeypatch.setattr(
        jobs, "execute_job", lambda *_: pytest.fail("cleared job executed")
    )
    jobs._execute_and_finish(store, claimed)
    with store.connection() as connection:
        assert (
            connection.execute(
                "SELECT status FROM load_attempts WHERE id='first'"
            ).fetchone()[0]
            == "failed"
        )


def test_cancellation_during_model_admission_releases_eventual_lease(
    store, context, monkeypatch
):
    entering, proceed = Event(), Event()
    original = runtime.acquire_model

    def delayed_acquire(*args):
        entering.set()
        assert proceed.wait(2)
        return original(*args)

    monkeypatch.setattr(runtime, "acquire_model", delayed_acquire)

    async def request():
        async with runtime.model_admission(store, context):
            pytest.fail("cancelled call reached provider")

    async def run():
        task = asyncio.create_task(request())
        while not entering.is_set():
            await asyncio.sleep(0.001)
        task.cancel()
        proceed.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    measured = runtime.usage(store, context)["model"]
    assert measured["attempts"] == measured["cancelled"] == 1
    assert measured["active"] == 0


def test_body_receive_deadline_rejects_slow_client():
    messages = []

    async def downstream(*_):
        pytest.fail("slow body reached parser")

    async def receive():
        await asyncio.Future()

    async def send(message):
        messages.append(message)

    middleware = runtime.RuntimeMiddleware(
        downstream, policy=runtime.RuntimePolicy(request_body_seconds=1)
    )
    asyncio.run(
        middleware(
            {"type": "http", "path": "/api/slow", "method": "POST", "headers": []},
            receive,
            send,
        )
    )
    assert messages[0]["status"] == 408
    assert json.loads(messages[1]["body"])["code"] == "request_body_timeout"


def test_recurring_pages_enqueue_bounded_continuation(store, monkeypatch):
    from server.platform import investing

    calls = []

    def run_due(_store, run_on, *, cursor=None):
        calls.append((run_on.isoformat(), cursor))
        return {
            "items": [],
            "next_cursor": "opaque-cursor" if cursor is None else None,
            "next_poll_on": "2026-10-20",
        }

    monkeypatch.setattr(investing, "run_due_recurring_plans", run_due)
    jobs.enqueue_job(
        store, None, "recurring_investments", {"date": "2026-09-20"}, "scheduled"
    )
    assert jobs.worker_tick(store)["status"] == "succeeded"
    assert jobs.worker_tick(store)["status"] == "succeeded"
    assert jobs.worker_tick(store) is None
    assert calls == [("2026-09-20", None), ("2026-09-20", "opaque-cursor")]
