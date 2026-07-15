"""Asset-symbol normalization and grounding helpers.

Behavior-preserving relocation from llm_interpreter.py (issue #131)."""

from __future__ import annotations

from typing import Any

from argus.agent_runtime.interpreter.shared import _selected_requested_field_base
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest


def _artifact_target_from_response(
    response: LLMInterpretationResponse,
) -> str | None:
    if response.artifact_target is not None:
        return response.artifact_target
    if response.uses_latest_result_context is True:
        return "latest_result"
    if response.uses_latest_result_context is False:
        return "none"
    return None


def _provider_exact_ticker_supports_extracted_symbol(
    symbol: str,
    *,
    provider_ticker_symbol_map: dict[str, Any],
) -> bool:
    asset = provider_ticker_symbol_map.get(symbol)
    if asset is None:
        return False
    asset_class = str(getattr(asset, "asset_class", "") or "").strip()
    return asset_class in {"crypto", "currency_pair"} and len(symbol) >= 3


def _normalized_extracted_symbol(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    return normalized or None


def _normalized_extracted_symbols(values: list[Any]) -> set[str]:
    symbols: set[str] = set()
    for value in values:
        symbol = _normalized_extracted_symbol(value)
        if symbol is not None:
            symbols.add(symbol)
    return symbols


def trusted_asset_symbols(
    response: LLMInterpretationResponse,
    suspicious_symbols: list[str],
) -> list[str]:
    suspicious = _normalized_extracted_symbols(suspicious_symbols)
    return [
        symbol
        for value in response.candidate_strategy_draft.asset_universe
        if (symbol := _normalized_extracted_symbol(value)) is not None
        and symbol not in suspicious
    ]


def _comparison_baseline_has_trusted_provenance(draft: LLMStrategyDraft) -> bool:
    provenance = draft.field_provenance or {}
    return provenance.get("comparison_baseline") in {
        "explicit_user",
        "stated_run_field_fidelity_audit",
    }


def _context_inheritable_asset_symbols(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
    current_grounded_symbols: set[str],
) -> set[str]:
    if (
        response.semantic_turn_act == "answer_pending_need"
        and _selected_requested_field_base(request) != "asset_universe"
    ):
        return _prior_strategy_symbols(request)
    if current_grounded_symbols:
        return set()
    if response.semantic_turn_act not in {
        "answer_pending_need",
        "approval",
        "refine_current_idea",
        "retry_failed_action",
    }:
        return set()
    return _prior_strategy_symbols(request)


def _prior_strategy_symbols(request: InterpretationRequest) -> set[str]:
    snapshot = request.latest_task_snapshot
    if snapshot is None:
        return set()
    prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    if prior is None:
        return set()
    return {
        str(symbol).strip().upper()
        for symbol in prior.asset_universe
        if str(symbol).strip()
    }


def _requested_asset_answer_candidate_audit_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    prior = None
    snapshot = request.latest_task_snapshot
    if snapshot is not None:
        prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    interpretation_context = response.model_dump(
        mode="json",
        exclude_none=True,
        exclude={"assistant_response", "user_goal_summary"},
    )
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's asset-answer candidate audit. The user is answering "
                "a visible request to change the asset in an existing strategy draft. "
                "Use semantic meaning and common public-market knowledge to propose "
                "likely listed symbols for the current answer only. The current answer "
                "does not need to be a ticker; a well-known public company, fund, crypto "
                "asset, or currency-pair name can be mapped to likely symbols. Provider "
                "validation will verify your candidates afterward. The primary "
                "interpretation may have rejected the answer without the pending-field "
                "context; do not copy that classification. Do not preserve the prior "
                "asset unless the current answer explicitly asks for it. Do not invent "
                "support for private companies, themes, sectors, or vague references. "
                "If a common public asset maps to multiple listed share classes or "
                "similar instruments, return likely symbols in preference order so "
                "provider validation can check them. Return an empty list only when "
                "there is no credible ordering, the answer is unsupported, or it is "
                "not an asset."
            ),
        },
        {
            "role": "system",
            "content": (
                "Prior strategy JSON, if any: "
                f"{prior.model_dump(mode='json') if prior else 'none'}"
            ),
        },
        {
            "role": "system",
            "content": f"Current asset answer: {request.current_user_message.strip()}",
        },
        {
            "role": "system",
            "content": (
                "Current structured interpretation context without assistant prose: "
                f"{interpretation_context}"
            ),
        },
        {"role": "user", "content": request.current_user_message},
    ]
