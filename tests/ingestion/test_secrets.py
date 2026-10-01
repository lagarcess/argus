"""Provider credentials sealed at rest and bound to their connection."""

import base64
import os

import pytest
from argus.domain.ingestion.secrets import (
    KEY_ENV,
    SecretBox,
    SecretBoxUnavailable,
    SecretUnreadable,
)


def box() -> SecretBox:
    return SecretBox(os.urandom(32))


def test_round_trip_and_no_plaintext_in_envelope():
    sealer = box()
    sealed = sealer.seal("access-sandbox-abc", source="plaid", connection_id="c1")
    assert b"access-sandbox-abc" not in sealed
    assert sealer.open(sealed, source="plaid", connection_id="c1") == "access-sandbox-abc"


def test_envelope_copied_to_another_connection_does_not_open():
    sealer = box()
    sealed = sealer.seal("token", source="plaid", connection_id="c1")
    with pytest.raises(SecretUnreadable):
        sealer.open(sealed, source="plaid", connection_id="c2")
    with pytest.raises(SecretUnreadable):
        sealer.open(sealed, source="gmail", connection_id="c1")
    with pytest.raises(SecretUnreadable):
        box().open(sealed, source="plaid", connection_id="c1")
    with pytest.raises(SecretUnreadable):
        sealer.open(b"\x02" + sealed[1:], source="plaid", connection_id="c1")


def test_key_comes_from_env_and_absence_keeps_connectors_off(monkeypatch):
    monkeypatch.delenv(KEY_ENV, raising=False)
    with pytest.raises(SecretBoxUnavailable):
        SecretBox.from_env()
    monkeypatch.setenv(KEY_ENV, "not base64!!")
    with pytest.raises(SecretBoxUnavailable):
        SecretBox.from_env()
    monkeypatch.setenv(KEY_ENV, base64.urlsafe_b64encode(b"short").decode())
    with pytest.raises(SecretBoxUnavailable):
        SecretBox.from_env()
    monkeypatch.setenv(
        KEY_ENV, base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")
    )
    assert SecretBox.from_env().seal("x", source="gmail", connection_id="c")
