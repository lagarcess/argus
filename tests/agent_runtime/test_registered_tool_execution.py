"""Executable declarations dispatch through the graph without a backtest form."""

from __future__ import annotations

import pytest
from argus.agent_runtime.stages import execute
from argus.agent_runtime.stages.interpret_types import StageResult
from argus.agent_runtime.state.models import RunState
from argus.domain.tool_contracts import (
    MAX_TOOL_CALLS,
    LocalizedText,
    ToolCall,
    ToolCardPresentation,
    ToolFact,
    ToolInputFact,
    ToolOutcome,
    ToolResultCard,
)
from faker import Faker
from pydantic import BaseModel, ConfigDict

fake = Faker()


class EchoArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: float


class EchoResult(BaseModel):
    value: float


def _presentation(arguments, outcome) -> ToolCardPresentation:
    return ToolCardPresentation(
        title=LocalizedText(locale_key="test.echo.title"),
        answer=(
            ToolFact(
                name="value",
                label=LocalizedText(locale_key="test.echo.value"),
                value=outcome.result["value"],
            )
            if outcome.status == "succeeded"
            else None
        ),
        inputs=[
            ToolInputFact(
                name="value",
                label=LocalizedText(locale_key="test.echo.value"),
                value=arguments.value,
                editable=True,
            )
        ],
    )


def _declaration(handler, *, name="echo", policy=None, confirmation_handler=None):
    from argus.domain.tool_declaration import (
        ToolCardBinding,
        ToolDeclaration,
        ToolPolicy,
        ToolProgressTemplate,
    )

    return ToolDeclaration(
        name=name,
        description="Return a typed input unchanged for registry contract tests.",
        handler=handler,
        confirmation_handler=confirmation_handler,
        policy=policy or ToolPolicy(editable_fields=("value",)),
        progress=ToolProgressTemplate(
            locale_key="test.echo.progress", argument_fields=("value",)
        ),
        card=ToolCardBinding(card_type="test_echo", version=1, presenter=_presentation),
    )


def _catalog(*declarations):
    from argus.domain.tool_declaration import ToolCatalog

    return ToolCatalog(declarations)


def _call(value, *, name="echo", call_id=None) -> ToolCall:
    return ToolCall(
        tool_name=name,
        call_id=call_id or fake.uuid4(),
        arguments={"value": value},
    )


def _forbid_launch(*args, **kwargs):
    raise AssertionError("A general tool turn must not construct a backtest launch")


@pytest.mark.asyncio()
async def test_zero_tool_calls_do_not_invent_a_backtest(monkeypatch) -> None:
    monkeypatch.setattr(execute, "_launch_payload", _forbid_launch)
    result = await execute.execute_stage_async(
        state=RunState(current_user_message=fake.sentence()),
        tool=object(),
    )

    assert result.outcome == "ready_to_respond"
    assert result.patch["tool_call_records"] == []
    assert not result.patch.get("final_response_payload", {}).get("result_card")


@pytest.mark.asyncio()
@pytest.mark.parametrize("names", [("echo",), ("echo", "echo"), ("echo", "identity")])
async def test_local_tools_execute_in_order_without_a_launch_payload(monkeypatch, names):
    observed = []

    def echo(arguments: EchoArguments) -> EchoResult:
        observed.append(arguments.value)
        return EchoResult(value=arguments.value)

    monkeypatch.setattr(execute, "_launch_payload", _forbid_launch)
    calls = [_call(index, name=name) for index, name in enumerate(names)]
    result = await execute.execute_stage_async(
        state=RunState(current_user_message=fake.sentence(), tool_calls=calls),
        tool=object(),
        catalog=_catalog(*(_declaration(echo, name=name) for name in set(names))),
    )

    assert observed == list(range(len(names)))
    assert result.outcome == "ready_to_respond"
    cards = result.patch["final_response_payload"]["tool_result_cards"]
    assert [card["call_id"] for card in cards] == [call.call_id for call in calls]
    assert len({card["artifact_id"] for card in cards}) == len(calls)
    assert [card["presentation"]["answer"]["value"] for card in cards] == observed
    assert "result_card" not in result.patch["final_response_payload"]
    assert result.patch["tool_calls"] == []


