"""Structured readout references bind visible occurrences to specific run facts."""

from copy import deepcopy

import pytest
from argus.domain.result_readout_grounding import accepted_readout_text


@pytest.fixture
def fact_sheet():
    values = {
        "portfolio.total_return": (15.126, "percent"),
        "portfolio.annualized_return": (6.846, "percent"),
        "portfolio.annualized_volatility": (28.567, "percent"),
        "portfolio.executed_fills": (17, "count"),
        "portfolio.max_drawdown": (-31.234, "percent"),
        "portfolio.profit": (1234.56, "currency"),
        "window.start": ("2023-09-01", "date"),
    }
    return {
        "schema_version": "result_readout_facts/v1",
        "symbols": ["DOCN"],
        "benchmark_symbol": "SPY",
        "benchmark_comparison_claim": "lagged_benchmark",
        "facts": {
            key: {
                "value": value,
                "unit": unit,
                "meaning": key,
                "scope": "portfolio",
                "basis": "stored_run",
                "provenance": {"kind": "stored", "path": key},
            }
            for key, (value, unit) in values.items()
        },
        "series": {},
    }


def figure(fact_sheet, key, quote, occurrence=1):
    return {
        "fact_key": key,
        "value": fact_sheet["facts"][key]["value"],
        "quote": quote,
        "occurrence": occurrence,
    }


def draft(text, figures=(), language="en"):
    return {"language": language, "text": text, "figures": list(figures)}


@pytest.mark.parametrize("language", ["en", "es-419"])
def test_structured_readout_accepts_exact_fact_bound_rounded_quote(fact_sheet, language):
    text = (
        "Annualized return: 6.8%."
        if language == "en"
        else "Rendimiento anualizado: 6.8%."
    )
    response = draft(
        text, [figure(fact_sheet, "portfolio.annualized_return", "6.8%")], language
    )
    assert accepted_readout_text(response, facts=fact_sheet, language=language) == (
        text,
        None,
    )


@pytest.mark.parametrize("mutation", ["key", "value", "quote", "occurrence"])
def test_structured_readout_rejects_swapped_or_unattached_reference(fact_sheet, mutation):
    ref = figure(fact_sheet, "portfolio.annualized_return", "6.8%")
    invalid = {
        "key": {"fact_key": "portfolio.total_return"},
        "value": {"value": 15.126},
        "quote": {"quote": "15.1%"},
        "occurrence": {"occurrence": 2},
    }
    ref.update(invalid[mutation])
    text, reason = accepted_readout_text(
        draft("Annualized return: 6.8%.", [ref]), facts=fact_sheet, language="en"
    )
    assert text is None
    assert reason == "invalid_figure_reference"


def test_structured_readout_requires_every_visible_number_reference(fact_sheet):
    response = draft(
        "Return was 15.1%, with 17 fills.",
        [figure(fact_sheet, "portfolio.total_return", "15.1%")],
    )
    assert accepted_readout_text(response, facts=fact_sheet, language="en") == (
        None,
        "unreferenced_figure",
    )


@pytest.mark.parametrize("overlap", [False, True])
def test_structured_readout_rejects_duplicate_or_overlapping_references(
    fact_sheet, overlap
):
    ref = figure(fact_sheet, "portfolio.total_return", "15.1%")
    second = deepcopy(ref)
    if overlap:
        second["quote"] = "Return was 15.1%"
    response = draft("Return was 15.1%.", [ref, second])
    assert accepted_readout_text(response, facts=fact_sheet, language="en") == (
        None,
        "invalid_figure_reference",
    )


def test_structured_readout_distinguishes_repeated_occurrences(fact_sheet):
    response = draft(
        "Return was 15.1%. That 15.1% was historical.",
        [figure(fact_sheet, "portfolio.total_return", "15.1%", i) for i in (1, 2)],
    )
    assert accepted_readout_text(response, facts=fact_sheet, language="en") == (
        response["text"],
        None,
    )


@pytest.mark.parametrize("name", ["S&P 500", "S&P\u00a0500", "S&P500"])
def test_identity_name_is_not_an_unreferenced_figure(fact_sheet, name):
    response = draft(f"The benchmark follows the {name}.")
    assert accepted_readout_text(response, facts=fact_sheet, language="en") == (
        response["text"],
        None,
    )


