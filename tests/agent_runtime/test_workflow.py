from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from argus.agent_runtime.graph.workflow import (
    WorkflowStageOutcome,
    _apply_stage_result,
    _build_task_snapshot,
    build_workflow,
)
from argus.agent_runtime.runtime import (
    _compose_runtime_response,
    _public_result,
    run_agent_turn,
    stream_agent_turn_events,
)
from argus.agent_runtime.stages.interpret import (
    InterpretationRequest,
    InterpretDecision,
    StageResult,
    StructuredInterpretation,
)
from argus.agent_runtime.stages.next_step import next_step_stage
from argus.agent_runtime.state.models import (
    ArtifactReference,
    FinalResponsePayload,
    ResolutionProvenance,
    ResponseIntent,
    ResponseProfile,
    RunState,
    SimplificationOption,
    StrategySummary,
    TaskSnapshot,
    UnsupportedConstraint,
    UserState,
)
from argus.api.chat.confirmation import runtime_confirmation_card
from argus.nlp.natural_time import resolve_date_range_intent
from langgraph.checkpoint.memory import MemorySaver


class ResolvedAssetStub:
    def __init__(self, canonical_symbol: str, asset_class: str) -> None:
        self.canonical_symbol = canonical_symbol
        self.asset_class = asset_class


class RecordingClarifier:
    def __init__(self, response: str) -> None:
        self.response = response
        self.requests: list[Any] = []

    def __call__(self, request: Any) -> str:
        self.requests.append(request)
        return self.response


def test_task_snapshot_clears_failed_action_after_new_confirmation() -> None:
    prior_failed = ArtifactReference(
        artifact_kind="failed_action",
        artifact_id="failed-run-1",
        artifact_status="failed",
        metadata={"retryable": True},
    )
    confirmation = ArtifactReference(
        artifact_kind="confirmation",
        artifact_id="confirm-1",
        artifact_status="active",
        metadata={},
    )

    snapshot = _build_task_snapshot(
        run_state=RunState(current_user_message="review this"),
        stage_outcome=WorkflowStageOutcome.AWAIT_APPROVAL,
        prior_task_snapshot=TaskSnapshot(latest_failed_action_reference=prior_failed),
        artifact_references=[confirmation],
    )

    assert snapshot.latest_failed_action_reference is None


def test_task_snapshot_normalizes_prior_dict_resolution_provenance() -> None:
    prior = TaskSnapshot(
        resolution_provenance=[
            {
                "field": "asset_universe[0]",
                "raw_text": "Tesla",
                "source": "llm_extraction",
                "candidate_kind": "asset",
                "resolution_status": "resolved",
                "canonical_symbol": "TSLA",
                "asset_class": "equity",
                "validated_by": "provider_catalog",
                "confidence": "high",
            },
            ResolutionProvenance(
                field="asset_universe[0]",
                raw_text="Tesla",
                source="llm_extraction",
                candidate_kind="asset",
                resolution_status="resolved",
                canonical_symbol="TSLA",
                asset_class="equity",
                validated_by="provider_catalog",
                confidence="high",
            ),
        ]
    )

    snapshot = _build_task_snapshot(
        run_state=RunState(current_user_message="si, ejecutalo"),
        stage_outcome=WorkflowStageOutcome.AWAIT_USER_REPLY,
        prior_task_snapshot=prior,
        artifact_references=[],
    )

    assert snapshot.resolution_provenance == [
        ResolutionProvenance(
            field="asset_universe[0]",
            raw_text="Tesla",
            source="llm_extraction",
            candidate_kind="asset",
            resolution_status="resolved",
            canonical_symbol="TSLA",
            asset_class="equity",
            validated_by="provider_catalog",
            confidence="high",
        )
    ]


def test_ready_response_with_requested_fields_promotes_current_pending_strategy() -> None:
    prior = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="signal_strategy",
            strategy_thesis="Unsupported ATR draft.",
            asset_universe=["TSLA"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
        )
    )
    strategy = StrategySummary(
        strategy_type="signal_strategy",
        strategy_thesis="Use a 50/200 moving-average crossover.",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_logic="Buy when the fast SMA crosses above the slow SMA.",
    )

    updated = _apply_stage_result(
        {
            "run_state": RunState(current_user_message="usa cruce de medias"),
            "user": UserState(user_id="u1", language_preference="es-419"),
            "latest_task_snapshot": prior,
            "artifact_references": [],
        },
        StageResult(
            outcome="ready_to_respond",
            stage_patch={
                "intent": "backtest_execution",
                "task_relation": "continue",
                "user_goal_summary": "Need the moving-average periods.",
                "semantic_turn_act": "answer_pending_need",
                "candidate_strategy_draft": strategy.model_dump(mode="python"),
                "response_intent": ResponseIntent(
                    kind="clarification",
                    semantic_needs=["rule_definition"],
                    requested_fields=["entry_rule"],
                ).model_dump(mode="python"),
                "assistant_response": "¿Qué cruce quieres usar?",
            },
        ),
    )

    snapshot = updated["latest_task_snapshot"]
    assert snapshot.completed is False
    assert snapshot.pending_strategy_summary is not None
    assert snapshot.pending_strategy_summary.asset_universe == ["TSLA"]
    assert snapshot.pending_strategy_summary.entry_logic == (
        "Buy when the fast SMA crosses above the slow SMA."
    )
    assert updated["selected_thread_metadata"]["requested_field"] == "entry_rule"


def test_public_result_normalizes_dict_resolution_provenance() -> None:
    run_state = RunState(current_user_message="si, ejecutalo")
    run_state.resolution_provenance = [
        {
            "field": "asset_universe[0]",
            "raw_text": "Tesla",
            "source": "llm_extraction",
            "candidate_kind": "asset",
            "resolution_status": "resolved",
            "canonical_symbol": "TSLA",
            "asset_class": "equity",
            "validated_by": "provider_catalog",
            "confidence": "high",
        },
        ResolutionProvenance(
            field="asset_universe[0]",
            raw_text="Tesla",
            source="llm_extraction",
            candidate_kind="asset",
            resolution_status="resolved",
            canonical_symbol="TSLA",
            asset_class="equity",
            validated_by="provider_catalog",
            confidence="high",
        ),
    ]

    public = _public_result({"run_state": run_state})

    assert public["resolution_provenance"] == [
        {
            "field": "asset_universe[0]",
            "raw_text": "Tesla",
            "source": "llm_extraction",
            "candidate_kind": "asset",
            "resolution_status": "resolved",
            "canonical_symbol": "TSLA",
            "asset_class": "equity",
            "validated_by": "provider_catalog",
            "confidence": "high",
        }
    ]


