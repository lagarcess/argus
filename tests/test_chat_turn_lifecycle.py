from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from argus.api.schemas import Conversation, Message
from argus.domain.chat_turn_lifecycle import (
    ALLOWED,
    TERMINAL,
    MemoryChatTurnLifecycleGateway,
    TransitionResult,
)
from argus.domain.store import AlphaStore

EXPECTED_ALLOWED = {
    "accepted": {
        "running",
        "completed",
        "recoverable_failed",
        "abandoned",
        "reconciled",
    },
    "running": {
        "completed",
        "recoverable_failed",
        "abandoned",
        "reconciled",
    },
}
EXPECTED_TERMINAL = {
    "completed",
    "recoverable_failed",
    "abandoned",
    "reconciled",
}


def _id() -> str:
    return str(uuid4())


def _message(
    *,
    message_id: str,
    conversation_id: str,
    role: str = "user",
    created_at: datetime | None = None,
    metadata: dict[str, object] | None = None,
    content: str = "Test this idea.",
) -> Message:
    return Message(
        id=message_id,
        conversation_id=conversation_id,
        role=role,
        content=content,
        metadata=metadata or {},
        created_at=created_at or datetime.now(timezone.utc),
    )


@pytest.fixture
def lifecycle() -> tuple[
    MemoryChatTurnLifecycleGateway,
    AlphaStore,
    str,
    str,
]:
    store = AlphaStore()
    user_id = _id()
    conversation_id = _id()
    now = datetime.now(timezone.utc)
    store.conversation_owners[conversation_id] = user_id
    store.conversations[conversation_id] = Conversation(
        id=conversation_id,
        title="Lifecycle proof",
        title_source="system_default",
        created_at=now,
        updated_at=now,
    )
    store.messages[conversation_id] = []
    return (
        MemoryChatTurnLifecycleGateway(store),
        store,
        user_id,
        conversation_id,
    )


def _accept(
    gateway: MemoryChatTurnLifecycleGateway,
    *,
    user_id: str,
    conversation_id: str,
    turn_id: str | None = None,
    request_id: str | None = None,
) -> Message:
    message = _message(
        message_id=turn_id or _id(),
        conversation_id=conversation_id,
    )
    return gateway.accept_chat_turn(
        user_id=user_id,
        conversation_id=conversation_id,
        request_id=request_id or f"request-{message.id}",
        message=message,
    )


def _terminal_message(
    store: AlphaStore,
    *,
    user_id: str,
    conversation_id: str,
    turn_id: str,
    request_id: str,
    status: str,
    message_id: str | None = None,
    created_at: datetime | None = None,
    failure_code: object = None,
    retryable: object = False,
    include_failure_code: bool = True,
    include_retryable: bool = True,
) -> Message:
    runtime_turn: dict[str, object] = {
        "turn_id": turn_id,
        "request_id": request_id,
        "terminal": True,
        "status": status,
    }
    if include_failure_code:
        runtime_turn["failure_code"] = failure_code
    if include_retryable:
        runtime_turn["retryable"] = retryable
    metadata: dict[str, object] = {"agent_runtime_turn": runtime_turn}
    message = _message(
        message_id=message_id or _id(),
        conversation_id=conversation_id,
        role="assistant",
        created_at=created_at,
        metadata=metadata,
        content="Durable terminal response.",
    )
    assert store.conversation_owners[conversation_id] == user_id
    store.messages[conversation_id].append(message)
    return message


def _transition_terminal(
    gateway: MemoryChatTurnLifecycleGateway,
    store: AlphaStore,
    *,
    user_id: str,
    conversation_id: str,
    turn_id: str,
    request_id: str,
    status: str,
) -> TransitionResult:
    if status == "abandoned":
        return gateway.transition_chat_turn(
            turn_id=turn_id,
            to_status="abandoned",
            assistant_message_id=None,
            reconciled_outcome=None,
            failure_code="turn_abandoned",
            retryable=True,
        )
    evidence_status = (
        "recoverable_failed" if status == "recoverable_failed" else "completed"
    )
    assistant = _terminal_message(
        store,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id=request_id,
        status=evidence_status,
        failure_code=(
            "runtime_failure" if evidence_status == "recoverable_failed" else None
        ),
        retryable=evidence_status == "recoverable_failed",
    )
    return gateway.transition_chat_turn(
        turn_id=turn_id,
        to_status=status,
        assistant_message_id=assistant.id,
        reconciled_outcome=(
            evidence_status if status == "reconciled" else None
        ),
        failure_code=(
            "runtime_failure" if evidence_status == "recoverable_failed" else None
        ),
        retryable=evidence_status == "recoverable_failed",
    )


