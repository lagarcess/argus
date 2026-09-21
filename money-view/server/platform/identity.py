"""Persisted local credentials, sessions and household membership authority."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import timedelta
from itertools import islice
from typing import Annotated, Callable
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request, Response

from ..store import Store
from .common import (
    CURRENCY_DIGITS,
    Context,
    PlatformError,
    get_context,
    identifier,
    now,
    require_owner,
)
from .identity_contracts import (
    COUNTRY_CURRENCY,
    HouseholdPatch,
    HouseholdSwitch,
    LocalMember,
    Login,
    MemberRole,
    PasswordChange,
    Preferences,
    SessionRevoke,
)

COOKIE = "clara_session"
DEMO_PASSWORD = "Clara-demo-2026!"
SESSION_AGE = timedelta(days=7)
SESSION_ACTIVITY_INTERVAL = timedelta(minutes=5)
MAX_MEMORY_CONTEXT_ROWS = 100
MAX_MEMORY_CONTEXT_BYTES = 32 * 1024
MAX_HOUSEHOLD_EXPORT_ROWS = 50_000
MAX_HOUSEHOLD_EXPORT_BYTES = 32 * 1024 * 1024
SCHEMA = """
CREATE TABLE IF NOT EXISTS p_identity_meta (id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS p_users (
 id TEXT PRIMARY KEY, display_name TEXT NOT NULL, preferred_name TEXT,
 avatar_color TEXT NOT NULL, password_hash TEXT NOT NULL,
 created_at TEXT NOT NULL, deleted_at TEXT, fixture INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS p_households (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, country TEXT NOT NULL,
 currency_override TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS p_memberships (
 household_id TEXT NOT NULL REFERENCES p_households(id),
 user_id TEXT NOT NULL REFERENCES p_users(id),
 role TEXT NOT NULL CHECK(role IN ('owner','editor','viewer')),
 PRIMARY KEY(household_id,user_id)
);
CREATE TABLE IF NOT EXISTS p_sessions (
 id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE,
 user_id TEXT NOT NULL REFERENCES p_users(id), household_id TEXT NOT NULL REFERENCES p_households(id),
 created_at TEXT NOT NULL, expires_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, revoked_at TEXT
);
CREATE INDEX IF NOT EXISTS p_sessions_user ON p_sessions(user_id);
CREATE TABLE IF NOT EXISTS p_preferences (
 user_id TEXT PRIMARY KEY REFERENCES p_users(id), document TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS p_memory_settings (
 user_id TEXT NOT NULL REFERENCES p_users(id), household_id TEXT NOT NULL REFERENCES p_households(id),
 enabled INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(user_id,household_id)
);
CREATE TABLE IF NOT EXISTS p_memories (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES p_users(id),
 household_id TEXT NOT NULL REFERENCES p_households(id), content TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS p_memories_owner ON p_memories(household_id,user_id);
CREATE TABLE IF NOT EXISTS p_local_feedback (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES p_users(id),
 household_id TEXT NOT NULL REFERENCES p_households(id), kind TEXT NOT NULL,
 message TEXT NOT NULL, created_at TEXT NOT NULL
);
"""


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def password_matches(password: str, encoded: str) -> bool:
    if not encoded:
        return False
    _, salt, expected = encoded.split("$")
    digest = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
    )
    return hmac.compare_digest(digest.hex(), expected)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def same_origin(request: Request) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = request.headers.get("origin")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise PlatformError("cross_origin_write", 403)
    if origin:
        parsed = urlsplit(origin)
        if parsed.scheme != request.url.scheme or parsed.netloc != request.url.netloc:
            raise PlatformError("cross_origin_write", 403)


def profile(row) -> dict:
    return {
        key: row[key] for key in ("id", "display_name", "preferred_name", "avatar_color")
    }


def household(row) -> dict:
    result = {key: row[key] for key in ("id", "name", "country", "currency_override")}
    result["effective_currency"] = (
        row["currency_override"]
        if row["currency_override"] is not None
        else COUNTRY_CURRENCY[row["country"]]
    )
    if "role" in row.keys():
        result["role"] = row["role"]
    return result


@dataclass(frozen=True)
class DataDomain:
    export: Callable
    clear: Callable
    usage: Callable


@dataclass
class ReadBudget:
    max_rows: int
    max_bytes: int
    error_code: str
    rows: int = 0
    bytes: int = 0

    def accept(self, row) -> None:
        self.rows += 1
        if self.rows > self.max_rows:
            raise PlatformError(self.error_code, 413)
        self.bytes += len(
            json.dumps(dict(row), ensure_ascii=False, separators=(",", ":")).encode()
        )
        if self.bytes > self.max_bytes:
            raise PlatformError(self.error_code, 413)


class BoundedCursor:
    """Check each source row before callers can grow their response collection."""

    def __init__(self, cursor, budget: ReadBudget):
        self._cursor = cursor
        self._budget = budget

    def __iter__(self):
        return self

    def __next__(self):
        row = next(self._cursor)
        self._budget.accept(row)
        return row

    def fetchone(self):
        return next(self, None)

    def fetchall(self):
        return list(self)

    def fetchmany(self, size: int = 1):
        return list(islice(self, size))


class ExportReader:
    """One cumulative source budget across existing domain SELECT callbacks."""

    def __init__(self, connection, budget: ReadBudget | None = None):
        self._connection = connection
        self._budget = (
            budget
            if budget is not None
            else ReadBudget(
                MAX_HOUSEHOLD_EXPORT_ROWS,
                MAX_HOUSEHOLD_EXPORT_BYTES,
                "household_export_too_large",
            )
        )

    def execute(self, sql: str, parameters=()) -> BoundedCursor:
        return BoundedCursor(self._connection.execute(sql, parameters), self._budget)


class Identity:
    def __init__(self, store: Store):
        self.store = store
        self.data_domains: dict[str, DataDomain] = {}

    def initialize(self) -> None:
        with self.store.connection(write=True) as db:
            db.executescript(SCHEMA)
        with self.store.connection(write=True) as db:
            if db.execute(
                "SELECT 1 FROM p_identity_meta WHERE id='fixtures-v1'"
            ).fetchone():
                return
            timestamp = now().isoformat()
            for household_id, name in (
                ("household-demo", "Rivera"),
                ("household-other", "Separate fixture"),
            ):
                db.execute(
                    "INSERT INTO p_households VALUES (?,?, 'DO',NULL,?)",
                    (household_id, name, timestamp),
                )
            for user_id, name, role, household_id in (
                ("user-demo", "Alex Rivera", "owner", "household-demo"),
                ("user-partner", "Sam Rivera", "editor", "household-demo"),
                ("user-viewer", "Taylor Rivera", "viewer", "household-demo"),
                ("user-other", "Morgan Lee", "owner", "household-other"),
            ):
                self._create_user(
                    db, user_id, name, DEMO_PASSWORD, timestamp, fixture=True
                )
                db.execute(
                    "INSERT INTO p_memberships VALUES (?,?,?)",
                    (household_id, user_id, role),
                )
            db.execute("INSERT INTO p_identity_meta VALUES ('fixtures-v1')")

    @staticmethod
    def _create_user(db, user_id, name, password, timestamp, *, fixture=False):
        db.execute(
            "INSERT INTO p_users VALUES (?,?,NULL,'forest',?,?,NULL,?)",
            (user_id, name, password_hash(password), timestamp, int(fixture)),
        )
        db.execute(
            "INSERT INTO p_preferences VALUES (?,?)",
            (user_id, Preferences().model_dump_json()),
        )

    def register_data_domain(
        self, name: str, *, export: Callable, clear: Callable, usage: Callable
    ) -> None:
        if name in self.data_domains:
            raise ValueError(f"duplicate_data_domain:{name}")
        self.data_domains[name] = DataDomain(export, clear, usage)

    def context(self, request: Request) -> Context:
        same_origin(request)
        token = request.cookies.get(COOKIE)
        if not token:
            raise PlatformError("authentication_required", 401)
        timestamp = now()
        activity_cutoff = (timestamp - SESSION_ACTIVITY_INTERVAL).isoformat()
        with self.store.connection() as db:
            row = db.execute(
                """SELECT s.id,s.user_id,s.household_id,s.last_seen_at,m.role FROM p_sessions s
                JOIN p_users u ON u.id=s.user_id AND u.deleted_at IS NULL
                JOIN p_memberships m ON m.user_id=s.user_id AND m.household_id=s.household_id
                WHERE s.token_hash=? AND s.revoked_at IS NULL AND s.expires_at>?""",
                (token_hash(token), timestamp.isoformat()),
            ).fetchone()
        if row is None:
            raise PlatformError("authentication_required", 401)
        if row["last_seen_at"] <= activity_cutoff:
            with self.store.connection(write=True) as db:
                db.execute(
                    """UPDATE p_sessions SET last_seen_at=? WHERE id=?
                    AND last_seen_at<=? AND revoked_at IS NULL AND expires_at>?""",
                    (
                        timestamp.isoformat(),
                        row["id"],
                        activity_cutoff,
                        timestamp.isoformat(),
                    ),
                )
        return Context(row["user_id"], row["household_id"], row["role"], row["id"])

    def snapshot(self, context: Context) -> dict:
        with self.store.connection() as db:
            user = db.execute(
                "SELECT * FROM p_users WHERE id=?", (context.user_id,)
            ).fetchone()
            home = db.execute(
                "SELECT h.*,m.role FROM p_households h JOIN p_memberships m ON h.id=m.household_id WHERE h.id=? AND m.user_id=?",
                (context.household_id, context.user_id),
            ).fetchone()
            prefs = db.execute(
                "SELECT document FROM p_preferences WHERE user_id=?", (context.user_id,)
            ).fetchone()
            session = db.execute(
                "SELECT id,created_at,expires_at FROM p_sessions WHERE id=? AND user_id=?",
                (context.session_id, context.user_id),
            ).fetchone()
        return {
            "user": profile(user),
            "household": household(home),
            "preferences": json.loads(prefs[0]),
            "session": dict(session),
            "local_only": True,
            "supported_currencies": list(CURRENCY_DIGITS),
        }

    def login(self, request: Request, response: Response, command: Login) -> dict:
        same_origin(request)
        timestamp = now()
        with self.store.connection(write=True) as db:
            user = db.execute(
                "SELECT * FROM p_users WHERE id=? AND deleted_at IS NULL",
                (command.user_id,),
            ).fetchone()
            if user is None or not password_matches(
                command.password, user["password_hash"]
            ):
                raise PlatformError("invalid_credentials", 401)
            memberships = db.execute(
                "SELECT * FROM p_memberships WHERE user_id=? ORDER BY household_id",
                (command.user_id,),
            ).fetchall()
            selected = next(
                (
                    m
                    for m in memberships
                    if command.household_id is None
                    or m["household_id"] == command.household_id
                ),
                None,
            )
            if selected is None:
                raise PlatformError("household_access_denied", 403)
            token = secrets.token_urlsafe(32)
            session_id = identifier("session")
            expires = timestamp + SESSION_AGE
            old_cookie = request.cookies.get(COOKIE)
            if old_cookie:
                db.execute(
                    "UPDATE p_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
                    (timestamp.isoformat(), token_hash(old_cookie)),
                )
            db.execute(
                "INSERT INTO p_sessions VALUES (?,?,?,?,?,?,?,NULL)",
                (
                    session_id,
                    token_hash(token),
                    user["id"],
                    selected["household_id"],
                    timestamp.isoformat(),
                    expires.isoformat(),
                    timestamp.isoformat(),
                ),
            )
        response.set_cookie(
            COOKIE,
            token,
            max_age=int(SESSION_AGE.total_seconds()),
            httponly=True,
            samesite="strict",
            secure=request.url.scheme == "https",
            path="/",
        )
        return self.snapshot(
            Context(user["id"], selected["household_id"], selected["role"], session_id)
        )

    def active_memories(self, context: Context) -> list[dict]:
        with self.store.connection() as connection:
            db = ExportReader(
                connection,
                ReadBudget(
                    MAX_MEMORY_CONTEXT_ROWS,
                    MAX_MEMORY_CONTEXT_BYTES,
                    "memory_context_too_large",
                ),
            )
            return [
                dict(row)
                for row in db.execute(
                    """SELECT m.id,m.content,m.created_at,m.updated_at
                FROM p_memories m JOIN p_memory_settings s ON s.user_id=m.user_id AND s.household_id=m.household_id
                WHERE m.user_id=? AND m.household_id=? AND s.enabled=1 ORDER BY m.created_at,m.id LIMIT ?""",
                    (context.user_id, context.household_id, MAX_MEMORY_CONTEXT_ROWS + 1),
                )
            ]


def initialize(store: Store) -> None:
    Identity(store).initialize()


def get_identity(request: Request) -> Identity:
    return request.app.state.identity


router = APIRouter(prefix="/api/platform")


@router.get("/demo/personas")
def personas(identity: Annotated[Identity, Depends(get_identity)]):
    with identity.store.connection() as db:
        items = []
        for user in db.execute(
            "SELECT id,display_name FROM p_users WHERE fixture=1 AND deleted_at IS NULL ORDER BY id"
        ):
            homes = [
                dict(row)
                for row in db.execute(
                    "SELECT h.id,h.name,m.role FROM p_households h JOIN p_memberships m ON m.household_id=h.id WHERE m.user_id=? ORDER BY h.id",
                    (user["id"],),
                )
            ]
            if homes:
                items.append(
                    {
                        "user_id": user["id"],
                        "display_name": user["display_name"],
                        "households": homes,
                    }
                )
    return {"items": items, "default_password": DEMO_PASSWORD, "local_only": True}


@router.post("/session/login")
def login(
    command: Login,
    request: Request,
    response: Response,
    identity: Annotated[Identity, Depends(get_identity)],
):
    return identity.login(request, response, command)


@router.get("/session")
def session(
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    return identity.snapshot(context)


@router.post("/session/logout")
def logout(
    request: Request,
    response: Response,
    identity: Annotated[Identity, Depends(get_identity)],
):
    same_origin(request)
    token = request.cookies.get(COOKIE)
    if token:
        with identity.store.connection(write=True) as db:
            db.execute(
                "UPDATE p_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
                (now().isoformat(), token_hash(token)),
            )
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="strict")
    return {"logged_out": True}


@router.get("/households")
def households(
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    with identity.store.connection() as db:
        items = [
            household(row)
            for row in db.execute(
                "SELECT h.*,m.role FROM p_households h JOIN p_memberships m ON m.household_id=h.id WHERE m.user_id=? ORDER BY h.id",
                (context.user_id,),
            )
        ]
    return {"items": items}


@router.post("/households/switch")
def switch_household(
    command: HouseholdSwitch,
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    with identity.store.connection(write=True) as db:
        member = db.execute(
            "SELECT role FROM p_memberships WHERE household_id=? AND user_id=?",
            (command.household_id, context.user_id),
        ).fetchone()
        if not member:
            raise PlatformError("household_access_denied", 403)
        db.execute(
            "UPDATE p_sessions SET household_id=? WHERE id=? AND user_id=?",
            (command.household_id, context.session_id, context.user_id),
        )
    return identity.snapshot(
        Context(context.user_id, command.household_id, member[0], context.session_id)
    )


@router.patch("/household")
def patch_household(
    command: HouseholdPatch,
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    require_owner(context)
    changes = command.model_dump(exclude_unset=True)
    if any(value is None for key, value in changes.items() if key != "currency_override"):
        raise PlatformError("invalid_household")
    with identity.store.connection(write=True) as db:
        for key, value in changes.items():
            db.execute(
                f"UPDATE p_households SET {key}=? WHERE id=?",
                (value, context.household_id),
            )
        return household(
            db.execute(
                "SELECT * FROM p_households WHERE id=?", (context.household_id,)
            ).fetchone()
        )


@router.get("/household/members")
def members(
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    with identity.store.connection() as db:
        return {
            "items": [
                dict(row)
                for row in db.execute(
                    "SELECT u.id AS user_id,u.display_name,u.preferred_name,u.avatar_color,m.role FROM p_users u JOIN p_memberships m ON m.user_id=u.id WHERE m.household_id=? AND u.deleted_at IS NULL ORDER BY u.id",
                    (context.household_id,),
                )
            ]
        }


@router.post("/household/members", status_code=201)
def add_member(
    command: LocalMember,
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    require_owner(context)
    user_id = identifier("user")
    with identity.store.connection(write=True) as db:
        identity._create_user(
            db, user_id, command.display_name, command.password, now().isoformat()
        )
        db.execute(
            "INSERT INTO p_memberships VALUES (?,?,?)",
            (context.household_id, user_id, command.role),
        )
    return {
        "user_id": user_id,
        "display_name": command.display_name,
        "role": command.role,
        "local_only": True,
    }


def protect_last_owner(db, household_id: str, user_id: str) -> None:
    member = db.execute(
        "SELECT role FROM p_memberships WHERE household_id=? AND user_id=?",
        (household_id, user_id),
    ).fetchone()
    if member is None:
        raise PlatformError("member_not_found", 404)
    if (
        member[0] == "owner"
        and db.execute(
            "SELECT COUNT(*) FROM p_memberships WHERE household_id=? AND role='owner'",
            (household_id,),
        ).fetchone()[0]
        == 1
    ):
        raise PlatformError("last_owner_required", 409)


def clear_member_personal_data(db, household_id: str, user_id: str) -> None:
    db.execute(
        "DELETE FROM p_memories WHERE household_id=? AND user_id=?",
        (household_id, user_id),
    )
    db.execute(
        "DELETE FROM p_memory_settings WHERE household_id=? AND user_id=?",
        (household_id, user_id),
    )
    db.execute(
        "DELETE FROM p_local_feedback WHERE household_id=? AND user_id=?",
        (household_id, user_id),
    )


def delete_local_identity(db, user_id: str) -> None:
    """Remove personal identity data, retaining an inactive foreign-key anchor."""
    db.execute("DELETE FROM p_memories WHERE user_id=?", (user_id,))
    db.execute("DELETE FROM p_memory_settings WHERE user_id=?", (user_id,))
    db.execute("DELETE FROM p_local_feedback WHERE user_id=?", (user_id,))
    db.execute("DELETE FROM p_preferences WHERE user_id=?", (user_id,))
    db.execute("DELETE FROM p_memberships WHERE user_id=?", (user_id,))
    db.execute("DELETE FROM p_sessions WHERE user_id=?", (user_id,))
    db.execute(
        "UPDATE p_users SET display_name='Deleted local user',preferred_name=NULL,avatar_color='forest',password_hash='',deleted_at=? WHERE id=?",
        (now().isoformat(), user_id),
    )


@router.patch("/household/members/{user_id}")
def change_member(
    user_id: str,
    command: MemberRole,
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    require_owner(context)
    with identity.store.connection(write=True) as db:
        if command.role != "owner":
            protect_last_owner(db, context.household_id, user_id)
        changed = db.execute(
            "UPDATE p_memberships SET role=? WHERE household_id=? AND user_id=?",
            (command.role, context.household_id, user_id),
        ).rowcount
        if not changed:
            raise PlatformError("member_not_found", 404)
    return {"user_id": user_id, "role": command.role}


@router.delete("/household/members/{user_id}")
def remove_member(
    user_id: str,
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    require_owner(context)
    with identity.store.connection(write=True) as db:
        protect_last_owner(db, context.household_id, user_id)
        db.execute(
            "DELETE FROM p_memberships WHERE household_id=? AND user_id=?",
            (context.household_id, user_id),
        )
        remaining = db.execute(
            "SELECT 1 FROM p_memberships WHERE user_id=? LIMIT 1", (user_id,)
        ).fetchone()
        if remaining:
            clear_member_personal_data(db, context.household_id, user_id)
            db.execute(
                "DELETE FROM p_sessions WHERE household_id=? AND user_id=?",
                (context.household_id, user_id),
            )
        else:
            delete_local_identity(db, user_id)
    return {
        "removed": True,
        "local_account_deleted": remaining is None,
        "personal_household_data_deleted": True,
        "shared_household_data_preserved": True,
    }


@router.get("/settings/sessions")
def sessions(
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    with identity.store.connection() as db:
        items = [
            {**dict(row), "current": row["id"] == context.session_id}
            for row in db.execute(
                "SELECT id,created_at,expires_at,last_seen_at FROM p_sessions WHERE user_id=? AND revoked_at IS NULL AND expires_at>? ORDER BY created_at DESC",
                (context.user_id, now().isoformat()),
            )
        ]
    return {"items": items}


@router.post("/settings/sessions/revoke")
def revoke_sessions(
    command: SessionRevoke,
    response: Response,
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    with identity.store.connection(write=True) as db:
        count = db.execute(
            "UPDATE p_sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL AND expires_at>? AND (?='all' OR id!=?)",
            (
                now().isoformat(),
                context.user_id,
                now().isoformat(),
                command.scope,
                context.session_id,
            ),
        ).rowcount
    if command.scope == "all":
        response.delete_cookie(COOKIE, path="/")
    return {"revoked": count, "logged_out": command.scope == "all"}


@router.delete("/settings/sessions/{session_id}")
def revoke_session(
    session_id: str,
    response: Response,
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    with identity.store.connection(write=True) as db:
        if not db.execute(
            "SELECT 1 FROM p_sessions WHERE id=? AND user_id=?",
            (session_id, context.user_id),
        ).fetchone():
            raise PlatformError("session_not_found", 404)
        db.execute(
            "UPDATE p_sessions SET revoked_at=COALESCE(revoked_at,?) WHERE id=? AND user_id=?",
            (now().isoformat(), session_id, context.user_id),
        )
    if session_id == context.session_id:
        response.delete_cookie(COOKIE, path="/")
    return {"revoked": True, "logged_out": session_id == context.session_id}


@router.post("/settings/password")
def change_password(
    command: PasswordChange,
    response: Response,
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    with identity.store.connection(write=True) as db:
        saved = db.execute(
            "SELECT password_hash FROM p_users WHERE id=?", (context.user_id,)
        ).fetchone()[0]
        if not password_matches(command.current_password, saved):
            raise PlatformError("invalid_credentials", 401)
        db.execute(
            "UPDATE p_users SET password_hash=? WHERE id=?",
            (password_hash(command.new_password), context.user_id),
        )
        db.execute(
            "UPDATE p_sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL",
            (now().isoformat(), context.user_id),
        )
    response.delete_cookie(COOKIE, path="/")
    return {"changed": True, "logged_out": True}


# Settings routes share this identity instance and its explicit domain callbacks.
from .settings import router as settings_router  # noqa: E402

router.include_router(settings_router)