def test_interpret_decision_patch_normalizes_dict_resolution_provenance() -> None:
    decision = InterpretDecision(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="El usuario aprobo la confirmacion visible.",
        confidence=0.9,
        effective_response_profile=ResponseProfile(
            effective_tone="friendly",
            effective_verbosity="medium",
            effective_expertise_mode="beginner",
        ),
    )
    decision.resolution_provenance = [
        {
            "field": "asset_universe[0]",
            "raw_text": "Tesla",
            "source": "llm_extraction",
            "candidate_kind": "asset",
            "resolution_status": "resolved",
            "canonical_symbol": "TSLA",
            "asset_class": "equity",
            "validated_by": "provider_catalog",
            "confidence": "high",
        }
    ]

    patch = decision.to_patch()

    assert patch["resolution_provenance"] == [
        {
            "field": "asset_universe[0]",
            "raw_text": "Tesla",
            "source": "llm_extraction",
            "candidate_kind": "asset",
            "resolution_status": "resolved",
            "canonical_symbol": "TSLA",
            "asset_class": "equity",
            "validated_by": "provider_catalog",
            "confidence": "high",
        }
    ]


class RsiConfirmationInterpreter:
    async def ainvoke(self, request: InterpretationRequest) -> StructuredInterpretation:
        return StructuredInterpretation(
            intent="backtest_execution",
            task_relation="new_task",
            requires_clarification=False,
            user_goal_summary="User is ready to confirm an RSI backtest.",
            candidate_strategy_draft=StrategySummary(
                raw_user_phrasing=request.current_user_message,
                strategy_type="rsi_threshold",
                strategy_thesis=request.current_user_message,
                asset_universe=["TSLA"],
                asset_class="equity",
                date_range="last year",
                entry_logic="RSI drops below 30",
                exit_logic="RSI rises above 55",
            ),
            confidence=0.94,
            semantic_turn_act="new_idea",
        )


class RunnableDraftClarifyingInterpreter:
    async def ainvoke(self, request: InterpretationRequest) -> StructuredInterpretation:
        return StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=True,
            user_goal_summary="User supplied the missing asset for a runnable draft.",
            candidate_strategy_draft=StrategySummary(
                raw_user_phrasing=request.current_user_message,
                strategy_type="buy_and_hold",
                strategy_thesis="Buy and hold Apple.",
                asset_universe=["AAPL"],
                asset_class="equity",
                date_range="last year",
            ),
            confidence=0.94,
            semantic_turn_act="answer_pending_need",
        )


class AssetAnswerInterpreter:
    async def ainvoke(self, request: InterpretationRequest) -> StructuredInterpretation:
        return StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User supplied the replacement asset.",
            candidate_strategy_draft=StrategySummary(asset_universe=["TSLA"]),
            confidence=0.94,
            semantic_turn_act="answer_pending_need",
        )


class NoisyAssetAnswerInterpreter:
    def __init__(self, mapped_symbol: str) -> None:
        self.mapped_symbol = mapped_symbol

    async def ainvoke(self, request: InterpretationRequest) -> StructuredInterpretation:
        return StructuredInterpretation(
            intent="conversation_followup",
            task_relation="continue",
            requires_clarification=True,
            user_goal_summary="User supplied a replacement asset, but prose was noisy.",
            assistant_response="The answer needs asset clarification.",
            candidate_strategy_draft=StrategySummary(asset_universe=[self.mapped_symbol]),
            confidence=0.72,
            semantic_turn_act="educational_question",
        )


class AssetAnswerThenApprovalInterpreter:
    def __init__(self, mapped_symbol: str) -> None:
        self.mapped_symbol = mapped_symbol
        self.requests: list[InterpretationRequest] = []

    async def ainvoke(self, request: InterpretationRequest) -> StructuredInterpretation:
        self.requests.append(request)
        if len(self.requests) == 1:
            return StructuredInterpretation(
                intent="conversation_followup",
                task_relation="continue",
                requires_clarification=True,
                user_goal_summary="User supplied a replacement asset.",
                assistant_response="The answer needs asset clarification.",
                candidate_strategy_draft=StrategySummary(
                    asset_universe=[self.mapped_symbol]
                ),
                confidence=0.72,
                semantic_turn_act="educational_question",
            )
        return StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User approved the visible confirmation.",
            candidate_strategy_draft=StrategySummary(),
            confidence=0.96,
            semantic_turn_act="approval",
        )


class SpanishDateAnswerInterpreter:
    def __init__(self) -> None:
        self.requests: list[InterpretationRequest] = []

    async def ainvoke(self, request: InterpretationRequest) -> StructuredInterpretation:
        self.requests.append(request)
        return StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="El usuario dio una nueva ventana de fechas.",
            candidate_strategy_draft=StrategySummary(
                raw_user_phrasing=request.current_user_message,
                date_range={"start": "2025-12-14", "end": "2026-06-12"},
                extra_parameters={
                    "date_range_intent": {
                        "kind": "rolling_window",
                        "count": 6,
                        "unit": "month",
                        "anchor": "today",
                        "evidence": "ultimos 6 meses",
                    },
                    "evidence_spans": {
                        "date_range_intent": "ultimos 6 meses",
                    },
                },
                refinement_of="visible confirmation",
            ),
            confidence=0.94,
            semantic_turn_act="answer_pending_need",
        )


class SpanishExplicitDayRangeDriftInterpreter:
    async def ainvoke(self, request: InterpretationRequest) -> StructuredInterpretation:
        return StructuredInterpretation(
            intent="backtest_execution",
            task_relation="new_task",
            requires_clarification=False,
            user_goal_summary="El usuario quiere comprar y mantener AAPL, MSFT y TSLA.",
            candidate_strategy_draft=StrategySummary(
                raw_user_phrasing=request.current_user_message,
                language="es-419",
                strategy_type="buy_and_hold",
                strategy_thesis=request.current_user_message,
                asset_universe=["AAPL", "MSFT", "TSLA"],
                asset_class="equity",
                date_range={"start": "2025-01-01", "end": "2025-12-31"},
                capital_amount=10000,
                comparison_baseline="SPY",
                extra_parameters={
                    "date_range_raw_text": "desde enero 1 2025 hasta junio 5 2026",
                    "date_range_intent": {
                        "kind": "calendar_year",
                        "year": 2025,
                        "confidence": 0.9,
                        "evidence": "desde enero 1 2025 hasta junio 5 2026",
                    },
                    "evidence_spans": {
                        "date_range": "desde enero 1 2025 hasta junio 5 2026",
                    },
                },
            ),
            confidence=0.9,
            semantic_turn_act="new_idea",
        )


class SpanishAssumptionAnswerInterpreter:
    def __init__(self) -> None:
        self.requests: list[InterpretationRequest] = []

    async def ainvoke(self, request: InterpretationRequest) -> StructuredInterpretation:
        self.requests.append(request)
        return StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="El usuario ajustó el capital inicial.",
            candidate_strategy_draft=StrategySummary(
                raw_user_phrasing=request.current_user_message,
                capital_amount=250000,
                refinement_of="visible confirmation",
            ),
            confidence=0.94,
            semantic_turn_act="answer_pending_need",
        )


