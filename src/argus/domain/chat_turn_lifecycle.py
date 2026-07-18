"""#240 — durable ordinary chat-turn lifecycle (memory twin).

One current lifecycle row per accepted non-backtest chat turn. This module is
the deterministic in-process twin of the database-owned compare-and-set
operation added by
``supabase/migrations/20260718000002_add_chat_turn_lifecycles.sql``: same
states, same allowed transitions, same no-op/conflict semantics, and the same
bounded stale-turn reconciliation predicate and ordering.

The record is recovery truth, not a second queue, chat brain, transcript, or
replacement for LangGraph checkpointer state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

TurnStatus = Literal[
    "accepted",
    "running",
    "completed",
    "recoverable_failed",
    "abandoned",
    "reconciled",
]

TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"completed", "recoverable_failed", "abandoned", "reconciled"}
)

_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "running": frozenset({"accepted"}),
    "completed": frozenset({"accepted", "running"}),
    "recoverable_failed": frozenset({"accepted", "running"}),
    "abandoned": frozenset({"accepted", "running"}),
    "reconciled": frozenset({"accepted", "running"}),
}

STALE_TURN_MINUTES = 15
STALE_TURN_BATCH = 20
ABANDONED_FAILURE_CODE = "turn_abandoned"

# Terminal metadata compatibility: persisted assistant metadata keeps the
# legacy status strings; the lifecycle maps them onto contract outcomes.
_METADATA_OUTCOMES: dict[str, str] = {
    "completed": "completed",
    "succeeded": "completed",
    "recoverable_failed": "recoverable_failed",
    "failed": "recoverable_failed",
}


@dataclass(frozen=True)
class TransitionResult:
    outcome: Literal["applied", "noop", "conflict", "missing", "invalid"]
    row: dict[str, Any] | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.isoformat()


def create_accepted_memory(
    store: Any,
    *,
    turn_id: str,
    user_id: str,
    conversation_id: str,
    request_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Acceptance: one durable lifecycle identity per accepted user message.
    Re-creating the same turn_id is a no-op returning the current row."""

    moment = now or _utcnow()
    with store.chat_turn_lifecycle_lock:
        existing = store.chat_turn_lifecycles.get(turn_id)
        if existing is not None:
            return dict(existing)
        row = {
            "turn_id": turn_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "request_id": request_id,
            "status": "accepted",
            "accepted_at": _iso(moment),
            "running_at": None,
            "finished_at": None,
            "assistant_message_id": None,
            "reconciled_outcome": None,
            "failure_code": None,
            "retryable": None,
            "created_at": _iso(moment),
            "updated_at": _iso(moment),
        }
        store.chat_turn_lifecycles[turn_id] = row
        return dict(row)


def transition_memory(
    store: Any,
    *,
    turn_id: str,
    to_status: TurnStatus,
    assistant_message_id: str | None = None,
    reconciled_outcome: str | None = None,
    failure_code: str | None = None,
    retryable: bool | None = None,
    now: datetime | None = None,
) -> TransitionResult:
    """The compare-and-set twin: verify the allowed source state, apply the
    transition and links, and return the current row. Repeating the same
    transition with the same links is a no-op; a conflicting terminal
    transition is rejected (late success never supersedes a durable failure).
    """

    if to_status == "reconciled" and reconciled_outcome not in (
        "completed",
        "recoverable_failed",
    ):
        return TransitionResult(outcome="invalid")
    if to_status != "reconciled" and reconciled_outcome is not None:
        return TransitionResult(outcome="invalid")

    moment = now or _utcnow()
    with store.chat_turn_lifecycle_lock:
        row = store.chat_turn_lifecycles.get(turn_id)
        if row is None:
            return TransitionResult(outcome="missing")

        current = str(row.get("status") or "")
        if current == to_status or (current in TERMINAL_STATUSES):
            same_links = (
                current == to_status
                and row.get("assistant_message_id") == assistant_message_id
                and row.get("reconciled_outcome") == reconciled_outcome
            )
            if same_links:
                return TransitionResult(outcome="noop", row=dict(row))
            return TransitionResult(outcome="conflict", row=dict(row))

        allowed = _ALLOWED_TRANSITIONS.get(to_status, frozenset())
        if current not in allowed:
            return TransitionResult(outcome="conflict", row=dict(row))

        row["status"] = to_status
        row["updated_at"] = _iso(moment)
        if to_status == "running":
            row["running_at"] = _iso(moment)
        else:
            row["finished_at"] = _iso(moment)
        if assistant_message_id is not None:
            row["assistant_message_id"] = assistant_message_id
        if to_status == "reconciled":
            row["reconciled_outcome"] = reconciled_outcome
        if failure_code is not None:
            row["failure_code"] = failure_code
        if retryable is not None:
            row["retryable"] = retryable
        return TransitionResult(outcome="applied", row=dict(row))


