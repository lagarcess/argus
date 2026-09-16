"""Free regressions for answer repairs that leave the model contract unchanged."""

import asyncio

import pytest
from argus.agent_runtime import answer_calculation as ac
from argus.agent_runtime import knowledge_answer as ka
from argus.agent_runtime import research_answer as ra
from argus.agent_runtime.llm_interpreter_types import LLMInterpretationResponse
from argus.agent_runtime.state.models import RunState, UserState

from tests.agent_runtime.test_answer_calculation import (
    LOAN,
    _published,
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
