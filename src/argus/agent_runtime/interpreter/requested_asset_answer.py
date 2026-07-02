"""Pending asset-answer completion for structured interpretation turns."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from typing import Any, Protocol

from argus.agent_runtime.interpreter.asset_grounding import (
    _prior_strategy_symbols,
    _requested_asset_answer_candidate_audit_messages,
)
from argus.agent_runtime.interpreter.audits import AssetAnswerCandidateAudit
from argus.agent_runtime.interpreter.pending_option import (
    _pending_strategy_draft_from_request_or_response,
)
from argus.agent_runtime.interpreter.shared import (
    _field_path_base,
    _selected_requested_field_base,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.resolution import AssetResolution
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import ResolutionSource
from argus.llm.openrouter import log_openrouter_failure

_REQUESTED_ASSET_ANSWER_PATCH_CODES = {
    "requested_asset_answer_candidate_audit",
    "requested_asset_answer_provider_resolution",
}


class AssetCandidateResolver(Protocol):
    def __call__(
        self,
        query: str,
        *,
        field: str,
        source: ResolutionSource,
    ) -> AssetResolution: ...


JsonSchemaInvoker = Callable[..., Awaitable[Any]]
ModelCandidateBuilder = Callable[[str], Iterable[str]]


async def requested_asset_answer_candidate_audited_response(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
    invoke_schema: JsonSchemaInvoker,
    resolve_asset_candidate: AssetCandidateResolver,
    model_candidates: ModelCandidateBuilder,
) -> LLMInterpretationResponse:
    provider_resolved = _response_from_provider_resolved_requested_asset_answer(
        response=response,
        request=request,
        resolve_asset_candidate=resolve_asset_candidate,
    )
    if provider_resolved is not None:
        return provider_resolved
    if not response_needs_requested_asset_answer_candidate_audit(
        response=response,
        request=request,
        resolve_asset_candidate=resolve_asset_candidate,
    ):
        return response
    messages = _requested_asset_answer_candidate_audit_messages(
        response=response,
        request=request,
    )
    for model_name in model_candidates(preferred_model):
        try:
            audit = await invoke_schema(
                task="interpretation",
                messages=messages,
                schema_model=AssetAnswerCandidateAudit,
                schema_name="AssetAnswerCandidateAudit",
                model_name=model_name,
            )
        except Exception as exc:
            log_openrouter_failure(
                task="interpretation",
                model_name=model_name,
                exc=exc,
                message=(
                    "Requested asset-answer candidate audit failed; trying next "
                    "candidate model"
                ),
            )
            continue
        updated = response_from_requested_asset_answer_candidate_audit(
            response=response,
            request=request,
            audit=audit,
            resolve_asset_candidate=resolve_asset_candidate,
        )
        if updated is not None:
            return updated
    return response


def response_from_requested_asset_answer_candidate_audit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
    audit: Any,
    resolve_asset_candidate: AssetCandidateResolver,
) -> LLMInterpretationResponse | None:
    if not isinstance(audit, AssetAnswerCandidateAudit) or audit.confidence < 0.6:
        return None
    candidate_symbols = [
        str(symbol or "").strip()
        for symbol in audit.candidate_symbols[:3]
        if str(symbol or "").strip()
    ]
    if audit.needs_clarification and not candidate_symbols:
        return None
    return _response_from_requested_asset_candidates(
        response=response,
        request=request,
        candidate_symbols=candidate_symbols,
        reason_code="requested_asset_answer_candidate_audit",
        resolve_asset_candidate=resolve_asset_candidate,
    )


def response_is_requested_asset_answer_patch(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
    resolve_asset_candidate: AssetCandidateResolver,
) -> bool:
    if _selected_requested_field_base(request) != "asset_universe":
        return False
    if not _REQUESTED_ASSET_ANSWER_PATCH_CODES.intersection(response.reason_codes):
        return False
    if response.semantic_turn_act != "answer_pending_need":
        return False
    if response.intent != "backtest_execution":
        return False
    if response.assistant_response:
        return False
    draft = response.candidate_strategy_draft
    return bool(
        draft.asset_universe
        and draft.asset_class
        and draft_has_valid_requested_asset_update(
            draft,
            request,
            resolve_asset_candidate=resolve_asset_candidate,
        )
    )


def response_needs_requested_asset_answer_candidate_audit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
    resolve_asset_candidate: AssetCandidateResolver,
) -> bool:
    if _selected_requested_field_base(request) != "asset_universe":
        return False
    if not request.current_user_message.strip():
        return False
    if response.semantic_turn_act in {
        "approval",
        "result_followup",
        "retry_failed_action",
    }:
        return False
    draft = response.candidate_strategy_draft
    if draft.asset_class and draft_has_valid_requested_asset_update(
        draft,
        request,
        resolve_asset_candidate=resolve_asset_candidate,
    ):
        return False
    return bool(_prior_strategy_symbols(request))


def draft_has_valid_requested_asset_update(
    draft: LLMStrategyDraft,
    request: InterpretationRequest,
    *,
    resolve_asset_candidate: AssetCandidateResolver,
) -> bool:
    return (
        _requested_asset_update_resolution(
            draft=draft,
            request=request,
            resolve_asset_candidate=resolve_asset_candidate,
        )
        is not None
    )


def _response_from_provider_resolved_requested_asset_answer(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
    resolve_asset_candidate: AssetCandidateResolver,
) -> LLMInterpretationResponse | None:
    if _selected_requested_field_base(request) != "asset_universe":
        return None
    if response.semantic_turn_act in {
        "approval",
        "educational_question",
        "result_followup",
        "retry_failed_action",
    }:
        return None
    update = _requested_asset_update_resolution(
        draft=response.candidate_strategy_draft,
        request=request,
        resolve_asset_candidate=resolve_asset_candidate,
    )
    if update is None:
        return None
    return _response_with_requested_asset_update(
        response=response,
        request=request,
        resolution=update,
        reason_code="requested_asset_answer_provider_resolution",
    )


def _response_from_requested_asset_candidates(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
    candidate_symbols: list[str],
    reason_code: str,
    resolve_asset_candidate: AssetCandidateResolver,
) -> LLMInterpretationResponse | None:
    prior_symbols = _prior_strategy_symbols(request)
    for index, candidate in enumerate(candidate_symbols):
        resolution = _resolve_requested_asset_candidate(
            candidate,
            index=index,
            resolve_asset_candidate=resolve_asset_candidate,
        )
        if resolution is None or resolution.asset is None:
            continue
        if resolution.asset.canonical_symbol in prior_symbols:
            continue
        return _response_with_requested_asset_update(
            response=response,
            request=request,
            resolution=resolution,
            reason_code=reason_code,
        )
    return None


def _response_with_requested_asset_update(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
    resolution: AssetResolution,
    reason_code: str,
) -> LLMInterpretationResponse | None:
    if resolution.asset is None:
        return None
    draft = _pending_strategy_draft_from_request_or_response(
        response=response,
        request=request,
    )
    if draft is None:
        draft = response.candidate_strategy_draft.model_copy(deep=True)
    else:
        draft = draft.model_copy(deep=True)
    draft.asset_universe = [resolution.asset.canonical_symbol]
    draft.asset_class = resolution.asset.asset_class
    draft.raw_user_phrasing = draft.raw_user_phrasing or request.current_user_message
    missing = [
        field
        for field in response.missing_required_fields
        if _field_path_base(field) != "asset_universe"
    ]
    return response.model_copy(
        update={
            "intent": "strategy_drafting" if missing else "backtest_execution",
            "task_relation": "continue",
            "requires_clarification": bool(missing),
            "candidate_strategy_draft": draft,
            "missing_required_fields": missing,
            "assistant_response": None,
            "semantic_turn_act": "answer_pending_need",
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *response.reason_codes,
                        reason_code,
                    ]
                )
            ),
        }
    )


def _requested_asset_update_resolution(
    *,
    draft: LLMStrategyDraft,
    request: InterpretationRequest,
    resolve_asset_candidate: AssetCandidateResolver,
) -> AssetResolution | None:
    prior_symbols = _prior_strategy_symbols(request)
    for index, symbol in enumerate(draft.asset_universe):
        resolution = _resolve_requested_asset_candidate(
            str(symbol or "").strip(),
            index=index,
            resolve_asset_candidate=resolve_asset_candidate,
        )
        if resolution is None or resolution.asset is None:
            continue
        if resolution.asset.canonical_symbol not in prior_symbols:
            return resolution
    return None


def _resolve_requested_asset_candidate(
    candidate: str,
    *,
    index: int,
    resolve_asset_candidate: AssetCandidateResolver,
) -> AssetResolution | None:
    if not candidate:
        return None
    try:
        resolution = resolve_asset_candidate(
            candidate,
            field=f"asset_universe[{index}]",
            source="llm_extraction",
        )
    except ValueError:
        return None
    if resolution.status != "resolved" or resolution.asset is None:
        return None
    return resolution
