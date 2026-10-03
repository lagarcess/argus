"""Invite codes, links and settings shared by household and beta invites.

A code is 8 Crockford base32 characters (about 40 bits), shown as XXXX-XXXX.
Only a hash is stored, beside the token hash. The token stays in the URL
fragment, so it never reaches a web server log.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass

CODE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
CODE_LENGTH = 8
UNIVERSAL_LINK_BASE = "https://cuadrao.ai/invite#"
LEGACY_HOUSEHOLD_LINK_BASE = "argus-household://invite#"
BETA_INVITE_QUOTA = 10
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_CONFUSABLE = str.maketrans({"O": "0", "I": "1", "L": "1", "U": "V"})


def new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def normalize_code(raw: str) -> str | None:
    """Uppercase, drop separators, fold look-alike letters. None if invalid."""
    value = "".join(ch for ch in raw.upper() if ch not in " -_\t").translate(_CONFUSABLE)
    if len(value) != CODE_LENGTH or any(ch not in CODE_ALPHABET for ch in value):
        return None
    return value


def format_code(code: str) -> str:
    return f"{code[:4]}-{code[4:]}"


def hash_code(code: str) -> str:
    return hashlib.sha256(f"argus-invite-code:v1:{code}".encode()).hexdigest()


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def _text(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


@dataclass(frozen=True)
class InviteSettings:
    universal_link_enabled: bool = False
    gate_enabled: bool = False
    waitlist_url: str | None = None
    testflight_url: str | None = None
    founder_user_id: str | None = None
    quota: int = BETA_INVITE_QUOTA

    @classmethod
    def from_env(cls) -> InviteSettings:
        return cls(
            universal_link_enabled=_flag("ARGUS_INVITE_UNIVERSAL_LINK_ENABLED"),
            gate_enabled=_flag("ARGUS_BETA_INVITE_GATE_ENABLED"),
            waitlist_url=_text("ARGUS_WAITLIST_URL"),
            testflight_url=_text("ARGUS_TESTFLIGHT_PUBLIC_URL"),
            founder_user_id=_text("ARGUS_INVITE_FOUNDER_USER_ID"),
        )

    def is_founder(self, user_id: str | None) -> bool:
        """Only a verified, non-empty subject can be the founder; null never is."""
        if not self.founder_user_id or not user_id:
            return False
        return self.founder_user_id.strip().lower() == str(user_id).strip().lower()


def invite_link(token: str, *, household: bool, settings: InviteSettings) -> str | None:
    """The share link. Off keeps today's household scheme; beta has no link yet."""
    if settings.universal_link_enabled:
        return UNIVERSAL_LINK_BASE + token
    return LEGACY_HOUSEHOLD_LINK_BASE + token if household else None


def unique_code(connection) -> tuple[str, str]:  # noqa: ANN001
    """A code whose hash is unused by every invite table."""
    for _ in range(8):
        code = new_code()
        digest = hash_code(code)
        taken = connection.execute(
            "select 1 from public.household_invitations where code_hash=%s"
            " union all select 1 from public.beta_invitations where code_hash=%s",
            (digest, digest),
        ).fetchone()
        if taken is None:
            return code, digest
    raise RuntimeError("Could not allocate a unique invite code.")
