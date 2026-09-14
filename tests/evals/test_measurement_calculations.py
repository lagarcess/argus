"""Free contract tests; authored outputs do not establish live answer quality."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.domain.calculations.support import run_calculation
from tests.evals import measurement_eval_harness as harness
from tests.evals.measurement_calculations import (
    compare_calculations,
    delivered_calculations,
    stored_calculation_history,
)


def money_cases():
    return [
        case
        for case in harness.load_eval_cases()
        if case.category == "calculation_followups"
    ]


def test_every_failure_mechanism_has_both_languages_and_a_substantive_rubric():
    grouped = {}
    for case in money_cases():
        grouped.setdefault(case.raw["regression"], set()).add(case.user_language)
        if case.raw["regression"] == "new_external_fact":
            assert case.expected.requires_new_facts is True
            continue
        assert set(case.prose_judge_criteria) - {
            "honesty",
            "no_raw_runtime_error",
            "spanish_language_integrity",
        }
        assert case.profile["currency"] == (
            "DOP" if case.user_language == "es-419" else "USD"
        )
    assert set(grouped) == {
        "q2_card_recall",
        "q3_periods_and_profile_currency",
        "q4_changed_principal",
        "q5_rewards_fill",
        "q5_no_personal_product_pick",
        "q7_conversion_fill",
        "q7_changed_goal_risk",
        "q10_historical_drawdown",
        "q10_generic_crypto",
        "explain_prior_answer",
        "new_external_fact",
    }
    assert all(languages == {"en", "es-419"} for languages in grouped.values())


@pytest.mark.parametrize("case", money_cases(), ids=lambda case: case.id)
def test_new_case_refuses_unapproved_rubric_before_spending(case, monkeypatch):
    # Remains valid after rubric approval: remove a required criterion to prove
    # an incomplete judge contract cannot silently produce a meaningless pass.
    criterion = case.prose_judge_criteria[-1]
    monkeypatch.setattr(
        harness,
        "PROSE_JUDGE_RUBRIC",
        harness.PROSE_JUDGE_RUBRIC.replace(f"- {criterion}:", "- unavailable:"),
    )
    monkeypatch.setattr(
        harness,
        "OpenRouterStructuredInterpreter",
        lambda **_: pytest.fail("spent model call before validating rubric"),
    )
    with pytest.raises(ValueError, match="unapproved prose rubric"):
        harness.run_eval_case(case)


@pytest.mark.parametrize(
    "case",
    [
        c
        for c in money_cases()
        if c.raw["regression"]
        in {
            "q2_card_recall",
            "q3_periods_and_profile_currency",
            "q4_changed_principal",
            "q5_rewards_fill",
            "q7_conversion_fill",
        }
    ],
    ids=lambda case: case.id,
)
def test_typed_checks_accept_the_declared_calculation_and_reject_lost_delivery(case):
    wanted = case.expected.calculations
    assert wanted
    reference = wanted[0]["reference"]
    card = run_calculation(reference["tool_name"], reference["arguments"]).model_dump(
        mode="json"
    )
    failures = []
    compare_calculations(wanted, [card], failures)
    assert not failures
    compare_calculations(wanted, [], failures)
    assert failures == ["calculations.count: expected 1, got 0"]


@pytest.mark.parametrize(
    "mutation",
    (
        "drop_periods",
        "wrong_currency",
        "wrong_answer",
        "no_answer",
        "failed_tool",
        "drop_assumption",
        "wrong_display_currency",
    ),
)
def test_typed_checks_reject_each_observed_card_fault(mutation):
    case = next(
        case
        for case in money_cases()
        if case.raw["regression"] == "q3_periods_and_profile_currency"
        and case.user_language == "es-419"
    )
    wanted = case.expected.calculations
    reference = wanted[0]["reference"]
    card = run_calculation(reference["tool_name"], reference["arguments"]).model_dump(
        mode="json"
    )
    if mutation == "drop_periods":
        card["arguments"]["periods"] = None
    elif mutation == "wrong_currency":
        card["arguments"]["currency"] = "USD"
    elif mutation == "wrong_answer":
        card["presentation"]["answer"]["value"] += 100
    elif mutation == "no_answer":
        card["presentation"]["answer"] = None
    elif mutation == "failed_tool":
        card["outcome"]["status"] = "invalid"
    elif mutation == "drop_assumption":
        card["arguments"]["sources"].pop("currency")
    elif mutation == "wrong_display_currency":
        card["presentation"]["answer"]["unit"]["interpolation_args"]["code"] = "USD"
    failures = []
    compare_calculations(wanted, [card], failures)
    assert failures


def test_projection_reads_final_delivery_only():
    assert delivered_calculations({"tool_result_cards": [{"not": "delivered"}]}) == []
    assert (
        delivered_calculations({"final_response_payload": {"tool_result_cards": []}})
        == []
    )


def test_stored_seed_runs_through_production_loader(monkeypatch):
    from tests.evals import measurement_calculations as calculations

    original = calculations.load_runtime_thread_history
    observed = []

    def recording_loader(**kwargs):
        observed.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(calculations, "load_runtime_thread_history", recording_loader)
    case = next(
        case for case in money_cases() if case.raw["regression"] == "q2_card_recall"
    )
    history = stored_calculation_history(list(case.stored_history))
    assert len(observed) == 1
    assert history[0]["role"] == "user" and history[1]["role"] == "assistant"
    import json

    facts = json.loads(history[1]["content"])["calculation_cards"][0]
    assert facts["arguments"]["monthly_debt_payments"] == 1129
    assert facts["arguments"]["sources"]["monthly_debt_payments"]["kind"] == "page"
    assert facts["result"]["monthly_income"] == 11290
    # Parent's runtime projection owns the serialized shape. The measurement
    # must never inject a handwritten typed-history substitute for that owner.
    assert stored_calculation_history([]) == []


def test_profile_reaches_real_user_state_and_history_reaches_interpreter(monkeypatch):
    case = next(
        case
        for case in money_cases()
        if case.raw["regression"] == "q2_card_recall" and case.user_language == "es-419"
    )
    observed = {}

    def stage(**kwargs):
        observed.update(kwargs)
        return SimpleNamespace(
            outcome="ready_to_respond",
            patch={"assistant_response": "Offline authored answer"},
        )

    monkeypatch.setattr(harness, "interpret_stage", stage)
    monkeypatch.setattr(harness, "OpenRouterStructuredInterpreter", lambda **_: object())
    monkeypatch.setattr(harness, "OpenRouterClarificationGenerator", lambda **_: object())
    harness.run_eval_case(case, run_prose_judge=False)
    assert observed["user"].country == "DO"
    assert observed["user"].currency == "DOP"
    assert len(observed["state"].recent_thread_history) == len(case.stored_history)


@pytest.mark.parametrize(
    "fault", [None, "research_source", "missing_window", "missing_display", "wrong_loss"]
)
def test_drawdown_requires_provider_provenance_and_observed_display(fault):
    from argus.domain.calculations.historical_drawdown import (
        get_historical_drawdown_declaration,
    )
    from argus.domain.tool_contracts import ToolCall, ToolOutcome

    declaration = get_historical_drawdown_declaration()
    result = {
        "symbol": "BTC",
        "asset_class": "crypto",
        "max_drawdown_pct": -50,
        "requested_start_date": "2021-01-01",
        "requested_end_date": "2024-12-31",
        "observed_start_date": "2021-01-01",
        "observed_end_date": "2024-12-31",
        "peak_date": "2021-11-10",
        "trough_date": "2022-11-21",
        "observations": 1461,
        "source": "argus_market_data",
        "timeframe": "1D",
        "price_basis": "close",
        "default_window": False,
    }
    call = ToolCall(
        tool_name=declaration.name,
        call_id="authored-drawdown",
        arguments={"symbol": "BTC"},
    )
    # This tests the assertion against an explicitly authored result. It never
    # invokes the provider or labels this fixture as a live market observation.
    card = declaration.result_card(
        call=call,
        outcome=ToolOutcome(status="succeeded", result=result),
        artifact_id="authored-drawdown",
    ).model_dump(mode="json")
    if fault == "research_source":
        card["outcome"]["result"]["source"] = "research"
    elif fault == "missing_window":
        del card["outcome"]["result"]["observed_start_date"]
    elif fault == "missing_display":
        card["presentation"]["rows"] = []
    elif fault == "wrong_loss":
        card["presentation"]["answer"]["value"] = -25
    failures = []
    compare_calculations([{"historical_drawdown": True}], [card], failures)
    assert bool(failures) == (fault is not None)


def test_research_attempt_observer_counts_actual_client_entry_without_network(
    monkeypatch,
):
    from argus.domain.research.perplexity_agent import PerplexityAgentClient

    from tests.evals.measurement_research_calls import capture_research_attempts

    returned = {"authored": "offline transport response"}
    monkeypatch.setattr(
        PerplexityAgentClient, "_send", lambda *_args, **_kwargs: returned
    )
    with capture_research_attempts() as attempts:
        assert attempts == []
        client = PerplexityAgentClient("unused-offline-key")
        assert client._send("POST", "https://example.com", {}, 1) is returned
        assert attempts == ["perplexity_agent_send"]
    assert client._send("POST", "https://example.com", {}, 1) is returned
    assert len(attempts) == 1


def test_no_new_facts_assertion_rejects_a_real_provider_attempt():
    case = next(
        case for case in money_cases() if case.raw["regression"] == "explain_prior_answer"
    )
    outcome = {
        "intent": "conversation_followup",
        "capability_verdict": "answer_only",
        "stage_outcomes": ["ready_to_respond"],
        "offered": {"response": True},
        "requires_new_facts": False,
        "research_provider_attempts": 0,
    }
    assert harness.typed_expectation_failures(case=case, outcome=outcome) == []
    outcome["research_provider_attempts"] = 1
    assert harness.typed_expectation_failures(case=case, outcome=outcome) == [
        "research_provider_attempts: expected 0, got 1"
    ]


@pytest.mark.asyncio
async def test_interpreter_observer_reads_actual_result_and_preserves_it():
    from tests.evals.measurement_research_calls import ObservedInterpreter

    result = SimpleNamespace(research_query=SimpleNamespace(requires_new_facts=False))
    requests = []

    class Delegate:
        async def ainvoke(self, request):
            requests.append(request)
            return result

    observed = ObservedInterpreter(Delegate())
    assert observed.research_need() is None
    assert await observed.ainvoke("authored offline request") is result
    assert observed.research_need() is False
    assert requests == ["authored offline request"]
