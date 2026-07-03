# ruff: noqa: F403, F405
"""Regression coverage for issue #141: a new idea referencing the prior
period ("try COST at $500/mo from the same time period") must bind to the
latest completed run's date range and materialize a full confirmation —
no verbal date re-ask, no repeated confirmation loop.

The interpreter emits the typed reference intent
`kind="same_as_latest_result"`; deterministic code resolves it against the
latest completed result's canonical window.
"""

from tests.agent_runtime._llm_interpreter_common import *


def _completed_result_reference() -> ArtifactReference:
    return ArtifactReference(
        artifact_kind="backtest_result",
        artifact_id="run-141",
        artifact_status="completed",
        metadata={
            "run_id": "run-141",
            "asset_class": "equity",
            "symbols": ["AAPL", "MSFT"],
            "benchmark_symbol": "SPY",
            "config_snapshot": {
                "template": "dca_accumulation",
                "symbols": ["AAPL", "MSFT"],
                "date_range": {"start": "2020-02-01", "end": "2026-07-02"},
                "resolved_parameters": {
                    "date_range": {"start": "2020-02-01", "end": "2026-07-02"},
                    "cadence": "monthly",
                    "recurring_contribution": 500,
                },
            },
        },
    )


def _same_period_new_idea_response() -> LLMInterpretationResponse:
    return LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary=(
            "User wants a new NVDA recurring-buy test over the same window as "
            "the completed run."
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Could we try to buy NVDA at 500 dollars a month from the "
                "same time period"
            ),
            strategy_type="dca_accumulation",
            strategy_thesis="Recurring monthly buys of NVDA.",
            asset_universe=["NVDA"],
            asset_class="equity",
            cadence="monthly",
            recurring_contribution=500,
            date_range_intent=LLMDateRangeIntent(
                kind="same_as_latest_result",
                confidence=0.9,
                evidence="from the same time period",
            ),
            evidence_spans={
                "asset_universe": "NVDA",
                "date_range": "from the same time period",
                "recurring_contribution": "500 dollars a month",
            },
            field_provenance={
                "asset_universe": "explicit_user",
                "recurring_contribution": "recurring_contribution",
            },
        ),
        semantic_turn_act="new_idea",
    )


@pytest.mark.asyncio
async def test_same_period_reference_binds_latest_result_window(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )
    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol, **kwargs: ResolvedAssetStub(
            symbol.strip().upper(), "equity", name="NVIDIA Corporation"
        ),
    )

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        if schema_model.__name__ == "LLMInterpretationResponse":
            return _same_period_new_idea_response()
        raise ValueError(f"unexpected schema request: {schema_model.__name__}")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(
        InterpretationRequest(
            current_user_message=(
                "Could we try to buy NVDA at 500 dollars a month from the "
                "same time period"
            ),
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                latest_task_type="backtest_execution",
                completed=True,
                latest_backtest_result_reference=_completed_result_reference(),
            ),
            selected_thread_metadata={
                "latest_task_type": "backtest_execution",
                "last_stage_outcome": "execution_succeeded",
            },
            user=UserState(user_id="u1"),
        )
    )

    assert result is not None
    draft = result.candidate_strategy_draft
    assert draft.date_range == {"start": "2020-02-01", "end": "2026-07-02"}
    assert draft.asset_universe == ["NVDA"]
    assert not result.requires_clarification
    assert "date_range" not in [
        str(field).partition(".")[0] for field in result.missing_required_fields
    ]


@pytest.mark.asyncio
async def test_pending_date_answer_with_period_reference_materializes_window(
    monkeypatch,
) -> None:
    """The repeated-confirmation loop: with a pending date_range request, an
    answer referencing the prior run's period must fill the pending draft's
    window instead of re-asking (issue #141 steps 2-5)."""

    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )
    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol, **kwargs: ResolvedAssetStub(
            symbol.strip().upper(), "equity", name="NVIDIA Corporation"
        ),
    )

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        if schema_model.__name__ == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="backtest_execution",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary=(
                    "User answered the date request with the prior run's window."
                ),
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing="the same period as the test we just ran",
                    strategy_type="dca_accumulation",
                    date_range_intent=LLMDateRangeIntent(
                        kind="same_as_latest_result",
                        confidence=0.9,
                        evidence="the same period as the test we just ran",
                    ),
                    evidence_spans={
                        "date_range": "the same period as the test we just ran",
                    },
                ),
                semantic_turn_act="answer_pending_need",
            )
        raise ValueError(f"unexpected schema request: {schema_model.__name__}")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(
        InterpretationRequest(
            current_user_message="the same period as the test we just ran",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                latest_task_type="backtest_execution",
                completed=False,
                pending_strategy_summary=StrategySummary(
                    strategy_type="dca_accumulation",
                    strategy_thesis="Recurring monthly buys of NVDA.",
                    asset_universe=["NVDA"],
                    asset_class="equity",
                    cadence="monthly",
                    extra_parameters={"recurring_contribution": 500},
                ),
                latest_backtest_result_reference=_completed_result_reference(),
            ),
            selected_thread_metadata={
                "latest_task_type": "backtest_execution",
                "last_stage_outcome": "await_user_reply",
                "requested_field": "date_range",
            },
            user=UserState(user_id="u1"),
        )
    )

    assert result is not None
    draft = result.candidate_strategy_draft
    assert draft.date_range == {"start": "2020-02-01", "end": "2026-07-02"}
    assert not result.requires_clarification
    assert "date_range" not in [
        str(field).partition(".")[0] for field in result.missing_required_fields
    ]


def test_same_period_reference_without_result_still_asks_for_dates() -> None:
    """Without a completed run to bind to, the reference intent must not
    invent dates — the normal date clarification stays."""

    from argus.agent_runtime.llm_interpreter import (
        _response_with_latest_result_window_bound,
    )
    from argus.agent_runtime.stages.interpret import InterpretationRequest

    response = _same_period_new_idea_response()
    request = InterpretationRequest(
        current_user_message=(
            "Could we try to buy NVDA at 500 dollars a month from the same "
            "time period"
        ),
        recent_thread_history=[],
        latest_task_snapshot=None,
        selected_thread_metadata={},
        user=UserState(user_id="u1"),
    )

    bound = _response_with_latest_result_window_bound(response, request=request)

    assert bound.candidate_strategy_draft.date_range is None


def test_pending_gap_fill_ignores_boolean_recurring_contribution() -> None:
    """A JSON boolean in the pending extra_parameters must not be coerced
    into a $1.00 recurring contribution (bool is an int subclass)."""

    from argus.agent_runtime.interpreter.date_window_repair import (
        _draft_with_pending_strategy_gaps_filled,
    )
    from argus.agent_runtime.stages.interpret import InterpretationRequest

    pending = StrategySummary(
        strategy_type="dca_accumulation",
        asset_universe=["AAPL"],
        extra_parameters={"recurring_contribution": True},
    )
    request = InterpretationRequest(
        current_user_message="same period as the last test",
        recent_thread_history=[],
        latest_task_snapshot=TaskSnapshot(
            latest_task_type="backtest_execution",
            completed=False,
            pending_strategy_summary=pending,
        ),
        selected_thread_metadata={},
        user=UserState(user_id="u1"),
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User answered the pending date question.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="same period as the last test",
        ),
        semantic_turn_act="answer_pending_need",
    )

    filled = _draft_with_pending_strategy_gaps_filled(
        response.candidate_strategy_draft,
        response=response,
        request=request,
    )

    assert filled.recurring_contribution is None
    assert "recurring_contribution" not in (filled.field_provenance or {})
