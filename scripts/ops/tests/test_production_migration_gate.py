from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts.ops.production_migration_gate import (
    AppliedMigration,
    CandidateMigration,
    MigrationGateError,
    ProductionDatabaseTarget,
    build_migration_report,
    classify_migration,
    load_gate_contract,
    main,
    read_applied_migrations,
    read_candidate_migrations,
    resolve_production_target,
)


def test_missing_additive_migration_blocks_promotion() -> None:
    candidate = CandidateMigration.from_source(
        "supabase/migrations/20260812000000_add_release_marker.sql",
        "create table public.release_marker (id uuid primary key);",
    )

    report = build_migration_report(
        candidate_sha="a" * 40,
        target=ProductionDatabaseTarget(
            project_ref="production-ref",
            database_host="pooler.supabase.test",
        ),
        candidate_migrations=[candidate],
        applied_migrations=[],
    )

    assert report["status"] == "blocked"
    assert report["stop_reasons"] == ["missing_candidate_migrations"]
    assert report["latest_applied_version"] is None
    assert report["human_approval"] == "required_before_out_of_band_apply"
    assert report["apply_result"] == "not_performed_by_gate"
    assert report["readback"] == "blocked_pending_schema_parity"
    assert report["missing_migrations"] == [
        {
            "version": "20260812000000",
            "name": "add_release_marker",
            "path": ("supabase/migrations/" "20260812000000_add_release_marker.sql"),
            "sha256": candidate.sha256,
            "classification": "additive",
            "classification_basis": "conservative_top_level_sql",
            "live_requirement": "human_review_and_live_readback",
        }
    ]


def test_exact_version_and_name_parity_passes() -> None:
    candidate = CandidateMigration.from_source(
        "supabase/migrations/20260812000000_add_release_marker.sql",
        "create table public.release_marker (id uuid primary key);",
    )

    report = build_migration_report(
        candidate_sha="b" * 40,
        target=ProductionDatabaseTarget(
            project_ref="production-ref",
            database_host="pooler.supabase.test",
        ),
        candidate_migrations=[candidate],
        applied_migrations=[
            AppliedMigration(
                version="20260812000000",
                name="add_release_marker",
            )
        ],
    )

    assert report["status"] == "pass"
    assert report["stop_reasons"] == []
    assert report["latest_applied_version"] == "20260812000000"
    assert report["human_approval"] == "not_required_no_gap"
    assert report["apply_result"] == "not_performed_by_gate"
    assert report["readback"] == "migration_ledger_parity_verified"
    assert report["missing_migrations"] == []
    assert report["applied_migrations"] == [
        {
            "version": "20260812000000",
            "name": "add_release_marker",
        }
    ]


def test_unexpected_applied_migration_and_name_drift_both_block() -> None:
    candidate = CandidateMigration.from_source(
        "supabase/migrations/20260812000000_add_release_marker.sql",
        "create table public.release_marker (id uuid primary key);",
    )

    report = build_migration_report(
        candidate_sha="c" * 40,
        target=ProductionDatabaseTarget(
            project_ref="production-ref",
            database_host="pooler.supabase.test",
        ),
        candidate_migrations=[candidate],
        applied_migrations=[
            AppliedMigration(
                version="20260812000000",
                name="different_name",
            ),
            AppliedMigration(
                version="20260813000000",
                name="production_only",
            ),
        ],
    )

    assert report["status"] == "blocked"
    assert report["stop_reasons"] == [
        "unexpected_applied_migrations",
        "applied_migration_name_drift",
    ]
    assert report["unexpected_applied_migrations"] == [
        {"version": "20260813000000", "name": "production_only"}
    ]
    assert report["name_drift"] == [
        {
            "version": "20260812000000",
            "candidate_name": "add_release_marker",
            "applied_name": "different_name",
        }
    ]
    assert report["human_approval"] == "required_for_migration_drift_reconciliation"


