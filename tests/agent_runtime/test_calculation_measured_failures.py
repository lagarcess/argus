"""Free reproductions of calculation boundaries exposed at faeff8e4."""

import json
from pathlib import Path

import pytest
from argus.agent_runtime import answer_calculation as ac
from argus.agent_runtime.llm_interpreter_types import LLMInterpretationResponse
from argus.domain.calculations.answer_request import AnswerCalculation
from argus.domain.capability_registry import get_tool_catalog

EVIDENCE = Path(
    "docs/reports/evidence/calculation-followups/measurement-faeff8e4/live-measurement.json"
)


def recorded(case):
    return next(r for r in json.loads(EVIDENCE.read_text())["results"] if r["id"] == case)


def resolve(request, *, prior=None, currency="DOP", notes=None):
    return ac.resolve_calculation(
        request,
        catalog=get_tool_catalog(),
        retrieved=[],
        currency=currency,
        subject_symbol=None,
        market_close=lambda _: pytest.fail("no price lookup"),
        notes=notes if notes is not None else [],
        prior_arguments=prior,
    )


def test_explicit_edit_owns_source_instead_of_reusing_old_assumption():
    card = recorded("calculation_followups_q2_card_recall_en")["typed_outcome"][
        "calculations"
    ][0]
    request = AnswerCalculation(
        kind=card["tool_name"],
        solve_for="monthly_income",
        updated_fields=["ratio_pct"],
        inputs=[{"name": "ratio_pct", "value": 15, "source": "assumption"}],
    )
    notes = []
    resolved = resolve(request, prior=card["arguments"], notes=notes)
    assert resolved.arguments["ratio_pct"] == 15
    assert resolved.arguments["sources"]["ratio_pct"] == {"kind": "user"}
    assert (
        resolved.arguments["sources"]["monthly_debt_payments"]
        == card["arguments"]["sources"]["monthly_debt_payments"]
    )
    assert "calculation_edit_source_normalized" in notes


@pytest.mark.parametrize("language", ["en", "es_419"])
def test_conversion_cannot_erase_a_stated_amount_with_an_invalid_solve_for(language):
    r = recorded("calculation_followups_q7_conversion_fill_" + language)
    request = AnswerCalculation.model_validate(
        r["typed_outcome"]["offered"]["clarification"]["payload"]["calculations"][0]
    )
    notes = []
    resolved = resolve(request, notes=notes)
    assert resolved.computable
    assert resolved.arguments["amount"] == 100
    assert resolved.arguments["currency"] == "USD"
    assert resolved.arguments["sources"]["currency"]["kind"] == "user"
    assert "calculation_solve_for_ignored" in notes


@pytest.mark.parametrize(
    "case",
    [
        "calculation_followups_q3_periods_and_profile_currency_en",
        "calculation_followups_q3_periods_and_profile_currency_es_419",
        "calculation_followups_q10_generic_crypto_en",
    ],
)
def test_a_question_without_a_computed_reference_cannot_voice_a_completed_card(case):
    r = recorded(case)
    card = ac.ToolResultCard.model_validate(r["typed_outcome"]["calculations"][0])
    prose = r["prose_judge"]["judged_assistant_text"]["text"]
    _, reason = ac.render_answer_text(prose, {"calculation_1": card})
    assert reason == "missing_computed_reference"


@pytest.mark.parametrize(
    "field", ["candidate_strategy_draft", "response_profile_overrides"]
)
def test_empty_optional_interpreter_objects_do_not_discard_the_other_typed_facts(field):
    payload = {
        "intent": "unsupported_or_out_of_scope",
        "task_relation": "new_task",
        "user_goal_summary": "Options are unsupported",
        field: None,
    }
    # Keep unrelated contracts at their defaults; this replay isolates the null-object failure.
    response = LLMInterpretationResponse.model_validate(payload)
    assert response.intent == "unsupported_or_out_of_scope"
    assert getattr(response, field) is not None


@pytest.mark.parametrize(
    "case",
    [
        "calculation_followups_q3_periods_and_profile_currency_en",
        "calculation_followups_q3_periods_and_profile_currency_es_419",
        "calculation_followups_q10_generic_crypto_en",
    ],
)
def test_completed_card_recovery_shows_the_result_and_cannot_repeat_the_question(case):
    card = ac.ToolResultCard.model_validate(
        recorded(case)["typed_outcome"]["calculations"][0]
    )
    text = ac.completed_card_readout({"calculation_1": card})
    assert ac.figure_text(card.presentation.answer) in text
    assert "?" not in text
    if card.tool_name == "historical_drawdown":
        assert (
            ac.render_answer_text("{{symbol}}", {"calculation_1": card})[1]
            == "missing_computed_reference"
        )


