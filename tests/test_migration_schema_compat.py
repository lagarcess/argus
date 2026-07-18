"""Real-schema compatibility for SQL migrations, without a database.

Builds the column catalog every migration produces (create table + alter
add/drop) and verifies that later SQL — insert column lists and the
alias-qualified references inside #240's lifecycle functions — is valid
against that schema. This is the class of failure source-string assertions
miss: an insert that omits a NOT NULL column or references a column that
does not exist only breaks on a real database.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "supabase" / "migrations"

_CONSTRAINT_STARTERS = ("primary key", "unique", "check", "constraint", "foreign key")


@dataclass
class _Table:
    columns: set[str] = field(default_factory=set)
    required: set[str] = field(default_factory=set)  # not null, no default


def _strip_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def _parse_create_table(catalog: dict[str, _Table], sql: str) -> None:
    for match in re.finditer(
        r"create table (?:if not exists )?public\.(\w+)\s*\((.*?)\);",
        sql,
        re.DOTALL | re.IGNORECASE,
    ):
        table = catalog.setdefault(match.group(1), _Table())
        depth = 0
        for raw_line in match.group(2).splitlines():
            line = raw_line.strip()
            starts_at_top_level = depth == 0
            depth += line.count("(") - line.count(")")
            if not starts_at_top_level or not line:
                continue
            lowered = line.lower()
            if any(lowered.startswith(starter) for starter in _CONSTRAINT_STARTERS):
                continue
            name = re.match(r"([a-z_][a-z0-9_]*)", lowered)
            if name is None:
                continue
            column = name.group(1)
            table.columns.add(column)
            not_null = "not null" in lowered or "primary key" in lowered
            if not_null and "default" not in lowered:
                table.required.add(column)


def _parse_alters(catalog: dict[str, _Table], sql: str) -> None:
    for statement in re.finditer(
        r"alter table (?:if exists )?public\.(\w+)\s+([^;]*add column[^;]*);",
        sql,
        re.DOTALL | re.IGNORECASE,
    ):
        table = catalog.setdefault(statement.group(1), _Table())
        for match in re.finditer(
            r"add column (?:if not exists )?([a-z_][a-z0-9_]*)([^,]*)",
            statement.group(2),
            re.DOTALL | re.IGNORECASE,
        ):
            column = match.group(1)
            tail = match.group(2).lower()
            table.columns.add(column)
            if "not null" in tail and "default" not in tail:
                table.required.add(column)
    for match in re.finditer(
        r"alter table (?:if exists )?public\.(\w+)\s+alter column "
        r"([a-z_][a-z0-9_]*)\s+drop not null",
        sql,
        re.IGNORECASE,
    ):
        table = catalog.get(match.group(1))
        if table is not None:
            table.required.discard(match.group(2))


def _catalog() -> dict[str, _Table]:
    catalog: dict[str, _Table] = {}
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        sql = _strip_comments(path.read_text(encoding="utf-8"))
        _parse_create_table(catalog, sql)
        _parse_alters(catalog, sql)
    return catalog


def _inserts(sql: str) -> list[tuple[str, list[str]]]:
    found = []
    for match in re.finditer(
        r"insert into public\.(\w+)\s*\(([^)]+)\)",
        sql,
        re.DOTALL | re.IGNORECASE,
    ):
        columns = [
            column.strip().lower()
            for column in match.group(2).split(",")
            if column.strip()
        ]
        found.append((match.group(1), columns))
    return found


def test_catalog_reflects_the_core_schema() -> None:
    catalog = _catalog()
    assert "user_id" in catalog["messages"].columns
    assert "user_id" in catalog["messages"].required
    assert "turn_id" in catalog["chat_turn_lifecycles"].required
    # Pass-1 regression: the direct-route contract relaxed this column.
    assert "conversation_id" not in catalog["backtest_jobs"].required


def test_every_insert_column_list_matches_the_real_schema() -> None:
    """Every inserted column must exist, and every NOT NULL column without a
    default must be present in the insert list."""

    catalog = _catalog()
    problems: list[str] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        sql = _strip_comments(path.read_text(encoding="utf-8"))
        for table_name, columns in _inserts(sql):
            table = catalog.get(table_name)
            if table is None:
                problems.append(f"{path.name}: unknown table {table_name}")
                continue
            unknown = set(columns) - table.columns
            missing = table.required - set(columns)
            if unknown:
                problems.append(
                    f"{path.name}: insert into {table_name} references "
                    f"unknown columns {sorted(unknown)}"
                )
            if missing:
                problems.append(
                    f"{path.name}: insert into {table_name} omits required "
                    f"columns {sorted(missing)}"
                )
    assert problems == []


def test_lifecycle_function_references_resolve_against_the_schema() -> None:
    """The reconciliation function's alias-qualified references must all be
    real columns of the tables the aliases bind to."""

    catalog = _catalog()
    sql = _strip_comments(
        (
            MIGRATIONS_DIR / "20260718000003_chat_turn_acceptance_and_reconciliation.sql"
        ).read_text(encoding="utf-8")
    )
    alias_tables = {"m": "messages", "c": "conversations"}
    for alias, table_name in alias_tables.items():
        columns = catalog[table_name].columns
        for match in re.finditer(rf"\b{alias}\.([a-z_][a-z0-9_]*)", sql):
            assert match.group(1) in columns, (
                f"{alias}.{match.group(1)} does not exist on {table_name}"
            )
    for match in re.finditer(r"\bv_row\.([a-z_][a-z0-9_]*)", sql):
        assert match.group(1) in catalog["chat_turn_lifecycles"].columns
