"""The answer step owns the math: an answer's calculation request is held to its
sources, computed by its declaration, and the prose states figures only through
references filled from the card and checked."""

from __future__ import annotations

from typing import Any

from argus.agent_runtime import answer_calculation as ac
from argus.domain.calculations.answer_request import AnswerCalculation
from argus.domain.capability_registry import get_tool_catalog
from argus.domain.research.contracts import ResearchSource
from argus.domain.tool_contracts import ToolResultCard

RATE_PAGE = ResearchSource(
    url="https://bank.example/rates", title="Bank rate sheet", source_date="2026-09-01"
)
LOAN: list[dict[str, Any]] = [
    {"name": "direction", "value": "borrow", "source": "user"},
    {"name": "present_value", "value": 180000, "source": "user", "currency": "DOP"},
    {
        "name": "annual_rate_pct",
        "value": 14,
        "source": "page",
        "source_url": RATE_PAGE.url,
        "as_of": "2026-09-01",
    },
    {"name": "periods", "value": 48, "source": "user"},
    {"name": "future_value", "value": 0, "source": "user"},
]


def _close(symbol: str) -> tuple[float, str] | None:
    return (187.5, "2026-09-11") if symbol == "AAPL" else None


def _request(kind: str, inputs: list[dict[str, Any]], solve_for: str | None = None):
    return AnswerCalculation.model_validate(
        {"kind": kind, "solve_for": solve_for, "inputs": inputs}
    )


def _resolve(request, *, retrieved=(RATE_PAGE,), currency="DOP", notes=None):
    return ac.resolve_calculation(
        request,
        catalog=get_tool_catalog(),
        retrieved=list(retrieved),
        currency=currency,
        subject_symbol=None,
        market_close=_close,
        notes=notes if notes is not None else [],
    )


def _published(template, *, inputs=LOAN, solve_for="payment", notes=None, language="en"):
    return ac.publish_calculation(
        _request("time_value", inputs, solve_for),
        template=template,
        language=language,
        catalog=get_tool_catalog(),
        retrieved=[RATE_PAGE],
        currency="DOP",
        subject_symbol=None,
        market_close=_close,
        notes=notes if notes is not None else [],
    )


def test_each_input_keeps_its_true_source() -> None:
    resolved = _resolve(_request("time_value", LOAN, solve_for="payment"))
    assert resolved.computable
    assert resolved.arguments["payment"] is None
    sources = resolved.arguments["sources"]
    assert sources["annual_rate_pct"] == {
        "kind": "page",
        "title": "Bank rate sheet",
        "url": RATE_PAGE.url,
        "date": "2026-09-01",
    }
    assert sources["present_value"] == {"kind": "user"}
    assert resolved.arguments["currency"] == "DOP"


def test_a_page_not_retrieved_for_this_answer_is_not_used_and_recorded() -> None:
    notes: list[str] = []
    resolved = _resolve(
        _request("time_value", LOAN, solve_for="payment"), retrieved=(), notes=notes
    )
    assert resolved.not_looked_up == ["annual_rate_pct"]
    assert ac.PAGE_UNCITED_REASON_CODE in notes


def test_the_current_price_comes_from_market_data_whatever_the_model_wrote() -> None:
    per_share = {
        "name": "per_share",
        "value": 6.25,
        "source": "page",
        "source_url": RATE_PAGE.url,
        "as_of": "2026-09-01",
    }
    resolved = _resolve(
        _request(
            "price_multiple",
            [
                {"name": "symbol", "value": "AAPL", "source": "user"},
                {"name": "price", "value": 999, "source": "market_data"},
                per_share,
            ],
            solve_for="multiple",
        ),
        currency="USD",
    )
    assert resolved.arguments["price"] == 187.5
    assert resolved.arguments["sources"]["price"] == {
        "kind": "market_data",
        "date": "2026-09-11",
    }
    notes: list[str] = []
    missing = _resolve(
        _request(
            "price_multiple",
            [
                {"name": "symbol", "value": "ZZZZ", "source": "user"},
                {"name": "price", "value": None, "source": "market_data"},
                {"name": "per_share", "value": 2, "source": "market_data"},
            ],
            solve_for="multiple",
        ),
        currency="USD",
        notes=notes,
    )
    assert missing.not_looked_up == ["price", "per_share"]
    assert ac.MARKET_PRICE_UNAVAILABLE_REASON_CODE in notes
    assert ac.MARKET_DATA_NOT_A_PRICE_REASON_CODE in notes


def test_a_figure_only_the_user_knows_is_owed_and_an_assumption_is_labeled() -> None:
    inputs = [
        *LOAN[:3],
        {"name": "periods", "value": None, "source": "user"},
        {"name": "future_value", "value": 0, "source": "assumption"},
    ]
    resolved = _resolve(_request("time_value", inputs, solve_for="payment"))
    assert resolved.user_owed == ["periods"]
    assert resolved.assumed == ["future_value"]
    assert resolved.arguments["sources"]["future_value"] == {"kind": "assumption"}


def test_an_input_the_model_left_out_is_owed_by_the_user() -> None:
    resolved = _resolve(_request("time_value", LOAN[:3], solve_for="payment"))
    assert resolved.user_owed == ["future_value", "periods"]


def test_a_money_input_in_another_currency_is_not_used() -> None:
    notes: list[str] = []
    inputs = [
        LOAN[0],
        {"name": "present_value", "value": 1200, "source": "user", "currency": "USD"},
        *LOAN[2:],
    ]
    resolved = _resolve(_request("time_value", inputs, solve_for="payment"), notes=notes)
    assert resolved.not_looked_up == ["present_value"]
    assert ac.CURRENCY_MISMATCH_REASON_CODE in notes