@pytest.mark.parametrize(
    "text", ["S&P 999 was the benchmark.", "The gain was $500.", "Return was 500%."]
)
def test_identity_name_exemption_cannot_allow_a_numeric_claim(fact_sheet, text):
    assert accepted_readout_text(draft(text), facts=fact_sheet, language="en") == (
        None,
        "unreferenced_figure",
    )


def test_reported_language_mismatch_rejects_the_complete_draft(fact_sheet):
    assert accepted_readout_text(
        draft("An uneven ride.", language="en"), facts=fact_sheet, language="es-419"
    ) == (None, "language_mismatch")


def test_readout_without_figures_is_valid_without_required_mentions(fact_sheet):
    response = draft("An uneven historical ride.")
    assert accepted_readout_text(response, facts=fact_sheet, language="en-US") == (
        response["text"],
        None,
    )


@pytest.mark.parametrize(
    "value", [True, False, float("nan"), float("inf"), -float("inf")]
)
def test_reference_value_must_be_finite_and_not_boolean(fact_sheet, value):
    ref = figure(fact_sheet, "portfolio.total_return", "15.1%")
    ref["value"] = value
    assert accepted_readout_text(
        draft("Return: 15.1%.", [ref]), facts=fact_sheet, language="en"
    ) == (None, "invalid_draft")


@pytest.mark.parametrize("unit", ["unknown", "text", "boolean"])
def test_unknown_or_nonnumeric_row_cannot_justify_number(fact_sheet, unit):
    fact_sheet["facts"]["portfolio.total_return"]["unit"] = unit
    ref = figure(fact_sheet, "portfolio.total_return", "15.1%")
    assert accepted_readout_text(
        draft("Return: 15.1%.", [ref]), facts=fact_sheet, language="en"
    ) == (None, "invalid_figure_reference")


@pytest.mark.parametrize(
    "suffix,accepted",
    [
        ("percentage points", True),
        ("puntos porcentuales", True),
        ("pp", True),
        ("%", False),
    ],
)
def test_percentage_points_do_not_become_percent(fact_sheet, suffix, accepted):
    fact_sheet["facts"]["portfolio.total_return"]["unit"] = "percentage_points"
    quote = f"15.1 {suffix}"
    response = draft(
        f"Cost drag: {quote}.", [figure(fact_sheet, "portfolio.total_return", quote)]
    )
    assert accepted_readout_text(response, facts=fact_sheet, language="en") == (
        (response["text"], None) if accepted else (None, "invalid_figure_reference")
    )


@pytest.mark.parametrize(
    "language,quote",
    [
        ("en", "September 2023"),
        ("es-419", "septiembre de 2023"),
        ("en", "September 1, 2023"),
        ("es-419", "1 de septiembre de 2023"),
        ("en", "2023-09-01"),
        ("en", "2023"),
    ],
)
def test_date_reference_validates_visible_date_precision(fact_sheet, language, quote):
    response = draft(
        f"Window: {quote}.", [figure(fact_sheet, "window.start", quote)], language
    )
    assert accepted_readout_text(response, facts=fact_sheet, language=language) == (
        response["text"],
        None,
    )


@pytest.mark.parametrize(
    "language,quote",
    [
        ("en", "October 2023"),
        ("es-419", "octubre de 2023"),
        ("en", "September 2024"),
        ("en", "2024-09-01"),
        ("es-419", "2 de septiembre de 2023"),
    ],
)
def test_date_reference_rejects_wrong_month_year_or_day(fact_sheet, language, quote):
    response = draft(
        f"Window: {quote}.", [figure(fact_sheet, "window.start", quote)], language
    )
    assert accepted_readout_text(response, facts=fact_sheet, language=language) == (
        None,
        "invalid_figure_reference",
    )


def test_referencing_only_year_cannot_hide_wrong_month(fact_sheet):
    response = draft(
        "Window: October 2023.", [figure(fact_sheet, "window.start", "2023")]
    )
    assert accepted_readout_text(response, facts=fact_sheet, language="en") == (
        None,
        "invalid_figure_reference",
    )


