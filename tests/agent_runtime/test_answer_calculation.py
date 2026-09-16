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
    return _published_many(
        template,
        [_request("time_value", inputs, solve_for)],
        notes=notes,
        language=language,
    )


def _published_many(template, requests, *, notes=None, language="en"):
    return ac.publish_calculations(
        requests,
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


def test_a_stated_money_currency_overrides_the_profile_default() -> None:
    notes: list[str] = []
    inputs = [
        LOAN[0],
        {"name": "present_value", "value": 1200, "source": "user", "currency": "USD"},
        *LOAN[2:],
    ]
    resolved = _resolve(_request("time_value", inputs, solve_for="payment"), notes=notes)
    assert resolved.computable
    assert resolved.arguments["currency"] == "USD"
    assert ac.CURRENCY_MISMATCH_REASON_CODE not in notes


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
        "cards": {"calculation_1": card.artifact_id},
        "text": template,
        "language": "en",
    }


def test_an_unknown_reference_hands_over_to_argus_lead_and_cited_digits_stand() -> None:
    notes: list[str] = []
    published = _published("It costs {{monthly_cost}}.", notes=notes)
    for card in ac.cards_in(published.patch):
        assert ac.figure_text(card.presentation.answer) in published.answer_text
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


def test_an_assumption_the_prose_does_not_name_is_listed_and_the_prose_stands() -> None:
    inputs = [
        *LOAN[:4],
        {"name": "periods_per_year", "value": 12, "source": "user"},
        {"name": "payment_timing", "value": "end", "source": "user"},
        {"name": "future_value", "value": 0, "source": "assumption"},
    ]
    notes: list[str] = []
    unnamed = _published("It costs {{payment}} a month.", inputs=inputs, notes=notes)
    card = ac.card_in(unnamed.patch)
    assert unnamed.template is not None
    assert unnamed.answer_text == (
        f"It costs {ac.figure_text(card.presentation.answer)} a month."
    )
    assert unnamed.assumptions == (
        {"artifact_id": card.artifact_id, "name": "future_value"},
    )
    named = _published(
        "Assuming the loan ends at {{future_value}}, it costs {{payment}} a month.",
        inputs=inputs,
    )
    assert named.template is not None and named.assumptions == ()


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
    assert ac.unresolved_references(template, {"calculation_1": card}) == []


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


def test_every_unnamed_assumption_is_listed_and_only_a_driving_one_is_recorded() -> None:
    stated = (
        "Paying {{present_value}} at {{annual_rate_pct}} over {{periods}} months "
        "costs {{payment}} a month."
    )
    detail = {"name": "periods_per_year", "value": 12, "source": "assumption"}
    quiet: list[str] = []
    timing = {"name": "payment_timing", "value": "end", "source": "user"}
    listed = _published(stated, inputs=[*LOAN, detail, timing], notes=quiet)
    assert listed.template is not None
    assert [item["name"] for item in listed.assumptions] == ["periods_per_year"]
    assert ac.FIGURE_CHECK_REASON_CODE not in quiet
    rate = {"name": "annual_rate_pct", "value": 14, "source": "assumption"}
    unstated = (
        "Paying {{present_value}} over {{periods}} months costs {{payment}} a month."
    )
    loan = [item for item in LOAN if item["name"] != "annual_rate_pct"]
    recorded: list[str] = []
    per_year = {"name": "periods_per_year", "value": 12, "source": "user"}
    driving = _published(unstated, inputs=[*loan, rate, per_year, timing], notes=recorded)
    assert driving.template is not None, "the prose stands"
    assert [item["name"] for item in driving.assumptions] == ["annual_rate_pct"]
    assert ac.FIGURE_CHECK_REASON_CODE in recorded


def test_the_prose_audit_counts_only_figures_with_no_row_or_calculation_value() -> None:
    card = ac.card_in(
        _published(
            "Paying {{present_value}} over {{periods}} months costs {{payment}}."
        ).patch
    )
    payment = card.presentation.answer.value
    prose = (
        f"At 14% over 48 months the payment is DOP {payment:,.2f}. Inflation was 3,1% "
        "in 2025, revenue reached 33.72 billion on 2026-09-11, and costs rose 22%."
    )
    assert ac.unsourced_prose_figures(
        prose, cited=[3.1, 33_720_000_000], cards=[card]
    ) == ["22%"]
    assert ac.unsourced_prose_figures("Nothing to count here.", cited=[], cards=[]) == []


def test_a_unit_written_after_a_reference_is_not_stated_twice() -> None:
    published = _published(
        "Paying {{present_value}} DOP at {{annual_rate_pct}}% over {{periods}} months "
        "costs {{payment}} DOP a month."
    )
    assert published.template is not None
    assert published.answer_text.count("DOP") == 2
    assert "%%" not in published.answer_text and "14%" in published.answer_text


def test_an_offer_keeps_its_prose_and_leaves_out_what_leans_on_a_result() -> None:
    card = ac.card_in(
        _published(
            "Paying {{present_value}} over {{periods}} months costs {{payment}}."
        ).patch
    )
    template = (
        "You owe {{present_value}}. At that balance the payment is {{nowhere}}.\n\n"
        "| Input | Value |\n|---|---|\n| Payment | {{nowhere}} |\n| Rate | {{annual_rate_pct}} |"
    )
    text, dropped = ac.render_offer_prose(template, {"calculation_1": card})
    assert text.startswith("You owe DOP 180,000.")
    assert "{{" not in text and "| Rate | 14% |" in text
    assert dropped == 2


