"""Block production promotion when candidate migrations are not applied."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Mapping, Protocol, Sequence, TypedDict, TypeVar, cast
from urllib.parse import unquote, urlsplit

MigrationClassification = Literal[
    "additive",
    "contract-replacing",
    "destructive",
]

_MIGRATION_PATH = re.compile(
    r"^supabase/migrations/(?P<version>\d{14})_(?P<name>[a-z0-9_]+)\.sql$"
)
_EXACT_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_PROJECT_REF = re.compile(r"^[a-z0-9]{20}$")
_RENDER_PATH = "render.yaml"


class MigrationGateError(RuntimeError):
    """Raised when the gate cannot prove a safe, exact comparison."""


class DatabaseCursor(Protocol):
    def __enter__(self) -> DatabaseCursor: ...

    def __exit__(self, *args: object) -> object: ...

    def execute(self, query: str) -> object: ...

    def fetchone(self) -> Sequence[object] | None: ...

    def fetchall(self) -> Sequence[Sequence[object]]: ...


class DatabaseConnection(Protocol):
    def cursor(self) -> DatabaseCursor: ...

    def close(self) -> None: ...


class ConnectFactory(Protocol):
    def __call__(
        self,
        database_url: str,
        **kwargs: object,
    ) -> DatabaseConnection: ...


class MigrationRecord(TypedDict):
    version: str
    name: str
    path: str
    sha256: str


class MissingMigrationRecord(MigrationRecord):
    classification: MigrationClassification
    classification_basis: str
    live_requirement: str


class AppliedMigrationRecord(TypedDict):
    version: str
    name: str


@dataclass(frozen=True)
class ProductionDatabaseTarget:
    """Sanitized production database identity for release evidence."""

    project_ref: str
    database_host: str


@dataclass(frozen=True)
class MigrationGateContract:
    """Production identity derived from the candidate release contract."""

    production_supabase_project_ref: str


@dataclass(frozen=True)
class AppliedMigration:
    """One migration row read from production's Supabase ledger."""

    version: str
    name: str

    def as_record(self) -> AppliedMigrationRecord:
        return {"version": self.version, "name": self.name}


@dataclass(frozen=True)
class CandidateMigration:
    """One migration read from the exact candidate Git tree."""

    version: str
    name: str
    path: str
    sha256: str
    source: str

    @classmethod
    def from_source(cls, path: str, source: str) -> CandidateMigration:
        match = _MIGRATION_PATH.fullmatch(path)
        if match is None:
            raise ValueError(f"invalid migration path: {path}")
        return cls(
            version=match.group("version"),
            name=match.group("name"),
            path=path,
            sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(),
            source=source,
        )

    def as_record(self) -> MigrationRecord:
        return {
            "version": self.version,
            "name": self.name,
            "path": self.path,
            "sha256": self.sha256,
        }

    def as_missing_record(self) -> MissingMigrationRecord:
        classification, requirement = classify_migration(self.source)
        return {
            **self.as_record(),
            "classification": classification,
            "classification_basis": "conservative_top_level_sql",
            "live_requirement": requirement,
        }


MigrationT = TypeVar("MigrationT", CandidateMigration, AppliedMigration)


def load_gate_contract(
    repo_root: Path,
    candidate_sha: str,
) -> MigrationGateContract:
    """Read the target contract from the exact candidate commit."""

    _verify_candidate_sha(repo_root, candidate_sha)
    raw = _read_git_file(repo_root, candidate_sha, _RENDER_PATH)
    try:
        render_source = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MigrationGateError(f"candidate {_RENDER_PATH} must be valid UTF-8") from exc
    api_block = re.search(
        r"(?ms)^  - type:.*?^    name: argus-api\s*$.*?(?=^  - type:|\Z)",
        render_source,
    )
    if api_block is None:
        raise MigrationGateError("candidate render.yaml does not declare argus-api")
    supabase_url = re.search(
        r"(?m)^      - key: SUPABASE_URL\s*$\n" r"^        value:\s*([^\s#]+)\s*$",
        api_block.group(0),
    )
    if supabase_url is None:
        raise MigrationGateError(
            "candidate argus-api does not declare a literal SUPABASE_URL"
        )
    project_ref = _project_ref_from_supabase_url(
        supabase_url.group(1).strip("'\""),
    )
    return MigrationGateContract(production_supabase_project_ref=project_ref)


