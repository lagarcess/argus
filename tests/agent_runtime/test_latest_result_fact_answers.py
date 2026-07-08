# ruff: noqa: F403, F405
from __future__ import annotations

from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.profile.response_profile import (
    resolve_effective_response_profile,
)
from argus.agent_runtime.result_followups import result_followup_fact_bank
from argus.agent_runtime.runtime import run_agent_turn
from argus.agent_runtime.stages.interpret_internal import (
    latest_result_answer as latest_result_answer_module,
)
from argus.agent_runtime.stages.interpret_internal.latest_result_answer import (
    LatestResultFactComposerDeclined,
    latest_result_answer_stage_result_if_applicable,
)
from argus.agent_runtime.stages.interpret_types import (
    InterpretDecision,
    StructuredInterpretation,
)
from langgraph.checkpoint.memory import MemorySaver

from tests.agent_runtime._llm_interpreter_common import *


def _latest_result_reference(*, include_curve: bool = True) -> ArtifactReference:
    metadata = {
        "run_id": "run-140",
        "conversation_id": "conversation-140",
        "strategy_id": "strategy-140",
        "asset_class": "equity",
        "symbols": ["COST", "TGT"],
        "benchmark_symbol": "SPY",
        "metrics": {
            "aggregate": {
                "performance": {
                    "total_return_pct": 28.4,
                    "portfolio_value_range": {
                        "peak_value": 14500.25,
                        "lowest_value": 9100.0,
                        "currency": "USD",
                        "source": "strategy_portfolio_equity_close",
                    },
                },
                "risk": {"max_drawdown_pct": -12.3},
            },
            "by_symbol": {},
        },
        "config_snapshot": {
            "template": "dca_accumulation",
            "symbols": ["COST", "TGT"],
            "date_range": {"start": "2020-02-01", "end": "2026-07-02"},
        },
        "result_card": {
            "execution_costs": {
                "fee_bps": 10.0,
                "slippage_bps": 5.0,
                "gross_total_return_pct": 28.9,
                "net_total_return_pct": 28.4,
                "return_drag_pct": 0.5,
                "benchmark_treatment": "same_modeled_costs",
            }
        },
    }
    if include_curve:
        metadata["chart"] = {
            "kind": "portfolio_equity",
            "currency": "USD",
            "series": [
                {"time": "2020-02-03", "value": 10000.0},
                {"time": "2021-11-09", "value": 14500.25},
                {"time": "2022-06-16", "value": 12716.72},
                {"time": "2026-07-02", "value": 13900.0},
            ],
            "value_summary": {
                "peak_value": 14500.25,
                "lowest_value": 10000.0,
                "currency": "USD",
                "source": "strategy_portfolio_equity_close",
            },
        }
    return ArtifactReference(
        artifact_kind="backtest_result",
        artifact_id="run-140",
        artifact_status="completed",
        metadata=metadata,
    )


def _decision(focus: str) -> InterpretDecision:
    user = UserState(user_id="u1")
    return InterpretDecision(
        intent="results_explanation",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asked about the latest result.",
        candidate_strategy_draft=StrategySummary(),
        missing_required_fields=[],
        optional_parameter_opportunity=[],
        confidence=0.9,
        arbitration_mode="structured_arbitration",
        reason_codes=["llm_interpreter_used"],
        effective_response_profile=resolve_effective_response_profile(
            user=user,
            explicit_overrides=None,
        ),
        semantic_turn_act="result_followup",
        result_followup_focus=focus,
        artifact_target="latest_result",
    )


def _active_confirmation_fixture() -> ArtifactReference:
    from argus.agent_runtime.confirmation_artifacts import (
        confirmation_artifact_reference,
    )

    payload = {
        "strategy": {
            "strategy_type": "dca_accumulation",
            "strategy_thesis": "Six month recurring buys.",
            "asset_universe": ["COST", "TGT"],
            "asset_class": "equity",
            "date_range": {"start": "2026-01-04", "end": "2026-07-03"},
            "cadence": "monthly",
        },
        "optional_parameters": {},
        "launch_payload": {
            "strategy_type": "dca_accumulation",
            "symbol": "COST",
            "symbols": ["COST", "TGT"],
            "timeframe": "1D",
            "date_range": {"start": "2026-01-04", "end": "2026-07-03"},
            "entry_rule": None,
            "exit_rule": None,
            "sizing_mode": "capital_amount",
            "capital_amount": 500,
            "position_size": None,
            "cadence": "monthly",
            "parameters": {"recurring_contribution": 500},
            "risk_rules": [],
            "benchmark_symbol": "SPY",
            "language": "en",
        },
        "validation": {"status": "ready_to_run", "executable": True},
    }
    return confirmation_artifact_reference(
        confirmation_id="confirm-6mo",
        confirmation_payload=payload,
    )


