"""Regression coverage for issue #345 result recommendation continuity."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

import pytest
from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.llm_clarifier import ClarificationRequest
from argus.agent_runtime.runtime import run_agent_turn
from argus.agent_runtime.stages.interpret import (
    StructuredInterpretation,
    interpret_stage,
)
from argus.agent_runtime.state.models import (
    ArtifactReference,
    RunState,
    StrategySummary,
    TaskSnapshot,
    UserState,
)
from argus.api.chat.actions import chat_request_message
from argus.api.schemas import ChatStreamRequest
from langgraph.checkpoint.memory import MemorySaver


@dataclass(frozen=True)
class _ResolvedAssetStub:
    canonical_symbol: str
    asset_class: str
    name: str = ""
    raw_symbol: str = ""


class _RecordingClarifier:
    def __init__(self, response: str) -> None:
        self.response = response
        self.requests: list[ClarificationRequest] = []

    def __call__(self, request: ClarificationRequest) -> str:
        self.requests.append(request)
        return self.response


def _source_result() -> ArtifactReference:
    realism = {
        "enabled": True,
        "fee_bps": 40.0,
        "slippage_bps": 0.25,
    }
    return ArtifactReference(
        artifact_kind="backtest_result",
        artifact_id="run-345-source",
        artifact_status="completed",
        metadata={
            "run_id": "run-345-source",
            "asset_class": "equity",
            "symbols": ["WMT", "HD", "TGT"],
            "benchmark_symbol": "SPY",
            "config_snapshot": {
                "template": "dca_accumulation",
                "symbols": ["WMT", "HD", "TGT"],
                "date_range": {
                    "start": "2021-01-04",
                    "end": "2025-12-31",
                },
                "resolved_strategy": {
                    "strategy_type": "dca_accumulation",
                    "strategy_thesis": "Buy WMT, HD, and TGT every week.",
                    "asset_universe": ["WMT", "HD", "TGT"],
                    "asset_class": "equity",
                    "date_range": {
                        "start": "2021-01-04",
                        "end": "2025-12-31",
                    },
                },
                "resolved_parameters": {
                    "timeframe": "1D",
                    "capital_amount": 1000,
                    "recurring_contribution": 1000,
                    "cadence": "weekly",
                    "benchmark_symbol": "SPY",
                    "engine_config": {"_execution_realism": dict(realism)},
                },
                "engine_config": {"_execution_realism": dict(realism)},
            },
        },
    )


def _recommendation_action(kind: str, label: str) -> dict[str, object]:
    return {
        "type": "refine_strategy",
        "label": label,
        "presentation": "result",
        "payload": {
            "run_id": "run-345-source",
            "next_experiment_kind": kind,
        },
    }


def _recommendation_state(kind: str, label: str) -> RunState:
    return RunState.new(
        current_user_message=label,
        recent_thread_history=[],
        action_context=_recommendation_action(kind, label),
    )


def _snapshot(reference: ArtifactReference) -> TaskSnapshot:
    return TaskSnapshot(
        latest_task_type="results_explanation",
        completed=True,
        latest_backtest_result_reference=reference,
        artifact_references=[reference],
    )


def _assert_source_is_unchanged(
    source: ArtifactReference,
    before: dict[str, object],
) -> None:
    assert source.metadata == before


def _assert_owned_facts(strategy: StrategySummary) -> None:
    assert strategy.asset_universe == ["WMT", "HD", "TGT"]
    assert strategy.asset_class == "equity"
    assert strategy.capital_amount == 1000
    assert strategy.timeframe == "1D"
    assert strategy.comparison_baseline == "SPY"
    assert strategy.extra_parameters["fee_rate"] == 0.004
    assert strategy.extra_parameters["slippage"] == 0.000025
    assert strategy.extra_parameters["field_provenance"] == {
        "fee_rate": "explicit_user",
        "slippage": "explicit_user",
    }


@pytest.mark.parametrize(
    ("language", "label_key", "kind", "expected"),
    [
        (
            "en",
            "chat.next_experiments.labels.change_date_range",
            "change_date_range",
            "Test a different date range",
        ),
        (
            "es-419",
            "chat.next_experiments.labels.change_date_range",
            "change_date_range",
            "Probar otro rango de fechas",
        ),
        (
            "en",
            "chat.next_experiments.labels.compare_buy_and_hold",
            "compare_buy_and_hold",
            "Compare with buy and hold",
        ),
        (
            "es-419",
            "chat.next_experiments.labels.compare_buy_and_hold",
            "compare_buy_and_hold",
            "Comparar con comprar y mantener",
        ),
    ],
)
def test_continuity_recommendation_uses_server_localized_label(
    language: str,
    label_key: str,
    kind: str,
    expected: str,
) -> None:
    request = ChatStreamRequest(
        conversation_id="conversation-345",
        language=language,
        action={
            "type": "refine_strategy",
            "label": "forged label",
            "labelKey": f"{label_key}.forged",
            "presentation": "result",
            "payload": {
                "run_id": "run-345-source",
                "next_experiment_kind": kind,
            },
        },
    )

    assert chat_request_message(request, language=language) == expected


def test_dca_compare_recommendation_builds_buy_and_hold_confirmation_from_source() -> (
    None
):
    source = _source_result()
    source_before = deepcopy(source.metadata)

    result = interpret_stage(
        state=_recommendation_state(
            "compare_buy_and_hold",
            "Compare with buy and hold",
        ),
        user=UserState(user_id="u-345"),
        latest_task_snapshot=_snapshot(source),
        selected_thread_metadata={
            "next_experiments_offered_kinds": ["compare_buy_and_hold"],
        },
        structured_interpreter=None,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.requested_strategy_template == "buy_and_hold"
    assert strategy.cadence is None
    assert strategy.date_range == {
        "start": "2021-01-04",
        "end": "2025-12-31",
    }
    _assert_owned_facts(strategy)
    _assert_source_is_unchanged(source, source_before)


@pytest.mark.parametrize(
    ("language", "date_reply"),
    [
        (
            "en",
            "Use January 3 through December 29, 2023.",
        ),
        (
            "es-419",
            "Usa del 3 de enero al 29 de diciembre de 2023.",
        ),
    ],
)
def test_date_range_recommendation_routes_anchored_draft_to_clarifier(
    monkeypatch: pytest.MonkeyPatch,
    language: str,
    date_reply: str,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: _ResolvedAssetStub(symbol.upper(), "equity"),
    )
    source = _source_result()
    source_before = deepcopy(source.metadata)

    result = interpret_stage(
        state=_recommendation_state(
            "change_date_range",
            "Test a different date range",
        ),
        user=UserState(user_id="u-345", language_preference=language),
        latest_task_snapshot=_snapshot(source),
        selected_thread_metadata={
            "next_experiments_offered_kinds": ["change_date_range"],
        },
        structured_interpreter=lambda _: pytest.fail(
            "the typed date action must not become a generic result follow-up"
        ),
    )

    assert result.outcome == "needs_clarification"
    assert "assistant_prompt" not in result.patch
    assert result.patch["requested_field"] == "date_range"
    assert result.patch["missing_required_fields"] == ["date_range"]
    strategy = StrategySummary.model_validate(result.patch["candidate_strategy_draft"])
    assert strategy.strategy_type == "dca_accumulation"
    assert strategy.cadence == "weekly"
    assert strategy.date_range == {
        "start": "2021-01-04",
        "end": "2025-12-31",
    }
    _assert_owned_facts(strategy)
    _assert_source_is_unchanged(source, source_before)

    interpretation = StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="Use the requested replacement date range.",
        candidate_strategy_draft=StrategySummary(
            date_range={"start": "2023-01-03", "end": "2023-12-29"},
            extra_parameters={
                "date_range_raw_text": date_reply,
                "date_range_intent": {
                    "kind": "explicit_range",
                    "start": "2023-01-03",
                    "end": "2023-12-29",
                    "evidence": date_reply,
                },
                "field_provenance": {"date_range": "explicit_user"},
            },
        ),
        semantic_turn_act="answer_pending_need",
    )
    confirmation = interpret_stage(
        state=RunState.new(
            current_user_message=date_reply,
            recent_thread_history=[],
        ),
        user=UserState(user_id="u-345", language_preference=language),
        latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=strategy,
            latest_backtest_result_reference=source,
            artifact_references=[source],
        ),
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "date_range",
            "response_intent": result.patch["response_intent"],
        },
        structured_interpreter=lambda _: interpretation,
    )

    assert confirmation.outcome == "ready_for_confirmation", (
        confirmation.decision,
        confirmation.patch,
    )
    patched = confirmation.decision.candidate_strategy_draft
    assert patched.strategy_type == "dca_accumulation"
    assert patched.cadence == "weekly"
    assert patched.date_range == {
        "start": "2023-01-03",
        "end": "2023-12-29",
    }
    _assert_owned_facts(patched)
    _assert_source_is_unchanged(source, source_before)


def test_date_range_answer_repairs_misrouted_model_output_with_result_anchor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: _ResolvedAssetStub(symbol.upper(), "equity"),
    )
    source = _source_result()
    clarification = interpret_stage(
        state=_recommendation_state(
            "change_date_range",
            "Test a different date range",
        ),
        user=UserState(user_id="u-345"),
        latest_task_snapshot=_snapshot(source),
        selected_thread_metadata={
            "next_experiments_offered_kinds": ["change_date_range"],
        },
        structured_interpreter=None,
    )
    pending = StrategySummary.model_validate(
        clarification.patch["candidate_strategy_draft"]
    )
    model_output = StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary="User supplied the requested replacement date range.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="dca_accumulation",
        ),
        semantic_turn_act="refine_current_idea",
        reason_codes=["date_range_refinement"],
    )

    confirmation = interpret_stage(
        state=RunState.new(
            current_user_message="Use Jan 3 through Dec 29, 2023.",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u-345"),
        latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=pending,
            latest_backtest_result_reference=source,
            artifact_references=[source],
        ),
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "date_range",
            "response_intent": clarification.patch["response_intent"],
        },
        structured_interpreter=lambda _: model_output,
    )

    assert confirmation.outcome == "ready_for_confirmation"
    patched = confirmation.decision.candidate_strategy_draft
    assert patched.date_range == {
        "start": "2023-01-03",
        "end": "2023-12-29",
    }
    _assert_owned_facts(patched)
    assert "pending_date_answer_route_repaired" in confirmation.decision.reason_codes


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("language", "model_prompt"),
    [
        ("en", "Which dates should anchor the follow-up experiment?"),
        ("es-419", "¿Qué fechas deben definir el experimento de seguimiento?"),
    ],
)
async def test_date_range_recommendation_uses_model_voice_with_provenance(
    language: str,
    model_prompt: str,
) -> None:
    source = _source_result()
    clarifier = _RecordingClarifier(model_prompt)
    workflow = build_workflow(
        structured_interpreter=lambda _: pytest.fail(
            "the typed recommendation must not call the interpreter"
        ),
        clarification_generator=clarifier,
        checkpointer=MemorySaver(),
    )

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id=f"u-345-{language}", language_preference=language),
        thread_id=f"issue-345-model-voice-{language}",
        message="Test a different date range",
        action_context=_recommendation_action(
            "change_date_range",
            "Test a different date range",
        ),
        fallback_latest_task_snapshot=_snapshot(source),
        fallback_selected_thread_metadata={
            "next_experiments_offered_kinds": ["change_date_range"],
        },
        fallback_artifact_references=[source],
    )

    assert result["stage_outcome"] == "await_user_reply"
    assert result["assistant_prompt"] == model_prompt
    assert result["assistant_response"] == model_prompt
    assert len(clarifier.requests) == 1
    request = clarifier.requests[0]
    assert request.language == language
    assert request.missing_required_fields == ["date_range"]
    assert request.candidate_strategy_draft.date_range == {
        "start": "2021-01-04",
        "end": "2025-12-31",
    }
    _assert_owned_facts(request.candidate_strategy_draft)
    assert result["clarification"]["prompt_source"] == "llm_generated"
    assert result["clarification"]["requested_field"] == "date_range"


@pytest.mark.asyncio
async def test_date_range_recommendation_declares_degraded_fallback_provenance() -> (
    None
):
    source = _source_result()
    workflow = build_workflow(
        structured_interpreter=lambda _: pytest.fail(
            "the typed recommendation must not call the interpreter"
        ),
        clarification_generator=None,
        checkpointer=MemorySaver(),
    )

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u-345-fallback", language_preference="es-419"),
        thread_id="issue-345-degraded-fallback",
        message="Probar otro rango de fechas",
        action_context=_recommendation_action(
            "change_date_range",
            "Probar otro rango de fechas",
        ),
        fallback_latest_task_snapshot=_snapshot(source),
        fallback_selected_thread_metadata={
            "next_experiments_offered_kinds": ["change_date_range"],
        },
        fallback_artifact_references=[source],
    )

    assert result["stage_outcome"] == "await_user_reply"
    assert result["assistant_prompt"]
    assert result["clarification"]["prompt_source"] == "degraded_fallback"
    assert result["clarification"]["requested_field"] == "date_range"
    assert result["clarification"]["payload"]["strategy"]["date_range"] == {
        "start": "2021-01-04",
        "end": "2025-12-31",
    }
