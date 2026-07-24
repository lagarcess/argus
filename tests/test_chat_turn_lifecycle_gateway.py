from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from argus.api.schemas import Message
from argus.domain.chat_turn_lifecycle import TransitionResult
from argus.domain.chat_turn_lifecycle_gateway import (
    ChatTurnLifecycleGatewayMixin,
)
from argus.domain.supabase_gateway import SupabaseGateway


def _id() -> str:
    return str(uuid4())


def _message(*, message_id: str, conversation_id: str) -> Message:
    return Message(
        id=message_id,
        conversation_id=conversation_id,
        role="user",
        content="Test this idea.",
        metadata={"chat_action": {"type": "change_dates"}},
        created_at=datetime.now(timezone.utc),
    )


def test_supabase_gateway_composes_the_focused_lifecycle_mixin() -> None:
    assert issubclass(SupabaseGateway, ChatTurnLifecycleGatewayMixin)
    for method_name in (
        "accept_chat_turn",
        "transition_chat_turn",
        "reconcile_stale_chat_turns",
        "list_projectable_chat_turns",
    ):
        assert method_name not in SupabaseGateway.__dict__


def test_accept_chat_turn_uses_the_atomic_acceptance_rpc() -> None:
    user_id = _id()
    conversation_id = _id()
    message = _message(message_id=_id(), conversation_id=conversation_id)
    client = MagicMock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(
        data=[
            {
                "message": message.model_dump(mode="json"),
                "lifecycle": {
                    "turn_id": message.id,
                    "status": "accepted",
                },
                "replayed": False,
            }
        ]
    )
    gateway = SupabaseGateway(client=client)

    accepted = gateway.accept_chat_turn(
        user_id=user_id,
        conversation_id=conversation_id,
        request_id="request-one",
        message=message,
    )

    assert accepted == message
    client.rpc.assert_called_once_with(
        "accept_chat_turn",
        {
            "p_user_id": user_id,
            "p_conversation_id": conversation_id,
            "p_message_id": message.id,
            "p_role": "user",
            "p_content": message.content,
            "p_metadata": message.metadata,
            "p_created_at": message.created_at.isoformat(),
            "p_preview": message.content,
            "p_request_id": "request-one",
        },
    )


def test_accept_chat_turn_rejects_a_mismatched_or_non_user_message() -> None:
    gateway = SupabaseGateway(client=MagicMock())
    conversation_id = _id()
    other_conversation_id = _id()

    with pytest.raises(ValueError, match="conversation"):
        gateway.accept_chat_turn(
            user_id=_id(),
            conversation_id=conversation_id,
            request_id="request-one",
            message=_message(
                message_id=_id(),
                conversation_id=other_conversation_id,
            ),
        )

    assistant = _message(message_id=_id(), conversation_id=conversation_id)
    assistant = assistant.model_copy(update={"role": "assistant"})
    with pytest.raises(ValueError, match="user"):
        gateway.accept_chat_turn(
            user_id=_id(),
            conversation_id=conversation_id,
            request_id="request-two",
            message=assistant,
        )


def test_transition_chat_turn_returns_the_frozen_database_outcome() -> None:
    turn_id = _id()
    assistant_message_id = _id()
    row = {
        "turn_id": turn_id,
        "status": "recoverable_failed",
        "assistant_message_id": assistant_message_id,
        "failure_code": "runtime_failure",
        "retryable": True,
    }
    client = MagicMock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(
        data={
            "outcome": "applied",
            "row": row,
        }
    )
    gateway = SupabaseGateway(client=client)

    result = gateway.transition_chat_turn(
        turn_id=turn_id,
        to_status="recoverable_failed",
        assistant_message_id=assistant_message_id,
        reconciled_outcome=None,
        failure_code="runtime_failure",
        retryable=True,
    )

    assert result == TransitionResult(outcome="applied", row=row)
    client.rpc.assert_called_once_with(
        "transition_chat_turn",
        {
            "p_turn_id": turn_id,
            "p_to_status": "recoverable_failed",
            "p_assistant_message_id": assistant_message_id,
            "p_reconciled_outcome": None,
            "p_failure_code": "runtime_failure",
            "p_retryable": True,
        },
    )


def test_transition_chat_turn_rejects_a_malformed_rpc_response() -> None:
    client = MagicMock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(data={})
    gateway = SupabaseGateway(client=client)

    with pytest.raises(RuntimeError, match="transition"):
        gateway.transition_chat_turn(
            turn_id=_id(),
            to_status="running",
            assistant_message_id=None,
            reconciled_outcome=None,
            failure_code=None,
            retryable=None,
        )


def test_reconcile_stale_chat_turns_uses_the_owner_scoped_rpc() -> None:
    user_id = _id()
    conversation_id = _id()
    rows = [
        {
            "turn_id": _id(),
            "user_id": user_id,
            "conversation_id": conversation_id,
            "status": "abandoned",
        }
    ]
    client = MagicMock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(data=rows)
    gateway = SupabaseGateway(client=client)

    result = gateway.reconcile_stale_chat_turns(
        conversation_id=conversation_id,
        user_id=user_id,
    )

    assert result == rows
    client.rpc.assert_called_once_with(
        "reconcile_stale_chat_turns",
        {
            "p_conversation_id": conversation_id,
            "p_user_id": user_id,
        },
    )


class _ProjectionQuery:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.operations: list[tuple[str, tuple[object, ...]]] = []

    def select(self, *args: object) -> _ProjectionQuery:
        self.operations.append(("select", args))
        return self

    def eq(self, *args: object) -> _ProjectionQuery:
        self.operations.append(("eq", args))
        return self

    def or_(self, *args: object) -> _ProjectionQuery:
        self.operations.append(("or_", args))
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self.rows)


def test_list_projectable_chat_turns_uses_one_snapshot_for_both_owners() -> None:
    user_id = _id()
    conversation_id = _id()
    assistant_message_id = _id()
    abandoned_turn_id = _id()
    assistant_row = {
        "turn_id": _id(),
        "user_id": user_id,
        "conversation_id": conversation_id,
        "assistant_message_id": assistant_message_id,
        "status": "completed",
    }
    abandoned_row = {
        "turn_id": abandoned_turn_id,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "assistant_message_id": None,
        "status": "abandoned",
    }
    query = _ProjectionQuery([assistant_row, abandoned_row])
    client = MagicMock()
    client.table.return_value = query
    gateway = SupabaseGateway(client=client)
    message_ids = [assistant_message_id, abandoned_turn_id]

    rows = gateway.list_projectable_chat_turns(
        conversation_id=conversation_id,
        user_id=user_id,
        message_ids=message_ids,
    )

    assert rows == sorted(
        [assistant_row, abandoned_row],
        key=lambda row: str(row["turn_id"]),
    )
    client.table.assert_called_once_with("chat_turn_lifecycles")
    message_ids_filter = ",".join(message_ids)
    assert query.operations == [
        ("select", ("*",)),
        ("eq", ("user_id", user_id)),
        ("eq", ("conversation_id", conversation_id)),
        (
            "or_",
            (
                (
                    f"assistant_message_id.in.({message_ids_filter}),"
                    "and(assistant_message_id.is.null,"
                    f"turn_id.in.({message_ids_filter}))"
                ),
            ),
        ),
    ]


def test_list_projectable_chat_turns_short_circuits_empty_ids() -> None:
    client = MagicMock()
    gateway = SupabaseGateway(client=client)

    assert (
        gateway.list_projectable_chat_turns(
            conversation_id=_id(),
            user_id=_id(),
            message_ids=[],
        )
        == []
    )
    client.table.assert_not_called()
