"""Bounded, synthetic-only local HTTP capacity qualification.

Run from money-view with .venv/bin/python scripts/scale_check.py --help.
The application factory is deliberately test tooling, never a production mode.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import ipaddress
import json
import math
import os
import platform
import resource
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ANCHOR = date(2026, 9, 20)
STAMP = "2026-09-20T12:00:00+00:00"
SEED = 20260920
MAX_BYTES = 10 * 1024**3
DELAYED_MODEL_SECONDS = 8


@dataclass(frozen=True)
class Profile:
    identities: int = 10_000
    households: int = 8_000
    transactions: int = 5_000_000
    heavy_households: int = 100
    heavy_transactions: int = 20_000
    stress_transactions: int = 50_000
    batch_size: int = 2_000

    def distribution(self):
        ordinary = self.households - self.heavy_households - 1
        remaining = (
            self.transactions
            - self.heavy_households * self.heavy_transactions
            - self.stress_transactions
        )
        if ordinary < 1 or remaining < ordinary or self.identities < self.households:
            raise ValueError(
                "profile requires populated ordinary households and one stress household"
            )
        return (
            [self.heavy_transactions] * self.heavy_households
            + [self.stress_transactions]
            + [
                remaining // ordinary + (i < remaining % ordinary)
                for i in range(ordinary)
            ]
        )


def stable(kind, index):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"clara-scale:{SEED}:{kind}:{index}"))


def session_token(index):
    # Public synthetic fixture secret. Never accepted by a non-fixture database.
    return hashlib.sha256(f"local-capacity-fixture:{SEED}:{index}".encode()).hexdigest()


def check_disk(path, estimate):
    free = shutil.disk_usage(path).free
    if estimate > MAX_BYTES or estimate > free * 0.2 or free - estimate < 10 * 1024**3:
        raise RuntimeError("resource_stop: estimated fixture exceeds disk budget")
    return {"free_bytes": free, "estimated_bytes": estimate, "limit_bytes": MAX_BYTES}


def database_sizes(path):
    return {
        suffix or "database": Path(str(path) + suffix).stat().st_size
        if Path(str(path) + suffix).exists()
        else 0
        for suffix in ("", "-wal", "-shm")
    }


def seed_database(path: Path, profile: Profile):
    from faker import Faker
    from fastapi import FastAPI
    from server.platform import composition
    from server.platform.identity import password_hash, token_hash
    from server.platform.identity_contracts import Preferences
    from server.store import Store

    distribution = profile.distribution()
    path.parent.mkdir(parents=True, exist_ok=True)
    preflight = check_disk(path.parent, profile.transactions * 1100 + 64_000_000)
    if path.exists():
        with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True) as existing:
            if not existing.execute(
                "SELECT 1 FROM sqlite_master WHERE name='capacity_fixture'"
            ).fetchone():
                raise ValueError(
                    "Refusing an existing database not owned by this harness"
                )
    if not path.exists():
        path.touch(mode=0o600)
    store = Store(path)
    composition.initialize(FastAPI(), store)
    with store.connection(write=True) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS capacity_fixture (id INTEGER PRIMARY KEY CHECK(id=1), config TEXT NOT NULL, next_household INTEGER NOT NULL)"
        )
        config = json.dumps(asdict(profile), sort_keys=True)
        saved = db.execute("SELECT config FROM capacity_fixture WHERE id=1").fetchone()
        if saved is not None and saved[0] != config:
            raise ValueError("Refusing to change an existing fixture profile")
        db.execute("INSERT OR IGNORE INTO capacity_fixture VALUES (1,?,0)", (config,))
        # Fixture-only reuse avoids 10,000 expensive password hashes.
        encoded = password_hash("Capacity-fixture-2026!")
        now = datetime.now(timezone.utc)
        for h in range(profile.households):
            db.execute(
                "INSERT OR IGNORE INTO p_households VALUES (?,?, 'US',NULL,?)",
                (stable("household", h), f"Synthetic household {h}", STAMP),
            )
        for i in range(profile.identities):
            user, home = stable("user", i), stable("household", i % profile.households)
            db.execute(
                "INSERT OR IGNORE INTO p_users VALUES (?,?,NULL,'forest',?,?,NULL,0)",
                (user, f"Synthetic member {i}", encoded, STAMP),
            )
            db.execute(
                "INSERT OR IGNORE INTO p_memberships VALUES (?,?,'owner')", (home, user)
            )
            db.execute(
                "INSERT OR IGNORE INTO p_preferences VALUES (?,?)",
                (user, Preferences().model_dump_json()),
            )
            db.execute(
                "INSERT OR IGNORE INTO p_sessions VALUES (?,?,?,?,?,?,?,NULL)",
                (
                    stable("session", i),
                    token_hash(session_token(i)),
                    user,
                    home,
                    now.isoformat(),
                    (now + timedelta(days=7)).isoformat(),
                    now.isoformat(),
                ),
            )
    fake = Faker("en_US")
    fake.seed_instance(SEED)
    merchants = [fake.company() for _ in range(128)]
    dates = [str(ANCHOR - timedelta(days=i)) for i in range(730)]
    categories = [
        "groceries",
        "dining",
        "housing",
        "transport",
        "utilities",
        "health",
        "shopping",
        "entertainment",
    ]
    with store.connection() as db:
        start = db.execute("SELECT next_household FROM capacity_fixture").fetchone()[0]
    started = time.monotonic()
    for h in range(start, profile.households):
        home = stable("household", h)
        accounts = [
            stable("account", f"{h}:{a}")
            for a in range(40 if h <= profile.heavy_households else 8)
        ]
        with store.connection(write=True) as db:
            for a, account in enumerate(accounts):
                db.execute(
                    "INSERT OR IGNORE INTO p_accounts(id,household_id,owner_id,name,institution,kind,currency,opening_minor,source_kind,recorded_at,as_of) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        account,
                        home,
                        stable("user", h),
                        f"Synthetic account {a}",
                        merchants[a % 128],
                        "checking",
                        "USD" if a % 4 < 2 else ("EUR" if a % 4 == 2 else "DOP"),
                        1000000,
                        "synthetic",
                        STAMP,
                        str(ANCHOR),
                    ),
                )
        for begin in range(0, distribution[h], profile.batch_size):
            rows, splits = [], []
            for j in range(begin, min(distribution[h], begin + profile.batch_size)):
                # Sequential UUID representation keeps bulk insertion bounded and repeatable.
                tx = str(uuid.UUID(int=(SEED << 96) + (h << 48) + j))
                a = j % len(accounts)
                code = "USD" if a % 4 < 2 else ("EUR" if a % 4 == 2 else "DOP")
                kind = (
                    "refund" if j % 100 == 2 else "income" if j % 40 == 8 else "expense"
                )
                amount = (1 if kind in {"refund", "income"} else -1) * (1000 + j % 24000)
                category = (
                    "income" if kind == "income" else categories[j % len(categories)]
                )
                transfer = None
                if j % 100 in (0, 1) and j - j % 100 + 1 < distribution[h]:
                    kind, category, code, a = "transfer", "transfer", "USD", j % 100
                    amount = -5000 if a == 0 else 5000
                    transfer = str(uuid.UUID(int=(SEED << 96) + (h << 48) + j - j % 100))
                status = "pending" if j % 37 == 10 else "posted"
                rows.append(
                    (
                        tx,
                        home,
                        accounts[a],
                        dates[(j // 2 + h * 7) % 730],
                        merchants[j % 128],
                        "Synthetic capacity fixture",
                        amount,
                        code,
                        category,
                        kind,
                        status,
                        "",
                        transfer,
                        None,
                        None,
                        "synthetic",
                        STAMP,
                    )
                )
                if j % 100 == 3:
                    first = amount // 2
                    splits.extend(
                        ((tx, 0, "groceries", first), (tx, 1, "shopping", amount - first))
                    )
            with store.connection(write=True) as db:
                db.executemany(
                    "INSERT OR IGNORE INTO p_transactions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    rows,
                )
                db.executemany(
                    "INSERT OR IGNORE INTO p_transaction_splits VALUES (?,?,?,?)", splits
                )
            if sum(database_sizes(path).values()) > MAX_BYTES:
                raise RuntimeError("resource_stop: fixture exceeds 10 GiB")
        with store.connection(write=True) as db:
            db.execute("UPDATE capacity_fixture SET next_household=?", (h + 1,))
        if h % 500 == 0 or h == profile.households - 1:
            print(
                json.dumps(
                    {
                        "seed_households_completed": h + 1,
                        "elapsed_seconds": round(time.monotonic() - started, 2),
                    }
                ),
                flush=True,
            )
    with store.connection() as db:
        counts = {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "p_users",
                "p_households",
                "p_memberships",
                "p_accounts",
                "p_transactions",
                "p_transaction_splits",
            )
        }
        indexed = [
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
            )
        ]
        measured = db.execute(
            "SELECT COUNT(*), MIN(c), MAX(c), SUM(c) FROM (SELECT COUNT(*) c FROM p_transactions WHERE description='Synthetic capacity fixture' GROUP BY household_id)"
        ).fetchone()
        assert tuple(measured) == (
            profile.households,
            min(distribution),
            max(distribution),
            profile.transactions,
        )
    return {
        "seed": SEED,
        "profile": asdict(profile),
        "preflight": preflight,
        "counts": counts,
        "fixture_household_count": measured[0],
        "fixture_ledger_count": measured[3],
        "minimum_household_rows": measured[1],
        "maximum_household_rows": measured[2],
        "demo_overhead_explicit": True,
        "date_range": [dates[-1], dates[0]],
        "currencies": ["USD", "EUR", "DOP"],
        "indexes": indexed,
        "sqlite_version": sqlite3.sqlite_version,
        "sizes": database_sizes(path),
        "seed_seconds": time.monotonic() - started,
    }


def capacity_app():
    """Real application plus a test-only semantic seam; all sockets stay local."""
    original = socket.socket.connect
    original_ex = socket.socket.connect_ex
    original_lookup = socket.getaddrinfo

    def permitted(host):
        return host in (None, "localhost") or ipaddress.ip_address(host).is_loopback

    def local_connect(sock, address):
        if isinstance(address, tuple) and not permitted(address[0]):
            raise RuntimeError("capacity_outbound_blocked")
        return original(sock, address)

    socket.socket.connect = local_connect

    def local_connect_ex(sock, address):
        if isinstance(address, tuple) and not permitted(address[0]):
            raise RuntimeError("capacity_outbound_blocked")
        return original_ex(sock, address)

    def local_lookup(host, *args, **kwargs):
        if not permitted(host):
            raise RuntimeError("capacity_outbound_blocked")
        return original_lookup(host, *args, **kwargs)

    socket.socket.connect_ex = local_connect_ex
    socket.getaddrinfo = local_lookup
    from server.platform import assistant
    from server.platform.assistant_contracts import SemanticChoice

    async def fixture_interpret(message, locale, parameters, memories, **kwargs):
        from server.platform.runtime import model_admission

        store, context = kwargs["store"], kwargs["context"]
        async with model_admission(store, context):
            await asyncio.sleep(
                DELAYED_MODEL_SECONDS if message == "capacity delayed fixture" else 0.02
            )
            return "answered", SemanticChoice(action="spending", parameters=parameters)

    assistant.interpret = fixture_interpret
    from server.app import create_app

    return create_app()


def clean_environment(path):
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(path.parent),
        "TMPDIR": str(path.parent),
        "PYTHONPATH": str(ROOT),
        "PYTHONUNBUFFERED": "1",
        "CLARA_DATABASE_PATH": str(path),
        "CLARA_LLM_BASE_URL": "",
        "CLARA_LLM_API_KEY": "",
        "CLARA_LLM_MODEL": "",
    }


def percentile(values, fraction):
    return (
        sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)] if values else None
    )


def measure_processes(parent):
    output = subprocess.check_output(["ps", "-axo", "pid=,ppid=,rss=,%cpu="], text=True)
    rows = [line.split() for line in output.splitlines()]
    children = {parent}
    for _ in range(4):
        children.update(int(row[0]) for row in rows if int(row[1]) in children)
    included = [row for row in rows if int(row[0]) in children]
    return {
        "rss_bytes": sum(int(row[2]) * 1024 for row in included),
        "cpu_percent": sum(float(row[3]) for row in included),
        "processes": len(included),
    }


async def run_http(path, profile, seconds, burst_seconds, rps, burst_rps, port):
    import httpx

    base = f"http://127.0.0.1:{port}"
    log = path.parent / "server.log"
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("127.0.0.1", port))
    handle = log.open("w")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "scripts.scale_check:capacity_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--workers",
            "2",
            "--no-access-log",
            "--log-level",
            "warning",
        ],
        cwd=ROOT,
        env=clean_environment(path),
        stdout=handle,
        stderr=handle,
    )
    evidence = {
        "server_workers": 2,
        "provider_mode": f"local deterministic semantic fixture; 20ms normal; {DELAYED_MODEL_SECONDS}s fault injection using shared model_admission",
        "outbound_policy": "allowlisted environment and loopback socket connect guard",
        "phases": [],
        "checks": {},
        "resource_peak": {"rss_bytes": 0, "cpu_percent": 0, "processes": 0},
    }

    def headers(i):
        return {"Cookie": f"clara_session={session_token(i)}"}

    async def checked(client, method, route, i, **kwargs):
        response = await client.request(method, route, headers=headers(i), **kwargs)
        if response.status_code >= 500:
            raise AssertionError(f"precheck_http_status:{response.status_code}:{route}")
        return response

    try:
        async with httpx.AsyncClient(
            base_url=base,
            timeout=12,
            trust_env=False,
            limits=httpx.Limits(max_connections=40),
        ) as client:
            cold_start = time.monotonic()
            for _ in range(150):
                try:
                    response = await client.get(
                        "/api/platform/session", headers=headers(0)
                    )
                    if response.status_code == 200:
                        break
                except httpx.ConnectError:
                    pass
                await asyncio.sleep(0.2)
            else:
                raise RuntimeError("server_start_timeout")
            evidence["cold_start_seconds"] = time.monotonic() - cold_start
            for i in (0, profile.heavy_households, profile.households - 1):
                response = await checked(
                    client, "GET", "/api/platform/transactions?limit=100", i
                )
                body = response.json()
                with sqlite3.connect(path) as db:
                    actual = db.execute(
                        "SELECT COUNT(*) FROM p_transactions WHERE household_id=? AND deleted_at IS NULL",
                        (stable("household", i),),
                    ).fetchone()[0]
                assert response.status_code == 200 and body["total"] == actual
                assert len(body["items"]) <= 100
                allowed = {
                    stable("account", f"{i}:{a}")
                    for a in range(40 if i <= profile.heavy_households else 8)
                }
                assert all(row["account_id"] in allowed for row in body["items"])
            negative = await checked(
                client, "GET", f"/api/platform/accounts/{stable('account', '1:0')}", 0
            )
            assert negative.status_code == 404
            overpage = await checked(
                client, "GET", "/api/platform/transactions?limit=101", 0
            )
            assert overpage.status_code == 422
            evidence["checks"].update(
                {
                    "cross_household_account_denied": True,
                    "page_bound_100": True,
                    "heavy_and_stress_count_truth": True,
                }
            )
            write_payload = {
                "idempotency_key": "capacity-dedupe-check",
                "account_id": stable("account", "0:0"),
                "date": str(ANCHOR),
                "merchant": "Synthetic capacity dedupe",
                "amount": "-1.00",
                "category": "groceries",
            }
            first = await checked(
                client, "POST", "/api/platform/transactions", 0, json=write_payload
            )
            second = await checked(
                client, "POST", "/api/platform/transactions", 0, json=write_payload
            )
            assert (
                first.status_code == second.status_code == 200
                and first.json() == second.json()
            )
            conflict = await checked(
                client,
                "POST",
                "/api/platform/transactions",
                0,
                json={**write_payload, "amount": "-2.00"},
            )
            assert conflict.status_code == 409
            evidence["checks"]["write_idempotency_and_conflict"] = True
            # A separate login uses actual password hashing and revocation; fixture sessions remain intact.
            login_start = time.monotonic()
            login = await client.post(
                "/api/platform/session/login",
                json={"user_id": stable("user", 0), "password": "Capacity-fixture-2026!"},
            )
            assert login.status_code == 200
            cookie = login.cookies.get("clara_session")
            revoked = await client.post(
                "/api/platform/settings/sessions/revoke",
                headers={"Cookie": f"clara_session={cookie}"},
                json={"scope": "all"},
            )
            assert revoked.status_code == 200
            assert (
                await client.get(
                    "/api/platform/session", headers={"Cookie": f"clara_session={cookie}"}
                )
            ).status_code == 401
            # Reconstitute this synthetic fixture session after testing revocation.
            with sqlite3.connect(path) as db:
                db.execute(
                    "UPDATE p_sessions SET revoked_at=NULL WHERE id=?",
                    (stable("session", 0),),
                )
            client.cookies.clear()
            evidence["checks"]["real_password_login_and_revocation"] = True
            evidence["login_revocation_seconds"] = time.monotonic() - login_start
            with sqlite3.connect(path) as db:
                ledger_rows_before_load = db.execute(
                    "SELECT COUNT(*) FROM p_transactions"
                ).fetchone()[0]
                evidence["query_plan"] = [
                    row[3]
                    for row in db.execute(
                        "EXPLAIN QUERY PLAN SELECT id FROM p_transactions WHERE household_id=? AND deleted_at IS NULL ORDER BY date DESC,id DESC LIMIT 100",
                        (stable("household", 0),),
                    )
                ]
                assert any(
                    "p_transactions_household_date" in row
                    for row in evidence["query_plan"]
                )
            totals = defaultdict(list)
            active, tasks, users = 0, set(), set()
            sequence = 0
            run_key = uuid.uuid4().hex

            async def phase(name, duration, rate):
                nonlocal active, sequence
                counters, latencies, queue_lags = Counter(), defaultdict(list), []
                route_status = Counter()
                evidence["active_phase"] = {
                    "name": name,
                    "offered_rps": rate,
                    "counters": counters,
                }
                max_active = 0
                started = time.monotonic()

                async def request(n, due):
                    nonlocal active
                    active += 1
                    i, slot = n % profile.identities, n % 100
                    route = (
                        "transactions"
                        if slot < 40
                        else "overview"
                        if slot < 65
                        else "spending"
                        if slot < 80
                        else "history"
                        if slot < 90
                        else "write"
                        if slot < 95
                        else "prepared"
                        if slot < 98
                        else "semantic"
                    )
                    method, url, payload = "GET", "/api/platform/" + route, None
                    if route == "transactions":
                        url += "?limit=50"
                    elif route == "history":
                        url = (
                            "/api/platform/settings"
                            if n % 2
                            else "/api/platform/assistant/conversations"
                        )
                    elif route == "write":
                        method, url = "POST", "/api/platform/transactions"
                        payload = {
                            "idempotency_key": f"capacity-{run_key}-{n}",
                            "account_id": stable(
                                "account", f"{i % profile.households}:0"
                            ),
                            "date": str(ANCHOR),
                            "merchant": "Synthetic capacity write",
                            "amount": "-1.00",
                            "category": "groceries",
                        }
                    elif route in {"prepared", "semantic"}:
                        method, url = "POST", "/api/platform/assistant/ask"
                        payload = {
                            "parameters": {"currency": "USD", "month": "2026-09"},
                            "locale": "en",
                            **(
                                {"action": "spending"}
                                if route == "prepared"
                                else {"message": "capacity fixture"}
                            ),
                        }
                    request_start = time.monotonic()
                    queue_lags.append((request_start - due) * 1000)
                    try:
                        response = await client.request(
                            method, url, headers=headers(i), json=payload
                        )
                        elapsed = (time.monotonic() - due) * 1000
                        counters[f"status_{response.status_code}"] += 1
                        route_status[f"{route}:{response.status_code}"] += 1
                        counters["completed"] += 1
                        counters["response_bytes"] += len(response.content)
                        counters["request_body_bytes"] += len(response.request.content)
                        users.add(i)
                        latencies[route].append(elapsed)
                        totals[route].append(elapsed)
                        if response.status_code == 200:
                            body = response.json()
                            if route == "transactions":
                                home = i % profile.households
                                allowed = {
                                    stable("account", f"{home}:{a}")
                                    for a in range(
                                        40 if home <= profile.heavy_households else 8
                                    )
                                }
                                assert len(body["items"]) <= 50 and all(
                                    row["account_id"] in allowed for row in body["items"]
                                ), "cross_household_or_page_integrity"
                            counters["success"] += 1
                        elif response.status_code in (429, 503):
                            assert response.headers.get("Retry-After"), (
                                "untyped_backpressure"
                            )
                            counters["backpressure"] += 1
                        else:
                            raise AssertionError(
                                f"unexpected_http_status:{response.status_code}:{route}"
                            )
                    finally:
                        active -= 1

                for k in range(round(duration * rate)):
                    due = started + k / rate
                    await asyncio.sleep(max(0, due - time.monotonic()))
                    for task in list(tasks):
                        if task.done():
                            task.result()
                            tasks.remove(task)
                    if active >= 40:
                        counters["client_capacity_rejected"] += 1
                        raise RuntimeError("resource_stop: 40 in-flight slots exhausted")
                    counters["offered"] += 1
                    tasks.add(asyncio.create_task(request(sequence, due)))
                    sequence += 1
                    max_active = max(max_active, active + 1)
                    if k and k % max(1, int(rate * 60)) == 0:
                        print(
                            json.dumps(
                                {
                                    "phase": name,
                                    "elapsed_seconds": round(time.monotonic() - started),
                                    "completed": counters["completed"],
                                    "distinct_users": len(users),
                                }
                            ),
                            flush=True,
                        )
                    if k % max(1, int(rate * 5)) == 0:
                        usage = measure_processes(process.pid)
                        for key in usage:
                            evidence["resource_peak"][key] = max(
                                usage[key], evidence["resource_peak"][key]
                            )
                        if usage["rss_bytes"] > 4 * 1024**3:
                            raise RuntimeError(
                                "resource_stop: server memory exceeds 4 GiB"
                            )
                        if k > 400:
                            ordinary = sum(
                                [
                                    latencies[r][-200:]
                                    for r in (
                                        "transactions",
                                        "overview",
                                        "spending",
                                        "history",
                                    )
                                ],
                                [],
                            )
                            if percentile(ordinary, 0.99) > 1000:
                                raise RuntimeError(
                                    "latency_stop: ordinary read p99 exceeds one second"
                                )
                await asyncio.gather(*tasks)
                tasks.clear()
                result = {
                    "name": name,
                    "duration_seconds": time.monotonic() - started,
                    "offered_rps": rate,
                    "max_in_flight": max_active,
                    "counters": dict(counters),
                    "normalized_route_status_counts": dict(route_status),
                    "queue_lag_p99_ms": percentile(queue_lags, 0.99),
                    "routes": {
                        key: {
                            "count": len(values),
                            "p50_ms": percentile(values, 0.5),
                            "p95_ms": percentile(values, 0.95),
                            "p99_ms": percentile(values, 0.99),
                        }
                        for key, values in latencies.items()
                    },
                }
                evidence["phases"].append(result)
                evidence.pop("active_phase", None)
                print(
                    json.dumps(
                        {
                            "phase_complete": name,
                            "completed": counters["completed"],
                            "distinct_users": len(users),
                        }
                    ),
                    flush=True,
                )

            await phase("sustained", seconds, rps)
            await phase("burst", burst_seconds, burst_rps)
            evidence["distinct_authenticated_users"] = len(users)
            delayed = [
                asyncio.create_task(
                    client.post(
                        "/api/platform/assistant/ask",
                        headers=headers(i),
                        json={
                            "message": "capacity delayed fixture",
                            "parameters": {"currency": "USD", "month": "2026-09"},
                        },
                    )
                )
                for i in range(4)
            ]
            await asyncio.sleep(0.5)
            rejected = await client.post(
                "/api/platform/assistant/ask",
                headers=headers(4),
                json={"message": "capacity fixture"},
            )
            assert rejected.status_code == 429 and rejected.headers.get("Retry-After")
            delayed_reads = []
            for i in range(40):
                started = time.monotonic()
                response = await client.get(
                    "/api/platform/overview",
                    headers=headers((i + 4) % profile.identities),
                )
                assert response.status_code == 200
                delayed_reads.append((time.monotonic() - started) * 1000)
            answers = await asyncio.gather(*delayed)
            assert all(answer.status_code == 200 for answer in answers)
            evidence["delayed_semantic_burst"] = {
                "concurrent_calls": 4,
                "fake_delay_seconds": DELAYED_MODEL_SECONDS,
                "ordinary_reads": len(delayed_reads),
                "read_p95_ms": percentile(delayed_reads, 0.95),
                "read_p99_ms": percentile(delayed_reads, 0.99),
                "fifth_call_typed_429": True,
            }
            with sqlite3.connect(path) as db:
                evidence["checks"]["foreign_key_check"] = not db.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall()
                evidence["checks"]["integrity_check"] = (
                    db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                )
                evidence["ledger_rows_after"] = db.execute(
                    "SELECT COUNT(*) FROM p_transactions"
                ).fetchone()[0]
            successful_writes = sum(
                p["normalized_route_status_counts"].get("write:200", 0)
                for p in evidence["phases"]
            )
            evidence["checks"]["exact_load_row_growth"] = (
                evidence["ledger_rows_after"]
                == ledger_rows_before_load + successful_writes
            )
            assert all(evidence["checks"].values()), "artifact_integrity_check_failed"
            evidence["sizes_after"] = database_sizes(path)
            evidence["passed_measured_slos"] = (
                percentile(delayed_reads, 0.95) < 250
                and percentile(delayed_reads, 0.99) < 1000
                and all(
                    p["counters"].get("success", 0) / p["counters"]["offered"] >= 0.999
                    and all(
                        v["p95_ms"]
                        < (500 if k in {"write", "prepared", "semantic"} else 250)
                        and v["p99_ms"] < 1000
                        for k, v in p["routes"].items()
                    )
                    for p in evidence["phases"]
                )
            )
    except BaseException as exc:
        evidence["stopped"] = type(exc).__name__ + ":" + str(exc)
        evidence["passed_measured_slos"] = False
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        handle.close()
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key, value in asdict(Profile()).items():
        parser.add_argument("--" + key.replace("_", "-"), type=int, default=value)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=600)
    parser.add_argument("--burst-seconds", type=float, default=60)
    parser.add_argument("--rps", type=float, default=20)
    parser.add_argument("--burst-rps", type=float, default=40)
    parser.add_argument("--port", type=int, default=8032)
    parser.add_argument("--seed-only", action="store_true")
    args = parser.parse_args()
    if args.port in (8012, 8022) or not 1 <= args.batch_size <= 10_000:
        parser.error("reserved port or unbounded batch")
    profile = Profile(**{key: getattr(args, key) for key in asdict(Profile())})
    sources = [
        ROOT / "server" / "app.py",
        ROOT / "server" / "store.py",
        *sorted((ROOT / "server" / "platform").glob("*.py")),
        Path(__file__),
    ]
    evidence = {
        "profile_name": "bounded-development",
        "full_retention_qualified": False,
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sources
        },
        "hardware": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
        },
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        hardware = subprocess.check_output(
            ["sysctl", "-n", "hw.memsize", "machdep.cpu.brand_string"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).splitlines()
        evidence["hardware"].update(ram_bytes=int(hardware[0]), cpu_model=hardware[1])
    except (OSError, subprocess.CalledProcessError, ValueError, IndexError):
        evidence["hardware"]["ram_bytes"] = None
    try:
        evidence["dataset"] = seed_database(args.database.resolve(), profile)
        if not args.seed_only:
            evidence["http"] = asyncio.run(
                run_http(
                    args.database.resolve(),
                    profile,
                    args.seconds,
                    args.burst_seconds,
                    args.rps,
                    args.burst_rps,
                    args.port,
                )
            )
    except BaseException as exc:
        evidence["stopped"] = type(exc).__name__ + ":" + str(exc)
    evidence["finished_at"] = datetime.now(timezone.utc).isoformat()
    evidence["generator_peak_rss_native"] = resource.getrusage(
        resource.RUSAGE_SELF
    ).ru_maxrss
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(
        json.dumps(
            {
                "evidence": str(args.output),
                "passed": evidence.get("http", {}).get("passed_measured_slos", False),
                "stopped": evidence.get(
                    "stopped", evidence.get("http", {}).get("stopped")
                ),
            }
        ),
        flush=True,
    )
    success = "stopped" not in evidence and (
        args.seed_only or evidence.get("http", {}).get("passed_measured_slos")
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