def _snapshot(
    *,
    include_curve: bool = True,
    pending: bool = False,
    confirmation: bool = False,
) -> TaskSnapshot:
    reference = _latest_result_reference(include_curve=include_curve)
    confirmation_reference = _active_confirmation_fixture() if confirmation else None
    return TaskSnapshot(
        latest_task_type="results_explanation",
        completed=True,
        pending_strategy_summary=(
            StrategySummary(
                strategy_type="dca_accumulation",
                strategy_thesis="Refine the latest result.",
                asset_universe=["COST", "TGT"],
                asset_class="equity",
                date_range={"start": "2020-02-01", "end": "2026-07-02"},
                cadence="monthly",
                extra_parameters={"recurring_contribution": 500},
            )
            if pending or confirmation
            else None
        ),
        latest_backtest_result_reference=reference,
        active_confirmation_reference=confirmation_reference,
        artifact_references=(
            [reference, confirmation_reference]
            if confirmation_reference is not None
            else [reference]
        ),
    )


class _StaticInterpreter:
    def __init__(self, response: StructuredInterpretation) -> None:
        self.response = response
        self.requests: list[InterpretationRequest] = []

    def __call__(self, request: InterpretationRequest) -> StructuredInterpretation:
        self.requests.append(request)
        return self.response


class _RecordingComposer:
    """Stub for the LLM composer: captures kwargs, returns canned prose."""

    def __init__(self, response: str | None = "COMPOSED_FACT_ANSWER") -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> str | None:
        self.calls.append(kwargs)
        return self.response


class _MessageSwitchInterpreter:
    def __init__(self, responses: dict[str, StructuredInterpretation]) -> None:
        self.responses = responses
        self.requests: list[InterpretationRequest] = []

    def __call__(self, request: InterpretationRequest) -> StructuredInterpretation:
        self.requests.append(request)
        return self.responses[request.current_user_message]


class _SequencedComposer:
    def __init__(self, responses: list[str | None]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> str | None:
        self.calls.append(kwargs)
        index = len(self.calls) - 1
        return self.responses[index] if index < len(self.responses) else None


def test_fact_bank_is_enriched_with_curve_and_supplemental_facts() -> None:
    fact_bank = result_followup_fact_bank(
        dict(_latest_result_reference().metadata)
    )

    assert fact_bank["peak_value"] == "$14,500.25"
    assert fact_bank["peak_date"] == "2021-11-09"
    assert fact_bank["lowest_value"] == "$10,000"
    assert fact_bank["lowest_date"] == "2020-02-03"
    assert fact_bank["final_value"] == "$13,900"
    assert fact_bank["final_date"] == "2026-07-02"
    assert fact_bank["drawdown_date"] == "2022-06-16"
    assert fact_bank["drawdown_depth"] == "12.3%"
    # Canonical entries stay owned by the bank, not the enrichment pass.
    assert fact_bank["total_return"] == "+28.4%"


def test_fact_bank_enrichment_falls_back_to_value_summaries_without_curve() -> None:
    fact_bank = result_followup_fact_bank(
        dict(_latest_result_reference(include_curve=False).metadata)
    )

    assert fact_bank["peak_value"] == "$14,500.25"
    assert "peak_date" not in fact_bank
    assert "drawdown_date" not in fact_bank


@pytest.mark.asyncio
async def test_latest_result_peak_date_answer_composes_from_typed_facts() -> None:
    composer = _RecordingComposer()

    result = await latest_result_answer_stage_result_if_applicable(
        decision=_decision("peak_date"),
        snapshot=_snapshot(),
        current_user_message="what date did this strategy peak in value?",
        language="en",
        compose_response_func=composer,
    )

    assert result is not None
    # Composed prose passes through verbatim — no baked markdown heading.
    assert result.patch["assistant_response"] == "COMPOSED_FACT_ANSWER"
    assert len(composer.calls) == 1
    call = composer.calls[0]
    assert call["focus"] == "peak_date"
    assert call["fact_key"] == "peak_date"
    assert call["language"] == "en"
    assert call["user_message"] == "what date did this strategy peak in value?"
    facts = result.patch["response_intent"]["facts"]
    assert result.patch["response_intent"]["kind"] == "beginner_guidance"
    assert facts["fact_key"] == "peak_date"
    assert facts["peak_date"] == "2021-11-09"
    assert facts["peak_value"] == "$14,500.25"
    assert result.patch["result_run_id"] == "run-140"
    assert result.patch["latest_run_id"] == "run-140"
    assert result.patch["result_conversation_id"] == "conversation-140"
    assert "latest_result_fact_answer" in result.decision.reason_codes


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fact_key", "expected_fact"),
    [
        ("fee_bps", {"fee_bps": "10 bps"}),
        ("slippage_bps", {"slippage_bps": "5 bps"}),
        (
            "gross_total_return",
            {
                "gross_total_return": "+28.9%",
                "net_total_return": "+28.4%",
            },
        ),
        (
            "return_drag",
            {"return_drag": "0.5 percentage points"},
        ),
        (
            "benchmark_cost_treatment",
            {
                "benchmark_cost_treatment": (
                    "Benchmark used the same modeled costs"
                )
            },
        ),
    ],
)
async def test_latest_result_execution_cost_answer_composes_from_typed_facts(
    fact_key: str,
    expected_fact: dict[str, str],
) -> None:
    composer = _RecordingComposer()
    decision = _decision("result_card_fact").model_copy(
        update={"result_followup_fact_key": fact_key}
    )

    result = await latest_result_answer_stage_result_if_applicable(
        decision=decision,
        snapshot=_snapshot(),
        current_user_message="what execution costs did this use?",
        language="en",
        compose_response_func=composer,
    )

    assert result is not None
    assert result.patch["assistant_response"] == "COMPOSED_FACT_ANSWER"
    assert composer.calls[0]["fact_key"] == fact_key
    facts = result.patch["response_intent"]["facts"]
    assert facts["fact_key"] == fact_key
    for key, value in expected_fact.items():
        assert facts[key] == value
    assert facts["source"] == "result_followup_fact_bank"
    assert "latest_result_fact_answer" in result.decision.reason_codes


