"""The measurement gate observes declared calls, including their real handoff."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.domain.tool_contracts import ToolCall
from faker import Faker

from tests.agent_runtime.test_registered_tool_execution import (
    EchoArguments,
    EchoResult,
    _catalog,
    _declaration,
)
from tests.evals import measurement_eval_harness as harness

fake = Faker()


def _case(*, expected):
    return harness.EvalCase(
        id=fake.uuid4(),
        category="ordinary_conversation",
        prompt=fake.sentence(),
        user_language="en",
        ui_language="en",
        expected=harness.TypedExpectations(**expected),
    )


def _interpreter(monkeypatch, calls, *, intent="calculate"):
    class Interpreter:
        async def ainvoke(self, request):
            return StructuredInterpretation(
                uses_tool_catalog=True,
                intent=intent,
                task_relation="new_task",
                user_goal_summary=request.current_user_message,
                semantic_turn_act="educational_question",
                tool_calls=calls,
                assistant_response="A measured response.",
            )

    monkeypatch.setattr(
        harness, "OpenRouterStructuredInterpreter", lambda **_: Interpreter()
    )


@pytest.mark.parametrize("names", [("echo",), ("echo", "echo"), ("echo", "identity")])
def test_measurement_dispatches_every_call_and_retains_raw_trace(monkeypatch, names):
    from argus.domain import capability_registry

    observed = []

    def echo(arguments: EchoArguments) -> EchoResult:
        observed.append(arguments.value)
        return EchoResult(value=arguments.value)

    catalog = _catalog(*(_declaration(echo, name=name) for name in dict.fromkeys(names)))
    monkeypatch.setattr(capability_registry, "get_tool_catalog", lambda **_: catalog)
    calls = [
        ToolCall(tool_name=name, call_id=fake.uuid4(), arguments={"value": index})
        for index, name in enumerate(names)
    ]
    _interpreter(monkeypatch, calls)
    case = _case(
        expected={
            "intent": "calculate",
            "capability_verdict": "answer_only",
            "stage_outcomes": ("ready_to_respond",),
            "tool_dispatch": True,
        },
    )

    result = harness.run_eval_case(case, run_prose_judge=False)

    assert observed == list(range(len(calls)))
    assert result["failed_checks"] == []
    outcome = result["typed_outcome"]
    assert outcome["tool_calls"] == [call.model_dump(mode="json") for call in calls]
    assert [record["call_id"] for record in outcome["tool_call_records"]] == [
        call.call_id for call in calls
    ]
    assert outcome["stage_outcomes"] == ["approved_for_execution", "ready_to_respond"]
    assert outcome["acceptance_stage_outcomes"] == ["ready_to_respond"]
    assert outcome["execution_trace"] == [
        {"stage": "interpret", "outcome": "approved_for_execution"},
        {"stage": "execute", "outcome": "ready_to_respond"},
    ]
    assert len(outcome["tool_result_cards"]) == len(calls)


def test_measurement_backtest_uses_real_confirmation_without_execution(monkeypatch):
    original = next(
        case
        for case in harness.load_eval_cases()
        if case.id == "action_chip_run_visible_confirmation_aapl"
    )
    strategy = original.confirmation_payload["strategy"]
    calls = [
        ToolCall(
            tool_name="backtest", call_id=fake.uuid4(), arguments={"strategy": strategy}
        )
    ]
    _interpreter(monkeypatch, calls)
    case = replace(
        original,
        action=None,
        snapshot=None,
        confirmation_payload=None,
        prompt=fake.sentence(),
        expected=replace(
            original.expected,
            intent="calculate",
            capability_verdict="executable",
            stage_outcomes=("ready_for_confirmation", "await_approval"),
        ),
    )

    result = harness.run_eval_case(case, run_prose_judge=False)

    assert result["failed_checks"] == []
    outcome = result["typed_outcome"]
    assert outcome["stage_outcomes"] == [
        "approved_for_execution",
        "ready_for_confirmation",
        "await_approval",
    ]
    assert outcome["tool_call_records"] == []
    assert outcome["offered"]["launch_payload"]["symbols"] == strategy["asset_universe"]


def test_zero_calls_never_claim_registered_dispatch(monkeypatch):
    _interpreter(monkeypatch, [], intent="explain")
    case = _case(expected={"intent": "explain", "capability_verdict": "answer_only"})

    result = harness.run_eval_case(case, run_prose_judge=False)

    assert result["failed_checks"] == []
    assert result["typed_outcome"]["tool_calls"] == []
    assert result["typed_outcome"]["acceptance_stage_outcomes"] == ["ready_to_respond"]
    assert result["typed_outcome"]["execution_trace"] == [
        {"stage": "interpret", "outcome": "ready_to_respond"},
    ]


@pytest.mark.parametrize("legacy", ["strategy_drafting", "backtest_execution"])
def test_legacy_fixture_intents_compare_with_canonical_outcomes(legacy):
    case = _case(expected={"intent": legacy, "capability_verdict": "executable"})

    assert (
        harness.typed_expectation_failures(
            case=case, outcome={"intent": "calculate", "capability_verdict": "executable"}
        )
        == []
    )


def test_missing_dispatch_cannot_remove_an_unwanted_stage():
    outcome = harness._typed_outcome(
        case=_case(expected={"intent": "calculate", "capability_verdict": "executable"}),
        interpret_result=SimpleNamespace(
            outcome="approved_for_execution", patch={"intent": "calculate"}
        ),
        confirm_result=None,
        clarify_result=None,
    )

    assert outcome["acceptance_stage_outcomes"] == ["approved_for_execution"]


@pytest.mark.parametrize("status", ["invalid", "bounded", "unavailable"])
def test_measurement_never_scores_a_failed_call_as_an_answer(monkeypatch, status):
    from argus.domain import capability_registry
    from argus.domain.tool_declaration import ToolInvocationError

    def bounded(arguments: EchoArguments) -> EchoResult:
        raise ToolInvocationError(status, code="test_failure")

    monkeypatch.setattr(
        capability_registry,
        "get_tool_catalog",
        lambda **_: _catalog(_declaration(bounded)),
    )
    calls = [ToolCall(tool_name="echo", call_id=fake.uuid4(), arguments={"value": 0})]
    _interpreter(monkeypatch, calls)
    case = _case(
        expected={
            "intent": "calculate",
            "capability_verdict": "answer_only",
            "tool_dispatch": True,
        }
    )

    result = harness.run_eval_case(case, run_prose_judge=False)

    assert result["status"] == "failed"
    assert any(check.startswith("tool_dispatch:") for check in result["failed_checks"])
    assert result["typed_outcome"]["tool_call_records"][0]["outcome"] == status
    assert (
        result["typed_outcome"]["tool_result_cards"][0]["presentation"]["answer"] is None
    )


def test_followup_dispatch_is_in_the_same_measurement_trace(monkeypatch):
    from argus.domain import capability_registry

    def echo(arguments: EchoArguments) -> EchoResult:
        return EchoResult(value=arguments.value)

    monkeypatch.setattr(
        capability_registry, "get_tool_catalog", lambda **_: _catalog(_declaration(echo))
    )
    call = ToolCall(tool_name="echo", call_id=fake.uuid4(), arguments={"value": 0})
    turns = iter(
        [
            SimpleNamespace(outcome="needs_clarification", patch={}),
            SimpleNamespace(
                outcome="approved_for_execution",
                patch={
                    "intent": "calculate",
                    "tool_calls": [call.model_dump()],
                },
            ),
        ]
    )
    monkeypatch.setattr(harness, "interpret_stage", lambda **_: next(turns))
    monkeypatch.setattr(
        harness,
        "clarify_stage",
        lambda **_: SimpleNamespace(
            outcome="await_user_reply",
            patch={"assistant_prompt": fake.sentence()},
        ),
    )
    case = replace(
        _case(
            expected={
                "intent": "calculate",
                "capability_verdict": "answer_only",
                "tool_dispatch": True,
                "stage_outcomes": (
                    "needs_clarification",
                    "await_user_reply",
                    "ready_to_respond",
                ),
            }
        ),
        followup_prompt=fake.sentence(),
    )

    result = harness.run_eval_case(case, run_prose_judge=False)

    assert result["failed_checks"] == []
    assert result["typed_outcome"]["stage_outcomes"] == [
        "needs_clarification",
        "await_user_reply",
        "approved_for_execution",
        "ready_to_respond",
    ]
    assert result["typed_outcome"]["tool_calls"] == [call.model_dump()]


@pytest.mark.parametrize(
    "field,value",
    [
        ("relationship", "peer"),
        ("anchor_symbols", ["NVDA"]),
        ("asset_class_hint", "crypto"),
        ("needs_current_facts", False),
        ("category_description", "unrelated category"),
    ],
)
def test_discovery_argument_migration_keeps_each_original_fact_check(field, value):
    expected = {
        "relationship": "comparison",
        "anchor_symbols": ["COST"],
        "asset_class_hint": "equity",
        "needs_current_facts": True,
        "category_description_includes_any": ["retail"],
    }
    arguments = {
        "relationship": expected["relationship"],
        "anchor_symbols": expected["anchor_symbols"],
        "asset_class_hint": expected["asset_class_hint"],
        "needs_current_facts": True,
        "category_description": "retail peers",
    }
    failures = []
    harness._compare_asset_discovery(expected, [arguments], failures)
    assert failures == []

    harness._compare_asset_discovery(expected, [{**arguments, field: value}], failures)

    assert len(failures) == 1
    assert field in failures[0]
