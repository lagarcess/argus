from __future__ import annotations

from collections.abc import Callable
from typing import Any

from argus.agent_runtime.interpreter.shared import (
    _llm_strategy_draft_has_extractable_fields,
)

# Acts whose deterministic follow-through acts on prior state (approve a
# pending run, replay a failed action) or already owns a materialized
# recovery. A discovery payload never redirects these; it is dropped and
# recorded instead.
_PAYLOAD_UNPROMOTABLE_ACTS = frozenset(
    {"approval", "retry_failed_action", "unsupported_request"}
)


def discovery_response_ready_for_runtime(
    *,
    response: Any,
    request: Any,
    asset_resolution_context: str | None,
    normalize: Callable[..., Any],
) -> Any | None:
    """Return the normalized discovery response when its typed shape is safe.

    The payload is the routing truth: a coherent asset_discovery payload owns
    the turn even when the model labeled the act educational_question, because
    a discovery request is often also a genuine question and the single-choice
    act cannot say both.
    """
    act_typed = response.semantic_turn_act == "asset_discovery"
    payload_routed = (
        not act_typed
        and response.semantic_turn_act not in _PAYLOAD_UNPROMOTABLE_ACTS
        and _payload_owns_discovery_route(response)
    )
    if not (act_typed or payload_routed):
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
        payload_routed=payload_routed,
    )


def _payload_owns_discovery_route(response: Any) -> bool:
    """A filled payload routes only when the rest of the turn does not claim
    a conflicting deterministic surface (draft, clarification, results,
    capability answer)."""
    discovery = response.asset_discovery
    if discovery is None:
        return False
    category = (discovery.category_description or "").strip()
    anchors = [symbol for symbol in discovery.anchor_symbols if symbol.strip()]
    if discovery.relationship == "category" and not category:
        return False
    if discovery.relationship != "category" and not (anchors or category):
        return False
    return response_shape_open_to_discovery(response)


def response_shape_open_to_discovery(response: Any) -> bool:
    """No conflicting surface claims the turn: no draft, clarification,
    result focus, or capability answer. Shared by the payload gate and the
    focused discovery read's trigger."""
    if response.intent != "conversation_followup":
        return False
    if response.requires_clarification or _llm_strategy_draft_has_extractable_fields(
        response.candidate_strategy_draft
    ):
        return False
    # context_question_focus is deliberately not a veto: "find me trending
    # cryptos" is both market curiosity and a discovery request, and the
    # payload wins that split; promotion clears the focus.
    return not any(
        (
            response.missing_required_fields,
            response.ambiguous_fields,
            response.unsupported_constraints,
            response.uses_latest_result_context is True,
            response.result_followup_focus,
            response.result_followup_fact_key,
            response.capability_question_focus,
            response.artifact_target not in {None, "none"},
        )
    )


def preserve_typed_discovery_act(
    *,
    primary_act_typed: bool,
    primary_discovery: Any | None,
    audited: Any,
    payload_routed: bool = False,
) -> Any:
    """Strategy-readiness audits never own discovery-act demotion. A primary
    parse that typed asset_discovery keeps the act — payload or not; the
    missing-target recovery owns the partial shape."""
    if not primary_act_typed or audited.semantic_turn_act == "asset_discovery":
        return audited
    reason_code = (
        "discovery_payload_act_promoted"
        if payload_routed
        else "typed_discovery_act_restored"
    )
    update: dict[str, Any] = {
        "semantic_turn_act": "asset_discovery",
        "asset_discovery": primary_discovery,
        "intent": "conversation_followup",
        "requires_clarification": False,
        "missing_required_fields": [],
        "reason_codes": list(dict.fromkeys([*audited.reason_codes, reason_code])),
    }
    if payload_routed:
        update["context_question_focus"] = None
    return audited.model_copy(update=update)


def response_without_unroutable_discovery_payload(response: Any) -> Any:
    """Clear a payload the route refused; downstream owners key on presence.

    knowledge_answer stands down whenever the payload exists, and the
    composer routes on it, so a payload that lost the coherence check would
    otherwise leave the turn with no owner at all.
    """
    if (
        response.asset_discovery is None
        or response.semantic_turn_act == "asset_discovery"
    ):
        return response
    return response.model_copy(
        update={
            "asset_discovery": None,
            "reason_codes": list(
                dict.fromkeys(
                    [*response.reason_codes, "discovery_payload_dropped_unroutable"]
                )
            ),
        }
    )
