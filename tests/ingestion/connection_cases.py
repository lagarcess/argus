"""Behavior both connection repositories must share.

Imported by the in-memory module and the real-Postgres module so the twin and
the database are held to one specification, not two copies of it.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from argus.domain.ingestion.connections import (
    ConnectionNotFound,
    DuplicateConnection,
)

NOW = datetime(2026, 10, 1, 13, 0, tzinfo=timezone.utc)


def make(repo, user, ref="item-1", source="plaid", secret=b"sealed"):
    return repo.create(
        user_id=user,
        source=source,
        external_ref=ref,
        label="Chase",
        now=NOW,
        secret=secret,
    )


def test_one_live_connection_per_reference_and_reconnect_after_disconnect(repo, users):
    first = make(repo, users["owner"])
    with pytest.raises(DuplicateConnection) as caught:
        make(repo, users["owner"])
    assert caught.value.existing_id == first.id
    # Another person may connect the same provider reference independently.
    make(repo, users["other"])
    repo.disconnect(user_id=users["owner"], connection_id=first.id, now=NOW)
    again = make(repo, users["owner"])
    assert again.id != first.id and again.status == "active"


def test_reads_are_owner_scoped(repo, users):
    row = make(repo, users["owner"])
    assert [c.id for c in repo.list(user_id=users["owner"])] == [row.id]
    assert repo.list(user_id=users["other"]) == []
    with pytest.raises(ConnectionNotFound):
        repo.get(user_id=users["other"], connection_id=row.id)
    with pytest.raises(ConnectionNotFound):
        repo.get(user_id=users["owner"], connection_id="not-a-uuid")
    with pytest.raises(ConnectionNotFound):
        repo.disconnect(user_id=users["other"], connection_id=row.id, now=NOW)
    assert repo.get(user_id=users["owner"], connection_id=row.id).status == "active"


def test_webhook_lookup_finds_only_live_connections(repo, users):
    row = make(repo, users["owner"], ref="item-hook")
    assert [c.id for c in repo.find_live(source="plaid", external_ref="item-hook")] == [
        row.id
    ]
    assert repo.find_live(source="gmail", external_ref="item-hook") == []
    repo.disconnect(user_id=users["owner"], connection_id=row.id, now=NOW)
    assert repo.find_live(source="plaid", external_ref="item-hook") == []


def test_lease_is_exclusive_until_released_or_expired(repo, users):
    row = make(repo, users["owner"])
    assert repo.lease(connection_id=row.id, holder="a", now=NOW)
    assert not repo.lease(connection_id=row.id, holder="b", now=NOW)
    assert repo.lease(connection_id=row.id, holder="a", now=NOW)  # renew
    later = NOW + timedelta(minutes=6)
    assert repo.lease(connection_id=row.id, holder="b", now=later)  # expired
    repo.release(connection_id=row.id, holder="a")  # stale holder: no effect
    assert not repo.lease(connection_id=row.id, holder="c", now=later)
    repo.release(connection_id=row.id, holder="b")
    assert repo.lease(connection_id=row.id, holder="c", now=later)


def test_concurrent_lease_has_one_winner(repo, users):
    row = make(repo, users["owner"])
    with ThreadPoolExecutor(max_workers=8) as pool:
        won = list(
            pool.map(
                lambda i: repo.lease(connection_id=row.id, holder=f"h{i}", now=NOW),
                range(8),
            )
        )
    assert won.count(True) == 1


def test_cursor_advances_only_by_compare_and_set_under_the_lease(repo, users):
    row = make(repo, users["owner"])
    assert repo.lease(connection_id=row.id, holder="a", now=NOW)
    assert not repo.record_success(
        connection_id=row.id, holder="b", expected_cursor=None, cursor="c1", now=NOW
    )
    assert repo.record_success(
        connection_id=row.id, holder="a", expected_cursor=None, cursor="c1", now=NOW
    )
    # A stale sync that started from the old cursor cannot rewind it.
    assert not repo.record_success(
        connection_id=row.id, holder="a", expected_cursor=None, cursor="c0", now=NOW
    )
    current = repo.get(user_id=users["owner"], connection_id=row.id)
    assert current.cursor == "c1" and current.last_success_at == NOW


def test_failure_keeps_old_freshness_and_cursor(repo, users):
    row = make(repo, users["owner"])
    repo.lease(connection_id=row.id, holder="a", now=NOW)
    repo.record_success(
        connection_id=row.id, holder="a", expected_cursor=None, cursor="c1", now=NOW
    )
    later = NOW + timedelta(hours=3)
    failed = repo.record_failure(
        connection_id=row.id, code="item_login_required", status="needs_reauth", now=later
    )
    assert failed.status == "needs_reauth"
    assert failed.last_success_at == NOW and failed.cursor == "c1"
    assert failed.last_attempt_at == later
    assert failed.last_error_code == "item_login_required"
    # Re-authenticating stores the new credential and clears the failure.
    fixed = repo.set_secret(
        connection_id=row.id, secret=b"new", status="active", now=later
    )
    assert fixed.status == "active" and fixed.last_error_code is None
    assert fixed.secret == b"new" and fixed.cursor == "c1"


def test_disconnect_clears_credential_cursor_and_lease_and_is_idempotent(repo, users):
    row = make(repo, users["owner"])
    repo.lease(connection_id=row.id, holder="a", now=NOW)
    repo.record_success(
        connection_id=row.id, holder="a", expected_cursor=None, cursor="c1", now=NOW
    )
    ended = repo.disconnect(user_id=users["owner"], connection_id=row.id, now=NOW)
    assert ended.status == "disconnected" and ended.disconnected_at == NOW
    assert ended.secret is None and ended.cursor is None and ended.lease_holder is None
    assert ended.last_success_at == NOW  # history of freshness is kept
    again = repo.disconnect(user_id=users["owner"], connection_id=row.id, now=NOW)
    assert again.version == ended.version
    # A disconnected connection cannot sync or take a credential again.
    assert not repo.lease(connection_id=row.id, holder="a", now=NOW)
    with pytest.raises(ConnectionNotFound):
        repo.set_secret(connection_id=row.id, secret=b"x", status="active", now=NOW)
    with pytest.raises(ConnectionNotFound):
        repo.record_failure(connection_id=row.id, code="x", status="error", now=NOW)


def test_attention_survives_successful_syncs_until_reauthorization(repo, users):
    row = make(repo, users["owner"])
    flagged = repo.flag_attention(
        connection_id=row.id, code="plaid_pending_expiration", now=NOW
    )
    assert flagged.attention_code == "plaid_pending_expiration"
    assert repo.lease(connection_id=row.id, holder="a", now=NOW)
    assert repo.record_success(
        connection_id=row.id, holder="a", expected_cursor=None, cursor="c1", now=NOW
    )
    synced = repo.get(user_id=users["owner"], connection_id=row.id)
    assert synced.status == "active"
    assert synced.attention_code == "plaid_pending_expiration"
    renewed = repo.set_secret(connection_id=row.id, secret=b"n", status="active", now=NOW)
    assert renewed.attention_code is None and renewed.attention_at is None
    repo.flag_attention(connection_id=row.id, code="plaid_pending_expiration", now=NOW)
    ended = repo.disconnect(user_id=users["owner"], connection_id=row.id, now=NOW)
    assert ended.attention_code is None
    with pytest.raises(ConnectionNotFound):
        repo.flag_attention(connection_id=row.id, code="x", now=NOW)
