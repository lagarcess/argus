# ruff: noqa: F403, F405
"""Post-result conversational edits must reach the typed edit contract.

A free-form message after a completed run ("could we try NVDA at $500 a month
from the same time period") is the no-chip twin of the Refine idea action:
when the interpreter classifies it as refining the current idea, the reply
must plan EditOperations against the strategy reconstructed from the latest
completed result — chips and natural language are two entry points to one
contract. New ideas and result questions keep full interpretation.
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


def _post_result_request(message: str) -> InterpretationRequest:
    """Post-result surface: a completed run, no pending or confirmation state."""

    return InterpretationRequest(
        current_user_message=message,
        recent_thread_history=[],
        latest_task_snapshot=TaskSnapshot(
            latest_task_type="results_explanation",
            completed=True,
            latest_backtest_result_reference=_completed_result_reference(),
        ),
        selected_thread_metadata={
            "latest_task_type": "results_explanation",
            "last_stage_outcome": "ready_to_respond",
        },
        user=UserState(user_id="u1"),
    )


def _post_result_refinement_request(message: str) -> InterpretationRequest:
    request = _post_result_request(message)
    return request.model_copy(
        update={
            "selected_thread_metadata": {
                "latest_task_type": "results_explanation",
                "last_stage_outcome": "ready_to_respond",
                "requested_field": "refinement",
            }
        }
    )


def _resolve_stub(symbol: str, **kwargs):
    del kwargs
    aliases = {
        "AAPL": ("AAPL", "Apple Inc."),
        "MSFT": ("MSFT", "Microsoft Corporation"),
        "NVDA": ("NVDA", "NVIDIA Corporation"),
        "NVIDIA": ("NVDA", "NVIDIA Corporation"),
        "TSLA": ("TSLA", "Tesla Inc."),
    }
    resolved = aliases.get(symbol.strip().upper())
    if resolved is None:
        raise ValueError("invalid_symbol")
    return ResolvedAssetStub(resolved[0], "equity", name=resolved[1])


@pytest.mark.asyncio
async def test_post_result_refine_reply_routes_to_edit_planner(
    monkeypatch,
) -> None:
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
    monkeypatch.setattr(interpreter_module, "resolve_asset", _resolve_stub)

    calls: list[str] = []
    planner_prior: dict = {}

    async def invoke_stub(*, schema_model, messages=None, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="strategy_drafting",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary=(
                    "User wants the completed recurring-buy idea on NVDA over "
                    "the same window."
                ),
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing=(
                        "Could we try to buy NVDA at 500 dollars a month from "
                        "the same time period"
                    ),
                    strategy_type="dca_accumulation",
                    asset_universe=["NVDA"],
                    asset_universe_operation="replace",
                    field_provenance={"asset_universe": "explicit_user"},
                    date_range_intent=LLMDateRangeIntent(
                        kind="same_as_latest_result",
                        confidence=0.9,
                        evidence="from the same time period",
                    ),
                ),
                semantic_turn_act="refine_current_idea",
            )
        if schema_model.__name__ != "ArtifactAssumptionEditPlan":
            raise ValueError(f"unexpected schema request: {schema_model.__name__}")
        planner_prior["messages"] = messages
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User swapped the completed idea to NVDA.",
            operations=[
                artifact_edit_planner.EditOperation(
                    op="replace",
                    target="asset",
                    symbols=["NVDA"],
                ),
                artifact_edit_planner.EditOperation(
                    op="set",
                    target="date_window",
                    date_window=LLMDateRangeIntent(
                        kind="same_as_latest_result",
                        confidence=0.9,
                        evidence="from the same time period",
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
        _post_result_request(
            "Could we try to buy NVDA at 500 dollars a month from the same "
            "time period"
        )
    )

    assert result is not None
    # Direct readiness route: no fallback or repair detours.
    assert calls == ["LLMInterpretationResponse", "ArtifactAssumptionEditPlan"]
    assert "artifact_assumption_edit_planned" in result.reason_codes
    draft = result.candidate_strategy_draft
    assert draft.asset_universe == ["NVDA"]
    assert draft.date_range == {"start": "2020-02-01", "end": "2026-07-02"}


@pytest.mark.asyncio
async def test_result_refine_prompt_after_fact_answer_routes_capital_edit_to_planner(
    monkeypatch,
) -> None:
    """The result-card Refine idea prompt can survive an intervening result
    question. A later capital edit still belongs to the typed edit planner, not
    the broad DCA clarification path.
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
    monkeypatch.setattr(interpreter_module, "resolve_asset", _resolve_stub)

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="strategy_drafting",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="User wants to change starting capital.",
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing="change starting capital to $2,000",
                    strategy_type="dca_accumulation",
                    date_range={"start": "2020-02-01", "end": "2026-07-02"},
                ),
                semantic_turn_act="refine_current_idea",
            )
        if schema_model.__name__ != "ArtifactAssumptionEditPlan":
            raise ValueError(f"unexpected schema request: {schema_model.__name__}")
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User set starting capital to $2,000.",
            operations=[
                artifact_edit_planner.EditOperation(
                    op="set",
                    target="capital",
                    number=2000,
                )
            ],
            confidence=0.95,
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
        _post_result_refinement_request("change starting capital to $2,000")
    )

    assert result is not None
    assert calls == ["LLMInterpretationResponse", "ArtifactAssumptionEditPlan"]
    assert "artifact_assumption_edit_planned" in result.reason_codes
    assert result.artifact_target == "latest_result"
    draft = result.candidate_strategy_draft
    assert result.semantic_turn_act == "answer_pending_need"
    assert draft.extra_parameters["initial_capital"] == 2000
    assert draft.extra_parameters["field_provenance"]["initial_capital"] == (
        "starting_capital"
    )