def test_state_machine_constants_match_the_locked_contract() -> None:
    assert ALLOWED == EXPECTED_ALLOWED
    assert TERMINAL == EXPECTED_TERMINAL


def test_transition_result_is_frozen() -> None:
    result = TransitionResult(outcome="missing")

    with pytest.raises(FrozenInstanceError):
        result.outcome = "applied"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("source_status", "target_status"),
    [
        (source, target)
        for source, targets in EXPECTED_ALLOWED.items()
        for target in sorted(targets)
    ],
)
def test_only_approved_source_transitions_apply(
    lifecycle: tuple[
        MemoryChatTurnLifecycleGateway,
        AlphaStore,
        str,
        str,
    ],
    source_status: str,
    target_status: str,
) -> None:
    gateway, store, user_id, conversation_id = lifecycle
    turn_id = _id()
    request_id = f"request-{turn_id}"
    _accept(
        gateway,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id=request_id,
    )
    if source_status == "running":
        running = gateway.transition_chat_turn(
            turn_id=turn_id,
            to_status="running",
            assistant_message_id=None,
            reconciled_outcome=None,
            failure_code=None,
            retryable=None,
        )
        assert running.outcome == "applied"

    if target_status == "running":
        result = gateway.transition_chat_turn(
            turn_id=turn_id,
            to_status="running",
            assistant_message_id=None,
            reconciled_outcome=None,
            failure_code=None,
            retryable=None,
        )
    else:
        result = _transition_terminal(
            gateway,
            store,
            user_id=user_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            request_id=request_id,
            status=target_status,
        )

    assert result.outcome == "applied"
    assert result.row is not None
    assert result.row["status"] == target_status


def test_exact_null_safe_transition_replay_is_a_noop(
    lifecycle: tuple[
        MemoryChatTurnLifecycleGateway,
        AlphaStore,
        str,
        str,
    ],
) -> None:
    gateway, store, user_id, conversation_id = lifecycle
    turn_id = _id()
    request_id = f"request-{turn_id}"
    _accept(
        gateway,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id=request_id,
    )
    assistant = _terminal_message(
        store,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id=request_id,
        status="completed",
    )

    applied = gateway.transition_chat_turn(
        turn_id=turn_id,
        to_status="completed",
        assistant_message_id=assistant.id,
        reconciled_outcome=None,
        failure_code=None,
        retryable=None,
    )
    replay = gateway.transition_chat_turn(
        turn_id=turn_id,
        to_status="completed",
        assistant_message_id=assistant.id,
        reconciled_outcome=None,
        failure_code=None,
        retryable=None,
    )

    assert applied.outcome == "applied"
    assert replay.outcome == "noop"
    assert replay.row == applied.row


def test_conflicting_terminal_replay_does_not_overwrite_the_row(
    lifecycle: tuple[
        MemoryChatTurnLifecycleGateway,
        AlphaStore,
        str,
        str,
    ],
) -> None:
    gateway, store, user_id, conversation_id = lifecycle
    turn_id = _id()
    request_id = f"request-{turn_id}"
    _accept(
        gateway,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id=request_id,
    )
    first = _terminal_message(
        store,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id=request_id,
        status="completed",
    )
    second = _terminal_message(
        store,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id=request_id,
        status="completed",
    )
    applied = gateway.transition_chat_turn(
        turn_id=turn_id,
        to_status="completed",
        assistant_message_id=first.id,
        reconciled_outcome=None,
        failure_code=None,
        retryable=False,
    )

    conflict = gateway.transition_chat_turn(
        turn_id=turn_id,
        to_status="completed",
        assistant_message_id=second.id,
        reconciled_outcome=None,
        failure_code=None,
        retryable=False,
    )

    assert conflict.outcome == "conflict"
    assert conflict.row == applied.row


