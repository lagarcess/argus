"""Both model readouts accept richer stored facts and reject false visible claims."""

import json
from copy import deepcopy

import pytest
from argus.agent_runtime.stages import explain
from argus.agent_runtime.state.models import RunState
from argus.api.chat import breakdown
from argus.domain.research.contracts import ResearchUsage
from argus.domain.research.perplexity_agent import StructuredAgentResult

from tests.result_readout_fixtures import (
    readout_draft,
    scalar_leaves,
    stored_scalar_values,
)


@pytest.fixture
def stored_result():
    return {
        "metrics": {
            "aggregate": {
                "performance": {
                    "total_return_pct": 15.126,
                    "benchmark_return_pct": 20.421,
                    "delta_vs_benchmark_pct": -5.295,
                    "annualized_return_pct": 6.846,
                    "execution_realism": {"enabled": True, "return_drag_pct": 0.234},
                },
                "risk": {"max_drawdown_pct": -31.234, "volatility_annual_pct": 28.567},
                "efficiency": {"sharpe_ratio": 0.456, "total_trades": 17},
            },
            "by_symbol": {"DOCN": {"efficiency": {"profit_factor": 1.876}}},
        },
        "config_snapshot": {"template": "buy_and_hold", "starting_capital": 10000},
        "symbols": ["DOCN"],
        "benchmark_symbol": "SPY",
        "date_range": {"start": "2023-09-01", "end": "2026-09-09"},
    }


async def compose(surface, text, result, monkeypatch, language="en", figures=()):
    captured = {}

    def draft(**kwargs):
        captured.update(kwargs)
        captured["prompt"] = kwargs["messages"][1]["content"]
        return readout_draft(text, figures, language=language)

    if surface == "breakdown":

        class Client:
            def run_structured(self, prompt, spec, **kwargs):
                captured.update(prompt=prompt, spec=spec, **kwargs)
                return StructuredAgentResult(
                    draft={
                        **readout_draft(text, figures, language=language),
                        "source_figures": [],
                        "citations": [],
                    },
                    sources=(),
                    usage=ResearchUsage(model=spec.model),
                    tool_results=(),
                    provider_response_id=None,
                )

        rendered = breakdown.llm_result_breakdown_message(
            {**result, "raw_metrics": result["metrics"]},
            language=language,
            client=Client(),
        )
        return rendered, captured

    async def async_draft(**kwargs):
        return draft(**kwargs)

    monkeypatch.setattr(explain, "invoke_openrouter_json_schema", async_draft)
    state = RunState.new(current_user_message="Explain", recent_thread_history=[])
    state.final_response_payload = {"result": result}
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "asset_universe": result["symbols"],
        },
        "optional_parameters": {},
    }
    response = await explain.explain_stage_async(state=state, language=language)
    patch = response.stage_patch
    rendered = (
        None if patch["assistant_response_fallback_used"] else patch["assistant_response"]
    )
    return rendered, captured


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize(
    "language,text,figures",
    [
        (
            "en",
            "Annualized return was 6.8%, volatility 28.6%, Sharpe 0.46, with 17 fills. The 31.2% worst drop illustrates about $3,123 on $10,000 of starting capital; that is not the actual dollar loss from the portfolio's peak.",
            [
                ("portfolio.annualized_return", 6.846, "6.8%"),
                ("portfolio.annualized_volatility", 28.567, "28.6%"),
                ("portfolio.sharpe_ratio", 0.456, "0.46"),
                ("portfolio.executed_fills", 17.0, "17"),
                ("portfolio.max_drawdown", -31.234, "31.2%"),
                ("portfolio.drawdown_illustration", 3123.4, "$3,123"),
                ("configuration.starting_capital", 10000.0, "$10,000"),
            ],
        ),
        (
            "es-419",
            "El rendimiento anualizado fue 6,8%, la volatilidad 28,6% y Sharpe 0,46. Hubo 17 operaciones y el factor de beneficio fue 1,88.",
            [
                ("portfolio.annualized_return", 6.846, "6,8%"),
                ("portfolio.annualized_volatility", 28.567, "28,6%"),
                ("portfolio.sharpe_ratio", 0.456, "0,46"),
                ("portfolio.executed_fills", 17.0, "17"),
                ("symbol.DOCN.profit_factor", 1.876, "1,88"),
            ],
        ),
    ],
)
async def test_readout_accepts_richer_rounded_metrics_without_forced_mentions(
    surface, language, text, stored_result, monkeypatch, figures
):
    rendered, captured = await compose(
        surface, text, stored_result, monkeypatch, language, figures=figures
    )
    assert rendered == text
    context = json.loads(captured["prompt"])
    assert {
        path: value
        for path, value in stored_scalar_values(context["run_facts"]).items()
        if path.startswith("metrics.")
    } == scalar_leaves(stored_result["metrics"], "metrics")
    assert context["product_language"] == language


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize(
    "provider_location", ["root", "resolved_parameters", "engine_config"]
)
async def test_readout_model_inputs_omit_provenance_and_preserve_run_evidence(
    surface, provider_location, stored_result, monkeypatch, faker
):
    from argus.domain.engine_launch.adapter import _provider_metadata

    execution = {
        **stored_result["config_snapshot"],
        "asset_class": "equity",
        "timeframe": "1D",
        "fee_bps": 5,
        "slippage_bps": 10,
        "date_range": stored_result["date_range"],
    }
    snapshot = deepcopy(execution)
    provenance = _provider_metadata(asset_class="equity", timeframe="1D")
    if provider_location == "root":
        snapshot["provider_metadata"] = provenance
    else:
        snapshot[provider_location] = {"provider_metadata": provenance}
    chart = {
        "kind": "portfolio_equity",
        "currency": "USD",
        "base_value": execution["starting_capital"],
        "series": [{"time": "2023-09-01", "value": 10000}],
        "markers": [{"time": "2023-09-01", "price": 32.45}],
        "marker_summary": {"total_groups": 1, "included_groups": 1, "sampled": False},
        "attribution": faker.company(),
    }
    result = {**stored_result, "config_snapshot": snapshot, "chart": chart}
    before = deepcopy(result)

    rendered, captured = await compose(
        surface, "The ride was uneven.", result, monkeypatch
    )

    assert rendered == "The ride was uneven."
    facts = json.loads(captured["prompt"])["run_facts"]
    scalars = stored_scalar_values(facts)
    assert {
        path: value
        for path, value in scalars.items()
        if path.startswith("configuration.")
    } == scalar_leaves(execution, "configuration")
    assert {
        path: value for path, value in scalars.items() if path.startswith("metrics.")
    } == scalar_leaves(stored_result["metrics"], "metrics")
    assert facts["series"]["portfolio_equity"]["points"] == chart["series"]
    assert facts["series"]["execution_markers"]["points"] == chart["markers"]
    assert {
        path: value for path, value in scalars.items() if path.startswith("chart.")
    } == scalar_leaves(
        {
            key: value
            for key, value in chart.items()
            if key not in {"series", "markers", "attribution"}
        },
        "chart",
    )
    assert "provider_metadata" not in json.dumps(facts)
    assert chart["attribution"] not in json.dumps(facts)
    assert result == before