@pytest.mark.asyncio
async def test_post_result_capital_edit_with_unprovenanced_amount_uses_planner(
    monkeypatch,
) -> None:
    """Live models can return a typed initial_capital value without
    field_provenance. On a post-result refine surface, that is still typed edit
    evidence and must not become a standalone incomplete DCA draft.
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
    monkeypatch.setattr(interpreter_module, "resolve_asset", _resolve_stub)

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="strategy_drafting",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="User wants to change starting capital.",
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing="change starting capital to $2,000",
                    strategy_type="dca_accumulation",
                    initial_capital=2000,
                ),
                semantic_turn_act="refine_current_idea",
            )
        if schema_model.__name__ != "ArtifactAssumptionEditPlan":
            raise ValueError(f"unexpected schema request: {schema_model.__name__}")
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User set starting capital to $2,000.",
            operations=[
                artifact_edit_planner.EditOperation(
                    op="set",
                    target="capital",
                    number=2000,
                )
            ],
            confidence=0.95,
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
        _post_result_refinement_request("change starting capital to $2,000")
    )

    assert result is not None
    assert calls == ["LLMInterpretationResponse", "ArtifactAssumptionEditPlan"]
    assert result.artifact_target == "latest_result"
    assert result.candidate_strategy_draft.extra_parameters["initial_capital"] == 2000


@pytest.mark.asyncio
async def test_post_result_capital_edit_with_unprovenanced_capital_amount_uses_planner(
    monkeypatch,
) -> None:
    """Fallback models can put the edited money value in capital_amount.

    On a post-result refine surface, the edit planner owns the target
    disambiguation instead of the broad DCA missing-contribution path.
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
    monkeypatch.setattr(interpreter_module, "resolve_asset", _resolve_stub)

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="strategy_drafting",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="User wants to change starting capital.",
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing="change starting capital to $2,000",
                    strategy_type="dca_accumulation",
                    capital_amount=2000,
                ),
                semantic_turn_act="refine_current_idea",
            )
        if schema_model.__name__ != "ArtifactAssumptionEditPlan":
            raise ValueError(f"unexpected schema request: {schema_model.__name__}")
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User set starting capital to $2,000.",
            operations=[
                artifact_edit_planner.EditOperation(
                    op="set",
                    target="capital",
                    number=2000,
                )
            ],
            confidence=0.95,
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
        _post_result_refinement_request("change starting capital to $2,000")
    )

    assert result is not None
    assert calls == ["LLMInterpretationResponse", "ArtifactAssumptionEditPlan"]
    assert result.artifact_target == "latest_result"
    assert result.candidate_strategy_draft.extra_parameters["initial_capital"] == 2000


@pytest.mark.asyncio
async def test_post_result_new_idea_keeps_full_interpretation(
    monkeypatch,
) -> None:
    """A genuinely new idea after a result must not be hijacked into an edit
    of the completed strategy."""

    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )
    monkeypatch.setattr(interpreter_module, "resolve_asset", _resolve_stub)

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="strategy_drafting",
                task_relation="new_task",
                requires_clarification=False,
                user_goal_summary="User wants a fresh Tesla buy-and-hold test.",
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing="test buying and holding TSLA for 2023",
                    strategy_type="buy_and_hold",
                    strategy_thesis="Buy and hold Tesla through 2023.",
                    asset_universe=["TSLA"],
                    asset_class="equity",
                    date_range_intent=LLMDateRangeIntent(
                        kind="calendar_year",
                        year=2023,
                        confidence=0.9,
                        evidence="2023",
                    ),
                    evidence_spans={
                        "asset_universe": "TSLA",
                        "date_range": "2023",
                    },
                ),
                semantic_turn_act="new_idea",
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
        _post_result_request("test buying and holding TSLA for 2023")
    )

    assert result is not None
    assert "ArtifactAssumptionEditPlan" not in calls
    assert result.semantic_turn_act == "new_idea"
    assert result.candidate_strategy_draft.asset_universe == ["TSLA"]


