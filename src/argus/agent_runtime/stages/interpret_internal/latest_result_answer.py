"""Typed routing for factual latest-result questions.

The runtime resolves which fact was asked for and whether the shared result
fact bank and the run's typed fact sheet state it; ``compose_result_conversation_answer`` writes the
user-visible answer in the detected turn language. Keep this module free of
user-visible copy, language gates, and fact-key synonym tables; unknown or
unavailable keys route to the typed limitation path.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from argus.agent_runtime.result_conversation import (
    compose_result_conversation_answer,
    stored_fact_is_stated,
)
from argus.agent_runtime.result_fact_enrichment import normalize_fact_key
from argus.agent_runtime.result_fact_figures import PAIRED_FACT_IDS
from argus.agent_runtime.result_followup_answers import (
    result_answer_sidecars,
    result_next_experiments,
    unavailable_result_followup_patch,
)
from argus.agent_runtime.result_followups import (
    public_result_followup_fact_bank,
    result_followup_fact_bank,
)
from argus.agent_runtime.stages.interpret_types import (
    InterpretDecision,
    ResultFollowupFocus,
    StageResult,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import TaskSnapshot


class LatestResultFactComposerDeclined:
    """Composer refusal for a resolved fact key. The turn is fact-shaped by
    classification but not answerable as a fact, so the caller may re-route it
    through the typed edit planner before the generic recovery chain."""

    __slots__ = ("fact_key",)

    def __init__(self, fact_key: str) -> None:
        self.fact_key = fact_key


_FACT_FOCUSES: dict[ResultFollowupFocus, str] = {
    "peak_date": "peak_date",
    "peak_value": "peak_value",
    "drawdown_date": "drawdown_date",
    "max_drawdown": "max_drawdown",
}

_FACT_ANSWER_FOCUSES: frozenset[str] = frozenset(
    {"peak_date", "peak_value", "drawdown_date", "max_drawdown", "result_card_fact"}
)

# Machine-only bank entries that are not user-askable facts.
_NON_ANSWERABLE_FACT_IDS: frozenset[str] = frozenset(
    {
        "caveat",
        "runnable_next_tests",
        "next_experiment_options",
        "context_packet_facts",
        "context_packet_limitations",
        "context_packet_ids",
        "benchmark_comparison_claim",
        "benchmark_delta_magnitude",
        "relative_performance",
        "requested_fact_unavailable",
        "available_result_facts",
    }
)


def overrides_refinement(
    interpretation: StructuredInterpretation,
    snapshot: TaskSnapshot,
    proposed: str | None,
    reason_codes: list[str],
) -> bool:
    """Keep typed latest-result questions answerable during pending refinements."""

    if (
        interpretation.semantic_turn_act != "result_followup"
        or snapshot.latest_backtest_result_reference is None
    ):
        return False
    # Claim the latest-result target only when a fact key resolves; otherwise
    # the pending-refinement misroute guard re-prompts the user.
    if _requested_fact_key(interpretation) is None:
        return False
    if proposed != "latest_result":
        reason_codes.append("latest_result_overrode_pending_refinement")
    return True


def stored_fact_key(
    *, decision: InterpretDecision, snapshot: TaskSnapshot | None
) -> str | None:
    """The stored run fact a result follow-up asked for, when the fact answer owns it."""
    if decision.semantic_turn_act != "result_followup":
        return None
    if snapshot is None or snapshot.latest_backtest_result_reference is None:
        return None
    return _requested_fact_key(decision)


async def latest_result_answer_stage_result_if_applicable(
    *,
    decision: InterpretDecision,
    snapshot: TaskSnapshot | None,
    current_user_message: str,
    language: str = "en",
    recent_messages: Sequence[Any] = (),
    compose_response_func=None,
) -> StageResult | LatestResultFactComposerDeclined | None:
    """Answer factual latest-result questions from typed intent and run facts."""

    requested_fact_key = stored_fact_key(decision=decision, snapshot=snapshot)
    reference = snapshot.latest_backtest_result_reference if snapshot else None
    if requested_fact_key is None or reference is None:
        return None
    if compose_response_func is None:
        compose_response_func = compose_result_conversation_answer

    metadata = dict(reference.metadata)
    answer_language = _answer_language(decision=decision, fallback=language)
    fact_bank = result_followup_fact_bank(metadata, language=answer_language)
    focus = _focus_for_answer(decision.result_followup_focus, requested_fact_key)
    # A stored value is answered only when the typed fact sheet states it.
    answerable = (
        requested_fact_key in fact_bank
        and requested_fact_key not in _NON_ANSWERABLE_FACT_IDS
        and stored_fact_is_stated(metadata, requested_fact_key)
    )
    rows = result_next_experiments(
        metadata, language=answer_language, source_run_id=reference.artifact_id
    )
    answer = await compose_response_func(
        metadata=metadata,
        user_message=current_user_message,
        language=answer_language,
        recent_messages=recent_messages,
        next_test_rows=rows["rows"] if rows is not None else (),
        **(
            {"requested_fact": requested_fact_key}
            if answerable
            else {"unavailable_fact": requested_fact_key}
        ),
    )
    if answer.text is None and answer.research_usage is None:
        return LatestResultFactComposerDeclined(requested_fact_key)

    if answerable:
        facts: dict[str, Any] = {
            fact_id: fact_bank[fact_id]
            for fact_id in PAIRED_FACT_IDS.get(requested_fact_key, (requested_fact_key,))
            if fact_id in fact_bank
        }
        facts["fact_key"] = requested_fact_key
        facts["source"] = "result_followup_fact_bank"
        reason_code = "latest_result_fact_answer"
        response_intent: dict[str, Any] = {"kind": "beginner_guidance", "facts": facts}
    else:
        available_facts = _available_result_facts(fact_bank)
        reason_code = "latest_result_fact_limitation"
        response_intent = {
            "kind": "unsupported_recovery",
            "facts": {
                "limitation_code": "latest_result_metric_unavailable",
                "requested_metric": requested_fact_key,
                "available_result_facts": available_facts,
            },
            "options": [
                {
                    "label": "Ask about an available result fact",
                    "label_key": "chat.result_followup.options.ask_supported",
                    "replacement_values": {
                        "semantic_turn_act": "result_followup",
                        "artifact_target": "latest_result",
                    },
                }
            ],
        }
    updated_decision = decision.model_copy(
        update={
            "intent": "conversation_followup",
            "requires_clarification": False,
            "missing_required_fields": [],
            "semantic_turn_act": "result_followup",
            "result_followup_focus": focus,
            "result_followup_fact_key": requested_fact_key,
            "reason_codes": [*decision.reason_codes, reason_code],
        }
    )
    # A paid Agent response that produced no answer still reaches the ledger.
    answer_patch = (
        {"assistant_response": answer.text, "response_intent": response_intent}
        if answer.text is not None
        else unavailable_result_followup_patch(language=answer_language)
    )
    return StageResult(
        outcome="ready_to_respond",
        decision=updated_decision,
        stage_patch={
            **answer_patch,
            **result_answer_sidecars(answer, rows),
            **_run_reference_patch(metadata=metadata, artifact_id=reference.artifact_id),
        },
    )


def _available_result_facts(fact_bank: dict[str, str]) -> list[str]:
    return sorted(
        fact_id
        for fact_id in public_result_followup_fact_bank(fact_bank)
        if fact_id not in _NON_ANSWERABLE_FACT_IDS
    )


def _answer_language(*, decision: InterpretDecision, fallback: str) -> str:
    if (
        isinstance(decision.detected_user_language, str)
        and decision.detected_user_language.strip()
    ):
        return decision.detected_user_language.strip()
    extra_parameters = decision.candidate_strategy_draft.extra_parameters
    typed_language = extra_parameters.get("language")
    if isinstance(typed_language, str) and typed_language.strip():
        return typed_language.strip()
    return fallback


def _requested_fact_key(
    decision: InterpretDecision | StructuredInterpretation,
) -> str | None:
    explicit_key = normalize_fact_key(decision.result_followup_fact_key)
    if explicit_key:
        return explicit_key
    focus = decision.result_followup_focus
    if focus is None:
        return None
    return _FACT_FOCUSES.get(focus)


def _focus_for_answer(
    focus: ResultFollowupFocus | None,
    fact_key: str,
) -> ResultFollowupFocus:
    if fact_key in _FACT_FOCUSES.values():
        return fact_key  # type: ignore[return-value]
    if focus in _FACT_ANSWER_FOCUSES:
        return focus  # type: ignore[return-value]
    return "result_card_fact"


def _run_reference_patch(
    *,
    metadata: dict[str, Any],
    artifact_id: str,
) -> dict[str, Any]:
    run_id = _string_value(
        metadata.get("run_id")
        or metadata.get("result_run_id")
        or metadata.get("latest_run_id")
        or artifact_id
    )
    patch: dict[str, Any] = {
        "result_fact_bank": metadata,
    }
    if run_id:
        patch["result_run_id"] = run_id
        patch["latest_run_id"] = _string_value(metadata.get("latest_run_id")) or run_id
    strategy_id = _string_value(
        metadata.get("strategy_id") or metadata.get("result_strategy_id")
    )
    if strategy_id:
        patch["result_strategy_id"] = strategy_id
    conversation_id = _string_value(
        metadata.get("conversation_id") or metadata.get("result_conversation_id")
    )
    if conversation_id:
        patch["result_conversation_id"] = conversation_id
    return patch


def _string_value(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
