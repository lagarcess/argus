"""Apply an explicit list of migration versions to a named non-hosted database.

The Supabase CLI cannot do this job against production's ledger: it stops on
local files older than the remote head and on remote rows with no local file,
and ``--include-all`` would re-run history whose effects already exist. This
tool applies only the versions it is given, in order, and records each ledger
row exactly as ``production_migration_gate.py`` reads it (the file's own
version and name, statements split by the gate's splitter).

It never targets a hosted Supabase host. A hosted target needs its own reviewed
change that adds the named project ref and the founder's approval record.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

try:
    from scripts.ops import production_migration_gate as gate
except ImportError:  # run as a script from the repository root
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.ops import production_migration_gate as gate

_HOSTED_SUFFIXES = (".supabase.co", ".supabase.com")
_LOOPBACK = {"localhost", "127.0.0.1", "::1"}
_REFUSED_ENVIRONMENT = ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGPASSFILE")
_LOCK_TIMEOUT = re.compile(r"[1-9]\d{0,5}(ms|s|min)")
_ADVISORY_LOCK_KEY = 7_340_118_221_605
_BEGIN = {"begin", "start"}
_COMMIT = {"commit", "end"}
_REFUSED_CONTROL = {"rollback", "abort", "savepoint", "release"}
_LEDGER_INSERT = (
    "insert into supabase_migrations.schema_migrations (version, statements, name)"
    " values (%s, %s, %s)"
)


def _plain_host(name: str) -> str:
    """The name libpq would connect to: decoded, lowercase, no trailing dot."""

    return unquote(name).lower().rstrip(".")


def _is_hosted(name: str) -> bool:
    plain = _plain_host(name)
    return plain.endswith(_HOSTED_SUFFIXES) or plain in {"supabase.co", "supabase.com"}


class ApplyError(RuntimeError):
    """Raised before any statement runs, or to explain why a run stopped."""


@dataclass(frozen=True)
class Step:
    version: str
    name: str
    statements: tuple[str, ...]  # exactly what the ledger row records
    segments: tuple[tuple[str, ...], ...]  # what runs, one transaction each
    record: bool
    classification: str


def check_target(
    url: str,
    allow_hosts: Sequence[str],
    allow_databases: Sequence[str],
    environ: dict[str, str] | None = None,
) -> None:
    """Fail closed: one named host and database, never a hosted Supabase one."""

    environment = os.environ if environ is None else environ
    for name in _REFUSED_ENVIRONMENT:
        if environment.get(name):
            raise ApplyError(f"{name} is set and could redirect the connection")
    parts = urlsplit(url)
    if "," in parts.netloc:
        raise ApplyError("a multi-host database URL is refused")
    host = _plain_host(parts.hostname or "")
    if parts.query or parts.fragment:
        raise ApplyError("the database URL must not carry a query or fragment")
    if "," in host:
        raise ApplyError("a multi-host database URL is refused")
    if not host or _is_hosted(host) or any(_is_hosted(value) for value in allow_hosts):
        raise ApplyError("hosted Supabase targets are refused by this tool")
    if host not in {_plain_host(value) for value in allow_hosts}:
        raise ApplyError("target host is not on the allowed list")
    if parts.path.lstrip("/") not in set(allow_databases):
        raise ApplyError("target database is not on the allowed list")


def verify_connection(
    connection: object, allow_hosts: Sequence[str], allow_databases: Sequence[str]
) -> None:
    """Check where the connection actually went, not where the URL said."""

    info = connection.info  # type: ignore[attr-defined]
    allowed = {_plain_host(value) for value in allow_hosts}
    host = _plain_host(info.host or "")
    hostaddr = _plain_host(info.hostaddr or "")
    if _is_hosted(host) or _is_hosted(hostaddr):
        raise ApplyError("the connection went to a hosted Supabase host")
    if host not in allowed:
        raise ApplyError("the connection went to a host that is not on the allowed list")
    if (
        hostaddr
        and hostaddr not in allowed
        and not (host in _LOOPBACK and hostaddr in _LOOPBACK)
    ):
        raise ApplyError("the connection address is not on the allowed list")
    row = connection.execute("select current_database()").fetchone()  # type: ignore[attr-defined]
    if not row or row[0] not in set(allow_databases):
        raise ApplyError("the connected database is not on the allowed list")


def split_segments(statements: Sequence[str]) -> tuple[tuple[str, ...], ...]:
    """Turn a file's statements into the transactions to run.

    A file wrapped in ``begin`` and ``commit`` is one transaction with the wrapper
    dropped. A ``commit`` in the middle starts a new transaction. Rollbacks and
    savepoints are refused. Comment-only statements are skipped.
    """

    segments: list[list[str]] = [[]]
    seen_statement = False
    for statement in statements:
        text = gate._strip_sql_literals_and_comments(statement).strip()
        if not text:
            continue
        keyword = text.split()[0].lower().rstrip(";")
        if keyword in _REFUSED_CONTROL:
            raise ApplyError(f"transaction control '{keyword}' is not supported")
        if keyword in _BEGIN:
            if seen_statement:
                raise ApplyError("'begin' is only supported as the first statement")
            seen_statement = True
            continue
        seen_statement = True
        if keyword in _COMMIT:
            segments.append([])
        else:
            segments[-1].append(statement)
    return tuple(tuple(segment) for segment in segments if segment)


def plan_steps(
    candidates: Sequence[gate.CandidateMigration],
    applied_versions: Sequence[str],
    approved: Sequence[str],
    unrecorded: Sequence[str] = (),
    allow_mid_file_commit: Sequence[str] = (),
) -> list[Step]:
    """Validate the approved list against the ledger and return ordered steps.

    ``approved`` versions are recorded. They must sit above the gate's
    reconciliation threshold and above everything already applied there, and
    must be the next versions in order with none skipped (a prefix is fine, so a
    run can go in batches). ``unrecorded`` versions run without a ledger row and
    must sit at or below the threshold, where the gate holds a pinned
    hand-reconciliation.
    """

    by_version = {migration.version: migration for migration in candidates}
    applied = set(applied_versions)
    threshold = gate._LEDGER_RECONCILIATION_THROUGH
    if len(set(approved)) != len(approved) or len(set(unrecorded)) != len(unrecorded):
        raise ApplyError("a version is listed more than once")
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
    above = sorted(version for version in by_version if version > head)
    if sorted(approved) != above[: len(approved)]:
        skipped = [
            version for version in above[: len(approved)] if version not in approved
        ]
        raise ApplyError(
            f"the approved list skips {skipped or 'versions'} that sit between the ledger head and "
            "its last entry; skipped versions could never be applied afterwards"
        )
    steps: list[Step] = []
    for version in sorted({*approved, *unrecorded}):
        migration = by_version[version]
        segments = split_segments(migration.statements)
        if not segments:
            raise ApplyError(
                f"version {version} has no runnable statement, so it could not be recorded"
            )
        if len(segments) > 1 and version not in allow_mid_file_commit:
            raise ApplyError(
                f"version {version} commits inside the file and would run in {len(segments)} "
                f"transactions; pass --allow-mid-file-commit {version} to accept that"
            )
        classification, _ = gate.classify_migration(migration.source)
        steps.append(
            Step(
                version,
                migration.name,
                migration.statements,
                segments,
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


def check_lock_timeout(value: str) -> str:
    """A file that cannot get its locks in time fails and rolls back instead of queueing behind traffic."""

    if _LOCK_TIMEOUT.fullmatch(value) is None:
        raise ApplyError("the lock timeout must look like 500ms, 5s or 1min")
    return value


def apply_steps(
    connection: object,
    steps: Sequence[Step],
    lock_timeout: str = "5s",
    on_done: object = None,
    on_segment: object = None,
) -> list[str]:
    """Run each file's transactions in order; the ledger row joins the last one.

    Stops at the first failure. Files that already committed stay applied, and
    ``on_segment(step, number, total)`` is called after each committed transaction
    and ``on_done(step)`` after each file, so the operator knows exactly which.
    """

    check_lock_timeout(lock_timeout)
    done: list[str] = []
    for step in steps:
        for index, segment in enumerate(step.segments):
            with connection.transaction():  # type: ignore[attr-defined]
                connection.execute(  # type: ignore[attr-defined]
                    "select set_config('lock_timeout', %s, true)", (lock_timeout,)
                )
                for statement in segment:
                    connection.execute(statement)  # type: ignore[attr-defined]
                if step.record and index == len(step.segments) - 1:
                    connection.execute(  # type: ignore[attr-defined]
                        _LEDGER_INSERT, (step.version, list(step.statements), step.name)
                    )
            if callable(on_segment):
                on_segment(step, index + 1, len(step.segments))
        done.append(step.version)
        if callable(on_done):
            on_done(step)
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
    parser.add_argument(
        "--allow-mid-file-commit",
        action="append",
        default=[],
        help="version whose file commits inside itself, applied in several transactions",
    )
    parser.add_argument("--database-url-env", default="ARGUS_APPLY_DATABASE_URL")
    parser.add_argument("--allow-host", action="append", required=True)
    parser.add_argument("--allow-database", action="append", required=True)
    parser.add_argument(
        "--lock-timeout",
        default="5s",
        help="per-transaction lock timeout such as 500ms, 5s or 1min",
    )
    parser.add_argument(
        "--execute", action="store_true", help="apply; the default only prints the plan"
    )
    args = parser.parse_args(argv)

    url = os.environ.get(args.database_url_env, "")
    if not url:
        raise ApplyError(f"{args.database_url_env} is not set")
    check_target(url, args.allow_host, args.allow_database)
    lock_timeout = check_lock_timeout(args.lock_timeout)
    approved = json.loads(Path(args.approved_file).read_text())
    if not isinstance(approved, list) or not all(
        isinstance(value, str) for value in approved
    ):
        raise ApplyError("the approved file must be a JSON list of version strings")
    candidates = gate.read_candidate_migrations(Path.cwd(), args.candidate_sha)

    import psycopg

    with psycopg.connect(url, autocommit=True) as connection:
        verify_connection(connection, args.allow_host, args.allow_database)
        locked = connection.execute(
            "select pg_try_advisory_lock(%s)", (_ADVISORY_LOCK_KEY,)
        ).fetchone()
        if not locked or not locked[0]:
            raise ApplyError("another run of this tool holds the migration lock")
        steps = plan_steps(
            candidates,
            read_ledger_versions(connection),
            approved,
            args.unrecorded,
            args.allow_mid_file_commit,
        )
        for step in steps:
            label = "RECORD" if step.record else "NO-LEDGER"
            print(f"{label:9} {step.version} {step.name} [{step.classification}]")
        if not args.execute:
            print(f"dry run: {len(steps)} step(s); nothing applied")
            return 0

        def report(step: Step) -> None:
            print(f"committed {step.version} {step.name}", flush=True)

        def report_segment(step: Step, number: int, total: int) -> None:
            if total > 1:
                print(
                    f"  transaction {number}/{total} of {step.version} committed",
                    flush=True,
                )

        try:
            done = apply_steps(connection, steps, lock_timeout, report, report_segment)
        except Exception as error:
            raise ApplyError(
                f"stopped: {error}. Everything reported as committed stays applied, including "
                "the first transactions of a file that commits inside itself. Recorded files can "
                "be read from the ledger; NO-LEDGER steps leave no trace, so take every one that "
                "was reported committed out of the retry command"
            ) from error
        print(f"applied {len(done)} step(s)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ApplyError as error:
        print(f"refused: {error}", file=sys.stderr)
        raise SystemExit(2) from None
