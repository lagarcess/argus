"""Google OAuth web-server flow for one Gmail mailbox.

``authorize`` returns Google's consent URL: ``gmail.readonly`` only, offline
access (a refresh token), ``prompt=consent``, incremental authorization, PKCE
S256 and a sealed single-use ``state`` bound to the person (see ``state``).

``callback`` redeems the state, exchanges the code with the PKCE verifier,
refuses a grant without ``gmail.readonly`` (granular consent lets a person
untick it), reads the mailbox address with ``users.getProfile`` and then:

- creates the connection (``external_ref`` = keyed digest of the address,
  ``label`` = masked address, refresh token sealed under the new id); or
- for a mailbox this person already connected, replaces that live
  connection's credential (reconnect), keeping its cursor and freshness; or
- for a mailbox another person connected, refuses without revoking anything,
  because revoking would end that person's grant too.

The access token from the exchange is used for the profile read and dropped.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode

from loguru import logger

from argus.domain.ingestion.connections import DuplicateConnection, SourceConnection
from argus.domain.ingestion.gmail.client import GmailClient, GmailError
from argus.domain.ingestion.gmail.config import (
    AUTHORIZE_URL,
    SCOPE,
    GmailConfig,
    mailbox_ref,
    masked_label,
)
from argus.domain.ingestion.gmail.senders import SenderRepository, SenderRule
from argus.domain.ingestion.gmail.state import OAuthStates
from argus.domain.ingestion.hub import IngestionHub
from argus.domain.ingestion.secrets import SecretBoxUnavailable


class ScopeNotGranted(RuntimeError):
    """The person did not allow reading Gmail; nothing was stored."""


class RefreshTokenMissing(RuntimeError):
    """Google issued no refresh token; nothing was stored."""


class MailboxOwnedElsewhere(RuntimeError):
    """This mailbox is connected by a different person."""


@dataclass(frozen=True)
class AuthorizationRequest:
    authorization_url: str
    expires_at: datetime


@dataclass(frozen=True)
class ConnectResult:
    connection: SourceConnection
    created: bool
    senders: list[SenderRule]


class GmailOAuth:
    def __init__(
        self,
        hub: IngestionHub,
        client: GmailClient,
        config: GmailConfig,
        states: OAuthStates,
        senders: SenderRepository,
        *,
        ref_key: bytes,
    ) -> None:
        self.hub = hub
        self.client = client
        self.config = config
        self.states = states
        self.senders = senders
        self._ref_key = ref_key

    def authorize(self, *, user_id: str) -> AuthorizationRequest:
        pending = self.states.issue(user_id=user_id)
        query = urlencode(
            {
                "client_id": self.config.client_id,
                "redirect_uri": self.config.redirect_uri,
                "response_type": "code",
                "scope": SCOPE,
                "access_type": "offline",
                "prompt": "consent",
                "include_granted_scopes": "true",
                "state": pending.state,
                "code_challenge": pending.code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return AuthorizationRequest(f"{AUTHORIZE_URL}?{query}", pending.expires_at)

    def callback(
        self,
        *,
        user_id: str,
        code: str,
        state: str,
        senders: tuple[str, ...] | None,
    ) -> ConnectResult:
        box = self.hub.box
        if box is None:
            raise SecretBoxUnavailable("credential sealing is not configured")
        verifier = self.states.redeem(user_id=user_id, state=state)
        grant = self.client.exchange_code(code=code, verifier=verifier)
        if SCOPE not in grant.scopes:
            # Partial consent: the token cannot read mail. With incremental
            # authorization an earlier gmail.readonly grant would be listed
            # here, so none exists and revoking cannot end a live connection.
            self._discard(grant.refresh_token or grant.access_token)
            raise ScopeNotGranted()
        if grant.refresh_token is None:
            # Not revoked: the grant may back this person's live connection.
            # The unused access token expires on its own within the hour.
            raise RefreshTokenMissing()
        profile = self.client.profile(grant.access_token)
        ref = mailbox_ref(profile.email, self._ref_key)
        live = self.hub.connections.find_live(source="gmail", external_ref=ref)
        mine = [row for row in live if row.user_id == user_id]
        if live and not mine:
            raise MailboxOwnedElsewhere()
        now = self.hub.clock()
        if mine:
            row = self._reseal(mine[0], grant.refresh_token)
            created = False
        else:
            connection_id = str(uuid.uuid4())
            try:
                row = self.hub.connections.create(
                    user_id=user_id,
                    source="gmail",
                    external_ref=ref,
                    label=masked_label(profile.email),
                    now=now,
                    secret=box.seal(
                        grant.refresh_token, source="gmail", connection_id=connection_id
                    ),
                    connection_id=connection_id,
                )
                created = True
            except DuplicateConnection as duplicate:
                # A concurrent callback for the same mailbox won the insert.
                existing = self.hub.connections.get(
                    user_id=user_id, connection_id=duplicate.existing_id
                )
                row = self._reseal(existing, grant.refresh_token)
                created = False
        if senders is not None:
            rules = self.senders.replace(
                user_id=user_id, connection_id=row.id, senders=senders, now=now
            )
        else:
            rules = self.senders.list(connection_id=row.id)
        return ConnectResult(row, created, rules)

    def _reseal(self, row: SourceConnection, refresh_token: str) -> SourceConnection:
        """Reconnect: the newest grant replaces the stored one. The old token is
        not revoked: Google revokes the whole grant, which now includes the new
        token too."""

        assert self.hub.box is not None
        return self.hub.connections.set_secret(
            connection_id=row.id,
            secret=self.hub.box.seal(refresh_token, source="gmail", connection_id=row.id),
            status="active",
            now=self.hub.clock(),
        )

    def _discard(self, token: str) -> None:
        try:
            self.client.revoke(token)
        except GmailError as exc:
            logger.info("Unused Google grant could not be revoked", reason=exc.reason)
