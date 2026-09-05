from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

OPS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = OPS_DIR.parents[1]
SCRIPT = OPS_DIR / "backfill_backtest_evidence.py"

CONNECTION_ENV = (
    "DATABASE_URL",
    "ARGUS_WORKFLOW_DATABASE_URL",
    "SUPABASE_URL",
    "SUPABASE_PROJECT_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
)


def _clean_env() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in CONNECTION_ENV}
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO_ROOT / "src"), str(REPO_ROOT), env.get("PYTHONPATH", "")]
    )
    return env


def test_entry_point_fails_closed_without_an_explicit_target(tmp_path: Path) -> None:
    """No dotenv discovery, no gateway: a missing DATABASE_URL stops the
    script at argument parsing, before any database coordinate is read."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--apply"],
        cwd=tmp_path,
        env=_clean_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "DATABASE_URL must be set explicitly" in result.stderr


def test_entry_point_holds_one_coordinate_and_rejects_a_bad_one(tmp_path: Path) -> None:
    """Selection, the run read, finalization, and the re-check all run on the
    one DATABASE_URL, so no Supabase URL or key is consulted, and an invalid
    URL is refused before any connection opens."""
    env = _clean_env()
    env["DATABASE_URL"] = "https://not-a-database.example"
    env["SUPABASE_URL"] = "https://ambient.example"
    env["SUPABASE_SERVICE_ROLE_KEY"] = "ambient-key"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--apply"],
        cwd=tmp_path,
        env=_clean_env() | env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "DATABASE_URL must use postgres:// or postgresql://" in result.stderr


def _module():
    sys.path.insert(0, str(OPS_DIR))
    try:
        import backfill_backtest_evidence as module
    finally:
        sys.path.pop(0)
    return module


def _completed_run(*, run_id: str, conversation_id: str):
    from argus.api.schemas import BacktestRun

    return BacktestRun(
        id=run_id,
        conversation_id=conversation_id,
        status="completed",
        asset_class="equity",
        symbols=["AAPL", "MSFT"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={"aggregate": {"performance": {"total_return_pct": 12.8}}},
        config_snapshot={"template": "buy_and_hold"},
        conversation_result_card={
            "title": "AAPL, MSFT buy and hold",
            "rows": [{"label": "Total return", "value": "+12.8%"}],
            "actions": [{"type": "show_breakdown", "payload": {}}],
        },
        created_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
        chart={"kind": "equity_curve", "series": []},
        trades=[],
    )


class _MemoryGateway:
    """The memory finalizer behind the two methods the script calls."""

    def __init__(self) -> None:
        from argus.domain.backtest_finalization import MemoryBacktestFinalizationGateway
        from argus.domain.store import AlphaStore

        self.store = AlphaStore()
        self._finalizer = MemoryBacktestFinalizationGateway(self.store)
        self.finalize_calls = 0

    def seed_run(self, *, user_id: str, run) -> None:
        self.store.backtest_runs[run.id] = run
        self.store.backtest_run_owners[run.id] = user_id

    def get_backtest_run(self, *, user_id: str, run_id: str):
        if self.store.backtest_run_owners.get(run_id) != user_id:
            return None
        return self.store.backtest_runs.get(run_id)

    def finalize_backtest_completion(self, *, finalization):
        self.finalize_calls += 1
        return self._finalizer.finalize_backtest_completion(finalization=finalization)


def _candidate(module, *, run_id: str, user_id: str, conversation_id: str):
    return module.Candidate(
        job_id="00000000-0000-4000-8000-000000000101",
        user_id=user_id,
        conversation_id=conversation_id,
        result_run_id=run_id,
        created_at="2026-06-10T00:00:00+00:00",
    )


def test_dry_run_lists_candidates_and_writes_nothing() -> None:
    module = _module()
    gateway = _MemoryGateway()
    run = _completed_run(run_id="run-1", conversation_id="conv-1")
    gateway.seed_run(user_id="user-1", run=run)

    report = module.run_backfill(
        [_candidate(module, run_id="run-1", user_id="user-1", conversation_id="conv-1")],
        gateway=gateway,
        apply=False,
        settled=lambda job_id: pytest.fail("dry run must not verify settlement"),
    )

    assert report["mode"] == "dry_run"
    assert report["status"] == "ready"
    assert [job["outcome"] for job in report["jobs"]] == ["candidate"]
    assert gateway.finalize_calls == 0
    assert gateway.store.evidence_artifacts == {}


def test_apply_finalizes_through_the_production_finalizer_and_verifies() -> None:
    module = _module()
    gateway = _MemoryGateway()
    run = _completed_run(run_id="run-1", conversation_id="conv-1")
    gateway.seed_run(user_id="user-1", run=run)
    candidate = _candidate(
        module, run_id="run-1", user_id="user-1", conversation_id="conv-1"
    )

    def settled(job_id: str) -> bool:
        assert job_id == candidate.job_id
        artifact = next(iter(gateway.store.evidence_artifacts.values()), None)
        card = gateway.store.backtest_runs["run-1"].conversation_result_card
        return artifact is not None and card.get("evidence_artifact_id") == artifact.id

    report = module.run_backfill(
        [candidate], gateway=gateway, apply=True, settled=settled
    )

    assert report["status"] == "ready"
    assert report["finalized_count"] == 1
    job = report["jobs"][0]
    assert job["outcome"] == "finalized"
    identity = job["identity"]
    artifact = gateway.store.evidence_artifacts[identity["evidence_artifact_id"]]
    assert artifact.source_run_id == "run-1"
    assert artifact.idea_id == identity["idea_id"]
    assert artifact.idea_version_id == identity["idea_version_id"]
    assert (
        gateway.store.backtest_finalizations[
            ("user-1", f"{module.EXECUTION_IDENTITY_PREFIX}:{candidate.job_id}")
        ]
        == "run-1"
    )
    # The card the conversation renders now carries the evidence identity.
    card = gateway.store.backtest_runs["run-1"].conversation_result_card
    assert card["evidence_artifact_id"] == artifact.id
    assert card["title"] == "AAPL, MSFT buy and hold"


def test_a_failing_job_is_reported_and_the_rest_continue() -> None:
    module = _module()
    gateway = _MemoryGateway()
    run = _completed_run(run_id="run-2", conversation_id="conv-2")
    gateway.seed_run(user_id="user-2", run=run)
    missing = module.Candidate(
        job_id="00000000-0000-4000-8000-000000000201",
        user_id="user-2",
        conversation_id="conv-2",
        result_run_id="run-missing",
        created_at="2026-06-11T00:00:00+00:00",
    )
    present = module.Candidate(
        job_id="00000000-0000-4000-8000-000000000202",
        user_id="user-2",
        conversation_id="conv-2",
        result_run_id="run-2",
        created_at="2026-06-12T00:00:00+00:00",
    )

    report = module.run_backfill(
        [missing, present],
        gateway=gateway,
        apply=True,
        settled=lambda job_id: job_id == present.job_id,
    )

    assert report["status"] == "attention"
    assert [job["outcome"] for job in report["jobs"]] == ["error", "finalized"]
    assert "linked run is missing" in report["jobs"][0]["error"]
    assert report["error_count"] == 1 and report["finalized_count"] == 1


def test_a_tuple_the_owner_predicate_still_rejects_is_flagged_not_hidden() -> None:
    module = _module()
    gateway = _MemoryGateway()
    run = _completed_run(run_id="run-3", conversation_id="conv-3")
    gateway.seed_run(user_id="user-3", run=run)

    report = module.run_backfill(
        [_candidate(module, run_id="run-3", user_id="user-3", conversation_id="conv-3")],
        gateway=gateway,
        apply=True,
        settled=lambda job_id: False,
    )

    assert report["status"] == "attention"
    assert report["jobs"][0]["outcome"] == "unsettled"
    assert report["unsettled_count"] == 1
