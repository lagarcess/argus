# ruff: noqa: F403, F405
"""Regression coverage for issue #141: result-card Refine idea replies must
route through the typed artifact edit planner.

The `Refine idea` result action stores `requested_field="refinement"`
(`api/chat/result_actions.py`) and the next natural-language edit must reach
`plan_artifact_assumption_edit` exactly like confirmation-card edits do —
chips and natural language are two entry points to one edit contract.
"""

from tests.agent_runtime._llm_interpreter_common import *


def _refine_pending_strategy() -> StrategySummary:
    return StrategySummary(
        strategy_type="dca_accumulation",
        strategy_thesis="Recurring monthly buys of AAPL and MSFT.",
        asset_universe=["AAPL", "MSFT"],
        asset_class="equity",
        cadence="monthly",
        date_range={"start": "2020-02-01", "end": "2026-07-02"},
        extra_parameters={"recurring_contribution": 500},
    )


def _refine_state_request(message: str) -> InterpretationRequest:
    """Interpretation request shaped like the turn after a Refine idea click.

    Mirrors `pending_strategy_metadata_fallback_context`: the pending strategy
    is the draft reconstructed from the completed result, the source result
    reference is attached, and `requested_field` is `refinement`.
    """

    pending = _refine_pending_strategy()
    source_reference = ArtifactReference(
        artifact_kind="backtest_result",
        artifact_id="run-141",
        artifact_status="completed",
        metadata={
            "strategy_type": "dca_accumulation",
            "symbols": ["AAPL", "MSFT"],
            "date_range": {"start": "2020-02-01", "end": "2026-07-02"},
        },
    )
    return InterpretationRequest(
        current_user_message=message,
        recent_thread_history=[],
        latest_task_snapshot=TaskSnapshot(
            latest_task_type="backtest_execution",
            completed=False,
            pending_strategy_summary=pending,
            latest_backtest_result_reference=source_reference,
            artifact_references=[source_reference],
        ),
        selected_thread_metadata={
            "latest_task_type": "backtest_execution",
            "last_stage_outcome": "await_user_reply",
            "requested_field": "refinement",
            "source_result_run_id": "run-141",
        },
        user=UserState(user_id="u1"),
    )


def _nvda_resolve_stub(symbol: str, **kwargs):
    del kwargs
    normalized = symbol.strip().upper()
    aliases = {
        "AAPL": "AAPL",
        "MSFT": "MSFT",
        "NVDA": "NVDA",
        "NVIDIA": "NVDA",
    }
    canonical = aliases.get(normalized)
    if canonical is None:
        raise ValueError("invalid_symbol")
    names = {
        "AAPL": "Apple Inc.",
        "MSFT": "Microsoft Corporation",
        "NVDA": "NVIDIA Corporation",
    }
    return ResolvedAssetStub(canonical, "equity", name=names[canonical])


def _replace_asset_plan_stub(schema_model):
    from argus.agent_runtime import artifact_edit_planner

    if schema_model.__name__ != "ArtifactAssumptionEditPlan":
        raise ValueError(f"unexpected schema request: {schema_model.__name__}")
    return schema_model(
        outcome="ready_to_confirm",
        user_goal_summary="User swapped the refine draft to NVDA.",
        operations=[
            artifact_edit_planner.EditOperation(
                op="replace",
                target="asset",
                symbols=["NVDA"],
            ),
        ],
        confidence=0.92,
    )


@pytest.mark.asyncio
async def test_refine_reply_routes_to_edit_planner_and_applies_asset_edit(
    monkeypatch,
) -> None:
    """A post-refine NL edit must reach the planner, not rebuild the old card.

    Live failure: the general interpreter classified the reply as
    `refine_current_idea` and rematerialized the AAPL/MSFT card with the NVDA
    edit silently dropped.
    """

    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )
    monkeypatch.setattr(interpreter_module, "resolve_asset", _nvda_resolve_stub)

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="strategy_drafting",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="User wants the refine draft on NVDA instead.",
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing="change the asset to NVDA",
                    strategy_type="dca_accumulation",
                    strategy_thesis="Recurring monthly buys of NVDA.",
                    asset_universe=["NVDA"],
                    asset_universe_operation="replace",
                    field_provenance={"asset_universe": "explicit_user"},
                ),
                semantic_turn_act="refine_current_idea",
                artifact_target="pending_refinement",
            )
        return _replace_asset_plan_stub(schema_model)

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(
        _refine_state_request("change the asset to NVDA")
    )

    assert result is not None
    assert "ArtifactAssumptionEditPlan" in calls
    assert "artifact_assumption_edit_planned" in result.reason_codes
    # The planner response is a patch draft: the asset swap is present and the
    # untouched fields are left to the stage-level merge with the pending
    # strategy (covered by the stage test below).
    assert result.candidate_strategy_draft.asset_universe == ["NVDA"]
    assert result.candidate_strategy_draft.strategy_type == "dca_accumulation"
    assert result.semantic_turn_act == "answer_pending_need"


