"""Durable, leased local work. Handlers call existing financial truth owners."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import sqlite3
import time
from datetime import date as CalendarDate
from typing import Literal
from uuid import uuid4

from pydantic import Field, ValidationError

from ..store import Store
from .common import Context, Model, PlatformError, require_owner
from .runtime import is_database_busy, policy_for, read_policy

logger = logging.getLogger("clara.jobs")
JobKind = Literal["deposit_load", "fixture_price_load", "recurring_investments"]
MARKET_KINDS = ("deposit_load", "fixture_price_load")


class DepositLoad(Model):
    scenario: Literal[
        "baseline", "same_winner", "leader_changed", "inflation_crossed", "failure"
    ]
    load_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")


class FixturePriceLoad(Model):
    outcome: Literal["success", "failure"] = "success"


class RecurringInvestments(Model):
    date: CalendarDate
    cursor: str | None = Field(default=None, max_length=512)


PAYLOADS = {
    "deposit_load": DepositLoad,
    "fixture_price_load": FixturePriceLoad,
    "recurring_investments": RecurringInvestments,
}
SCHEMA = """
CREATE TABLE IF NOT EXISTS p_runtime_jobs (
 id TEXT PRIMARY KEY, household_id TEXT, requested_by TEXT,
 kind TEXT NOT NULL CHECK(kind IN ('deposit_load','fixture_price_load','recurring_investments')),
 scope TEXT NOT NULL, dedupe_key TEXT NOT NULL, payload_hash TEXT NOT NULL,
 payload TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('queued','running','succeeded','failed')),
 created_at REAL NOT NULL, available_at REAL NOT NULL,
 lease_owner TEXT, lease_until REAL, attempt_count INTEGER NOT NULL DEFAULT 0,
 completed_at REAL, result_ref TEXT, error_code TEXT, correlation_id TEXT NOT NULL,
 UNIQUE(kind,scope,dedupe_key)
);
CREATE INDEX IF NOT EXISTS p_runtime_jobs_ready
 ON p_runtime_jobs(status,available_at,created_at);
CREATE INDEX IF NOT EXISTS p_runtime_jobs_household
 ON p_runtime_jobs(household_id,status,created_at);
CREATE INDEX IF NOT EXISTS p_runtime_jobs_expiry
 ON p_runtime_jobs(status,lease_until);
