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

    Without planner routing, the general interpreter classifies the reply
    as `refine_current_idea` and rematerializes the prior card, silently
    dropping the asset edit (#141).
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

    Otherwise a turn where every candidate fails lands in "could not
    safely apply that change" recovery prose instead of the typed edit (#141).
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
    """With every interpretation model down, the offline planner must serve
    refine pending drafts the way it serves confirmation cards; otherwise the
    reply lands in generic "could not safely apply" recovery copy (#141).
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


def test_refine_planned_edit_merges_full_confirmation_from_pending_draft(
    monkeypatch,
) -> None:
    """Stage-level AC: the confirmation produced by a refine edit must carry
    the resolved prior date range, assets, and contribution — not a sparse or
    rebuilt draft.
    """

    from argus.agent_runtime.stages import interpret as interpret_module
    from argus.agent_runtime.stages.interpret_types import StructuredInterpretation

    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
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
    assumption-field edit."""

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
    edit and must not fall through to full interpretation."""

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


@pytest.mark.asyncio
async def test_refine_same_period_planner_edit_binds_latest_result_window(
    monkeypatch,
) -> None:
    """A planner date op referencing the latest result must bind the canonical
    run window. resolve_date_range_intent cannot resolve the reference on its
    own, and the date edit used to vanish silently while other ops applied.
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

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        if schema_model.__name__ == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="backtest_execution",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary=(
                    "User set capital and reused the latest test window."
                ),
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing=(
                        "set capital to $5000 and use the same period as the "
                        "last test"
                    ),
                    strategy_type="dca_accumulation",
                    capital_amount=5000.0,
                    date_range_intent=LLMDateRangeIntent(
                        kind="same_as_latest_result",
                        confidence=0.9,
                        evidence="same period as the last test",
                    ),
                    field_provenance={"capital_amount": "starting_capital"},
                ),
                semantic_turn_act="answer_pending_need",
                artifact_target="pending_refinement",
            )
        if schema_model.__name__ != "ArtifactAssumptionEditPlan":
            raise ValueError(f"unexpected schema request: {schema_model.__name__}")
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User set capital and reused the latest window.",
            operations=[
                artifact_edit_planner.EditOperation(
                    op="set",
                    target="capital",
                    number=5000.0,
                ),
                artifact_edit_planner.EditOperation(
                    op="set",
                    target="date_window",
                    date_window=LLMDateRangeIntent(
                        kind="same_as_latest_result",
                        confidence=0.9,
                        evidence="same period as the last test",
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

    request = _refine_state_request(
        "set capital to $5000 and use the same period as the last test"
    )
    # A window distinct from the pending draft's proves the dates came from
    # the canonical result binding, not the pending-strategy merge.
    request.latest_task_snapshot.latest_backtest_result_reference.metadata[
        "config_snapshot"
    ] = {"date_range": {"start": "2023-01-01", "end": "2023-12-31"}}

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(request)

    assert result is not None
    assert "artifact_assumption_edit_planned" in result.reason_codes
    draft = result.candidate_strategy_draft
    assert draft.date_range == {"start": "2023-01-01", "end": "2023-12-31"}
    intent_payload = draft.extra_parameters.get("date_range_intent")
    assert isinstance(intent_payload, dict)
    assert intent_payload.get("kind") == "explicit_range"


def test_refine_same_period_offline_plan_binds_latest_result_window(
    monkeypatch,
) -> None:
    """The interpreter-unavailable refine planner must bind a same-period date
    op from the canonical result metadata instead of silently dropping it."""

    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime.stages import interpret as interpret_module

    async def plan_stub(**kwargs):
        del kwargs
        # A date-only plan is the sharpest case: if the reference stays
        # unresolved the applier produces nothing, the plan collapses to None,
        # and the turn falls to generic recovery copy.
        return artifact_edit_planner.ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            user_goal_summary="User reused the latest test window.",
            operations=[
                artifact_edit_planner.EditOperation(
                    op="set",
                    target="date_window",
                    date_window=LLMDateRangeIntent(
                        kind="same_as_latest_result",
                        confidence=0.9,
                        evidence="mismo periodo",
                    ),
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
            current_user_message="usa el mismo periodo que la última prueba",
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
                metadata={
                    "config_snapshot": {
                        "date_range": {"start": "2023-01-01", "end": "2023-12-31"},
                    },
                },
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
    assert strategy.date_range == {"start": "2023-01-01", "end": "2023-12-31"}
    intent_payload = strategy.extra_parameters.get("date_range_intent")
    assert isinstance(intent_payload, dict)
    assert intent_payload.get("kind") == "explicit_range"


@pytest.mark.asyncio
async def test_refine_reshape_plan_steps_aside_on_non_recurring_strategy(
    monkeypatch,
) -> None:
    """"Make it recurring buys instead" on a non-recurring refine draft is a
    reshape the edit-operation set cannot express; the failure-path planner
    must return None instead of bolting cadence onto the old strategy type."""

    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def plan_stub(**kwargs):
        del kwargs
        return artifact_edit_planner.ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            user_goal_summary="User asked for recurring monthly buys of 500.",
            operations=[
                artifact_edit_planner.EditOperation(
                    op="set",
                    target="cadence",
                    value="monthly",
                ),
                artifact_edit_planner.EditOperation(
                    op="set",
                    target="recurring_contribution",
                    number=500.0,
                ),
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        interpreter_module,
        "plan_artifact_assumption_edit",
        plan_stub,
    )

    request = _refine_state_request("make it recurring monthly buys of 500 instead")
    request.latest_task_snapshot.pending_strategy_summary.strategy_type = "momentum"
    planned = await interpreter_module._plan_pending_artifact_assumption_edit(
        request=request,
        preferred_model="test-model",
    )
    assert planned is None

    # The same plan on a recurring pending strategy is a plain cadence edit.
    request.latest_task_snapshot.pending_strategy_summary.strategy_type = (
        "dca_accumulation"
    )
    planned = await interpreter_module._plan_pending_artifact_assumption_edit(
        request=request,
        preferred_model="test-model",
    )
    assert planned is not None


@pytest.mark.asyncio
async def test_refine_result_fact_question_keeps_result_followup_routing(
    monkeypatch,
) -> None:
    """"How did it do in 2022?" right after Refine idea is a result question;
    the planner must not override the interpreter's result_followup
    classification with an edit confirmation card."""

    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def plan_stub(**kwargs):
        del kwargs
        raise AssertionError("planner must not run for a result fact question")

    monkeypatch.setattr(
        interpreter_module,
        "plan_artifact_assumption_edit",
        plan_stub,
    )

    response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asked how the strategy performed in 2022.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="how did it do in 2022?",
            date_range_intent=LLMDateRangeIntent(
                kind="calendar_year",
                year=2022,
                confidence=0.9,
                evidence="2022",
            ),
        ),
        assistant_response="Here is how the strategy performed in 2022.",
        semantic_turn_act="result_followup",
    )
    planned = await interpreter_module._ready_active_artifact_edit_planned_response(
        response=response,
        preferred_model="test-model",
        request=_refine_state_request("how did it do in 2022?"),
    )
    assert planned is None


def test_refine_rule_tweak_reply_is_not_underfilled_assumption_edit() -> None:
    """A rule tweak ("use a 20-day moving average") is a full-interpretation
    refine reply; the assumption-edit underfill check must not reject it into
    the repair loop."""

    from argus.agent_runtime import llm_interpreter as interpreter_module

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User switched the rule to a 20-day moving average.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="use a 20-day moving average instead of 50",
            strategy_type="indicator_threshold",
            indicator="moving_average",
            indicator_period=20,
        ),
        semantic_turn_act="refine_current_idea",
    )
    assert not interpreter_module._response_underfills_active_artifact_assumption_edit(
        response=response,
        request=_refine_state_request("use a 20-day moving average instead of 50"),
    )
