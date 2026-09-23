"""Allowlisted acceptance-turn attribution for later authorized rechecks.

Issue #653 needs a later acceptance run to name the producing path for
``unrequested_capability_refusal`` without customer text. This module is the
single owner of that export shape. Historical replay drivers must call it
instead of projecting nested sidecar paths themselves.

It only copies finite reason, state, and route codes already stored on the
turn or route receipts. Missing keys stay ``None``; this file does not invent
runtime fields or read assistant prose.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

# Same token `research_grounded.DECLINED_REASON_CODE` writes onto an
# in-memory interpretation. This exporter does not import that module: the
# research runtime is not an attribution dependency. The lock is
# `test_declined_reason_code_matches_runtime_owner`.
STORED_RESEARCH_DECLINED_CODE = "research_declined_not_a_money_request"

# Lifecycle columns the historical exporters already allowlisted. Identifiers
# such as turn_id and request_id stay out.
TURN_LIFECYCLE_KEYS: tuple[str, ...] = (
    "status",
    "terminal",
    "reconciled_outcome",
    "failure_code",
    "retryable",
)

ROUTE_KEYS: tuple[str, ...] = (
    "task",
    "tier",
    "model",
    "fallback_model",
    "mode",
    "schema_name",
    "latency_ms",
    "outcome",
    "failure_mode",
    "fallback_used",
    "token_usage",
)

COST_KEYS: tuple[str, ...] = (
    "source",
    "service",
    "provider",
    "model",
    "feature_area",
    "task",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cost_amount",
    "cost_currency",
    "cost_source",
    "latency_ms",
    "status",
)

ROUTE_KIND_KEYS: tuple[str, ...] = (
    "task",
    "schema_name",
    "outcome",
    "failure_mode",
)

# Stored locations the runtime may already have written. Do not add a new
# product writer here; a missing read stays None until storage exists.
_REASON_CODE_PATHS: tuple[tuple[str, ...], ...] = (
    ("reason_codes",),
    ("interpretation", "reason_codes"),
    ("agent_runtime_turn", "reason_codes"),
    ("optional_parameter_status", "reason_codes"),
    ("pending_strategy", "reason_codes"),
    ("response_intent", "reason_codes"),
)

_CAPABILITY_FOOTER_PATHS: tuple[tuple[str, ...], ...] = (
    ("capability_footer_appended",),
    ("appended_capability_footer",),
    ("follow_up", "capability_footer_appended"),
    ("follow_up", "appended_capability_footer"),
)

_UNSUPPORTED_LIST_PATHS: tuple[tuple[str, ...], ...] = (
    ("clarification", "deferred_unsupported_categories"),
    ("unsupported",),
    ("optional_parameter_status", "unsupported_constraints"),
    ("response_intent", "facts", "unsupported_constraints"),
    ("pending_strategy", "unsupported_constraints"),
    ("pending_strategy", "optional_parameter_status", "unsupported_constraints"),
)

# #653 checklist keys. A later authorized run attributes from this schema.
FAILURE_METADATA_KEYS: tuple[str, ...] = (
    "lifecycle",
    "stage_outcome",
    "interpreter_reason_codes",
    "capability_verdict",
    "capability_verdict_measurement_harness_derived",
    "research_declined",
    "research_degraded_code",
    "research_capability_footer_appended",
    "clarification_reason",
    "clarification_payload_reason",
    "clarification_requested_field",
    "clarification_kind",
    "clarification_prompt_source",
    "recovery_code",
    "recovery_reason_code",
    "unsupported_categories",
    "route_receipt_kinds",
)

# Keys that would reintroduce customer text or identifiers into the export.
FORBIDDEN_EXPORT_KEYS: frozenset[str] = frozenset(
    {
        "assistant_prompt",
        "assistant_response",
        "content",
        "conversation_id",
        "frames",
        "message_id",
        "metadata",
        "payload",
        "prompt",
        "raw_value",
        "request_id",
        "stored_messages",
        "user_id",
        "user_message",
    }
)

_MAX_FINITE_CODE_LEN = 80


def allowlisted_failure_metadata(
    meta: Mapping[str, Any] | None,
    *,
    routes: Sequence[Mapping[str, Any]] = (),
    harness_capability_verdict: str | None = None,
) -> dict[str, Any]:
    """Project stored turn metadata into the #653 allowlisted schema.

    ``clarification_reason`` reads the contract owner
    ``clarification.reason_code``. The nested payload path is recorded
    separately and never stands in for a missing top-level reason.

    ``capability_verdict_measurement_harness_derived`` is true only when the
    exported verdict came from ``harness_capability_verdict`` because the
    stored turn had none. Runtime does not currently persist a verdict.
    """

    stored = meta if isinstance(meta, Mapping) else {}
    clarification = _mapping(stored.get("clarification"))
    payload = _mapping(clarification.get("payload"))
    research = _mapping(stored.get("research"))
    recovery = _mapping(stored.get("recovery"))
    turn = _mapping(stored.get("agent_runtime_turn"))
    stored_verdict = _finite_code(stored.get("capability_verdict"))
    harness_verdict = _finite_code(harness_capability_verdict)
    reason_codes = _first_code_list(stored, _REASON_CODE_PATHS)
    return {
        "lifecycle": _lifecycle(turn),
        "stage_outcome": _finite_code(stored.get("agent_runtime_stage_outcome")),
        "interpreter_reason_codes": reason_codes,
        "capability_verdict": stored_verdict or harness_verdict,
        "capability_verdict_measurement_harness_derived": (
            stored_verdict is None and harness_verdict is not None
        ),
        "research_declined": _research_declined(research, reason_codes),
        "research_degraded_code": _finite_code(
            _mapping(research.get("degraded")).get("code")
        ),
        "research_capability_footer_appended": _first_bool(
            research, _CAPABILITY_FOOTER_PATHS
        ),
        "clarification_reason": _finite_code(clarification.get("reason_code")),
        "clarification_payload_reason": _finite_code(payload.get("reason_code")),
        "clarification_requested_field": _finite_code(
            clarification.get("requested_field")
        ),
        "clarification_kind": _finite_code(clarification.get("kind")),
        "clarification_prompt_source": _finite_code(clarification.get("prompt_source")),
        "recovery_code": _finite_code(recovery.get("code")),
        "recovery_reason_code": _finite_code(recovery.get("reason_code")),
        "unsupported_categories": _unsupported_categories(stored, clarification),
        "route_receipt_kinds": [
            {key: allowlisted_route_row(row).get(key) for key in ROUTE_KIND_KEYS}
            for row in routes
        ],
    }


def allowlisted_route_row(row: Mapping[str, Any] | None) -> dict[str, Any]:
    return _project(row, ROUTE_KEYS)


def allowlisted_cost_row(row: Mapping[str, Any] | None) -> dict[str, Any]:
    return _project(row, COST_KEYS)


def _lifecycle(turn: Mapping[str, Any]) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for key in TURN_LIFECYCLE_KEYS:
        value = turn.get(key)
        if key in {"terminal", "retryable"}:
            projected[key] = value if isinstance(value, bool) else None
        else:
            projected[key] = _finite_code(value)
    return projected


def _research_declined(
    research: Mapping[str, Any],
    reason_codes: list[str] | None,
) -> bool | None:
    declined = research.get("declined")
    if isinstance(declined, bool):
        return declined
    declined_code = _finite_code(declined)
    if declined_code == STORED_RESEARCH_DECLINED_CODE:
        return True
    if reason_codes is not None and STORED_RESEARCH_DECLINED_CODE in reason_codes:
        return True
    return None


def _unsupported_categories(
    stored: Mapping[str, Any],
    clarification: Mapping[str, Any],
) -> list[str] | None:
    collected: list[str] = []
    seen: set[str] = set()
    found = False
    for path in _UNSUPPORTED_LIST_PATHS:
        container = (
            {"clarification": clarification} if path[0] == "clarification" else stored
        )
        raw = _walk(container, path)
        codes = _category_codes(raw)
        if codes is None:
            continue
        found = True
        for code in codes:
            if code not in seen:
                seen.add(code)
                collected.append(code)
    return collected if found else None


def _category_codes(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    codes: list[str] = []
    for item in value:
        if isinstance(item, Mapping):
            code = _finite_code(item.get("category"))
        else:
            code = _finite_code(item)
        if code is not None:
            codes.append(code)
    return codes


def _first_code_list(
    stored: Mapping[str, Any],
    paths: Sequence[tuple[str, ...]],
) -> list[str] | None:
    for path in paths:
        codes = _code_list(_walk(stored, path))
        if codes is not None:
            return codes
    return None


def _first_bool(
    stored: Mapping[str, Any],
    paths: Sequence[tuple[str, ...]],
) -> bool | None:
    for path in paths:
        value = _walk(stored, path)
        if isinstance(value, bool):
            return value
    return None


def _code_list(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    return [code for item in value if (code := _finite_code(item)) is not None]


def _project(row: Mapping[str, Any] | None, keys: Sequence[str]) -> dict[str, Any]:
    source = row if isinstance(row, Mapping) else {}
    return {key: source.get(key) for key in keys}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _walk(stored: Mapping[str, Any], path: Sequence[str]) -> Any:
    current: Any = stored
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _finite_code(value: Any) -> str | None:
    """Allow snake_case / token codes only. Prose and identifiers stay out."""

    if not isinstance(value, str):
        return None
    code = value.strip()
    if not code or len(code) > _MAX_FINITE_CODE_LEN:
        return None
    if any(character.isspace() for character in code):
        return None
    return code
