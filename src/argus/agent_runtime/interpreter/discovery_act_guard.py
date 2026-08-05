from __future__ import annotations

from collections.abc import Callable
from typing import Any

from argus.agent_runtime.interpreter.shared import (
    _llm_strategy_draft_has_extractable_fields,
)


def discovery_response_ready_for_runtime(
    *,
    response: Any,
    request: Any,
    asset_resolution_context: str | None,
    normalize: Callable[..., Any],
) -> Any | None:
    """Return the normalized discovery response when its typed shape is safe."""
    primary_act_typed = response.semantic_turn_act == "asset_discovery" or (
        response.semantic_turn_act is None
        and _response_has_unambiguous_missing_act_discovery(response)
    )
    if not primary_act_typed:
        return None
    normalized = normalize(
        response,
        request=request,
        asset_resolution_context=asset_resolution_context,
    )
    return preserve_typed_discovery_act(
        primary_act_typed=True,
        primary_discovery=response.asset_discovery,
        audited=normalized,
    )


def _response_has_unambiguous_missing_act_discovery(response: Any) -> bool:
    discovery = response.asset_discovery
    if discovery is None or response.intent != "conversation_followup":
        return False
    category = (discovery.category_description or "").strip()
    anchors = [symbol for symbol in discovery.anchor_symbols if symbol.strip()]
    if discovery.relationship == "category" and not category:
        return False
    if discovery.relationship != "category" and not (anchors or category):
        return False
    if response.requires_clarification or _llm_strategy_draft_has_extractable_fields(
        response.candidate_strategy_draft
    ):
        return False
    return not any(
        (
            response.missing_required_fields,
            response.ambiguous_fields,
            response.unsupported_constraints,
            response.uses_latest_result_context is True,
            response.result_followup_focus,
            response.result_followup_fact_key,
            response.capability_question_focus,
            response.context_question_focus,
            response.artifact_target not in {None, "none"},
        )
    )


def preserve_typed_discovery_act(
    *,
    primary_act_typed: bool,
    primary_discovery: Any | None,
    audited: Any,
) -> Any:
    """Strategy-readiness audits never own discovery-act demotion. A primary
    parse that typed asset_discovery keeps the act — payload or not; the
    missing-target recovery owns the partial shape."""
    if not primary_act_typed or audited.semantic_turn_act == "asset_discovery":
        return audited
    return audited.model_copy(
        update={
            "semantic_turn_act": "asset_discovery",
            "asset_discovery": primary_discovery,
            "intent": "conversation_followup",
            "requires_clarification": False,
            "missing_required_fields": [],
            "reason_codes": list(
                dict.fromkeys(
                    [*audited.reason_codes, "typed_discovery_act_restored"]
                )
            ),
        }
    )
