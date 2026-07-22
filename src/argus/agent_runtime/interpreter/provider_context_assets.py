from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from argus.agent_runtime.interpreter import unsupported_request_context
from argus.agent_runtime.llm_interpreter_types import (
    LLMAmbiguousField,
    LLMInterpretationResponse,
)
from argus.agent_runtime.resolution import AssetResolution
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import ResolutionProvenance
from argus.domain.market_data.assets import ResolvedAsset

_PROVIDER_RESOLVED_ASSETS_KEY = "provider_resolved_assets"


def response_with_runtime_context_assets(
    response: LLMInterpretationResponse,
    *,
    request: InterpretationRequest,
    asset_resolution_context: str | None,
) -> LLMInterpretationResponse:
    response = response_with_provider_context_assets(
        response,
        asset_resolution_context=asset_resolution_context,
        include_unsupported_request=True,
    )
    return unsupported_request_context.response_with_unsupported_request_runtime_facts(
        response,
        request=request,
    )


def _response_without_model_authored_provider_records(
    response: LLMInterpretationResponse,
) -> LLMInterpretationResponse:
    """`provider_resolved_assets` is runtime-owned.

    The model can write anything into `extra_parameters`; a hallucinated
    record must never masquerade as provider truth. The reserved key is
    cleared here, before enrichment, so only the actual runtime
    provider-context rows can populate it on every path."""

    extra_parameters = response.candidate_strategy_draft.extra_parameters or {}
    if _PROVIDER_RESOLVED_ASSETS_KEY not in extra_parameters:
        return response
    draft = response.candidate_strategy_draft.model_copy(deep=True)
    cleaned = dict(draft.extra_parameters or {})
    cleaned.pop(_PROVIDER_RESOLVED_ASSETS_KEY, None)
    draft.extra_parameters = cleaned
    return response.model_copy(update={"candidate_strategy_draft": draft})


def response_with_provider_context_assets(
    response: LLMInterpretationResponse,
    *,
    asset_resolution_context: str | None,
    include_unsupported_request: bool = False,
) -> LLMInterpretationResponse:
    response = _response_without_model_authored_provider_records(response)
    supported_intents = {"strategy_drafting", "backtest_execution"}
    if include_unsupported_request:
        supported_intents.add("unsupported_or_out_of_scope")
    if response.intent not in supported_intents:
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
    resolved_records: list[dict[str, Any]] = []
    asset_classes: set[str] = set()
    ambiguous_fields: list[LLMAmbiguousField] = []
    for row in candidate_rows[:5]:
        if row.get("status") == "ambiguous":
            ambiguous_fields.append(_ambiguous_field_from_context_row(row))
            continue
        symbol = str(row.get("symbol") or "").strip().upper()
        if symbol and symbol not in resolved_symbols:
            resolved_symbols.append(symbol)
            resolved_records.append(_resolved_asset_record_from_context_row(row))
        asset_class = str(row.get("asset_class") or "").strip().lower()
        if asset_class:
            asset_classes.add(asset_class)

    draft = response.candidate_strategy_draft.model_copy(deep=True)
    draft_assets = [
        str(value).strip()
        for value in draft.asset_universe
        if str(value).strip()
    ]
    context_is_partial = len(resolved_symbols) < len(draft_assets)
    preserved_fuller_draft = context_is_partial
    if not context_is_partial:
        draft.asset_universe = resolved_symbols
    else:
        draft_symbols = {value.upper() for value in draft_assets}
        draft.asset_universe = [
            *[symbol for symbol in resolved_symbols if symbol not in draft_symbols],
            *draft_assets,
        ]
        ambiguous_fields.append(
            _ambiguous_field_from_partial_context(
                rows=candidate_rows,
                resolved_symbols=resolved_symbols,
                reason_code="asset_resolution_context_underfilled",
            )
        )
    if len(asset_classes) == 1:
        draft.asset_class = next(iter(asset_classes))
    elif len(asset_classes) > 1:
        draft.asset_class = "mixed"
    if resolved_records:
        extra_parameters = dict(draft.extra_parameters or {})
        extra_parameters[_PROVIDER_RESOLVED_ASSETS_KEY] = resolved_records
        draft.extra_parameters = extra_parameters

    # Unsupported turns borrow resolved assets only; never escalate a refusal.
    if response.intent == "unsupported_or_out_of_scope":
        if not resolved_symbols:
            return response
        draft.asset_universe = resolved_symbols
        preserved_fuller_draft = False
        ambiguous_fields = []
    if (
        not ambiguous_fields
        and not preserved_fuller_draft
        and draft == response.candidate_strategy_draft
    ):
        return response
    update: dict[str, Any] = {"candidate_strategy_draft": draft}
    if preserved_fuller_draft:
        update["reason_codes"] = list(
            dict.fromkeys(
                [
                    *response.reason_codes,
                    "provider_context_partial_preserved_fuller_draft",
                ]
            )
        )
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