class SpanishAssetAnswerInterpreter:
    def __init__(self) -> None:
        self.requests: list[InterpretationRequest] = []

    async def ainvoke(self, request: InterpretationRequest) -> StructuredInterpretation:
        self.requests.append(request)
        return StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="El usuario dio un activo de reemplazo.",
            candidate_strategy_draft=StrategySummary(
                raw_user_phrasing=request.current_user_message,
                asset_universe=["GOOGL"],
                refinement_of="visible confirmation",
            ),
            confidence=0.94,
            semantic_turn_act="answer_pending_need",
        )


class ConversationalInterpreter:
    async def ainvoke(self, request: InterpretationRequest) -> StructuredInterpretation:
        return StructuredInterpretation(
            intent="conversation_followup",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User asked a product question.",
            assistant_response="I help turn investing ideas into supported backtests.",
            confidence=0.94,
            semantic_turn_act="educational_question",
        )


class AsyncBacktestJobTool:
    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        del payload
        return {
            "success": True,
            "payload": {
                "backtest_job": {
                    "id": "job-async-1",
                    "conversation_id": "thread-async-job",
                    "request_message_id": "request-message-1",
                    "confirmation_message_id": "confirmation-message-1",
                    "status": "queued",
                    "result_run_id": None,
                    "failure_code": None,
                    "failure_detail": None,
                    "retryable": False,
                    "queued_at": "2026-06-06T12:00:00Z",
                    "started_at": None,
                    "finished_at": None,
                    "created_at": "2026-06-06T12:00:00Z",
                    "updated_at": "2026-06-06T12:00:00Z",
                }
            },
            "error_type": None,
            "error_message": None,
            "retryable": False,
            "capability_context": {"execution_status": "queued"},
        }


class ShortWindowCrossoverInterpreter:
    async def ainvoke(self, request: InterpretationRequest) -> StructuredInterpretation:
        return StructuredInterpretation(
            intent="backtest_execution",
            task_relation="new_task",
            requires_clarification=False,
            user_goal_summary="User wants a short-window moving-average crossover.",
            candidate_strategy_draft=StrategySummary(
                raw_user_phrasing=request.current_user_message,
                strategy_type="signal_strategy",
                strategy_thesis="Test SPY on a 20/50 SMA crossover.",
                asset_universe=["SPY"],
                asset_class="equity",
                date_range="past month",
                extra_parameters={
                    "date_range_intent": {
                        "kind": "rolling_window",
                        "count": 1,
                        "unit": "month",
                        "anchor": "today",
                        "evidence": "last month",
                    }
                },
                entry_logic="20-day SMA crosses above 50-day SMA",
                exit_logic="20-day SMA crosses below 50-day SMA",
                entry_rule={
                    "type": "moving_average_crossover",
                    "fast_indicator": "sma",
                    "fast_period": 20,
                    "slow_indicator": "sma",
                    "slow_period": 50,
                    "direction": "bullish",
                },
                exit_rule={
                    "type": "moving_average_crossover",
                    "fast_indicator": "sma",
                    "fast_period": 20,
                    "slow_indicator": "sma",
                    "slow_period": 50,
                    "direction": "bearish",
                },
            ),
            confidence=0.94,
            semantic_turn_act="new_idea",
        )


class ApprovalInterpreter:
    def __init__(self) -> None:
        self.seen_snapshots: list[object] = []

    async def ainvoke(self, request: InterpretationRequest) -> StructuredInterpretation:
        self.seen_snapshots.append(request.latest_task_snapshot)
        if len(self.seen_snapshots) == 1:
            return StructuredInterpretation(
                intent="backtest_execution",
                task_relation="new_task",
                requires_clarification=False,
                user_goal_summary="User is drafting a buy and hold backtest.",
                candidate_strategy_draft=StrategySummary(
                    raw_user_phrasing=request.current_user_message,
                    strategy_type="buy_and_hold",
                    strategy_thesis=request.current_user_message,
                    asset_universe=["BTC"],
                    asset_class="crypto",
                    date_range="last year",
                ),
                confidence=0.94,
                semantic_turn_act="new_idea",
            )
        return StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User approved the pending strategy.",
            candidate_strategy_draft=StrategySummary(),
            confidence=0.96,
            semantic_turn_act="approval",
        )


class IndicatorDateRepairInterpreter:
    def __init__(self) -> None:
        self.turns = 0

    async def ainvoke(self, request: InterpretationRequest) -> StructuredInterpretation:
        self.turns += 1
        if self.turns == 1:
            return StructuredInterpretation(
                intent="backtest_execution",
                task_relation="new_task",
                requires_clarification=False,
                user_goal_summary="User wants a TSLA RSI threshold test.",
                candidate_strategy_draft=StrategySummary(
                    raw_user_phrasing=request.current_user_message,
                    strategy_type="indicator_threshold",
                    strategy_thesis="Test TSLA with RSI threshold entries.",
                    asset_universe=["TSLA"],
                    asset_class="equity",
                    date_range={"start": "2015-01-01", "end": "2024-12-31"},
                    entry_logic="Buy when RSI(14) drops to 30 or below",
                    exit_logic="Sell when RSI(14) rises to 55 or above",
                    extra_parameters={
                        "raw_strategy_type": "rsi_mean_reversion",
                        "indicator": "rsi",
                        "indicator_parameters": {
                            "indicator": "rsi",
                            "indicator_period": 14,
                            "entry_threshold": 30,
                            "exit_threshold": 55,
                        },
                    },
                ),
                confidence=0.94,
                semantic_turn_act="new_idea",
            )
        return StructuredInterpretation(
            intent="backtest_execution",
            task_relation="refine",
            requires_clarification=False,
            user_goal_summary="User supplied the shorter supported date range.",
            candidate_strategy_draft=StrategySummary(
                raw_user_phrasing=request.current_user_message,
                strategy_type="indicator_threshold",
                date_range={"start": "2021-01-01", "end": "2024-01-01"},
                extra_parameters={"raw_strategy_type": "indicator_threshold"},
                refinement_of="prior strategy card",
            ),
            confidence=0.94,
            semantic_turn_act="answer_pending_need",
        )


def test_runtime_preserves_explicit_stage_prompt_over_recovery_fallback() -> None:
    run_state = RunState.new(
        current_user_message="use a 20-day SMA crossing above the 50-day SMA",
        recent_thread_history=[],
    )
    run_state.response_intent = ResponseIntent(
        kind="clarification",
        semantic_needs=["period"],
        requested_fields=["date_range"],
        facts={"strategy": {"strategy_type": "signal_strategy"}},
    )

    result = _compose_runtime_response(
        {
            "run_state": run_state,
            "assistant_prompt": (
                "That rule needs more historical bars than the selected window "
                "can provide. Choose a longer date range, or use a shorter "
                "indicator period so the backtest has enough data to evaluate "
                "the signal."
            ),
        }
    )

    assert result["assistant_prompt"].startswith("That rule needs more historical bars")


