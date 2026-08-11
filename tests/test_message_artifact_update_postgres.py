"""In-place card updates against real persistence.

``update_message_artifact`` is the primitive every non-turn confirmation
change writes through, and until this file it had only memory-store parity.
This proof runs the real Supabase gateway against the disposable local stack
(the guest-release-gates job exports the URL and keys, and the
``tests/test_*_postgres.py`` glob carries this file without a workflow
edit): the same row is rewritten in place, the transcript never grows, and
ownership is enforced by the update itself.

Set ``ARGUS_DISPOSABLE_DATABASE_URL`` plus ``ARGUS_LOCAL_SUPABASE_URL`` and
``ARGUS_LOCAL_SUPABASE_SERVICE_ROLE_KEY`` to run locally.
"""

from __future__ import annotations

import os
import uuid

import pytest

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()
LOCAL_URL = os.getenv("ARGUS_LOCAL_SUPABASE_URL", "").strip()
LOCAL_SERVICE_KEY = os.getenv("ARGUS_LOCAL_SUPABASE_SERVICE_ROLE_KEY", "").strip()

pytestmark = pytest.mark.skipif(
    not (DSN and LOCAL_URL and LOCAL_SERVICE_KEY),
    reason="disposable local Supabase is not configured",
)
psycopg = pytest.importorskip("psycopg")


def _connect():
    return psycopg.connect(DSN, autocommit=True)


def _seed_owner(connection) -> dict[str, str]:
    user_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())
    email = f"artifact-update-{user_id[:8]}@argus.local"
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into auth.users (id, email) values (%s, %s)",
            (user_id, email),
        )
        cursor.execute(
            "insert into public.profiles (id, email) values (%s, %s)",
            (user_id, email),
        )
        cursor.execute(
            "insert into public.conversations (id, user_id, title)"
            " values (%s, %s, 'artifact update proof')",
            (conversation_id, user_id),
        )
    return {"user_id": user_id, "conversation_id": conversation_id}


def _gateway():
    from argus.domain.supabase_gateway import SupabaseGateway

    from supabase import create_client

    return SupabaseGateway(client=create_client(LOCAL_URL, LOCAL_SERVICE_KEY))


def _message_count(connection, conversation_id: str) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            "select count(*) from public.messages where conversation_id = %s",
            (conversation_id,),
        )
        return int(cursor.fetchone()[0])


def test_update_message_artifact_rewrites_the_same_row() -> None:
    with _connect() as connection:
        owner = _seed_owner(connection)
        gateway = _gateway()
        created = gateway.create_message(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            role="assistant",
            content="Buy and hold NFLX",
            metadata={
                "conversation_mode": "confirm",
                "confirmation_payload": {"strategy": {"capital_amount": 10000}},
            },
        )
        assert _message_count(connection, owner["conversation_id"]) == 1

        updated = gateway.update_message_artifact(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            message_id=created.id,
            content="Buy and hold NFLX, edited",
            metadata={
                "conversation_mode": "confirm",
                "confirmation_payload": {"strategy": {"capital_amount": 25000}},
            },
            expected_source_metadata=created.metadata,
            expected_latest_message_id=created.id,
        )
        assert updated.id == created.id, "in place means the same row"
        assert updated.content == "Buy and hold NFLX, edited"
        assert (
            updated.metadata["confirmation_payload"]["strategy"]["capital_amount"]
            == 25000
        )
        assert (
            _message_count(connection, owner["conversation_id"]) == 1
        ), "a non-turn change never grows the transcript, on real Postgres too"

        stored = gateway.get_message(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            message_id=created.id,
        )
        assert stored is not None
        assert (
            stored.metadata["confirmation_payload"]["strategy"]["capital_amount"] == 25000
        ), "the durable record is the edited card, not a copy"


