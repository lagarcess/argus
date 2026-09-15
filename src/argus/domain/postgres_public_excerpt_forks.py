"""Atomic receipt copying through the existing database pool and guest RPCs."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from argus.api.public_excerpt_schemas import PUBLIC_EXCERPT_DOCUMENT_ADAPTER
from argus.api.schemas import Conversation
from argus.domain.public_excerpt_forks import ForkError, carried_messages, fork_marker


def fork_public_excerpt(
    pool: Any,
    *,
    user_id: str,
    public_id: str,
    request_id: str,
    language: str,
    guest: bool,
    replace_guest_conversation_id: str | None,
) -> tuple[Conversation, bool]:
    marker = fork_marker(user_id, request_id)
    with (
        pool.connection() as conn,
        conn.transaction(),
        conn.cursor(row_factory=dict_row) as cur,
    ):
        # Same receiver/request serializes even across app workers. The marker is
        # receiver-owned, so a replay survives owner revocation or deletion.
        cur.execute("select pg_advisory_xact_lock(hashtextextended(%s, 0))", (marker,))
        cur.execute(
            """select c.*, m.metadata as fork_metadata from public.messages m
            join public.conversations c on c.id=m.conversation_id
            where m.id=%s and m.user_id=%s and c.user_id=%s""",
            (marker, user_id, user_id),
        )
        replay = cur.fetchone()
        if replay:
            if (replay.get("fork_metadata") or {}).get("shared_conversation", {}).get(
                "public_id"
            ) != public_id:
                raise ForkError("receipt_request_conflict")
            if replay.get("deleted_at") is not None:
                raise ForkError("receipt_fork_deleted", 410)
            return Conversation.model_validate({**replay, "id": str(replay["id"])}), False
        # Source lock precedes snapshot lock, matching the delete/revoke trigger.
        cur.execute(
            "select source_conversation_id from public.public_excerpt_snapshots where public_id=%s",
            (public_id,),
        )
        source = cur.fetchone()
        if not source or source["source_conversation_id"] is None:
            raise ForkError("receipt_unavailable", 410)
        cur.execute(
            "select id from public.conversations where id=%s and deleted_at is null for share",
            (source["source_conversation_id"],),
        )
        if not cur.fetchone():
            raise ForkError("receipt_unavailable", 410)
        cur.execute(
            "select payload,created_at,revoked_at from public.public_excerpt_snapshots where public_id=%s for share",
            (public_id,),
        )
        snapshot = cur.fetchone()
        if not snapshot or snapshot["revoked_at"] is not None:
            raise ForkError("receipt_unavailable", 410)
        messages = carried_messages(
            PUBLIC_EXCERPT_DOCUMENT_ADAPTER.validate_python(snapshot["payload"]),
            snapshot_at=snapshot["created_at"],
            public_id=public_id,
            request_id=request_id,
        )
        conversation = None
        if guest:
            cur.execute(
                "select * from public.guest_workspaces where user_id=%s and status='active' and expires_at>now() for update",
                (user_id,),
            )
            workspace = cur.fetchone()
            if not workspace:
                raise ForkError("guest_session_expired", 403)
            existing_id = (
                str(workspace["conversation_id"])
                if workspace["conversation_id"]
                else None
            )
            if (
                replace_guest_conversation_id
                and replace_guest_conversation_id != existing_id
            ):
                raise ForkError("receipt_guest_choice_stale")
            if existing_id:
                # The canonical writer locks this row before appending. Lock it
                # before deciding an empty chat is safe to reuse.
                cur.execute(
                    "select * from public.conversations where id=%s and user_id=%s and deleted_at is null for update",
                    (existing_id, user_id),
                )
                existing = cur.fetchone()
                cur.execute(
                    "select 1 from public.messages where conversation_id=%s and role='user' limit 1",
                    (existing_id,),
                )
                nonempty = cur.fetchone() is not None
                if nonempty and not replace_guest_conversation_id:
                    raise ForkError("receipt_guest_choice_required")
                if nonempty:
                    cur.execute(
                        "select * from public.replace_guest_conversation(%s,%s,%s,%s)",
                        (user_id, "New idea", "system_default", language),
                    )
                    conversation = cur.fetchone()
                elif existing:
                    conversation = existing
                else:
                    raise ForkError("receipt_guest_choice_stale")
        if conversation is None:
            cur.execute(
                """insert into public.conversations (user_id,title,title_source,language)
                values (%s,%s,%s,%s) returning *""",
                (user_id, "New idea", "system_default", language),
            )
            conversation = cur.fetchone()
        for index, message in enumerate(messages):
            cur.execute(
                """insert into public.messages (id,user_id,conversation_id,role,content,metadata,created_at)
                values (%s,%s,%s,%s,%s,%s,clock_timestamp())""",
                (
                    marker if index == 0 else str(uuid4()),
                    user_id,
                    conversation["id"],
                    message["role"],
                    message["content"],
                    Jsonb(message["metadata"]),
                ),
            )
        # Imported answers are visible history, but never owner-derived recents
        # previews or titles. Their own first follow-up writes ordinary activity.
        return Conversation.model_validate(
            {**conversation, "id": str(conversation["id"])}
        ), True
