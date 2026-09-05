"""Finalize succeeded chat backtest jobs whose linked run never became evidence.

Between 2026-06-06 and 2026-07-12 the Render worker linked a completed run to
its job and marked the job succeeded without writing the idea, idea version,
and evidence artifact tuple; the finalizer only arrived with #201 on
2026-07-13. The settle rule (``argus.domain.job_settlement``) is right to keep
those jobs unsettled: no predicate can honestly read a result that has no
evidence identity, and loosening it would hide every future half-finalized
job. So this script gives each such run the tuple it is owed, through the same
finalizer every live path uses (``public.finalize_backtest_completion``, called
the way the worker calls it), and the rule flips true on the facts.

One coordinate. Selection, the run read, the finalization, and the settlement
re-check all run on the one ``DATABASE_URL`` connection, so no second URL can
name a different project. Dry run by default; ``--apply`` writes. Idempotent:
a finalized run leaves the candidate set, and the finalizer replays an
existing tuple instead of duplicating it. Candidates are selected with the
owner predicate itself, never a restatement of it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Sequence
from uuid import uuid4

if __package__:
    from scripts.ops.destructive_database_target import (
        DestructiveDatabaseTargetError,
        announce_destructive_postgres_target,
        resolve_destructive_postgres_target,
    )
else:
    from destructive_database_target import (  # type: ignore[no-redef]
        DestructiveDatabaseTargetError,
        announce_destructive_postgres_target,
        resolve_destructive_postgres_target,
    )

EXECUTION_IDENTITY_PREFIX = "evidence_backfill"

# A succeeded chat job the owner predicate cannot hydrate, whose linked run is
# complete, in the job's conversation, and has never been captured as
# evidence. Anything else the predicate rejects is not this defect.
CANDIDATE_SQL = """
select
  j.id as job_id,
  j.user_id,
  j.conversation_id,
  j.result_run_id,
  j.created_at
from public.backtest_jobs as j
join public.backtest_runs as r
  on r.id = j.result_run_id
 and r.user_id = j.user_id
where j.status = 'succeeded'
  and j.operation_scope = %(scope)s
  and not argus_private.backtest_job_result_hydrateable(j)
  and r.status = 'completed'
  and r.conversation_id = j.conversation_id
  and not exists (
    select 1
    from public.evidence_artifacts as e
    where e.source_run_id = r.id
  )
order by j.created_at, j.id
limit %(limit)s
"""

SETTLED_SQL = """
select argus_private.backtest_job_result_hydrateable(j)
from public.backtest_jobs as j
where j.id = %(job_id)s
"""

RUN_SQL = """
select *
from public.backtest_runs
where id = %(run_id)s
  and user_id = %(user_id)s
