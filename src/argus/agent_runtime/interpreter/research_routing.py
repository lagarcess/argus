"""Typed ownership checks shared by preparation and both research entries."""

from __future__ import annotations

from typing import Any

from argus.agent_runtime.interpreter.draft_shape import strategy_has_execution_evidence
from argus.agent_runtime.interpreter.strategy_routing import route_owner
from argus.agent_runtime.research_query import ResearchQueryExtraction


def research_turn_has_conflicting_owner(interpretation: Any) -> bool:
    """A question payload cannot take execution, refusal or artifact ownership."""
    return bool(
        getattr(interpretation, "uses_tool_catalog", False)
        or getattr(interpretation, "tool_calls", None)
        or route_owner(
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


def primary_read_asks_a_fact_question(interpretation: Any) -> bool:
    """Read research payloads only for historical, noncatalog interpretations."""
    if getattr(interpretation, "uses_tool_catalog", False) or getattr(
        interpretation, "tool_calls", None
    ):
        return False
    query = getattr(interpretation, "research_query", None)
    return query is not None and query.question_kind not in ("concept", "none")


def primary_research_query(interpretation: Any) -> ResearchQueryExtraction | None:
    if not primary_read_asks_a_fact_question(interpretation):
        return None
    query = interpretation.research_query
    return None if research_turn_has_conflicting_owner(interpretation) else query