@pytest.mark.asyncio()
@pytest.mark.parametrize("status", ["invalid", "ambiguous", "bounded", "unavailable"])
async def test_declared_failure_has_no_answer_or_result(monkeypatch, status):
    from argus.domain.tool_declaration import ToolInvocationError

    def bounded(arguments: EchoArguments) -> EchoResult:
        raise ToolInvocationError(status, code="test_bound")

    monkeypatch.setattr(execute, "_launch_payload", _forbid_launch)
    result = await execute.execute_stage_async(
        state=RunState(current_user_message=fake.sentence(), tool_calls=[_call(0)]),
        tool=object(),
        catalog=_catalog(_declaration(bounded)),
    )

    card = result.patch["final_response_payload"]["tool_result_cards"][0]
    assert card["outcome"]["status"] == status
    assert card["outcome"]["result"] is None
    assert card["presentation"]["answer"] is None


@pytest.mark.asyncio()
async def test_duplicate_call_ids_fail_before_any_callable_runs(monkeypatch):
    def echo(arguments: EchoArguments) -> EchoResult:
        raise AssertionError("Duplicate identities must fail before any dispatch")

    monkeypatch.setattr(execute, "_launch_payload", _forbid_launch)
    call_id = fake.uuid4()
    result = await execute.execute_stage_async(
        state=RunState(
            current_user_message=fake.sentence(),
            tool_calls=[_call(0, call_id=call_id), _call(1, call_id=call_id)],
        ),
        tool=object(),
        catalog=_catalog(_declaration(echo)),
    )

    assert result.outcome == "execution_failed_terminally"
    assert result.patch["final_response_payload"]["code"] == "duplicate_tool_call_id"


@pytest.mark.asyncio()
async def test_oversized_batch_is_rejected_before_any_call_executes():
    def echo(arguments: EchoArguments) -> EchoResult:
        raise AssertionError("An oversized batch cannot execute partial work")

    state = RunState(current_user_message=fake.sentence())
    # A mutated already-validated state still cannot execute a partial batch.
    state.tool_calls.extend(_call(index) for index in range(MAX_TOOL_CALLS + 1))
    result = await execute.execute_stage_async(
        state=state,
        tool=object(),
        catalog=_catalog(_declaration(echo)),
    )

    assert result.outcome == "execution_failed_terminally"
    assert result.patch["final_response_payload"]["code"] == "too_many_tool_calls"


@pytest.mark.asyncio()
async def test_cost_policy_requires_confirmation_before_invocation(monkeypatch):
    from argus.agent_runtime.tools.registered_backtest import get_backtest_declaration

    monkeypatch.setattr(execute, "_launch_payload", _forbid_launch)
    state = _dca_state(approved=False)
    calls = [
        ToolCall(
            tool_name="backtest",
            call_id=fake.uuid4(),
            arguments={
                "strategy": state.candidate_strategy_draft.model_dump(mode="json")
            },
        )
    ]
    state.tool_calls = calls
    declaration = get_backtest_declaration()
    result = await execute.execute_stage_async(
        state=state,
        tool=object(),
        catalog=_catalog(declaration),
    )
    assert declaration.policy.confirmation == "required"
    assert result.outcome == "ready_for_confirmation"
    assert result.patch["tool_calls"] == calls
    assert result.patch["tool_call_records"] == []


def _dca_state(*, approved: bool) -> RunState:
    from argus.agent_runtime.state.models import ConfirmationPayload, StrategySummary

    contribution = fake.random_int(min=25, max=500)
    dates = {"start": "2024-01-02", "end": "2024-12-31"}
    strategy = StrategySummary(
        strategy_type="dca_accumulation",
        asset_universe=["AAPL"],
        asset_class="equity",
        capital_amount=contribution,
        cadence="monthly",
        date_range=dates,
        timeframe="1D",
    )
    launch_payload = {
        "strategy_type": strategy.strategy_type,
        "symbol": strategy.asset_universe[0],
        "symbols": strategy.asset_universe,
        "asset_class": strategy.asset_class,
        "timeframe": strategy.timeframe,
        "date_range": dates,
        "sizing_mode": "capital_amount",
        "capital_amount": contribution,
        "starting_capital": 0,
        "recurring_contribution": contribution,
        "cadence": strategy.cadence,
        "benchmark_symbol": "SPY",
        "coverage_preflight": {
            "outcome": "full_coverage",
            "requested_date_range": dates,
            "effective_date_range": dates,
            "preflight_id": "sha256:" + fake.sha256(),
        },
    }
    return RunState(
        current_user_message=fake.sentence(),
        candidate_strategy_draft=strategy,
        confirmation_payload=(
            ConfirmationPayload(
                strategy=strategy,
                launch_payload=launch_payload,
                validation={"executable": True, "status": "ready_to_run"},
            )
            if approved
            else None
        ),
        structured_action={"type": "run_backtest"} if approved else None,
    )


