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
from collections.abc import Callable, Iterable
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


# Typed containers whose contents are projected with the same allowlist.
_FINGERPRINT_CONTAINER_KEYS = frozenset(
    {
        "run_state",
        "latest_task_snapshot",
        "pending_strategy",
        "strategy",
        "candidate_strategy_draft",
        "pending_strategy_summary",
        "confirmed_strategy_summary",
        "structured_action",
        "confirmation_payload",
        "response_intent",
        "clarification",
        "recovery",
        "artifact_references",
        "active_draft_reference",
        "active_confirmation_reference",
        "latest_backtest_result_reference",
        "latest_collection_action_reference",
        "latest_failed_action_reference",
        "saved_strategy_reference",
    }
)

# Typed leaves included structurally. Prose carriers (strategy_thesis,
# raw_user_phrasing, assistant_response/prompt, labels, messages, history)
# are excluded by omission: the projection is allowlist-only.
_FINGERPRINT_TYPED_LEAF_KEYS = frozenset(
    {
        # typed stage / route
        "stage_outcome",
        "intent",
        "task_relation",
        "semantic_turn_act",
        "failure_classification",
        "kind",
        "conversation_mode",
        # pending need
        "requested_field",
        "missing_required_fields",
        "pending_needs",
        "semantic_needs",
        "requested_fields",
        "requires_clarification",
        "retryable",
        # canonical strategy fields
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
        "optional_parameters",
        # structured action + artifact identity
        "type",
        "action_type",
        "payload",
        "status",
        "artifact_kind",
        "artifact_id",
        "artifact_status",
        "version",
        # result identity
        "latest_run_id",
        "result_run_id",
        "result_strategy_id",
    }
)


def _is_empty_fingerprint_value(value: Any) -> bool:
    return value is None or value is False or value == "" or value == [] or value == {}


def _canonical_typed_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="python")
    if isinstance(value, dict):
        canonical: dict[str, Any] = {}
        for key in sorted(value, key=str):
            item = _canonical_typed_value(value[key])
            if not _is_empty_fingerprint_value(item):
                canonical[str(key)] = item
        return canonical
    if isinstance(value, (list, tuple)):
        items = [
            item
            for item in (_canonical_typed_value(entry) for entry in value)
            if not _is_empty_fingerprint_value(item)
        ]
        if items and all(isinstance(item, str) for item in items):
            return sorted(items)
        return items
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _typed_projection(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="python")
    if isinstance(value, (list, tuple)):
        return [
            item
            for item in (_typed_projection(entry) for entry in value)
            if not _is_empty_fingerprint_value(item)
        ]
    if not isinstance(value, dict):
        return None
    projection: dict[str, Any] = {}
    for key in sorted(value, key=str):
        if key in _FINGERPRINT_CONTAINER_KEYS:
            item = _typed_projection(value[key])
        elif key in _FINGERPRINT_TYPED_LEAF_KEYS:
            item = _canonical_typed_value(value[key])
        else:
            continue
        if not _is_empty_fingerprint_value(item):
            projection[str(key)] = item
    return projection


def semantic_turn_fingerprint(state: Any) -> str | None:
    """Deterministic hash of the turn's typed semantic state, or None when
    the state carries no typed material. Prose, localized copy, raw user
    text, model names, and timestamps never participate."""

    if state is None:
        return None
    projection = _typed_projection(state)
    if not isinstance(projection, dict) or not projection:
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
        "outcomes": [
            str(getattr(receipt, "outcome", "")) for receipt in receipt_list
        ],
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