def test_an_unknown_kind_or_undeclared_name_is_dropped_on_record() -> None:
    notes: list[str] = []
    assert _resolve(_request("loan_wizard", LOAN), notes=notes) is None
    assert ac.KIND_UNKNOWN_REASON_CODE in notes
    notes = []
    extra = {"name": "coupon_rate_pct", "value": 5, "source": "user"}
    resolved = _resolve(
        _request("time_value", [*LOAN, extra], solve_for="payment"), notes=notes
    )
    assert "coupon_rate_pct" not in resolved.arguments
    assert ac.INPUT_UNDECLARED_REASON_CODE in notes


def test_the_prose_states_the_computed_payment_through_its_reference() -> None:
    template = (
        "Paying {{present_value}} at {{annual_rate_pct}} over {{periods}} months "
        "costs **{{payment}}** a month."
    )
    published = _published(template)
    card = ac.card_in(published.patch)
    payment = ac.figure_text(card.presentation.answer)
    assert payment.startswith("DOP ")
    assert published.answer_text == (
        f"Paying DOP 180,000 at 14% over 48 months costs **{payment}** a month."
    )
    assert published.template == {
        "artifact_id": card.artifact_id,
        "text": template,
        "language": "en",
    }


def test_an_unknown_reference_hands_over_to_argus_lead_and_cited_digits_stand() -> None:
    notes: list[str] = []
    published = _published("It costs {{monthly_cost}}.", notes=notes)
    assert published.answer_text == ac.fallback_answer_lead("en", succeeded=True)
    assert published.template is None
    assert ac.FIGURE_CHECK_REASON_CODE in notes
    cited = _published(
        "At the bank's published 14% rate, paying {{present_value}} at "
        "{{annual_rate_pct}} over {{periods}} months costs {{payment}} a month."
    )
    assert cited.template is not None
    assert "published 14% rate" in cited.answer_text
    assert (
        _published("Cuesta {{payment}} al mes.", language="es-419").template is not None
    )


def test_an_assumption_the_prose_does_not_state_fails_the_check() -> None:
    inputs = [*LOAN[:4], {"name": "future_value", "value": 0, "source": "assumption"}]
    assert _published("It costs {{payment}} a month.", inputs=inputs).template is None
    stated = _published(
        "Assuming the loan ends at {{future_value}}, it costs {{payment}} a month.",
        inputs=inputs,
    )
    assert stated.template is not None


def test_a_plan_that_does_not_solve_keeps_its_card_under_argus_lead() -> None:
    inputs = [
        LOAN[0],
        LOAN[1],
        {"name": "payment", "value": 2000, "source": "user", "currency": "DOP"},
        LOAN[2],
        LOAN[4],
    ]
    published = _published(
        "It takes {{periods}} months.", inputs=inputs, solve_for="periods"
    )
    card: ToolResultCard = ac.card_in(published.patch)
    assert card.outcome.status != "succeeded"
    assert published.answer_text == ac.fallback_answer_lead("en", succeeded=False)


def test_an_owed_or_unfound_figure_publishes_no_card() -> None:
    owed = _published(
        "Over how many months will you pay it?",
        inputs=[*LOAN[:3], {"name": "periods", "value": None, "source": "user"}, LOAN[4]],
    )
    assert owed.patch == {} and owed.question_field == "periods"
    uncited = [
        *LOAN[:2],
        {**LOAN[2], "source_url": "https://elsewhere.example"},
        *LOAN[3:],
    ]
    unfound = _published("It costs {{payment}}.", inputs=uncited)
    assert unfound.patch == {} and unfound.not_looked_up == ("annual_rate_pct",)


def test_a_declared_input_held_as_text_is_stated_as_the_card_received_it() -> None:
    template = "Starting {{start_date}}, the payment is **{{payment}}** a month."
    published = _published(
        template,
        inputs=[*LOAN, {"name": "start_date", "value": "2026-10-01", "source": "user"}],
    )
    card = ac.card_in(published.patch)
    payment = ac.figure_text(card.presentation.answer)
    assert published.answer_text == (
        f"Starting 2026-10-01, the payment is **{payment}** a month."
    )
    assert published.template is not None
    assert ac.unresolved_references(template, card) == []


def test_a_currency_written_before_a_money_reference_is_not_stated_twice() -> None:
    published = _published(
        "For DOP {{present_value}} or RD$ {{present_value}} at {{annual_rate_pct}} "
        "over {{periods}} months, the payment is {{payment}}."
    )
    card = ac.card_in(published.patch)
    payment = ac.figure_text(card.presentation.answer)
    assert published.answer_text == (
        "For DOP 180,000 or DOP 180,000 at 14% over 48 months, the payment is "
        f"{payment}."
    )


def test_only_an_assumption_that_drives_the_result_must_be_stated() -> None:
    stated = (
        "Paying {{present_value}} at {{annual_rate_pct}} over {{periods}} months "
        "costs {{payment}} a month."
    )
    detail = {"name": "periods_per_year", "value": 12, "source": "assumption"}
    assert _published(stated, inputs=[*LOAN, detail]).template is not None
    rate = {"name": "annual_rate_pct", "value": 14, "source": "assumption"}
    unstated = (
        "Paying {{present_value}} over {{periods}} months costs {{payment}} a month."
    )
    loan = [item for item in LOAN if item["name"] != "annual_rate_pct"]
    assert _published(unstated, inputs=[*loan, rate]).template is None