def test_conversion_keeps_the_output_currency_separate_from_the_input():
    case = recorded("calculation_followups_q7_conversion_fill_es_419")
    request = AnswerCalculation.model_validate(
        case["typed_outcome"]["offered"]["clarification"]["payload"]["calculations"][0]
    )
    resolved = resolve(request)
    card = ac.card_in(ac.computed_answer_patch(resolved))
    assert card.arguments["currency"] == "USD"
    assert card.arguments["output_currency"] == "DOP"
    assert card.outcome.result["scaled_amount"] == pytest.approx(5886.66)


@pytest.mark.parametrize(
    "kind", ["historical_drawdown", "time_value", "debt_to_income", "scaled_amount"]
)
def test_required_calculation_cannot_be_replaced_by_an_empty_prose_answer(
    monkeypatch, kind
):
    from argus.agent_runtime import calculated_answer as ca
    from argus.agent_runtime.state.models import UserState

    monkeypatch.setattr(ca, "resolve_openrouter_api_key", lambda: "test")
    seen = []

    def voice(messages):
        seen.extend(messages)
        return ca.CalculatedVoicedAnswer(lead="How much do you want to invest?")

    monkeypatch.setattr(ca, "_voice", voice)
    notes = []
    assert (
        ca.calculated_answer(
            message="Use the supplied inputs.",
            language="en",
            user=UserState(user_id="test"),
            notes=notes,
            required_kind=kind,
        )
        is None
    )
    assert "required_calculation_missing" in notes
    assert kind in seen[0]["content"]


@pytest.mark.parametrize("language", ["en", "es-419"])
def test_changed_principal_recomputes_from_the_stored_coupon_without_research(
    monkeypatch, language
):
    from argus.agent_runtime import calculated_answer as ca
    from argus.domain.calculation_turn_facts import (
        calculation_turn_facts,
        calculation_turn_history_text,
    )
    from argus.domain.tool_contracts import ToolCall

    from tests.agent_runtime.test_calculated_answer import USER, _voice

    declaration = get_tool_catalog().get("income_yield")
    call = ToolCall(
        tool_name=declaration.name,
        call_id="prior-coupon",
        arguments={
            "currency": "DOP",
            "price": 1000000,
            "yield_pct": 10.5,
            "annual_income": None,
            "sources": {
                field: {"kind": "user"} for field in ("currency", "price", "yield_pct")
            },
        },
    )
    prior = declaration.result_card(
        call=call,
        outcome=declaration.invoke_sync(call.arguments),
        artifact_id="prior-coupon",
    )
    history = [
        {
            "role": "assistant",
            "content": calculation_turn_history_text(
                calculation_turn_facts(
                    {"tool_result_cards": [prior.model_dump(mode="json")]}
                ),
                "Prior coupon calculation.",
            ),
        }
    ]
    request = AnswerCalculation(
        kind=declaration.name,
        prior_artifact_id=prior.artifact_id,
        solve_for="annual_income",
        updated_fields=["price"],
        inputs=[
            {"name": "price", "value": 500000, "source": "user"},
        ],
    )
    _voice(
        monkeypatch,
        [ca.CalculatedVoicedAnswer(lead="{{annual_income}}", calculations=[request])],
    )
    result = ca.calculated_answer(
        message="Change the principal only.",
        language=language,
        user=USER,
        notes=[],
        history=history,
        required_kind=declaration.name,
        market_close=lambda _: pytest.fail("No new fact is needed"),
    )
    assert result is not None
    card = ac.card_in(result.patch)
    assert card.outcome.status == "succeeded"
    assert card.outcome.result["annual_income"] == 52500
    assert card.arguments["yield_pct"] == prior.arguments["yield_pct"]
    assert (
        card.arguments["sources"]["yield_pct"] == prior.arguments["sources"]["yield_pct"]
    )
    assert "52,500" in result.answer_text
    assert card.artifact_id != prior.artifact_id


def test_an_unedited_stored_currency_keeps_its_original_source():
    request = AnswerCalculation(
        kind="income_yield",
        solve_for="annual_income",
        updated_fields=["price"],
        inputs=[
            {"name": "price", "value": 500000, "source": "user", "currency": "DOP"},
        ],
    )
    prior = {
        "currency": "DOP",
        "price": 1000000,
        "yield_pct": 10.5,
        "annual_income": None,
        "sources": {"currency": {"kind": "assumption"}},
    }
    resolved = resolve(request, prior=prior)
    assert resolved.arguments["sources"]["currency"] == prior["sources"]["currency"]
    assert resolved.arguments["price"] == 500000