def test_update_message_artifact_enforces_ownership() -> None:
    with _connect() as connection:
        owner = _seed_owner(connection)
        stranger = _seed_owner(connection)
        gateway = _gateway()
        created = gateway.create_message(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            role="assistant",
            content="owned card",
            metadata={"conversation_mode": "confirm"},
        )
        with pytest.raises(ValueError):
            gateway.update_message_artifact(
                user_id=stranger["user_id"],
                conversation_id=owner["conversation_id"],
                message_id=created.id,
                content="hijacked",
                metadata={},
                expected_source_metadata=None,
                expected_latest_message_id=None,
            )
        stored = gateway.get_message(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            message_id=created.id,
        )
        assert stored is not None and stored.content == "owned card"


def test_update_message_artifact_conflicts_on_a_stale_read() -> None:
    """The write is conditional on the metadata the caller read: a
    concurrent change surfaces as a conflict on real Postgres, and the
    winner's row is untouched."""
    from argus.domain.supabase_conversation_messages import (
        StaleMessageArtifactError,
    )

    with _connect() as connection:
        owner = _seed_owner(connection)
        gateway = _gateway()
        created = gateway.create_message(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            role="assistant",
            content="Buy and hold NFLX",
            metadata={
                "conversation_mode": "confirm",
                "confirmation_payload": {"strategy": {"capital_amount": 10000}},
            },
        )
        stale_read = dict(created.metadata)
        winner = gateway.update_message_artifact(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            message_id=created.id,
            content="Buy and hold NFLX, edited",
            metadata={
                "conversation_mode": "confirm",
                "confirmation_payload": {"strategy": {"capital_amount": 25000}},
            },
            expected_source_metadata=created.metadata,
            expected_latest_message_id=created.id,
        )
        with pytest.raises(StaleMessageArtifactError):
            gateway.update_message_artifact(
                user_id=owner["user_id"],
                conversation_id=owner["conversation_id"],
                message_id=created.id,
                content="stale rewrite",
                metadata={"conversation_mode": "confirm"},
                expected_source_metadata=stale_read,
                expected_latest_message_id=created.id,
            )
        stored = gateway.get_message(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            message_id=created.id,
        )
        assert stored is not None
        assert stored.content == winner.content
        assert (
            stored.metadata["confirmation_payload"]["strategy"]["capital_amount"] == 25000
        ), "the losing writer must not roll back the winning edit"


def _conversation_row(connection, conversation_id: str):
    with connection.cursor() as cursor:
        cursor.execute(
            "select last_message_preview, updated_at from public.conversations"
            " where id = %s",
            (conversation_id,),
        )
        return cursor.fetchone()


def test_update_message_artifact_carries_the_preview_when_latest() -> None:
    with _connect() as connection:
        owner = _seed_owner(connection)
        gateway = _gateway()
        created = gateway.create_message(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            role="assistant",
            content="Buy and hold NFLX",
            metadata={"conversation_mode": "confirm"},
        )
        before_preview, before_updated_at = _conversation_row(
            connection, owner["conversation_id"]
        )
        assert before_preview == "Buy and hold NFLX"

        gateway.update_message_artifact(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            message_id=created.id,
            content="Buy and hold NFLX, edited",
            metadata={"conversation_mode": "confirm"},
            expected_source_metadata=created.metadata,
            expected_latest_message_id=created.id,
            preview="Buy and hold NFLX, edited",
        )
        after_preview, after_updated_at = _conversation_row(
            connection, owner["conversation_id"]
        )
        assert (
            after_preview == "Buy and hold NFLX, edited"
        ), "recents must describe the edited card"
        assert (
            after_updated_at == before_updated_at
        ), "a non-turn change must not reorder recents"


