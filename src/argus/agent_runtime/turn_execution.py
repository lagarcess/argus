"""#239 — one removable turn-wide execution budget for accepted runtime turns.

One internal controller per accepted chat turn owns: a monotonic absolute
deadline, a shared provider-call allowance, the entry/exit semantic
fingerprint, and exactly one internal terminal outcome. Provider boundaries
reserve from the shared allowance before each actual request/fallback
attempt; nested components and fallback candidates can never restart either
allowance, and task-local provider timeouts remain valid but are bounded by
the remaining turn deadline.

This is internal runtime truth for receipts and observability — it is not a
second orchestrator, not durable state, and not a public contract. #240 owns
the durable lifecycle. The whole module is removable: nothing here changes
behavior when no context is active.

Defaults are derived from existing runtime limits, never invented:

- Turn deadline: ``ARGUS_TURN_DEADLINE_SECONDS``, defaulting to the existing
  API runtime-event ceiling (``ARGUS_RUNTIME_EVENT_TIMEOUT_SECONDS``, 120s) —
  the stall bound users already experience per event becomes the whole-turn
  bound.
- Call allowance: ``ARGUS_TURN_CALL_ALLOWANCE``, defaulting to 6 — the
  audited maximal legitimate chain: structured interpretation primary plus
  its one configured fallback (2), one bounded conditional repair pass
  (plan + audit, 2), one clarification/recovery composition (1), and one
  result composition (1). The canonical simple turn remains one call, as the
  trajectory route budgets pin.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

InternalTurnOutcome = Literal[
    "completed",
    "answered",
    "recoverable_failed",
    "terminal_failed",
    "no_progress",
]

FingerprintTransition = Literal["initial", "advanced", "unchanged"]

DEFAULT_TURN_DEADLINE_SECONDS = 120.0
DEFAULT_TURN_CALL_ALLOWANCE = 6

_monotonic: Callable[[], float] = time.monotonic


def set_monotonic_for_testing(clock: Callable[[], float] | None) -> None:
    global _monotonic
    _monotonic = clock if clock is not None else time.monotonic


def turn_deadline_seconds() -> float:
    raw = os.getenv("ARGUS_TURN_DEADLINE_SECONDS", "").strip()
    if raw:
        try:
            value = float(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    event_raw = os.getenv("ARGUS_RUNTIME_EVENT_TIMEOUT_SECONDS", "").strip()
    if event_raw:
        try:
            value = float(event_raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return DEFAULT_TURN_DEADLINE_SECONDS


def turn_call_allowance() -> int:
    raw = os.getenv("ARGUS_TURN_CALL_ALLOWANCE", "").strip()
    if raw:
        try:
            value = int(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return DEFAULT_TURN_CALL_ALLOWANCE


@dataclass
class ProviderCallPermit:
    """One reserved provider attempt with its deadline-bounded timeout."""

    task: str
    timeout_seconds: float


@dataclass
class TurnExecutionContext:
    deadline_monotonic: float
    call_allowance: int
    entry_fingerprint: str | None
    calls_reserved: int = 0
    deadline_exhausted: bool = False
    calls_exhausted: bool = False
    exit_fingerprint: str | None = None
    fingerprint_transition: FingerprintTransition | None = None
    terminal: InternalTurnOutcome | None = None
    terminal_reason: str | None = None
    blocked_tasks: list[str] = field(default_factory=list)

    def remaining_deadline_seconds(self) -> float:
        return self.deadline_monotonic - _monotonic()


_ACTIVE_TURN_EXECUTION: ContextVar[TurnExecutionContext | None] = ContextVar(
    "argus_turn_execution",
    default=None,
)


def begin_turn_execution(
    *,
    deadline_seconds: float | None = None,
    call_allowance: int | None = None,
    entry_fingerprint: str | None = None,
) -> Token[TurnExecutionContext | None]:
    context = TurnExecutionContext(
        deadline_monotonic=_monotonic()
        + (deadline_seconds if deadline_seconds is not None else turn_deadline_seconds()),
        call_allowance=(
            call_allowance if call_allowance is not None else turn_call_allowance()
        ),
        entry_fingerprint=entry_fingerprint,
    )
    return _ACTIVE_TURN_EXECUTION.set(context)


def reset_turn_execution(token: Token[TurnExecutionContext | None]) -> None:
    _ACTIVE_TURN_EXECUTION.reset(token)


def active_turn_execution() -> TurnExecutionContext | None:
    return _ACTIVE_TURN_EXECUTION.get()


@contextmanager
def turn_execution_scope(
    *,
    entry_fingerprint: str | None = None,
) -> Iterator[TurnExecutionContext | None]:
    """One accepted-turn execution scope.

    Begins the context, guarantees exactly one internal terminal (paths claim
    their own; a severed exit lands the backstop), and always releases the
    context so nothing leaks into the next turn.
    """

    token = begin_turn_execution(entry_fingerprint=entry_fingerprint)
    try:
        yield _ACTIVE_TURN_EXECUTION.get()
    finally:
        claim_turn_terminal("recoverable_failed", reason="stream_severed")
        reset_turn_execution(token)


def detach_turn_execution() -> None:
    """Detach the current task from any inherited turn context.

    After-stream work is created before the route releases its scope, so the
    spawned task inherits the finished turn's mutable context; it must not
    share that turn's budget or evidence.
    """

    _ACTIVE_TURN_EXECUTION.set(None)


def mark_turn_deadline_exhausted() -> None:
    context = _ACTIVE_TURN_EXECUTION.get()
    if context is not None:
        context.deadline_exhausted = True


def reserve_provider_call(
    task: str,
    *,
    task_timeout_seconds: float | None = None,
) -> ProviderCallPermit | None:
    """Reserve one provider attempt from the shared turn allowance.

    Returns None when the turn deadline or the call allowance is exhausted —
    the caller must not perform a provider request. With no active context
    (background/after-stream work), the permit is unconstrained apart from
    the task-local timeout.
    """

    context = _ACTIVE_TURN_EXECUTION.get()
    if context is None:
        return ProviderCallPermit(
            task=task,
            timeout_seconds=(
                task_timeout_seconds
                if task_timeout_seconds is not None
                else turn_deadline_seconds()
            ),
        )
    remaining = context.remaining_deadline_seconds()
    if remaining <= 0:
        context.deadline_exhausted = True
        context.blocked_tasks.append(task)
        return None
    if context.calls_reserved >= context.call_allowance:
        context.calls_exhausted = True
        context.blocked_tasks.append(task)
        return None
    context.calls_reserved += 1
    timeout = remaining
    if task_timeout_seconds is not None:
        timeout = min(task_timeout_seconds, remaining)
    return ProviderCallPermit(task=task, timeout_seconds=timeout)


# The canonical strategy shape: typed configuration fields only. Prose
# carriers (strategy_thesis, raw_user_phrasing, entry/exit prose) never
# participate.
_STRATEGY_TYPED_FIELDS = (
    "strategy_type",
    "asset_universe",
    "asset_class",
    "timeframe",
    "cadence",
    "date_range",
    "sizing_mode",
    "capital_amount",
    "position_size",
    "comparison_baseline",
    "refinement_of",
    "entry_rule",
    "exit_rule",
    "rule_spec",
    "risk_rules",
)

# Typed identity keys a structured action's payload may carry. Everything
# else in the payload (message text, labels, replacement prose) is excluded.
_ACTION_IDENTITY_KEYS = (
    "confirmation_id",
    "failed_action_id",
    "option_id",
    "selected_option_id",
    "action_identity",
    "artifact_id",
    "strategy_id",
    "run_id",
    "message_id",
)

_NAMED_ARTIFACT_REFERENCE_KEYS = (
    "active_draft_reference",
    "active_confirmation_reference",
    "latest_backtest_result_reference",
    "latest_collection_action_reference",
    "latest_failed_action_reference",
    "saved_strategy_reference",
)

_RESULT_IDENTITY_KEYS = ("latest_run_id", "result_run_id", "result_strategy_id")


def _is_empty_fingerprint_value(value: Any) -> bool:
    return value is None or value is False or value == "" or value == [] or value == {}


def _as_state_mapping(value: Any) -> dict[str, Any] | None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="python")
    return value if isinstance(value, dict) else None


def _scalar_fingerprint_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (str, int, float, bool)):
        return value
    return None


def _canonical_structural_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="python")
    if isinstance(value, dict):
        canonical: dict[str, Any] = {}
        for key in sorted(value, key=str):
            item = _canonical_structural_value(value[key])
            if not _is_empty_fingerprint_value(item):
                canonical[str(key)] = item
        return canonical
    if isinstance(value, (list, tuple)):
        items = [
            item
            for item in (_canonical_structural_value(entry) for entry in value)
            if not _is_empty_fingerprint_value(item)
        ]
        if items and all(isinstance(item, str) for item in items):
            return sorted(items)
        return items
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _canonical_strategy(value: Any) -> dict[str, Any]:
    mapping = _as_state_mapping(value)
    if not mapping:
        return {}
    canonical: dict[str, Any] = {}
    for field_name in _STRATEGY_TYPED_FIELDS:
        item = _canonical_structural_value(mapping.get(field_name))
        if not _is_empty_fingerprint_value(item):
            canonical[field_name] = item
    return canonical


def _first_canonical_strategy(*candidates: Any) -> dict[str, Any]:
    for candidate in candidates:
        canonical = _canonical_strategy(candidate)
        if canonical:
            return canonical
    return {}


def _first_scalar(*candidates: Any) -> Any:
    for candidate in candidates:
        scalar = _scalar_fingerprint_value(candidate)
        if not _is_empty_fingerprint_value(scalar):
            return scalar
    return None


def _first_string_list(*candidates: Any) -> list[str]:
    for candidate in candidates:
        if isinstance(candidate, (list, tuple)):
            values = [str(item) for item in candidate if isinstance(item, str) and item]
            if values:
                return sorted(values)
    return []


def _action_identity(value: Any) -> dict[str, Any]:
    mapping = _as_state_mapping(value)
    if not mapping:
        return {}
    identity: dict[str, Any] = {}
    action_type = _scalar_fingerprint_value(mapping.get("type"))
    if not _is_empty_fingerprint_value(action_type):
        identity["type"] = action_type
    payload = _as_state_mapping(mapping.get("payload")) or {}
    for key in _ACTION_IDENTITY_KEYS:
        scalar = _scalar_fingerprint_value(payload.get(key))
        if not _is_empty_fingerprint_value(scalar):
            identity[key] = scalar
    return identity


def _artifact_identity(value: Any) -> dict[str, Any] | None:
    mapping = _as_state_mapping(value)
    if not mapping:
        return None
    identity: dict[str, Any] = {}
    for key in ("artifact_kind", "artifact_id", "artifact_status"):
        scalar = _scalar_fingerprint_value(mapping.get(key))
        if not _is_empty_fingerprint_value(scalar):
            identity[key] = scalar
    metadata = _as_state_mapping(mapping.get("metadata")) or {}
    version = _scalar_fingerprint_value(metadata.get("version"))
    if not _is_empty_fingerprint_value(version):
        identity["version"] = version
    return identity or None


def _artifact_identities(
    root: dict[str, Any],
    snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[Any] = []
    for source in (root.get("artifact_references"), snapshot.get("artifact_references")):
        if isinstance(source, (list, tuple)):
            candidates.extend(source)
    for key in _NAMED_ARTIFACT_REFERENCE_KEYS:
        candidates.append(snapshot.get(key))
        candidates.append(root.get(key))
    seen: set[str] = set()
    identities: list[dict[str, Any]] = []
    for candidate in candidates:
        identity = _artifact_identity(candidate)
        if identity is None:
            continue
        canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"))
        if canonical in seen:
            continue
        seen.add(canonical)
        identities.append(identity)
    identities.sort(key=lambda item: json.dumps(item, sort_keys=True))
    return identities


def semantic_turn_fingerprint(state: Any) -> str | None:
    """Deterministic hash of the turn's canonical typed semantic state.

    One projection covers every real representation of the same semantics:
    the runtime checkpoint (``run_state.candidate_strategy_draft``,
    ``latest_task_snapshot.pending_strategy_summary``, model objects) and the
    public result payload (``pending_strategy.strategy``, serialized dicts)
    normalize to the same canonical shape. Prose, localized copy, raw user
    text, structured-action message text, model names, and timestamps never
    participate. Returns None when the state carries no typed material.
    """

    root = _as_state_mapping(state)
    if root is None:
        return None
    run_state = _as_state_mapping(root.get("run_state")) or {}
    snapshot = _as_state_mapping(root.get("latest_task_snapshot")) or {}
    pending = _as_state_mapping(root.get("pending_strategy")) or {}

    projection: dict[str, Any] = {}

    stage = _first_scalar(root.get("stage_outcome"))
    if stage is not None:
        projection["stage"] = stage

    requested_field = _first_scalar(
        root.get("requested_field"),
        pending.get("requested_field"),
        run_state.get("requested_field"),
    )
    if requested_field is not None:
        projection["requested_field"] = requested_field

    missing_required = _first_string_list(
        root.get("missing_required_fields"),
        pending.get("missing_required_fields"),
        run_state.get("missing_required_fields"),
    )
    if missing_required:
        projection["missing_required_fields"] = missing_required

    strategy = _first_canonical_strategy(
        pending.get("strategy"),
        snapshot.get("pending_strategy_summary"),
        run_state.get("candidate_strategy_draft"),
    )
    if strategy:
        projection["strategy"] = strategy

    confirmed = _first_canonical_strategy(
        snapshot.get("confirmed_strategy_summary"),
        (_as_state_mapping(root.get("confirmation_payload")) or {}).get("strategy"),
        (_as_state_mapping(run_state.get("confirmation_payload")) or {}).get("strategy"),
    )
    if confirmed:
        projection["confirmed_strategy"] = confirmed

    action = _action_identity(
        root.get("structured_action") or run_state.get("structured_action")
    )
    if action:
        projection["action"] = action

    artifacts = _artifact_identities(root, snapshot)
    if artifacts:
        projection["artifacts"] = artifacts

    results = {
        key: _scalar_fingerprint_value(root.get(key))
        for key in _RESULT_IDENTITY_KEYS
        if not _is_empty_fingerprint_value(_scalar_fingerprint_value(root.get(key)))
    }
    if results:
        projection["results"] = results

    if not projection:
        return None
    canonical = json.dumps(
        projection,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def turn_budget_block_reason() -> str:
    """Receipt-facing reason for the most recent blocked reservation."""

    context = _ACTIVE_TURN_EXECUTION.get()
    if context is not None and context.remaining_deadline_seconds() <= 0:
        return "turn_deadline_exhausted"
    return "turn_call_allowance_exhausted"


def record_exit_fingerprint(
    exit_fingerprint: str | None,
) -> FingerprintTransition | None:
    context = _ACTIVE_TURN_EXECUTION.get()
    if context is None:
        return None
    context.exit_fingerprint = exit_fingerprint
    if context.entry_fingerprint is None:
        context.fingerprint_transition = "initial"
    elif exit_fingerprint == context.entry_fingerprint:
        context.fingerprint_transition = "unchanged"
    else:
        context.fingerprint_transition = "advanced"
    return context.fingerprint_transition


def no_progress_detected() -> bool:
    context = _ACTIVE_TURN_EXECUTION.get()
    return context is not None and context.fingerprint_transition == "unchanged"


def claim_turn_terminal(
    outcome: InternalTurnOutcome,
    *,
    reason: str | None = None,
) -> bool:
    """Claim the turn's single internal terminal. First claim wins; a second
    claim is a no-op and returns False."""

    context = _ACTIVE_TURN_EXECUTION.get()
    if context is None:
        return False
    if context.terminal is not None:
        return False
    context.terminal = outcome
    context.terminal_reason = reason
    return True


def turn_execution_summary(receipts: Iterable[Any]) -> dict[str, Any]:
    """Receipt-facing evidence: counts, latency, transition, exhaustion, and
    the internal terminal — never user content."""

    context = _ACTIVE_TURN_EXECUTION.get()
    receipt_list = list(receipts)
    summary: dict[str, Any] = {
        "call_count": len(receipt_list),
        "per_call_latency_ms": [
            int(getattr(receipt, "latency_ms", 0)) for receipt in receipt_list
        ],
        "total_latency_ms": sum(
            int(getattr(receipt, "latency_ms", 0)) for receipt in receipt_list
        ),
        "tasks": [str(getattr(receipt, "task", "")) for receipt in receipt_list],
        "outcomes": [str(getattr(receipt, "outcome", "")) for receipt in receipt_list],
    }
    if context is not None:
        summary.update(
            {
                "calls_reserved": context.calls_reserved,
                "call_allowance": context.call_allowance,
                "deadline_exhausted": context.deadline_exhausted,
                "calls_exhausted": context.calls_exhausted,
                "blocked_tasks": list(context.blocked_tasks),
                "fingerprint_transition": context.fingerprint_transition,
                "terminal": context.terminal,
                "terminal_reason": context.terminal_reason,
            }
        )
    return summary