def read_candidate_migrations(
    repo_root: Path,
    candidate_sha: str,
) -> list[CandidateMigration]:
    """Enumerate migration sources from an exact candidate Git tree."""

    _verify_candidate_sha(repo_root, candidate_sha)
    listing = _run_git(
        repo_root,
        "ls-tree",
        "-r",
        "--name-only",
        candidate_sha,
        "--",
        "supabase/migrations",
    )
    try:
        paths = listing.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise MigrationGateError("candidate migration paths are not UTF-8") from exc
    migrations: list[CandidateMigration] = []
    for path in paths:
        if not path.endswith(".sql"):
            continue
        source_bytes = _read_git_file(repo_root, candidate_sha, path)
        try:
            source = source_bytes.decode("utf-8")
            migration = CandidateMigration.from_source(path, source)
        except (UnicodeDecodeError, ValueError) as exc:
            raise MigrationGateError(f"candidate migration is malformed: {path}") from exc
        migrations.append(migration)
    migrations.sort(key=lambda migration: (migration.version, migration.path))
    if not migrations:
        raise MigrationGateError("candidate contains no Supabase migrations")
    _unique_by_version(migrations, source="candidate")
    return migrations


def resolve_production_target(
    database_url: str,
    *,
    expected_project_ref: str,
) -> ProductionDatabaseTarget:
    """Verify a direct or pooler URL without retaining its credentials."""

    if not _PROJECT_REF.fullmatch(expected_project_ref):
        raise MigrationGateError("checked-in production project ref is invalid")
    try:
        parsed = urlsplit(database_url)
        host = (parsed.hostname or "").lower()
        _ = parsed.port
    except ValueError as exc:
        raise MigrationGateError("production database URL is malformed") from exc
    if parsed.scheme.lower() not in {"postgres", "postgresql"} or not host:
        raise MigrationGateError(
            "production database URL must be an absolute Postgres URL"
        )
    username = unquote(parsed.username or "")
    direct_host = f"db.{expected_project_ref}.supabase.co"
    direct_match = host == direct_host
    pooler_match = (
        host.endswith(".pooler.supabase.com")
        and username == f"postgres.{expected_project_ref}"
    )
    if not direct_match and not pooler_match:
        raise MigrationGateError(
            "production database target does not match the checked-in "
            "Supabase project ref"
        )
    return ProductionDatabaseTarget(
        project_ref=expected_project_ref,
        database_host=host,
    )


def read_applied_migrations(
    database_url: str,
    *,
    connect_factory: ConnectFactory | None = None,
) -> list[AppliedMigration]:
    """Read production's migration ledger through a read-only session."""

    if connect_factory is None:
        from psycopg import connect

        connect_factory = cast(ConnectFactory, connect)
    connection: DatabaseConnection | None = None
    try:
        connection = connect_factory(
            database_url,
            application_name="argus-production-migration-gate",
            autocommit=True,
            connect_timeout=10,
            options="-c default_transaction_read_only=on",
        )
        with connection.cursor() as cursor:
            cursor.execute("show transaction_read_only")
            read_only = cursor.fetchone()
            if read_only is None or str(read_only[0]).lower() != "on":
                raise MigrationGateError(
                    "production database session did not enter read-only mode"
                )
            cursor.execute(
                "select version, coalesce(name, '') "
                "from supabase_migrations.schema_migrations order by version"
            )
            rows = cursor.fetchall()
        if any(len(row) < 2 for row in rows):
            raise MigrationGateError(
                "production migration ledger returned a malformed row"
            )
        applied = [
            AppliedMigration(version=str(row[0]), name=str(row[1])) for row in rows
        ]
        _unique_by_version(applied, source="production")
    except MigrationGateError:
        raise
    except Exception as exc:
        raise MigrationGateError("production migration ledger read failed") from exc
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
    return applied


