"""Is this process's credential key the deployment's current key? (Lane 6, B1)

``SecretBox`` has one key and no key id, so a credential that does not open
looks the same whether it is truly dead (sealed under a key rotated away) or
this process simply holds the wrong key, or none. Account deletion may give up
on a credential only in the first case: a wrong key must never drop a live
Plaid, Gmail or Apple token.

The one check, used for every provider and for Apple before #802's
``discard_unreadable``: the key is verified when it opens the newest
credential anyone else stored (a Plaid or Gmail connection, or an Apple
refresh token). New credentials are always sealed with the deployment's
current key, so an old rotated-away key and a misconfigured one both fail, and
the person's own credentials never count as evidence. With nothing else stored
the key is unproven, and nothing is dropped: the step stays pending and the
operator decides (``force_complete_step``).
"""

from __future__ import annotations

from typing import Any, Literal

from argus.domain.ingestion.secrets import SecretBox, SecretUnreadable

KeyCheck = Literal["verified", "mismatch", "unproven", "unavailable"]

_NEWEST = """
    select source, id::text, secret_ciphertext, updated_at
      from public.financial_source_connections
     where secret_ciphertext is not null and source in ('plaid', 'gmail')
       and user_id <> %(user)s
    union all
    select 'apple_sign_in', user_id::text, secret_ciphertext, updated_at
      from public.apple_sign_in_credentials
     where user_id <> %(user)s
    order by 4 desc
    limit 1
"""


def check_current_key(
    connection: Any, box: SecretBox | None, *, user_id: str
) -> KeyCheck:
    if box is None:
        return "unavailable"
    row = connection.execute(_NEWEST, {"user": user_id}).fetchone()
    if row is None:
        return "unproven"
    source, ref, envelope, _ = row
    try:
        box.open(bytes(envelope), source=str(source), connection_id=str(ref))
    except SecretUnreadable:
        return "mismatch"
    return "verified"
