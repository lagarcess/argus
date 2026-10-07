"""The applier refuses everything it was not explicitly given."""

from __future__ import annotations

import pytest

from scripts.ops import apply_approved_migrations as applier
from scripts.ops.production_migration_gate import CandidateMigration

THRESHOLD = "20260811210000"


def _migration(
    version: str, name: str, sql: str = "create table t (id int);"
) -> CandidateMigration:
    return CandidateMigration.from_source(
        f"supabase/migrations/{version}_{name}.sql", sql
    )


CANDIDATES = [
    _migration(
        "20260505000001", "old_missing", "alter table t drop constraint if exists c"
    ),
    _migration("20260606000001", "old_effect_exists"),
    _migration("20260914120000", "ledger_head"),
    _migration("20260925120000", "first_new"),
    _migration("20260928200000", "second_new"),
]
APPLIED = ["20260606000001", "20260914120000"]


def test_hosted_and_unlisted_targets_are_refused() -> None:
    allow = (["127.0.0.1"], ["rehearsal"])
    applier.check_target("postgresql://u:p@127.0.0.1:5432/rehearsal", *allow)
    for url in (
        "postgresql://u:p@db.abcdefghijklmnopqrst.supabase.co:5432/postgres",
        "postgresql://u:p@aws-0-us-east-1.pooler.supabase.com:5432/postgres",
        "postgresql://u:p@127.0.0.1:5432/postgres",
        "postgresql://u:p@10.0.0.9:5432/rehearsal",
        "postgresql://u:p@127.0.0.1:5432/rehearsal?host=elsewhere",
    ):
        with pytest.raises(applier.ApplyError):
            applier.check_target(url, *allow)


def test_recorded_steps_are_ordered_and_classified() -> None:
    steps = applier.plan_steps(CANDIDATES, APPLIED, ["20260928200000", "20260925120000"])
    assert [(s.version, s.record) for s in steps] == [
        ("20260925120000", True),
        ("20260928200000", True),
    ]


def test_unrecorded_history_runs_without_a_ledger_row() -> None:
    steps = applier.plan_steps(
        CANDIDATES, APPLIED, ["20260925120000"], ["20260505000001"]
    )
    assert [(s.version, s.record) for s in steps] == [
        ("20260505000001", False),
        ("20260925120000", True),
    ]
    assert steps[0].classification == "destructive"


@pytest.mark.parametrize(
    ("approved", "unrecorded"),
    [
        (["20260999999999"], []),  # not a candidate
        (["20260914120000"], []),  # already applied
        (["20260505000001"], []),  # recorded below the threshold
        (["20260925120000"], ["20260925120000"]),  # both lists
        ([], ["20260925120000"]),  # unrecorded above the threshold
    ],
)
def test_plan_refuses_anything_unapproved(
    approved: list[str], unrecorded: list[str]
) -> None:
    with pytest.raises(applier.ApplyError):
        applier.plan_steps(CANDIDATES, APPLIED, approved, unrecorded)


def test_recorded_versions_must_follow_the_ledger_head() -> None:
    candidates = [*CANDIDATES, _migration("20260915000000", "behind_head")]
    with pytest.raises(applier.ApplyError):
        applier.plan_steps(candidates, ["20260925120000"], ["20260915000000"])


class _Transaction:
    def __init__(self, log: list[str], fail_on: str | None) -> None:
        self.log, self.fail_on = log, fail_on

    def __enter__(self) -> None:
        self.log.append("begin")

    def __exit__(self, exc_type: object, *_: object) -> bool:
        self.log.append("rollback" if exc_type else "commit")
        return False


class _Connection:
    def __init__(self, fail_on: str | None = None) -> None:
        self.log: list[str] = []
        self.fail_on = fail_on

    def transaction(self) -> _Transaction:
        return _Transaction(self.log, self.fail_on)

    def execute(self, statement: str, params: object = None) -> None:
        if self.fail_on and self.fail_on in statement:
            raise RuntimeError("boom")
        if params is not None and "set_config" in statement:
            self.log.append(f"timeout={params[0]}")
        else:
            self.log.append("ledger" if params is not None else statement)


def test_each_file_is_one_transaction_and_records_its_own_ledger_row() -> None:
    steps = applier.plan_steps(
        CANDIDATES, APPLIED, ["20260925120000"], ["20260505000001"]
    )
    connection = _Connection()
    assert applier.apply_steps(connection, steps) == ["20260505000001", "20260925120000"]
    assert connection.log == [
        "begin",
        "timeout=5s",
        "alter table t drop constraint if exists c",
        "commit",
        "begin",
        "timeout=5s",
        "create table t (id int)",
        "ledger",
        "commit",
    ]


def test_a_failing_file_rolls_back_and_stops_the_run() -> None:
    steps = applier.plan_steps(CANDIDATES, APPLIED, ["20260925120000", "20260928200000"])
    connection = _Connection(fail_on="create table")
    with pytest.raises(RuntimeError):
        applier.apply_steps(connection, steps)
    assert connection.log == ["begin", "timeout=5s", "rollback"]


@pytest.mark.parametrize("value", ["5s", "500ms", "1min"])
def test_lock_timeout_accepts_plain_durations(value: str) -> None:
    assert applier.check_lock_timeout(value) == value


@pytest.mark.parametrize("value", ["", "0", "5", "5 s; drop table x", "-1s", "1h"])
def test_lock_timeout_refuses_anything_else(value: str) -> None:
    with pytest.raises(applier.ApplyError):
        applier.check_lock_timeout(value)
