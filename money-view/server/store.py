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
    def transaction(self):
        """One explicit unit of work shared only with audited synchronous writers."""
        with self.connection(write=True) as connection:
            with TransactionBoundStore(connection) as bound:
                yield bound

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


class TransactionBoundaryError(RuntimeError):
    """A transaction-bound handler attempted to escape its unit of work."""


class _BoundCursor:
    __slots__ = ("__owner", "__cursor")

    def __init__(self, owner, cursor):
        self.__owner, self.__cursor = owner, cursor

    def fetchone(self):
        self.__owner._check()
        return self.__owner._fetch(self.__cursor.fetchone)

    def fetchall(self):
        self.__owner._check()
        return self.__owner._fetch(self.__cursor.fetchall)

    def fetchmany(self, size=1):
        self.__owner._check()
        return self.__owner._fetch(lambda: self.__cursor.fetchmany(size))

    @property
    def rowcount(self):
        self.__owner._check()
        return self.__cursor.rowcount

    @property
    def lastrowid(self):
        self.__owner._check()
        return self.__cursor.lastrowid

    @property
    def description(self):
        self.__owner._check()
        return self.__cursor.description

    def __iter__(self):
        return self

    def __next__(self):
        self.__owner._check()
        return self.__owner._fetch(lambda: next(self.__cursor))

    def __getattr__(self, name):
        self.__owner._reject(f"Cursor capability is not available: {name}")


class _BoundConnection:
    __slots__ = ("__owner",)

    def __init__(self, owner):
        self.__owner = owner

    def execute(self, statement, parameters=()):
        return self.__owner._execute(statement, parameters, many=False)

    def executemany(self, statement, parameters):
        return self.__owner._execute(statement, parameters, many=True)

    @property
    def in_transaction(self):
        self.__owner._check()
        return True

    def __getattr__(self, name):
        self.__owner._reject(f"Connection capability is not available: {name}")


class TransactionBoundStore:
    """Explicit, synchronous facade for audited existing domain writers.

    Obtain through Store.transaction(). Only that outer scope commits. This is
    an API contract for trusted registered handlers, not a Python-code sandbox.
    """

    __slots__ = (
        "__connection",
        "__proxy",
        "__thread",
        "__open",
        "__poisoned",
        "__yield_handle",
    )

    def __init__(self, connection):
        self.__connection = connection
        self.__proxy = _BoundConnection(self)
        self.__thread = get_ident()
        self.__open = False
        self.__poisoned = False
        self.__yield_handle = None

    def __enter__(self):
        import asyncio

        if self.__open or not self.__connection.in_transaction:
            raise TransactionBoundaryError(
                "An existing exclusive transaction is required"
            )
        self.__open = True
        self.__connection.set_authorizer(self._authorize)
        try:
            self.__yield_handle = asyncio.get_running_loop().call_soon(self._yielded)
        except RuntimeError:
            pass
        return self

    def __exit__(self, exc_type, exc, traceback):
        # Python 3.10 does not support disabling this callback with None.
        # The facade is closing; only Store's outer commit/rollback follows.
        self.__connection.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
        if self.__yield_handle is not None:
            self.__yield_handle.cancel()
        self.__open = False
        if exc_type is None and self.__poisoned:
            raise TransactionBoundaryError("An inner failure poisoned the unit of work")
        return False

    def _yielded(self):
        self.__poisoned = True

    def _reject(self, message):
        self.__poisoned = True
        raise TransactionBoundaryError(message)

    def _check(self):
        if not self.__open:
            self._reject("Transaction scope has closed")
        if get_ident() != self.__thread:
            self._reject("Transaction cannot cross threads")
        if self.__poisoned:
            raise TransactionBoundaryError("Unit of work is poisoned")

    def _authorize(self, action, arg1, arg2, database, source):
        # Only row operations and their query expressions belong in handlers.
        allowed = {
            sqlite3.SQLITE_SELECT,
            sqlite3.SQLITE_READ,
            sqlite3.SQLITE_INSERT,
            sqlite3.SQLITE_UPDATE,
            sqlite3.SQLITE_DELETE,
            sqlite3.SQLITE_FUNCTION,
            sqlite3.SQLITE_RECURSIVE,
        }
        if action not in allowed:
            self.__poisoned = True
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    def _execute(self, statement, parameters, *, many):
        self._check()
        try:
            cursor = (
                self.__connection.executemany if many else self.__connection.execute
            )(statement, parameters)
            return _BoundCursor(self, cursor)
        except BaseException:
            self.__poisoned = True
            raise

    def _fetch(self, operation):
        self._check()
        try:
            return operation()
        except StopIteration:
            raise
        except BaseException:
            self.__poisoned = True
            raise

    @contextmanager
    def connection(self, *, write=False):
        self._check()
        try:
            yield self.__proxy
        except BaseException:
            self.__poisoned = True
            raise

    def read_snapshot(self):
        self._reject("Nested snapshots cannot escape the command transaction")

    def transaction(self):
        self._reject("Nested units of work are not supported")

    def __getattr__(self, name):
        self._reject(f"Store capability is not available: {name}")