@pytest.mark.asyncio
async def test_stage_declines_untyped_focus_without_fact_key() -> None:
    # Untyped focus stays out of the fact stage; the composer chain owns it.
    composer = _RecordingComposer()
    decision = _decision("general").model_copy(
        update={
            "result_followup_focus": "general",
            "result_followup_fact_key": None,
        }
    )

    result = await latest_result_answer_stage_result_if_applicable(
        decision=decision,
        snapshot=_snapshot(),
        current_user_message="what date did this peak?",
        language="en",
        compose_response_func=composer,
    )

    assert result is None
    assert composer.calls == []


@pytest.mark.asyncio
async def test_latest_result_drawdown_date_pairs_depth_with_trough_date() -> None:
    composer = _RecordingComposer()

    result = await latest_result_answer_stage_result_if_applicable(
        decision=_decision("drawdown_date"),
        snapshot=_snapshot(),
        current_user_message="when was the worst drawdown?",
        language="en",
        compose_response_func=composer,
    )

    assert result is not None
    facts = result.patch["response_intent"]["facts"]
    assert facts["drawdown_date"] == "2022-06-16"
    # Depth is computed at the same trough as the date.
    assert facts["drawdown_depth"] == "12.3%"


@pytest.mark.asyncio
async def test_fact_answer_passes_detected_turn_language_through() -> None:
    composer = _RecordingComposer()
    decision = _decision("peak_date").model_copy(
        update={
            "detected_user_language": "es-419",
            "candidate_strategy_draft": StrategySummary(
                extra_parameters={"language": "en"}
            ),
        }
    )

    result = await latest_result_answer_stage_result_if_applicable(
        decision=decision,
        snapshot=_snapshot(),
        current_user_message="¿En qué fecha alcanzó su punto máximo?",
        language="en",
        compose_response_func=composer,
    )

    assert result is not None
    assert composer.calls[0]["language"] == "es-419"


@pytest.mark.asyncio
async def test_fact_answer_is_language_agnostic_for_any_detected_language() -> None:
    # A French turn reaches the composer as fr — not collapsed to en or es.
    composer = _RecordingComposer()
    decision = _decision("peak_date").model_copy(
        update={"detected_user_language": "fr"}
    )

    result = await latest_result_answer_stage_result_if_applicable(
        decision=decision,
        snapshot=_snapshot(),
        current_user_message="À quelle date le portefeuille a-t-il atteint son sommet ?",
        language="en",
        compose_response_func=composer,
    )

    assert result is not None
    assert composer.calls[0]["language"] == "fr"


