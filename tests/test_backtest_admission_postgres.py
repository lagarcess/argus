"""#230 — real-Postgres barriered admission proof.

The atomicity acceptance criterion explicitly requires a real database:
mock-only evidence is insufficient. This module therefore runs only when a
disposable Postgres with the repository migrations applied is provided via
``ARGUS_ADMISSION_TEST_DATABASE_URL`` (never a shared QA/production database).
Without it, the criterion stays EXTERNAL_GATE_PENDING in the Wave 0 ledger.
"""

from __future__ import annotations

import json
import os
import threading
import uuid

import pytest

DATABASE_URL = os.getenv("ARGUS_ADMISSION_TEST_DATABASE_URL", "").strip()

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason=(
        "real-Postgres admission proof requires "
        "ARGUS_ADMISSION_TEST_DATABASE_URL (external gate)"
    ),
)


def _connect():
    psycopg = pytest.importorskip("psycopg")
    return psycopg.connect(DATABASE_URL, autocommit=True)


def _admit(connection, *, user_id: str, key: str, identity: str, limit_one: bool):
    with connection.cursor() as cursor:
        cursor.execute(
            "select public.admit_backtest_job("
            "%s::uuid, 'chat.run_backtest', %s, %s, %s, %s::jsonb, 'queued',"
            " null, null, null, '{}'::jsonb,"
            " %s, %s, %s, %s, %s)",
            (
                user_id,
                key,
                identity,
                "sha256:" + "b" * 64,
                json.dumps({"kind": "postgres-proof"}),
                5,
                1 if limit_one else 2,
                5,
                10,
                50,
            ),
        )
        row = cursor.fetchone()[0]
        return row if isinstance(row, dict) else json.loads(row)


def test_barriered_concurrency_admits_at_most_one_with_limit_one() -> None:
    user_id = str(uuid.uuid4())
    barrier = threading.Barrier(10)
    outcomes: list[dict] = []
    lock = threading.Lock()

    def worker(index: int) -> None:
        connection = _connect()
        try:
            barrier.wait()
            outcome = _admit(
                connection,
                user_id=user_id,
                key=f"pg-key-{index}",
                identity=f"sha256:{index:064d}"[:71],
                limit_one=True,
            )
            with lock:
                outcomes.append(outcome)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    admitted = [o for o in outcomes if o.get("decision") == "admitted"]
    assert len(admitted) == 1, outcomes


def test_exact_replay_and_conflict_on_real_postgres() -> None:
    user_id = str(uuid.uuid4())
    connection = _connect()
    try:
        first = _admit(
            connection,
            user_id=user_id,
            key="pg-replay",
            identity="sha256:" + "a" * 64,
            limit_one=False,
        )
        replay = _admit(
            connection,
            user_id=user_id,
            key="pg-replay",
            identity="sha256:" + "a" * 64,
            limit_one=False,
        )
        conflict = _admit(
            connection,
            user_id=user_id,
            key="pg-replay",
            identity="sha256:" + "c" * 64,
            limit_one=False,
        )
    finally:
        connection.close()

    assert first["decision"] == "admitted"
    assert replay["decision"] == "replay"
    assert replay["job"]["id"] == first["job"]["id"]
    assert conflict == {"decision": "conflict"}