def test_the_prose_audit_skips_day_numbers_and_model_names() -> None:
    prose = (
        "A Porsche 911 cost $135,500 on September 12, 2025, an iPhone 16 costs less, "
        "and a 911 needs 22% of income."
    )
    assert ac.unsourced_prose_figures(
        prose, cited=[135_500], cards=[], names=["Porsche 911 starting MSRP"]
    ) == ["22%"]


def test_a_figure_from_finance_data_is_cited_without_the_provider_url() -> None:
    from argus.domain.research.contracts import RetrievedRow

    evidence = [
        RetrievedRow(
            subject="NVIDIA",
            symbol="NVDA",
            label="trailing diluted EPS",
            value=7.91,
            kind="currency",
            unit="USD",
            as_of="2026-07-26",
            source_url=None,
        )
    ]
    request = _request(
        "price_multiple",
        [
            {"name": "price", "value": 218.29, "source": "user", "currency": "USD"},
            {
                "name": "per_share",
                "value": 7.91,
                "source": "page",
                "source_url": "https://finance.example/provider/NVDA",
                "as_of": "2026-07-26",
                "currency": "USD",
            },
        ],
        "multiple",
    )
    notes: list[str] = []
    resolved = ac.resolve_calculation(
        request,
        catalog=get_tool_catalog(),
        retrieved=[],
        currency="USD",
        subject_symbol="NVDA",
        market_close=_close,
        notes=notes,
        evidence=evidence,
    )
    assert resolved is not None and resolved.computable, notes
    source = resolved.arguments["sources"]["per_share"]
    assert source["kind"] == "page" and source.get("url") is None
    assert source["title"] == "NVIDIA trailing diluted EPS"
    assert source["date"] == "2026-07-26"
    unevidenced = ac.resolve_calculation(
        request,
        catalog=get_tool_catalog(),
        retrieved=[],
        currency="USD",
        subject_symbol="NVDA",
        market_close=_close,
        notes=[],
    )
    assert unevidenced is not None and "per_share" in unevidenced.not_looked_up


LOAN_AT_12 = [
    {**item, "value": 12} if item["name"] == "annual_rate_pct" else item for item in LOAN
]


def _named(name: str, inputs: list[dict[str, Any]], solve_for: str = "payment"):
    return AnswerCalculation.model_validate(
        {"name": name, "kind": "time_value", "solve_for": solve_for, "inputs": inputs}
    )


def test_each_option_computes_its_own_card_and_the_prose_names_each() -> None:
    template = (
        "At {{bank_a.annual_rate_pct}} the payment is {{bank_a.payment}}; at "
        "{{bank_b.annual_rate_pct}} it is {{bank_b.payment}}."
    )
    published = _published_many(
        template, [_named("Bank A", LOAN), _named("Bank B", LOAN_AT_12)]
    )
    cards = ac.cards_in(published.patch)
    assert [card.arguments["annual_rate_pct"] for card in cards] == [14, 12]
    first, second = (ac.figure_text(card.presentation.answer) for card in cards)
    assert first != second
    assert (
        published.answer_text == f"At 14% the payment is {first}; at 12% it is {second}."
    )
    assert published.template == {
        "cards": {"bank_a": cards[0].artifact_id, "bank_b": cards[1].artifact_id},
        "text": template,
        "language": "en",
    }


def test_a_reference_two_options_both_hold_is_never_guessed() -> None:
    notes: list[str] = []
    published = _published_many(
        "The payment is {{payment}}.",
        [_named("a", LOAN), _named("b", LOAN_AT_12)],
        notes=notes,
    )
    assert published.template is None
    for card in ac.cards_in(published.patch):
        assert ac.figure_text(card.presentation.answer) in published.answer_text
    assert ac.FIGURE_CHECK_REASON_CODE in notes


def test_an_option_that_cannot_compute_holds_back_every_card() -> None:
    uncited = [
        {**item, "source_url": "https://elsewhere.example"}
        if item["name"] == "annual_rate_pct"
        else item
        for item in LOAN
    ]
    held = _published_many(
        "{{a.payment}} or {{b.payment}}", [_named("a", LOAN), _named("b", uncited)]
    )
    assert held.patch == {} and held.not_looked_up == ("annual_rate_pct",)
    owing = [
        {"name": "periods", "value": None, "source": "user"}
        if item["name"] == "periods"
        else item
        for item in LOAN
    ]
    asked = _published_many(
        "{{a.payment}} or {{b.payment}}",
        [
            _named("a", owing),
            _named(
                "b",
                [
                    {**item, "value": 12} if item["name"] == "annual_rate_pct" else item
                    for item in owing
                ],
            ),
        ],
    )
    assert asked.patch == {} and asked.owed == ("periods",)


def test_a_calculation_named_in_the_readers_language_still_reads() -> None:
    published = _published_many(
        "En dólares paga {{dólares.payment}} al mes.",
        [_named("Dólares", LOAN)],
        language="es-419",
    )
    card = ac.card_in(published.patch)
    payment = ac.figure_text(card.presentation.answer)
    assert published.answer_text == f"En dólares paga {payment} al mes."
    assert published.template is not None
    assert ac.template_cards(published.template) == {"dolares": card.artifact_id}


def test_a_template_stored_before_answers_carried_several_reads_its_one_card() -> None:
    card = ac.card_in(_published("It costs {{payment}}.").patch)
    stored = {
        "artifact_id": card.artifact_id,
        "text": "It costs {{payment}}.",
        "language": "en",
    }
    assert ac.template_cards(stored) == {"calculation": card.artifact_id}
    text, failure = ac.render_answer_text(stored["text"], {"calculation": card})
    assert failure is None
    assert text == f"It costs {ac.figure_text(card.presentation.answer)}."