@pytest.mark.asyncio
async def test_non_canonical_fact_key_normalizes_mechanically() -> None:
    composer = _RecordingComposer()
    decision = _decision("result_card_fact").model_copy(
        update={"result_followup_fact_key": "Peak Date"}
    )

    result = await latest_result_answer_stage_result_if_applicable(
        decision=decision,
        snapshot=_snapshot(),
        current_user_message="peak date?",
        language="en",
        compose_response_func=composer,
    )

    assert result is not None
    assert composer.calls[0]["fact_key"] == "peak_date"
    assert result.decision.result_followup_fact_key == "peak_date"


@pytest.mark.asyncio
async def test_latest_result_missing_peak_date_returns_typed_limitation() -> None:
    composer = _RecordingComposer(response="COMPOSED_LIMITATION")

    result = await latest_result_answer_stage_result_if_applicable(
        decision=_decision("peak_date"),
        snapshot=_snapshot(include_curve=False),
        current_user_message="what date did it peak?",
        language="en",
        compose_response_func=composer,
    )

    assert result is not None
    assert result.patch["assistant_response"] == "COMPOSED_LIMITATION"
    call = composer.calls[0]
    assert "requested_fact_unavailable" in call["extra_facts"]
    assert "available_result_facts" in call["extra_facts"]
    intent = result.patch["response_intent"]
    assert intent["kind"] == "unsupported_recovery"
    assert intent["facts"]["limitation_code"] == "latest_result_metric_unavailable"
    assert intent["facts"]["requested_metric"] == "peak_date"
    assert "peak_value" in intent["facts"]["available_result_facts"]
    assert intent["options"][0]["replacement_values"] == {
        "semantic_turn_act": "result_followup",
        "artifact_target": "latest_result",
    }
    assert "latest_result_fact_limitation" in result.decision.reason_codes


@pytest.mark.asyncio
async def test_latest_result_unknown_metric_returns_typed_limitation() -> None:
    composer = _RecordingComposer(response="COMPOSED_LIMITATION")

    result = await latest_result_answer_stage_result_if_applicable(
        decision=_decision("result_card_fact").model_copy(
            update={"result_followup_fact_key": "sortino_ratio"}
        ),
        snapshot=_snapshot(),
        current_user_message="What was the Sortino ratio?",
        language="en",
        compose_response_func=composer,
    )

    assert result is not None
    facts = result.patch["response_intent"]["facts"]
    assert facts["limitation_code"] == "latest_result_metric_unavailable"
    assert facts["requested_metric"] == "sortino_ratio"
    assert "total_return" in facts["available_result_facts"]
    assert "latest_result_fact_limitation" in result.decision.reason_codes


@pytest.mark.asyncio
async def test_latest_result_context_packet_ids_routes_to_limitation() -> None:
    composer = _RecordingComposer(response="COMPOSED_LIMITATION")
    reference = _latest_result_reference()
    metadata = dict(reference.metadata)
    metadata["context_packets"] = [
        {
            "id": "context-packet-1",
            "packet_type": "macro",
            "facts": [
                {
                    "label": "Fed funds latest observation",
                    "value": "5.25%",
                }
            ],
        }
    ]
    snapshot = TaskSnapshot(
        latest_task_type="results_explanation",
        completed=True,
        latest_backtest_result_reference=reference.model_copy(
            update={"metadata": metadata}
        ),
        artifact_references=[
            reference.model_copy(update={"metadata": metadata}),
        ],
    )

    result = await latest_result_answer_stage_result_if_applicable(
        decision=_decision("result_card_fact").model_copy(
            update={"result_followup_fact_key": "context_packet_ids"}
        ),
        snapshot=snapshot,
        current_user_message="Which context packet did this use?",
        language="en",
        compose_response_func=composer,
    )

    assert result is not None
    assert result.patch["assistant_response"] == "COMPOSED_LIMITATION"
    assert composer.calls[0].get("fact_key") is None
    facts = result.patch["response_intent"]["facts"]
    assert facts["limitation_code"] == "latest_result_metric_unavailable"
    assert facts["requested_metric"] == "context_packet_ids"
    assert "context_packet_ids" not in facts["available_result_facts"]
    assert "latest_result_fact_limitation" in result.decision.reason_codes


@pytest.mark.asyncio
async def test_stage_signals_typed_decline_when_composition_fails() -> None:
    # Composer refusal on a resolved fact key is a typed decline signal so the
    # stage can try the edit planner before the recovery chain (#160).
    composer = _RecordingComposer(response=None)

    result = await latest_result_answer_stage_result_if_applicable(
        decision=_decision("peak_date"),
        snapshot=_snapshot(),
        current_user_message="what date did it peak?",
        language="en",
        compose_response_func=composer,
    )

    assert isinstance(result, LatestResultFactComposerDeclined)
    assert result.fact_key == "peak_date"
    assert len(composer.calls) == 1


