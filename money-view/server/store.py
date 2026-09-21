"""SQLite persistence for Clara's local, single-owner workspace."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

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
"""


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def connection(self, *, write: bool = False):
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()
