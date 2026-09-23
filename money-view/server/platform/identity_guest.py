"""Bounded local guest workspace policy; no provider identity or email claims."""

from datetime import timedelta

GUEST_AGE = timedelta(hours=24)
MAX_GUEST_WORKSPACES = 1000
SCHEMA = """
CREATE TABLE IF NOT EXISTS p_guest_workspaces (
 user_id TEXT PRIMARY KEY REFERENCES p_users(id),
 household_id TEXT NOT NULL REFERENCES p_households(id),
 mode TEXT NOT NULL CHECK(mode IN ('demo','empty')),
 created_at TEXT NOT NULL, expires_at TEXT NOT NULL, claimed_at TEXT
);
"""


def guest_status(db, user_id):
    row = db.execute(
        "SELECT mode,expires_at,claimed_at FROM p_guest_workspaces WHERE user_id=?",
        (user_id,),
    ).fetchone()
    is_guest = row is not None and row["claimed_at"] is None
    return {
        "is_guest": is_guest,
        "expires_at": row["expires_at"] if is_guest else None,
        "mode": row["mode"] if is_guest else None,
        "can_claim": is_guest,
        "local_only": True,
    }