@pytest.mark.asyncio
async def test_pending_refine_result_question_answers_without_clearing_pending_state() -> None:
    composer = _RecordingComposer()
    snapshot = _snapshot(pending=True)

    result = await latest_result_answer_stage_result_if_applicable(
        decision=_decision("peak_date").model_copy(
            update={"artifact_target": "pending_refinement"}
        ),
        snapshot=snapshot,
        current_user_message="what date did this strategy peak in value?",
        language="en",
        compose_response_func=composer,
    )

    assert result is not None
    assert result.outcome == "ready_to_respond"
    assert snapshot.pending_strategy_summary is not None
    assert snapshot.pending_strategy_summary.asset_universe == ["COST", "TGT"]
    assert result.patch["candidate_strategy_draft"]["asset_universe"] == []
    assert "requested_field" not in result.stage_patch
    assert result.patch["result_run_id"] == "run-140"


@pytest.mark.asyncio
async def test_workflow_latest_result_fact_answer_uses_typed_turn_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    composer = _RecordingComposer(
        response="El valor máximo de la cartera fue $14,500.25 el 2021-11-09."
    )
    monkeypatch.setattr(
        latest_result_answer_module,
        "compose_result_followup_response",
        composer,
    )
    interpreter = _StaticInterpreter(
        StructuredInterpretation(
            intent="results_explanation",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="El usuario preguntó por el punto máximo.",
            detected_user_language="es-419",
            semantic_turn_act="result_followup",
            result_followup_focus="peak_date",
            artifact_target="latest_result",
            confidence=0.9,
        )
    )
    workflow = build_workflow(
        structured_interpreter=interpreter,
        checkpointer=MemorySaver(),
    )

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1", language_preference="en"),
        thread_id="thread-issue-140-spanish-turn-language",
        message="¿En qué fecha alcanzó su punto máximo?",
        fallback_latest_task_snapshot=_snapshot(),
    )

    assert result["stage_outcome"] == "ready_to_respond"
    assert result["assistant_response"] == (
        "El valor máximo de la cartera fue $14,500.25 el 2021-11-09."
    )
    # Heading chrome is rendered by the frontend from the typed fact key.
    assert not result["assistant_response"].startswith("**")
    assert composer.calls[0]["language"] == "es-419"
    assert result["response_intent"]["facts"]["fact_key"] == "peak_date"


@pytest.mark.asyncio
async def test_workflow_refine_then_result_fact_answer_keeps_pending_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    composer = _RecordingComposer(
        response="The peak portfolio value was $14,500.25 on 2021-11-09."
    )
    monkeypatch.setattr(
        latest_result_answer_module,
        "compose_result_followup_response",
        composer,
    )
    interpreter = _StaticInterpreter(
        StructuredInterpretation(
            intent="results_explanation",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User asked about the latest result peak.",
            semantic_turn_act="result_followup",
            result_followup_focus="peak_date",
            artifact_target="latest_result",
            confidence=0.9,
        )
    )
    workflow = build_workflow(
        structured_interpreter=interpreter,
        checkpointer=MemorySaver(),
    )
    thread_id = "thread-issue-140-refine-fact"

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1"),
        thread_id=thread_id,
        message="what date did this strategy peak in value?",
        fallback_latest_task_snapshot=_snapshot(pending=True),
        fallback_selected_thread_metadata={
            "latest_task_type": "backtest_execution",
            "last_stage_outcome": "await_user_reply",
            "requested_field": "refinement",
            "source_result_run_id": "run-140",
        },
    )

    assert result["stage_outcome"] == "ready_to_respond"
    assert "2021-11-09" in result["assistant_response"]
    assert result["latest_run_id"] == "run-140"
    assert result["result_run_id"] == "run-140"
    state = await workflow.aget_state({"configurable": {"thread_id": thread_id}})
    snapshot = state.values["latest_task_snapshot"]
    assert snapshot.pending_strategy_summary is not None
    assert snapshot.pending_strategy_summary.asset_universe == ["COST", "TGT"]
    assert state.values["selected_thread_metadata"]["requested_field"] == "refinement"