@pytest.mark.parametrize(
    "language,text,quote",
    [
        ("en", "There were four winning trades.", "four"),
        ("es-419", "Hubo cuatro operaciones ganadoras.", "cuatro"),
        ("en", "There was one winning trade.", "one"),
        ("es-419", "Hubo una operación ganadora.", "una"),
        ("en", "There were two fills.", "two"),
        ("es-419", "Hubo dos operaciones.", "dos"),
    ],
)
def test_spelled_counts_require_matching_references(fact_sheet, language, text, quote):
    assert accepted_readout_text(
        draft(text, language=language), facts=fact_sheet, language=language
    ) == (None, "unreferenced_figure")
    response = draft(
        text, [figure(fact_sheet, "portfolio.executed_fills", quote)], language
    )
    assert accepted_readout_text(response, facts=fact_sheet, language=language) == (
        None,
        "invalid_figure_reference",
    )


@pytest.mark.parametrize(
    "language,text",
    [
        ("en", "A strategy with an uneven ride."),
        ("es-419", "Una estrategia con un recorrido irregular."),
        ("en", "One strategy had an uneven ride."),
    ],
)
def test_ordinary_articles_are_not_quoted_figures(fact_sheet, language, text):
    assert accepted_readout_text(
        draft(text, language=language), facts=fact_sheet, language=language
    ) == (text, None)


@pytest.mark.parametrize(
    "language,text,quote",
    [
        ("en", "Return was fifteen percent.", "fifteen percent"),
        ("es-419", "El rendimiento fue quince por ciento.", "quince por ciento"),
    ],
)
def test_spelled_percent_preserves_unit_words(fact_sheet, language, text, quote):
    response = draft(
        text, [figure(fact_sheet, "portfolio.total_return", quote)], language
    )
    assert accepted_readout_text(response, facts=fact_sheet, language=language) == (
        text,
        None,
    )


def test_raw_reference_spans_checked_before_punctuation_normalization(fact_sheet):
    text = "Return was 15.1% — an uneven ride."
    response = draft(text, [figure(fact_sheet, "portfolio.total_return", "15.1% —")])
    assert accepted_readout_text(response, facts=fact_sheet, language="en") == (
        "Return was 15.1%, an uneven ride.",
        None,
    )


def test_sp500_name_requires_supplied_spy_identity(fact_sheet):
    fact_sheet["benchmark_symbol"] = "BTC"
    assert accepted_readout_text(
        draft("Compared with S&P 500."), facts=fact_sheet, language="en"
    ) == (None, "unreferenced_figure")


@pytest.mark.parametrize(
    "quote", ["$1,235", "$ 1\u202f235", "1235 dólares", "1235 dolares", "$1.235k"]
)
def test_currency_quote_formats_preserve_rounding(fact_sheet, quote):
    response = draft(f"Profit: {quote}.", [figure(fact_sheet, "portfolio.profit", quote)])
    assert accepted_readout_text(response, facts=fact_sheet, language="en") == (
        response["text"],
        None,
    )


@pytest.mark.parametrize("quote", ["$1,234", "$999k", "$1e9", "$31.2"])
def test_explicit_false_currency_not_excused_by_other_numbers(fact_sheet, quote):
    response = draft(f"Profit: {quote}.", [figure(fact_sheet, "portfolio.profit", quote)])
    assert accepted_readout_text(response, facts=fact_sheet, language="en") == (
        None,
        "invalid_figure_reference",
    )


@pytest.mark.parametrize(
    "presentation,unit,value,quote,expected",
    [
        ([], "count", 17, "17%", False),
        ([], "percentage_points", 0.234, "0.23%", False),
        ([], "ratio", 0.57, "57%", False),
        (["fraction_as_percent"], "ratio", 0.57, "57%", True),
        (["absolute_magnitude"], "percent", -31.234, "31.2%", True),
        ([], "percent", -31.234, "31.2%", False),
        (["basis_points_as_percentage_points"], "basis_points", 5, ".05pp", True),
        (["basis_points_as_percentage_points"], "basis_points", 5, ".05%", False),
        ([], "basis_points", 5, "5bps", True),
        ([], "basis_points", 5, "5 bps", True),
    ],
)
def test_only_declared_unit_conversions_are_valid(
    fact_sheet, presentation, unit, value, quote, expected
):
    row = fact_sheet["facts"]["portfolio.total_return"]
    row.update(value=value, unit=unit, presentation=presentation)
    response = draft(
        f"Observed: {quote}.", [figure(fact_sheet, "portfolio.total_return", quote)]
    )
    assert accepted_readout_text(response, facts=fact_sheet, language="en") == (
        (response["text"], None) if expected else (None, "invalid_figure_reference")
    )