def test_late_success_cannot_supersede_recoverable_failure(
    lifecycle: tuple[
        MemoryChatTurnLifecycleGateway,
        AlphaStore,
        str,
        str,
    ],
) -> None:
    gateway, store, user_id, conversation_id = lifecycle
    turn_id = _id()
    request_id = f"request-{turn_id}"
    _accept(
        gateway,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id=request_id,
    )
    failure = _terminal_message(
        store,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id=request_id,
        status="recoverable_failed",
        failure_code="runtime_failure",
        retryable=True,
    )
    failed = gateway.transition_chat_turn(
        turn_id=turn_id,
        to_status="recoverable_failed",
        assistant_message_id=failure.id,
        reconciled_outcome=None,
        failure_code="runtime_failure",
        retryable=True,
    )
    success = _terminal_message(
        store,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id=request_id,
        status="completed",
    )

    late = gateway.transition_chat_turn(
        turn_id=turn_id,
        to_status="completed",
        assistant_message_id=success.id,
        reconciled_outcome=None,
        failure_code=None,
        retryable=False,
    )

    assert failed.outcome == "applied"
    assert late.outcome == "conflict"
    assert late.row is not None
    assert late.row["status"] == "recoverable_failed"
    assert late.row["assistant_message_id"] == failure.id


@pytest.mark.parametrize(
    ("to_status", "reconciled_outcome"),
    [
        ("recoverable_failed", None),
        ("reconciled", "recoverable_failed"),
    ],
)
@pytest.mark.parametrize(
    (
        "include_failure_code",
        "include_retryable",
        "evidence_failure_code",
        "evidence_retryable",
        "caller_failure_code",
        "caller_retryable",
    ),
    [
        (False, True, "runtime_failure", True, "runtime_failure", True),
        (True, False, "runtime_failure", True, "runtime_failure", True),
        (True, True, "durable_failure", True, "caller_failure", True),
        (True, True, "runtime_failure", True, "runtime_failure", False),
        pytest.param(
            True,
            True,
            7,
            True,
            "7",
            True,
            id="numeric-json-failure-code-text-match",
        ),
    ],
)
def test_recoverable_failure_evidence_fields_are_required_and_exact(
    lifecycle: tuple[
        MemoryChatTurnLifecycleGateway,
        AlphaStore,
        str,
        str,
    ],
    to_status: str,
    reconciled_outcome: str | None,
    include_failure_code: bool,
    include_retryable: bool,
    evidence_failure_code: object,
    evidence_retryable: bool,
    caller_failure_code: str,
    caller_retryable: bool,
) -> None:
    gateway, store, user_id, conversation_id = lifecycle
    turn_id = _id()
    request_id = f"request-{turn_id}"
    _accept(
        gateway,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id=request_id,
    )
    failure = _terminal_message(
        store,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id=request_id,
        status="recoverable_failed",
        failure_code=evidence_failure_code,
        retryable=evidence_retryable,
        include_failure_code=include_failure_code,
        include_retryable=include_retryable,
    )
    before = dict(store.chat_turn_lifecycles[turn_id])

    result = gateway.transition_chat_turn(
        turn_id=turn_id,
        to_status=to_status,
        assistant_message_id=failure.id,
        reconciled_outcome=reconciled_outcome,
        failure_code=caller_failure_code,
        retryable=caller_retryable,
    )

    assert result.outcome == "invalid"
    assert result.row == before
    assert store.chat_turn_lifecycles[turn_id] == before


@pytest.mark.parametrize(
    ("to_status", "reconciled_outcome"),
    [
        ("recoverable_failed", None),
        ("reconciled", "recoverable_failed"),
    ],
)
def test_recoverable_failure_evidence_matches_null_safely(
    lifecycle: tuple[
        MemoryChatTurnLifecycleGateway,
        AlphaStore,
        str,
        str,
    ],
    to_status: str,
    reconciled_outcome: str | None,
) -> None:
    gateway, store, user_id, conversation_id = lifecycle
    turn_id = _id()
    request_id = f"request-{turn_id}"
    _accept(
        gateway,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id=request_id,
    )
    failure = _terminal_message(
        store,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id=request_id,
        status="recoverable_failed",
        failure_code=None,
        retryable=False,
    )

    result = gateway.transition_chat_turn(
        turn_id=turn_id,
        to_status=to_status,
        assistant_message_id=failure.id,
        reconciled_outcome=reconciled_outcome,
        failure_code=None,
        retryable=None,
    )

    assert result.outcome == "applied"
    assert result.row is not None
    assert result.row["failure_code"] is None
    assert result.row["retryable"] is False