limit 1
"""


@dataclass(frozen=True)
class Candidate:
    job_id: str
    user_id: str
    conversation_id: str
    result_run_id: str
    created_at: str


def _copy_first_env(target: str, candidates: Sequence[str]) -> None:
    if os.getenv(target):
        return
    for candidate in candidates:
        value = os.getenv(candidate)
        if value:
            os.environ[target] = value
            return


def _prepare_database_env() -> None:
    _copy_first_env("DATABASE_URL", ("ARGUS_WORKFLOW_DATABASE_URL",))


def _evidence_backfill_gateway_class() -> type:
    """The worker's Postgres gateway, extended with the reads this job needs.

    Subclassing keeps the finalization call the worker's own; the one
    connection the worker opens serves selection and verification too.
    """
    from argus.api.schemas import BacktestRun
    from argus.domain.backtest_job_scopes import CHAT_RUN_SCOPE

    from workflows.backtest_job import PostgresBacktestJobGateway, _json_safe

    class EvidenceBackfillGateway(PostgresBacktestJobGateway):
        def select_candidates(self, *, limit: int) -> list[Candidate]:
            with self._connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        CANDIDATE_SQL,
                        {"scope": CHAT_RUN_SCOPE, "limit": max(1, limit)},
                    )
                    rows = cur.fetchall()
            return [
                Candidate(
                    job_id=str(row["job_id"]),
                    user_id=str(row["user_id"]),
                    conversation_id=str(row["conversation_id"]),
                    result_run_id=str(row["result_run_id"]),
                    created_at=_json_safe(row["created_at"]),
                )
                for row in rows
            ]

        def job_is_settled(self, job_id: str) -> bool:
            with self._connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(SETTLED_SQL, {"job_id": job_id})
                    row = cur.fetchone()
            return bool(row and next(iter(row.values())))

        def get_backtest_run(self, *, user_id: str, run_id: str) -> BacktestRun | None:
            with self._connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(RUN_SQL, {"run_id": run_id, "user_id": user_id})
                    row = cur.fetchone()
            if row is None:
                return None
            return BacktestRun.model_validate(_json_safe(dict(row)))

    return EvidenceBackfillGateway


def evidence_backfill_gateway(database_url: str) -> Any:
    return _evidence_backfill_gateway_class()(database_url)


def finalize_candidate(
    gateway: Any,
    candidate: Candidate,
    *,
    now: datetime,
    new_id: Callable[[], str] = lambda: str(uuid4()),
) -> dict[str, str]:
    """One run through the production finalizer. Returns the tuple identity."""
    from argus.domain.backtest_finalization import (
        BacktestFinalizationInput,
        finalize_backtest_completion,
    )

    run = gateway.get_backtest_run(
        user_id=candidate.user_id, run_id=candidate.result_run_id
    )
    if run is None:
        raise RuntimeError("linked run is missing or not owned by the job's user")
    finalized = finalize_backtest_completion(
        gateway,
        BacktestFinalizationInput(
            user_id=candidate.user_id,
            execution_identity=f"{EXECUTION_IDENTITY_PREFIX}:{candidate.job_id}",
            run=run,
            result_card=dict(run.conversation_result_card),
            idea_id=new_id(),
            idea_version_id=new_id(),
            evidence_artifact_id=new_id(),
            finalized_at=now,
        ),
    )
    identity = finalized.identity
    return {
        "run_id": identity.run_id,
        "idea_id": identity.idea_id,
        "idea_version_id": identity.idea_version_id,
        "evidence_artifact_id": identity.evidence_artifact_id,
    }


def run_backfill(
    candidates: Sequence[Candidate],
    *,
    gateway: Any,
    apply: bool,
    settled: Callable[[str], bool],
    now: datetime | None = None,
) -> dict[str, Any]:
    finalized_at = now or datetime.now(timezone.utc)
    report: dict[str, Any] = {
        "mode": "apply" if apply else "dry_run",
        "candidate_count": len(candidates),
        "finalized_count": 0,
        "unsettled_count": 0,
        "error_count": 0,
        "jobs": [],
    }
    for candidate in candidates:
        entry: dict[str, Any] = {
            "job_id": candidate.job_id,
            "conversation_id": candidate.conversation_id,
            "result_run_id": candidate.result_run_id,
            "created_at": candidate.created_at,
        }
        if not apply:
            entry["outcome"] = "candidate"
            report["jobs"].append(entry)
            continue
        try:
            entry["identity"] = finalize_candidate(gateway, candidate, now=finalized_at)
        except Exception as exc:
            entry["outcome"] = "error"
            entry["error"] = f"{type(exc).__name__}: {exc}"
            report["error_count"] += 1
            report["jobs"].append(entry)
            continue
        if settled(candidate.job_id):
            entry["outcome"] = "finalized"
            report["finalized_count"] += 1
        else:
            # The tuple landed but the owner predicate still says no: the
            # run and its evidence disagree in a way this script must not
            # paper over.
            entry["outcome"] = "unsettled"
            report["unsettled_count"] += 1
        report["jobs"].append(entry)
    report["status"] = (
        "ready"
        if report["error_count"] == 0 and report["unsettled_count"] == 0
        else "attention"
    )
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Finalize succeeded chat backtest jobs whose linked run never became "
            "evidence. Dry run unless --apply."
        ),
    )
    parser.add_argument("--apply", action="store_true", help="Write the tuples.")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _prepare_database_env()
    try:
        target = resolve_destructive_postgres_target()
    except DestructiveDatabaseTargetError as exc:
        parser.error(str(exc))
    announce_destructive_postgres_target(
        target,
        stream=sys.stderr if args.json else sys.stdout,
    )

    with evidence_backfill_gateway(os.environ["DATABASE_URL"]) as gateway:
        candidates = gateway.select_candidates(limit=args.limit)
        report = run_backfill(
            candidates,
            gateway=gateway,
            apply=args.apply,
            settled=gateway.job_is_settled,
        )

    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        print(
            "backtest evidence backfill: "
            f"mode={report['mode']} status={report['status']} "
            f"candidates={report['candidate_count']} "
            f"finalized={report['finalized_count']} "
            f"unsettled={report['unsettled_count']} "
            f"errors={report['error_count']}"
        )
        for job in report["jobs"]:
            line = (
                f"{job['outcome']}: job={job['job_id']} "
                f"conversation={job['conversation_id']} run={job['result_run_id']} "
                f"created_at={job['created_at']}"
            )
            if job.get("error"):
                line += f" error={job['error']}"
            print(line)

    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