@pytest.mark.asyncio
async def test_workflow_fact_answer_then_composer_none_edit_reroutes_to_planner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.artifact_edit_planner import (
        ArtifactAssumptionEditPlan,
        EditOperation,
    )
    from argus.agent_runtime.stages import interpret as interpret_module

    fact_message = "what date did this strategy peak in value?"
    edit_message = "change starting capital to $2,000"
    composer = _SequencedComposer(
        ["The peak portfolio value was $14,500.25 on 2021-11-09.", None]
    )
    monkeypatch.setattr(
        latest_result_answer_module,
        "compose_result_followup_response",
        composer,
    )
    monkeypatch.setattr(
        interpret_module,
        "compose_result_followup_response",
        composer,
    )

    planner_calls: list[dict[str, object]] = []

    async def planned_capital_edit(**kwargs: object) -> ArtifactAssumptionEditPlan:
        planner_calls.append(kwargs)
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            user_goal_summary="User set starting capital to $2,000.",
            operations=[
                EditOperation(op="set", target="capital", number=2000),
            ],
            confidence=0.95,
        )

    monkeypatch.setattr(
        interpret_module,
        "plan_artifact_assumption_edit",
        planned_capital_edit,
    )

    interpreter = _MessageSwitchInterpreter(
        {
            fact_message: StructuredInterpretation(
                intent="results_explanation",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="User asked about the latest result peak.",
                semantic_turn_act="result_followup",
                result_followup_focus="peak_date",
                artifact_target="latest_result",
                confidence=0.9,
            ),
            edit_message: StructuredInterpretation(
                intent="results_explanation",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="User wants to change starting capital.",
                semantic_turn_act="result_followup",
                result_followup_focus="result_card_fact",
                result_followup_fact_key="starting_capital",
                artifact_target="latest_result",
                confidence=0.9,
            ),
        }
    )
    workflow = build_workflow(
        structured_interpreter=interpreter,
        checkpointer=MemorySaver(),
    )
    thread_id = "thread-issue-160-composer-none-edit"

    first = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1"),
        thread_id=thread_id,
        message=fact_message,
        fallback_latest_task_snapshot=_snapshot(pending=True),
        fallback_selected_thread_metadata={
            "latest_task_type": "backtest_execution",
            "last_stage_outcome": "await_user_reply",
            "requested_field": "refinement",
            "source_result_run_id": "run-140",
        },
    )

    assert first["stage_outcome"] == "ready_to_respond"

    second = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1"),
        thread_id=thread_id,
        message=edit_message,
    )

    assert planner_calls
    # The planned edit lands in the typed edit contract: the DCA money-role
    # guard owns the turn instead of the terminal followup recovery.
    assert second["stage_outcome"] == "await_user_reply"
    clarification = second["clarification"]
    assert clarification["reason_code"] == "unsupported_dca_starting_principal"
    anchored = clarification["payload"]["strategy"]
    assert anchored["asset_universe"] == ["COST", "TGT"]
    assert anchored["extra_parameters"]["recurring_contribution"] == 500
    assert "latest_result_followup_unavailable" not in str(second)


@pytest.mark.asyncio
async def test_workflow_post_result_composer_none_edit_without_pending_reroutes_to_planner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No-chip twin of the composer-decline reroute: nothing pending, so the
    planned edit anchors on the strategy that actually ran (#160)."""

    from argus.agent_runtime.artifact_edit_planner import (
        ArtifactAssumptionEditPlan,
        EditOperation,
    )
    from argus.agent_runtime.stages import interpret as interpret_module
    from argus.agent_runtime.stages import interpret_actions as interpret_actions_module

    composer = _RecordingComposer(response=None)
    monkeypatch.setattr(
        latest_result_answer_module,
        "compose_result_followup_response",
        composer,
    )
    monkeypatch.setattr(
        interpret_module,
        "compose_result_followup_response",
        composer,
    )
    monkeypatch.setattr(
        interpret_actions_module,
        "compose_result_followup_response",
        composer,
    )

    planner_calls: list[dict[str, object]] = []

    async def planned_capital_edit(**kwargs: object) -> ArtifactAssumptionEditPlan:
        planner_calls.append(kwargs)
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            user_goal_summary="User set starting capital to $2,000.",
            operations=[
                EditOperation(op="set", target="capital", number=2000),
            ],
            confidence=0.95,
        )

    monkeypatch.setattr(
        interpret_module,
        "plan_artifact_assumption_edit",
        planned_capital_edit,
    )

    interpreter = _StaticInterpreter(
        StructuredInterpretation(
            intent="results_explanation",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User wants to change starting capital.",
            semantic_turn_act="result_followup",
            result_followup_focus="result_card_fact",
            result_followup_fact_key="starting_capital",
            artifact_target="latest_result",
            confidence=0.9,
        )
    )
    workflow = build_workflow(
        structured_interpreter=interpreter,
        checkpointer=MemorySaver(),
    )

    reference = _latest_result_reference()
    reference.metadata["config_snapshot"]["resolved_parameters"] = {
        "date_range": {"start": "2020-02-01", "end": "2026-07-02"},
        "cadence": "monthly",
        "recurring_contribution": 500,
    }
    snapshot = TaskSnapshot(
        latest_task_type="results_explanation",
        completed=True,
        latest_backtest_result_reference=reference,
        artifact_references=[reference],
    )

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1"),
        thread_id="thread-issue-160-composer-none-no-pending",
        message="change starting capital to $2,000",
        fallback_latest_task_snapshot=snapshot,
        fallback_selected_thread_metadata={
            "latest_task_type": "results_explanation",
            "last_stage_outcome": "ready_to_respond",
        },
    )

    assert planner_calls
    assert result["stage_outcome"] == "await_user_reply"
    clarification = result["clarification"]
    assert clarification["reason_code"] == "unsupported_dca_starting_principal"
    anchored = clarification["payload"]["strategy"]
    assert anchored["asset_universe"] == ["COST", "TGT"]
    assert "latest_result_followup_unavailable" not in str(result)