def test_duplicate_candidate_version_fails_closed() -> None:
    first = CandidateMigration.from_source(
        "supabase/migrations/20260812000000_first.sql",
        "create table public.first (id uuid primary key);",
    )
    second = CandidateMigration.from_source(
        "supabase/migrations/20260812000000_second.sql",
        "create table public.second (id uuid primary key);",
    )

    with pytest.raises(MigrationGateError, match="duplicate candidate"):
        build_migration_report(
            candidate_sha="d" * 40,
            target=ProductionDatabaseTarget(
                project_ref="production-ref",
                database_host="pooler.supabase.test",
            ),
            candidate_migrations=[first, second],
            applied_migrations=[],
        )


def test_classifier_is_conservative_and_ignores_function_body_deletes() -> None:
    contract_source = """
    create or replace function public.remove_row() returns void
    language plpgsql as $$
    begin
        delete from public.rows;
    end;
    $$;
    """

    assert classify_migration(contract_source) == (
        "contract-replacing",
        "expand_contract_or_maintenance_required",
    )
    assert classify_migration(contract_source.replace(" or replace", "")) == (
        "additive",
        "human_review_and_live_readback",
    )
    assert classify_migration("alter table public.rows drop column legacy;") == (
        "destructive",
        "maintenance_backup_and_founder_approval_required",
    )
    assert classify_migration("drop table public.rows;") == (
        "destructive",
        "maintenance_backup_and_founder_approval_required",
    )
    assert classify_migration("drop function public.old_contract();") == (
        "contract-replacing",
        "expand_contract_or_maintenance_required",
    )
    assert classify_migration(
        "with old_rows as (select id from public.rows) "
        "delete from public.rows where id in (select id from old_rows);"
    ) == (
        "destructive",
        "maintenance_backup_and_founder_approval_required",
    )
    assert classify_migration("alter table public.rows enable row level security;") == (
        "contract-replacing",
        "expand_contract_or_maintenance_required",
    )


def test_candidate_and_contract_are_read_from_exact_git_commit(
    tmp_path: Path,
) -> None:
    repo, candidate_sha = _candidate_repo(tmp_path, project_ref="a" * 20)
    migration_path = (
        repo / "supabase" / "migrations" / "20260812000000_add_release_marker.sql"
    )
    migration_path.write_text(
        "drop table public.release_marker;\n",
        encoding="utf-8",
    )

    migrations = read_candidate_migrations(repo, candidate_sha)
    contract = load_gate_contract(repo, candidate_sha)

    assert [migration.source for migration in migrations] == [
        "create table public.release_marker (id uuid primary key);\n"
    ]
    assert contract.production_supabase_project_ref == "a" * 20
    with pytest.raises(MigrationGateError, match="40-character"):
        read_candidate_migrations(repo, candidate_sha[:8])


@pytest.mark.parametrize(
    "database_url",
    (
        "postgresql://postgres:secret@db.{ref}.supabase.co:5432/postgres",
        (
            "postgresql://postgres.{ref}:secret@"
            "aws-0-us-east-1.pooler.supabase.com:6543/postgres"
        ),
    ),
)
def test_production_target_requires_the_checked_in_project_ref(
    database_url: str,
) -> None:
    project_ref = "a" * 20

    target = resolve_production_target(
        database_url.format(ref=project_ref),
        expected_project_ref=project_ref,
    )

    assert target.project_ref == project_ref
    assert "secret" not in repr(target)


def test_production_target_rejects_a_different_pooler_project_without_leaking() -> None:
    database_url = (
        "postgresql://postgres."
        f"{'b' * 20}:do-not-print@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
    )

    with pytest.raises(MigrationGateError) as exc_info:
        resolve_production_target(
            database_url,
            expected_project_ref="a" * 20,
        )

    assert "does not match" in str(exc_info.value)
    assert "do-not-print" not in str(exc_info.value)


