"""Free regressions for answer repairs that leave the model contract unchanged."""

import asyncio
import json
from pathlib import Path

import pytest
from argus.agent_runtime import answer_calculation as ac
from argus.agent_runtime import knowledge_answer as ka
from argus.agent_runtime import research_answer as ra
from argus.agent_runtime.llm_interpreter_types import LLMInterpretationResponse
from argus.agent_runtime.state.models import RunState, UserState
from argus.domain.calculations.answer_request import AnswerCalculation

from tests.agent_runtime.test_answer_calculation import (
    LOAN,
    _published,
    _published_many,
    _request,
    _resolve,
)
from tests.agent_runtime.test_calculated_answer import _read


@pytest.mark.parametrize(
    "field", ["candidate_strategy_draft", "response_profile_overrides"]
)
@pytest.mark.parametrize("empty", [None, {}])
def test_empty_optional_objects_preserve_the_rest_of_the_interpretation(field, empty):
    payload = dict(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        user_goal_summary="Options are unsupported",
    )
    response = LLMInterpretationResponse.model_validate({**payload, field: empty})
    default = LLMInterpretationResponse.model_validate(payload)
    assert response == default


@pytest.mark.parametrize("solve_for", ["price", "amount", "growth_base_pct"])
def test_one_way_calculation_keeps_inputs_named_as_an_unknown(solve_for):
    inputs = {
        "symbol": "AAPL",
        "price": 100,
        "per_share": 5,
        "growth_base_pct": 15,
        "amount": 1200,
    }
    notes = []
    resolved = _resolve(
        _request(
            "valuation_scenarios",
            [
                {"name": name, "value": value, "source": "user"}
                for name, value in inputs.items()
            ],
            solve_for=solve_for,
        ),
        notes=notes,
    )
    assert resolved.computable
    assert resolved.arguments[solve_for] == inputs[solve_for]
    assert "calculation_solve_for_ignored" in notes
    assert ac.card_in(ac.computed_answer_patch(resolved)).outcome.status == "succeeded"


@pytest.mark.parametrize("source", ["user", "page"])
def test_stated_amount_owns_currency_and_its_source(source):
    from tests.agent_runtime.test_answer_calculation import RATE_PAGE

    inputs = [
        {
            **item,
            "currency": "USD",
            "source": source,
            "source_url": RATE_PAGE.url if source == "page" else None,
        }
        if item["name"] == "present_value"
        else item
        for item in LOAN
    ]
    resolved = _resolve(_request("time_value", inputs, "payment"), currency="DOP")
    assert resolved.computable
    assert resolved.arguments["currency"] == "USD"
    assert (
        resolved.arguments["sources"]["currency"]
        == resolved.arguments["sources"]["present_value"]
    )


@pytest.mark.parametrize("cited", [False, True])
def test_standalone_page_currency_requires_the_same_source_admission(cited):
    from tests.agent_runtime.test_answer_calculation import RATE_PAGE

    inputs = [
        {key: value for key, value in item.items() if key != "currency"} for item in LOAN
    ]
    inputs.append(
        {
            "name": "currency",
            "value": "USD",
            "source": "page",
            "source_url": RATE_PAGE.url
            if cited
            else "https://unretrieved.example/currency",
        }
    )
    notes = []
    resolved = _resolve(
        _request("time_value", inputs, "payment"), currency="DOP", notes=notes
    )
    expected = "USD" if cited else "DOP"
    assert resolved.computable
    assert resolved.arguments["currency"] == expected
    card = ac.card_in(ac.computed_answer_patch(resolved))
    assert card.outcome.status == "succeeded"
    assert card.presentation.answer.unit.interpolation_args["code"] == expected
    assert (ac.PAGE_UNCITED_REASON_CODE in notes) is (not cited)


@pytest.mark.parametrize("source", ["user", "assumption", "market_data"])
def test_standalone_currency_cannot_claim_an_unsupported_market_data_source(source):
    inputs = [
        {key: value for key, value in item.items() if key != "currency"} for item in LOAN
    ]
    inputs.append({"name": "currency", "value": "USD", "source": source})
    notes = []
    resolved = _resolve(
        _request("time_value", inputs, "payment"), currency="DOP", notes=notes
    )
    assert resolved.computable
    assert resolved.arguments["currency"] == ("DOP" if source == "market_data" else "USD")
    assert (ac.MARKET_DATA_NOT_A_PRICE_REASON_CODE in notes) is (source == "market_data")


@pytest.mark.parametrize("source", ["user", "page"])
def test_accepted_amount_keeps_its_currency_despite_an_uncited_standalone_code(source):
    from tests.agent_runtime.test_answer_calculation import RATE_PAGE

    inputs = [
        {
            **item,
            "currency": "USD",
            "source": source,
            "source_url": RATE_PAGE.url if source == "page" else None,
        }
        if item["name"] == "present_value"
        else item
        for item in LOAN
    ]
    inputs.append(
        {
            "name": "currency",
            "value": "EUR",
            "source": "page",
            "source_url": "https://unretrieved.example/currency",
        }
    )
    notes = []
    resolved = _resolve(
        _request("time_value", inputs, "payment"), currency="DOP", notes=notes
    )
    assert resolved.computable
    assert resolved.arguments["currency"] == "USD"
    assert (
        resolved.arguments["sources"]["currency"]
        == resolved.arguments["sources"]["present_value"]
    )
    card = ac.card_in(ac.computed_answer_patch(resolved))
    assert card.outcome.status == "succeeded"
    assert card.presentation.answer.unit.interpolation_args["code"] == "USD"
    assert ac.PAGE_UNCITED_REASON_CODE in notes