def test_missing_and_invalid_transitions_are_distinct(
    lifecycle: tuple[
        MemoryChatTurnLifecycleGateway,
        AlphaStore,
        str,
        str,
    ],
) -> None:
    gateway, _store, user_id, conversation_id = lifecycle
    missing = gateway.transition_chat_turn(
        turn_id=_id(),
        to_status="running",
        assistant_message_id=None,
        reconciled_outcome=None,
        failure_code=None,
        retryable=None,
    )
    turn = _accept(
        gateway,
        user_id=user_id,
        conversation_id=conversation_id,
    )

    invalid = gateway.transition_chat_turn(
        turn_id=turn.id,
        to_status="reconciled",
        assistant_message_id=None,
        reconciled_outcome="abandoned",
        failure_code=None,
        retryable=None,
    )

    assert missing == TransitionResult(outcome="missing")
    assert invalid.outcome == "invalid"
    assert invalid.row is not None
    assert invalid.row["status"] == "accepted"


def test_acceptance_is_atomic_idempotent_and_owner_scoped(
    lifecycle: tuple[
        MemoryChatTurnLifecycleGateway,
        AlphaStore,
        str,
        str,
    ],
) -> None:
    gateway, store, user_id, conversation_id = lifecycle
    message = _message(message_id=_id(), conversation_id=conversation_id)

    accepted = gateway.accept_chat_turn(
        user_id=user_id,
        conversation_id=conversation_id,
        request_id="request-one",
        message=message,
    )
    replay = gateway.accept_chat_turn(
        user_id=user_id,
        conversation_id=conversation_id,
        request_id="request-one",
        message=message,
    )

    assert replay == accepted
    assert store.messages[conversation_id] == [accepted]
    assert store.chat_turn_lifecycles[message.id]["status"] == "accepted"
    with pytest.raises(ValueError, match="request"):
        gateway.accept_chat_turn(
            user_id=user_id,
            conversation_id=conversation_id,
            request_id="different-request",
            message=message,
        )
    with pytest.raises(ValueError, match="owned"):
        gateway.accept_chat_turn(
            user_id=_id(),
            conversation_id=conversation_id,
            request_id="request-foreign",
            message=_message(
                message_id=_id(),
                conversation_id=conversation_id,
            ),
        )