@pytest.mark.parametrize(
    "language,text,quote",
    [
        ("en", "There were seventeen fills.", "seventeen"),
        ("es-419", "Hubo diecisiete operaciones.", "diecisiete"),
    ],
)
def test_truthful_spelled_cardinals_accept_exact_references(
    fact_sheet, language, text, quote
):
    response = draft(
        text, [figure(fact_sheet, "portfolio.executed_fills", quote)], language
    )
    assert accepted_readout_text(response, facts=fact_sheet, language=language) == (
        text,
        None,
    )


@pytest.mark.parametrize("quote", ["17%", "$17", "Sharpe 17"])
def test_explicit_unit_cannot_be_justified_with_fill_count(fact_sheet, quote):
    response = draft(quote, [figure(fact_sheet, "portfolio.executed_fills", quote)])
    assert accepted_readout_text(response, facts=fact_sheet, language="en") == (
        None,
        "invalid_figure_reference",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize(
    "failure",
    [
        None,
        "language_mismatch",
        "unreferenced_figure",
        "invalid_figure_reference",
        "provider_error",
    ],
)
async def test_composer_one_call_and_complete_fallback_with_precise_reason(
    surface, failure, monkeypatch
):
    from argus.agent_runtime.stages import explain
    from argus.agent_runtime.state.models import RunState
    from argus.api.chat import breakdown
    from argus.domain.research.contracts import ResearchUsage
    from argus.domain.research.perplexity_agent import StructuredAgentResult

    calls = []
    text = "El recorrido histórico fue irregular."
    language = "en" if failure == "language_mismatch" else "es-419"
    response = draft(text, language=language)
    if failure in {"unreferenced_figure", "invalid_figure_reference"}:
        response["text"] += " El rendimiento fue 99%."
    if failure == "invalid_figure_reference":
        response["figures"] = [
            {
                "fact_key": "portfolio.total_return",
                "value": 99,
                "quote": "99%",
                "occurrence": 1,
            }
        ]
    result = {
        "metrics": {
            "aggregate": {
                "performance": {
                    "total_return_pct": 15.126,
                    "benchmark_return_pct": 20.421,
                    "delta_vs_benchmark_pct": -5.295,
                }
            }
        },
        "config_snapshot": {"template": "buy_and_hold", "starting_capital": 10000},
        "symbols": ["DOCN"],
        "benchmark_symbol": "SPY",
    }

    def invoke(**kwargs):
        calls.append(kwargs)
        if failure == "provider_error":
            raise RuntimeError("provider unavailable")
        return response

    if surface == "quick_take":

        async def async_invoke(**kwargs):
            return invoke(**kwargs)

        monkeypatch.setattr(explain, "invoke_openrouter_json_schema", async_invoke)
        state = RunState.new(current_user_message="Explain", recent_thread_history=[])
        state.final_response_payload = {"result": result}
        state.confirmation_payload = {
            "strategy": {
                "strategy_type": "buy_and_hold",
                "asset_universe": result["symbols"],
            },
            "optional_parameters": {},
        }
        stage = await explain.explain_stage_async(state=state, language="es-419")
        patch = stage.stage_patch
        rendered = patch["assistant_response"]
        used_fallback = patch["assistant_response_fallback_used"]
        reason = patch.get("assistant_response_failure_mode")
        source = patch["assistant_response_source"]
    else:

        class Client:
            def run_structured(self, prompt, spec, **kwargs):
                return StructuredAgentResult(
                    draft={
                        **invoke(prompt=prompt, spec=spec, **kwargs),
                        "source_figures": [],
                        "citations": [],
                    },
                    sources=(),
                    usage=ResearchUsage(model=spec.model),
                    tool_results=(),
                    provider_response_id=None,
                )

        monkeypatch.setattr(
            breakdown,
            "result_breakdown_context",
            lambda run: {**result, "raw_metrics": result["metrics"]},
        )
        message = breakdown.result_breakdown_message_with_metadata(
            object(), language="es-419", client=Client()
        )
        rendered, used_fallback, reason, source = (
            message.text,
            message.fallback_used,
            message.failure_mode,
            message.source,
        )
    assert len(calls) == 1
    assert used_fallback is bool(failure)
    if failure:
        assert text not in rendered
        expected = (
            (
                explain.RESULT_READOUT_FAILURE_LLM_UNAVAILABLE
                if surface == "quick_take"
                else "llm_unavailable_or_contract_rejected"
            )
            if failure == "provider_error"
            else failure
        )
        assert reason == expected
        assert source == "deterministic_fallback"
    else:
        assert rendered == text
        assert reason is None


@pytest.mark.parametrize("language", [None, "", "fr", 123])
def test_breakdown_unsupported_requested_language_never_uses_context_locale(language):
    from argus.api.chat.breakdown import _llm_result_breakdown_with_metadata

    calls = []

    class Client:
        def run_structured(self, *args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("Unsupported language must not call the provider")

    assert _llm_result_breakdown_with_metadata(
        {"language": "en"}, language=language, client=Client()
    ) == (None, "language_mismatch", None, ())
    assert calls == []


@pytest.mark.parametrize(
    "quote,accepted",
    [("$1,235", True), ("1235 USD", True), ("€1,235", False), ("1235 EUR", False)],
)
def test_explicit_currency_must_match_supplied_currency(fact_sheet, quote, accepted):
    fact_sheet["facts"]["portfolio.profit"]["currency"] = "USD"
    response = draft(f"Profit: {quote}.", [figure(fact_sheet, "portfolio.profit", quote)])
    assert accepted_readout_text(response, facts=fact_sheet, language="en") == (
        (response["text"], None) if accepted else (None, "invalid_figure_reference")
    )


def test_malformed_numeric_exponent_falls_back_atomically(fact_sheet):
    quote = "1e" + "9" * 5000 + "%"
    response = draft(
        f"Return: {quote}.", [figure(fact_sheet, "portfolio.total_return", quote)]
    )
    assert accepted_readout_text(response, facts=fact_sheet, language="en") == (
        None,
        "invalid_figure_reference",
    )


@pytest.mark.parametrize(
    "text",
    [
        "ResultReadoutFigure is available.",
        "Inspect `figures`.",
        'The output has "language": "en".',
    ],
)
def test_new_schema_names_and_fields_stay_internal(fact_sheet, text):
    assert accepted_readout_text(draft(text), facts=fact_sheet, language="en") == (
        None,
        "internal_field_name",
    )


@pytest.mark.parametrize(
    "quote",
    [
        "October, 2023",
        "October of 2023",
        "October2023",
        "octubre, 2023",
        "octubre del 2023",
    ],
)
def test_whole_date_recognition_prevents_wrong_month_hiding_behind_year(
    fact_sheet, quote
):
    language = "es-419" if "octubre" in quote else "en"
    response = draft(
        f"Window: {quote}.", [figure(fact_sheet, "window.start", "2023")], language
    )
    assert accepted_readout_text(response, facts=fact_sheet, language=language) == (
        None,
        "invalid_figure_reference",
    )


@pytest.mark.parametrize(
    "language,quote",
    [
        ("en", "September, 2023"),
        ("en", "September of 2023"),
        ("en", "September2023"),
        ("es-419", "septiembre, 2023"),
        ("es-419", "septiembre del 2023"),
    ],
)
def test_truthful_whole_date_punctuation_and_connectors(fact_sheet, language, quote):
    response = draft(
        f"Window: {quote}.", [figure(fact_sheet, "window.start", quote)], language
    )
    assert accepted_readout_text(response, facts=fact_sheet, language=language) == (
        response["text"],
        None,
    )


@pytest.mark.parametrize("currency", ["euros", "pounds", "libras"])
def test_written_currency_names_cannot_change_usd(fact_sheet, currency):
    fact_sheet["facts"]["portfolio.profit"]["currency"] = "USD"
    quote = f"1235 {currency}"
    response = draft(f"Profit: {quote}.", [figure(fact_sheet, "portfolio.profit", quote)])
    assert accepted_readout_text(response, facts=fact_sheet, language="en") == (
        None,
        "invalid_figure_reference",
    )


def test_indefinite_article_does_not_inherit_prior_count_unit(fact_sheet):
    text = "Se ejecutaron diecisiete trades, con una entrada el 1 de septiembre de 2023."
    response = draft(
        text,
        [
            figure(fact_sheet, "portfolio.executed_fills", "diecisiete"),
            figure(fact_sheet, "window.start", "1 de septiembre de 2023"),
        ],
        "es-419",
    )
    assert accepted_readout_text(response, facts=fact_sheet, language="es-419") == (
        text,
        None,
    )
