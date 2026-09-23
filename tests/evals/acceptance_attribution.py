"""Allowlisted #653 attribution. Confirmed capture shape only.

A later authorized acceptance recheck needs these stored codes, and no
customer text, to name the producing path for
``unrequested_capability_refusal``:

1. top-level ``clarification.reason_code``
2. research ``declined`` and the capability-footer boolean
3. interpreter reason codes and capability verdict

This module is the single owner of that export. Historical replay drivers
must call it. Missing keys stay ``None``. Nested
``clarification.payload.reason_code`` is never the owner. This file does
not invent runtime fields, match assistant prose, or close the runtime
refusal issue.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

# Same token `research_grounded.DECLINED_REASON_CODE` writes onto an
# in-memory interpretation. This exporter does not import that module.
# The lock is `test_declined_reason_code_matches_runtime_owner`.
STORED_RESEARCH_DECLINED_CODE = "research_declined_not_a_money_request"

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

# Confirmed #653 schema. Do not add sibling keys.
FAILURE_METADATA_KEYS: tuple[str, ...] = (
    "clarification_reason",
    "research_declined",
    "research_capability_footer_appended",
    "interpreter_reason_codes",
    "capability_verdict",
    "capability_verdict_measurement_harness_derived",
)

FORBIDDEN_EXPORT_KEYS: frozenset[str] = frozenset(
    {
        "assistant_prompt",
        "assistant_response",
        "clarification_kind",
        "clarification_payload_reason",
        "clarification_prompt_source",
        "clarification_requested_field",
        "content",
        "conversation_id",
        "frames",
        "message_id",
        "metadata",
        "payload",
        "prompt",
        "raw_value",
        "recovery_code",
        "recovery_reason_code",
        "request_id",
        "research_degraded_code",
        "route_receipt_kinds",
        "stored_messages",
        "unsupported_categories",
        "user_id",
        "user_message",
    }
)

_MAX_FINITE_CODE_LEN = 80


def allowlisted_failure_metadata(
    meta: Mapping[str, Any] | None,
    *,
    harness_capability_verdict: str | None = None,
) -> dict[str, Any]:
    """Project stored turn metadata into the confirmed #653 schema.

    ``clarification_reason`` reads ``clarification.reason_code`` only.
    A nested ``payload.reason_code`` does not fill a missing owner.

    ``capability_verdict_measurement_harness_derived`` is true only when
    the exported verdict came from ``harness_capability_verdict`` because
    the stored turn had none.
    """

    stored = meta if isinstance(meta, Mapping) else {}
    clarification = _mapping(stored.get("clarification"))
    research = _mapping(stored.get("research"))
    stored_verdict = _finite_code(stored.get("capability_verdict"))
    harness_verdict = _finite_code(harness_capability_verdict)
    reason_codes = _first_code_list(stored, _REASON_CODE_PATHS)
    return {
        "clarification_reason": _finite_code(clarification.get("reason_code")),
        "research_declined": _research_declined(research, reason_codes),
        "research_capability_footer_appended": _first_bool(
            research, _CAPABILITY_FOOTER_PATHS
        ),
        "interpreter_reason_codes": reason_codes,
        "capability_verdict": stored_verdict or harness_verdict,
        "capability_verdict_measurement_harness_derived": (
            stored_verdict is None and harness_verdict is not None
        ),
    }


def allowlisted_route_row(row: Mapping[str, Any] | None) -> dict[str, Any]:
    return _project(row, ROUTE_KEYS)


def allowlisted_cost_row(row: Mapping[str, Any] | None) -> dict[str, Any]:
    return _project(row, COST_KEYS)


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