def test_response_option_retry_uses_server_owned_request_and_accepts_once(
    lifecycle: tuple[
        MemoryChatTurnLifecycleGateway,
        AlphaStore,
        str,
        str,
    ],
) -> None:
    gateway, store, user_id, conversation_id = lifecycle
    source = _message(
        message_id=_id(),
        conversation_id=conversation_id,
        role="assistant",
        content="Which timeframe?",
        metadata={
            "clarification": {
                "options": [
                    {
                        "id": "daily",
                        "replacement_values": {"timeframe": "1D"},
                    }
                ],
                "payload": {"strategy": {"asset_universe": ["AAPL"]}},
            }
        },
    )
    store.messages[conversation_id].append(source)
    original = _message(
        message_id=_id(),
        conversation_id=conversation_id,
        content="Use daily bars",
        metadata={
            "agent_runtime_turn": {"request_id": "request-original"},
            "chat_action": {
                "type": "select_response_option",
                "label": "Use daily bars",
                "payload": {
                    "option_id": "daily",
                    "replacement_values": {"timeframe": "1D"},
                },
                "presentation": None,
            },
        },
    )
    claim = gateway.accept_response_option_chat_turn(
        user_id=user_id,
        conversation_id=conversation_id,
        request_id="request-original",
        message=original,
        source_assistant_id=source.id,
        expected_source_metadata=source.metadata,
        option_id="daily",
        replacement_values={"timeframe": "1D"},
    )
    assert claim == (source, original)
    failure = _terminal_message(
        store,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=original.id,
        request_id="request-original",
        status="recoverable_failed",
        failure_code="runtime_failure",
        retryable=True,
    )
    transitioned = gateway.transition_chat_turn(
        turn_id=original.id,
        to_status="recoverable_failed",
        assistant_message_id=failure.id,
        reconciled_outcome=None,
        failure_code="runtime_failure",
        retryable=True,
    )
    assert transitioned.outcome == "applied"

    retry_candidate = _message(
        message_id=_id(),
        conversation_id=conversation_id,
        content="tampered replay content",
        metadata={
            "agent_runtime_turn": {"request_id": "request-retry"},
            "mentions": [{"id": "tampered"}],
            "chat_action": {
                "type": "select_response_option",
                "label": "Tampered",
                "payload": {
                    "request_message_id": original.id,
                    "source_assistant_id": _id(),
                    "option_id": "tampered",
                    "replacement_values": {"timeframe": "5m"},
                },
            },
        },
    )
    retried = gateway.accept_response_option_chat_turn(
        user_id=user_id,
        conversation_id=conversation_id,
        request_id="request-retry",
        message=retry_candidate,
        source_assistant_id=None,
        expected_source_metadata=None,
        option_id=None,
        replacement_values=None,
        request_message_id=original.id,
    )

    assert retried is not None
    accepted_source, accepted_retry = retried
    assert accepted_source == source
    assert accepted_retry.id == retry_candidate.id
    assert accepted_retry.content == original.content
    assert accepted_retry.metadata == {
        "agent_runtime_turn": {"request_id": "request-retry"},
        "chat_action": original.metadata["chat_action"],
    }
    assert store.chat_turn_lifecycles[original.id]["status"] == (
        "recoverable_failed"
    )
    assert store.chat_turn_lifecycles[retry_candidate.id]["status"] == "accepted"

    replay = gateway.accept_response_option_chat_turn(
        user_id=user_id,
        conversation_id=conversation_id,
        request_id="request-retry",
        message=retry_candidate,
        source_assistant_id=None,
        expected_source_metadata=None,
        option_id=None,
        replacement_values=None,
        request_message_id=original.id,
    )
    competing = gateway.accept_response_option_chat_turn(
        user_id=user_id,
        conversation_id=conversation_id,
        request_id="request-competing",
        message=_message(
            message_id=_id(),
            conversation_id=conversation_id,
            content="different replay",
        ),
        source_assistant_id=None,
        expected_source_metadata=None,
        option_id=None,
        replacement_values=None,
        request_message_id=original.id,
    )

    assert replay == (source, accepted_retry)
    assert competing is None
    assert sum(
        row["status"] == "accepted"
        for row in store.chat_turn_lifecycles.values()
    ) == 1
    successful_assistant = _message(
        message_id=_id(),
        conversation_id=conversation_id,
        role="assistant",
        content="Completed retry.",
        metadata={
            "agent_runtime_turn": {
                "turn_id": accepted_retry.id,
                "request_id": "request-retry",
                "status": "completed",
                "terminal": True,
            }
        },
    )
    gateway.finalize_chat_turn(
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=accepted_retry.id,
        request_id="request-retry",
        message=successful_assistant,
        to_status="completed",
        failure_code=None,
        retryable=False,
        settle_usage={
            "resource": "messages",
            "limits": [("hour", 20), ("day", 100)],
        },
    )
    assert store.chat_turn_lifecycles[original.id]["status"] == (
        "recoverable_failed"
    )
    assert store.chat_turn_lifecycles[accepted_retry.id]["status"] == "completed"
    assert {
        key: row["used_count"]
        for key, row in store.usage_counters.items()
    } == {
        (user_id, "messages", "hour"): 1,
        (user_id, "messages", "day"): 1,
    }


