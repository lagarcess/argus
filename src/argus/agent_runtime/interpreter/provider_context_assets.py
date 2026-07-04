from __future__ import annotations

import json
from typing import Any

from argus.agent_runtime.llm_interpreter_types import (
    LLMAmbiguousField,
    LLMInterpretationResponse,
)


def response_with_provider_context_assets(
    response: LLMInterpretationResponse,
    *,
    asset_resolution_context: str | None,
) -> LLMInterpretationResponse:
    if response.intent not in {"strategy_drafting", "backtest_execution"}:
        return response
    rows = _asset_context_rows(asset_resolution_context)
    candidate_rows = [
        row
        for row in rows
        if row.get("role") in {"traded_asset", "unknown"}
        and row.get("status") in {"resolved", "ambiguous"}
    ]
    if not candidate_rows:
        return response

    resolved_symbols: list[str] = []
    asset_classes: set[str] = set()
    ambiguous_fields: list[LLMAmbiguousField] = []
    for row in candidate_rows[:5]:
        if row.get("status") == "ambiguous":
            ambiguous_fields.append(_ambiguous_field_from_context_row(row))
            continue
        symbol = str(row.get("symbol") or "").strip().upper()
        if symbol and symbol not in resolved_symbols:
            resolved_symbols.append(symbol)
        asset_class = str(row.get("asset_class") or "").strip().lower()
        if asset_class:
            asset_classes.add(asset_class)

    draft = response.candidate_strategy_draft.model_copy(deep=True)
    draft.asset_universe = resolved_symbols
    if len(asset_classes) == 1:
        draft.asset_class = next(iter(asset_classes))
    elif len(asset_classes) > 1:
        draft.asset_class = "mixed"

    if not ambiguous_fields and draft == response.candidate_strategy_draft:
        return response
    update: dict[str, Any] = {"candidate_strategy_draft": draft}
    if ambiguous_fields:
        update.update(
            {
                "intent": "strategy_drafting",
                "requires_clarification": True,
                "assistant_response": None,
                "ambiguous_fields": _dedupe_ambiguous_fields(
                    [*response.ambiguous_fields, *ambiguous_fields]
                ),
            }
        )
    return response.model_copy(update=update)


def _asset_context_rows(asset_resolution_context: str | None) -> list[dict[str, Any]]:
    if not asset_resolution_context:
        return []
    try:
        payload = json.loads(asset_resolution_context)
    except (TypeError, json.JSONDecodeError):
        return []
    rows = payload.get("asset_resolution_candidates")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _ambiguous_field_from_context_row(row: dict[str, Any]) -> LLMAmbiguousField:
    candidates = [
        str(candidate.get("symbol") or "").strip().upper()
        for candidate in row.get("candidates") or []
        if isinstance(candidate, dict) and str(candidate.get("symbol") or "").strip()
    ]
    return LLMAmbiguousField(
        field_name="asset_universe",
        raw_value=str(row.get("raw_text") or "").strip(),
        candidate_normalized_value=candidates or None,
        reason_code="asset_resolution_ambiguous",
    )


def _dedupe_ambiguous_fields(
    fields: list[LLMAmbiguousField],
) -> list[LLMAmbiguousField]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[LLMAmbiguousField] = []
    for field in fields:
        key = (field.field_name, field.raw_value, field.reason_code)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(field)
    return deduped
