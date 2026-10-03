"""Is this process's credential key the deployment's current key? (Lane 6, B1)

``SecretBox`` has one key and no key id, so a credential that does not open
looks the same whether it is truly dead (sealed under a key rotated away) or
this process simply holds the wrong key, or none. Account deletion may give up
on a credential only in the first case: a wrong key must never drop a live
Plaid, Gmail or Apple token.

The one check, used for every provider and for Apple before #802's
``discard_unreadable``: the key is verified for a credential when it opens the
credential anyone else most recently *sealed* (a Plaid or Gmail connection, or
an Apple refresh token), and that seal is not older than the credential being
given up. ``secret_sealed_at`` is stamped by the database only when the
ciphertext changes (migration 20261004090000, section 7), so status, attention
and lease updates never make an old-key row look current (Marcus re-check S1).
New credentials are always sealed with the deployment's current key, so an old
rotated-away key and a misconfigured one both fail, and the person's own
credentials never count as evidence. With no such evidence, or evidence older
than the credential, the key is unproven and nothing is dropped: the step stays
pending and the operator decides (``force_complete_step``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from argus.domain.ingestion.secrets import SecretBox, SecretUnreadable

KeyCheck = Literal["verified", "mismatch", "unproven", "unavailable"]

_NEWEST_SEAL = """
    select source, id::text, secret_ciphertext, secret_sealed_at
      from public.financial_source_connections
     where secret_ciphertext is not null and secret_sealed_at is not null
       and source in ('plaid', 'gmail') and user_id <> %(user)s
    union all
    select 'apple_sign_in', user_id::text, secret_ciphertext, secret_sealed_at
      from public.apple_sign_in_credentials
     where secret_sealed_at is not null and user_id <> %(user)s
    order by 4 desc
    limit 1
"""


def check_current_key(
    connection: Any,
    box: SecretBox | None,
    *,
    user_id: str,
    sealed_at: datetime | None,
) -> KeyCheck:
    """``sealed_at`` is when the credential about to be given up was sealed
    (null when it predates the seal stamp)."""

    if box is None:
        return "unavailable"
    row = connection.execute(_NEWEST_SEAL, {"user": user_id}).fetchone()
    if row is None:
        return "unproven"
    source, ref, envelope, evidence_sealed_at = row
    if sealed_at is not None and evidence_sealed_at < sealed_at:
        # The credential was sealed after the newest evidence: a key rotated
        # since then could have sealed it, so opening the evidence proves
        # nothing about it.
        return "unproven"
    try:
        box.open(bytes(envelope), source=str(source), connection_id=str(ref))
    except SecretUnreadable:
        return "mismatch"
    return "verified"