def test_applied_migrations_are_read_in_a_read_only_session() -> None:
    calls: dict[str, Any] = {}

    class FakeCursor:
        def __init__(self) -> None:
            self.queries: list[str] = []

        def __enter__(self) -> FakeCursor:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def execute(self, query: str) -> None:
            self.queries.append(query)

        def fetchone(self) -> tuple[str]:
            return ("on",)

        def fetchall(self) -> list[tuple[str, str]]:
            return [
                ("20260811000000", "first"),
                ("20260812000000", "second"),
            ]

    class FakeConnection:
        def __init__(self) -> None:
            self.cursor_instance = FakeCursor()
            self.closed = False

        def cursor(self) -> FakeCursor:
            return self.cursor_instance

        def close(self) -> None:
            self.closed = True

    connection = FakeConnection()

    def connect(database_url: str, **kwargs: object) -> FakeConnection:
        calls["database_url"] = database_url
        calls["kwargs"] = kwargs
        return connection

    applied = read_applied_migrations(
        "postgresql://postgres:do-not-print@db.example.test/postgres",
        connect_factory=connect,
    )

    assert applied == [
        AppliedMigration(version="20260811000000", name="first"),
        AppliedMigration(version="20260812000000", name="second"),
    ]
    assert calls["kwargs"] == {
        "application_name": "argus-production-migration-gate",
        "autocommit": True,
        "connect_timeout": 10,
        "options": "-c default_transaction_read_only=on",
    }
    assert connection.cursor_instance.queries == [
        "show transaction_read_only",
        (
            "select version, coalesce(name, '') "
            "from supabase_migrations.schema_migrations order by version"
        ),
    ]
    assert connection.closed is True


