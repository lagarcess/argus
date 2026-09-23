"""Shared SQLite admission and bounded HTTP transport for the local platform."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import sqlite3
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

import anyio
import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from ..store import Store
from .common import Context, PlatformError, assert_active_context, get_context, get_store

logger = logging.getLogger("clara.runtime")
router = APIRouter(prefix="/api/platform")


class RuntimePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    household_queued_jobs: int = Field(default=2, ge=1, le=100)
    global_queued_jobs: int = Field(default=500, ge=1, le=10000)
    household_running_jobs: int = Field(default=1, ge=1, le=4)
    worker_slots: int = Field(default=2, ge=1, le=16)
    market_slots: int = Field(default=1, ge=1, le=4)
    job_lease_seconds: int = Field(default=30, ge=3, le=300)
    job_max_attempts: int = Field(default=3, ge=1, le=10)
    model_household_daily: int = Field(default=50, ge=1, le=10000)
    model_global_daily: int = Field(default=1000, ge=1, le=1000000)
    model_household_concurrent: int = Field(default=1, ge=1, le=16)
    model_global_concurrent: int = Field(default=4, ge=1, le=100)
    model_lease_seconds: int = Field(default=30, ge=11, le=300)
    model_call_seconds: float = Field(default=10, gt=0, le=299)
    login_ip_per_minute: int = Field(default=10, ge=1, le=1000)
    login_global_per_minute: int = Field(default=100, ge=1, le=10000)
    request_body_bytes: int = Field(default=65536, ge=1024, le=1048576)
    csv_body_bytes: int = Field(default=2097152, ge=1024, le=4194304)
    request_header_bytes: int = Field(default=16384, ge=1024, le=65536)
    request_body_seconds: int = Field(default=10, ge=1, le=60)

    @model_validator(mode="after")
    def model_deadline_within_lease(self) -> RuntimePolicy:
        if self.model_call_seconds >= self.model_lease_seconds:
            raise ValueError(
                "model_call_seconds must be shorter than model_lease_seconds"
            )
        return self

    @classmethod
    def from_environment(cls) -> RuntimePolicy:
        # Process environment only; this module never reads or writes .env files.
        return cls.model_validate(
            {
                field: os.environ[f"CLARA_RUNTIME_{field.upper()}"]
                for field in cls.model_fields
                if f"CLARA_RUNTIME_{field.upper()}" in os.environ
            }
        )


SCHEMA = """
CREATE TABLE IF NOT EXISTS p_runtime_policy (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1), document TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS p_runtime_model_daily (
 day INTEGER NOT NULL, scope TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
 completed INTEGER NOT NULL DEFAULT 0, failed INTEGER NOT NULL DEFAULT 0,
 timeout INTEGER NOT NULL DEFAULT 0, cancelled INTEGER NOT NULL DEFAULT 0,
 expired INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(day,scope)
);
CREATE TABLE IF NOT EXISTS p_runtime_model_leases (
 id TEXT PRIMARY KEY, household_id TEXT NOT NULL, day INTEGER NOT NULL,
 expires_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS p_runtime_model_expiry
 ON p_runtime_model_leases(expires_at);
CREATE INDEX IF NOT EXISTS p_runtime_model_household
 ON p_runtime_model_leases(household_id,expires_at);
CREATE TABLE IF NOT EXISTS p_runtime_login_windows (
 window INTEGER NOT NULL, scope TEXT NOT NULL, attempts INTEGER NOT NULL,
 PRIMARY KEY(window,scope)
);
"""


def initialize(store: Store, policy: RuntimePolicy | None = None) -> None:
    selected = policy or RuntimePolicy.from_environment()
    with store.connection(write=True) as connection:
        connection.executescript(SCHEMA)
    with store.connection(write=True) as connection:
        connection.execute(
            "INSERT OR IGNORE INTO p_runtime_policy VALUES(1,?)",
            (selected.model_dump_json(),),
        )
        if read_policy(connection) != selected:
            raise PlatformError("runtime_configuration_mismatch", 503)
    from .jobs_runtime import initialize_jobs

    initialize_jobs(store)


def read_policy(connection: sqlite3.Connection) -> RuntimePolicy:
    row = connection.execute(
        "SELECT document FROM p_runtime_policy WHERE singleton=1"
    ).fetchone()
    if row is None:
        raise PlatformError("runtime_not_initialized", 503)
    return RuntimePolicy.model_validate_json(row[0])


def policy_for(store: Store) -> RuntimePolicy:
    with store.connection() as connection:
        return read_policy(connection)


def _household_scope(household_id: str) -> str:
    return f"household:{household_id}"


@dataclass(frozen=True)
class ModelLease:
    id: str
    household_id: str
    expires_at: float
    call_timeout_seconds: float


ModelOutcome = Literal["completed", "failed", "timeout", "cancelled"]


def _expire_models(connection: sqlite3.Connection, at: float) -> None:
    rows = connection.execute(
        "SELECT day,household_id,COUNT(*) AS count FROM p_runtime_model_leases "
        "WHERE expires_at<=? GROUP BY day,household_id",
        (at,),
    ).fetchall()
    for row in rows:
        connection.execute(
            "UPDATE p_runtime_model_daily SET expired=expired+? WHERE day=? AND scope IN (?,?)",
            (row["count"], row["day"], "global", _household_scope(row["household_id"])),
        )
    connection.execute("DELETE FROM p_runtime_model_leases WHERE expires_at<=?", (at,))


def acquire_model(store: Store, context: Context) -> ModelLease:
    at = time.time()
    day = int(at // 86400)
    with store.connection(write=True) as connection:
        assert_active_context(connection, context)
        policy = read_policy(connection)
        _expire_models(connection, at)
        active = connection.execute(
            "SELECT COUNT(*) AS total,COALESCE(SUM(household_id=?),0) AS household "
            "FROM p_runtime_model_leases",
            (context.household_id,),
        ).fetchone()
        if (
            active["total"] >= policy.model_global_concurrent
            or active["household"] >= policy.model_household_concurrent
        ):
            raise PlatformError("model_concurrency_exceeded", 429)
        for scope, limit in (
            ("global", policy.model_global_daily),
            (_household_scope(context.household_id), policy.model_household_daily),
        ):
            row = connection.execute(
                "SELECT attempts FROM p_runtime_model_daily WHERE day=? AND scope=?",
                (day, scope),
            ).fetchone()
            if row and row[0] >= limit:
                raise PlatformError("model_daily_limit_exceeded", 429)
        lease = ModelLease(
            uuid4().hex,
            context.household_id,
            at + policy.model_lease_seconds,
            policy.model_call_seconds,
        )
        connection.execute(
            "INSERT INTO p_runtime_model_leases VALUES(?,?,?,?)",
            (lease.id, lease.household_id, day, lease.expires_at),
        )
        for scope in ("global", _household_scope(context.household_id)):
            connection.execute(
                "INSERT INTO p_runtime_model_daily(day,scope,attempts) VALUES(?,?,1) "
                "ON CONFLICT(day,scope) DO UPDATE SET attempts=attempts+1",
                (day, scope),
            )
        # Aggregate daily operational counts have a 31-day retention policy.
        connection.execute("DELETE FROM p_runtime_model_daily WHERE day<?", (day - 30,))
    return lease


def release_model(
    store: Store, lease: ModelLease, outcome: ModelOutcome = "completed"
) -> None:
    if outcome not in ("completed", "failed", "timeout", "cancelled"):
        raise ValueError("invalid model outcome")
    with store.connection(write=True) as connection:
        _expire_models(connection, time.time())
        row = connection.execute(
            "DELETE FROM p_runtime_model_leases WHERE id=? AND household_id=? RETURNING day",
            (lease.id, lease.household_id),
        ).fetchone()
        if row is None:
            return
        connection.execute(
            f"UPDATE p_runtime_model_daily SET {outcome}={outcome}+1 WHERE day=? AND scope IN (?,?)",
            (row[0], "global", _household_scope(lease.household_id)),
        )


@asynccontextmanager
async def model_admission(store: Store, context: Context):
    """One cancellation-safe lease owner for every actual async model call."""
    pending = asyncio.create_task(run_in_threadpool(acquire_model, store, context))
    try:
        lease = await asyncio.shield(pending)
    except asyncio.CancelledError as cancelled:
        try:
            lease = await pending
        except Exception:
            raise cancelled from None
        await asyncio.shield(run_in_threadpool(release_model, store, lease, "cancelled"))
        raise
    outcome: ModelOutcome = "completed"
    try:
        with anyio.fail_after(lease.call_timeout_seconds):
            yield lease
    except asyncio.CancelledError:
        outcome = "cancelled"
        raise
    except (TimeoutError, asyncio.TimeoutError):
        outcome = "timeout"
        # Both model adapters already translate HTTPX timeouts into their typed
        # unavailable outcome; share that boundary for a whole-call deadline.
        raise httpx.ReadTimeout("model_call_deadline_exceeded") from None
    except httpx.TimeoutException:
        outcome = "timeout"
        raise
    except BaseException:
        outcome = "failed"
        raise
    finally:
        releasing = asyncio.create_task(
            run_in_threadpool(release_model, store, lease, outcome)
        )
        try:
            await asyncio.shield(releasing)
        except asyncio.CancelledError:
            await releasing
            raise


def admit_login(store: Store, address: str) -> None:
    window = int(time.time() // 60)
    # No raw IP is stored or logged. Window salting also avoids long-lived linkage.
    scope = "ip:" + hashlib.sha256(f"{window}:{address}".encode()).hexdigest()
    with store.connection(write=True) as connection:
        policy = read_policy(connection)
        connection.execute(
            "DELETE FROM p_runtime_login_windows WHERE window<?", (window,)
        )
        for key, limit in (
            ("global", policy.login_global_per_minute),
            (scope, policy.login_ip_per_minute),
        ):
            row = connection.execute(
                "SELECT attempts FROM p_runtime_login_windows WHERE window=? AND scope=?",
                (window, key),
            ).fetchone()
            if row and row[0] >= limit:
                raise PlatformError("login_rate_exceeded", 429)
        for key in ("global", scope):
            connection.execute(
                "INSERT INTO p_runtime_login_windows VALUES(?,?,1) "
                "ON CONFLICT(window,scope) DO UPDATE SET attempts=attempts+1",
                (window, key),
            )


def usage(store: Store, context: Context) -> dict:
    at = time.time()
    with store.connection() as connection:
        policy = read_policy(connection)
        row = connection.execute(
            "SELECT attempts,completed,failed,timeout,cancelled,expired FROM p_runtime_model_daily WHERE day=? AND scope=?",
            (int(at // 86400), _household_scope(context.household_id)),
        ).fetchone()
        active = connection.execute(
            "SELECT COUNT(*) FROM p_runtime_model_leases WHERE household_id=? AND expires_at>?",
            (context.household_id, at),
        ).fetchone()[0]
    return {
        "model": {
            **(
                dict(row)
                if row
                else dict.fromkeys(
                    (
                        "attempts",
                        "completed",
                        "failed",
                        "timeout",
                        "cancelled",
                        "expired",
                    ),
                    0,
                )
            ),
            "active": active,
            "daily_limit": policy.model_household_daily,
            "concurrent_limit": policy.model_household_concurrent,
            "window": "UTC day",
        },
        "pricing": "unknown",
        "mode": "local_only",
    }


@router.get("/runtime/usage")
def runtime_usage(request: Request) -> dict:
    return usage(get_store(request), get_context(request))


def export_data(connection: sqlite3.Connection, context: Context) -> dict:
    # Financial receipts belong to their domains. Export only owned queue status.
    from .jobs_runtime import _public

    count = connection.execute(
        "SELECT COUNT(*) FROM p_runtime_jobs WHERE household_id=?",
        (context.household_id,),
    ).fetchone()[0]
    rows = connection.execute(
        "SELECT * FROM p_runtime_jobs WHERE household_id=? ORDER BY created_at DESC,id LIMIT 1000",
        (context.household_id,),
    )
    return {
        "jobs": [_public(row) for row in rows],
        "total": count,
        "truncated": count > 1000,
    }


def usage_data(connection: sqlite3.Connection, context: Context) -> dict:
    return {
        "jobs": connection.execute(
            "SELECT COUNT(*) FROM p_runtime_jobs WHERE household_id=?",
            (context.household_id,),
        ).fetchone()[0]
    }


def clear_data(connection: sqlite3.Connection, context: Context) -> None:
    from .jobs_runtime import clear_data as clear_jobs

    clear_jobs(connection, context)


@router.get("/jobs/{job_id}")
def owned_job(job_id: str, request: Request) -> dict:
    from .jobs_runtime import get_job

    return get_job(get_store(request), get_context(request), job_id)


def is_database_busy(exc: sqlite3.OperationalError) -> bool:
    code = getattr(exc, "sqlite_errorcode", None)
    if code is not None:
        return code & 255 in (5, 6)  # SQLite's stable BUSY and LOCKED result codes.
    # Python 3.10 does not expose sqlite_errorcode on database exceptions.
    return str(exc) in (
        "database is locked",
        "database table is locked",
        "database schema is locked",
    )


class RuntimeMiddleware:
    """Cap bytes before JSON parsing; log only fixed route metadata after response."""

    def __init__(self, app, *, policy: RuntimePolicy | None = None):
        self.app = app
        self.policy = policy or RuntimePolicy.from_environment()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api/"):
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        request_id = uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        status = 500
        response_started = False

        async def observed_send(message):
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status = message["status"]
                headers = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() != b"x-request-id"
                ]
                headers.append((b"x-request-id", request_id.encode()))
                if status in (429, 503) and not any(
                    k.lower() == b"retry-after" for k, _ in headers
                ):
                    headers.append((b"retry-after", b"1"))
                message = {**message, "headers": headers}
            await send(message)

        async def reject(code, error_status):
            await JSONResponse({"code": code}, status_code=error_status)(
                scope, receive, observed_send
            )

        try:
            headers = scope.get("headers", [])
            if (
                sum(len(key) + len(value) for key, value in headers)
                > self.policy.request_header_bytes
            ):
                await reject("request_headers_too_large", 431)
                return
            csv_paths = (
                "/api/platform/imports/preview",
                "/api/platform/investing/holding-imports/preview",
            )
            limit = (
                self.policy.csv_body_bytes
                if scope["path"] in csv_paths
                else self.policy.request_body_bytes
            )
            for key, value in headers:
                if key.lower() == b"content-length":
                    try:
                        length = int(value)
                    except ValueError:
                        await reject("invalid_request_length", 400)
                        return
                    if length < 0 or length > limit:
                        await reject("request_body_too_large", 413)
                        return
            # Buffer at most limit bytes. Counting actual chunks protects requests
            # without Content-Length and keeps parser exception handlers irrelevant.
            body = bytearray()
            deadline = time.monotonic() + self.policy.request_body_seconds
            while True:
                try:
                    message = await asyncio.wait_for(
                        receive(), timeout=max(0.001, deadline - time.monotonic())
                    )
                except asyncio.TimeoutError:
                    await reject("request_body_timeout", 408)
                    return
                if message["type"] == "http.disconnect":
                    return
                if message["type"] != "http.request":
                    continue
                chunk = message.get("body", b"")
                if len(body) + len(chunk) > limit:
                    await reject("request_body_too_large", 413)
                    return
                body.extend(chunk)
                if not message.get("more_body", False):
                    break
            consumed = False

            async def bounded_receive():
                nonlocal consumed
                if consumed:
                    return await receive()
                consumed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}

            if (
                scope["path"] in {
                    "/api/platform/session/login",
                    "/api/platform/session/guest",
                }
                and scope["method"] == "POST"
            ):
                address = (scope.get("client") or ("unknown",))[0]
                await run_in_threadpool(admit_login, scope["app"].state.store, address)
            await self.app(scope, bounded_receive, observed_send)
        except PlatformError as exc:
            if response_started:
                raise
            await reject(exc.code, exc.status)
        except sqlite3.OperationalError as exc:
            if response_started or not is_database_busy(exc):
                raise
            await reject("database_busy", 503)
        finally:
            route = getattr(scope.get("route"), "path", "unmatched")
            logger.info(
                json.dumps(
                    {
                        "request_id": request_id,
                        "route": route,
                        "method": scope["method"]
                        if scope["method"]
                        in ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD")
                        else "OTHER",
                        "status": status,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    },
                    sort_keys=True,
                )
            )
