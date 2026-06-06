from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]


class FakeProofGateway:
    def __init__(self, row: dict[str, object]) -> None:
        self.row = dict(row)
        self.transitions: list[tuple[str, dict[str, object]]] = []

    def fetch_job(self, job_id: str) -> dict[str, object] | None:
        if self.row["id"] != job_id:
            return None
        return dict(self.row)

    def update_job_status(
        self,
        *,
        job_id: str,
        status: str,
        execution_metadata: dict[str, object],
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> dict[str, object]:
        assert self.row["id"] == job_id
        self.transitions.append(
            (
                status,
                {
                    "execution_metadata": execution_metadata,
                    "started_at": started_at,
                    "finished_at": finished_at,
                },
            )
        )
        self.row["status"] = status
        self.row["execution_metadata"] = execution_metadata
        if started_at is not None:
            self.row["started_at"] = started_at
        if finished_at is not None:
            self.row["finished_at"] = finished_at
        return dict(self.row)


def test_workflow_proof_marks_queued_job_running_then_succeeded() -> None:
    from workflows.proof import run_workflow_proof

    job_id = str(uuid4())
    gateway = FakeProofGateway(
        {
            "id": job_id,
            "status": "queued",
            "attempts": 0,
            "launch_payload": {"kind": "render_workflow_proof"},
            "execution_metadata": {"existing": "kept"},
        }
    )

    result = run_workflow_proof(
        gateway,
        job_id=job_id,
        nonce="proof-nonce",
        workflow_run_id="local-run",
    )

    assert result["job_id"] == job_id
    assert result["status"] == "succeeded"
    assert result["nonce"] == "proof-nonce"
    assert result["workflow_run_id"] == "local-run"
    assert [transition[0] for transition in gateway.transitions] == [
        "running",
        "succeeded",
    ]
    metadata = gateway.row["execution_metadata"]
    assert metadata["existing"] == "kept"
    assert metadata["workflow_proof"]["nonce"] == "proof-nonce"
    assert metadata["workflow_proof"]["workflow_run_id"] == "local-run"


def test_workflow_proof_rejects_non_proof_jobs() -> None:
    from workflows.proof import WorkflowProofError, run_workflow_proof

    job_id = str(uuid4())
    gateway = FakeProofGateway(
        {
            "id": job_id,
            "status": "queued",
            "attempts": 0,
            "launch_payload": {"kind": "real_backtest"},
            "execution_metadata": {},
        }
    )

    with pytest.raises(WorkflowProofError, match="render_workflow_proof"):
        run_workflow_proof(gateway, job_id=job_id, nonce="proof-nonce")


def test_workflow_proof_requires_secret_database_url() -> None:
    from workflows.proof import require_database_url

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        require_database_url({})

    assert require_database_url({"DATABASE_URL": "postgres://user:secret@example/db"})


def test_backtest_jobs_migration_defines_durable_workflow_boundary() -> None:
    migrations = list((ROOT / "supabase" / "migrations").glob("*backtest_jobs*.sql"))
    assert migrations, "missing backtest_jobs migration"

    sql = "\n".join(path.read_text(encoding="utf-8") for path in migrations)

    assert "create table if not exists public.backtest_jobs" in sql
    for column in (
        "id uuid primary key",
        "user_id uuid not null references public.profiles",
        "conversation_id uuid not null references public.conversations",
        "idempotency_key text",
        "payload_hash text not null",
        "launch_payload jsonb not null",
        "status text not null",
        "execution_metadata jsonb not null default '{}'::jsonb",
        "result_run_id uuid references public.backtest_runs",
    ):
        assert column in sql

    for status in ("queued", "running", "succeeded", "failed", "canceled", "expired"):
        assert f"'{status}'" in sql

    for index_name in (
        "idx_backtest_jobs_user_status_queued",
        "idx_backtest_jobs_conversation_created",
        "idx_backtest_jobs_result_run",
        "idx_backtest_jobs_user_idempotency_key",
        "idx_backtest_jobs_user_payload_hash",
    ):
        assert index_name in sql

    assert "alter table public.backtest_jobs enable row level security" in sql
    assert "create policy backtest_jobs_owner_select" in sql
    assert "to authenticated" in sql
    assert "using (user_id = auth.uid())" in sql
    assert "grant select on table public.backtest_jobs to authenticated" in sql
    assert "grant all privileges on table public.backtest_jobs to service_role" in sql


def test_api_contract_documents_backtest_job_boundary_fields() -> None:
    contract = (ROOT / "docs" / "API_CONTRACT.md").read_text(encoding="utf-8")
    section_start = contract.index("\n## Backtest Job\n")
    section_end = contract.index("# 5. Metrics Catalog")
    section = contract[section_start:section_end]

    for field in (
        '"user_id": "uuid"',
        '"idempotency_key": "uuid-or-client-key"',
        '"launch_payload":',
        '"priority": "normal"',
        '"attempts": 1',
        '"max_attempts": 1',
        '"queued_at": "timestamp"',
        '"started_at": "timestamp"',
        '"finished_at": null',
    ):
        assert field in section


def test_workflow_requirements_keep_render_sdk_isolated_from_api_install() -> None:
    requirements_path = ROOT / "workflows" / "requirements.txt"
    assert requirements_path.exists()
    requirements = requirements_path.read_text(encoding="utf-8")

    assert "render_sdk>=0.7.0" in requirements
    assert "psycopg[binary]" in requirements

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "render_sdk" not in pyproject
