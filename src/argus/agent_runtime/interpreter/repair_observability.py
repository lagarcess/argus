from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel

_RESPONSE_TEXT_FIELDS = frozenset({"assistant_response", "user_goal_summary"})
_DRAFT_TEXT_FIELDS = frozenset(
    {
        "date_range_raw_text",
        "evidence_spans",
        "raw_user_phrasing",
        "strategy_thesis",
    }
)


def repair_effect_metadata(
    *,
    before: BaseModel,
    after: BaseModel,
    trigger_reason: str,
    repair_applied: bool,
    no_op_reason: str | None = None,
) -> dict[str, object]:
    """Describe a repair without retaining user text or interpreted values."""

    before_projection = _fingerprint_projection(before)
    after_projection = _fingerprint_projection(after)
    changed_fields = _changed_field_names(
        before_projection,
        after_projection,
    )
    typed_change_applied = repair_applied and bool(changed_fields)
    resolved_no_op_reason = no_op_reason
    if repair_applied and not typed_change_applied and resolved_no_op_reason is None:
        resolved_no_op_reason = "no_typed_change"
    return {
        "schema_version": "argus_repair_effect/v1",
        "trigger_reason": trigger_reason,
        "repair_applied": typed_change_applied,
        "changed_fields": changed_fields,
        "before_fingerprint": _projection_fingerprint(before_projection),
        "after_fingerprint": _projection_fingerprint(after_projection),
        "no_op_reason": resolved_no_op_reason,
    }


def _fingerprint_projection(response: BaseModel) -> dict[str, Any]:
    projection = response.model_dump(mode="json")
    for field_name in _RESPONSE_TEXT_FIELDS:
        projection.pop(field_name, None)
    draft = projection.get("candidate_strategy_draft")
    if isinstance(draft, dict):
        for field_name in _DRAFT_TEXT_FIELDS:
            draft.pop(field_name, None)
    return projection


def _projection_fingerprint(projection: dict[str, Any]) -> str:
    encoded = json.dumps(
        projection,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _changed_field_names(
    before: dict[str, Any],
    after: dict[str, Any],
) -> list[str]:
    changed: list[str] = []
    draft_field = "candidate_strategy_draft"
    for field_name in sorted(set(before) | set(after)):
        if field_name == draft_field:
            continue
        if before.get(field_name) != after.get(field_name):
            changed.append(field_name)
    before_draft = before.get(draft_field)
    after_draft = after.get(draft_field)
    if isinstance(before_draft, dict) and isinstance(after_draft, dict):
        for field_name in sorted(set(before_draft) | set(after_draft)):
            if before_draft.get(field_name) != after_draft.get(field_name):
                changed.append(f"{draft_field}.{field_name}")
    elif before_draft != after_draft:
        changed.append(draft_field)
    return sorted(changed)
