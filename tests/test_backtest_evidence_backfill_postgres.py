"""The evidence backfill against the real finalizer on the disposable stack.

A June-shaped job: succeeded, linked to a completed run in its conversation,
no idea / idea version / evidence artifact, card without identity. The owner
predicate rejects it and the activity projection reads ``checking``. The
backfill selects it with the owner predicate, finalizes it through
``public.finalize_backtest_completion`` on the same connection, and the same
predicate then accepts it. A second pass finds nothing.

The backfill forwards the stored run into the finalizer, whose identity check
replays it field by field, so the fixtures are generated rather than typed
and parametrized over materially different run shapes: one with a chart and
trades, one without either, with a quick take, non-integer timestamps, tiny
and negative metrics, and non-ASCII text.

Set ``ARGUS_DISPOSABLE_DATABASE_URL`` to run locally.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from faker import Faker

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()

pytestmark = pytest.mark.skipif(
    not DSN,
    reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured",
)
psycopg = pytest.importorskip("psycopg")

OPS_DIR = Path(__file__).resolve().parents[1] / "scripts" / "ops"

fake = Faker()
Faker.seed(20260904)


def _module():
    sys.path.insert(0, str(OPS_DIR))
    try:
        import backfill_backtest_evidence as module
    finally:
        sys.path.pop(0)
    return module


def _connect():
    return psycopg.connect(DSN, autocommit=True)


def _symbol() -> str:
    return fake.lexify("????").upper()


@dataclass(frozen=True)
class RunShape:
    id: str
    asset_class: str
    symbol_count: int
    with_chart: bool
    with_trades: bool
    with_quick_take: bool


SHAPES = (
    RunShape(
        id="equity_with_chart_and_trades",
        asset_class="equity",
        symbol_count=2,
        with_chart=True,
        with_trades=True,
        with_quick_take=False,
    ),
    RunShape(
        id="crypto_without_chart_or_trades_with_quick_take",
        asset_class="crypto",
        symbol_count=1,
        with_chart=False,
        with_trades=False,
        with_quick_take=True,
    ),
)


def _generated_run(shape: RunShape) -> dict[str, Any]:
    symbols = [_symbol() for _ in range(shape.symbol_count)]
    start = fake.date_between(start_date="-3y", end_date="-1y")
    end = fake.date_between(start_date=start, end_date="-1d")
    total_return = fake.pyfloat(min_value=-60, max_value=180, right_digits=3)
    card: dict[str, Any] = {
        "title": f"{', '.join(symbols)} {fake.catch_phrase()}",
        "symbols": symbols,
        "strategy_label": fake.bs(),
        "asset_class": shape.asset_class,
        "date_range": f"{start.isoformat()} to {end.isoformat()}",
        "status_label": "Completed",
        "rows": [
            {"label": "Total return", "value": f"{total_return:+.2f}%"},
            {"label": fake.word().capitalize(), "value": fake.sentence(nb_words=4)},
        ],
        "benchmark_note": fake.sentence(nb_words=6),
        "assumptions": [fake.sentence(nb_words=5) for _ in range(2)],
        "actions": [{"type": "show_breakdown", "payload": {"note": fake.word()}}],
    }
    if shape.with_quick_take:
        card["quick_take"] = f"Resumen: {fake.sentence(nb_words=8)} ñ é ü"
    metrics = {
        "aggregate": {
            "performance": {
                "total_return_pct": total_return,
                "alpha": fake.pyfloat(
                    min_value=-0.0001, max_value=0.0001, right_digits=8
                ),
            },
            "risk": {"max_drawdown_pct": -abs(fake.pyfloat(min_value=0, max_value=45))},
        },
        "by_symbol": {
            symbol: {"performance": {"total_return_pct": fake.pyfloat(right_digits=5)}}
            for symbol in symbols
        },
    }
    return {
        "symbols": symbols,
        "benchmark_symbol": _symbol(),
        "metrics": metrics,
        "config_snapshot": {
            "template": fake.slug(),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "parameters": {"window": fake.random_int(5, 200), "label": "ñandú"},
        },
        "card": card,
        "chart": (
            {
                "kind": "equity_curve",
                "currency": "USD",
                "base_value": fake.random_int(1_000, 100_000),
                "series": [
                    {"date": fake.date_between(start, end).isoformat(), "value": v}
                    for v in fake.pylist(6, False, [float])
                ],
                "markers": [],
                "attribution": {"provider": fake.company()},
            }
            if shape.with_chart
            else None
        ),
        "trades": (
            [
                {
                    "symbol": symbols[0],
                    "side": "buy",
                    "qty": fake.pyfloat(min_value=0.001, max_value=50, right_digits=6),
                }
            ]
            if shape.with_trades
            else None
        ),
        "created_at": fake.date_time_between(
            start_date="-4M", end_date="-2M", tzinfo=timezone.utc
        ),
    }


def _seed_owner(connection) -> dict[str, str]:
    user_id = str(uuid4())
    conversation_id = str(uuid4())
    email = fake.unique.email(domain="argus.local")
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into auth.users (id, email) values (%s, %s)", (user_id, email)
        )
        cursor.execute(
            "insert into public.profiles (id, email) values (%s, %s)", (user_id, email)
        )
        cursor.execute(
            "insert into public.conversations (id, user_id, title) values (%s, %s, %s)",
            (conversation_id, user_id, fake.sentence(nb_words=3)),
        )
    return {"user_id": user_id, "conversation_id": conversation_id}


def _seed_june_shaped_job(connection, owner, run: dict[str, Any]) -> tuple[str, str]:
    """The worker's pre-#201 output: run persisted, card without identity,
    job linked and succeeded, no evidence tuple."""
    run_id = str(uuid4())
    job_id = str(uuid4())
    with connection.cursor() as cursor:
        cursor.execute(
            """
            insert into public.backtest_runs
              (id, user_id, conversation_id, status, asset_class, symbols,
               allocation_method, benchmark_symbol, metrics, config_snapshot,
               conversation_result_card, chart, trades, created_at)
            values (%s, %s, %s, 'completed', %s, %s, 'equal_weight', %s,
                    %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s)
            """,
            (
                run_id,
                owner["user_id"],
                owner["conversation_id"],
                run["card"]["asset_class"],
                run["symbols"],
                run["benchmark_symbol"],
                json.dumps(run["metrics"]),
                json.dumps(run["config_snapshot"]),
                json.dumps(run["card"]),
                json.dumps(run["chart"]) if run["chart"] is not None else None,
                json.dumps(run["trades"]) if run["trades"] is not None else None,
                run["created_at"],
            ),
        )
        cursor.execute(
            """
            insert into public.backtest_jobs
              (id, user_id, conversation_id, operation_scope, idempotency_key,
               identity_hash, payload_hash, launch_payload, status, result_run_id,
               queued_at, started_at, finished_at, execution_metadata)
            values (%s, %s, %s, 'chat.run_backtest', %s, %s, %s, %s::jsonb,
                    'succeeded', %s, %s, %s, %s, %s::jsonb)
            """,
            (
                job_id,
                owner["user_id"],
                owner["conversation_id"],
                f"conf-{fake.uuid4()[:8]}",
                f"sha256:{fake.sha256()}",
                f"sha256:{fake.sha256()}",
                json.dumps({"kind": "run_backtest_job", "request": {}}),
                run_id,
                run["created_at"],
                run["created_at"],
                run["created_at"],
                json.dumps(
                    {
                        "shadow_mode": "true",
                        "workflow_backtest": {
                            "kind": "run_backtest_job",
                            "result_run_id": run_id,
                        },
                    }
                ),
            ),
        )
    return job_id, run_id


def _settled(connection, job_id: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            "select argus_private.backtest_job_result_hydrateable(j)"
            " from public.backtest_jobs as j where j.id = %s",
            (job_id,),
        )
        return bool(cursor.fetchone()[0])


def _job_source(connection, owner) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            "select sources from public.read_conversation_activity_sources(%s, %s)",
            (owner["user_id"], [owner["conversation_id"]]),
        )
        sources = cursor.fetchone()[0]
    jobs = [source for source in sources if source["source_kind"] == "backtest_job"]
    assert len(jobs) == 1
    return jobs[0]


def _delete_identity(connection, user_id: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute("delete from auth.users where id = %s", (user_id,))


@pytest.mark.parametrize("shape", SHAPES, ids=[shape.id for shape in SHAPES])
def test_backfill_finalizes_a_june_shaped_job_until_the_owner_predicate_accepts_it(
    shape: RunShape,
) -> None:
    module = _module()
    run = _generated_run(shape)
    with _connect() as connection, module.evidence_backfill_gateway(DSN) as gateway:
        owner = _seed_owner(connection)
        try:
            job_id, run_id = _seed_june_shaped_job(connection, owner, run)
            assert not _settled(connection, job_id)
            assert _job_source(connection, owner)["result_hydrateable"] is False

            candidates = gateway.select_candidates(limit=100)
            ours = [candidate for candidate in candidates if candidate.job_id == job_id]
            assert len(ours) == 1
            assert ours[0].result_run_id == run_id

            dry = module.run_backfill(
                ours,
                gateway=gateway,
                apply=False,
                settled=lambda _job_id: pytest.fail("dry run must not verify"),
            )
            assert dry["jobs"][0]["outcome"] == "candidate"
            assert not _settled(connection, job_id)

            report = module.run_backfill(
                ours, gateway=gateway, apply=True, settled=gateway.job_is_settled
            )
            assert report["status"] == "ready", report
            assert report["jobs"][0]["outcome"] == "finalized"
            identity = report["jobs"][0]["identity"]

            assert _settled(connection, job_id)
            assert _job_source(connection, owner)["result_hydrateable"] is True
            with connection.cursor() as cursor:
                cursor.execute(
                    "select e.id::text, e.idea_id::text, e.idea_version_id::text,"
                    " e.source_conversation_id::text, e.title, e.digest,"
                    " r.conversation_result_card, r.chart, r.trades, r.metrics"
                    " from public.evidence_artifacts as e"
                    " join public.backtest_runs as r on r.id = e.source_run_id"
                    " where e.source_run_id = %s",
                    (run_id,),
                )
                (
                    artifact_id,
                    idea_id,
                    version_id,
                    source_conversation,
                    title,
                    digest,
                    card,
                    chart,
                    trades,
                    metrics,
                ) = cursor.fetchone()
            assert (artifact_id, idea_id, version_id) == (
                identity["evidence_artifact_id"],
                identity["idea_id"],
                identity["idea_version_id"],
            )
            assert source_conversation == owner["conversation_id"]
            # The card gained exactly the identity; everything it held stays.
            assert card["evidence_artifact_id"] == artifact_id
            assert card["idea_id"] == idea_id
            assert card["idea_version_id"] == version_id
            assert {key: card[key] for key in run["card"]} == run["card"]
            # The run's immutable payload replayed unchanged through the RPC.
            assert chart == run["chart"]
            assert trades == run["trades"]
            assert metrics == run["metrics"]
            # Evidence text derives from the card, not from anything typed here.
            assert title == run["card"]["title"]
            if shape.with_quick_take:
                assert digest == run["card"]["quick_take"]
            else:
                assert run["card"]["rows"][0]["value"] in digest

            # A second pass has nothing left to do.
            assert [
                candidate
                for candidate in gateway.select_candidates(limit=100)
                if candidate.job_id == job_id
            ] == []
        finally:
            _delete_identity(connection, owner["user_id"])