@pytest.mark.parametrize(
    "rejection_case",
    [
        "foreign_owner",
        "foreign_conversation",
        "completed",
        "nonretryable",
        "superseded",
    ],
)
def test_response_option_retry_rejection_is_side_effect_free(
    lifecycle: tuple[
        MemoryChatTurnLifecycleGateway,
        AlphaStore,
        str,
        str,
    ],
    rejection_case: str,
) -> None:
    gateway, store, user_id, conversation_id = lifecycle
    source = _message(
        message_id=_id(),
        conversation_id=conversation_id,
        role="assistant",
        content="Which timeframe?",
        metadata={
            "clarification": {
                "options": [
                    {
                        "id": "daily",
                        "replacement_values": {"timeframe": "1D"},
                    }
                ]
            }
        },
    )
    store.messages[conversation_id].append(source)
    original = _message(
        message_id=_id(),
        conversation_id=conversation_id,
        content="Use daily bars",
        metadata={
            "chat_action": {
                "type": "select_response_option",
                "label": "Use daily bars",
                "payload": {
                    "option_id": "daily",
                    "replacement_values": {"timeframe": "1D"},
                },
            }
        },
    )
    assert gateway.accept_response_option_chat_turn(
        user_id=user_id,
        conversation_id=conversation_id,
        request_id="request-original",
        message=original,
        source_assistant_id=source.id,
        expected_source_metadata=source.metadata,
        option_id="daily",
        replacement_values={"timeframe": "1D"},
    )
    terminal_status = (
        "completed" if rejection_case == "completed" else "recoverable_failed"
    )
    retryable = rejection_case not in {"completed", "nonretryable"}
    terminal = _terminal_message(
        store,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=original.id,
        request_id="request-original",
        status=terminal_status,
        failure_code=(
            "runtime_failure" if terminal_status == "recoverable_failed" else None
        ),
        retryable=retryable,
    )
    assert gateway.transition_chat_turn(
        turn_id=original.id,
        to_status=terminal_status,
        assistant_message_id=terminal.id,
        reconciled_outcome=None,
        failure_code=(
            "runtime_failure" if terminal_status == "recoverable_failed" else None
        ),
        retryable=retryable,
    ).outcome == "applied"
    if rejection_case == "superseded":
        _accept(
            gateway,
            user_id=user_id,
            conversation_id=conversation_id,
            request_id="request-later",
        )

    retry_user_id = _id() if rejection_case == "foreign_owner" else user_id
    retry_conversation_id = conversation_id
    if rejection_case == "foreign_conversation":
        retry_conversation_id = _id()
        store.conversation_owners[retry_conversation_id] = user_id
        store.conversations[retry_conversation_id] = Conversation(
            id=retry_conversation_id,
            title="Other conversation",
            title_source="system_default",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        store.messages[retry_conversation_id] = []
    retry_candidate = _message(
        message_id=_id(),
        conversation_id=retry_conversation_id,
        content="tampered retry",
    )
    messages_before = deepcopy(store.messages)
    lifecycles_before = deepcopy(store.chat_turn_lifecycles)
    usage_before = deepcopy(store.usage_counters)

    rejected = gateway.accept_response_option_chat_turn(
        user_id=retry_user_id,
        conversation_id=retry_conversation_id,
        request_id="request-retry",
        message=retry_candidate,
        source_assistant_id=None,
        expected_source_metadata=None,
        option_id=None,
        replacement_values=None,
        request_message_id=original.id,
    )

    assert rejected is None
    assert store.messages == messages_before
    assert store.chat_turn_lifecycles == lifecycles_before
    assert store.usage_counters == usage_before


@pytest.mark.parametrize(
    ("content", "expected_preview"),
    [
        ("Test this normal idea.", "Test this normal idea."),
        ("__ONBOARDING_GOAL__:test_stock_idea", None),
        ("__ONBOARDING_SKIP__", None),
    ],
)
def test_acceptance_preview_keeps_normal_text_but_hides_typed_onboarding_controls(
    lifecycle: tuple[
        MemoryChatTurnLifecycleGateway,
        AlphaStore,
        str,
        str,
    ],
    content: str,
    expected_preview: str | None,
) -> None:
    gateway, store, user_id, conversation_id = lifecycle
    message = _message(
        message_id=_id(),
        conversation_id=conversation_id,
        content=content,
    )

    gateway.accept_chat_turn(
        user_id=user_id,
        conversation_id=conversation_id,
        request_id=f"request-{message.id}",
        message=message,
    )

    assert store.conversations[conversation_id].last_message_preview == expected_preview


def test_reconciliation_uses_stale_order_and_processes_at_most_twenty(
    lifecycle: tuple[
        MemoryChatTurnLifecycleGateway,
        AlphaStore,
        str,
        str,
    ],
) -> None:
    gateway, store, user_id, conversation_id = lifecycle
    stale_base = datetime.now(timezone.utc) - timedelta(minutes=30)
    expected: list[tuple[datetime, str]] = []
    all_turn_ids: list[str] = []
    for index in range(22):
        turn_id = _id()
        all_turn_ids.append(turn_id)
        _accept(
            gateway,
            user_id=user_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
        )
        stale_at = stale_base + timedelta(seconds=index % 3)
        store.chat_turn_lifecycles[turn_id]["accepted_at"] = stale_at.isoformat()
        expected.append((stale_at, turn_id))

    rows = gateway.reconcile_stale_chat_turns(
        conversation_id=conversation_id,
        user_id=user_id,
    )

    expected_turn_ids = [
        turn_id for _stale_at, turn_id in sorted(expected)[:20]
    ]
    assert [row["turn_id"] for row in rows] == expected_turn_ids
    assert all(row["status"] == "abandoned" for row in rows)
    assert all(row["failure_code"] == "turn_abandoned" for row in rows)
    assert all(row["retryable"] is True for row in rows)
    untouched = set(all_turn_ids) - set(expected_turn_ids)
    assert {
        store.chat_turn_lifecycles[turn_id]["status"] for turn_id in untouched
    } == {"accepted"}


def test_equal_timestamp_failure_evidence_wins_before_success(
    lifecycle: tuple[
        MemoryChatTurnLifecycleGateway,
        AlphaStore,
        str,
        str,
    ],
) -> None:
    gateway, store, user_id, conversation_id = lifecycle
    turn_id = _id()
    request_id = f"request-{turn_id}"
    _accept(
        gateway,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id=request_id,
    )
    store.chat_turn_lifecycles[turn_id]["accepted_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=30)
    ).isoformat()
    created_at = datetime.now(timezone.utc)
    success = _terminal_message(
        store,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id=request_id,
        status="completed",
        message_id="00000000-0000-0000-0000-000000000001",
        created_at=created_at,
    )
    failure = _terminal_message(
        store,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id=request_id,
        status="recoverable_failed",
        message_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
        created_at=created_at,
        failure_code="runtime_failure",
        retryable=True,
    )

    [row] = gateway.reconcile_stale_chat_turns(
        conversation_id=conversation_id,
        user_id=user_id,
    )

    assert success.id < failure.id
    assert row["status"] == "reconciled"
    assert row["reconciled_outcome"] == "recoverable_failed"
    assert row["assistant_message_id"] == failure.id
    assert row["failure_code"] == "runtime_failure"
    assert row["retryable"] is True


def test_reconciliation_skips_malformed_failure_for_later_valid_evidence(
    lifecycle: tuple[
        MemoryChatTurnLifecycleGateway,
        AlphaStore,
        str,
        str,
    ],
) -> None:
    gateway, store, user_id, conversation_id = lifecycle
    turn_id = _id()
    request_id = f"request-{turn_id}"
    _accept(
        gateway,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id=request_id,
    )
    store.chat_turn_lifecycles[turn_id]["accepted_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=30)
    ).isoformat()
    malformed = _terminal_message(
        store,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id=request_id,
        status="recoverable_failed",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=2),
        failure_code="malformed_failure",
        retryable=True,
        include_failure_code=False,
    )
    valid = _terminal_message(
        store,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id=request_id,
        status="recoverable_failed",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        failure_code="durable_failure",
        retryable=True,
    )

    [row] = gateway.reconcile_stale_chat_turns(
        conversation_id=conversation_id,
        user_id=user_id,
    )

    assert malformed.created_at < valid.created_at
    assert row["status"] == "reconciled"
    assert row["assistant_message_id"] == valid.id
    assert row["reconciled_outcome"] == "recoverable_failed"
    assert row["failure_code"] == "durable_failure"
    assert row["retryable"] is True


