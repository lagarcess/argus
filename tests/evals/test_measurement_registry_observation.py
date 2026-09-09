"""Observe actual stage state and delivered answers without classifying questions."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
from argus.agent_runtime.stages.interpret_types import StageResult
from argus.domain.tool_contracts import (
    LocalizedText,
    ToolCall,
    ToolCardPresentation,
    ToolFact,
    ToolOutcome,
    ToolResultCard,
)
from faker import Faker

from tests.agent_runtime.test_registered_tool_execution import (
    EchoArguments,
    EchoResult,
    _catalog,
    _declaration,
)
from tests.evals import measurement_eval_harness as harness
from tests.evals.test_measurement_registry_dispatch import _case, _interpreter

fake = Faker()


@pytest.mark.parametrize("followup", [False, True])
@pytest.mark.parametrize("declared_dispatch", [False, True])
def test_clarification_readiness_reaches_real_confirmation_in_chronological_order(
    monkeypatch, followup, declared_dispatch
):
    from argus.agent_runtime.graph import workflow
    from argus.agent_runtime.stages import confirm as confirmation_stage
    from argus.domain.backtesting.confirmation_preflight import (
        ConfirmationLaunchPreflight,
    )

    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
    monkeypatch.setattr(confirmation_stage, "_market_clock_for_strategy", lambda _: None)
    original = next(
        case
        for case in harness.load_eval_cases()
        if case.id == "dca_capital_semantics_stated_seed_reaches_ready_to_run_issue_455"
    )
    expected = original.expected

    def coverage(payload):
        # Authored provider boundary: January 1 is not an equity trading session.
        return ConfirmationLaunchPreflight(
            outcome="ready_to_confirm",
            launch_payload={
                **payload,
                "date_range": expected.effective_date_range,
                "coverage_preflight": {
                    "requested_date_range": expected.date_range,
                    "effective_date_range": expected.effective_date_range,
                    "adjustment_reason": expected.adjustment_reason,
                },
            },
        )

    monkeypatch.setattr(confirmation_stage, "prepare_confirmation_launch", coverage)
    strategy = {
        "strategy_type": expected.strategy_type,
        "asset_universe": list(expected.assets),
        "asset_class": expected.asset_class,
        "capital_amount": expected.capital_amount,
        "cadence": expected.contribution_period,
        "date_range": expected.date_range,
        "extra_parameters": {
            "initial_capital": expected.starting_capital,
            "recurring_contribution": expected.recurring_contribution,
            "field_provenance": {
                "initial_capital": "explicit_user",
                "recurring_contribution": "explicit_user",
                "cadence": "explicit_user",
            },
        },
    }
    prepared = StageResult(
        outcome="needs_clarification",
        stage_patch={
            "intent": "calculate",
            "candidate_strategy_draft": strategy,
            "missing_required_fields": [],
            "optional_parameter_status": {"initial_capital": expected.starting_capital},
        },
    )
    interpreted = prepared
    if declared_dispatch:
        interpreted = StageResult(
            outcome="approved_for_execution",
            stage_patch={
                "intent": "calculate",
                "tool_calls": [
                    ToolCall(
                        tool_name="backtest",
                        call_id=fake.uuid4(),
                        arguments={"strategy": strategy},
                    )
                ],
            },
        )
    turns = [interpreted]
    prefix = []
    if followup:
        turns.insert(
            0,
            StageResult(
                outcome="needs_clarification",
                stage_patch={"missing_required_fields": ["asset_universe"]},
            ),
        )
        prefix = [
            {"stage": "interpret", "outcome": "needs_clarification"},
            {"stage": "clarify", "outcome": "await_user_reply"},
        ]
    reads = iter(turns)
    monkeypatch.setattr(harness, "interpret_stage", lambda **_: next(reads))
    monkeypatch.setattr(
        harness,
        "dispatch_requested_calls",
        lambda **kwargs: prepared
        if kwargs["interpreted"].outcome == "approved_for_execution"
        else None,
    )
    actual_clarify, actual_confirm = harness.clarify_stage, harness.confirm_stage
    confirmed_states, routed_outcomes = [], []
    actual_route = workflow._route_from_stage_outcome

    def clarify(**kwargs):
        result = actual_clarify(**kwargs)
        if result.outcome == "ready_for_confirmation":
            result.stage_patch["intent"] = "explain"
        return result

    def confirm(**kwargs):
        confirmed_states.append(kwargs["state"])
        result = actual_confirm(**kwargs)
        result.stage_patch["intent"] = "calculate"
        return result

    def route(state):
        routed_outcomes.append(str(state["stage_outcome"]))
        return actual_route(state)

    monkeypatch.setattr(harness, "clarify_stage", clarify)
    monkeypatch.setattr(harness, "confirm_stage", confirm)
    monkeypatch.setattr(workflow, "_route_from_stage_outcome", route)
    expected_milestones = tuple(entry["outcome"] for entry in prefix) + (
        "needs_clarification",
        "ready_for_confirmation",
        "await_approval",
    )
    case = replace(
        original,
        expected=replace(expected, stage_outcomes=expected_milestones),
        followup_prompt=original.prompt if followup else None,
        degraded_mode={"clarifier": "offline"},
    )

    result = harness.run_eval_case(case, run_prose_judge=False)

    assert len(confirmed_states) == 1
    assert "ready_for_confirmation" in routed_outcomes
    assert result["failed_checks"] == [], result["failed_checks"]
    outcome = result["typed_outcome"]
    raw = [
        {"stage": "interpret", "outcome": interpreted.outcome},
        *(
            [{"stage": "execute", "outcome": prepared.outcome}]
            if declared_dispatch
            else []
        ),
        {"stage": "clarify", "outcome": "ready_for_confirmation"},
        {"stage": "confirm", "outcome": "await_approval"},
    ]
    assert outcome["execution_trace"] == prefix + raw
    assert outcome["acceptance_stage_outcomes"] == list(expected_milestones)
    assert outcome["intent"] == "calculate"
    assert outcome["starting_capital"] == expected.starting_capital
    assert outcome["recurring_contribution"] == expected.recurring_contribution
    assert outcome["offered"]["launch_payload"]
    # Following the real edge does not erase an unexpected clarification event.
    unchanged_fixture = replace(case, expected=expected)
    assert any(
        failure.startswith("stage_outcomes:")
        for failure in harness.typed_expectation_failures(
            case=unchanged_fixture, outcome=outcome
        )
    )


def test_a_real_clarification_blocker_stops_before_confirmation(monkeypatch):
    monkeypatch.setattr(
        harness,
        "interpret_stage",
        lambda **_: StageResult(
            outcome="needs_clarification",
            stage_patch={
                "intent": "calculate",
                "missing_required_fields": ["asset_universe"],
            },
        ),
    )
    monkeypatch.setattr(
        harness,
        "confirm_stage",
        lambda **_: (_ for _ in ()).throw(AssertionError("A real blocker must stop")),
    )
    case = replace(
        _case(
            expected={
                "intent": "calculate",
                "capability_verdict": "needs_clarification",
                "stage_outcomes": ("needs_clarification", "await_user_reply"),
                "offered": {"response": True},
            }
        ),
        degraded_mode={"clarifier": "offline"},
    )

    result = harness.run_eval_case(case, run_prose_judge=False)

    assert result["failed_checks"] == []
    assert result["typed_outcome"]["offered"]["launch_payload"] == {}


def test_runtime_terminal_route_does_not_invent_a_clarification(monkeypatch):
    monkeypatch.setattr(
        harness,
        "interpret_stage",
        lambda **_: StageResult(
            outcome="needs_clarification",
            stage_patch={
                "intent": "cannot",
                "failure_classification": "unsupported_capability",
            },
        ),
    )
    monkeypatch.setattr(
        harness,
        "clarify_stage",
        lambda **_: (_ for _ in ()).throw(AssertionError("Runtime chose to end")),
    )

    result = harness.run_eval_case(
        _case(expected={"intent": "cannot", "capability_verdict": "needs_clarification"}),
        run_prose_judge=False,
    )

    assert result["typed_outcome"]["execution_trace"] == [
        {"stage": "interpret", "outcome": "needs_clarification"}
    ]


def test_repeated_runtime_state_stops_before_repeating_stage_work(monkeypatch):
    observed = []
    monkeypatch.setattr(
        harness,
        "interpret_stage",
        lambda **_: StageResult(outcome="needs_clarification"),
    )

    def stage(name, outcome):
        def invoke(**_):
            observed.append(name)
            return StageResult(outcome=outcome)

        return invoke

    monkeypatch.setattr(
        harness, "clarify_stage", stage("clarify", "ready_for_confirmation")
    )
    monkeypatch.setattr(harness, "confirm_stage", stage("confirm", "needs_clarification"))

    with pytest.raises(RuntimeError, match="repeated runtime route and state") as error:
        harness.run_eval_case(
            _case(expected={"intent": "calculate", "capability_verdict": "executable"}),
            run_prose_judge=False,
        )

    assert observed == ["clarify", "confirm"]
    assert "('confirm', 'needs_clarification')" in str(error.value)


def test_revisited_confirmation_keeps_each_event_and_latest_patch(monkeypatch):
    from argus.agent_runtime.state.models import RunState

    from tests.evals.measurement_registry import continue_turn_stages

    interpreted = StageResult(outcome="ready_for_confirmation")
    amount = fake.pyfloat(min_value=1, max_value=10000, right_digits=2)

    def confirm(*, state, **_):
        if state.candidate_strategy_draft.capital_amount is None:
            return StageResult(
                outcome="needs_clarification",
                stage_patch={"missing_required_fields": ["capital_amount"]},
            )
        return StageResult(
            outcome="await_approval",
            stage_patch={
                "intent": "calculate",
                "confirmation_payload": {"validation": {"executable": True}},
            },
        )

    def clarify(*, state, **_):
        return StageResult(
            outcome="ready_for_confirmation",
            stage_patch={
                "intent": "explain",
                "candidate_strategy_draft": state.candidate_strategy_draft.model_copy(
                    update={"capital_amount": amount}
                ).model_dump(mode="python"),
                "missing_required_fields": [],
            },
        )

    stages = continue_turn_stages(
        state=RunState(current_user_message=fake.sentence()),
        interpreted=interpreted,
        dispatched=None,
        contract=harness.build_default_capability_contract(),
        language="en",
        clarification_generator=None,
        confirm=confirm,
        clarify=clarify,
    )
    outcome = harness._typed_outcome(
        case=_case(expected={"intent": "calculate", "capability_verdict": "executable"}),
        interpret_result=interpreted,
        confirm_result=stages[-1][1],
        clarify_result=stages[-2][1],
        stage_results=stages,
    )

    assert outcome["execution_trace"] == [
        {"stage": "interpret", "outcome": "ready_for_confirmation"},
        {"stage": "confirm", "outcome": "needs_clarification"},
        {"stage": "clarify", "outcome": "ready_for_confirmation"},
        {"stage": "confirm", "outcome": "await_approval"},
    ]
    assert outcome["intent"] == "calculate"
    assert outcome["capability_verdict"] == "executable"


@pytest.mark.parametrize("followup", [False, True])
def test_dispatch_receives_the_same_trusted_context_as_interpret(monkeypatch, followup):
    from argus.domain import capability_registry

    interpreted_contexts, executed_contexts = [], []

    def echo(arguments: EchoArguments, *, context) -> EchoResult:
        executed_contexts.append(context)
        return EchoResult(value=arguments.value)

    monkeypatch.setattr(
        capability_registry, "get_tool_catalog", lambda **_: _catalog(_declaration(echo))
    )
    call = ToolCall(tool_name="echo", call_id=fake.uuid4(), arguments={"value": 0})

    def interpret(**context):
        interpreted_contexts.append(context)
        if followup and len(interpreted_contexts) == 1:
            return StageResult(outcome="needs_clarification", stage_patch={})
        return StageResult(
            outcome="approved_for_execution",
            stage_patch={"intent": "calculate", "tool_calls": [call]},
        )

    monkeypatch.setattr(harness, "interpret_stage", interpret)
    monkeypatch.setattr(
        harness,
        "clarify_stage",
        lambda **_: StageResult(
            outcome="await_user_reply",
            stage_patch={
                "assistant_prompt": fake.sentence(),
                "requested_field": "date_range",
                "missing_required_fields": ["date_range"],
            },
        ),
    )
    snapshot = next(
        item.snapshot
        for item in harness.load_eval_cases()
        if item.snapshot and item.snapshot.latest_backtest_result_reference
    )
    case = replace(
        _case(
            expected={
                "intent": "calculate",
                "capability_verdict": "answer_only",
                "tool_dispatch": True,
            }
        ),
        snapshot=snapshot,
        thread_metadata={"fixture_context_marker": fake.uuid4()},
        followup_prompt=fake.sentence() if followup else None,
    )

    result = harness.run_eval_case(case, run_prose_judge=False)

    assert result["failed_checks"] == []
    assert len(executed_contexts) == 1
    interpreted = interpreted_contexts[-1]
    executed = executed_contexts[0]
    assert (
        executed.latest_task_snapshot is interpreted["latest_task_snapshot"] is snapshot
    )
    assert executed.selected_thread_metadata is interpreted["selected_thread_metadata"]
    if followup:
        assert executed.selected_thread_metadata["requested_field"] == "date_range"
        assert (
            executed.selected_thread_metadata["last_stage_outcome"] == "await_user_reply"
        )
    else:
        assert (
            executed.selected_thread_metadata["fixture_context_marker"]
            == case.thread_metadata["fixture_context_marker"]
        )


@pytest.mark.parametrize("primary_intent", ["explain", "calculate", "follow_up"])
def test_measurement_reads_post_dispatch_intent_and_retains_primary(
    monkeypatch, primary_intent
):
    from argus.domain import capability_registry

    observed = []

    def echo(arguments: EchoArguments, *, context) -> EchoResult:
        observed.append(arguments.value)
        context.stage_result = StageResult(
            outcome="ready_to_respond", stage_patch={"intent": "follow_up"}
        )
        return EchoResult(value=arguments.value)

    monkeypatch.setattr(
        capability_registry, "get_tool_catalog", lambda **_: _catalog(_declaration(echo))
    )
    call = ToolCall(tool_name="echo", call_id=fake.uuid4(), arguments={"value": 0})
    _interpreter(monkeypatch, [call], intent=primary_intent)
    case = _case(
        expected={
            "intent": "follow_up",
            "capability_verdict": "answer_only",
            "tool_dispatch": True,
        }
    )

    result = harness.run_eval_case(case, run_prose_judge=False)

    assert observed == [0]
    assert result["failed_checks"] == []
    assert result["typed_outcome"]["intent"] == "follow_up"
    assert result["typed_outcome"]["primary_intent"] == primary_intent


def test_primary_explanation_cannot_pass_when_requested_dispatch_is_missing(monkeypatch):
    call = ToolCall(tool_name="echo", call_id=fake.uuid4(), arguments={"value": 0})
    _interpreter(monkeypatch, [call], intent="explain")
    monkeypatch.setattr(harness, "dispatch_requested_calls", lambda **_: None)
    case = _case(
        expected={
            "intent": "follow_up",
            "capability_verdict": "answer_only",
            "tool_dispatch": True,
        }
    )

    result = harness.run_eval_case(case, run_prose_judge=False)

    assert result["status"] == "failed"
    assert any(check.startswith("tool_dispatch:") for check in result["failed_checks"])
    assert result["typed_outcome"]["intent"] == "explain"
    assert result["typed_outcome"]["primary_intent"] == "explain"
    assert result["typed_outcome"]["stage_outcomes"] == ["approved_for_execution"]


@pytest.mark.parametrize(
    "confirmation_intent,clarification_intent,expected_intent",
    [
        (None, None, "follow_up"),
        ("cannot", None, "cannot"),
        ("cannot", "explain", "explain"),
    ],
)
def test_intent_uses_ordered_stage_patch_precedence(
    confirmation_intent, clarification_intent, expected_intent
):
    def stage(outcome, intent):
        return SimpleNamespace(
            outcome=outcome, patch={} if intent is None else {"intent": intent}
        )

    result = harness._typed_outcome(
        case=_case(
            expected={"intent": expected_intent, "capability_verdict": "answer_only"}
        ),
        interpret_result=stage("approved_for_execution", "calculate"),
        dispatch_result=stage("ready_for_confirmation", "follow_up"),
        confirm_result=stage("needs_clarification", confirmation_intent),
        clarify_result=stage("await_user_reply", clarification_intent),
    )

    assert result["intent"] == expected_intent
    assert result["primary_intent"] == "calculate"


@pytest.mark.parametrize("declared_call", [False, True])
@pytest.mark.parametrize("expected_handoff", [False, True])
def test_verified_confirmation_clarification_handoff_compares_at_its_owner(
    declared_call, expected_handoff
):
    call = ToolCall(tool_name="backtest", call_id=fake.uuid4(), arguments={})
    interpreted = SimpleNamespace(
        outcome="approved_for_execution" if declared_call else "ready_for_confirmation",
        patch={"intent": "calculate", "tool_calls": [call] if declared_call else []},
    )
    dispatched = (
        SimpleNamespace(outcome="ready_for_confirmation", patch={})
        if declared_call
        else None
    )
    confirmed = SimpleNamespace(outcome="needs_clarification", patch={})
    clarified = SimpleNamespace(outcome="await_user_reply", patch={})
    expected = ["needs_clarification", "await_user_reply"]
    if expected_handoff:
        expected.insert(0, "ready_for_confirmation")
    case = _case(
        expected={
            "intent": "calculate",
            "capability_verdict": "needs_clarification",
            "stage_outcomes": tuple(expected),
        }
    )

    outcome = harness._typed_outcome(
        case=case,
        interpret_result=interpreted,
        dispatch_result=dispatched,
        confirm_result=confirmed,
        clarify_result=clarified,
    )

    assert harness.typed_expectation_failures(case=case, outcome=outcome) == []
    assert outcome["acceptance_stage_outcomes"] == [
        "needs_clarification",
        "await_user_reply",
    ]
    assert outcome["execution_trace"][-2:] == [
        {"stage": "confirm", "outcome": "needs_clarification"},
        {"stage": "clarify", "outcome": "await_user_reply"},
    ]
    assert "ready_for_confirmation" in outcome["stage_outcomes"]


@pytest.mark.parametrize("missing_stage", ["confirm", "clarify"])
def test_handoff_projection_cannot_hide_missing_clarification_stages(missing_stage):
    case = _case(
        expected={
            "intent": "calculate",
            "capability_verdict": "needs_clarification",
            "stage_outcomes": ("needs_clarification", "await_user_reply"),
        }
    )
    result = harness._typed_outcome(
        case=case,
        interpret_result=SimpleNamespace(
            outcome="ready_for_confirmation", patch={"intent": "calculate"}
        ),
        confirm_result=None
        if missing_stage == "confirm"
        else SimpleNamespace(outcome="needs_clarification", patch={}),
        clarify_result=None
        if missing_stage == "clarify"
        else SimpleNamespace(outcome="await_user_reply", patch={}),
    )

    failures = harness.typed_expectation_failures(case=case, outcome=result)

    assert any(check.startswith("stage_outcomes:") for check in failures)


def _delivered_call(*, completed):
    call = ToolCall(
        tool_name="synthetic_measured_call", call_id=fake.uuid4(), arguments={}
    )
    returned = ToolOutcome(
        status="succeeded", result={"value": 0} if completed else {"status": "pending"}
    )
    card = ToolResultCard(
        artifact_id=fake.uuid4(),
        call_id=call.call_id,
        tool_name=call.tool_name,
        arguments=call.arguments,
        card_type="synthetic_measured_result",
        card_version=1,
        outcome=returned,
        presentation=ToolCardPresentation(
            title=LocalizedText(locale_key="test.echo.title"),
            answer=ToolFact(
                name="value", label=LocalizedText(locale_key="test.echo.value"), value=0
            )
            if completed
            else None,
        ),
    )
    return {
        "tool_calls": [call.model_dump(mode="json")],
        "tool_call_records": [
            {
                "call_id": call.call_id,
                "outcome": "succeeded",
                "tool_outcome": returned.model_dump(mode="json"),
            }
        ],
        "tool_result_cards": [card.model_dump(mode="json")],
    }


@pytest.mark.parametrize("completed", [False, True])
def test_successful_queue_is_not_a_completed_answer(completed):
    case = _case(
        expected={
            "intent": "follow_up",
            "capability_verdict": "answer_only",
            "tool_dispatch": True,
        }
    )
    outcome = {
        "intent": "follow_up",
        "capability_verdict": "answer_only",
        **_delivered_call(completed=completed),
    }

    failures = harness.typed_expectation_failures(case=case, outcome=outcome)

    assert bool(failures) is not completed
    assert all(check.startswith("tool_dispatch:") for check in failures)


@pytest.mark.parametrize("narrative", ["present", None, "", " \n "])
def test_actual_research_presenter_can_deliver_narrative_without_a_numeric_headline(
    narrative,
):
    from argus.agent_runtime.research_tools import (
        ResearchArguments,
        ResearchToolResult,
        research_card_presentation,
    )
    from argus.domain.research.contracts import ResearchSource

    text = fake.paragraph() if narrative == "present" else narrative
    returned = ToolOutcome(
        status="succeeded",
        result=ResearchToolResult(
            answer=text,
            sources=(ResearchSource(url=fake.url(), title=fake.sentence()),),
        ).model_dump(mode="json"),
    )
    presentation = research_card_presentation(
        ResearchArguments(request=fake.sentence()), returned
    )
    assert presentation.answer is None
    assert presentation.narrative == text
    evidence = _delivered_call(completed=False)
    evidence["tool_call_records"][0]["tool_outcome"] = returned.model_dump(mode="json")
    evidence["tool_result_cards"][0].update(
        outcome=returned.model_dump(mode="json"),
        presentation=presentation.model_dump(mode="json"),
    )
    case = _case(
        expected={
            "intent": "follow_up",
            "capability_verdict": "answer_only",
            "tool_dispatch": True,
        }
    )

    failures = harness.typed_expectation_failures(
        case=case,
        outcome={"intent": "follow_up", "capability_verdict": "answer_only", **evidence},
    )

    assert bool(failures) is (narrative != "present")
    assert all(check.startswith("tool_dispatch:") for check in failures)


def test_a_completed_answer_can_accompany_an_honest_pending_call():
    case = _case(
        expected={
            "intent": "follow_up",
            "capability_verdict": "answer_only",
            "tool_dispatch": True,
        }
    )
    completed, pending = _delivered_call(completed=True), _delivered_call(completed=False)
    outcome = {
        "intent": "follow_up",
        "capability_verdict": "answer_only",
        **{key: completed[key] + pending[key] for key in completed},
    }

    assert harness.typed_expectation_failures(case=case, outcome=outcome) == []


def test_a_queue_only_contract_does_not_demand_a_completed_answer():
    case = _case(
        expected={
            "intent": "follow_up",
            "capability_verdict": "approved_for_execution",
            "tool_dispatch": True,
        }
    )
    outcome = {
        "intent": "follow_up",
        "capability_verdict": "approved_for_execution",
        **_delivered_call(completed=False),
    }

    assert harness.typed_expectation_failures(case=case, outcome=outcome) == []


@pytest.mark.parametrize(
    "mutation", ["missing_card", "unrelated_card", "different_result"]
)
def test_answer_required_dispatch_needs_the_answer_from_its_actual_call(mutation):
    case = _case(
        expected={
            "intent": "follow_up",
            "capability_verdict": "answer_only",
            "tool_dispatch": True,
        }
    )
    evidence = _delivered_call(completed=True)
    if mutation == "missing_card":
        evidence["tool_result_cards"] = []
    elif mutation == "unrelated_card":
        evidence["tool_result_cards"][0]["call_id"] = fake.uuid4()
    else:
        evidence["tool_result_cards"][0]["outcome"]["result"]["value"] = 1

    failures = harness.typed_expectation_failures(
        case=case,
        outcome={"intent": "follow_up", "capability_verdict": "answer_only", **evidence},
    )

    assert any(check.startswith("tool_dispatch:") for check in failures)


def test_research_fixtures_retain_the_original_canonical_effective_intents():
    cases = harness.load_eval_cases()
    discovery = [case for case in cases if case.expected.asset_discovery]
    assert len(discovery) == 9
    assert all(case.expected.intent == "follow_up" for case in discovery)
    macro = next(
        case for case in cases if case.id == "ordinary_conversation_macro_curiosity_en"
    )
    assert macro.expected.intent == ("follow_up", "explain", "cannot")
    assert all(case.expected.tool_dispatch is True for case in [*discovery, macro])


def test_execution_evidence_retains_only_reported_per_call_research_usage():
    from tests.evals.measurement_registry import measurement_execution_evidence

    amounts = [None, 0, fake.pyfloat(min_value=0.01, max_value=1)]
    calls = [
        ToolCall(tool_name="balanced_lookup", call_id=fake.uuid4(), arguments={})
        for _ in amounts
    ]
    usages = [
        {
            "cost_usd": cost,
            "latency_ms": index,
            "invocations": None,
            "cache_status": "miss",
        }
        for index, cost in enumerate(amounts)
    ]
    interpreted = SimpleNamespace(
        outcome="approved_for_execution", patch={"tool_calls": calls}
    )
    dispatched = SimpleNamespace(
        outcome="ready_to_respond",
        patch={
            "tool_effects": [
                {
                    "call_id": call.call_id,
                    "tool_name": call.tool_name,
                    "stage_patch": {
                        "research": {
                            "usage": {
                                **usage,
                                "private_provider_payload": fake.sentence(),
                            }
                        },
                        "private_user_context": fake.sentence(),
                    },
                }
                for call, usage in zip(calls, usages, strict=True)
            ]
        },
    )

    evidence = measurement_execution_evidence(
        interpreted=interpreted,
        dispatched=dispatched,
        confirmed=None,
        clarified=None,
        followup=None,
    )

    assert evidence["tool_usage"] == [
        {"call_id": call.call_id, "tool_name": call.tool_name, "usage": usage}
        for call, usage in zip(calls, usages, strict=True)
    ]