@pytest.mark.asyncio
async def test_refine_reply_reaches_edit_planner_when_general_model_fails(
    monkeypatch,
) -> None:
    """When the general interpreter fails, the refine reply must still get the
    focused planner attempt instead of falling to generic recovery copy.

    Live failure: both general-interpretation model candidates failed and the
    turn ended in "could not safely apply that change" recovery prose.
    """

    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )
    monkeypatch.setattr(interpreter_module, "resolve_asset", _nvda_resolve_stub)

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            raise ValueError("general interpreter returned unusable JSON")
        return _replace_asset_plan_stub(schema_model)

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(
        _refine_state_request("change the asset to NVDA")
    )

    assert calls[0] == "LLMInterpretationResponse"
    assert "ArtifactAssumptionEditPlan" in calls
    assert result is not None
    assert "artifact_assumption_edit_planned" in result.reason_codes
    assert result.candidate_strategy_draft.asset_universe == ["NVDA"]


class _RecordingInterpreter:
    def __init__(self, response) -> None:
        self.response = response
        self.requests: list = []

    def __call__(self, request):
        self.requests.append(request)
        return self.response


def test_refine_edit_plans_offline_when_interpreter_unavailable(
    monkeypatch,
) -> None:
    """Live failure mode: every interpretation model failed and the refine
    reply died in generic "could not safely apply" recovery copy. The offline
    planner must serve refine pending drafts the way it serves confirmation
    cards.
    """

    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime.stages import interpret as interpret_module

    async def plan_stub(**kwargs):
        assert kwargs["current_user_message"] == "change the asset to NVDA"
        assert kwargs["prior_strategy"]["asset_universe"] == ["AAPL", "MSFT"]
        return artifact_edit_planner.ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            user_goal_summary="User swapped the refine draft to NVDA.",
            operations=[
                artifact_edit_planner.EditOperation(
                    op="replace",
                    target="asset",
                    symbols=["NVDA"],
                ),
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        interpret_module,
        "plan_artifact_assumption_edit",
        plan_stub,
    )
    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="change the asset to NVDA",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=TaskSnapshot(
            latest_task_type="backtest_execution",
            completed=False,
            pending_strategy_summary=_refine_pending_strategy(),
            latest_backtest_result_reference=ArtifactReference(
                artifact_kind="backtest_result",
                artifact_id="run-141",
                artifact_status="completed",
            ),
        ),
        selected_thread_metadata={
            "latest_task_type": "backtest_execution",
            "last_stage_outcome": "await_user_reply",
            "requested_field": "refinement",
            "source_result_run_id": "run-141",
        },
        structured_interpreter=_RecordingInterpreter(None),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["NVDA"]
    assert strategy.date_range == {"start": "2020-02-01", "end": "2026-07-02"}
    assert strategy.extra_parameters.get("recurring_contribution") == 500
    assert "artifact_assumption_edit_planned" in result.decision.reason_codes