@pytest.mark.parametrize(
    (
        "failure_code",
        "retryable",
        "include_failure_code",
        "include_retryable",
    ),
    [
        ("runtime_failure", True, False, True),
        ("runtime_failure", True, True, False),
        (7, True, True, True),
        ("runtime_failure", "yes", True, True),
    ],
)
def test_reconciliation_abandons_when_only_failure_evidence_is_malformed(
    lifecycle: tuple[
        MemoryChatTurnLifecycleGateway,
        AlphaStore,
        str,
        str,
    ],
    failure_code: object,
    retryable: object,
    include_failure_code: bool,
    include_retryable: bool,
) -> None:
    gateway, store, user_id, conversation_id = lifecycle
    turn_id = _id()
    request_id = f"request-{turn_id}"
    _accept(
        gateway,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id=request_id,
    )
    store.chat_turn_lifecycles[turn_id]["accepted_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=30)
    ).isoformat()
    _terminal_message(
        store,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_id=request_id,
        status="recoverable_failed",
        failure_code=failure_code,
        retryable=retryable,
        include_failure_code=include_failure_code,
        include_retryable=include_retryable,
    )

    [row] = gateway.reconcile_stale_chat_turns(
        conversation_id=conversation_id,
        user_id=user_id,
    )
    replay = gateway.reconcile_stale_chat_turns(
        conversation_id=conversation_id,
        user_id=user_id,
    )

    assert row["status"] == "abandoned"
    assert row["assistant_message_id"] is None
    assert row["failure_code"] == "turn_abandoned"
    assert row["retryable"] is True
    assert replay == []


