from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from argus.api.guest_access import AccountContext, guest_capabilities
from argus.api.schemas import Message
from argus.domain.chat_turn_lifecycle import TransitionResult
from argus.domain.chat_turn_lifecycle_gateway import (
    ChatTurnLifecycleGatewayMixin,
)
from argus.domain.supabase_gateway import SupabaseGateway
from argus.domain.usage_limits import message_usage_settlement


def _id() -> str:
    return str(uuid4())


def _message(
    *,
    message_id: str,
    conversation_id: str,
    content: str = "Test this idea.",
) -> Message:
    return Message(
        id=message_id,
        conversation_id=conversation_id,
        role="user",
        content=content,
        metadata={"chat_action": {"type": "change_dates"}},
        created_at=datetime.now(timezone.utc),
    )


def _assistant_message(
    *,
    message_id: str,
    conversation_id: str,
    turn_id: str,
    request_id: str,
    status: str = "completed",
) -> Message:
    runtime_turn: dict[str, object] = {
        "turn_id": turn_id,
        "request_id": request_id,
        "status": status,
        "terminal": True,
    }
    if status == "recoverable_failed":
        runtime_turn.update(
            failure_code="agent_runtime_failure",
            retryable=True,
        )
    return Message(
        id=message_id,
        conversation_id=conversation_id,
        role="assistant",
        content="Terminal response.",
        metadata={"agent_runtime_turn": runtime_turn},
        created_at=datetime.now(timezone.utc),
    )


def test_supabase_gateway_composes_the_focused_lifecycle_mixin() -> None:
    assert issubclass(SupabaseGateway, ChatTurnLifecycleGatewayMixin)
    for method_name in (
        "accept_chat_turn",
        "accept_response_option_chat_turn",
        "finalize_chat_turn",
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


@pytest.mark.parametrize(
    "control",
    [
        "__ONBOARDING_GOAL__:test_stock_idea",
        "__ONBOARDING_SKIP__",
    ],
)
def test_accept_chat_turn_suppresses_typed_onboarding_control_preview(
    control: str,
) -> None:
    user_id = _id()
    conversation_id = _id()
    message = _message(
        message_id=_id(),
        conversation_id=conversation_id,
        content=control,
    )
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
        request_id="request-onboarding",
        message=message,
    )

    assert accepted == message
    assert client.rpc.call_args.args[1]["p_preview"] is None


def test_response_option_acceptance_uses_one_lifecycle_rpc() -> None:
    user_id = _id()
    conversation_id = _id()
    source = _assistant_message(
        message_id=_id(),
        conversation_id=conversation_id,
        turn_id=_id(),
        request_id="source-request",
    )
    source = source.model_copy(
        update={
            "metadata": {
                "clarification": {
                    "options": [
                        {
                            "id": "option-1",
                            "replacement_values": {"timeframe": "1D"},
                        }
                    ]
                }
            }
        }
    )
    message = _message(message_id=_id(), conversation_id=conversation_id)
    client = MagicMock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(
        data=[
            {
                "message": message.model_dump(mode="json"),
                "source_message": source.model_dump(mode="json"),
                "lifecycle": {"turn_id": message.id, "status": "accepted"},
                "replayed": False,
            }
        ]
    )
    gateway = SupabaseGateway(client=client)

    accepted_source, accepted_message = gateway.accept_response_option_chat_turn(
        user_id=user_id,
        conversation_id=conversation_id,
        request_id="request-option",
        message=message,
        source_assistant_id=source.id,
        expected_source_metadata=source.metadata,
        option_id="option-1",
        replacement_values={"timeframe": "1D"},
    )

    assert accepted_source == source
    assert accepted_message == message
    assert client.rpc.call_args.args[0] == "accept_chat_turn"
    params = client.rpc.call_args.args[1]
    assert params["p_expected_source_assistant_id"] == source.id
    assert params["p_expected_source_metadata"] == source.metadata
    assert params["p_option_id"] == "option-1"
    assert params["p_replacement_values"] == {"timeframe": "1D"}


def test_terminal_finalization_uses_service_only_atomic_rpc() -> None:
    user_id = _id()
    conversation_id = _id()
    turn_id = _id()
    assistant = _assistant_message(
        message_id=_id(),
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id="request-final",
    )
    client = MagicMock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(
        data=[{"message": assistant.model_dump(mode="json")}]
    )
    gateway = SupabaseGateway(client=client)

    persisted = gateway.finalize_chat_turn(
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id="request-final",
        message=assistant,
        to_status="completed",
        failure_code=None,
        retryable=False,
        settle_usage={
            "resource": "messages",
            "limits": (("hour", 20), ("day", 100)),
        },
    )

    assert persisted == assistant
    assert client.rpc.call_args.args[0] == "finalize_chat_turn"
    params = client.rpc.call_args.args[1]
    assert params["p_turn_id"] == turn_id
    assert params["p_request_id"] == "request-final"
    assert params["p_message_id"] == assistant.id
    assert params["p_to_status"] == "completed"
    assert params["p_usage_resource"] == "messages"
    assert params["p_usage_limits"] == [
        {"period": "hour", "limit": 20},
        {"period": "day", "limit": 100},
    ]