@pytest.mark.asyncio
@pytest.mark.parametrize("with_chart", [True, False])
async def test_production_quick_take_uses_optional_card_chart_for_ending_value(
    with_chart, stored_result, monkeypatch
):
    from argus.agent_runtime.result_readout import (
        result_readout_with_metadata_from_backtest_payload_async,
    )

    captured = {}
    text = "The ending value was $11,513."

    async def draft(**kwargs):
        captured.update(kwargs)
        return readout_draft(text, [("portfolio.ending_equity", 11512.6, "$11,513")])

    monkeypatch.setattr(explain, "invoke_openrouter_json_schema", draft)
    card = {}
    if with_chart:
        card["chart"] = {
            "kind": "portfolio_equity",
            "currency": "USD",
            "series": [
                {"time": stored_result["date_range"]["start"], "value": 10000},
                {"time": stored_result["date_range"]["end"], "value": 11512.6},
            ],
        }
    response = await result_readout_with_metadata_from_backtest_payload_async(
        request={"symbols": stored_result["symbols"], "strategy_type": "buy_and_hold"},
        envelope={
            "metrics": stored_result["metrics"],
            "resolved_strategy": {"strategy_type": "buy_and_hold"},
            "resolved_parameters": {
                **stored_result["config_snapshot"],
                "benchmark_symbol": stored_result["benchmark_symbol"],
                "date_range": stored_result["date_range"],
            },
        },
        result_card=card,
        explanation_context=None,
    )
    facts = json.loads(captured["messages"][1]["content"])["run_facts"]
    assert response.fallback_used is not with_chart
    if with_chart:
        assert response.text == text
        assert facts["series"]["portfolio_equity"]["points"] == card["chart"]["series"]
    else:
        assert "portfolio_equity" not in facts["series"]
        assert response.failure_mode == "invalid_figure_reference"


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize(
    "text,figures,language",
    [
        ("DOCN returned 99.9%.", [("portfolio.total_return", 15.126, "99.9%")], "en"),
        ("The Sharpe ratio was 8.88.", [("portfolio.sharpe_ratio", 0.456, "8.88")], "en"),
        ("There were 999 fills.", [("portfolio.executed_fills", 17.0, "999")], "en"),
        (
            "The drop illustrates $9,876 of the starting capital.",
            [("portfolio.drawdown_illustration", 3123.4, "$9,876")],
            "en",
        ),
        (
            "DOCN beat SPY by 5.3 percentage points.",
            [("portfolio.benchmark_gap", -5.295, "5.3 percentage points")],
            "en",
        ),
        (
            "DOCN superó a SPY por 5,3 puntos porcentuales.",
            [("portfolio.benchmark_gap", -5.295, "5,3 puntos porcentuales")],
            "es-419",
        ),
        (
            "SPY lagged DOCN by 5.3 percentage points.",
            [("portfolio.benchmark_gap", -5.295, "5.3 percentage points")],
            "en",
        ),
        (
            "The total_return_pct was 15.1%.",
            [("portfolio.total_return", 15.126, "15.1%")],
            "en",
        ),
        ("The schema_version gives the result.", [], "en"),
        ("The result was 1.2.3%.", [("portfolio.total_return", 15.126, "1.2.3%")], "en"),
        ("The QuickTakeDraft says the ride was uneven.", [], "en"),
        ("The ResultBreakdownDraft says the ride was uneven.", [], "en"),
    ],
)
async def test_readout_rejects_complete_draft_with_false_statement(
    surface, text, stored_result, monkeypatch, figures, language
):
    rendered, _ = await compose(
        surface, text, stored_result, monkeypatch, figures=figures, language=language
    )
    assert rendered is None


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize(
    "text,figures,language",
    [
        (
            "DOCN lagged SPY by 5.3 percentage points.",
            [("portfolio.benchmark_gap", -5.295, "5.3 percentage points")],
            "en",
        ),
        (
            "SPY beat DOCN by 5.3 percentage points.",
            [("portfolio.benchmark_gap", -5.295, "5.3 percentage points")],
            "en",
        ),
        ("DOCN did not beat SPY.", [], "en"),
        ("DOCN no superó a SPY.", [], "es-419"),
        (
            "The spread was -5.3 percentage points versus SPY.",
            [("portfolio.benchmark_gap", -5.295, "-5.3 percentage points")],
            "en",
        ),
        (
            "DOCN quedó por debajo de SPY por 5,3 puntos porcentuales.",
            [("portfolio.benchmark_gap", -5.295, "5,3 puntos porcentuales")],
            "es-419",
        ),
    ],
)
async def test_readout_accepts_truthful_comparison_without_content_caps(
    surface, text, stored_result, monkeypatch, figures, language
):
    rendered, _ = await compose(
        surface, text, stored_result, monkeypatch, figures=figures, language=language
    )
    assert rendered == text


