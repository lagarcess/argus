"""Lane 6: account deletion revokes provider tokens from the captured ciphertext."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from argus.domain.ingestion.hub import IngestionHub
from argus.domain.ingestion.secrets import SecretBox


class _Adapter:
    def __init__(self, source: str, fail: bool = False) -> None:
        self.source = source
        self.fail = fail
        self.revoked: list[str | None] = []

    def revoke(self, connection, credential):  # noqa: ANN001
        self.revoked.append(credential)
        if self.fail:
            raise RuntimeError("provider down")

    def forget(self, connection):  # noqa: ANN001
        raise AssertionError("deletion never touches connection rows")


def _hub(*adapters):  # noqa: ANN002
    hub = IngestionHub(
        None,  # type: ignore[arg-type]
        box=SecretBox(secrets.token_bytes(32)),
        sink=None,
        clock=lambda: datetime(2026, 10, 3, tzinfo=UTC),
    )
    for adapter in adapters:
        hub.register(adapter)
    return hub


def test_gmail_and_plaid_tokens_are_opened_and_revoked():
    gmail, plaid = _Adapter("gmail"), _Adapter("plaid")
    hub = _hub(gmail, plaid)
    for adapter, token in ((gmail, "google-refresh"), (plaid, "access-sandbox")):
        envelope = hub.box.seal(token, source=adapter.source, connection_id="c-1")
        outcome = hub.revoke_for_deletion(
            source=adapter.source,
            connection_id="c-1",
            external_ref="x",
            envelope=envelope,
        )
        assert outcome == "revoked"
        assert adapter.revoked == [token]


def test_a_failed_or_unreadable_revoke_stays_pending():
    gmail = _Adapter("gmail", fail=True)
    hub = _hub(gmail)
    envelope = hub.box.seal("t", source="gmail", connection_id="c-1")
    assert (
        hub.revoke_for_deletion(
            source="gmail", connection_id="c-1", external_ref="x", envelope=envelope
        )
        == "failed"
    )
    # Sealed for another connection: does not open, so nothing is revoked.
    assert (
        _hub(_Adapter("gmail")).revoke_for_deletion(
            source="gmail", connection_id="c-2", external_ref="x", envelope=envelope
        )
        == "failed"
    )
    # A connector that is switched off cannot revoke: pending, not success.
    assert (
        _hub().revoke_for_deletion(
            source="plaid", connection_id="c-1", external_ref="x", envelope=b"\x01" * 40
        )
        == "failed"
    )
    assert (
        _hub().revoke_for_deletion(
            source="plaid", connection_id="c-1", external_ref="x", envelope=None
        )
        == "not_applicable"
    )
