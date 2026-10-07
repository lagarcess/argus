"""Apply an explicit list of migration versions to a named non-hosted database.

The Supabase CLI cannot do this job against production's ledger: it stops on
local files older than the remote head and on remote rows with no local file,
and ``--include-all`` would re-run history whose effects already exist. This
tool applies only the versions it is given, in order, one transaction per file,
and records each ledger row exactly as ``production_migration_gate.py`` reads it
(the file's own version and name, statements split by the gate's splitter).

It never targets a hosted Supabase host. A hosted target needs its own reviewed
change that adds the named project ref and the founder's approval record.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

try:
    from scripts.ops import production_migration_gate as gate
except ImportError:  # run as a script from the repository root
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.ops import production_migration_gate as gate

_HOSTED_SUFFIXES = (".supabase.co", ".supabase.com")
_LEDGER_INSERT = (
    "insert into supabase_migrations.schema_migrations (version, statements, name)"
    " values (%s, %s, %s)"
)


class ApplyError(RuntimeError):
    """Raised before any statement runs."""


@dataclass(frozen=True)
class Step:
    version: str
    name: str
    statements: tuple[str, ...]
    record: bool
    classification: str


def check_target(
    url: str, allow_hosts: Sequence[str], allow_databases: Sequence[str]
) -> None:
    """Fail closed: a named host and database, never a hosted Supabase one."""

    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.query or parts.fragment:
        raise ApplyError("the database URL must not carry a query or fragment")
    if not host or host.endswith(_HOSTED_SUFFIXES):
        raise ApplyError("hosted Supabase targets are refused by this tool")
    if host not in {value.lower() for value in allow_hosts}:
        raise ApplyError("target host is not on the allowed list")
    if parts.path.lstrip("/") not in set(allow_databases):
        raise ApplyError("target database is not on the allowed list")


def plan_steps(
    candidates: Sequence[gate.CandidateMigration],
    applied_versions: Sequence[str],
    approved: Sequence[str],
    unrecorded: Sequence[str] = (),
) -> list[Step]:
    """Validate the approved list against the ledger and return ordered steps.

    ``approved`` versions are recorded and must sit above the gate's
    reconciliation threshold and above everything already applied there.
    ``unrecorded`` versions run without a ledger row and must sit at or below
    the threshold, where the gate holds a pinned hand-reconciliation.
    """

    by_version = {migration.version: migration for migration in candidates}
    applied = set(applied_versions)
    threshold = gate._LEDGER_RECONCILIATION_THROUGH
    overlap = set(approved) & set(unrecorded)
    if overlap:
        raise ApplyError(
            f"versions listed as both recorded and unrecorded: {sorted(overlap)}"
        )
    for version in (*approved, *unrecorded):
        if version not in by_version:
            raise ApplyError(f"version {version} is not a candidate migration")
        if version in applied:
            raise ApplyError(f"version {version} is already in the ledger")
    for version in approved:
        if version <= threshold:
            raise ApplyError(
                f"recorded version {version} is at or below the reconciliation threshold"
            )
    for version in unrecorded:
        if version > threshold:
            raise ApplyError(
                f"unrecorded version {version} is above the reconciliation threshold"
            )
    head = max((version for version in applied if version > threshold), default=threshold)
    for version in approved:
        if version <= head:
            raise ApplyError(
                f"recorded version {version} is not above the ledger head {head}"
            )
    steps: list[Step] = []
    for version in sorted({*approved, *unrecorded}):
        migration = by_version[version]
        classification, _ = gate.classify_migration(migration.source)
        steps.append(
            Step(
                version,
                migration.name,
                migration.statements,
                version in approved,
                classification,
            )
        )
    return steps


def read_ledger_versions(connection: object) -> list[str]:
    rows = connection.execute(  # type: ignore[attr-defined]
        "select version from supabase_migrations.schema_migrations order by version"
    ).fetchall()
    return [str(row[0]) for row in rows]


def apply_steps(connection: object, steps: Sequence[Step]) -> list[str]:
    """One transaction per file; stop at the first failure, leaving earlier files applied."""

    done: list[str] = []
    for step in steps:
        with connection.transaction():  # type: ignore[attr-defined]
            for statement in step.statements:
                connection.execute(statement)  # type: ignore[attr-defined]
            if step.record:
                connection.execute(  # type: ignore[attr-defined]
                    _LEDGER_INSERT, (step.version, list(step.statements), step.name)
                )
        done.append(step.version)
    return done


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument(
        "--approved-file", required=True, help="JSON list of versions to apply and record"
    )
    parser.add_argument(
        "--unrecorded",
        action="append",
        default=[],
        help="version to run without a ledger row",
    )
    parser.add_argument("--database-url-env", default="ARGUS_APPLY_DATABASE_URL")
    parser.add_argument("--allow-host", action="append", required=True)
    parser.add_argument("--allow-database", action="append", required=True)
    parser.add_argument(
        "--execute", action="store_true", help="apply; the default only prints the plan"
    )
    args = parser.parse_args(argv)

    url = os.environ.get(args.database_url_env, "")
    if not url:
        raise ApplyError(f"{args.database_url_env} is not set")
    check_target(url, args.allow_host, args.allow_database)
    approved = json.loads(Path(args.approved_file).read_text())
    if not isinstance(approved, list) or not all(
        isinstance(value, str) for value in approved
    ):
        raise ApplyError("the approved file must be a JSON list of version strings")
    candidates = gate.read_candidate_migrations(Path.cwd(), args.candidate_sha)

    from psycopg import connect

    with connect(url, autocommit=True) as connection:
        steps = plan_steps(
            candidates, read_ledger_versions(connection), approved, args.unrecorded
        )
        for step in steps:
            print(
                f"{'RECORD' if step.record else 'NO-LEDGER':9} {step.version} {step.name} [{step.classification}]"
            )
        if not args.execute:
            print(f"dry run: {len(steps)} step(s); nothing applied")
            return 0
        done = apply_steps(connection, steps)
        print(f"applied {len(done)} step(s)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ApplyError as error:
        print(f"refused: {error}", file=sys.stderr)
        raise SystemExit(2) from None