def test_cli_writes_a_complete_blocking_report_without_leaking_credentials(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, candidate_sha = _candidate_repo(tmp_path, project_ref="a" * 20)
    output_path = tmp_path / "evidence" / "migration-gate.json"
    connection = _FakeConnection([])

    exit_code = main(
        ["--candidate-sha", candidate_sha, "--output", str(output_path)],
        environ={
            "ARGUS_PRODUCTION_DATABASE_URL": (
                "postgresql://postgres."
                f"{'a' * 20}:do-not-print@"
                "aws-0-us-east-1.pooler.supabase.com:6543/postgres"
            )
        },
        repo_root=repo,
        connect_factory=lambda *_args, **_kwargs: connection,
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    captured = capsys.readouterr()
    assert exit_code == 1
    assert json.loads(captured.out) == report
    assert report["status"] == "blocked"
    assert report["candidate_sha"] == candidate_sha
    assert report["counts"] == {
        "applied": 0,
        "candidate": 1,
        "missing": 1,
        "name_drift": 0,
        "unexpected": 0,
    }
    assert report["database_access"] == "read_only"
    assert report["migration_apply"] == "never"
    assert "do-not-print" not in captured.out
    assert "do-not-print" not in output_path.read_text(encoding="utf-8")


def test_cli_passes_only_when_the_production_ledger_matches(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, candidate_sha = _candidate_repo(tmp_path, project_ref="a" * 20)
    output_path = tmp_path / "migration-gate.json"
    connection = _FakeConnection([("20260812000000", "add_release_marker")])

    exit_code = main(
        ["--candidate-sha", candidate_sha, "--output", str(output_path)],
        environ={
            "ARGUS_PRODUCTION_DATABASE_URL": (
                "postgresql://postgres:do-not-print@"
                f"db.{'a' * 20}.supabase.co:5432/postgres"
            )
        },
        repo_root=repo,
        connect_factory=lambda *_args, **_kwargs: connection,
    )

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert report["status"] == "pass"
    assert report["missing_migrations"] == []
    assert json.loads(output_path.read_text(encoding="utf-8")) == report


def test_cli_redacts_database_failures_and_writes_a_blocked_report(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, candidate_sha = _candidate_repo(tmp_path, project_ref="a" * 20)
    output_path = tmp_path / "migration-gate.json"

    def fail_connect(*_args: object, **_kwargs: object) -> _FakeConnection:
        raise RuntimeError("driver failed with password do-not-print")

    exit_code = main(
        ["--candidate-sha", candidate_sha, "--output", str(output_path)],
        environ={
            "ARGUS_PRODUCTION_DATABASE_URL": (
                "postgresql://postgres:do-not-print@"
                f"db.{'a' * 20}.supabase.co:5432/postgres"
            )
        },
        repo_root=repo,
        connect_factory=fail_connect,
    )

    rendered = capsys.readouterr().out
    report = json.loads(rendered)
    assert exit_code == 2
    assert report["status"] == "blocked"
    assert report["stop_reasons"] == ["gate_execution_failed"]
    assert report["error"] == "production migration ledger read failed"
    assert "do-not-print" not in rendered
    assert output_path.read_text(encoding="utf-8") == rendered


def test_cli_rejects_a_candidate_that_is_not_the_clean_checkout_head(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, candidate_sha = _candidate_repo(tmp_path, project_ref="a" * 20)
    (repo / "README.md").write_text("new head\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-qm", "advance fixture"],
        cwd=repo,
        check=True,
    )
    output_path = tmp_path / "migration-gate.json"

    exit_code = main(
        ["--candidate-sha", candidate_sha, "--output", str(output_path)],
        environ={
            "ARGUS_PRODUCTION_DATABASE_URL": (
                "postgresql://postgres:do-not-print@"
                f"db.{'a' * 20}.supabase.co:5432/postgres"
            )
        },
        repo_root=repo,
        connect_factory=lambda *_args, **_kwargs: pytest.fail(
            "database access must not start"
        ),
    )

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert report["error"] == "checkout HEAD does not match the candidate SHA"


def test_cli_rejects_tracked_changes_before_database_access(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, candidate_sha = _candidate_repo(tmp_path, project_ref="a" * 20)
    (repo / "render.yaml").write_text("dirty checkout\n", encoding="utf-8")
    output_path = tmp_path / "migration-gate.json"

    exit_code = main(
        ["--candidate-sha", candidate_sha, "--output", str(output_path)],
        environ={
            "ARGUS_PRODUCTION_DATABASE_URL": (
                "postgresql://postgres:do-not-print@"
                f"db.{'a' * 20}.supabase.co:5432/postgres"
            )
        },
        repo_root=repo,
        connect_factory=lambda *_args, **_kwargs: pytest.fail(
            "database access must not start"
        ),
    )

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert report["error"] == "checkout has tracked changes outside the candidate"


def _candidate_repo(tmp_path: Path, *, project_ref: str) -> tuple[Path, str]:
    repo = tmp_path / "candidate-repo"
    migration_path = (
        repo / "supabase" / "migrations" / "20260812000000_add_release_marker.sql"
    )
    render_path = repo / "render.yaml"
    migration_path.parent.mkdir(parents=True)
    migration_path.write_text(
        "create table public.release_marker (id uuid primary key);\n",
        encoding="utf-8",
    )
    render_path.write_text(
        "services:\n"
        "  - type: web\n"
        "    name: argus-api\n"
        "    envVars:\n"
        "      - key: SUPABASE_URL\n"
        f"        value: https://{project_ref}.supabase.co\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "migration-gate@example.test"],
        cwd=repo,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Migration Gate Test"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-qm", "test fixture"],
        cwd=repo,
        check=True,
    )
    candidate_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return repo, candidate_sha


class _FakeCursor:
    def __init__(self, rows: list[tuple[str, str]]) -> None:
        self._rows = rows

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, _query: str) -> None:
        return None

    def fetchone(self) -> tuple[str]:
        return ("on",)

    def fetchall(self) -> list[tuple[str, str]]:
        return self._rows


class _FakeConnection:
    def __init__(self, rows: list[tuple[str, str]]) -> None:
        self._cursor = _FakeCursor(rows)

    def cursor(self) -> _FakeCursor:
        return self._cursor

    def close(self) -> None:
        return None