def response_with_grounded_partial_context(
    response: LLMInterpretationResponse,
) -> LLMInterpretationResponse:
    if "provider_context_partial_preserved_fuller_draft" not in response.reason_codes:
        return response
    remaining_ambiguous_fields = [
        field
        for field in response.ambiguous_fields
        if field.reason_code != "asset_resolution_context_underfilled"
    ]
    if len(remaining_ambiguous_fields) == len(response.ambiguous_fields):
        return response
    can_clear_clarification = (
        not remaining_ambiguous_fields
        and not response.missing_required_fields
        and not response.unsupported_constraints
        and response.assistant_response is None
    )
    return response.model_copy(
        update={
            "requires_clarification": (
                False if can_clear_clarification else response.requires_clarification
            ),
            "ambiguous_fields": remaining_ambiguous_fields,
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *response.reason_codes,
                        "provider_context_partial_grounded_by_current_message",
                    ]
                )
            ),
        }
    )


def resolved_asset_symbols_from_strategy_context(strategy: Any) -> list[str]:
    """Symbols of the interpreter's provider-grounded current-turn asset records."""

    extra_parameters = getattr(strategy, "extra_parameters", None)
    if not isinstance(extra_parameters, dict):
        return []
    records = extra_parameters.get(_PROVIDER_RESOLVED_ASSETS_KEY)
    if not isinstance(records, list):
        return []
    symbols: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        symbol = str(record.get("symbol") or "").strip().upper()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols


def resolution_from_strategy_context(
    strategy: Any,
    symbol: str,
    *,
    field: str,
) -> AssetResolution | None:
    record = _resolved_asset_record_for_symbol(strategy, symbol)
    if record is None:
        return None
    canonical_symbol = str(record.get("symbol") or "").strip().upper()
    asset_class = str(record.get("asset_class") or "").strip().lower()
    if asset_class not in {"equity", "crypto", "currency_pair"}:
        return None
    asset = ResolvedAsset(
        canonical_symbol=canonical_symbol,
        asset_class=asset_class,  # type: ignore[arg-type]
        name=str(record.get("name") or canonical_symbol),
        raw_symbol=str(record.get("raw_symbol") or canonical_symbol),
        provider=str(record.get("provider") or "provider_catalog"),
        exchange=str(record.get("exchange") or "") or None,
    )
    provenance = ResolutionProvenance(
        field=field,
        raw_text=str(record.get("raw_text") or symbol),
        source="llm_extraction",
        candidate_kind="asset",
        resolution_status="resolved",
        canonical_symbol=canonical_symbol,
        asset_class=asset_class,
        validated_by="provider_catalog",
        confidence="medium",
    )
    return AssetResolution(
        status="resolved",
        raw_text=symbol,
        asset=asset,
        candidates=(asset,),
        provenance=provenance,
    )