"""


def initialize_jobs(store: Store) -> None:
    with store.connection(write=True) as connection:
        connection.executescript(SCHEMA)


def owns_deposit_load(connection: sqlite3.Connection, load_id: str) -> bool:
    if (
        connection.execute(
            "SELECT 1 FROM sqlite_schema WHERE name='p_runtime_jobs'"
        ).fetchone()
        is None
    ):
        return False
    return (
        connection.execute(
            "SELECT 1 FROM p_runtime_jobs WHERE kind='deposit_load' AND status IN ('queued','running') "
            "AND json_extract(payload,'$.load_id')=? LIMIT 1",
            (load_id,),
        ).fetchone()
        is not None
    )


def _fail_domain_load(
    store: Store, connection: sqlite3.Connection, job, error_code: str
) -> None:
    if job["kind"] == "deposit_load":
        from ..service import fail_load_in_transaction

        payload = DepositLoad.model_validate_json(job["payload"])
        fail_load_in_transaction(connection, payload.load_id, error_code)


def _public(row: sqlite3.Row | dict) -> dict:
    return {
        key: row[key]
        for key in (
            "id",
            "kind",
            "status",
            "created_at",
            "available_at",
            "attempt_count",
            "completed_at",
            "result_ref",
            "error_code",
            "correlation_id",
        )
    }


def enqueue_job(
    store: Store,
    context: Context | None,
    kind: JobKind,
    payload: dict | Model,
    idempotency_key: str,
    correlation_id: str | None = None,
) -> dict:
    if kind not in PAYLOADS:
        raise PlatformError("unknown_job_kind")
    if context is not None:
        require_owner(context)
        if kind == "recurring_investments":
            raise PlatformError("scheduler_required", 403)
    if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 128:
        raise PlatformError("invalid_idempotency_key")
    try:
        value = PAYLOADS[kind].model_validate(
            payload.model_dump() if isinstance(payload, Model) else payload
        )
    except ValidationError:
        raise PlatformError("invalid_job_payload") from None
    document = json.dumps(
        value.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )
    fingerprint = hashlib.sha256(document.encode()).hexdigest()
    household = context.household_id if context else None
    scope = f"household:{household}" if context else "scheduler"
    at = time.time()
    with store.connection(write=True) as connection:
        policy = read_policy(connection)
        previous = connection.execute(
            "SELECT * FROM p_runtime_jobs WHERE kind=? AND scope=? AND dedupe_key=?",
            (kind, scope, idempotency_key),
        ).fetchone()
        if previous:
            if previous["payload_hash"] != fingerprint:
                raise PlatformError("job_idempotency_conflict", 409)
            return _public(previous)
        counts = connection.execute(
            "SELECT COUNT(*) AS total,COALESCE(SUM(scope=?),0) AS owned FROM p_runtime_jobs WHERE status='queued'",
            (scope,),
        ).fetchone()
        if (
            counts["total"] >= policy.global_queued_jobs
            or counts["owned"] >= policy.household_queued_jobs
        ):
            raise PlatformError("job_queue_full", 429)
        if kind == "deposit_load":
            from ..service import PlacementService

            PlacementService(store).begin_load(
                value.scenario, load_id=value.load_id, connection=connection
            )
        job_id = uuid4().hex
        # Only server IDs are accepted as correlation metadata, never arbitrary input.
        correlation = (
            correlation_id
            if correlation_id
            and len(correlation_id) == 32
            and all(c in "0123456789abcdef" for c in correlation_id)
            else uuid4().hex
        )
        connection.execute(
            "INSERT INTO p_runtime_jobs(id,household_id,requested_by,kind,scope,dedupe_key,payload_hash,payload,status,created_at,available_at,correlation_id) VALUES(?,?,?,?,?,?,?,?,'queued',?,?,?)",
            (
                job_id,
                household,
                context.user_id if context else None,
                kind,
                scope,
                idempotency_key,
                fingerprint,
                document,
                at,
                at,
                correlation,
            ),
        )
        row = connection.execute(
            "SELECT * FROM p_runtime_jobs WHERE id=?", (job_id,)
        ).fetchone()
        return _public(row)


def get_job(store: Store, context: Context, job_id: str) -> dict:
    with store.connection() as connection:
        row = connection.execute(
            "SELECT * FROM p_runtime_jobs WHERE id=? AND household_id=?",
            (job_id, context.household_id),
        ).fetchone()
        if row is None:
            raise PlatformError("job_not_found", 404)
        return _public(row)


def get_job_internal(store: Store, job_id: str) -> dict:
    """Trusted local scheduler status; never mount as an unauthenticated route."""
    with store.connection() as connection:
        row = connection.execute(
            "SELECT * FROM p_runtime_jobs WHERE id=?", (job_id,)
        ).fetchone()
        if row is None:
            raise PlatformError("job_not_found", 404)
        return _public(row)


def list_jobs(
    store: Store, context: Context, *, limit: int = 50, offset: int = 0
) -> list[dict]:
    if not 1 <= limit <= 100 or not 0 <= offset <= 10000:
        raise PlatformError("invalid_job_page")
    with store.connection() as connection:
        return [
            _public(row)
            for row in connection.execute(
                "SELECT * FROM p_runtime_jobs WHERE household_id=? ORDER BY created_at DESC,id LIMIT ? OFFSET ?",
                (context.household_id, limit, offset),
            )
        ]


def claim(store: Store) -> dict | None:
    at = time.time()
    # Idle workers are readers. Acquire the single SQLite write slot only when
    # queued work or an expired lease may require an atomic state transition.
    with store.connection() as connection:
        ready = connection.execute(
            "SELECT 1 FROM p_runtime_jobs WHERE (status='queued' AND available_at<=?) "
            "OR (status='running' AND lease_until<=?) LIMIT 1",
            (at, at),
        ).fetchone()
        if ready is None:
            return None
    with store.connection(write=True) as connection:
        policy = read_policy(connection)
        # Price loading owns no idempotent domain operation ID. Mark an interrupted
        # load failed rather than inventing exactly-once behavior on recovery.
        expired = connection.execute(
            "UPDATE p_runtime_jobs SET status='failed',completed_at=?,error_code=CASE WHEN kind='fixture_price_load' THEN 'interrupted_nonreplayable_job' ELSE 'job_attempts_exhausted' END,lease_owner=NULL,lease_until=NULL WHERE status='running' AND lease_until<=? AND (attempt_count>=? OR kind='fixture_price_load') RETURNING kind,payload,error_code",
            (at, at, policy.job_max_attempts),
        ).fetchall()
        for expired_job in expired:
            _fail_domain_load(store, connection, expired_job, expired_job["error_code"])
        connection.execute(
            "UPDATE p_runtime_jobs SET status='queued',available_at=?,lease_owner=NULL,lease_until=NULL,error_code='worker_lease_expired' WHERE status='running' AND lease_until<=?",
            (at, at),
        )
        running = connection.execute(
            "SELECT SUM(kind IN ('deposit_load','fixture_price_load')) AS market,SUM(kind='recurring_investments') AS ordinary FROM p_runtime_jobs WHERE status='running'"
        ).fetchone()
        row = connection.execute(
            """SELECT queued.* FROM p_runtime_jobs queued
            WHERE queued.status='queued' AND queued.available_at<=?
            AND (SELECT COUNT(*) FROM p_runtime_jobs active WHERE active.scope=queued.scope AND active.status='running')<?
            AND ((queued.kind IN ('deposit_load','fixture_price_load') AND ?<?)
              OR (queued.kind='recurring_investments' AND ?<?))
            ORDER BY queued.created_at,queued.id LIMIT 1""",
            (
                at,
                policy.household_running_jobs,
                running["market"] or 0,
                policy.market_slots,
                running["ordinary"] or 0,
                policy.worker_slots,
            ),
        ).fetchone()
        if row is None:
            return None
        token = uuid4().hex
        connection.execute(
            "UPDATE p_runtime_jobs SET status='running',lease_owner=?,lease_until=?,attempt_count=attempt_count+1,error_code=NULL WHERE id=?",
            (token, at + policy.job_lease_seconds, row["id"]),
        )
        return dict(
            connection.execute(
                "SELECT * FROM p_runtime_jobs WHERE id=?", (row["id"],)
            ).fetchone()
        )


def heartbeat(store: Store, job: dict) -> bool:
    at = time.time()
    with store.connection(write=True) as connection:
        policy = read_policy(connection)
        return bool(
            connection.execute(
                "UPDATE p_runtime_jobs SET lease_until=? WHERE id=? AND status='running' AND lease_owner=? AND lease_until>?",
                (at + policy.job_lease_seconds, job["id"], job["lease_owner"], at),
            ).rowcount
        )


def _finish(
    store: Store,
    job: dict,
    *,
    result_ref: str | None = None,
    error_code: str | None = None,
) -> bool:
    at = time.time()
    with store.connection(write=True) as connection:
        updated = bool(
            connection.execute(
                "UPDATE p_runtime_jobs SET status=?,completed_at=?,result_ref=?,error_code=?,lease_owner=NULL,lease_until=NULL WHERE id=? AND status='running' AND lease_owner=? AND lease_until>?",
                (
                    "failed" if error_code else "succeeded",
                    at,
                    result_ref,
                    error_code,
                    job["id"],
                    job["lease_owner"],
                    at,
                ),
            ).rowcount
        )
        if updated and error_code:
            _fail_domain_load(store, connection, job, error_code)
    if updated:
        logger.info(
            json.dumps(
                {
                    "request_id": job["correlation_id"],
                    "job_kind": job["kind"],
                    "state": "failed" if error_code else "succeeded",
                    "error_code": error_code,
                },
                sort_keys=True,
            )
        )
    return updated


def complete(store: Store, job: dict, result_ref: str | None = None) -> bool:
    return _finish(store, job, result_ref=result_ref)


def fail(store: Store, job: dict, error_code: str = "job_failed") -> bool:
    # Handler exceptions and their text never enter operational records.
    allowed = {
        "job_failed",
        "domain_load_failed",
        "database_busy",
        "job_authorization_revoked",
    }
    return _finish(
        store, job, error_code=error_code if error_code in allowed else "job_failed"
    )


def execute_job(store: Store, job: dict) -> tuple[str | None, str | None]:
    payload = PAYLOADS[job["kind"]].model_validate_json(job["payload"])
    if job["kind"] == "deposit_load":
        from ..providers import FixtureProvider
        from ..service import PlacementService

        service = PlacementService(store)
        load_id = service.begin_load(payload.scenario, load_id=payload.load_id)
        service.finish_load(load_id, FixtureProvider(payload.scenario))
        result = service.load_status(load_id)
    elif job["kind"] == "fixture_price_load":
        from .market_data import FixtureMarketDataAdapter, load_market_prices

        result = load_market_prices(store, FixtureMarketDataAdapter(payload.outcome))
    else:
        from .investing import run_due_recurring_plans

        page = run_due_recurring_plans(store, payload.date, cursor=payload.cursor)
        if page["next_cursor"]:
            cursor = page["next_cursor"]
            enqueue_job(
                store,
                None,
                "recurring_investments",
                {"date": payload.date.isoformat(), "cursor": cursor},
                f"{job['id']}:{hashlib.sha256(cursor.encode()).hexdigest()[:32]}",
                job["correlation_id"],
            )
        # Receipts remain in their domain; operational jobs never copy finances.
        return None, "domain_load_failed" if any(
            item.get("status") == "failed" for item in page["items"]
        ) else None
    return str(result["id"]), "domain_load_failed" if result[
        "status"
    ] == "failed" else None


def _execute_and_finish(store: Store, job: dict) -> None:
    try:
        with store.connection() as connection:
            active = connection.execute(
                "SELECT 1 FROM p_runtime_jobs WHERE id=? AND status='running' AND lease_owner=? AND lease_until>?",
                (job["id"], job["lease_owner"], time.time()),
            ).fetchone()
            if active is None:
                return
            if job["requested_by"] is not None:
                authorized = connection.execute(
                    "SELECT 1 FROM p_memberships membership JOIN p_users person ON person.id=membership.user_id "
                    "WHERE membership.household_id=? AND membership.user_id=? AND membership.role='owner' AND person.deleted_at IS NULL",
                    (job["household_id"], job["requested_by"]),
                ).fetchone()
                if authorized is None:
                    # Release the read snapshot before attempting a terminal write.
                    raise PlatformError("job_authorization_revoked", 403)
        result_ref, error = execute_job(store, job)
    except PlatformError as exc:
        fail(store, job, exc.code)
    except sqlite3.OperationalError as exc:
        fail(store, job, "database_busy" if is_database_busy(exc) else "job_failed")
    except Exception:
        fail(store, job)
    else:
        if error:
            fail(store, job, error)
        else:
            complete(store, job, result_ref)


def worker_tick(store: Store) -> dict | None:
    """Synchronous CLI entry to the same renewed execution used by lifespan."""
    return asyncio.run(run_one(store))


async def run_one(store: Store) -> dict | None:
    """Claim and finish one local job with renewal; safe for async callers."""
    policy = await asyncio.to_thread(policy_for, store)
    job = await asyncio.to_thread(claim, store)
    if job is None:
        return None
    await _execute_with_lease(store, job, policy.job_lease_seconds)
    return await asyncio.to_thread(get_job_internal, store, job["id"])


async def _execute_with_lease(store: Store, job: dict, lease_seconds: int) -> None:
    async def supervise() -> None:
        work = asyncio.create_task(asyncio.to_thread(_execute_and_finish, store, job))
        renewed = time.monotonic()
        while not work.done():
            await asyncio.wait({work}, timeout=min(1, lease_seconds / 3))
            if not work.done() and time.monotonic() - renewed >= lease_seconds / 3:
                await asyncio.to_thread(heartbeat, store, job)
                renewed = time.monotonic()
        await work

    supervision = asyncio.create_task(supervise())
    try:
        await asyncio.shield(supervision)
    except asyncio.CancelledError:
        # Local threads cannot be cancelled safely. Keep their existing renewal
        # supervisor alive while draining work, including during CLI shutdown.
        await asyncio.shield(supervision)
        raise


async def _worker_slot(
    store: Store, stop_event: asyncio.Event, lease_seconds: int
) -> None:
    while not stop_event.is_set():
        try:
            job = await asyncio.to_thread(claim, store)
            if job is None:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=0.25)
                except asyncio.TimeoutError:
                    pass
                continue
            await _execute_with_lease(store, job, lease_seconds)
        except sqlite3.OperationalError as exc:
            if not is_database_busy(exc):
                raise
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=0.25)
            except asyncio.TimeoutError:
                pass


async def run_worker(store: Store, stop_event: asyncio.Event) -> None:
    policy = await asyncio.to_thread(policy_for, store)
    await asyncio.gather(
        *(
            _worker_slot(store, stop_event, policy.job_lease_seconds)
            for _ in range(policy.worker_slots + policy.market_slots)
        )
    )


def clear_data(connection: sqlite3.Connection, context: Context) -> None:
    from ..service import fail_load_in_transaction

    # The supplied connection owns this lifecycle transaction; the service uses
    # it directly, so constructing a second Store is neither needed nor safe.
    for row in connection.execute(
        "SELECT payload FROM p_runtime_jobs WHERE household_id=? AND kind='deposit_load' AND status IN ('queued','running')",
        (context.household_id,),
    ).fetchall():
        payload = DepositLoad.model_validate_json(row["payload"])
        fail_load_in_transaction(connection, payload.load_id, "job_authorization_revoked")
    connection.execute(
        "DELETE FROM p_runtime_jobs WHERE household_id=?", (context.household_id,)
    )
    # Product reset cannot cancel an in-flight provider or refund an attempt.
    # Opaque admission keys contain no product content and follow the runtime's
    # lease expiry and 31-day aggregate retention, including after deletion.
