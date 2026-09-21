"""SQLite persistence for Clara's local, single-owner workspace."""

import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from threading import get_ident

BUSY_TIMEOUT_MS = 5_000
_snapshots: ContextVar[dict[tuple[Path, int], sqlite3.Connection] | None] = ContextVar(
    "sqlite_read_snapshots", default=None
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS datasets (
    id TEXT PRIMARY KEY, country TEXT NOT NULL, metadata TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deposit_rates (
    dataset_id TEXT NOT NULL REFERENCES datasets(id), id TEXT NOT NULL,
    document TEXT NOT NULL, PRIMARY KEY(dataset_id, id)
);
CREATE TABLE IF NOT EXISTS inflation_rates (
    dataset_id TEXT NOT NULL REFERENCES datasets(id), currency TEXT NOT NULL,
    document TEXT NOT NULL, PRIMARY KEY(dataset_id, currency)
);
CREATE TABLE IF NOT EXISTS load_attempts (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL, scenario TEXT NOT NULL, created_at TEXT NOT NULL,
    completed_at TEXT, status TEXT NOT NULL CHECK(status IN ('loading','succeeded','failed')),
    error_code TEXT
);
CREATE TABLE IF NOT EXISTS p_load_rechecks (
    load_id TEXT PRIMARY KEY REFERENCES load_attempts(id),
    status TEXT NOT NULL CHECK(status IN ('pending','completed','superseded','failed')),
    cursor INTEGER NOT NULL DEFAULT 0, high_water INTEGER NOT NULL,
    checked_count INTEGER NOT NULL DEFAULT 0, error_code TEXT, completed_at TEXT
);
CREATE TABLE IF NOT EXISTS load_datasets (
    load_id TEXT NOT NULL REFERENCES load_attempts(id), country TEXT NOT NULL,
    dataset_id TEXT NOT NULL REFERENCES datasets(id), PRIMARY KEY(load_id,country)
);
CREATE TABLE IF NOT EXISTS confirmations (
    id TEXT PRIMARY KEY, inputs TEXT NOT NULL, pinned_datasets TEXT NOT NULL,
    created_at TEXT NOT NULL, expires_at TEXT NOT NULL, consumed_inputs TEXT,
    comparison_id TEXT REFERENCES comparisons(id)
);
CREATE TABLE IF NOT EXISTS comparisons (
    id TEXT PRIMARY KEY, document TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS saved_decisions (
    id TEXT PRIMARY KEY, comparison_id TEXT NOT NULL UNIQUE REFERENCES comparisons(id),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decision_checks (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
    decision_id TEXT NOT NULL REFERENCES saved_decisions(id),
    load_id TEXT NOT NULL REFERENCES load_attempts(id), created_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('succeeded','failed')),
    before_id TEXT NOT NULL REFERENCES comparisons(id),
    after_id TEXT NOT NULL REFERENCES comparisons(id), reasons TEXT NOT NULL,
    reference_rate_pct TEXT, error_code TEXT, read_at TEXT,
    UNIQUE(decision_id,load_id)
);
CREATE TABLE IF NOT EXISTS p_placement_confirmations (
    id TEXT PRIMARY KEY REFERENCES confirmations(id) ON DELETE CASCADE,
    household_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS p_placement_comparisons (
    id TEXT PRIMARY KEY REFERENCES comparisons(id) ON DELETE CASCADE,
    household_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS p_placement_confirmation_household
    ON p_placement_confirmations(household_id);
CREATE INDEX IF NOT EXISTS p_placement_comparison_household
    ON p_placement_comparisons(household_id);
-- The original single-household local demo belongs to the seeded household.
INSERT OR IGNORE INTO p_placement_confirmations SELECT id, 'household-demo' FROM confirmations;
INSERT OR IGNORE INTO p_placement_comparisons SELECT id, 'household-demo' FROM comparisons;
"""


class Store:
    def __init__(self, path: str | Path, *, busy_timeout_ms: int = BUSY_TIMEOUT_MS):
        if not 0 <= busy_timeout_ms <= BUSY_TIMEOUT_MS:
            raise ValueError(f"busy_timeout_ms must be between 0 and {BUSY_TIMEOUT_MS}")
        self.path = Path(path).resolve()
        self.busy_timeout_ms = busy_timeout_ms
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._open_connection() as connection:
            mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            if mode != "wal":
                raise RuntimeError("SQLite WAL is required")
        with self.connection() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def _open_connection(self):
        connection = sqlite3.connect(
            self.path, timeout=self.busy_timeout_ms / 1000, isolation_level=None
        )
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
            yield connection
        finally:
            connection.close()

    @contextmanager
    def read_snapshot(self):
        """Pin composed reads during one synchronous call; never span an await."""
        key = (self.path, get_ident())
        existing = (_snapshots.get() or {}).get(key)
        if existing is not None:
            yield existing
            return
        with self.connection() as connection:
            connection.execute("PRAGMA query_only = ON")
            # BEGIN alone does not pin a SQLite snapshot until its first read.
            connection.execute("SELECT count(*) FROM sqlite_schema").fetchone()
            token = _snapshots.set({**(_snapshots.get() or {}), key: connection})
            try:
                yield connection
            finally:
                _snapshots.reset(token)

    @contextmanager
    def connection(self, *, write: bool = False):
        existing = (_snapshots.get() or {}).get((self.path, get_ident()))
        if existing is not None:
            if write:
                raise RuntimeError("Cannot write inside a read snapshot")
            yield existing
            return
        with self._open_connection() as connection:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