def test_refine_planned_edit_merges_full_confirmation_from_pending_draft() -> None:
    """Stage-level AC: the confirmation produced by a refine edit must carry
    the resolved prior date range, assets, and contribution — not a sparse or
    rebuilt draft.
    """

    from argus.agent_runtime.stages.interpret_types import StructuredInterpretation

    pending = _refine_pending_strategy()
    snapshot = TaskSnapshot(
        latest_task_type="backtest_execution",
        completed=False,
        pending_strategy_summary=pending,
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-141",
            artifact_status="completed",
        ),
    )
    planned = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User swapped the refine draft to NVDA.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing="change the asset to NVDA",
            strategy_type="dca_accumulation",
            asset_universe=["NVDA"],
            extra_parameters={
                "asset_universe_operation": "replace",
                "field_provenance": {"asset_universe": "explicit_user"},
            },
        ),
        semantic_turn_act="answer_pending_need",
        reason_codes=["artifact_assumption_edit_planned"],
    )
    interpreter = _RecordingInterpreter(planned)

    result = interpret_stage(
        state=RunState.new(
            current_user_message="change the asset to NVDA",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "latest_task_type": "backtest_execution",
            "last_stage_outcome": "await_user_reply",
            "requested_field": "refinement",
            "source_result_run_id": "run-141",
        },
        structured_interpreter=interpreter,
    )

    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["NVDA"]
    assert strategy.date_range == {"start": "2020-02-01", "end": "2026-07-02"}
    assert strategy.cadence == "monthly"
    assert strategy.extra_parameters.get("recurring_contribution") == 500
    assert result.outcome == "ready_for_confirmation"


@pytest.mark.asyncio
async def test_refine_date_window_reply_routes_to_edit_planner(
    monkeypatch,
) -> None:
    """A refine reply that only changes the window ("change the date range to
    2021") must reach the planner: EditOperation supports date_window, so
    date-only evidence is planner-expressible even though it is not an
    assumption-field edit (PR #148 review)."""

    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )
    monkeypatch.setattr(interpreter_module, "resolve_asset", _nvda_resolve_stub)

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="strategy_drafting",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="User moved the refine draft to calendar 2021.",
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing="change the date range to 2021",
                    strategy_type="dca_accumulation",
                    date_range_intent=LLMDateRangeIntent(
                        kind="calendar_year",
                        year=2021,
                        confidence=0.9,
                        evidence="2021",
                    ),
                    evidence_spans={"date_range": "2021"},
                ),
                semantic_turn_act="refine_current_idea",
                artifact_target="pending_refinement",
            )
        if schema_model.__name__ != "ArtifactAssumptionEditPlan":
            raise ValueError(f"unexpected schema request: {schema_model.__name__}")
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User moved the window to calendar 2021.",
            operations=[
                artifact_edit_planner.EditOperation(
                    op="set",
                    target="date_window",
                    date_window=LLMDateRangeIntent(
                        kind="calendar_year",
                        year=2021,
                        confidence=0.9,
                        evidence="2021",
                    ),
                ),
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(
        _refine_state_request("change the date range to 2021")
    )

    assert result is not None
    # Direct readiness route: no fallback or repair detours.
    assert calls == ["LLMInterpretationResponse", "ArtifactAssumptionEditPlan"]
    assert "artifact_assumption_edit_planned" in result.reason_codes
    assert result.candidate_strategy_draft.date_range == {
        "start": "2021-01-01",
        "end": "2021-12-31",
    }


@pytest.mark.asyncio
async def test_refine_cadence_reply_routes_to_edit_planner(
    monkeypatch,
) -> None:
    """"Make it weekly" after Refine idea is a planner-expressible cadence
    edit and must not fall through to full interpretation (PR #148 review)."""

    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )
    monkeypatch.setattr(interpreter_module, "resolve_asset", _nvda_resolve_stub)

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="strategy_drafting",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="User wants weekly buys in the refine draft.",
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing="make it weekly",
                    strategy_type="dca_accumulation",
                    cadence="weekly",
                    field_provenance={"cadence": "explicit_user"},
                ),
                semantic_turn_act="refine_current_idea",
                artifact_target="pending_refinement",
            )
        if schema_model.__name__ != "ArtifactAssumptionEditPlan":
            raise ValueError(f"unexpected schema request: {schema_model.__name__}")
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User switched the cadence to weekly.",
            operations=[
                artifact_edit_planner.EditOperation(
                    op="set",
                    target="cadence",
                    value="weekly",
                ),
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(_refine_state_request("make it weekly"))

    assert result is not None
    # Direct readiness route: no fallback or repair detours.
    assert calls == ["LLMInterpretationResponse", "ArtifactAssumptionEditPlan"]
    assert "artifact_assumption_edit_planned" in result.reason_codes
    assert result.candidate_strategy_draft.cadence == "weekly"
