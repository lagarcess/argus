"""Typed ownership checks shared by preparation and both research entries."""

from __future__ import annotations

from typing import Any

from argus.agent_runtime.interpreter.draft_shape import strategy_has_execution_evidence
from argus.agent_runtime.interpreter.strategy_routing import strategy_route_expected
from argus.agent_runtime.research_query import ResearchQueryExtraction


def research_turn_has_conflicting_owner(interpretation: Any) -> bool:
    """A question payload cannot take execution, refusal or artifact ownership."""
    return bool(
        strategy_route_expected(
            intent=interpretation.intent,
            semantic_turn_act=interpretation.semantic_turn_act,
        )
        or strategy_has_execution_evidence(
            interpretation.candidate_strategy_draft, include_defaults=False
        )
        or interpretation.unsupported_constraints
        or interpretation.semantic_turn_act in {"result_followup", "retry_failed_action"}
        or interpretation.artifact_target not in (None, "none")
        # An explicit discovery act owns the turn even when the interpreter
        # also supplies a generic result-composition hint. Artifact targets,
        # result acts and factual result keys still protect their own route.
        or (
            interpretation.result_followup_focus
            and interpretation.semantic_turn_act != "asset_discovery"
        )
        or interpretation.result_followup_fact_key
        or interpretation.capability_question_focus
        or getattr(interpretation, "uses_latest_result_context", False)
    )


def primary_research_query(interpretation: Any) -> ResearchQueryExtraction | None:
    query = interpretation.research_query
    if query is None or query.question_kind in ("concept", "none"):
        return None
    return None if research_turn_has_conflicting_owner(interpretation) else query