def test_breakdown_context_retains_optional_chart_and_prior_quick_take(
    stored_result, faker
):
    run = breakdown.BacktestRun(
        id=faker.uuid4(),
        conversation_id=faker.uuid4(),
        status="completed",
        asset_class="equity",
        allocation_method="equal_weight",
        created_at=faker.iso8601(),
        **deepcopy(stored_result),
        chart={"series": [{"values": [10000, 11512.6]}]},
        conversation_result_card={
            "result_readout_content": {
                "schema_version": "result_readout/v1",
                "surface": "quick_take",
                "language": "en",
                "text": "An uneven historical ride.",
            }
        },
    )
    context = breakdown.result_breakdown_context(run)
    assert context["chart"] == run.chart
    assert context["prior_quick_take"] == "An uneven historical ride."


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize(
    "text,figures,language",
    [
        (
            "Sharpe was 1.234. The win rate was 57%.",
            [
                ("portfolio.sharpe_ratio", 1.234, "1.234"),
                ("portfolio.win_rate", 0.57, "57%"),
            ],
            "en",
        ),
        (
            "Sharpe fue 1,234. La tasa de aciertos fue 57%.",
            [
                ("portfolio.sharpe_ratio", 1.234, "1,234"),
                ("portfolio.win_rate", 0.57, "57%"),
            ],
            "es-419",
        ),
        ("The profit was $1,234.", [("portfolio.profit", 1234.0, "$1,234")], "en"),
    ],
)
async def test_readouts_understand_decimal_precision_and_typed_ratio_percentages(
    surface, text, stored_result, monkeypatch, figures, language
):
    metrics = stored_result["metrics"]["aggregate"]
    metrics["efficiency"].update(sharpe_ratio=1.234, win_rate=0.57)
    metrics["performance"]["profit"] = 1234
    rendered, _ = await compose(
        surface, text, stored_result, monkeypatch, figures=figures, language=language
    )
    assert rendered == text


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize("grouping", [" ", "\u00a0", "\u202f"])
@pytest.mark.parametrize("currency_gap", ["", " ", "\u00a0", "\u202f"])
async def test_readouts_accept_grouped_money_and_currency_whitespace(
    surface, grouping, currency_gap, stored_result, monkeypatch
):
    stored_result["metrics"]["aggregate"]["performance"]["profit"] = 1234.56
    text = f"El capital fue ${currency_gap}10{grouping}000 y la ganancia ${currency_gap}1{grouping}234,56."
    rendered, _ = await compose(
        surface,
        text,
        stored_result,
        monkeypatch,
        "es-419",
        figures=[
            (
                "configuration.starting_capital",
                10000.0,
                f"${currency_gap}10{grouping}000",
            ),
            ("portfolio.profit", 1234.56, f"${currency_gap}1{grouping}234,56"),
        ],
    )
    assert rendered == text


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize(
    "text,figures,language",
    [
        (
            "Holding shares in DigitalOcean (DOCN) since September 2023.",
            [("window.start", "2023-09-01", "September 2023")],
            "en",
        ),
        (
            "Comprar y mantener acciones de DigitalOcean (DOCN) desde septiembre de 2023.",
            [("window.start", "2023-09-01", "septiembre de 2023")],
            "es-419",
        ),
        (
            "Comprar y mantener acciones de DOCN desde septiembre de 2023.",
            [("window.start", "2023-09-01", "septiembre de 2023")],
            "es-419",
        ),
        (
            "Shares were held; the period began in September 2023.",
            [("window.start", "2023-09-01", "September 2023")],
            "en",
        ),
    ],
)
async def test_readout_year_does_not_inherit_a_previous_clause_unit(
    surface, text, stored_result, monkeypatch, figures, language
):
    rendered, _ = await compose(
        surface, text, stored_result, monkeypatch, figures=figures, language=language
    )
    assert rendered == text


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
async def test_readouts_preserve_parenthetical_unit_labels(
    surface, stored_result, monkeypatch
):
    text = "Capital (USD) 10,000. Sharpe (risk-adjusted) 0.456."
    rendered, _ = await compose(
        surface,
        text,
        stored_result,
        monkeypatch,
        figures=[
            ("configuration.starting_capital", 10000.0, "10,000"),
            ("portfolio.sharpe_ratio", 0.456, "0.456"),
        ],
    )
    assert rendered == text


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize(
    "text,accepted,figures,language",
    [
        (
            "La ganancia fue $3\u202f962.",
            False,
            [("portfolio.profit", 3962.59, "$3\u202f962")],
            "es-419",
        ),
        (
            "La ganancia fue $3\u202f963.",
            True,
            [("portfolio.profit", 3962.59, "$3\u202f963")],
            "es-419",
        ),
        (
            "La volatilidad fue 68%.",
            False,
            [("portfolio.annualized_volatility", 68.62, "68%")],
            "es-419",
        ),
        (
            "La volatilidad fue 69%.",
            True,
            [("portfolio.annualized_volatility", 68.62, "69%")],
            "es-419",
        ),
    ],
)
async def test_readout_format_support_preserves_quoted_rounding_precision(
    surface, text, accepted, stored_result, monkeypatch, figures, language
):
    metrics = stored_result["metrics"]["aggregate"]
    metrics["performance"]["profit"] = 3962.59
    metrics["risk"]["volatility_annual_pct"] = 68.62
    rendered, _ = await compose(
        surface, text, stored_result, monkeypatch, language, figures=figures
    )
    assert rendered == (text if accepted else None)


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize("currency", ["dólares", "dolares", "do\u0301lares"])
@pytest.mark.parametrize("available", [True, False])
async def test_numeric_currency_matching_folds_accents_without_changing_text(
    surface, currency, available, stored_result, monkeypatch
):
    metrics = stored_result["metrics"]["aggregate"]
    metrics["performance"]["profit"] = 85.97 if available else 198.52
    metrics["efficiency"]["total_trades"] = 4 if available else 86
    text = f"La ganancia fue de unos 86 {currency}."
    rendered, _ = await compose(
        surface,
        text,
        stored_result,
        monkeypatch,
        "es-419",
        figures=[
            ("portfolio.profit", metrics["performance"]["profit"], f"86 {currency}"),
        ],
    )
    assert rendered == (text if available else None)


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize(
    "text,accepted,figures,language",
    [
        (
            "There were 4 trades, with an entry on 18 November 2025 and an exit on 9 December 2025.",
            True,
            [
                ("portfolio.executed_fills", 4.0, "4 trades"),
                ("chart.markers.0.time", "2025-11-18", "18 November 2025"),
                ("chart.markers.1.time", "2025-12-09", "9 December 2025"),
            ],
            "en",
        ),
        (
            "Se ejecutaron 4 trades, con una entrada el 18 de noviembre de 2025 y una salida el 9 de diciembre de 2025.",
            True,
            [
                ("portfolio.executed_fills", 4.0, "4 trades"),
                ("chart.markers.0.time", "2025-11-18", "18 de noviembre de 2025"),
                ("chart.markers.1.time", "2025-12-09", "9 de diciembre de 2025"),
            ],
            "es-419",
        ),
        ("There were 18 trades.", False, [("portfolio.executed_fills", 4.0, "18")], "en"),
        (
            "Hubo 18 operaciones.",
            False,
            [("portfolio.executed_fills", 4.0, "18")],
            "es-419",
        ),
        (
            "El saldo fue 18 dolares.",
            False,
            [("configuration.starting_capital", 10000.0, "18 dolares")],
            "es-419",
        ),
        (
            "La entrada fue el 19 de noviembre de 2025.",
            False,
            [("chart.markers.0.time", "2025-11-18", "19 de noviembre de 2025")],
            "es-419",
        ),
    ],
)
async def test_natural_date_parts_do_not_inherit_distant_count_labels(
    surface, text, accepted, stored_result, monkeypatch, figures, language
):
    stored_result["metrics"]["aggregate"]["efficiency"]["total_trades"] = 4
    stored_result["date_range"] = {"start": "2025-09-10", "end": "2026-09-09"}
    stored_result["chart"] = {"markers": [{"time": "2025-11-18"}, {"time": "2025-12-09"}]}
    rendered, _ = await compose(
        surface, text, stored_result, monkeypatch, figures=figures, language=language
    )
    assert rendered == (text if accepted else None)


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
async def test_readouts_normalize_em_dash_without_dropping_prose(
    surface, stored_result, monkeypatch
):
    rendered, _ = await compose(
        surface, "DOCN lagged SPY — the ride was uneven.", stored_result, monkeypatch
    )
    assert rendered == "DOCN lagged SPY, the ride was uneven."