@pytest.mark.asyncio()
async def test_approved_dca_uses_the_registered_callable_and_existing_launch_owner():
    from argus.agent_runtime.tools.registered_backtest import get_backtest_declaration

    received = []

    class BacktestTool:
        def run(self, payload):
            received.append(payload)
            return {
                "success": True,
                "payload": {"total_return": 0.14, "benchmark_return": 0.09},
            }

    state = _dca_state(approved=True)
    result = await execute.execute_stage_async(
        state=state, tool=BacktestTool(), catalog=_catalog(get_backtest_declaration())
    )

    assert result.outcome == "execution_succeeded"
    assert len(received) == 1
    assert received[0]["starting_capital"] == 0
    assert (
        received[0]["recurring_contribution"]
        == state.candidate_strategy_draft.capital_amount
    )
    assert received[0]["cadence"] == state.candidate_strategy_draft.cadence
    assert result.patch["tool_call_records"][0]["tool_name"] == "backtest"


def test_pending_calls_survive_the_existing_task_snapshot():
    from argus.agent_runtime.graph.workflow import _build_task_snapshot

    calls = [_call(0), _call(1)]
    snapshot = _build_task_snapshot(
        run_state=RunState(current_user_message=fake.sentence(), tool_calls=calls),
        stage_outcome="await_approval",
        prior_task_snapshot=None,
        artifact_references=[],
    )

    assert snapshot.pending_tool_calls == calls


def test_legacy_run_action_uses_the_existing_confirmation_identity():
    from argus.agent_runtime.tools.registered_backtest import approved_backtest_call

    state = _dca_state(approved=True)
    confirmation_id = "confirmation-" + fake.uuid4()
    state.structured_action.payload["confirmation_id"] = confirmation_id

    first = approved_backtest_call(state)
    replay = approved_backtest_call(state)

    assert first.call_id == confirmation_id
    assert replay.call_id == first.call_id


@pytest.mark.parametrize("explicit_final", [True, False])
def test_new_tool_answer_does_not_publish_a_carried_strategy_confirmation(explicit_final):
    from argus.agent_runtime.runtime import _public_result
    from argus.agent_runtime.state.models import ConfirmationPayload, StrategySummary

    confirmation = ConfirmationPayload(
        strategy=StrategySummary(strategy_type="buy_and_hold", asset_universe=["AAPL"])
    )
    card = ToolResultCard(
        tool_name="echo",
        call_id=fake.uuid4(),
        artifact_id=fake.uuid4(),
        card_type="test_echo",
        card_version=1,
        arguments={"value": 0},
        outcome=ToolOutcome(status="succeeded", result={"value": 0}),
        presentation=ToolCardPresentation(
            title=LocalizedText(locale_key="test.echo.title")
        ),
    )
    result = {
        "run_state": RunState(
            current_user_message=fake.sentence(),
            confirmation_payload=confirmation,
            final_response_payload={"tool_result_cards": [card]},
        ),
        "stage_outcome": "ready_to_respond",
    }
    if explicit_final:
        result["final_response_payload"] = {
            "tool_result_cards": [card.model_dump(mode="json")]
        }
    payload = _public_result(result)

    assert "confirmation_payload" not in payload


@pytest.mark.asyncio()
async def test_one_approval_cannot_dispatch_the_same_backtest_twice():
    from argus.agent_runtime.tools.registered_backtest import get_backtest_declaration

    received = []

    class BacktestTool:
        def run(self, payload):
            received.append(payload)
            return {"success": True, "payload": {"total_return": 0}}

    state = _dca_state(approved=True)
    calls = [
        ToolCall(
            tool_name="backtest",
            call_id=fake.uuid4(),
            arguments={
                "strategy": state.candidate_strategy_draft.model_dump(mode="json")
            },
        )
        for _ in range(2)
    ]
    state.tool_calls = calls
    result = await execute.execute_stage_async(
        state=state, tool=BacktestTool(), catalog=_catalog(get_backtest_declaration())
    )

    assert len(received) == 1
    assert result.outcome == "ready_for_confirmation"
    assert result.patch["tool_calls"] == calls[1:]
    assert result.patch["confirmation_payload"] is None