def test_no_terminal_evidence_reconciles_directly_to_abandoned(
    lifecycle: tuple[
        MemoryChatTurnLifecycleGateway,
        AlphaStore,
        str,
        str,
    ],
) -> None:
    gateway, store, user_id, conversation_id = lifecycle
    turn = _accept(
        gateway,
        user_id=user_id,
        conversation_id=conversation_id,
    )
    store.chat_turn_lifecycles[turn.id]["accepted_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=16)
    ).isoformat()

    [row] = gateway.reconcile_stale_chat_turns(
        conversation_id=conversation_id,
        user_id=user_id,
    )

    assert row["status"] == "abandoned"
    assert row["assistant_message_id"] is None
    assert row["failure_code"] == "turn_abandoned"
    assert row["retryable"] is True


def test_reconciliation_and_projection_are_owner_scoped(
    lifecycle: tuple[
        MemoryChatTurnLifecycleGateway,
        AlphaStore,
        str,
        str,
    ],
) -> None:
    gateway, store, user_id, conversation_id = lifecycle
    turn = _accept(
        gateway,
        user_id=user_id,
        conversation_id=conversation_id,
    )
    store.chat_turn_lifecycles[turn.id]["accepted_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=30)
    ).isoformat()

    assert (
        gateway.reconcile_stale_chat_turns(
            conversation_id=conversation_id,
            user_id=_id(),
        )
        == []
    )
    assert (
        gateway.list_projectable_chat_turns(
            conversation_id=conversation_id,
            user_id=_id(),
            message_ids=[turn.id],
        )
        == []
    )
    assert store.chat_turn_lifecycles[turn.id]["status"] == "accepted"


def test_projection_uses_linked_assistant_or_abandoned_user_message(
    lifecycle: tuple[
        MemoryChatTurnLifecycleGateway,
        AlphaStore,
        str,
        str,
    ],
) -> None:
    gateway, store, user_id, conversation_id = lifecycle
    completed_turn_id = _id()
    completed_request_id = f"request-{completed_turn_id}"
    _accept(
        gateway,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=completed_turn_id,
        request_id=completed_request_id,
    )
    assistant = _terminal_message(
        store,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=completed_turn_id,
        request_id=completed_request_id,
        status="completed",
    )
    assert (
        gateway.transition_chat_turn(
            turn_id=completed_turn_id,
            to_status="completed",
            assistant_message_id=assistant.id,
            reconciled_outcome=None,
            failure_code=None,
            retryable=False,
        ).outcome
        == "applied"
    )
    abandoned = _accept(
        gateway,
        user_id=user_id,
        conversation_id=conversation_id,
    )
    assert (
        gateway.transition_chat_turn(
            turn_id=abandoned.id,
            to_status="abandoned",
            assistant_message_id=None,
            reconciled_outcome=None,
            failure_code="turn_abandoned",
            retryable=True,
        ).outcome
        == "applied"
    )

    rows = gateway.list_projectable_chat_turns(
        conversation_id=conversation_id,
        user_id=user_id,
        message_ids=[assistant.id, abandoned.id, _id()],
    )

    assert {row["turn_id"] for row in rows} == {
        completed_turn_id,
        abandoned.id,
    }
    by_turn = {row["turn_id"]: row for row in rows}
    assert by_turn[completed_turn_id]["assistant_message_id"] == assistant.id
    assert by_turn[abandoned.id]["assistant_message_id"] is None
