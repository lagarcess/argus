"""Pure conversation operation, attention, and cursor projection rules."""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import total_ordering
from typing import Literal
from uuid import UUID

from argus.api.schemas import (
    ConversationActivity,
    ConversationAttention,
    ConversationAttentionStatus,
    ConversationOperation,
    ConversationOperationStatus,
)

SourceKind = Literal["chat_turn", "backtest_job"]

_SOURCE_KIND_RANK: dict[SourceKind, int] = {
    "chat_turn": 1,
    "backtest_job": 2,
}
_OPERATION_PRECEDENCE: dict[ConversationOperationStatus, int] = {
    "idle": 0,
    "checking": 1,
    "queued": 2,
    "running": 3,
}
_NEEDS_INPUT_OUTCOMES = {
    "await_user_reply",
    "needs_clarification",
    "await_approval",
}
_CURSOR_VERSION = 1


class CursorShapeError(ValueError):
    """The supplied attention cursor is not a canonical server cursor."""


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@total_ordering
@dataclass(frozen=True)
class Boundary:
    """Canonical read boundary ordered by time, source kind, then UUID."""

    source_kind: SourceKind
    source_id: str
    occurred_at: datetime

    def _key(self) -> tuple[datetime, int, str]:
        return (
            _utc(self.occurred_at),
            _SOURCE_KIND_RANK[self.source_kind],
            str(UUID(self.source_id)),
        )

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Boundary):
            return NotImplemented
        return self._key() < other._key()


@dataclass(frozen=True)
class CursorSource:
    """Identity decoded from the opaque cursor; timestamps stay server-side."""

    source_kind: SourceKind
    source_id: str


@dataclass(frozen=True)
class ActivityReadState:
    read_through: Boundary | None = None
    manual_unread_at: datetime | None = None


@dataclass(frozen=True)
class ActivitySource:
    """One owner-validated lifecycle/job fact used by the pure projector."""

    conversation_id: str
    source_kind: SourceKind
    source_id: str
    status: str
    occurred_at: datetime
    stage_outcome: str | None = None
    result_hydrateable: bool = False

    @property
    def boundary(self) -> Boundary:
        return Boundary(
            source_kind=self.source_kind,
            source_id=self.source_id,
            occurred_at=self.occurred_at,
        )


def encode_attention_cursor(boundary: Boundary) -> str:
    """Encode version plus source identity; durable ordering stays in storage."""

    payload = {
        "v": _CURSOR_VERSION,
        "k": boundary.source_kind,
        "i": str(UUID(boundary.source_id)),
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    return encoded.decode("ascii").rstrip("=")


def decode_attention_cursor(cursor: str) -> CursorSource:
    """Decode and structurally validate an opaque attention cursor."""

    if not cursor or len(cursor) > 256:
        raise CursorShapeError("Invalid attention cursor.")
    padding = "=" * (-len(cursor) % 4)
    try:
        decoded = base64.b64decode(
            f"{cursor}{padding}",
            altchars=b"-_",
            validate=True,
        )
        payload = json.loads(decoded.decode("utf-8"))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CursorShapeError("Invalid attention cursor.") from exc
    if not isinstance(payload, dict) or set(payload) != {"v", "k", "i"}:
        raise CursorShapeError("Invalid attention cursor.")
    if payload.get("v") != _CURSOR_VERSION:
        raise CursorShapeError("Invalid attention cursor.")
    source_kind = payload.get("k")
    if source_kind not in _SOURCE_KIND_RANK:
        raise CursorShapeError("Invalid attention cursor.")
    source_id = payload.get("i")
    if not isinstance(source_id, str):
        raise CursorShapeError("Invalid attention cursor.")
    try:
        canonical_id = str(UUID(source_id))
    except ValueError as exc:
        raise CursorShapeError("Invalid attention cursor.") from exc
    return CursorSource(source_kind=source_kind, source_id=canonical_id)


def _operation_status(source: ActivitySource) -> ConversationOperationStatus:
    if source.source_kind == "chat_turn":
        if source.status == "accepted":
            return "queued"
        if source.status == "running":
            return "running"
        return "idle"
    if source.status == "queued":
        return "queued"
    if source.status == "running":
        return "running"
    if source.status == "succeeded" and not source.result_hydrateable:
        return "checking"
    return "idle"


def terminal_attention_status(
    source: ActivitySource,
) -> ConversationAttentionStatus | None:
    if source.source_kind == "backtest_job":
        if source.status == "succeeded" and source.result_hydrateable:
            return "new_activity"
        if source.status in {"failed", "canceled", "expired"}:
            return "needs_attention"
        return None
    if source.status in {
        "recoverable_failed",
        "abandoned",
        "reconciled:recoverable_failed",
    }:
        return "needs_attention"
    if source.status not in {"completed", "reconciled:completed"}:
        return None
    if source.stage_outcome in _NEEDS_INPUT_OUTCOMES:
        return "needs_input"
    return "new_activity"


def project_conversation_activity(
    *,
    conversation_id: str,
    sources: list[ActivitySource],
    read_state: ActivityReadState | None,
) -> ConversationActivity:
    """Project one conversation without transcript text or persistence access."""

    owned_sources = [
        source for source in sources if source.conversation_id == conversation_id
    ]
    operation_candidates = [
        (source, _operation_status(source))
        for source in owned_sources
        if _operation_status(source) != "idle"
    ]
    if operation_candidates:
        operation_source, operation_status = max(
            operation_candidates,
            key=lambda item: (
                _OPERATION_PRECEDENCE[item[1]],
                _utc(item[0].occurred_at),
                _SOURCE_KIND_RANK[item[0].source_kind],
                str(UUID(item[0].source_id)),
            ),
        )
        operation = ConversationOperation(
            status=operation_status,
            kind=operation_source.source_kind,
            updated_at=operation_source.occurred_at,
        )
    else:
        operation = ConversationOperation(status="idle", kind=None, updated_at=None)

    terminal_candidates: list[
        tuple[ActivitySource, ConversationAttentionStatus]
    ] = []
    for source in owned_sources:
        terminal_status = terminal_attention_status(source)
        if terminal_status is not None:
            terminal_candidates.append((source, terminal_status))
    latest_terminal: tuple[ActivitySource, ConversationAttentionStatus] | None = None
    if terminal_candidates:
        latest_terminal = max(
            terminal_candidates,
            key=lambda item: item[0].boundary,
        )

    if latest_terminal is not None:
        terminal_source, terminal_attention = latest_terminal
        consumed = (
            read_state is not None
            and read_state.read_through is not None
            and terminal_source.boundary <= read_state.read_through
        )
        if not consumed:
            projected_attention = ConversationAttention(
                status=terminal_attention,
                cursor=encode_attention_cursor(terminal_source.boundary),
            )
        elif read_state is not None and read_state.manual_unread_at is not None:
            projected_attention = ConversationAttention(
                status="manual_unread",
                cursor=encode_attention_cursor(terminal_source.boundary),
            )
        else:
            projected_attention = ConversationAttention(status="none", cursor=None)
    elif read_state is not None and read_state.manual_unread_at is not None:
        projected_attention = ConversationAttention(
            status="manual_unread", cursor=None
        )
    else:
        projected_attention = ConversationAttention(status="none", cursor=None)

    return ConversationActivity(operation=operation, attention=projected_attention)