def test_next_step_preserves_completed_result_answer() -> None:
    run_state = RunState.new(
        current_user_message="",
        recent_thread_history=[],
    )
    run_state.final_response_payload = FinalResponsePayload(
        result={"total_return": 0.14},
        summary="Completed run",
    )
    state = {
        "run_state": run_state,
        "user": UserState(user_id="u1"),
        "stage_outcome": WorkflowStageOutcome.READY_TO_RESPOND,
        "assistant_response": "Grounded result readout.",
    }

    updated = _apply_stage_result(state, next_step_stage(state=run_state))

    assert updated["stage_outcome"] == WorkflowStageOutcome.END_RUN
    assert updated["assistant_response"] == "Grounded result readout."
    assert updated["next_actions"] == [
        "show_breakdown",
        "refine_strategy",
        "save_strategy",
    ]
    assert "compare_benchmark" not in updated["next_actions"]


def test_next_step_without_completed_result_does_not_emit_legacy_actions() -> None:
    run_state = RunState.new(
        current_user_message="",
        recent_thread_history=[],
    )

    result = next_step_stage(state=run_state)

    assert result.outcome == "end_run"
    assert result.patch["next_actions"] == []


def test_runtime_preserves_offline_clarifier_as_recovery() -> None:
    run_state = RunState.new(
        current_user_message="Test buying SPY when it starts rising.",
        recent_thread_history=[],
    )
    run_state.response_intent = ResponseIntent(
        kind="clarification",
        semantic_needs=["period", "rule_definition"],
        requested_fields=["date_range", "entry_logic"],
        facts={
            "strategy": {
                "strategy_type": "signal_strategy",
                "asset_universe": ["SPY"],
            }
        },
    )

    result = _compose_runtime_response(
        {
            "run_state": run_state,
            "assistant_prompt": (
                "I could not phrase the follow-up clearly just now. Your draft "
                "is still here; tell me the detail you want to change, or try "
                "again in a moment."
            ),
        }
    )

    assert result["assistant_prompt"].startswith(
        "I could not phrase the follow-up clearly"
    )
    assert "I can test" not in result["assistant_prompt"]
    assert "Which date window" not in result["assistant_prompt"]
    assert result["assistant_response"] == result["assistant_prompt"]


def test_runtime_does_not_synthesize_slot_copy_for_general_clarification() -> None:
    run_state = RunState.new(
        current_user_message="Cambiar fechas",
        recent_thread_history=[],
    )
    run_state.response_intent = ResponseIntent(
        kind="clarification",
        semantic_needs=["period"],
        requested_fields=["date_range"],
        facts={
            "language": "es-419",
            "strategy": {
                "strategy_type": "buy_and_hold",
                "asset_universe": ["AAPL"],
            },
        },
    )

    result = _compose_runtime_response({"run_state": run_state})

    assert "assistant_prompt" not in result
    assert "assistant_response" not in result


def test_runtime_preserves_successful_llm_rule_clarification() -> None:
    run_state = RunState.new(
        current_user_message="Test buying SPY when it starts rising.",
        recent_thread_history=[],
    )
    run_state.response_intent = ResponseIntent(
        kind="clarification",
        semantic_needs=["rule_definition"],
        requested_fields=["entry_logic"],
        facts={
            "strategy": {
                "strategy_type": "signal_strategy",
                "asset_universe": ["SPY"],
            }
        },
    )

    result = _compose_runtime_response(
        {
            "run_state": run_state,
            "assistant_prompt": (
                "Could you please define what starts rising means in terms of "
                "price movement, indicators, or other measurable criteria?"
            ),
        }
    )

    assert result["assistant_prompt"].startswith("Could you please define")
    assert result["assistant_prompt"].endswith("measurable criteria?")
    assert result["assistant_response"] == result["assistant_prompt"]


def test_runtime_preserves_specific_dca_execution_clarification() -> None:
    run_state = RunState.new(
        current_user_message=(
            "I would like to invest in LYFT over 5 years feb 2020-feb 2025, "
            "$200,000 of capital"
        ),
        recent_thread_history=[],
    )
    run_state.response_intent = ResponseIntent(
        kind="clarification",
        semantic_needs=["sizing_amount"],
        requested_fields=["capital_amount"],
        facts={
            "strategy": {
                "strategy_type": "dca_accumulation",
                "asset_universe": ["LYFT"],
                "asset_class": "equity",
                "date_range": {"start": "2020-02-01", "end": "2025-02-28"},
                "extra_parameters": {"initial_capital": 200000},
            }
        },
    )

    result = _compose_runtime_response(
        {
            "run_state": run_state,
            "assistant_prompt": (
                "I can test recurring buys for LYFT. How much should each "
                "recurring purchase be, and how often should those buys happen?"
            ),
        }
    )

    prompt = result["assistant_prompt"]
    assert "LYFT" in prompt
    assert "recurring purchase" in prompt
    assert "how often" in prompt.lower()
    assert "one more detail" not in prompt.lower()


def test_workflow_publishes_pending_response_intent_options_for_recovery() -> None:
    strategy = StrategySummary(
        strategy_type="dca_accumulation",
        strategy_thesis="Quarterly recurring buys for MSFT.",
        asset_universe=["MSFT"],
        asset_class="equity",
        date_range={"start": "2021-01-01", "end": "2023-12-31"},
        capital_amount=750,
        cadence="quarterly",
        extra_parameters={
            "recurring_contribution": 750,
            "total_budget": 9000,
            "field_provenance": {
                "capital_amount": "recurring_contribution",
                "total_capital": "cap",
            },
        },
    )
    constraint = UnsupportedConstraint(
        category="unsupported_dca_starting_principal",
        raw_value="$9,000 contribution cap",
        explanation=(
            "The DCA engine can run the recurring contribution but not the cap."
        ),
        simplification_options=[
            SimplificationOption(
                label="Run recurring buys only",
                replacement_values={"ignore_initial_capital": True},
            )
        ],
    )
    response_intent = {
        "kind": "unsupported_recovery",
        "semantic_needs": ["simplification_choice"],
        "facts": {"unsupported_constraints": [constraint.model_dump(mode="python")]},
        "options": [
            {
                "label": "Run recurring buys only",
                "replacement_values": {"ignore_initial_capital": True},
            }
        ],
    }

    updated = _apply_stage_result(
        {
            "run_state": RunState.new(
                current_user_message=(
                    "try buying $750 of MSFT quarterly from 2021 through 2023 "
                    "with a $9,000 cap"
                ),
                recent_thread_history=[],
            ),
            "user": UserState(user_id="u1"),
            "latest_task_snapshot": None,
        },
        StageResult(
            outcome="needs_clarification",
            stage_patch={
                "candidate_strategy_draft": strategy.model_dump(mode="python"),
                "optional_parameter_status": {
                    "unsupported_constraints": [constraint.model_dump(mode="python")]
                },
                "response_intent": response_intent,
            },
        ),
    )

    metadata_intent = updated["selected_thread_metadata"]["response_intent"]
    assert metadata_intent["kind"] == "unsupported_recovery"
    assert metadata_intent["semantic_needs"] == ["simplification_choice"]
    assert metadata_intent["options"][0]["replacement_values"] == {
        "ignore_initial_capital": True
    }

    public = _public_result(updated)
    assert public["pending_strategy"]["response_intent"]["options"][0][
        "replacement_values"
    ] == {"ignore_initial_capital": True}