@pytest.mark.asyncio
async def test_post_result_reshape_reply_keeps_full_interpretation(
    monkeypatch,
) -> None:
    """A post-result reply that reshapes the strategy type must fork through
    full interpretation, exactly like reshape replies during refine."""

    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )
    monkeypatch.setattr(interpreter_module, "resolve_asset", _resolve_stub)

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="strategy_drafting",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary=(
                    "User wants the same assets as a single buy-and-hold "
                    "instead of recurring buys."
                ),
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing="just buy and hold them instead",
                    strategy_type="buy_and_hold",
                    strategy_thesis="Buy and hold AAPL and MSFT.",
                    asset_universe=["AAPL", "MSFT"],
                    asset_class="equity",
                ),
                semantic_turn_act="refine_current_idea",
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
        _post_result_request("just buy and hold them instead")
    )

    assert result is not None
    assert "ArtifactAssumptionEditPlan" not in calls


def test_prior_asset_preservation_defers_to_explicit_ticker_mention(
    monkeypatch,
) -> None:
    """Inherited assets must never override a ticker the user literally
    typed this turn (semantic integrity: explicit constraints are immutable).

    The preservation escape only recognized cashtags and draft-carried
    symbols; a bare foreign ticker in the message with an asset-less draft
    let the prior set win.
    """

    from types import SimpleNamespace

    from argus.agent_runtime.interpreter import strategy_builder
    from argus.agent_runtime.llm_interpreter_types import (
        LLMInterpretationResponse,
        LLMStrategyDraft,
    )

    def resolve_candidate_stub(query, **kwargs):
        return SimpleNamespace(status="resolved", asset=_resolve_stub(query))

    monkeypatch.setattr(
        strategy_builder,
        "resolve_asset_candidate",
        resolve_candidate_stub,
    )

    strategy = StrategySummary(
        strategy_type="dca_accumulation",
        cadence="monthly",
        extra_parameters={"recurring_contribution": 500},
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User answered the date request.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Could we try to buy NVDA at 500 dollars a month from the "
                "same time period"
            ),
        ),
        semantic_turn_act="answer_pending_need",
    )
    request = InterpretationRequest(
        current_user_message=(
            "Could we try to buy NVDA at 500 dollars a month from the same "
            "time period"
        ),
        recent_thread_history=[],
        latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=StrategySummary(
                strategy_type="dca_accumulation",
                asset_universe=["AAPL", "MSFT"],
                asset_class="equity",
            ),
        ),
        selected_thread_metadata={
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
        },
        user=UserState(user_id="u1"),
    )

    strategy_builder._merge_prior_strategy(
        strategy=strategy,
        request=request,
        response=response,
    )

    assert strategy.asset_universe != ["AAPL", "MSFT"]
    assert (
        "pending_non_asset_answer_preserved_prior_asset"
        not in response.reason_codes
    )


class _RecordingInterpreter:
    def __init__(self, response) -> None:
        self.response = response

    def __call__(self, request):
        return self.response