def response_with_canonical_interpreter_assets(
    response: LLMInterpretationResponse,
    *,
    resolve_asset_candidate: Callable[..., AssetResolution],
) -> LLMInterpretationResponse:
    draft = response.candidate_strategy_draft
    if response.intent not in {"strategy_drafting", "backtest_execution"}:
        return response
    if not draft.asset_universe:
        return response

    canonical_symbols: list[str] = []
    seen: set[str] = set()
    asset_classes: set[str] = set()
    changed = False
    for index, value in enumerate(draft.asset_universe):
        raw_text = str(value or "").strip()
        if not raw_text:
            changed = True
            continue
        symbol = raw_text
        try:
            resolution = resolution_from_strategy_context(
                draft,
                raw_text,
                field=f"asset_universe[{index}]",
            ) or resolve_asset_candidate(
                raw_text,
                field=f"asset_universe[{index}]",
                source="llm_extraction",
                asset_class_hint=draft.asset_class,
            )
        except Exception:
            resolution = None
        if (
            resolution is not None
            and resolution.status == "resolved"
            and resolution.asset is not None
        ):
            resolved_symbol = str(
                resolution.asset.canonical_symbol or ""
            ).strip().upper()
            if resolved_symbol:
                symbol = resolved_symbol
            asset_class = str(resolution.asset.asset_class or "").strip().lower()
            if asset_class:
                asset_classes.add(asset_class)
        if symbol != raw_text:
            changed = True
        if symbol and symbol not in seen:
            seen.add(symbol)
            canonical_symbols.append(symbol)
        elif symbol:
            changed = True

    if not canonical_symbols:
        return response
    resolved_asset_class: str | None = None
    if len(asset_classes) == 1:
        resolved_asset_class = next(iter(asset_classes))
    elif len(asset_classes) > 1:
        resolved_asset_class = "mixed"
    if resolved_asset_class and draft.asset_class != resolved_asset_class:
        changed = True
    if not changed:
        return response

    repaired_draft = draft.model_copy(deep=True)
    repaired_draft.asset_universe = canonical_symbols
    if resolved_asset_class:
        repaired_draft.asset_class = resolved_asset_class
    return response.model_copy(update={"candidate_strategy_draft": repaired_draft})


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


def _resolved_asset_record_from_context_row(row: dict[str, Any]) -> dict[str, Any]:
    symbol = str(row.get("symbol") or "").strip().upper()
    return {
        "raw_text": str(row.get("raw_text") or "").strip(),
        "symbol": symbol,
        "asset_class": str(row.get("asset_class") or "").strip().lower(),
        "name": str(row.get("name") or symbol).strip(),
        "raw_symbol": str(row.get("raw_symbol") or symbol).strip(),
        "provider": str(row.get("provider") or "provider_catalog").strip(),
        "exchange": str(row.get("exchange") or "").strip(),
    }


def _resolved_asset_record_for_symbol(
    strategy: Any,
    symbol: str,
) -> dict[str, Any] | None:
    extra_parameters = getattr(strategy, "extra_parameters", None)
    if not isinstance(extra_parameters, dict):
        return None
    records = extra_parameters.get(_PROVIDER_RESOLVED_ASSETS_KEY)
    if not isinstance(records, list):
        return None
    for record in records:
        if isinstance(record, dict) and _provider_record_matches_symbol(record, symbol):
            return record
    return None


def _provider_record_matches_symbol(record: dict[str, Any], symbol: str) -> bool:
    normalized = str(symbol or "").strip().upper()
    compact = normalized.replace("/", "")
    candidates = {
        str(record.get("symbol") or "").strip().upper(),
        str(record.get("raw_symbol") or "").strip().upper(),
        str(record.get("raw_text") or "").strip().upper(),
        str(record.get("name") or "").strip().upper(),
    }
    return any(
        candidate and candidate.replace("/", "") == compact
        for candidate in candidates
    )


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


def _ambiguous_field_from_partial_context(
    *,
    rows: list[dict[str, Any]],
    resolved_symbols: list[str],
    reason_code: str,
) -> LLMAmbiguousField:
    raw_values = [
        str(row.get("raw_text") or "").strip()
        for row in rows
        if str(row.get("raw_text") or "").strip()
    ]
    return LLMAmbiguousField(
        field_name="asset_universe",
        raw_value=", ".join(raw_values),
        candidate_normalized_value=resolved_symbols or None,
        reason_code=reason_code,
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
