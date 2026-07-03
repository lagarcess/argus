from __future__ import annotations

import json
import os
from typing import Any, Callable

from loguru import logger

from argus.agent_runtime.llm_interpreter_types import LLMAssetMentionExtraction
from argus.agent_runtime.resolution import AssetResolution
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.llm.openrouter import (
    OpenRouterTask,
    openrouter_structured_model_candidates,
)

_INTERPRETATION_REPAIR_TASK: OpenRouterTask = "interpretation_repair"


async def provider_asset_resolution_context_for_request(
    *,
    request: InterpretationRequest,
    preferred_model: str,
    invoke_schema: Callable[..., Any],
    resolve_asset_candidate: Callable[..., AssetResolution],
) -> str | None:
    if not _provider_asset_context_preflight_enabled(
        preferred_model,
        invoke_schema=invoke_schema,
    ):
        return None
    messages = _asset_mention_extraction_messages(request)
    for model_name in openrouter_structured_model_candidates(
        preferred_model,
        task=_INTERPRETATION_REPAIR_TASK,
    ):
        try:
            extraction = await invoke_schema(
                task=_INTERPRETATION_REPAIR_TASK,
                messages=messages,
                schema_model=LLMAssetMentionExtraction,
                schema_name="LLMAssetMentionExtraction",
                model_name=model_name,
            )
        except Exception as exc:
            logger.debug(
                "Provider-backed asset context extraction unavailable",
                error=type(exc).__name__,
            )
            continue
        if not isinstance(extraction, LLMAssetMentionExtraction):
            continue
        context = provider_asset_resolution_context_from_extraction(
            extraction,
            resolve_asset_candidate=resolve_asset_candidate,
        )
        if context is not None:
            return context
    return None


def provider_asset_resolution_context_from_extraction(
    extraction: LLMAssetMentionExtraction,
    *,
    resolve_asset_candidate: Callable[..., AssetResolution],
) -> str | None:
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for mention in extraction.asset_mentions[:5]:
        raw_text = str(mention.raw_text or "").strip()
        raw_key = raw_text.casefold()
        if not raw_key or raw_key in seen:
            continue
        seen.add(raw_key)
        role = mention.role if mention.role in {"traded_asset", "benchmark"} else "unknown"
        field = (
            "comparison_baseline"
            if role == "benchmark"
            else f"asset_universe[{len(rows)}]"
        )
        try:
            resolution = resolve_asset_candidate(
                raw_text,
                field=field,
                source="llm_extraction",
            )
        except ValueError:
            continue
        row = _provider_asset_resolution_context_row(
            resolution=resolution,
            role=role,
            confidence=mention.confidence,
        )
        if row is not None:
            rows.append(row)
        if len(rows) >= 5:
            break
    if not rows:
        return None
    payload = {
        "asset_resolution_candidates": rows,
        "extraction_contract": (
            "Use resolved traded_asset/unknown rows as asset_universe candidates "
            "when the user is buying, holding, testing, or including them. Use "
            "benchmark rows only as comparison_baseline. If status is ambiguous, "
            "keep the raw_text in the relevant structured field and require an "
            "asset clarification instead of choosing a symbol."
        ),
    }
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def _provider_asset_context_preflight_enabled(
    preferred_model: str,
    *,
    invoke_schema: Callable[..., Any],
) -> bool:
    if not preferred_model:
        return False
    if not (os.getenv("OPENROUTER_API_KEY") or "").strip():
        return False
    return getattr(invoke_schema, "__module__", "") == "argus.llm.openrouter"


def _asset_mention_extraction_messages(
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Asset mention extraction tool for Argus interpretation. Read only "
                "the current user message and identify exact spans that name possible "
                "public-market assets: company names, ticker symbols, crypto assets, "
                "currency pairs, benchmarks, or comparison assets. Preserve each "
                "separate same-class company-name mention when the user lists a "
                "basket. Do not infer assets from ordinary grammar, months, amounts, "
                "or strategy words. Do not canonicalize yourself; return only the "
                "short raw text span and whether the user framed it as a traded asset, "
                "a benchmark/comparison, or unknown. Return at most five distinct "
                "mentions. If none are visible, return an empty list."
            ),
        },
        {"role": "user", "content": request.current_user_message},
    ]


def _provider_asset_resolution_context_row(
    *,
    resolution: AssetResolution,
    role: str,
    confidence: float,
) -> dict[str, object] | None:
    raw_text = str(resolution.raw_text or "").strip()
    if resolution.status == "resolved" and resolution.asset is not None:
        return {
            "raw_text": raw_text,
            "role": role,
            "status": "resolved",
            "symbol": str(resolution.asset.canonical_symbol or "").strip().upper(),
            "asset_class": str(resolution.asset.asset_class or "").strip(),
            "name": str(resolution.asset.name or "").strip(),
            "confidence": confidence,
        }
    if resolution.status == "ambiguous" and resolution.candidates:
        candidates = [
            {
                "symbol": str(getattr(candidate, "canonical_symbol", "") or "")
                .strip()
                .upper(),
                "asset_class": str(getattr(candidate, "asset_class", "") or "").strip(),
                "name": str(getattr(candidate, "name", "") or "").strip(),
            }
            for candidate in resolution.candidates[:5]
        ]
        return {
            "raw_text": raw_text,
            "role": role,
            "status": "ambiguous",
            "candidates": candidates,
            "confidence": confidence,
        }
    return None
