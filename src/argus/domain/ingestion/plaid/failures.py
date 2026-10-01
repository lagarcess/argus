"""What a Plaid failure means for the connection the person sees.

Three outcomes, chosen from Plaid's structured ``error_type``/``error_code``:

- ``needs_reauth``: the person can fix it through Link update mode
  (``ITEM_LOGIN_REQUIRED``, consent expiring or about to disconnect).
- ``error``: the Item is gone or its permission was revoked; the person must
  disconnect and connect again.
- transient: Plaid, the institution or our own configuration is unavailable;
  the connection keeps its status and only records the failure code.

The stored code is ``plaid_<lowercased Plaid code>`` so the app can show an
actionable message; it never contains provider text.
"""

from __future__ import annotations

from dataclasses import dataclass

from argus.domain.ingestion.connections import ConnectionStatus

REAUTH_CODES = frozenset(
    {
        "ITEM_LOGIN_REQUIRED",
        "PENDING_EXPIRATION",
        "PENDING_DISCONNECT",
        "ITEM_LOCKED",
        "USER_SETUP_REQUIRED",
        "INVALID_CREDENTIALS",
        "INVALID_MFA",
        "ACCESS_NOT_GRANTED",
        "NO_ACCOUNTS",
    }
)
ENDED_CODES = frozenset(
    {
        "ITEM_NOT_FOUND",
        "INVALID_ACCESS_TOKEN",
        "USER_PERMISSION_REVOKED",
        "ITEM_NO_LONGER_AVAILABLE",
    }
)
MUTATION_DURING_PAGINATION = "TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION"


@dataclass(frozen=True)
class FailureMeaning:
    code: str
    # None keeps the connection's current status (transient failure).
    status: ConnectionStatus | None


def meaning(error_code: str) -> FailureMeaning:
    code = failure_code(error_code)
    if error_code in REAUTH_CODES:
        return FailureMeaning(code, "needs_reauth")
    if error_code in ENDED_CODES:
        return FailureMeaning(code, "error")
    return FailureMeaning(code, None)


def failure_code(error_code: str) -> str:
    cleaned = "".join(
        ch if ch.isascii() and (ch.isalnum() or ch == "_") else "_"
        for ch in error_code.lower()
    )
    return ("plaid_" + cleaned)[:64]