@pytest.mark.parametrize(
    "extra",
    [
        {"name": "price", "value": 99, "source": "user", "currency": "USD"},
        {"name": "payment", "value": 99, "source": "user", "currency": "USD"},
        {"name": "present_value", "value": None, "source": "user", "currency": "USD"},
        {
            "name": "present_value",
            "value": 99,
            "source": "page",
            "currency": "USD",
            "source_url": "https://unretrieved.example/amount",
        },
    ],
)
def test_discarded_inputs_cannot_change_the_calculation_currency(extra):
    inputs = [
        {key: value for key, value in item.items() if key != "currency"} for item in LOAN
    ]
    resolved = _resolve(
        _request("time_value", [*inputs, extra], "payment"), currency="DOP"
    )
    assert resolved.arguments["currency"] == "DOP"
    if extra["name"] in {"price", "payment"}:
        assert (
            ac.card_in(
                ac.computed_answer_patch(resolved)
            ).presentation.answer.unit.interpolation_args["code"]
            == "DOP"
        )


@pytest.mark.parametrize(
    "template",
    [
        "How many payments?",
        "With {{present_value}} principal.",
        "Total interest: {{total_interest}}.",
    ],
)
def test_completed_card_attaches_its_primary_result_without_discarding_prose(template):
    notes = []
    published = _published(template, notes=notes)
    card = ac.card_in(published.patch)
    assert published.template is not None
    assert ac.figure_text(card.presentation.answer) in published.answer_text
    rendered, failure = ac.render_answer_text(template, {"calculation_1": card})
    assert failure == "missing_computed_reference"
    assert rendered in published.answer_text
    assert ac.FIGURE_CHECK_REASON_CODE in notes


@pytest.mark.parametrize("language", ["en", "es-419"])
def test_omitted_savings_goal_result_uses_localized_card_label(language):
    # Production walk after a9286b21: prose omitted the computed periods, so
    # recovery printed the model's identifier name as the label.
    request = AnswerCalculation.model_validate(
        {
            "name": "months_to_goal",
            "kind": "time_value",
            "solve_for": "periods",
            "inputs": [
                {"name": "direction", "value": "save", "source": "user"},
                {
                    "name": "present_value",
                    "value": 1200,
                    "source": "user",
                    "currency": "USD",
                },
                {
                    "name": "payment",
                    "value": 300,
                    "source": "user",
                    "currency": "USD",
                },
                {
                    "name": "future_value",
                    "value": 3000,
                    "source": "user",
                    "currency": "USD",
                },
                {"name": "annual_rate_pct", "value": 0, "source": "assumption"},
            ],
        }
    )
    published = _published_many(
        "Saving another 300 each month reaches the goal.",
        [request],
        language=language,
    )
    card = ac.card_in(published.patch)
    answer = card.presentation.answer
    assert answer is not None
    assert answer.name == "periods"
    assert answer.label.locale_key == "tools.calc.fields.periods"
    figure = ac.figure_text(answer)
    assert published.answer_text is not None
    assert published.template is not None
    expected = _locale_copy(language, answer.label.locale_key)
    assert expected
    assert expected != "months_to_goal"
    assert "months_to_goal" not in published.answer_text
    assert f"{expected}: {figure}" in published.answer_text
    owner = ac.calculation_names([request])[0]
    assert (
        f"{expected}: {{{{{owner}.{answer.name}}}}}" in published.template["text"]
    )


def _locale_copy(language: str, locale_key: str) -> str:
    locale = "es-419" if language.startswith("es") else "en"
    node = json.loads(
        (Path("web/public/locales") / locale / "common.json").read_text(encoding="utf-8")
    )
    for part in locale_key.split("."):
        node = node[part]
    return str(node)


def test_each_completed_card_needs_its_own_primary_reference():
    card = ac.card_in(_published("{{payment}}").patch)
    cards = {"first": card, "second": card.model_copy(update={"artifact_id": "second"})}
    assert (
        ac.render_answer_text("{{first.payment}}", cards)[1]
        == "missing_computed_reference"
    )
    assert (
        ac.render_answer_text("{{first.payment}} and {{second.payment}}", cards)[1]
        is None
    )


@pytest.mark.parametrize(
    "intent",
    ["conversation_followup", "beginner_guidance", "unsupported_or_out_of_scope"],
)
@pytest.mark.parametrize("rail", [True, False])
def test_missing_educational_query_never_dispatches_research(monkeypatch, intent, rail):
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", str(rail).lower())

    async def forbidden(**kwargs):
        pytest.fail("A missing educational query cannot authorize research")

    monkeypatch.setattr(ra, "_dispatch", forbidden)
    monkeypatch.setattr(ka, "_classify_question", forbidden)
    interpretation = _read().model_copy(update={"intent": intent})
    common = dict(
        interpretation=interpretation,
        state=RunState.new(
            current_user_message="Explain the earlier answer", recent_thread_history=[]
        ),
        user=UserState(user_id="test"),
    )
    assert asyncio.run(ra.research_answer_stage_result(**common)) is None
    assert (
        asyncio.run(
            ka.knowledge_answer_stage_result(
                **common, snapshot=None, selected_thread_metadata={}
            )
        )
        is None
    )