@pytest.mark.asyncio
async def test_workflow_requires_confirmation_before_execute(monkeypatch) -> None:
    from argus.agent_runtime import resolution as resolution_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        return ResolvedAssetStub(symbol.upper(), "equity")

    monkeypatch.setattr(resolution_module, "resolve_market_asset", resolve_stub)

    workflow = build_workflow(
        structured_interpreter=RsiConfirmationInterpreter(),
        checkpointer=MemorySaver(),
    )
    user = UserState(user_id="u1", expertise_level="advanced")

    result = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id="thread-1",
        message=(
            "Backtest Tesla when RSI drops below 30 and exit above 55 "
            "over the last year"
        ),
    )

    assert result["stage_outcome"] == "await_approval"
    assert result["confirmation_payload"]["strategy"]["asset_universe"] == ["TSLA"]
    assert result["pending_strategy"]["strategy"]["asset_universe"] == ["TSLA"]
    assert result["pending_strategy"]["missing_required_fields"] == []
    assert result.get("assistant_prompt") is None
    assert "RSI" in result["confirmation_payload"]["strategy"]["entry_logic"]


@pytest.mark.asyncio
async def test_workflow_run_backtest_action_returns_async_job_payload(
    monkeypatch,
) -> None:
    from argus.agent_runtime import resolution as resolution_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        return ResolvedAssetStub(symbol.upper(), "crypto")

    monkeypatch.setattr(resolution_module, "resolve_market_asset", resolve_stub)

    workflow = build_workflow(
        structured_interpreter=ApprovalInterpreter(),
        tool=AsyncBacktestJobTool(),
        checkpointer=MemorySaver(),
    )
    user = UserState(user_id="u1", expertise_level="beginner")
    thread_id = "thread-async-job"

    confirmation = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id=thread_id,
        message="Buy and hold BTC over the last year",
    )

    confirmation_reference = confirmation["artifact_references"][0]
    confirmation_metadata = confirmation_reference["metadata"]
    action = {
        "type": "run_backtest",
        "label": "Run backtest",
        "presentation": "confirmation",
        "payload": {
            "artifact_id": confirmation_reference["artifact_id"],
            "confirmation_id": confirmation_reference["artifact_id"],
            "conversation_id": thread_id,
            "launch_payload_hash": confirmation_metadata["launch_payload_hash"],
        },
    }
    result = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id=thread_id,
        message="Run backtest",
        action_context=action,
    )

    assert result["stage_outcome"] == "ready_to_respond"
    assert result["backtest_job"]["id"] == "job-async-1"
    assert result["final_response_payload"]["backtest_job"]["id"] == "job-async-1"
    assert result["artifact_references"][0]["artifact_kind"] == "backtest_job"


@pytest.mark.asyncio
async def test_workflow_preserves_confirmation_validation_prompt(monkeypatch) -> None:
    from argus.agent_runtime import resolution as resolution_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        return ResolvedAssetStub(symbol.upper(), "equity")

    monkeypatch.setattr(resolution_module, "resolve_market_asset", resolve_stub)

    clarifier = RecordingClarifier(
        "Use a longer date range, or choose a shorter indicator period."
    )
    workflow = build_workflow(
        structured_interpreter=ShortWindowCrossoverInterpreter(),
        clarification_generator=clarifier,
        checkpointer=MemorySaver(),
    )

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1", expertise_level="advanced"),
        thread_id="thread-short-window-crossover",
        message="Use a 20-day SMA crossing above the 50-day SMA over the last month.",
    )

    assert result["stage_outcome"] == "await_user_reply"
    assert result["assistant_prompt"] == (
        "Use a longer date range, or choose a shorter indicator period."
    )
    assert result["pending_strategy"]["requested_field"] == "date_range"
    response_intent = result["pending_strategy"]["response_intent"]
    assert response_intent["kind"] == "unsupported_recovery"
    assert clarifier.requests
    assert (
        clarifier.requests[0].response_intent["facts"]["unsupported_constraints"][0][
            "category"
        ]
        == "data_window_too_short_for_rule"
    )
    assert clarifier.requests[0].response_intent["options"] == [
        {"label": "Use a longer date range"},
        {"label": "Use a shorter indicator period"},
        {"label": "Choose a simpler supported rule"},
    ]
    assert "confirmation_payload" not in result


@pytest.mark.asyncio
async def test_workflow_preserves_indicator_parameters_when_user_repairs_date_range(
    monkeypatch,
) -> None:
    from argus.agent_runtime import resolution as resolution_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        return ResolvedAssetStub(symbol.upper(), "equity")

    monkeypatch.setattr(resolution_module, "resolve_market_asset", resolve_stub)

    workflow = build_workflow(
        structured_interpreter=IndicatorDateRepairInterpreter(),
        checkpointer=MemorySaver(),
    )
    user = UserState(user_id="u1", expertise_level="beginner")
    thread_id = "thread-indicator-date-repair"

    first = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id=thread_id,
        message="test tsla rsi below 30 and sell above 55 since 2015",
    )

    assert first["stage_outcome"] == "await_user_reply"
    assert first["pending_strategy"]["requested_field"] == "date_range"

    second = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id=thread_id,
        message="use jan 1 2021 to jan 1 2024",
    )

    assert second["stage_outcome"] == "await_approval"
    strategy = second["confirmation_payload"]["strategy"]
    assert strategy["asset_universe"] == ["TSLA"]
    assert strategy["entry_logic"] == "Buy when RSI(14) drops to 30 or below"
    assert strategy["extra_parameters"]["indicator"] == "rsi"
    assert strategy["extra_parameters"]["indicator_parameters"] == {
        "indicator": "rsi",
        "indicator_period": 14,
        "entry_threshold": 30,
        "exit_threshold": 55,
    }
    assert second["pending_strategy"]["missing_required_fields"] == []


@pytest.mark.asyncio
async def test_workflow_confirms_runnable_draft_instead_of_optional_settings_prompt(
    monkeypatch,
) -> None:
    from argus.agent_runtime import resolution as resolution_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        return ResolvedAssetStub(symbol.upper(), "equity")

    monkeypatch.setattr(resolution_module, "resolve_market_asset", resolve_stub)

    workflow = build_workflow(
        structured_interpreter=RunnableDraftClarifyingInterpreter(),
        checkpointer=MemorySaver(),
    )
    user = UserState(user_id="u1", expertise_level="beginner")

    result = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id="thread-optional-defaults",
        message="yes AAPL stock",
        fallback_latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=StrategySummary(
                strategy_type="buy_and_hold",
                strategy_thesis="Hold Apple stock for one year.",
                asset_class="equity",
                date_range="last year",
            )
        ),
        fallback_selected_thread_metadata={"last_stage_outcome": "await_user_reply"},
    )

    assert result["stage_outcome"] == "await_approval"
    assert result["confirmation_payload"]["strategy"]["asset_universe"] == ["AAPL"]
    assert (
        result["confirmation_payload"]["optional_parameters"]["initial_capital"]["value"]
        == 1000.0
    )
    assert "optional_parameter_choices" not in result