@pytest.mark.asyncio
async def test_workflow_composer_none_without_edit_plan_keeps_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the planner has no edit either, the composer decline degrades to
    the existing followup recovery — the guard never invents a route."""

    from argus.agent_runtime.stages import interpret as interpret_module
    from argus.agent_runtime.stages import interpret_actions as interpret_actions_module

    composer = _RecordingComposer(response=None)
    monkeypatch.setattr(
        latest_result_answer_module,
        "compose_result_followup_response",
        composer,
    )
    monkeypatch.setattr(
        interpret_module,
        "compose_result_followup_response",
        composer,
    )
    monkeypatch.setattr(
        interpret_actions_module,
        "compose_result_followup_response",
        composer,
    )

    async def no_edit_plan(**kwargs: object) -> None:
        return None

    monkeypatch.setattr(
        interpret_module,
        "plan_artifact_assumption_edit",
        no_edit_plan,
    )

    interpreter = _StaticInterpreter(
        StructuredInterpretation(
            intent="results_explanation",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User asked about an unstored result value.",
            semantic_turn_act="result_followup",
            result_followup_focus="result_card_fact",
            result_followup_fact_key="starting_capital",
            artifact_target="latest_result",
            confidence=0.9,
        )
    )
    workflow = build_workflow(
        structured_interpreter=interpreter,
        checkpointer=MemorySaver(),
    )

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1"),
        thread_id="thread-issue-160-composer-none-no-plan",
        message="what was the starting capital?",
        fallback_latest_task_snapshot=_snapshot(),
        fallback_selected_thread_metadata={
            "latest_task_type": "results_explanation",
            "last_stage_outcome": "ready_to_respond",
        },
    )

    assert result["stage_outcome"] == "ready_to_respond"
    assert "latest_result_followup_unavailable" in str(result)


@pytest.mark.asyncio
async def test_workflow_refine_result_question_with_strategy_baggage_does_not_confirm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    composer = _RecordingComposer(
        response="The peak portfolio value was $14,500.25 on 2021-11-09."
    )
    monkeypatch.setattr(
        latest_result_answer_module,
        "compose_result_followup_response",
        composer,
    )
    interpreter = _StaticInterpreter(
        StructuredInterpretation(
            intent="results_explanation",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User asked about the latest result peak.",
            candidate_strategy_draft=StrategySummary(
                strategy_type="dca_accumulation",
                asset_universe=["COST", "TGT"],
                asset_class="equity",
                date_range={"start": "2020-02-01", "end": "2026-07-02"},
                cadence="monthly",
                extra_parameters={"recurring_contribution": 500},
            ),
            semantic_turn_act="result_followup",
            result_followup_focus="peak_date",
            artifact_target="latest_result",
            confidence=0.9,
        )
    )
    workflow = build_workflow(
        structured_interpreter=interpreter,
        checkpointer=MemorySaver(),
    )

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1"),
        thread_id="thread-refine-result-question-strategy-baggage",
        message="what date did this peak?",
        fallback_latest_task_snapshot=_snapshot(),
        fallback_selected_thread_metadata={
            "latest_task_type": "backtest_execution",
            "last_stage_outcome": "await_user_reply",
            "requested_field": "refinement",
            "source_result_run_id": "run-140",
        },
    )

    assert result["stage_outcome"] == "ready_to_respond"
    assert "The peak portfolio value was $14,500.25 on 2021-11-09." in result[
        "assistant_response"
    ]
    assert composer.calls[0]["focus"] == "peak_date"
    assert composer.calls[0]["fact_key"] == "peak_date"


@pytest.mark.asyncio
async def test_workflow_result_fact_limitation_exposes_response_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    composer = _RecordingComposer(response="COMPOSED_LIMITATION")
    monkeypatch.setattr(
        latest_result_answer_module,
        "compose_result_followup_response",
        composer,
    )
    interpreter = _StaticInterpreter(
        StructuredInterpretation(
            intent="results_explanation",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User asked about an unavailable result metric.",
            semantic_turn_act="result_followup",
            result_followup_focus="result_card_fact",
            result_followup_fact_key="sortino_ratio",
            artifact_target="latest_result",
            confidence=0.9,
        )
    )
    workflow = build_workflow(
        structured_interpreter=interpreter,
        checkpointer=MemorySaver(),
    )

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1"),
        thread_id="thread-issue-140-unsupported-result-fact",
        message="What was the Sortino ratio?",
        fallback_latest_task_snapshot=_snapshot(),
    )

    assert result["stage_outcome"] == "ready_to_respond"
    assert result["response_intent"]["kind"] == "unsupported_recovery"
    facts = result["response_intent"]["facts"]
    assert facts["limitation_code"] == "latest_result_metric_unavailable"
    assert facts["requested_metric"] == "sortino_ratio"


@pytest.mark.asyncio
async def test_workflow_unknown_metric_during_active_confirmation_preserves_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    composer = _RecordingComposer(response="COMPOSED_LIMITATION")
    monkeypatch.setattr(
        latest_result_answer_module,
        "compose_result_followup_response",
        composer,
    )
    interpreter = _StaticInterpreter(
        StructuredInterpretation(
            intent="results_explanation",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User asked for the Sortino ratio mid-confirmation.",
            semantic_turn_act="result_followup",
            result_followup_focus="result_card_fact",
            result_followup_fact_key="sortino_ratio",
            artifact_target="active_confirmation",
            confidence=0.9,
        )
    )
    workflow = build_workflow(
        structured_interpreter=interpreter,
        checkpointer=MemorySaver(),
    )
    thread_id = "thread-issue-140-sortino-mid-confirmation"

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1"),
        thread_id=thread_id,
        message="what was the sortino ratio?",
        fallback_latest_task_snapshot=_snapshot(confirmation=True),
        fallback_selected_thread_metadata={
            "latest_task_type": "backtest_execution",
            "last_stage_outcome": "await_approval",
            "source_result_run_id": "run-140",
        },
    )

    assert result["stage_outcome"] == "ready_to_respond"
    assert result["assistant_response"] == "COMPOSED_LIMITATION"
    facts = result["response_intent"]["facts"]
    assert facts["limitation_code"] == "latest_result_metric_unavailable"
    assert facts["requested_metric"] == "sortino_ratio"
    assert result["result_run_id"] == "run-140"
    state = await workflow.aget_state({"configurable": {"thread_id": thread_id}})
    snapshot = state.values["latest_task_snapshot"]
    # The typed limitation answer must not consume the pending confirmation.
    assert snapshot.active_confirmation_reference is not None
    assert snapshot.pending_strategy_summary is not None
    assert snapshot.latest_backtest_result_reference is not None


def test_render_appends_runtime_pinned_facts_instead_of_rejecting() -> None:
    from argus.agent_runtime.result_followups import (
        ResultFollowupDraft,
        render_result_followup_draft,
    )

    fact_bank = {
        "caveat": "Historical simulation evidence, not a prediction",
        "symbols": "AAPL",
        "peak_date": "2026-06-02",
        "peak_value": "$1,501.36",
    }
    draft = ResultFollowupDraft(
        relative_performance_claim="unknown",
        causal_attribution_claim="none",
        answer="The peak was $1,501.36 on June 2, 2026.",
        answer_blocks=["The peak was $1,501.36 on June 2, 2026."],
        fact_ids=["caveat"],
    )
    required = {"caveat", "symbols", "peak_date", "peak_value"}

    # The runtime computed the pinned facts itself: a draft that omits them
    # from fact_ids gets them appended as a grounded fact line.
    rendered = render_result_followup_draft(
        draft=draft,
        fact_bank=fact_bank,
        required_fact_ids=required,
        focus="peak_date",
        extra_appendable_fact_ids={"symbols", "peak_date", "peak_value"},
    )
    assert rendered is not None
    assert "$1,501.36" in rendered

    # Without the appendable extension the same draft is rejected.
    assert (
        render_result_followup_draft(
            draft=draft,
            fact_bank=fact_bank,
            required_fact_ids=required,
            focus="peak_date",
        )
        is None
    )