@pytest.mark.asyncio()
async def test_approval_restores_remaining_call_ids_from_the_task_snapshot(monkeypatch):
    from argus.agent_runtime.graph import workflow
    from argus.agent_runtime.stages.interpret_types import StageResult
    from argus.agent_runtime.state.models import TaskSnapshot, UserState

    state = _dca_state(approved=True)
    pending = [
        ToolCall(
            tool_name="backtest",
            call_id=fake.uuid4(),
            arguments={
                "strategy": state.candidate_strategy_draft.model_dump(mode="json")
            },
        ),
        _call(0),
    ]

    async def approve(**kwargs):
        return StageResult(
            outcome="approved_for_execution",
            stage_patch={"candidate_strategy_draft": state.candidate_strategy_draft},
        )

    monkeypatch.setattr(workflow, "interpret_stage_async", approve)
    result = await workflow._interpret_node_async(
        {
            "run_state": state,
            "user": UserState(user_id=fake.uuid4()),
            "latest_task_snapshot": TaskSnapshot(pending_tool_calls=pending),
        },
        structured_interpreter=None,
    )

    assert [call.call_id for call in result["run_state"].tool_calls] == [
        call.call_id for call in pending
    ]


@pytest.mark.asyncio()
async def test_actual_graph_streams_each_call_before_its_handler_finishes(monkeypatch):
    import asyncio

    from argus.agent_runtime.graph.workflow import build_workflow
    from argus.agent_runtime.runtime import stream_agent_turn_events
    from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
    from argus.agent_runtime.state.models import UserState
    from langgraph.checkpoint.memory import MemorySaver

    release = asyncio.Event()
    calls = [_call(0), _call(1)]
    interpreted = []

    async def echo(arguments: EchoArguments) -> EchoResult:
        await asyncio.wait_for(release.wait(), timeout=2)
        return EchoResult(value=arguments.value)

    class Interpreter:
        async def ainvoke(self, request):
            interpreted.append(request)
            return StructuredInterpretation(
                intent="calculate",
                task_relation="new_task",
                user_goal_summary=fake.sentence(),
                tool_calls=calls,
            )

    monkeypatch.setattr(execute, "_launch_payload", _forbid_launch)
    graph = build_workflow(
        tool=object(),
        tool_catalog=_catalog(_declaration(echo)),
        structured_interpreter=Interpreter(),
        checkpointer=MemorySaver(),
    )
    events = []
    async for event in stream_agent_turn_events(
        workflow=graph,
        user=UserState(user_id=fake.uuid4()),
        thread_id=fake.uuid4(),
        message=fake.sentence(),
    ):
        events.append(event)
        if event.get("tool_progress"):
            release.set()

    progress = [event["tool_progress"] for event in events if event.get("tool_progress")]
    assert [item["call_id"] for item in progress] == [call.call_id for call in calls]
    assert progress[0]["interpolation_args"] == {"value": 0}
    assert len(interpreted) == 1
    assert not {"confirm", "explain"}.intersection(event.get("stage") for event in events)
    final = events[-1]["payload"]["final_response_payload"]
    assert [card["call_id"] for card in final["tool_result_cards"]] == [
        call.call_id for call in calls
    ]
    assert not final.get("result_card")


@pytest.mark.asyncio()
async def test_empty_call_turn_ignores_a_carried_confirmation(monkeypatch):
    state = _dca_state(approved=True)
    state.structured_action = None
    monkeypatch.setattr(execute, "_launch_payload", _forbid_launch)

    result = await execute.execute_stage_async(state=state, tool=object())

    assert result.outcome == "ready_to_respond"
    assert result.patch["tool_call_records"] == []


@pytest.mark.parametrize("same_turn", [True, False])
def test_private_tool_effects_survive_only_the_executing_turn(same_turn):
    from argus.agent_runtime.graph.workflow import _apply_stage_result
    from argus.agent_runtime.stages.interpret_types import StageResult
    from argus.agent_runtime.state.models import UserState

    call_id = fake.uuid4()
    effect = {
        "call_id": call_id,
        "stage_patch": {"research_job_request": {"query": fake.word()}},
    }
    state = RunState(
        current_user_message=fake.sentence(),
        tool_call_records=[{"tool_name": "echo", "call_id": call_id}]
        if same_turn
        else [],
    )
    result = _apply_stage_result(
        {
            "run_state": state,
            "user": UserState(user_id=fake.uuid4()),
            "tool_effects": [effect],
        },
        StageResult(
            outcome="ready_to_respond",
            stage_patch={"assistant_response": fake.sentence()},
        ),
    )

    assert result["tool_effects"] == ([effect] if same_turn else None)