@pytest.mark.asyncio
async def test_workflow_confirmation_assumption_action_stays_in_clarification() -> None:
    workflow = build_workflow(
        structured_interpreter=None,
        checkpointer=MemorySaver(),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2025-06-14", "end": "2026-06-12"},
        capital_amount=100000,
        comparison_baseline="SPY",
    )

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1", language_preference="es-419"),
        thread_id="thread-confirmation-assumption-action",
        message="adjust assumptions",
        action_context={
            "type": "adjust_assumptions",
            "label": "Adjust assumptions",
            "presentation": "confirmation",
            "payload": {"confirmation_id": "confirmation-1"},
        },
        fallback_latest_task_snapshot=TaskSnapshot(pending_strategy_summary=pending),
        fallback_selected_thread_metadata={"last_stage_outcome": "await_approval"},
    )

    assert result["stage_outcome"] == "await_user_reply"
    assert result["assistant_response"]
    clarification = result["clarification"]
    assert clarification["kind"] == "clarification"
    assert clarification["reason_code"] == "missing_assumption"
    assert clarification["requested_field"] == "assumption"
    assert clarification["payload"]["strategy"]["asset_universe"] == ["AAPL"]
    assert "confirmation_payload" not in result


@pytest.mark.asyncio
async def test_workflow_clears_requested_field_after_chip_answer_confirmation(
    monkeypatch,
) -> None:
    from argus.agent_runtime import resolution as resolution_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        return ResolvedAssetStub(symbol.upper(), "equity")

    monkeypatch.setattr(resolution_module, "resolve_market_asset", resolve_stub)

    workflow = build_workflow(
        structured_interpreter=AssetAnswerInterpreter(),
        checkpointer=MemorySaver(),
    )
    user = UserState(user_id="u1", expertise_level="beginner")
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Nvidia.",
        asset_universe=["NVDA"],
        asset_class="equity",
        date_range="last year",
    )

    prompt_result = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id="thread-chip-answer",
        message="Change asset",
        action_context={
            "type": "change_asset",
            "label": "Change asset",
            "presentation": "confirmation",
            "payload": {},
        },
        fallback_latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=pending,
        ),
        fallback_selected_thread_metadata={"last_stage_outcome": "await_approval"},
    )

    assert prompt_result["stage_outcome"] == "await_user_reply"
    assert prompt_result["pending_strategy"]["requested_field"] == "asset_universe"

    answer_result = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id="thread-chip-answer",
        message="TSLA",
    )

    assert answer_result["stage_outcome"] == "await_approval"
    assert answer_result["confirmation_payload"]["strategy"]["asset_universe"] == ["TSLA"]
    assert answer_result["pending_strategy"]["requested_field"] is None
    assert answer_result["pending_strategy"]["missing_required_fields"] == []


@pytest.mark.parametrize(
    ("answer", "resolved_symbol"),
    [("google", "GOOGL"), ("microsoft", "MSFT")],
)
@pytest.mark.asyncio
async def test_workflow_pending_asset_answer_contract_wins_over_noisy_interpreter_copy(
    monkeypatch,
    answer: str,
    resolved_symbol: str,
) -> None:
    from argus.agent_runtime import resolution as resolution_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        normalized = symbol.strip().casefold()
        if normalized == answer.casefold() or normalized == resolved_symbol.casefold():
            return ResolvedAssetStub(resolved_symbol, "equity")
        return ResolvedAssetStub(symbol.upper(), "equity")

    monkeypatch.setattr(resolution_module, "resolve_market_asset", resolve_stub)

    workflow = build_workflow(
        structured_interpreter=NoisyAssetAnswerInterpreter(resolved_symbol),
        checkpointer=MemorySaver(),
    )
    user = UserState(user_id="u1", expertise_level="beginner")
    pending = StrategySummary(
        strategy_type="indicator_threshold",
        strategy_thesis="Test TSLA with an RSI threshold rule.",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_logic="Buy when RSI(14) drops to 30 or below",
        exit_logic="Sell when RSI(14) rises to 55 or above",
        extra_parameters={
            "indicator": "rsi",
            "indicator_parameters": {
                "indicator": "rsi",
                "indicator_period": 14,
                "entry_threshold": 30,
                "exit_threshold": 55,
            },
        },
    )

    prompt_result = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id=f"thread-noisy-asset-answer-{resolved_symbol}",
        message="Change asset",
        action_context={
            "type": "change_asset",
            "label": "Change asset",
            "presentation": "confirmation",
            "payload": {},
        },
        fallback_latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=pending,
        ),
        fallback_selected_thread_metadata={"last_stage_outcome": "await_approval"},
    )

    assert prompt_result["stage_outcome"] == "await_user_reply"
    assert prompt_result["pending_strategy"]["requested_field"] == "asset_universe"

    answer_result = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id=f"thread-noisy-asset-answer-{resolved_symbol}",
        message=answer,
    )

    assert answer_result["stage_outcome"] == "await_approval"
    strategy = answer_result["confirmation_payload"]["strategy"]
    assert strategy["asset_universe"] == [resolved_symbol]
    assert strategy["entry_logic"] == "Buy when RSI(14) drops to 30 or below"
    assert strategy["exit_logic"] == "Sell when RSI(14) rises to 55 or above"
    assert "assistant_response" not in answer_result
    assert answer_result["pending_strategy"]["requested_field"] is None


