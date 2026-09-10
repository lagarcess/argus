"""Selected calls use the existing grounded-input owner, with a bounded scope."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import pytest
from argus.agent_runtime import llm_interpreter
from argus.agent_runtime.llm_interpreter_types import LLMStrategyDraft
from argus.agent_runtime.stages.tool_execution import execute_tool_calls_async
from argus.agent_runtime.state.models import RunState, UserState
from argus.domain.tool_contracts import ToolCall

from tests.evals.measurement_eval_harness import load_eval_cases


@pytest.fixture(autouse=True)
def local_input_preparation(monkeypatch):
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
    monkeypatch.setenv("ARGUS_EXECUTION_REALISM_ENABLED", "true")

    async def no_provider(**kwargs):
        raise AssertionError("A preparation test must script every model response")

    monkeypatch.setattr(llm_interpreter, "invoke_openrouter_json_schema", no_provider)


@lru_cache
def retained_rows():
    path = (
        Path(__file__).parents[2]
        / "docs/reports/evidence/registry/live-measurement-second.json"
    )
    return {row["id"]: row for row in json.loads(path.read_text())["results"]}


def retained_call(case_id):
    row = retained_rows()[case_id]
    return ToolCall.model_validate(deepcopy(row["typed_outcome"]["tool_calls"][0]))


async def execute(calls, *, message, **kwargs):
    return await execute_tool_calls_async(
        state=RunState(
            current_user_message=message,
            intent="calculate",
            task_relation="new_task",
            semantic_turn_act="new_idea",
            tool_calls=calls,
        ),
        tool=object(),
        user=UserState(user_id="input-readiness"),
        **kwargs,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case_id",
    [
        "capability_honesty_golden_cross_control_aapl",
        "dca_capital_semantics_stated_seed_reaches_ready_to_run_issue_455",
        "messy_english_complete_sma_crossover_benchmark_issue_270",
    ],
)
async def test_retained_calls_reuse_existing_readiness_without_reselecting(
    monkeypatch, case_id
):
    call = retained_call(case_id)
    original = call.model_dump(mode="json")
    case = next(case for case in load_eval_cases() if case.id == case_id)
    seen = []

    async def existing_readiness(*, response, request, **kwargs):
        seen.append(request.current_user_message)
        assert response.tool_calls == []
        values = response.candidate_strategy_draft.model_dump()
        for field in (
            "date_range",
            "capital_amount",
            "entry_rule",
            "exit_rule",
            "rule_spec",
            "recurring_contribution",
        ):
            expected = getattr(case.expected, field)
            if expected is not None:
                values[field] = expected
        if (
            values["requested_strategy_template"] == "moving_average_crossover"
            and values["entry_rule"] is None
        ):
            # The established shorthand owner supplies this canonical default.
            specified = next(
                item
                for item in load_eval_cases()
                if item.id == "messy_english_complete_sma_crossover_benchmark_issue_270"
            )
            values["entry_rule"] = specified.expected.entry_rule
            values["exit_rule"] = specified.expected.exit_rule
        return response.model_copy(
            update={"candidate_strategy_draft": LLMStrategyDraft.model_validate(values)}
        )

    monkeypatch.setattr(
        llm_interpreter, "_audited_response_ready_for_runtime", existing_readiness
    )
    result = await execute([call], message=case.prompt)

    assert seen == [case.prompt]
    assert result.outcome == "ready_for_confirmation", json.dumps(
        result.patch, default=str
    )
    strategy = result.patch["candidate_strategy_draft"]
    assert strategy["date_range"] == case.expected.date_range
    assert strategy["capital_amount"] == case.expected.capital_amount
    assert call.model_dump(mode="json") == original
    assert result.patch["tool_calls"] == [call]
    assert (
        result.patch["normalized_signals"]["tool_input_repair"]["call_id"] == call.call_id
    )


@pytest.mark.asyncio
async def test_existing_provider_receipts_keep_isolated_call_scope():
    import asyncio

    from argus.llm import openrouter

    def record():
        return openrouter.record_openrouter_route_receipt(
            task="interpretation_repair",
            model_name="fixture/model",
            mode="json_schema",
            schema_name="FocusedStrategyExtraction",
            latency_ms=7,
            outcome="succeeded",
            usage_cost_usd=0.01,
        )

    async def scoped(call_id):
        with openrouter.tool_call_receipt_scope(call_id=call_id, tool_name="backtest"):
            await asyncio.sleep(0)
            return record()

    token = openrouter.begin_openrouter_route_receipt_capture()
    try:
        first, second = await asyncio.gather(scoped("first"), scoped("second"))
        assert first.repair_effect["tool_call_id"] == "first"
        assert second.repair_effect["tool_call_id"] == "second"
        openrouter.annotate_latest_openrouter_route_receipt(
            task="interpretation_repair",
            schema_name="FocusedStrategyExtraction",
            repair_effect={"repair_applied": True},
        )
        assert second.repair_effect["tool_call_id"] == "second"
        with (
            pytest.raises(ValueError),
            openrouter.tool_call_receipt_scope(call_id="failed", tool_name="backtest"),
        ):
            raise ValueError("scope reset")
        outside = record()
        assert "tool_call_id" not in outside.repair_effect
    finally:
        receipts = openrouter.end_openrouter_route_receipt_capture(token)
    assert len(receipts) == 3
    assert [receipt.latency_ms for receipt in receipts] == [7, 7, 7]
    assert [receipt.usage_cost_usd for receipt in receipts] == [0.01, 0.01, 0.01]


@pytest.mark.asyncio
async def test_unresolved_declared_cost_blocker_survives_stage_decision(monkeypatch):
    call = retained_call("natural_language_establishes_modeled_costs_issue_271")

    async def no_repair(*, response, **kwargs):
        return response

    monkeypatch.setattr(llm_interpreter, "_audited_response_ready_for_runtime", no_repair)
    result = await execute(
        [call], message=call.arguments["strategy"]["raw_user_phrasing"]
    )

    assert result.outcome == "needs_clarification"
    assert {item["field_name"] for item in result.patch["ambiguous_fields"]} >= {
        "fee_rate",
        "slippage",
    }
    assert result.patch["tool_calls"] == [call]


@pytest.mark.parametrize("field_name,value", [("fee_rate", 0), ("slippage", 0.0005)])
@pytest.mark.parametrize("source", ["typed", "extra"])
def test_unresolved_cost_preserves_candidate_in_canonical_ambiguity(
    field_name, value, source, faker
):
    from argus.agent_runtime.interpreter.execution_cost_fidelity import (
        apply_cost_fidelity,
    )
    from argus.agent_runtime.llm_interpreter_types import LLMInterpretationResponse
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest

    values = (
        {field_name: value}
        if source == "typed"
        else {"extra_parameters": {field_name: value}}
    )
    response = LLMInterpretationResponse(
        intent="calculate",
        task_relation="new_task",
        semantic_turn_act="new_idea",
        user_goal_summary="Review execution cost assumptions.",
        candidate_strategy_draft=LLMStrategyDraft(
            **values,
            # A claimed user cost needs evidence even when the rate is zero;
            # an unclaimed zero on a fresh idea is only the engine default.
            field_provenance={field_name: "explicit_user"},
        ),
    )
    request = InterpretationRequest(
        current_user_message="Review these execution cost assumptions.",
        user=UserState(user_id=faker.uuid4()),
    )

    assert apply_cost_fidelity(
        response,
        llm_interpreter.StatedRunFieldFidelityAudit(),
        request.current_user_message,
        None,
    )
    canonical = llm_interpreter.canonical_strategy_interpretation(
        response, request=request
    )

    assert canonical.requires_clarification
    assert field_name not in canonical.candidate_strategy_draft.extra_parameters
    assert [
        (item.field_name, float(item.raw_value), item.reason_code)
        for item in canonical.ambiguous_fields
    ] == [
        (
            field_name,
            value,
            "execution_cost_evidence_unresolved",
        )
    ]


@pytest.mark.asyncio
async def test_unscoped_repeated_calls_never_use_whole_question_repair(monkeypatch):
    original = retained_call(
        "dca_capital_semantics_stated_seed_reaches_ready_to_run_issue_455"
    )
    calls = [
        original.model_copy(deep=True, update={"call_id": f"repeat-{index}"})
        for index in range(2)
    ]
    calls[0].arguments["strategy"]["initial_capital"] = 0
    before = [call.model_dump(mode="json") for call in calls]

    async def unexpected_repair(**kwargs):
        raise AssertionError("The whole multi-call question cannot be replayed per call")

    monkeypatch.setattr(
        llm_interpreter, "_audited_response_ready_for_runtime", unexpected_repair
    )
    result = await execute(
        calls, message=original.arguments["strategy"]["raw_user_phrasing"]
    )

    assert result.outcome == "needs_clarification"
    assert [call.model_dump(mode="json") for call in result.patch["tool_calls"]] == before
    assert (
        result.patch["candidate_strategy_draft"]["extra_parameters"]["initial_capital"]
        == 0
    )


@pytest.mark.asyncio
async def test_repair_cannot_replace_a_known_zero(monkeypatch):
    call = retained_call(
        "dca_capital_semantics_stated_seed_reaches_ready_to_run_issue_455"
    )
    call.arguments["strategy"]["initial_capital"] = 0

    async def conflicting_repair(*, response, **kwargs):
        values = response.candidate_strategy_draft.model_dump()
        values.update(
            initial_capital=5000,
            recurring_contribution=200,
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
        )
        return response.model_copy(
            update={"candidate_strategy_draft": LLMStrategyDraft.model_validate(values)}
        )

    monkeypatch.setattr(
        llm_interpreter, "_audited_response_ready_for_runtime", conflicting_repair
    )
    result = await execute(
        [call], message=call.arguments["strategy"]["raw_user_phrasing"]
    )

    assert result.outcome == "needs_clarification"
    assert "initial_capital" in {
        item["field_name"] for item in result.patch["ambiguous_fields"]
    }
    assert (
        result.patch["candidate_strategy_draft"]["extra_parameters"]["initial_capital"]
        == 0
    )
    assert result.patch["tool_calls"] == [call]


@pytest.mark.asyncio
async def test_retained_cost_call_uses_the_real_fidelity_owner_and_existing_receipt(
    monkeypatch,
):
    from argus.llm import openrouter

    call = retained_call("natural_language_establishes_modeled_costs_issue_271")
    message = call.arguments["strategy"]["raw_user_phrasing"]
    schemas = []

    async def scripted_provider(**kwargs):
        schema = kwargs["schema_name"]
        schemas.append(schema)
        assert schema in {"StatedRunFieldFidelityAudit", "FocusedDateWindowExtraction"}
        openrouter.record_openrouter_route_receipt(
            task=kwargs["task"],
            model_name="fixture/model",
            mode="json_schema",
            schema_name=schema,
            latency_ms=11,
            outcome="succeeded",
            usage_cost_usd=0.01,
        )
        if schema == "FocusedDateWindowExtraction":
            return llm_interpreter.FocusedDateWindowExtraction(
                has_date_window=True,
                date_range=call.arguments["strategy"]["date_range"],
                confidence=0.95,
            )
        return llm_interpreter.StatedRunFieldFidelityAudit(
            fee={"rate": 0.001, "evidence_span": "10 bps fee"},
            slippage={"rate": 0.0005, "evidence_span": "5 bps slippage"},
        )

    monkeypatch.setattr(
        llm_interpreter, "invoke_openrouter_json_schema", scripted_provider
    )
    monkeypatch.setattr(
        llm_interpreter,
        "_unique_repair_models",
        lambda _preferred, **kwargs: ["fixture/model"],
    )
    token = openrouter.begin_openrouter_route_receipt_capture()
    try:
        result = await execute([call], message=message)
    finally:
        receipts = openrouter.end_openrouter_route_receipt_capture(token)

    assert result.outcome == "ready_for_confirmation", result.patch
    extra = result.patch["candidate_strategy_draft"]["extra_parameters"]
    assert extra["fee_rate"] == call.arguments["strategy"]["fee_rate"]
    assert extra["slippage"] == call.arguments["strategy"]["slippage"]
    assert result.patch["ambiguous_fields"] == []
    assert schemas == ["StatedRunFieldFidelityAudit", "FocusedDateWindowExtraction"]
    assert len(receipts) == len(schemas)
    assert all(
        receipt.repair_effect["tool_call_id"] == call.call_id for receipt in receipts
    )
    assert all(receipt.usage_cost_usd == 0.01 for receipt in receipts)


@pytest.mark.asyncio
async def test_batch_repair_reads_only_its_disjoint_literal_source(monkeypatch):
    first = retained_call("capability_honesty_golden_cross_control_aapl")
    second = first.model_copy(deep=True, update={"call_id": "other-call"})
    source = first.arguments["strategy"]["raw_user_phrasing"]
    second_source = source.replace("AAPL", "MSFT")
    second.arguments["strategy"].update(
        asset_universe=["MSFT"], raw_user_phrasing=second_source
    )
    observed = []

    async def repair(*, response, request, **kwargs):
        observed.append(request)
        assert request.current_user_message == source
        assert request.recent_thread_history == []
        assert request.latest_task_snapshot is None
        assert request.selected_thread_metadata == {}
        # A scripted empty repair must keep both original calls for clarification.
        return response

    monkeypatch.setattr(llm_interpreter, "_audited_response_ready_for_runtime", repair)
    result = await execute([first, second], message=f"{source} Also: {second_source}")

    assert len(observed) == 1
    assert result.outcome == "needs_clarification"
    assert result.patch["candidate_strategy_draft"]["asset_universe"] == ["AAPL"]
    assert result.patch["tool_calls"] == [first, second]


@pytest.mark.asyncio
async def test_retained_indicator_call_reaches_the_real_focused_extraction_owner(
    monkeypatch,
):
    from argus.agent_runtime import signal_rule_repair
    from argus.llm import openrouter

    case_id = "messy_english_complete_sma_crossover_benchmark_issue_270"
    case = next(case for case in load_eval_cases() if case.id == case_id)
    call = retained_call(case_id)
    values = deepcopy(call.arguments["strategy"])
    for field in ("date_range", "capital_amount", "entry_rule", "exit_rule", "rule_spec"):
        expected = getattr(case.expected, field)
        if expected is not None:
            values[field] = expected
    values["timeframe"] = "1D"
    scripted = {
        "FocusedStrategyExtraction": llm_interpreter.FocusedStrategyExtraction(
            **values,
            is_testable_strategy=True,
            user_goal_summary=case.prompt,
        ),
        "StatedRunFieldFidelityAudit": llm_interpreter.StatedRunFieldFidelityAudit(
            capital_amount=case.expected.capital_amount,
            date_range=case.expected.date_range,
            timeframe="1D",
            comparison_baseline=values["comparison_baseline"],
        ),
        "StatedStartingCapitalAudit": llm_interpreter.StatedStartingCapitalAudit(
            starting_capital=case.expected.capital_amount,
        ),
        "FocusedDateWindowExtraction": llm_interpreter.FocusedDateWindowExtraction(
            has_date_window=True,
            date_range=case.expected.date_range,
            confidence=0.95,
        ),
        "ExecutableStrategyGroundingAudit": llm_interpreter.ExecutableStrategyGroundingAudit(
            outcome="grounded"
        ),
        "SignalRuleGroundingAudit": signal_rule_repair.SignalRuleGroundingAudit(
            outcome="grounded"
        ),
    }
    observed = []

    async def provider(**kwargs):
        schema = kwargs["schema_name"]
        observed.append(schema)
        assert schema in scripted
        openrouter.record_openrouter_route_receipt(
            task=kwargs["task"],
            model_name="fixture/model",
            mode="json_schema",
            schema_name=schema,
            latency_ms=3,
            outcome="succeeded",
            usage_cost_usd=0.01,
        )
        return scripted[schema].model_copy(deep=True)

    monkeypatch.setattr(llm_interpreter, "invoke_openrouter_json_schema", provider)
    monkeypatch.setattr(signal_rule_repair, "invoke_openrouter_json_schema", provider)
    monkeypatch.setattr(
        llm_interpreter,
        "_unique_repair_models",
        lambda _preferred, **kwargs: ["fixture/model"],
    )
    token = openrouter.begin_openrouter_route_receipt_capture()
    try:
        result = await execute([call], message=case.prompt)
    finally:
        receipts = openrouter.end_openrouter_route_receipt_capture(token)
    assert result.outcome == "ready_for_confirmation", result.patch
    strategy = result.patch["candidate_strategy_draft"]
    assert strategy["date_range"] == case.expected.date_range
    assert strategy["capital_amount"] == case.expected.capital_amount
    assert strategy["timeframe"] == "1D"
    assert strategy["entry_rule"] == case.expected.entry_rule
    assert strategy["exit_rule"] == case.expected.exit_rule
    assert "FocusedStrategyExtraction" in observed
    assert len(receipts) == len(observed)
    assert all(
        receipt.repair_effect["tool_call_id"] == call.call_id for receipt in receipts
    )
    assert result.patch["tool_calls"] == [call]


@pytest.mark.asyncio
async def test_complete_repeated_calls_keep_distinct_inputs_without_audit(monkeypatch):
    from argus.agent_runtime.backtest_input import BacktestStrategyInput
    from argus.agent_runtime.interpreter.backtest_calls import prepare_backtest_tool_input

    from tests.agent_runtime.test_registered_tool_execution import _dca_state

    state = _dca_state(approved=False)
    input = BacktestStrategyInput.from_runtime_strategy(state.candidate_strategy_draft)
    state.tool_calls = [
        ToolCall(
            tool_name="backtest",
            call_id=f"repeat-{index}",
            arguments={
                "strategy": input.model_copy(
                    deep=True, update={"initial_capital": seed}
                ).model_dump(mode="json")
            },
        )
        for index, seed in enumerate((0, 5000))
    ]
    # The canonical fixture carries extension fields; changing a typed input
    # must update that one field's legacy representation too.
    for call in state.tool_calls:
        call.arguments["strategy"]["extra_parameters"].pop("initial_capital", None)
        call.arguments["strategy"]["raw_user_phrasing"] = call.call_id
    state.current_user_message = " / ".join(call.call_id for call in state.tool_calls)

    async def forbid_audit(**kwargs):
        raise AssertionError("A complete batch must use typed arguments directly")

    monkeypatch.setattr(
        llm_interpreter, "_audited_response_ready_for_runtime", forbid_audit
    )
    for call in state.tool_calls:
        result = await prepare_backtest_tool_input(
            BacktestStrategyInput.model_validate(call.arguments["strategy"]),
            state=state,
            user=None,
            call=call,
        )
        assert result.outcome == "ready_for_confirmation", result.patch
        repair = result.patch["normalized_signals"]["tool_input_repair"]
        assert repair["repair_attempted"] is False
        assert repair["repair_applied"] is False
        assert (
            result.patch["candidate_strategy_draft"]["extra_parameters"][
                "initial_capital"
            ]
            == call.arguments["strategy"]["initial_capital"]
        )


@pytest.mark.asyncio
async def test_pending_answer_keeps_trusted_history_snapshot_and_requested_field(
    monkeypatch,
):
    from argus.agent_runtime.stages import interpret
    from argus.agent_runtime.state.models import StrategySummary, TaskSnapshot

    from tests.agent_runtime.test_provider_asset_ownership import ResolvedAssetStub

    # KO is absent from the synthetic catalog; script that real provider fact.
    for module in (llm_interpreter, interpret):
        original_resolver = module.resolve_asset

        def resolver(symbol, *, original=original_resolver, **kwargs):
            if symbol.upper() == "KO":
                return ResolvedAssetStub("KO", "equity")
            return original(symbol, **kwargs)

        monkeypatch.setattr(module, "resolve_asset", resolver)

    call = retained_call(
        "dca_capital_semantics_prebaked_chip_bare_amount_reaches_ready_to_run"
    )
    window = {"start": "2019-09-09", "end": "2024-09-09"}
    pending = StrategySummary(
        strategy_type="dca_accumulation",
        asset_universe=["KO"],
        asset_class="equity",
        date_range=window,
        cadence="monthly",
    )
    snapshot = TaskSnapshot(pending_strategy_summary=pending)
    metadata = {
        "last_stage_outcome": "await_user_reply",
        "requested_field": "capital_amount",
    }
    state = RunState(
        current_user_message="$200",
        task_relation="continue",
        semantic_turn_act="answer_pending_need",
        recent_thread_history=[
            {
                "role": "user",
                "content": "Test monthly KO buys over the previous five years.",
            }
        ],
        tool_calls=[call],
    )
    observed = []

    async def existing_readiness(*, response, request, **kwargs):
        observed.append(request)
        assert response.task_relation == "continue"
        assert response.semantic_turn_act == "answer_pending_need"
        return response

    monkeypatch.setattr(
        llm_interpreter, "_audited_response_ready_for_runtime", existing_readiness
    )
    result = await execute_tool_calls_async(
        state=state,
        tool=object(),
        latest_task_snapshot=snapshot,
        selected_thread_metadata=metadata,
    )

    assert len(observed) == 1
    assert observed[0].recent_thread_history == state.recent_thread_history
    assert observed[0].latest_task_snapshot is snapshot
    assert observed[0].selected_thread_metadata == metadata
    assert result.outcome == "ready_for_confirmation", json.dumps(
        result.patch, default=str
    )
    strategy = result.patch["candidate_strategy_draft"]
    assert strategy["date_range"] == window
    assert strategy["capital_amount"] == call.arguments["strategy"]["capital_amount"]
    assert result.patch["tool_calls"] == [call]


@pytest.mark.asyncio
async def test_preflight_facts_survive_catalog_handoff_and_stay_scoped_to_declared_assets(
    monkeypatch,
):
    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )
    from argus.agent_runtime.interpreter import provider_context_assets
    from argus.agent_runtime.interpreter.tool_calls import (
        catalog_stage_result,
        runtime_catalog_interpretation,
    )
    from argus.agent_runtime.llm_interpreter_types import LLMInterpretationResponse
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest

    from tests.agent_runtime.test_provider_asset_ownership import BTC_CONTEXT_ROW

    call = retained_call("natural_language_establishes_modeled_costs_issue_271")
    call.arguments["strategy"].update(
        asset_universe=["BTC"],
        asset_class=None,
        fee_rate=None,
        slippage=None,
        extra_parameters={
            "provider_resolved_assets": [{**BTC_CONTEXT_ROW, "asset_class": "equity"}]
        },
    )
    other = call.model_copy(deep=True, update={"call_id": "other-call"})
    other.arguments["strategy"].update(asset_universe=["MSFT"], extra_parameters={})
    source_context = json.dumps(
        {
            "asset_resolution_candidates": [
                BTC_CONTEXT_ROW,
                {
                    **BTC_CONTEXT_ROW,
                    "raw_text": "Microsoft",
                    "symbol": "MSFT",
                    "asset_class": "equity",
                    "raw_symbol": "MSFT",
                },
                {
                    **BTC_CONTEXT_ROW,
                    "raw_text": "unselected",
                    "symbol": "AAPL",
                    "asset_class": "equity",
                    "raw_symbol": "AAPL",
                },
            ]
        }
    )
    user = UserState(user_id="provider-handoff")
    request = InterpretationRequest(
        current_user_message="Test both independently.", user=user
    )
    response = LLMInterpretationResponse(
        intent="calculate",
        task_relation="new_task",
        semantic_turn_act="new_idea",
        user_goal_summary="",
        tool_calls=[call, other],
    )
    ready = await llm_interpreter._response_ready_for_runtime(
        response=response,
        preferred_model="unused",
        request=request,
        asset_resolution_context=source_context,
    )
    interpretation = runtime_catalog_interpretation(ready)

    async def forbid_composer(**kwargs):
        raise AssertionError("A tool call does not need a capability composer")

    handoff = await catalog_stage_result(
        interpretation,
        user=user,
        current_user_message=request.current_user_message,
        contract=build_default_capability_contract(),
        compose_capability_answer=forbid_composer,
    )
    assert handoff is not None
    assert "_tool_asset_resolution_context" not in ready.model_dump()
    assert "_tool_asset_resolution_context" not in interpretation.model_dump()
    rows = json.loads(
        handoff.patch["normalized_signals"][
            provider_context_assets.TOOL_ASSET_CONTEXT_SIGNAL
        ]
    )["asset_resolution_candidates"]
    assert {row["symbol"] for row in rows} == {"BTC", "MSFT", "AAPL"}
    result = await execute_tool_calls_async(
        state=RunState.model_validate(
            {"current_user_message": request.current_user_message, **handoff.patch}
        ),
        tool=object(),
        user=user,
    )
    strategy = result.patch["candidate_strategy_draft"]
    assert strategy["asset_universe"] == ["BTC"]
    assert strategy["asset_class"] == "crypto"
    assert strategy["comparison_baseline"] == "BTC"
    assert {
        record["symbol"]
        for record in strategy["extra_parameters"]["provider_resolved_assets"]
    } == {"BTC"}
    assert (
        result.patch["normalized_signals"][
            provider_context_assets.TOOL_ASSET_CONTEXT_SIGNAL
        ]
        == source_context
    )


@pytest.mark.asyncio
async def test_generic_catalog_handoff_accepts_an_unrelated_string_strategy_argument():
    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )
    from argus.agent_runtime.interpreter.tool_calls import catalog_stage_result
    from argus.agent_runtime.stages.interpret_types import StructuredInterpretation

    call = ToolCall(
        tool_name="test_tool",
        call_id="unrelated",
        arguments={"strategy": "ordinary typed string"},
    )
    interpretation = StructuredInterpretation(
        uses_tool_catalog=True,
        intent="calculate",
        task_relation="new_task",
        user_goal_summary="",
        tool_calls=[call],
    )

    async def unused(**kwargs):
        raise AssertionError("No capability prose needed")

    result = await catalog_stage_result(
        interpretation,
        user=UserState(user_id="unrelated-tool"),
        current_user_message="",
        contract=build_default_capability_contract(),
        compose_capability_answer=unused,
    )
    assert result is not None
    assert result.outcome == "approved_for_execution"
    assert result.patch["tool_calls"] == [call.model_dump(mode="json")]


@pytest.mark.asyncio
async def test_interleaved_receipt_annotation_targets_its_active_call_scope():
    import asyncio

    from argus.llm import openrouter

    both_recorded = asyncio.Event()
    count = 0

    async def scoped(call_id):
        nonlocal count
        with openrouter.tool_call_receipt_scope(call_id=call_id, tool_name="backtest"):
            receipt = openrouter.record_openrouter_route_receipt(
                task="interpretation_repair",
                model_name="fixture/model",
                mode="json_schema",
                schema_name="FocusedStrategyExtraction",
                latency_ms=1,
                outcome="succeeded",
            )
            count += 1
            if count == 2:
                both_recorded.set()
            await both_recorded.wait()
            openrouter.annotate_latest_openrouter_route_receipt(
                task="interpretation_repair",
                schema_name="FocusedStrategyExtraction",
                repair_effect={"trigger_reason": call_id},
            )
            return receipt

    token = openrouter.begin_openrouter_route_receipt_capture()
    try:
        receipts = await asyncio.gather(scoped("first"), scoped("second"))
    finally:
        captured = openrouter.end_openrouter_route_receipt_capture(token)
    assert receipts == captured
    assert [receipt.repair_effect for receipt in captured] == [
        {"tool_call_id": call_id, "tool_name": "backtest", "trigger_reason": call_id}
        for call_id in ("first", "second")
    ]


def test_receipt_scope_nesting_restores_parent_and_omits_unsafe_identity():
    from argus.llm import openrouter

    def record():
        return openrouter.record_openrouter_route_receipt(
            task="interpretation_repair",
            model_name="fixture/model",
            mode="json_schema",
            schema_name="FocusedStrategyExtraction",
            latency_ms=0,
            outcome="succeeded",
        )

    unsafe_identity = "user text must not enter a receipt"
    with openrouter.tool_call_receipt_scope(call_id="outer", tool_name="backtest"):
        with openrouter.tool_call_receipt_scope(
            call_id=unsafe_identity, tool_name="backtest"
        ):
            inner = record()
        outer = record()
    assert unsafe_identity not in json.dumps(inner.as_dict())
    assert len(inner.repair_effect["tool_call_id"]) == 64
    assert outer.repair_effect["tool_call_id"] == "outer"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scope",
    [
        "fresh",
        "pending",
        "repeated_history",
        "assistant_history",
        "not_run",
        "changed_identity",
    ],
)
async def test_cost_bearing_second_call_uses_history_only_during_approved_queue_resume(
    monkeypatch, scope
):
    from argus.agent_runtime.backtest_input import BacktestStrategyInput
    from argus.agent_runtime.interpreter.backtest_calls import prepare_backtest_tool_input
    from argus.agent_runtime.state.models import ConversationMessage, TaskSnapshot

    from tests.agent_runtime.test_registered_tool_execution import _dca_state

    state = _dca_state(approved=True)
    first = ToolCall(
        tool_name="backtest",
        call_id="approved-first",
        arguments={
            "strategy": BacktestStrategyInput.from_runtime_strategy(
                state.candidate_strategy_draft
            ).model_dump(mode="json")
        },
    )
    second = retained_call("natural_language_establishes_modeled_costs_issue_271")
    second.arguments["strategy"]["evidence_spans"].update(
        fee_rate="10 bps fee",
        slippage="5 bps slippage",
    )
    source = second.arguments["strategy"]["raw_user_phrasing"]
    state.current_user_message = "Run"
    state.recent_thread_history = [
        ConversationMessage(
            role="user", content=f"Run the first setup. Separately: {source}"
        )
    ]
    snapshot = (
        TaskSnapshot(pending_tool_calls=[first, second]) if scope != "fresh" else None
    )
    if scope == "repeated_history":
        state.recent_thread_history *= 2
    if scope == "assistant_history":
        state.recent_thread_history[0].role = "assistant"
    if scope == "not_run":
        state.structured_action = None
    if scope == "changed_identity":
        second = second.model_copy(update={"call_id": "not-the-pending-call"})
    before = second.model_dump(mode="json")
    state.tool_calls = [first, second]

    async def no_audit(**kwargs):
        raise AssertionError("Complete typed calls need no model repair")

    monkeypatch.setattr(llm_interpreter, "_audited_response_ready_for_runtime", no_audit)
    result = await prepare_backtest_tool_input(
        BacktestStrategyInput.model_validate(second.arguments["strategy"]),
        state=state,
        user=None,
        call=second,
        latest_task_snapshot=snapshot,
    )
    assert result.outcome == (
        "ready_for_confirmation" if scope == "pending" else "needs_clarification"
    )
    if scope == "pending":
        extra = result.patch["candidate_strategy_draft"]["extra_parameters"]
        assert extra["fee_rate"] == second.arguments["strategy"]["fee_rate"]
        assert extra["slippage"] == second.arguments["strategy"]["slippage"]
    assert (
        result.patch["normalized_signals"]["tool_input_repair"]["repair_attempted"]
        is False
    )
    assert second.model_dump(mode="json") == before


@pytest.mark.parametrize(
    ("message", "source", "other", "expected"),
    [
        ("alpha beta gamma", "alpha beta", "beta gamma", None),
        ("alpha beta / alpha beta", "alpha beta", "beta", None),
        ("alpha beta / gamma delta", "alpha beta", "gamma delta", "alpha beta"),
    ],
)
def test_repair_source_uses_unique_nonoverlapping_spans(message, source, other, expected):
    from argus.agent_runtime.backtest_input import BacktestStrategyInput
    from argus.agent_runtime.interpreter.backtest_calls import _call_source

    calls = [
        ToolCall(
            tool_name="backtest",
            call_id=str(index),
            arguments={"strategy": {"raw_user_phrasing": text}},
        )
        for index, text in enumerate((source, other))
    ]
    state = RunState(current_user_message=message, tool_calls=calls)
    assert (
        _call_source(
            BacktestStrategyInput(raw_user_phrasing=source), state=state, call=calls[0]
        )
        == expected
    )