@pytest.mark.asyncio()
async def test_a_declared_confirmation_callback_owns_its_tool_policy():
    from argus.domain.tool_declaration import ToolPolicy

    def echo(arguments: EchoArguments) -> EchoResult:
        raise AssertionError("An unapproved declared call cannot run")

    def confirm(arguments: EchoArguments, *, context) -> StageResult:
        assert arguments.value == 0
        return StageResult(outcome="await_approval")

    declaration = _declaration(
        echo,
        policy=ToolPolicy(execution="workflow", confirmation="required"),
        confirmation_handler=confirm,
    )
    result = await execute.execute_stage_async(
        state=RunState(current_user_message=fake.sentence(), tool_calls=[_call(0)]),
        tool=object(),
        catalog=_catalog(declaration),
    )

    assert result.outcome == "await_approval"
    assert result.patch["tool_call_records"] == []


@pytest.mark.asyncio()
async def test_trusted_call_identity_reaches_sync_adapter_then_is_cleared():
    from argus.agent_runtime.stages import tool_execution
    from argus.agent_runtime.tools.registered_backtest import get_backtest_declaration

    observed = []

    class BacktestTool:
        def run(self, payload):
            context = tool_execution.current_tool_execution_context()
            observed.append((context.call.call_id, context.artifact_id))
            return {"success": True, "payload": {"total_return": 0}}

    result = await execute.execute_stage_async(
        state=_dca_state(approved=True),
        tool=BacktestTool(),
        catalog=_catalog(get_backtest_declaration()),
    )

    card = result.patch["final_response_payload"]["tool_result_cards"][0]
    assert observed == [(card["call_id"], card["artifact_id"])]
    assert tool_execution.current_tool_execution_context() is None


@pytest.mark.asyncio()
async def test_replayed_job_preserves_the_durable_call_and_card_identity():
    from argus.agent_runtime.stages.tool_execution import current_tool_execution_context
    from argus.agent_runtime.tools.registered_backtest import get_backtest_declaration

    original_call_id, original_artifact_id = fake.uuid4(), fake.uuid4()

    class ReplayedTool:
        def run(self, payload):
            context = current_tool_execution_context()
            context.call = context.call.model_copy(update={"call_id": original_call_id})
            context.artifact_id = original_artifact_id
            return {
                "success": True,
                "payload": {
                    "backtest_job": {
                        "id": fake.uuid4(),
                        "conversation_id": fake.uuid4(),
                        "status": "queued",
                    }
                },
            }

    result = await execute.execute_stage_async(
        state=_dca_state(approved=True),
        tool=ReplayedTool(),
        catalog=_catalog(get_backtest_declaration()),
    )

    card = result.patch["final_response_payload"]["tool_result_cards"][0]
    assert card["call_id"] == original_call_id
    assert card["artifact_id"] == original_artifact_id
    assert result.patch["tool_call_records"][0]["call_id"] == original_call_id
    assert result.patch["tool_effects"][0]["call_id"] == original_call_id


@pytest.mark.parametrize("settlement", ["pending", "unavailable", "succeeded"])
@pytest.mark.parametrize("trailing_pending", [False, True])
def test_only_a_completed_tool_answer_supersedes_a_failed_action(
    settlement, trailing_pending
):
    from argus.agent_runtime.graph.workflow import _current_failed_action_reference
    from argus.agent_runtime.state.models import ArtifactReference
    from argus.domain.tool_contracts import ToolFailure

    call = _call(0)
    outcome = (
        ToolOutcome(status="unavailable", failure=ToolFailure(code="test_unavailable"))
        if settlement == "unavailable"
        else ToolOutcome(status="succeeded", result={"value": 0})
    )
    presentation = _presentation(EchoArguments(value=0), outcome)
    if settlement == "pending":
        presentation = presentation.model_copy(update={"answer": None})
    card = ToolResultCard(
        tool_name=call.tool_name,
        call_id=call.call_id,
        artifact_id=fake.uuid4(),
        card_type="test_echo",
        card_version=1,
        arguments=call.arguments,
        outcome=outcome,
        presentation=presentation,
    )
    failed = ArtifactReference(artifact_kind="failed_action", artifact_id=fake.uuid4())
    references = [
        failed,
        ArtifactReference(
            artifact_kind="tool_result",
            artifact_id=card.artifact_id,
            metadata=card.model_dump(mode="json"),
        ),
    ]
    if trailing_pending:
        pending = card.model_copy(
            update={
                "call_id": fake.uuid4(),
                "artifact_id": fake.uuid4(),
                "presentation": presentation.model_copy(update={"answer": None}),
            }
        )
        references.append(
            ArtifactReference(
                artifact_kind="tool_result",
                artifact_id=pending.artifact_id,
                metadata=pending.model_dump(mode="json"),
            )
        )
    current = _current_failed_action_reference(
        latest_failed_action_reference=failed,
        prior_task_snapshot=None,
        artifact_references=references,
    )
    assert current == (None if settlement == "succeeded" else failed)