def test_post_result_planned_edit_materializes_full_confirmation(monkeypatch) -> None:
    """The confirmation from a post-result planned edit must carry the
    completed run's contribution, cadence, and window — there is no pending
    strategy to merge from on this surface."""

    from argus.agent_runtime.stages import interpret as interpret_module
    from argus.agent_runtime.stages.interpret_types import StructuredInterpretation

    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
    monkeypatch.setattr(interpret_module, "resolve_asset", _resolve_stub)
    planned = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User swapped the completed idea to NVDA.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing=(
                "Could we try to buy NVDA at 500 dollars a month from the "
                "same time period"
            ),
            strategy_type="dca_accumulation",
            asset_universe=["NVDA"],
            date_range={"start": "2020-02-01", "end": "2026-07-02"},
            extra_parameters={
                "asset_universe_operation": "replace",
                "field_provenance": {"asset_universe": "explicit_user"},
            },
        ),
        semantic_turn_act="answer_pending_need",
        reason_codes=["artifact_assumption_edit_planned"],
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message=(
                "Could we try to buy NVDA at 500 dollars a month from the "
                "same time period"
            ),
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=TaskSnapshot(
            latest_task_type="results_explanation",
            completed=True,
            latest_backtest_result_reference=_completed_result_reference(),
        ),
        selected_thread_metadata={
            "latest_task_type": "results_explanation",
            "last_stage_outcome": "ready_to_respond",
        },
        structured_interpreter=_RecordingInterpreter(planned),
    )

    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["NVDA"]
    assert strategy.date_range == {"start": "2020-02-01", "end": "2026-07-02"}
    assert strategy.cadence == "monthly"
    # The run's recurring contribution rides on capital_amount in anchor
    # drafts (draft_from_result_metadata); the card renders it as
    # CONTRIBUTION.
    assert strategy.capital_amount == 500
    assert result.outcome == "ready_for_confirmation"


def test_post_result_starting_capital_edit_defers_unexecutable_principal(
    monkeypatch,
) -> None:
    """Starting-capital edits keep the DCA anchor (no re-ask for the known
    contribution) but stay blocked: the engine cannot execute a separate
    starting principal (docs/API_CONTRACT.md).
    """

    from argus.agent_runtime.stages import interpret as interpret_module
    from argus.agent_runtime.stages.interpret_types import StructuredInterpretation

    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
    monkeypatch.setattr(interpret_module, "resolve_asset", _resolve_stub)
    planned = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User set starting capital to $2,000.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing="change starting capital to $2,000",
            strategy_type="dca_accumulation",
            extra_parameters={
                "initial_capital": 2000,
                "field_provenance": {"initial_capital": "starting_capital"},
            },
        ),
        semantic_turn_act="answer_pending_need",
        reason_codes=["artifact_assumption_edit_planned"],
        artifact_target="latest_result",
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="change starting capital to $2,000",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=TaskSnapshot(
            latest_task_type="results_explanation",
            completed=True,
            latest_backtest_result_reference=_completed_result_reference(),
        ),
        selected_thread_metadata={
            "latest_task_type": "results_explanation",
            "last_stage_outcome": "ready_to_respond",
            "requested_field": "refinement",
        },
        structured_interpreter=_RecordingInterpreter(planned),
    )

    strategy = result.decision.candidate_strategy_draft
    assert result.outcome == "needs_clarification"
    assert strategy.strategy_type == "dca_accumulation"
    assert strategy.asset_universe == ["AAPL", "MSFT"]
    assert strategy.cadence == "monthly"
    assert strategy.capital_amount == 500
    assert "capital_amount" not in result.decision.missing_required_fields
    assert strategy.extra_parameters["initial_capital"] == 2000
    assert "unsupported_dca_starting_principal" in {
        constraint.category
        for constraint in result.decision.unsupported_constraints
    }


def test_result_followup_asset_swap_with_inferred_target_confirms(
    monkeypatch,
) -> None:
    """An inferred-target result edit ("try NVDA instead") reaches the patch
    path even when the echoed draft carries executable fields beyond dates.
    """

    from argus.agent_runtime.stages import interpret as interpret_module
    from argus.agent_runtime.stages.interpret_types import StructuredInterpretation

    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
    monkeypatch.setattr(interpret_module, "resolve_asset", _resolve_stub)
    planned = StructuredInterpretation(
        intent="results_explanation",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User wants the same run with NVDA instead.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing="try NVDA instead",
            strategy_type="dca_accumulation",
            asset_universe=["NVDA"],
            asset_class="equity",
            cadence="monthly",
            capital_amount=500,
            date_range={"start": "2020-02-01", "end": "2026-07-02"},
            extra_parameters={"asset_universe_operation": "replace"},
        ),
        semantic_turn_act="result_followup",
        result_followup_focus="general",
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="try NVDA instead",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=TaskSnapshot(
            latest_task_type="results_explanation",
            completed=True,
            latest_backtest_result_reference=_completed_result_reference(),
        ),
        selected_thread_metadata={
            "latest_task_type": "results_explanation",
            "last_stage_outcome": "ready_to_respond",
        },
        structured_interpreter=_RecordingInterpreter(planned),
    )

    strategy = result.decision.candidate_strategy_draft
    assert result.outcome == "ready_for_confirmation"
    assert strategy.asset_universe == ["NVDA"]
    assert strategy.cadence == "monthly"
    assert strategy.capital_amount == 500
    assert "result_followup_target_inferred" in result.decision.reason_codes