def find_active_turn_memory(
    store: Any,
    *,
    conversation_id: str,
    request_id: str,
) -> dict[str, Any] | None:
    """Locate the accepted/running lifecycle row for one request identity."""

    with store.chat_turn_lifecycle_lock:
        for row in store.chat_turn_lifecycles.values():
            if (
                row.get("conversation_id") == conversation_id
                and row.get("request_id") == request_id
                and row.get("status") in ("accepted", "running")
            ):
                return dict(row)
    return None


def _stale_since(row: dict[str, Any]) -> datetime | None:
    raw = row.get("running_at") or row.get("accepted_at")
    if isinstance(raw, str) and raw:
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _terminal_turn_evidence(message: Any, *, row: dict[str, Any]) -> str | None:
    """The complete reconciliation predicate: owner, conversation, role,
    turn_id, request_id, terminal flag, and a mapped terminal status."""

    metadata = getattr(message, "metadata", None)
    if not isinstance(metadata, dict):
        return None
    if getattr(message, "role", None) != "assistant":
        return None
    if getattr(message, "conversation_id", None) != row.get("conversation_id"):
        return None
    turn = metadata.get("agent_runtime_turn")
    if not isinstance(turn, dict):
        return None
    if turn.get("turn_id") != row.get("turn_id"):
        return None
    if turn.get("request_id") != row.get("request_id"):
        return None
    if turn.get("terminal") is not True:
        return None
    return _METADATA_OUTCOMES.get(str(turn.get("status") or ""))


def reconcile_stale_turns_memory(
    store: Any,
    *,
    conversation_id: str,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Bounded reconciliation for one conversation: at most 20 stale
    accepted/running rows in deterministic stale_since ASC, turn_id ASC order.
    Durable terminal evidence wins (failure precedence on ties); no proof
    transitions directly to abandoned with retryable typed recovery."""

    moment = now or _utcnow()
    cutoff = moment - timedelta(minutes=STALE_TURN_MINUTES)

    with store.chat_turn_lifecycle_lock:
        stale_rows = []
        for row in store.chat_turn_lifecycles.values():
            if row.get("conversation_id") != conversation_id:
                continue
            if row.get("status") not in ("accepted", "running"):
                continue
            stale_since = _stale_since(row)
            if stale_since is None or stale_since > cutoff:
                continue
            stale_rows.append((stale_since, str(row["turn_id"]), row))
        stale_rows.sort(key=lambda item: (item[0], item[1]))
        stale_rows = stale_rows[:STALE_TURN_BATCH]

    reconciled: list[dict[str, Any]] = []
    for _, _, row in stale_rows:
        candidates = []
        for message in store.messages.get(conversation_id, []):
            outcome = _terminal_turn_evidence(message, row=row)
            if outcome is None:
                continue
            precedence = 0 if outcome == "recoverable_failed" else 1
            candidates.append(
                (message.created_at, precedence, str(message.id), outcome, message)
            )
        candidates.sort(key=lambda item: (item[0], item[1], item[2]))

        if candidates:
            _, _, _, outcome, winner = candidates[0]
            result = transition_memory(
                store,
                turn_id=str(row["turn_id"]),
                to_status="reconciled",
                assistant_message_id=str(winner.id),
                reconciled_outcome=outcome,
                now=moment,
            )
        else:
            result = transition_memory(
                store,
                turn_id=str(row["turn_id"]),
                to_status="abandoned",
                failure_code=ABANDONED_FAILURE_CODE,
                retryable=True,
                now=moment,
            )
        if result.row is not None:
            reconciled.append(result.row)
    return reconciled