def test_update_message_artifact_keeps_preview_when_not_latest() -> None:
    with _connect() as connection:
        owner = _seed_owner(connection)
        gateway = _gateway()
        card = gateway.create_message(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            role="assistant",
            content="Buy and hold NFLX",
            metadata={"conversation_mode": "confirm"},
        )
        follow_up = gateway.create_message(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            role="user",
            content="How risky is this idea?",
        )
        gateway.update_message_artifact(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            message_id=card.id,
            content="Buy and hold NFLX, edited",
            metadata={"conversation_mode": "confirm"},
            expected_source_metadata=card.metadata,
            expected_latest_message_id=follow_up.id,
            preview="Buy and hold NFLX, edited",
        )
        preview, _updated_at = _conversation_row(connection, owner["conversation_id"])
        assert (
            preview == "How risky is this idea?"
        ), "editing an older card must not overwrite the newer preview"


def test_update_message_artifact_conflicts_when_an_append_intervened() -> None:
    """The activity guard: a write whose latest-message expectation predates
    an append conflicts on real Postgres, and the card row is untouched."""
    from argus.domain.supabase_conversation_messages import (
        StaleMessageArtifactError,
    )

    with _connect() as connection:
        owner = _seed_owner(connection)
        gateway = _gateway()
        card = gateway.create_message(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            role="assistant",
            content="Buy and hold NFLX",
            metadata={"conversation_mode": "confirm"},
        )
        gateway.create_message(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            role="assistant",
            content="a superseding turn landed here",
        )
        with pytest.raises(StaleMessageArtifactError):
            gateway.update_message_artifact(
                user_id=owner["user_id"],
                conversation_id=owner["conversation_id"],
                message_id=card.id,
                content="rewrite past a superseding append",
                metadata={"conversation_mode": "confirm"},
                expected_source_metadata=card.metadata,
                expected_latest_message_id=card.id,
            )
        stored = gateway.get_message(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            message_id=card.id,
        )
        assert stored is not None and stored.content == "Buy and hold NFLX"


def test_consume_and_restore_round_trip_on_real_postgres() -> None:
    """Run consumption is stamped and restored through the guarded writer
    on the real database, and only a consumed card is restorable."""
    from argus.api.chat.confirmation import (
        consume_pending_card_for_run,
        restore_pending_card_after_run,
    )

    with _connect() as connection:
        owner = _seed_owner(connection)
        gateway = _gateway()
        card = gateway.create_message(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            role="assistant",
            content="Buy and hold NFLX",
            metadata={
                "conversation_mode": "confirm",
                "confirmation_card": {
                    "confirmation_id": "conf-1",
                    "confirmation_state": "active",
                },
                "confirmation_payload": {"strategy": {"capital_amount": 10000}},
            },
        )
        outcome = consume_pending_card_for_run(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            message_id=card.id,
            gateway=gateway,
        )
        assert outcome == "consumed"
        stored = gateway.get_message(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            message_id=card.id,
        )
        assert stored is not None
        assert stored.metadata["confirmation_card"]["confirmation_state"] == "consumed"
        assert (
            consume_pending_card_for_run(
                user_id=owner["user_id"],
                conversation_id=owner["conversation_id"],
                message_id=card.id,
                gateway=gateway,
            )
            == "already_consumed"
        )
        assert restore_pending_card_after_run(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            message_id=card.id,
            gateway=gateway,
        )
        restored = gateway.get_message(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            message_id=card.id,
        )
        assert restored is not None
        assert restored.metadata["confirmation_card"]["confirmation_state"] == "active"


def test_newest_first_window_returns_the_tail_chronologically() -> None:
    """#433: a recent window must come from the conversation's tail. The
    ascending read with a limit returned the head and starved every
    recent-state reader on long hosted conversations."""
    with _connect() as connection:
        owner = _seed_owner(connection)
        gateway = _gateway()
        for index in range(25):
            gateway.create_message(
                user_id=owner["user_id"],
                conversation_id=owner["conversation_id"],
                role="user" if index % 2 else "assistant",
                content=f"message {index:02d}",
            )
        window = gateway.list_messages(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            limit=20,
            newest_first_window=True,
        )
        contents = [message.content for message in window]
        assert contents == [
            f"message {index:02d}" for index in range(5, 25)
        ], "the window is the newest 20 in chronological order"
