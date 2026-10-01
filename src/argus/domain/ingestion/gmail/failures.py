"""What a Google failure means for the connection the person sees.

- ``needs_reauth``: the person can fix it by authorizing again: the refresh
  token was revoked or expired (``invalid_grant``), the access token was
  refused (401), or the grant lacks ``gmail.readonly`` (403 insufficient
  scope) or Gmail refused access for another account-level reason.
- ``error``: Google is unavailable or rate limiting after bounded retries
  (``gmail_unavailable``), or our own OAuth client is misconfigured.

``last_success_at`` and the cursor are never touched by a failure. Stored
codes are fixed ``gmail_*`` strings, never provider text.
"""

from __future__ import annotations

from dataclasses import dataclass

from argus.domain.ingestion.connections import ConnectionStatus
from argus.domain.ingestion.gmail.client import GmailError

TOKEN_REVOKED = "gmail_token_revoked"
SCOPE_MISSING = "gmail_scope_missing"
ACCESS_DENIED = "gmail_access_denied"
UNAVAILABLE = "gmail_unavailable"
CLIENT_INVALID = "gmail_oauth_client_invalid"
CREDENTIAL_UNAVAILABLE = "gmail_credential_unavailable"

_SCOPE_REASONS = frozenset(
    {"insufficientPermissions", "ACCESS_TOKEN_SCOPE_INSUFFICIENT", "insufficient_scope"}
)
_RATE_REASONS = frozenset(
    {"rateLimitExceeded", "userRateLimitExceeded", "quotaExceeded", "RATE_LIMIT_EXCEEDED"}
)


@dataclass(frozen=True)
class FailureMeaning:
    code: str
    status: ConnectionStatus


def meaning(error: GmailError) -> FailureMeaning:
    if "invalid_grant" in error.reasons:
        return FailureMeaning(TOKEN_REVOKED, "needs_reauth")
    if error.reasons & {"invalid_client", "unauthorized_client"}:
        return FailureMeaning(CLIENT_INVALID, "error")
    if error.status == 401:
        return FailureMeaning(TOKEN_REVOKED, "needs_reauth")
    if error.status == 403:
        if error.reasons & _SCOPE_REASONS:
            return FailureMeaning(SCOPE_MISSING, "needs_reauth")
        if error.reasons & _RATE_REASONS:
            return FailureMeaning(UNAVAILABLE, "error")
        return FailureMeaning(ACCESS_DENIED, "needs_reauth")
    return FailureMeaning(UNAVAILABLE, "error")
