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
            )
        stored = gateway.get_message(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            message_id=created.id,
        )
        assert stored is not None and stored.content == "owned card"