@pytest.mark.asyncio
async def test_workflow_typed_approval_after_card_edit_defers_to_card_action(
    monkeypatch,
) -> None:
    from argus.agent_runtime import resolution as resolution_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        normalized = symbol.strip().casefold()
        if normalized in {"google", "googl"}:
            return ResolvedAssetStub("GOOGL", "equity")
        return ResolvedAssetStub(symbol.upper(), "equity")

    monkeypatch.setattr(resolution_module, "resolve_market_asset", resolve_stub)

    workflow = build_workflow(
        structured_interpreter=AssetAnswerThenApprovalInterpreter("GOOGL"),
        checkpointer=MemorySaver(),
    )
    user = UserState(user_id="u1", expertise_level="beginner")
    pending = StrategySummary(
        strategy_type="indicator_threshold",
        strategy_thesis="Test TSLA with an RSI threshold rule.",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_logic="Buy when RSI(14) drops to 30 or below",
        exit_logic="Sell when RSI(14) rises to 55 or above",
        extra_parameters={
            "indicator": "rsi",
            "indicator_parameters": {
                "indicator": "rsi",
                "indicator_period": 14,
                "entry_threshold": 30,
                "exit_threshold": 55,
            },
        },
    )
    thread_id = "thread-approval-after-card-edit"

    await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id=thread_id,
        message="Change asset",
        action_context={
            "type": "change_asset",
            "label": "Change asset",
            "presentation": "confirmation",
            "payload": {},
        },
        fallback_latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=pending,
        ),
        fallback_selected_thread_metadata={"last_stage_outcome": "await_approval"},
    )
    answer_result = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id=thread_id,
        message="google",
    )

    assert answer_result["stage_outcome"] == "await_approval"
    state_snapshot = await workflow.aget_state({"configurable": {"thread_id": thread_id}})
    snapshot = state_snapshot.values["latest_task_snapshot"]
    assert snapshot.active_confirmation_reference is not None

    approval_result = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id=thread_id,
        message="yes, run it",
    )

    assert approval_result["stage_outcome"] == "ready_to_respond"
    assert "visible confirmation" in approval_result["assistant_response"]
    assert "simulation" in approval_result["assistant_response"]
    assert "confirmation_payload" not in approval_result


@pytest.mark.asyncio
async def test_spanish_explicit_day_range_survives_confirmation_payload(
    monkeypatch,
) -> None:
    from argus.agent_runtime import resolution as resolution_module

    monkeypatch.setattr(
        resolution_module,
        "resolve_market_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )

    prompt = (
        "probemos algo medio simple: comprar y mantener AAPL, MSFT y TSLA, "
        "pesos iguales, desde enero 1 2025 hasta junio 5 2026, con 10000 "
        "dolares, comparalo con SPY, sin fees ni deslizamiento"
    )
    workflow = build_workflow(
        structured_interpreter=SpanishExplicitDayRangeDriftInterpreter(),
        checkpointer=MemorySaver(),
    )

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1", language_preference="es-419"),
        thread_id="thread-spanish-explicit-day-range",
        message=prompt,
    )

    expected_range = {"start": "2025-01-01", "end": "2026-06-05"}
    assert result["stage_outcome"] == "await_approval"
    assert result["confirmation_payload"]["strategy"]["date_range"] == expected_range
    assert (
        result["confirmation_payload"]["launch_payload"]["date_range"] == expected_range
    )

    card = runtime_confirmation_card(result, language="es-419")
    assert card is not None
    assert card["date_range"]["start"] == "2025-01-01"
    assert card["date_range"]["end"] == "2026-06-05"
    assert "5 de junio de 2026" in card["date_range"]["display"]
    assert any(
        row["key"] == "period" and "5 de junio de 2026" in row["value"]
        for row in card["rows"]
    )


@pytest.mark.asyncio
async def test_workflow_spanish_change_dates_answer_reenters_interpreter(
    monkeypatch,
) -> None:
    from argus.agent_runtime import resolution as resolution_module
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        resolution_module,
        "resolve_market_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )

    class FrozenDate(date):
        @classmethod
        def today(cls) -> date:
            return cls(2026, 6, 15)

    monkeypatch.setattr(interpret_module, "date", FrozenDate)

    interpreter = SpanishDateAnswerInterpreter()
    workflow = build_workflow(
        structured_interpreter=interpreter,
        checkpointer=MemorySaver(),
    )
    user = UserState(user_id="u1", language_preference="es-419")
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Comprar y mantener AAPL.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        capital_amount=100000,
        comparison_baseline="SPY",
    )
    thread_id = "thread-spanish-change-dates-answer"

    prompt_result = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id=thread_id,
        message="Cambiar fechas",
        action_context={
            "type": "change_dates",
            "label": "Cambiar fechas",
            "presentation": "confirmation",
            "payload": {},
        },
        fallback_latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=pending,
        ),
        fallback_selected_thread_metadata={"last_stage_outcome": "await_approval"},
    )

    assert interpreter.requests == []
    assert prompt_result["stage_outcome"] == "await_user_reply"
    assert prompt_result["pending_strategy"]["requested_field"] == "date_range"
    assert prompt_result["pending_strategy"]["missing_required_fields"] == ["date_range"]

    answer_result = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id=thread_id,
        message="ultimos 6 meses",
    )

    assert len(interpreter.requests) == 1
    assert interpreter.requests[0].user.language_preference == "es-419"
    assert interpreter.requests[0].latest_task_snapshot is not None
    assert (
        interpreter.requests[0].latest_task_snapshot.pending_strategy_summary is not None
    )
    assert interpreter.requests[0].selected_thread_metadata["requested_field"] == (
        "date_range"
    )
    assert answer_result["stage_outcome"] == "await_approval"
    strategy = answer_result["confirmation_payload"]["strategy"]
    assert strategy["asset_universe"] == ["AAPL"]
    assert strategy["capital_amount"] == 100000
    assert strategy["comparison_baseline"] == "SPY"
    expected_range = resolve_date_range_intent(
        {
            "kind": "rolling_window",
            "count": 6,
            "unit": "month",
            "anchor": "today",
        },
        today=date(2026, 6, 15),
    )
    assert expected_range is not None
    assert strategy["date_range"] == expected_range.payload
    assert answer_result["pending_strategy"]["requested_field"] is None
    assert answer_result["pending_strategy"]["missing_required_fields"] == []


@pytest.mark.asyncio
async def test_workflow_spanish_adjust_assumptions_answer_reenters_interpreter() -> None:
    interpreter = SpanishAssumptionAnswerInterpreter()
    workflow = build_workflow(
        structured_interpreter=interpreter,
        checkpointer=MemorySaver(),
    )
    user = UserState(user_id="u1", language_preference="es-419")
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Comprar y mantener AAPL.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2025-06-14", "end": "2026-06-12"},
        comparison_baseline="SPY",
    )
    thread_id = "thread-spanish-adjust-assumptions-answer"

    prompt_result = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id=thread_id,
        message="Ajustar supuestos",
        action_context={
            "type": "adjust_assumptions",
            "label": "Ajustar supuestos",
            "presentation": "confirmation",
            "payload": {},
        },
        fallback_latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=pending,
        ),
        fallback_selected_thread_metadata={"last_stage_outcome": "await_approval"},
    )

    assert interpreter.requests == []
    assert prompt_result["stage_outcome"] == "await_user_reply"
    assert prompt_result["pending_strategy"]["requested_field"] == "assumption"
    assert prompt_result["pending_strategy"]["missing_required_fields"] == ["assumption"]

    answer_result = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id=thread_id,
        message="ponle como doscientos cincuenta mil",
    )

    assert len(interpreter.requests) == 1
    request = interpreter.requests[0]
    assert request.user.language_preference == "es-419"
    assert request.latest_task_snapshot is not None
    assert request.latest_task_snapshot.pending_strategy_summary is not None
    assert request.selected_thread_metadata["requested_field"] == "assumption"
    assert answer_result["stage_outcome"] == "await_approval"
    strategy = answer_result["confirmation_payload"]["strategy"]
    assert strategy["asset_universe"] == ["AAPL"]
    assert strategy["date_range"] == {"start": "2025-06-14", "end": "2026-06-12"}
    assert strategy["comparison_baseline"] == "SPY"
    assert strategy.get("capital_amount") is None
    assert (
        answer_result["confirmation_payload"]["optional_parameters"]["initial_capital"][
            "value"
        ]
        == 250000
    )
    assert answer_result["pending_strategy"]["requested_field"] is None
    assert answer_result["pending_strategy"]["missing_required_fields"] == []


