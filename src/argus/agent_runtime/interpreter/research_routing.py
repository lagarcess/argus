"""Typed ownership checks shared by preparation and both research entries."""

from __future__ import annotations

from typing import Any

from loguru import logger

from argus.agent_runtime.interpreter.draft_shape import (
    strategy_draft_future_horizon,
    strategy_has_execution_evidence,
)
from argus.agent_runtime.interpreter.strategy_routing import route_owner
from argus.agent_runtime.research_query import ResearchQueryExtraction

# Recorded on the interpretation when a strategy claim was set aside because
# its horizon points forward: the question was answered by research, not
# refused as a test that cannot run (decision 10).
FUTURE_HORIZON_QUESTION_REASON_CODE = "research_answers_future_horizon_question"


def _strategy_route_claims_the_turn(interpretation: Any) -> bool:
    return bool(
        route_owner(
            intent=interpretation.intent,
            semantic_turn_act=interpretation.semantic_turn_act,
        )
        or strategy_has_execution_evidence(
            interpretation.candidate_strategy_draft, include_defaults=False
        )
    )


def strategy_claim_waived_by_future_horizon(interpretation: Any) -> bool:
    """A strategy claim over a future horizon is not a runnable test.

    There is no market data for a period that has not happened yet, so the
    claim cannot own the turn: the question it arrived with is what research
    answers, and the horizon survives typed for the answer's next steps."""
    return _strategy_route_claims_the_turn(interpretation) and bool(
        strategy_draft_future_horizon(interpretation.candidate_strategy_draft)
    )


def research_turn_has_conflicting_owner(interpretation: Any) -> bool:
    """A question payload cannot take execution, refusal or artifact ownership."""
    return bool(
        (
            _strategy_route_claims_the_turn(interpretation)
            and not strategy_claim_waived_by_future_horizon(interpretation)
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
    """The primary read typed the message as a finance fact question."""
    query = getattr(interpretation, "research_query", None)
    return query is not None and query.question_kind not in ("concept", "none")


def primary_research_query(interpretation: Any) -> ResearchQueryExtraction | None:
    if not primary_read_asks_a_fact_question(interpretation):
        return None
    if research_turn_has_conflicting_owner(interpretation):
        return None
    if strategy_claim_waived_by_future_horizon(interpretation):
        _note_future_horizon_question(interpretation)
    return interpretation.research_query


def _note_future_horizon_question(interpretation: Any) -> None:
    """Record that a strategy claim was set aside for a future horizon."""
    if FUTURE_HORIZON_QUESTION_REASON_CODE in interpretation.reason_codes:
        return
    interpretation.reason_codes.append(FUTURE_HORIZON_QUESTION_REASON_CODE)
    draft = interpretation.candidate_strategy_draft
    logger.info(
        "Research answers a future-horizon question over a strategy claim "
        "intent={} act={} assets={} horizon={}",
        interpretation.intent,
        interpretation.semantic_turn_act,
        list(getattr(draft, "asset_universe", None) or []),
        (strategy_draft_future_horizon(draft) or {}).get("evidence"),
        failure_classification=FUTURE_HORIZON_QUESTION_REASON_CODE,
    )