@pytest.mark.parametrize("template", ["buy_and_hold", "dca_accumulation"])
def test_readout_configuration_derives_from_executed_engine_config(
    template, stored_result, faker
):
    from argus.domain.result_readout_grounding import stored_readout_facts

    from tests.public_excerpt_factories import generated_card_config

    engine = generated_card_config(template)
    expected_capital = (
        engine["dca_capital"]["starting_capital"]
        if template == "dca_accumulation"
        else engine["starting_capital"]
    )
    snapshot = {
        "resolved_parameters": {
            "starting_capital": faker.pyint(min_value=9000),
            "engine_config": engine,
        },
    }
    facts = stored_readout_facts(**{**stored_result, "config_snapshot": snapshot})
    assert facts["facts"]["configuration.starting_capital"]["value"] == expected_capital
    assert "portfolio_equity" not in facts["series"]
    if expected_capital == 0:
        assert facts["facts"]["portfolio.drawdown_illustration"]["value"] is None
    else:
        drawdown = stored_result["metrics"]["aggregate"]["risk"]["max_drawdown_pct"]
        assert facts["facts"]["portfolio.drawdown_illustration"][
            "value"
        ] == pytest.approx(abs(drawdown) * expected_capital / 100)


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize(
    "text,figures,language",
    [
        ("DOCN returned 17%.", [("portfolio.total_return", 15.126, "17%")], "en"),
        ("DOCN rindió 17%.", [("portfolio.total_return", 15.126, "17%")], "es-419"),
        (
            "The drawdown illustrates a $31.2 loss.",
            [("portfolio.drawdown_illustration", 3123.4, "$31.2")],
            "en",
        ),
        (
            "La caída ilustra una pérdida de $31,2.",
            [("portfolio.drawdown_illustration", 3123.4, "$31,2")],
            "es-419",
        ),
        ("There were 15.1 fills.", [("portfolio.executed_fills", 17.0, "15.1")], "en"),
        (
            "El índice tuvo 15,1 operaciones.",
            [("portfolio.executed_fills", 17.0, "15,1")],
            "es-419",
        ),
        ("The Sharpe ratio was 17.", [("portfolio.sharpe_ratio", 0.456, "17")], "en"),
        ("Sharpe fue 17.", [("portfolio.sharpe_ratio", 0.456, "17")], "es-419"),
        ("The return was 2023%.", [("portfolio.total_return", 15.126, "2023%")], "en"),
        (
            "The final balance was $999k.",
            [("configuration.starting_capital", 10000.0, "$999k")],
            "en",
        ),
        (
            "El saldo final fue $999k.",
            [("configuration.starting_capital", 10000.0, "$999k")],
            "es-419",
        ),
        (
            "The final balance was $1e9.",
            [("configuration.starting_capital", 10000.0, "$1e9")],
            "en",
        ),
        (
            "There were 1e9 fills.",
            [("portfolio.executed_fills", 17.0, "1e9 fills")],
            "en",
        ),
        ("There were 2023 shares.", [("portfolio.executed_fills", 17.0, "2023")], "en"),
        ("Hubo 2023 acciones.", [("portfolio.executed_fills", 17.0, "2023")], "es-419"),
        ("Trades were 2023.", [("portfolio.executed_fills", 17.0, "2023")], "en"),
        ("Sharpe was 2023.", [("portfolio.sharpe_ratio", 0.456, "2023")], "en"),
        (
            "The final balance was $2023.",
            [("configuration.starting_capital", 10000.0, "$2023")],
            "en",
        ),
        (
            "Holding shares in DigitalOcean (DOCN) since September 1999.",
            [("window.start", "2023-09-01", "September 1999")],
            "en",
        ),
    ],
)
async def test_readouts_reject_numbers_with_wrong_units_or_unsupported_magnitudes(
    surface, text, stored_result, monkeypatch, figures, language
):
    rendered, _ = await compose(
        surface, text, stored_result, monkeypatch, figures=figures, language=language
    )
    assert rendered is None


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize(
    "text,figures,language",
    [
        (
            "The starting capital was $10k, with 17 fills and a Sharpe ratio of 0.46.",
            [
                ("configuration.starting_capital", 10000.0, "$10k"),
                ("portfolio.executed_fills", 17.0, "17"),
                ("portfolio.sharpe_ratio", 0.456, "0.46"),
            ],
            "en",
        ),
        (
            "El capital inicial fue $10k, con 17 operaciones y Sharpe de 0,46.",
            [
                ("configuration.starting_capital", 10000.0, "$10k"),
                ("portfolio.executed_fills", 17.0, "17"),
                ("portfolio.sharpe_ratio", 0.456, "0,46"),
            ],
            "es-419",
        ),
        (
            "The starting capital was $1e4.",
            [("configuration.starting_capital", 10000.0, "$1e4")],
            "en",
        ),
        (
            "The drawdown illustrates about $3.12k of starting capital.",
            [("portfolio.drawdown_illustration", 3123.4, "$3.12k")],
            "en",
        ),
    ],
)
async def test_readouts_accept_compatible_units_and_rounded_compact_money(
    surface, text, stored_result, monkeypatch, figures, language
):
    rendered, _ = await compose(
        surface, text, stored_result, monkeypatch, figures=figures, language=language
    )
    assert rendered == text


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize(
    "text,accepted,figures,language",
    [
        ("The benchmark lagged DOCN.", False, [], "en"),
        ("El índice quedó por debajo de DOCN.", False, [], "es-419"),
        ("The benchmark beat DOCN.", True, [], "en"),
        ("El índice superó a DOCN.", True, [], "es-419"),
        ("DOCN lagged the benchmark.", True, [], "en"),
        ("DOCN quedó por debajo del índice.", True, [], "es-419"),
        ("DOCN beat the benchmark.", False, [], "en"),
        ("DOCN superó al índice.", False, [], "es-419"),
        ("The benchmark did not lag DOCN.", True, [], "en"),
        ("El índice no superó a DOCN.", False, [], "es-419"),
    ],
)
async def test_readouts_resolve_generic_benchmark_subjects_consistently(
    surface, text, accepted, stored_result, monkeypatch, figures, language
):
    rendered, _ = await compose(
        surface, text, stored_result, monkeypatch, figures=figures, language=language
    )
    assert rendered == (text if accepted else None)


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize(
    "text,accepted,figures,language",
    [
        ("The RSI strategy in SPY lagged the SPY benchmark.", True, [], "en"),
        ("La estrategia RSI en SPY quedó por detrás del índice SPY.", True, [], "es-419"),
        ("The RSI strategy in SPY beat the SPY benchmark.", False, [], "en"),
        ("La estrategia RSI en SPY superó al índice SPY.", False, [], "es-419"),
        ("The SPY benchmark beat the RSI strategy in SPY.", True, [], "en"),
        ("El índice SPY superó a la estrategia RSI en SPY.", True, [], "es-419"),
        ("The SPY benchmark lagged the RSI strategy in SPY.", False, [], "en"),
        (
            "El índice SPY quedó por debajo de la estrategia RSI en SPY.",
            False,
            [],
            "es-419",
        ),
        ("The RSI strategy lagged SPY.", True, [], "en"),
        ("La estrategia RSI quedó por detrás de SPY.", True, [], "es-419"),
        ("The RSI strategy beat SPY.", False, [], "en"),
        ("La estrategia RSI superó a SPY.", False, [], "es-419"),
        ("SPY beat the RSI strategy.", True, [], "en"),
        ("SPY superó a la estrategia RSI.", True, [], "es-419"),
        ("SPY lagged the RSI strategy.", False, [], "en"),
        ("SPY quedó por debajo de la estrategia RSI.", False, [], "es-419"),
    ],
)
async def test_shared_ticker_comparison_derives_roles_from_explicit_subjects(
    surface, text, accepted, stored_result, monkeypatch, figures, language
):
    original_symbol = stored_result["symbols"][0]
    benchmark = stored_result["benchmark_symbol"]
    by_symbol = stored_result["metrics"]["by_symbol"]
    by_symbol[benchmark] = by_symbol.pop(original_symbol)
    stored_result["symbols"] = [benchmark]
    stored_result["config_snapshot"]["template"] = "rsi_mean_reversion"
    rendered, _ = await compose(
        surface, text, stored_result, monkeypatch, figures=figures, language=language
    )
    assert rendered == (text if accepted else None)


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize(
    "text,figures,language",
    [
        (
            "The slippage assumption was 5bps.",
            [("configuration.slippage_bps", 5.0, "5bps")],
            "en",
        ),
        (
            "The slippage assumption was 5 bps.",
            [("configuration.slippage_bps", 5.0, "5 bps")],
            "en",
        ),
        (
            "El supuesto de deslizamiento fue 5bps.",
            [("configuration.slippage_bps", 5.0, "5bps")],
            "es-419",
        ),
        (
            "El supuesto de deslizamiento fue 5 bps.",
            [("configuration.slippage_bps", 5.0, "5 bps")],
            "es-419",
        ),
        (
            "The slippage assumption was 5basis points.",
            [("configuration.slippage_bps", 5.0, "5basis points")],
            "en",
        ),
        (
            "El supuesto de deslizamiento fue 5puntos básicos.",
            [("configuration.slippage_bps", 5.0, "5puntos básicos")],
            "es-419",
        ),
        (
            "The starting capital was $10K.",
            [("configuration.starting_capital", 10000.0, "$10K")],
            "en",
        ),
        (
            "El capital inicial fue $10k.",
            [("configuration.starting_capital", 10000.0, "$10k")],
            "es-419",
        ),
    ],
)
async def test_compact_suffix_does_not_consume_the_start_of_a_unit(
    surface, text, stored_result, monkeypatch, figures, language
):
    stored_result["config_snapshot"]["slippage_bps"] = 5
    rendered, _ = await compose(
        surface, text, stored_result, monkeypatch, figures=figures, language=language
    )
    assert rendered == text
