"""Durable ordinary-turn recovery state and its in-memory development twin."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, cast

from argus.api.chat.previews import accepted_user_message_preview, plain_text_preview
from argus.api.schemas import Message
from argus.domain.store import AlphaStore, utcnow
from argus.domain.usage_limits import settle_memory_usage

TurnStatus = Literal[
    "accepted",
    "running",
    "completed",
    "recoverable_failed",
    "abandoned",
    "reconciled",
]
ReconciledOutcome = Literal["completed", "recoverable_failed"]
TransitionOutcome = Literal["applied", "noop", "conflict", "missing", "invalid"]

ALLOWED: dict[str, set[str]] = {
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
TERMINAL = {"completed", "recoverable_failed", "abandoned", "reconciled"}
_EVIDENCE_STATUSES = {"completed", "recoverable_failed"}
_STALE_AFTER = timedelta(minutes=15)
_RECONCILIATION_LIMIT = 20


@dataclass(frozen=True)
class TransitionResult:
    outcome: TransitionOutcome
    row: dict[str, Any] | None = None


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("Lifecycle timestamp is invalid.")
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _canonical_payload(
    *,
    to_status: str,
    assistant_message_id: str | None,
    reconciled_outcome: str | None,
    failure_code: str | None,
    retryable: bool | None,
) -> tuple[str | None, str | None, str | None, bool] | None:
    normalized_retryable = bool(retryable) if retryable is not None else False
    if to_status == "running":
        if (
            assistant_message_id is not None
            or reconciled_outcome is not None
            or failure_code is not None
            or normalized_retryable
        ):
            return None
    elif to_status == "completed":
        if (
            assistant_message_id is None
            or reconciled_outcome is not None
            or failure_code is not None
            or normalized_retryable
        ):
            return None
    elif to_status == "recoverable_failed":
        if assistant_message_id is None or reconciled_outcome is not None:
            return None
    elif to_status == "abandoned":
        if (
            assistant_message_id is not None
            or reconciled_outcome is not None
            or failure_code != "turn_abandoned"
            or not normalized_retryable
        ):
            return None
    elif to_status == "reconciled":
        if (
            assistant_message_id is None
            or reconciled_outcome not in _EVIDENCE_STATUSES
        ):
            return None
        if reconciled_outcome == "completed" and (
            failure_code is not None or normalized_retryable
        ):
            return None
    else:
        return None
    return (
        assistant_message_id,
        reconciled_outcome,
        failure_code,
        normalized_retryable,
    )


def _terminal_metadata(message: Message) -> dict[str, Any] | None:
    metadata = message.metadata
    if not isinstance(metadata, dict):
        return None
    runtime_turn = metadata.get("agent_runtime_turn")
    return runtime_turn if isinstance(runtime_turn, dict) else None


def _qualifies_as_terminal_evidence(metadata: dict[str, Any]) -> bool:
    status = metadata.get("status")
    if status == "completed":
        return True
    return (
        status == "recoverable_failed"
        and "failure_code" in metadata
        and (
            metadata["failure_code"] is None
            or isinstance(metadata["failure_code"], str)
        )
        and "retryable" in metadata
        and isinstance(metadata["retryable"], bool)
    )


class MemoryChatTurnLifecycleGateway:
    """Mirror the SQL lifecycle for hermetic development and contract tests."""

    def __init__(self, store: AlphaStore) -> None:
        self.store = store

    def accept_chat_turn(
        self,
        *,
        user_id: str,
        conversation_id: str,
        request_id: str,
        message: Message,
    ) -> Message:
        if message.conversation_id != conversation_id:
            raise ValueError("Message conversation does not match acceptance.")
        if message.role != "user":
            raise ValueError("Accepted chat-turn message must be a user message.")
        if not request_id.strip():
            raise ValueError("Lifecycle request id must not be blank.")
        with (
            self.store.chat_turn_lifecycle_lock,
            self.store.conversation_message_lock,
        ):
            if self.store.conversation_owners.get(conversation_id) != user_id:
                raise ValueError("Conversation is not owned by the user.")
            existing_row = self.store.chat_turn_lifecycles.get(message.id)
            existing_message = self._message_by_id(message.id)
            if existing_row is not None:
                if (
                    existing_row["user_id"] != user_id
                    or existing_row["conversation_id"] != conversation_id
                    or existing_row["request_id"] != request_id
                    or existing_message is None
                    or not self._same_immutable_message(existing_message, message)
                ):
                    raise ValueError(
                        "Chat-turn identity collided with a different request."
                    )
                return existing_message
            if existing_message is not None:
                if not self._same_immutable_message(existing_message, message):
                    raise ValueError(
                        "Message identity collided with a different payload."
                    )
                appended = existing_message
            else:
                appended = self._append_message(message)
            accepted_at = utcnow().isoformat()
            self.store.chat_turn_lifecycles[message.id] = {
                "turn_id": message.id,
                "user_id": user_id,
                "conversation_id": conversation_id,
                "assistant_message_id": None,
                "request_id": request_id,
                "status": "accepted",
                "reconciled_outcome": None,
                "failure_code": None,
                "retryable": False,
                "accepted_at": accepted_at,
                "running_at": None,
                "terminal_at": None,
                "reconciled_at": None,
                "created_at": accepted_at,
                "updated_at": accepted_at,
            }
            return appended

    def accept_response_option_chat_turn(
        self,
        *,
        user_id: str,
        conversation_id: str,
        request_id: str,
        message: Message,
        source_assistant_id: str | None,
        expected_source_metadata: dict[str, Any] | None,
        option_id: str | None,
        replacement_values: dict[str, Any] | None,
        request_message_id: str | None = None,
    ) -> tuple[Message, Message] | None:
        with (
            self.store.chat_turn_lifecycle_lock,
            self.store.conversation_message_lock,
        ):
            if self.store.conversation_owners.get(conversation_id) != user_id:
                return None
            if request_message_id is not None:
                return self._accept_response_option_retry(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    request_id=request_id,
                    message=message,
                    request_message_id=request_message_id,
                )
            if (
                source_assistant_id is None
                or expected_source_metadata is None
                or option_id is None
                or replacement_values is None
            ):
                return None
            messages = self.store.messages.get(conversation_id, [])
            existing = self._message_by_id(message.id)
            if existing is None:
                source = messages[-1] if messages else None
            else:
                preceding = [
                    item
                    for item in messages
                    if (item.created_at, item.id)
                    < (existing.created_at, existing.id)
                ]
                source = preceding[-1] if preceding else None
            if (
                source is None
                or source.id != source_assistant_id
                or source.role != "assistant"
                or (source.metadata or {}) != expected_source_metadata
                or not self._source_has_response_option(
                    source,
                    option_id=option_id,
                    replacement_values=replacement_values,
                )
            ):
                return None
            accepted = self.accept_chat_turn(
                user_id=user_id,
                conversation_id=conversation_id,
                request_id=request_id,
                message=message,
            )
            return source, accepted

    def _accept_response_option_retry(
        self,
        *,
        user_id: str,
        conversation_id: str,
        request_id: str,
        message: Message,
        request_message_id: str,
    ) -> tuple[Message, Message] | None:
        if message.id == request_message_id:
            return None
        original = self._message_by_id(request_message_id)
        lifecycle = self.store.chat_turn_lifecycles.get(request_message_id)
        if (
            original is None
            or lifecycle is None
            or original.role != "user"
            or original.conversation_id != conversation_id
            or lifecycle.get("user_id") != user_id
            or lifecycle.get("conversation_id") != conversation_id
            or not self._is_retryable_terminal(lifecycle)
        ):
            return None
        action = self._response_option_action(original)
        if action is None:
            return None
        action_payload = action["payload"]
        option_id = action_payload["option_id"]
        replacement_values = action_payload["replacement_values"]
        messages = self.store.messages.get(conversation_id, [])
        source = next(
            (
                item
                for item in reversed(messages)
                if (item.created_at, item.id)
                < (original.created_at, original.id)
                and item.role == "assistant"
                and self._source_has_response_option(
                    item,
                    option_id=option_id,
                    replacement_values=replacement_values,
                )
            ),
            None,
        )
        if source is None:
            return None
        canonical_metadata = {
            key: value
            for key, value in (message.metadata or {}).items()
            if key not in {"chat_action", "mentions", "resolution_provenance"}
        }
        canonical_metadata["chat_action"] = action
        canonical_message = message.model_copy(
            update={
                "content": original.content,
                "metadata": canonical_metadata,
            }
        )
        existing = self._message_by_id(message.id)
        if existing is not None:
            existing_lifecycle = self.store.chat_turn_lifecycles.get(message.id)
            if (
                existing_lifecycle is None
                or existing_lifecycle.get("user_id") != user_id
                or existing_lifecycle.get("conversation_id") != conversation_id
                or existing_lifecycle.get("request_id") != request_id
                or not self._same_immutable_message(
                    existing,
                    canonical_message,
                )
            ):
                return None
            return source, existing
        latest = messages[-1] if messages else None
        expected_latest_id = (
            original.id
            if lifecycle["status"] == "abandoned"
            else lifecycle.get("assistant_message_id")
        )
        if latest is None or latest.id != expected_latest_id:
            return None
        accepted = self.accept_chat_turn(
            user_id=user_id,
            conversation_id=conversation_id,
            request_id=request_id,
            message=canonical_message,
        )
        return source, accepted

    def finalize_chat_turn(
        self,
        *,
        user_id: str,
        conversation_id: str,
        turn_id: str,
        request_id: str,
        message: Message,
        to_status: TurnStatus,
        failure_code: str | None,
        retryable: bool,
        settle_usage: dict[str, Any] | None,
    ) -> Message:
        with (
            self.store.chat_turn_lifecycle_lock,
            self.store.conversation_message_lock,
        ):
            row = self.store.chat_turn_lifecycles.get(turn_id)
            if (
                row is None
                or row["user_id"] != user_id
                or row["conversation_id"] != conversation_id
                or row["request_id"] != request_id
                or row["status"] not in {"accepted", "running"}
            ):
                raise ValueError("Chat-turn finalization conflict.")
            if (
                message.role != "assistant"
                or message.conversation_id != conversation_id
                or to_status not in {"completed", "recoverable_failed"}
                or (to_status == "completed" and (failure_code or retryable))
                or (to_status == "recoverable_failed" and settle_usage is not None)
            ):
                raise ValueError("Chat-turn terminal payload is invalid.")
            runtime_turn = _terminal_metadata(message)
            if (
                runtime_turn is None
                or runtime_turn.get("turn_id") != turn_id
                or runtime_turn.get("request_id") != request_id
                or runtime_turn.get("status") != to_status
                or runtime_turn.get("terminal") is not True
                or (
                    to_status == "recoverable_failed"
                    and (
                        runtime_turn.get("failure_code") != failure_code
                        or runtime_turn.get("retryable") is not retryable
                    )
                )
            ):
                raise ValueError("Chat-turn terminal evidence is invalid.")
            appended = self._append_message(message)
            result = self.transition_chat_turn(
                turn_id=turn_id,
                to_status=to_status,
                assistant_message_id=appended.id,
                reconciled_outcome=None,
                failure_code=failure_code,
                retryable=retryable,
            )
            if result.outcome not in {"applied", "noop"}:
                self.store.messages[conversation_id] = [
                    item
                    for item in self.store.messages.get(conversation_id, [])
                    if item.id != appended.id
                ]
                raise ValueError("Chat-turn finalization conflict.")
            if settle_usage is not None:
                settle_memory_usage(
                    self.store.usage_counters,
                    user_id=user_id,
                    resource=settle_usage["resource"],
                    limits=settle_usage["limits"],
                )
            return appended

    def transition_chat_turn(
        self,
        *,
        turn_id: str,
        to_status: TurnStatus,
        assistant_message_id: str | None,
        reconciled_outcome: str | None,
        failure_code: str | None,
        retryable: bool | None,
    ) -> TransitionResult:
        with self.store.chat_turn_lifecycle_lock:
            row = self.store.chat_turn_lifecycles.get(turn_id)
            if row is None:
                return TransitionResult(outcome="missing")
            payload = _canonical_payload(
                to_status=to_status,
                assistant_message_id=assistant_message_id,
                reconciled_outcome=reconciled_outcome,
                failure_code=failure_code,
                retryable=retryable,
            )
            if payload is None:
                return TransitionResult(outcome="invalid", row=dict(row))
            (
                canonical_assistant_id,
                canonical_reconciled_outcome,
                canonical_failure_code,
                canonical_retryable,
            ) = payload
            if row["status"] == to_status:
                if self._matches_payload(
                    row,
                    assistant_message_id=canonical_assistant_id,
                    reconciled_outcome=canonical_reconciled_outcome,
                    failure_code=canonical_failure_code,
                    retryable=canonical_retryable,
                ):
                    return TransitionResult(outcome="noop", row=dict(row))
                return TransitionResult(outcome="conflict", row=dict(row))
            if row["status"] in TERMINAL or to_status not in ALLOWED.get(
                row["status"], set()
            ):
                return TransitionResult(outcome="conflict", row=dict(row))
            if canonical_assistant_id is not None and not self._valid_evidence(
                row,
                message_id=canonical_assistant_id,
                to_status=to_status,
                reconciled_outcome=canonical_reconciled_outcome,
                failure_code=canonical_failure_code,
                retryable=canonical_retryable,
            ):
                return TransitionResult(outcome="invalid", row=dict(row))
            now = utcnow().isoformat()
            updated = {
                **row,
                "assistant_message_id": canonical_assistant_id,
                "status": to_status,
                "reconciled_outcome": canonical_reconciled_outcome,
                "failure_code": canonical_failure_code,
                "retryable": canonical_retryable,
                "running_at": (
                    now if to_status == "running" else row.get("running_at")
                ),
                "terminal_at": now if to_status in TERMINAL else None,
                "reconciled_at": now if to_status == "reconciled" else None,
                "updated_at": now,
            }
            self.store.chat_turn_lifecycles[turn_id] = updated
            return TransitionResult(outcome="applied", row=dict(updated))

    def reconcile_stale_chat_turns(
        self,
        *,
        conversation_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        now = utcnow()
        with self.store.chat_turn_lifecycle_lock:
            stale = sorted(
                (
                    row
                    for row in self.store.chat_turn_lifecycles.values()
                    if row["user_id"] == user_id
                    and row["conversation_id"] == conversation_id
                    and row["status"] in {"accepted", "running"}
                    and self._is_stale(row, now=now)
                ),
                key=lambda row: (
                    _as_datetime(row.get("running_at") or row["accepted_at"]),
                    row["turn_id"],
                ),
            )[:_RECONCILIATION_LIMIT]
            reconciled: list[dict[str, Any]] = []
            for current in stale:
                row = self.store.chat_turn_lifecycles.get(current["turn_id"])
                if (
                    row is None
                    or row["status"] not in {"accepted", "running"}
                    or not self._is_stale(row, now=now)
                ):
                    continue
                evidence = self._first_terminal_evidence(row)
                if evidence is None:
                    result = self.transition_chat_turn(
                        turn_id=row["turn_id"],
                        to_status="abandoned",
                        assistant_message_id=None,
                        reconciled_outcome=None,
                        failure_code="turn_abandoned",
                        retryable=True,
                    )
                else:
                    metadata = cast(
                        dict[str, Any],
                        _terminal_metadata(evidence),
                    )
                    outcome = cast(ReconciledOutcome, metadata["status"])
                    result = self.transition_chat_turn(
                        turn_id=row["turn_id"],
                        to_status="reconciled",
                        assistant_message_id=evidence.id,
                        reconciled_outcome=outcome,
                        failure_code=(
                            metadata.get("failure_code")
                            if outcome == "recoverable_failed"
                            else None
                        ),
                        retryable=(
                            bool(metadata.get("retryable", False))
                            if outcome == "recoverable_failed"
                            else False
                        ),
                    )
                if result.outcome in {"applied", "noop"} and result.row is not None:
                    reconciled.append(result.row)
            return reconciled

    def list_projectable_chat_turns(
        self,
        *,
        conversation_id: str,
        user_id: str,
        message_ids: list[str],
    ) -> list[dict[str, Any]]:
        if not message_ids:
            return []
        ids = set(message_ids)
        with self.store.chat_turn_lifecycle_lock:
            rows = [
                dict(row)
                for row in self.store.chat_turn_lifecycles.values()
                if row["user_id"] == user_id
                and row["conversation_id"] == conversation_id
                and (
                    row.get("assistant_message_id") in ids
                    or row["turn_id"] in ids
                )
            ]
        return sorted(rows, key=lambda row: row["turn_id"])

    def _append_message(self, message: Message) -> Message:
        messages = self.store.messages.setdefault(message.conversation_id, [])
        appended = message
        if messages:
            latest_created_at = max(item.created_at for item in messages)
            if appended.created_at <= latest_created_at:
                appended = appended.model_copy(
                    update={
                        "created_at": latest_created_at + timedelta(microseconds=1)
                    }
                )
        messages.append(appended)
        conversation = self.store.conversations.get(message.conversation_id)
        preview = (
            accepted_user_message_preview(message.content, max_length=180)
            if message.role == "user"
            else plain_text_preview(message.content, max_length=180)
        )
        if conversation is not None and preview:
            self.store.conversations[message.conversation_id] = (
                conversation.model_copy(
                    update={
                        "last_message_preview": preview,
                        "updated_at": utcnow(),
                    }
                )
            )
        return appended

    def _message_by_id(self, message_id: str) -> Message | None:
        for messages in self.store.messages.values():
            for message in messages:
                if message.id == message_id:
                    return message
        return None

    @staticmethod
    def _source_has_response_option(
        source: Message,
        *,
        option_id: str,
        replacement_values: dict[str, Any],
    ) -> bool:
        metadata = source.metadata
        clarification = (
            metadata.get("clarification") if isinstance(metadata, dict) else None
        )
        options = (
            clarification.get("options")
            if isinstance(clarification, dict)
            else None
        )
        if not isinstance(options, list):
            return False
        return any(
            isinstance(option, dict)
            and option.get("id") == option_id
            and option.get("replacement_values") == replacement_values
            for option in options
        )

    @staticmethod
    def _response_option_action(message: Message) -> dict[str, Any] | None:
        metadata = message.metadata
        action = (
            metadata.get("chat_action") if isinstance(metadata, dict) else None
        )
        if (
            not isinstance(action, dict)
            or action.get("type") != "select_response_option"
        ):
            return None
        payload = action.get("payload")
        option_id = payload.get("option_id") if isinstance(payload, dict) else None
        replacement_values = (
            payload.get("replacement_values")
            if isinstance(payload, dict)
            else None
        )
        if (
            not isinstance(option_id, str)
            or not option_id.strip()
            or not isinstance(replacement_values, dict)
        ):
            return None
        return {
            **action,
            "payload": {
                "option_id": option_id,
                "replacement_values": replacement_values,
            },
        }

    @staticmethod
    def _is_retryable_terminal(row: dict[str, Any]) -> bool:
        if row.get("retryable") is not True:
            return False
        status = row.get("status")
        return status in {"recoverable_failed", "abandoned"} or (
            status == "reconciled"
            and row.get("reconciled_outcome") == "recoverable_failed"
        )

    @staticmethod
    def _same_immutable_message(left: Message, right: Message) -> bool:
        return (
            left.id == right.id
            and left.conversation_id == right.conversation_id
            and left.role == right.role
            and left.content == right.content
            and (left.metadata or {}) == (right.metadata or {})
        )

    @staticmethod
    def _matches_payload(
        row: dict[str, Any],
        *,
        assistant_message_id: str | None,
        reconciled_outcome: str | None,
        failure_code: str | None,
        retryable: bool,
    ) -> bool:
        return (
            row.get("assistant_message_id") == assistant_message_id
            and row.get("reconciled_outcome") == reconciled_outcome
            and row.get("failure_code") == failure_code
            and bool(row.get("retryable", False)) is retryable
        )

    def _valid_evidence(
        self,
        row: dict[str, Any],
        *,
        message_id: str,
        to_status: str,
        reconciled_outcome: str | None,
        failure_code: str | None,
        retryable: bool,
    ) -> bool:
        message = self._message_by_id(message_id)
        if message is None or message.conversation_id != row["conversation_id"]:
            return False
        metadata = _terminal_metadata(message)
        expected_status = (
            reconciled_outcome if to_status == "reconciled" else to_status
        )
        identity_matches = (
            message.role == "assistant"
            and metadata is not None
            and metadata.get("turn_id") == row["turn_id"]
            and metadata.get("request_id") == row["request_id"]
            and metadata.get("terminal") is True
            and metadata.get("status") == expected_status
        )
        if not identity_matches or expected_status != "recoverable_failed":
            return identity_matches
        return (
            "failure_code" in metadata
            and "retryable" in metadata
            and isinstance(metadata["retryable"], bool)
            and metadata["failure_code"] == failure_code
            and metadata["retryable"] is retryable
        )

    @staticmethod
    def _is_stale(row: dict[str, Any], *, now: datetime) -> bool:
        stale_since = _as_datetime(row.get("running_at") or row["accepted_at"])
        return stale_since <= now - _STALE_AFTER

    def _first_terminal_evidence(
        self,
        row: dict[str, Any],
    ) -> Message | None:
        candidates: list[tuple[datetime, int, str, Message]] = []
        for message in self.store.messages.get(row["conversation_id"], []):
            metadata = _terminal_metadata(message)
            if (
                message.role != "assistant"
                or metadata is None
                or metadata.get("turn_id") != row["turn_id"]
                or metadata.get("request_id") != row["request_id"]
                or metadata.get("terminal") is not True
                or not _qualifies_as_terminal_evidence(metadata)
            ):
                continue
            precedence = (
                0 if metadata["status"] == "recoverable_failed" else 1
            )
            candidates.append(
                (message.created_at, precedence, message.id, message)
            )
        return min(candidates)[-1] if candidates else None