@pytest.mark.asyncio
async def test_workflow_spanish_change_asset_answer_reenters_interpreter(
    monkeypatch,
) -> None:
    from argus.agent_runtime import resolution as resolution_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        normalized = symbol.strip().casefold()
        if normalized in {"google", "googl"}:
            return ResolvedAssetStub("GOOGL", "equity")
        return ResolvedAssetStub(symbol.upper(), "equity")

    monkeypatch.setattr(resolution_module, "resolve_market_asset", resolve_stub)

    interpreter = SpanishAssetAnswerInterpreter()
    workflow = build_workflow(
        structured_interpreter=interpreter,
        checkpointer=MemorySaver(),
    )
    user = UserState(user_id="u1", language_preference="es-419")
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Comprar y mantener AAPL.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2025-06-14", "end": "2026-06-12"},
        capital_amount=100000,
        comparison_baseline="SPY",
    )
    thread_id = "thread-spanish-change-asset-answer"

    prompt_result = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id=thread_id,
        message="Cambiar activo",
        action_context={
            "type": "change_asset",
            "label": "Cambiar activo",
            "presentation": "confirmation",
            "payload": {},
        },
        fallback_latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=pending,
        ),
        fallback_selected_thread_metadata={"last_stage_outcome": "await_approval"},
    )

    assert interpreter.requests == []
    assert prompt_result["stage_outcome"] == "await_user_reply"
    assert prompt_result["pending_strategy"]["requested_field"] == "asset_universe"
    assert prompt_result["pending_strategy"]["missing_required_fields"] == [
        "asset_universe"
    ]

    answer_result = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id=thread_id,
        message="ponlo con google mejor",
    )

    assert len(interpreter.requests) == 1
    request = interpreter.requests[0]
    assert request.user.language_preference == "es-419"
    assert request.latest_task_snapshot is not None
    assert request.latest_task_snapshot.pending_strategy_summary is not None
    assert request.selected_thread_metadata["requested_field"] == "asset_universe"
    assert answer_result["stage_outcome"] == "await_approval"
    strategy = answer_result["confirmation_payload"]["strategy"]
    assert strategy["strategy_type"] == "buy_and_hold"
    assert strategy["asset_universe"] == ["GOOGL"]
    assert strategy["asset_class"] == "equity"
    assert strategy["date_range"] == {"start": "2025-06-14", "end": "2026-06-12"}
    assert strategy["capital_amount"] == 100000
    assert strategy["comparison_baseline"] == "SPY"
    assert "assistant_response" not in answer_result
    assert answer_result["pending_strategy"]["requested_field"] is None
    assert answer_result["pending_strategy"]["missing_required_fields"] == []


@pytest.mark.asyncio
async def test_workflow_routes_from_stage_outcome_without_persisting_route() -> None:
    workflow = build_workflow(
        structured_interpreter=ConversationalInterpreter(),
        checkpointer=MemorySaver(),
    )

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1", expertise_level="beginner"),
        thread_id="thread-1",
        message="what can you do?",
    )
    assert result["stage_outcome"] == "ready_to_respond"
    assert result["assistant_response"] == (
        "I help turn investing ideas into supported backtests."
    )
    assert "route" not in result


@pytest.mark.asyncio
async def test_workflow_streams_stage_events_and_final_payload() -> None:
    workflow = build_workflow(
        structured_interpreter=ConversationalInterpreter(),
        checkpointer=MemorySaver(),
    )
    user = UserState(user_id="u1", expertise_level="advanced")

    events = [
        event
        async for event in stream_agent_turn_events(
            workflow=workflow,
            user=user,
            thread_id="thread-events",
            message="what can you do?",
        )
    ]

    assert events[0] == {"type": "stage_start", "stage": "interpret"}
    assert {"type": "stage_outcome", "outcome": "ready_to_respond"} in events
    assert events[-1]["type"] == "final"
    assert events[-1]["payload"]["assistant_response"] == (
        "I help turn investing ideas into supported backtests."
    )


@pytest.mark.asyncio
async def test_workflow_preserves_pending_draft_after_interpreter_recovery() -> None:
    workflow = build_workflow(checkpointer=MemorySaver())
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range="past year",
        capital_amount=10000,
    )

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1", expertise_level="beginner"),
        thread_id="thread-recovery",
        message="actually make it NVDA",
        fallback_latest_task_snapshot=TaskSnapshot(
            latest_task_type="backtest_execution",
            completed=False,
            pending_strategy_summary=pending,
        ),
        fallback_selected_thread_metadata={"last_stage_outcome": "await_approval"},
    )

    assert result["stage_outcome"] == "ready_to_respond"
    assert "AAPL" in result["assistant_response"]
    state_snapshot = await workflow.aget_state(
        {"configurable": {"thread_id": "thread-recovery"}}
    )
    snapshot = state_snapshot.values["latest_task_snapshot"]
    assert snapshot.completed is False
    assert snapshot.pending_strategy_summary is not None
    assert snapshot.pending_strategy_summary.asset_universe == ["AAPL"]
    assert snapshot.confirmed_strategy_summary is None


@pytest.mark.asyncio
async def test_workflow_uses_checkpointer_for_thread_state(monkeypatch) -> None:
    from argus.agent_runtime import resolution as resolution_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        asset_class = "crypto" if symbol.upper() == "BTC" else "equity"
        return ResolvedAssetStub(symbol.upper(), asset_class)

    monkeypatch.setattr(resolution_module, "resolve_market_asset", resolve_stub)

    interpreter = ApprovalInterpreter()
    workflow = build_workflow(
        structured_interpreter=interpreter,
        checkpointer=MemorySaver(),
    )
    user = UserState(user_id="u1", expertise_level="advanced")

    first = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id="thread-checkpoint",
        message="Buy and hold Bitcoin over the last year.",
    )
    second = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id="thread-checkpoint",
        message="yes, run it",
    )

    assert first["stage_outcome"] == "await_approval"
    assert interpreter.seen_snapshots[0] is None
    snapshot = interpreter.seen_snapshots[1]
    assert snapshot is not None
    assert snapshot.pending_strategy_summary is not None
    assert snapshot.pending_strategy_summary.asset_universe == ["BTC"]
    assert second["stage_outcome"] == "ready_to_respond"
    assert "visible confirmation" in second["assistant_response"]
    assert "simulation" in second["assistant_response"]
    assert "run" not in second