def test_terminal_finalization_serializes_guest_visitor_window() -> None:
    user_id = _id()
    conversation_id = _id()
    turn_id = _id()
    expires_at = datetime(2026, 8, 1, 8, 3, 9, 708198, tzinfo=timezone.utc)
    assistant = _assistant_message(
        message_id=_id(),
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id="request-guest-final",
    )
    client = MagicMock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(
        data=[{"message": assistant.model_dump(mode="json")}]
    )
    gateway = SupabaseGateway(client=client)
    settlement = message_usage_settlement(
        AccountContext(
            kind="guest",
            user_id=user_id,
            expires_at=expires_at,
            capabilities=guest_capabilities(),
        ),
        visitor_key="visitor:serialization-proof",
    )

    persisted = gateway.finalize_chat_turn(
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id="request-guest-final",
        message=assistant,
        to_status="completed",
        failure_code=None,
        retryable=False,
        settle_usage=settlement,
    )

    assert persisted == assistant
    assert client.rpc.call_args.args[1]["p_usage_limits"] == [
        {"period": "day", "limit": 10}
    ]
    assert (
        client.rpc.call_args.args[1]["p_visitor_key"]
        == "visitor:serialization-proof"
    )


def test_response_option_retry_sends_only_the_persisted_request_identity() -> None:
    user_id = _id()
    conversation_id = _id()
    request_message_id = _id()
    source = _assistant_message(
        message_id=_id(),
        conversation_id=conversation_id,
        turn_id=request_message_id,
        request_id="request-original",
    )
    message = _message(message_id=_id(), conversation_id=conversation_id)
    client = MagicMock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(
        data=[
            {
                "message": message.model_dump(mode="json"),
                "source_message": source.model_dump(mode="json"),
                "lifecycle": {"turn_id": message.id, "status": "accepted"},
                "replayed": False,
            }
        ]
    )
    gateway = SupabaseGateway(client=client)

    accepted_source, accepted_message = gateway.accept_response_option_chat_turn(
        user_id=user_id,
        conversation_id=conversation_id,
        request_id="request-retry",
        message=message,
        source_assistant_id="tampered-not-a-uuid",
        expected_source_metadata={"response_options": ["tampered"]},
        option_id="tampered-option",
        replacement_values={"timeframe": "tampered"},
        request_message_id=request_message_id,
    )

    assert accepted_source == source
    assert accepted_message == message
    params = client.rpc.call_args.args[1]
    assert params["p_request_message_id"] == request_message_id
    assert params["p_expected_source_assistant_id"] is None
    assert params["p_expected_source_metadata"] is None
    assert params["p_option_id"] is None
    assert params["p_replacement_values"] is None


def test_response_option_retry_rejects_malformed_identity_before_rpc() -> None:
    conversation_id = _id()
    client = MagicMock()
    gateway = SupabaseGateway(client=client)

    with pytest.raises(ValueError, match="request message id"):
        gateway.accept_response_option_chat_turn(
            user_id=_id(),
            conversation_id=conversation_id,
            request_id="request-retry",
            message=_message(
                message_id=_id(),
                conversation_id=conversation_id,
            ),
            source_assistant_id=None,
            expected_source_metadata=None,
            option_id=None,
            replacement_values=None,
            request_message_id="not-a-uuid",
        )

    client.rpc.assert_not_called()


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
                    f"turn_id.in.({message_ids_filter})"
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


def test_list_projectable_chat_turns_batches_and_deduplicates_large_snapshots() -> None:
    user_id = _id()
    conversation_id = _id()
    message_ids = [_id() for _ in range(26)]
    row_from_second_batch = {
        "turn_id": message_ids[-1],
        "user_id": user_id,
        "conversation_id": conversation_id,
        "assistant_message_id": None,
        "status": "abandoned",
    }
    first_query = _ProjectionQuery([row_from_second_batch])
    second_query = _ProjectionQuery([row_from_second_batch])
    client = MagicMock()
    client.table.side_effect = [first_query, second_query]
    gateway = SupabaseGateway(client=client)

    rows = gateway.list_projectable_chat_turns(
        conversation_id=conversation_id,
        user_id=user_id,
        message_ids=message_ids,
    )

    assert rows == [row_from_second_batch]
    assert client.table.call_count == 2
    for query, expected_ids in (
        (first_query, message_ids[:25]),
        (second_query, message_ids[25:]),
    ):
        message_ids_filter = ",".join(expected_ids)
        assert query.operations == [
            ("select", ("*",)),
            ("eq", ("user_id", user_id)),
            ("eq", ("conversation_id", conversation_id)),
            (
                "or_",
                (
                    (
                        f"assistant_message_id.in.({message_ids_filter}),"
                        f"turn_id.in.({message_ids_filter})"
                    ),
                ),
            ),
        ]


def test_list_projectable_chat_turns_rejects_malformed_ids_before_query() -> None:
    client = MagicMock()
    gateway = SupabaseGateway(client=client)

    with pytest.raises(ValueError):
        gateway.list_projectable_chat_turns(
            conversation_id=_id(),
            user_id=_id(),
            message_ids=[_id(), "not-a-uuid"],
        )

    client.table.assert_not_called()