def classify_migration(
    source: str,
) -> tuple[MigrationClassification, str]:
    """Classify top-level SQL conservatively for live-database review."""

    statements = _top_level_statements(source)
    if any(_is_destructive(statement) for statement in statements):
        return (
            "destructive",
            "maintenance_backup_and_founder_approval_required",
        )
    if statements and all(_is_additive(statement) for statement in statements):
        return "additive", "human_review_and_live_readback"
    return (
        "contract-replacing",
        "expand_contract_or_maintenance_required",
    )


def build_migration_report(
    *,
    candidate_sha: str,
    target: ProductionDatabaseTarget,
    candidate_migrations: Sequence[CandidateMigration],
    applied_migrations: Sequence[AppliedMigration],
) -> dict[str, object]:
    """Build a fail-closed comparison report for release evidence."""

    candidate_by_version = _unique_by_version(
        candidate_migrations,
        source="candidate",
    )
    applied_by_version = _unique_by_version(
        applied_migrations,
        source="production",
    )
    missing = [
        migration.as_missing_record()
        for version, migration in candidate_by_version.items()
        if version not in applied_by_version
    ]
    unexpected = [
        migration.as_record()
        for version, migration in applied_by_version.items()
        if version not in candidate_by_version
    ]
    name_drift = [
        {
            "version": version,
            "candidate_name": candidate.name,
            "applied_name": applied_by_version[version].name,
        }
        for version, candidate in candidate_by_version.items()
        if version in applied_by_version
        and applied_by_version[version].name
        and applied_by_version[version].name != candidate.name
    ]
    stop_reasons: list[str] = []
    if missing:
        stop_reasons.append("missing_candidate_migrations")
    if unexpected:
        stop_reasons.append("unexpected_applied_migrations")
    if name_drift:
        stop_reasons.append("applied_migration_name_drift")
    parity_verified = not stop_reasons
    return {
        "schema_version": "argus.production_migration_gate.v1",
        "status": "pass" if parity_verified else "blocked",
        "candidate_sha": candidate_sha,
        "production_target": {
            "project_ref": target.project_ref,
            "database_host": target.database_host,
        },
        "candidate_migrations": [
            migration.as_record() for migration in candidate_migrations
        ],
        "applied_migrations": [migration.as_record() for migration in applied_migrations],
        "missing_migrations": missing,
        "unexpected_applied_migrations": unexpected,
        "name_drift": name_drift,
        "stop_reasons": stop_reasons,
        "latest_applied_version": max(applied_by_version, default=None),
        "human_approval": (
            "not_required_no_gap"
            if parity_verified
            else (
                "required_before_out_of_band_apply"
                if missing
                else "required_for_migration_drift_reconciliation"
            )
        ),
        "apply_result": "not_performed_by_gate",
        "readback": (
            "migration_ledger_parity_verified"
            if parity_verified
            else "blocked_pending_schema_parity"
        ),
        "counts": {
            "candidate": len(candidate_migrations),
            "applied": len(applied_migrations),
            "missing": len(missing),
            "unexpected": len(unexpected),
            "name_drift": len(name_drift),
        },
        "database_access": "read_only",
        "migration_apply": "never",
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    repo_root: Path | None = None,
    connect_factory: ConnectFactory | None = None,
) -> int:
    """Run the production migration gate and write its durable JSON report."""

    parser = argparse.ArgumentParser(
        description=(
            "Compare an exact candidate's migrations with production's "
            "read-only Supabase ledger. This command never applies migrations."
        )
    )
    parser.add_argument(
        "--candidate-sha",
        required=True,
        help="Exact 40-character candidate commit SHA.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path for the JSON release-evidence report.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    root = repo_root or Path(__file__).resolve().parents[2]
    source = os.environ if environ is None else environ

    try:
        _verify_checkout_head(root, args.candidate_sha)
        contract = load_gate_contract(root, args.candidate_sha)
        candidate_migrations = read_candidate_migrations(
            root,
            args.candidate_sha,
        )
        database_url = str(source.get("ARGUS_PRODUCTION_DATABASE_URL") or "").strip()
        if not database_url:
            raise MigrationGateError(
                "ARGUS_PRODUCTION_DATABASE_URL must be set explicitly; "
                "dotenv discovery is disabled"
            )
        target = resolve_production_target(
            database_url,
            expected_project_ref=contract.production_supabase_project_ref,
        )
        applied_migrations = read_applied_migrations(
            database_url,
            connect_factory=connect_factory,
        )
        report = build_migration_report(
            candidate_sha=args.candidate_sha,
            target=target,
            candidate_migrations=candidate_migrations,
            applied_migrations=applied_migrations,
        )
        exit_code = 0 if report["status"] == "pass" else 1
    except MigrationGateError as exc:
        report = {
            "schema_version": "argus.production_migration_gate.v1",
            "status": "blocked",
            "candidate_sha": args.candidate_sha,
            "database_access": "read_only",
            "migration_apply": "never",
            "stop_reasons": ["gate_execution_failed"],
            "error": str(exc),
        }
        exit_code = 2

    report["checked_at"] = (
        datetime.now(timezone.utc)
        .isoformat()
        .replace(
            "+00:00",
            "Z",
        )
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    except OSError:
        report["status"] = "blocked"
        report["stop_reasons"] = ["evidence_write_failed"]
        report["error"] = "migration gate evidence could not be written"
        rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
        exit_code = 2
    sys.stdout.write(rendered)
    return exit_code


def _unique_by_version(
    migrations: Sequence[MigrationT],
    *,
    source: str,
) -> dict[str, MigrationT]:
    by_version: dict[str, MigrationT] = {}
    for migration in migrations:
        if migration.version in by_version:
            raise MigrationGateError(
                f"duplicate {source} migration version: {migration.version}"
            )
        by_version[migration.version] = migration
    return by_version


def _top_level_statements(source: str) -> list[str]:
    sanitized = _strip_sql_literals_and_comments(source)
    return [
        " ".join(statement.lower().split())
        for statement in sanitized.split(";")
        if statement.strip()
    ]


def _strip_sql_literals_and_comments(source: str) -> str:
    output: list[str] = []
    index = 0
    length = len(source)
    while index < length:
        if source.startswith("--", index):
            newline = source.find("\n", index + 2)
            if newline == -1:
                break
            output.append("\n")
            index = newline + 1
            continue
        if source.startswith("/*", index):
            index = _skip_block_comment(source, index)
            output.append(" ")
            continue
        if source[index] == "'":
            index = _skip_quoted(source, index, "'")
            output.append(" ")
            continue
        if source[index] == '"':
            index = _skip_quoted(source, index, '"')
            output.append(" quoted_identifier ")
            continue
        dollar_tag = _dollar_tag_at(source, index)
        if dollar_tag is not None:
            end = source.find(dollar_tag, index + len(dollar_tag))
            index = length if end == -1 else end + len(dollar_tag)
            output.append(" ")
            continue
        output.append(source[index])
        index += 1
    return "".join(output)


def _skip_block_comment(source: str, start: int) -> int:
    depth = 1
    index = start + 2
    while index < len(source) and depth:
        if source.startswith("/*", index):
            depth += 1
            index += 2
        elif source.startswith("*/", index):
            depth -= 1
            index += 2
        else:
            index += 1
    return index


def _skip_quoted(source: str, start: int, quote: str) -> int:
    index = start + 1
    while index < len(source):
        if source[index] != quote:
            index += 1
            continue
        if index + 1 < len(source) and source[index + 1] == quote:
            index += 2
            continue
        return index + 1
    return index


def _dollar_tag_at(source: str, index: int) -> str | None:
    if source[index] != "$":
        return None
    match = re.match(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$", source[index:])
    return match.group(0) if match else None


def _is_destructive(statement: str) -> bool:
    return bool(
        re.search(r"\b(?:truncate|delete\s+from)\b", statement)
        or re.search(r"\bdrop\b", statement)
    )


def _is_additive(statement: str) -> bool:
    if statement.startswith("create or replace "):
        return False
    additive_prefixes = (
        "create table ",
        "create table if not exists ",
        "create schema ",
        "create schema if not exists ",
        "create type ",
        "create sequence ",
        "create index ",
        "create index if not exists ",
        "create unique index ",
        "create unique index if not exists ",
        "create function ",
        "create policy ",
        "comment on ",
        "grant ",
    )
    if statement.startswith(additive_prefixes):
        return True
    if statement.startswith("alter table "):
        return _alter_table_actions_are_additive(statement)
    return False


def _alter_table_actions_are_additive(statement: str) -> bool:
    match = re.fullmatch(
        r"alter table (?:if exists )?(?:only )?\S+(?: \*)? (?P<actions>.+)",
        statement,
    )
    if match is None:
        return False
    actions = _split_top_level_commas(match.group("actions"))
    return bool(actions) and all(action.startswith("add ") for action in actions)


def _split_top_level_commas(value: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    for index, character in enumerate(value):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                return []
        elif character == "," and depth == 0:
            parts.append(value[start:index].strip())
            start = index + 1
    if depth != 0:
        return []
    parts.append(value[start:].strip())
    return parts if all(parts) else []


def _verify_candidate_sha(repo_root: Path, candidate_sha: str) -> None:
    if not _EXACT_COMMIT_SHA.fullmatch(candidate_sha):
        raise MigrationGateError(
            "candidate SHA must be an exact 40-character lowercase commit SHA"
        )
    resolved = (
        _run_git(
            repo_root,
            "rev-parse",
            "--verify",
            f"{candidate_sha}^{{commit}}",
        )
        .decode("ascii", errors="strict")
        .strip()
    )
    if resolved != candidate_sha:
        raise MigrationGateError("candidate SHA did not resolve exactly")


def _verify_checkout_head(repo_root: Path, candidate_sha: str) -> None:
    _verify_candidate_sha(repo_root, candidate_sha)
    head = _run_git(repo_root, "rev-parse", "HEAD").decode("ascii").strip()
    if head != candidate_sha:
        raise MigrationGateError("checkout HEAD does not match the candidate SHA")
    tracked_status = _run_git(
        repo_root,
        "status",
        "--porcelain",
        "--untracked-files=no",
    )
    if tracked_status.strip():
        raise MigrationGateError("checkout has tracked changes outside the candidate")


def _read_git_file(repo_root: Path, candidate_sha: str, path: str) -> bytes:
    return _run_git(repo_root, "show", f"{candidate_sha}:{path}")


def _project_ref_from_supabase_url(supabase_url: str) -> str:
    try:
        parsed = urlsplit(supabase_url)
        host = (parsed.hostname or "").lower()
        _ = parsed.port
    except ValueError as exc:
        raise MigrationGateError("candidate argus-api SUPABASE_URL is malformed") from exc
    host_match = re.fullmatch(r"([a-z0-9]{20})\.supabase\.co", host)
    if parsed.scheme.lower() != "https" or host_match is None:
        raise MigrationGateError(
            "candidate argus-api SUPABASE_URL must identify one Supabase project"
        )
    return host_match.group(1)


def _run_git(repo_root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise MigrationGateError(f"Git candidate read failed: git {args[0]}")
    return result.stdout


if __name__ == "__main__":
    raise SystemExit(main())
