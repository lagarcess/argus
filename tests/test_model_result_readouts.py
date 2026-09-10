"""Both model readouts accept richer stored facts and reject false visible claims."""

import json
from copy import deepcopy

import pytest
from argus.agent_runtime.stages import explain
from argus.agent_runtime.state.models import RunState
from argus.api.chat import breakdown


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


async def compose(surface, text, result, monkeypatch, language="en"):
    captured = {}

    def draft(**kwargs):
        captured.update(kwargs)
        return {"text": text}

    if surface == "breakdown":
        rendered = breakdown.llm_result_breakdown_message(
            {**result, "raw_metrics": result["metrics"]},
            language=language,
            invoke_json_schema_func=draft,
        )
        return rendered, captured

    async def async_draft(**kwargs):
        return draft(**kwargs)

    monkeypatch.setattr(explain, "invoke_openrouter_json_schema", async_draft)
    state = RunState.new(current_user_message="Explain", recent_thread_history=[])
    state.final_response_payload = {"result": result}
    state.confirmation_payload = {
        "strategy": {"strategy_type": "buy_and_hold", "asset_universe": ["DOCN"]},
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
    "language,text",
    [
        (
            "en",
            "Annualized return was 6.8%, volatility 28.6%, Sharpe 0.46, with 17 fills. "
            "The 31.2% worst drop illustrates about $3,123 on $10,000 of starting capital; "
            "that is not the actual dollar loss from the portfolio's peak.",
        ),
        (
            "es-419",
            "El rendimiento anualizado fue 6,8%, la volatilidad 28,6% y Sharpe 0,46. "
            "Hubo 17 operaciones y el factor de beneficio fue 1,88.",
        ),
    ],
)
async def test_readout_accepts_richer_rounded_metrics_without_forced_mentions(
    surface, language, text, stored_result, monkeypatch
):
    rendered, captured = await compose(
        surface, text, stored_result, monkeypatch, language
    )
    assert rendered == text
    context = json.loads(captured["messages"][1]["content"])
    assert context["run_facts"]["metrics"] == stored_result["metrics"]
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
    facts = json.loads(captured["messages"][1]["content"])["run_facts"]
    assert facts["configuration"] == execution
    assert facts["metrics"] == stored_result["metrics"]
    assert facts["chart"] == {
        key: value for key, value in chart.items() if key != "attribution"
    }
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
        return {"text": text}

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
        assert facts["chart"] == card["chart"]
    else:
        assert "chart" not in facts
        assert response.failure_mode == "unknown_figure"


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize(
    "text",
    [
        "DOCN returned 99.9%.",
        "The Sharpe ratio was 8.88.",
        "There were 999 fills.",
        "The drop illustrates $9,876 of the starting capital.",
        "DOCN beat SPY by 5.3 percentage points.",
        "DOCN superó a SPY por 5,3 puntos porcentuales.",
        "SPY lagged DOCN by 5.3 percentage points.",
        "The total_return_pct was 15.1%.",
        "The schema_version gives the result.",
        "The result was 1.2.3%.",
        "The QuickTakeDraft says the ride was uneven.",
        "The ResultBreakdownDraft says the ride was uneven.",
    ],
)
async def test_readout_rejects_complete_draft_with_false_statement(
    surface, text, stored_result, monkeypatch
):
    rendered, _ = await compose(surface, text, stored_result, monkeypatch)
    assert rendered is None


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize(
    "text",
    [
        "DOCN lagged SPY by 5.3 percentage points.",
        "SPY beat DOCN by 5.3 percentage points.",
        "DOCN did not beat SPY.",
        "DOCN no superó a SPY.",
        "The spread was -5.3 percentage points versus SPY.",
        "DOCN quedó por debajo de SPY por 5,3 puntos porcentuales.",
    ],
)
async def test_readout_accepts_truthful_comparison_without_content_caps(
    surface, text, stored_result, monkeypatch
):
    rendered, _ = await compose(surface, text, stored_result, monkeypatch)
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
    "text",
    [
        "Sharpe was 1.234. The win rate was 57%.",
        "Sharpe fue 1,234. La tasa de aciertos fue 57%.",
        "The profit was $1,234.",
    ],
)
async def test_readouts_understand_decimal_precision_and_typed_ratio_percentages(
    surface, text, stored_result, monkeypatch
):
    metrics = stored_result["metrics"]["aggregate"]
    metrics["efficiency"].update(sharpe_ratio=1.234, win_rate=0.57)
    metrics["performance"]["profit"] = 1234
    rendered, _ = await compose(surface, text, stored_result, monkeypatch)
    assert rendered == text


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
    assert facts["configuration"]["starting_capital"] == expected_capital
    assert "chart" not in facts
    if expected_capital == 0:
        assert "illustrations" not in facts
    else:
        drawdown = stored_result["metrics"]["aggregate"]["risk"]["max_drawdown_pct"]
        assert facts["illustrations"][
            "drawdown_scaled_to_starting_capital"
        ] == pytest.approx(abs(drawdown) * expected_capital / 100)


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize(
    "text",
    [
        "DOCN returned 17%.",
        "DOCN rindió 17%.",
        "The drawdown illustrates a $31.2 loss.",
        "La caída ilustra una pérdida de $31,2.",
        "There were 15.1 fills.",
        "El índice tuvo 15,1 operaciones.",
        "The Sharpe ratio was 17.",
        "Sharpe fue 17.",
        "The return was 2023%.",
        "The final balance was $999k.",
        "El saldo final fue $999k.",
        "The final balance was $1e9.",
        "There were 1e9 fills.",
    ],
)
async def test_readouts_reject_numbers_with_wrong_units_or_unsupported_magnitudes(
    surface, text, stored_result, monkeypatch
):
    rendered, _ = await compose(surface, text, stored_result, monkeypatch)
    assert rendered is None


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize(
    "text",
    [
        "The starting capital was $10k, with 17 fills and a Sharpe ratio of 0.46.",
        "El capital inicial fue $10k, con 17 operaciones y Sharpe de 0,46.",
        "The starting capital was $1e4.",
        "The drawdown illustrates about $3.12k of starting capital.",
    ],
)
async def test_readouts_accept_compatible_units_and_rounded_compact_money(
    surface, text, stored_result, monkeypatch
):
    rendered, _ = await compose(surface, text, stored_result, monkeypatch)
    assert rendered == text


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize(
    "text,accepted",
    [
        ("The benchmark lagged DOCN.", False),
        ("El índice quedó por debajo de DOCN.", False),
        ("The benchmark beat DOCN.", True),
        ("El índice superó a DOCN.", True),
        ("DOCN lagged the benchmark.", True),
        ("DOCN quedó por debajo del índice.", True),
        ("DOCN beat the benchmark.", False),
        ("DOCN superó al índice.", False),
        ("The benchmark did not lag DOCN.", True),
        ("El índice no superó a DOCN.", False),
    ],
)
async def test_readouts_resolve_generic_benchmark_subjects_consistently(
    surface, text, accepted, stored_result, monkeypatch
):
    rendered, _ = await compose(surface, text, stored_result, monkeypatch)
    assert rendered == (text if accepted else None)


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize(
    "text",
    [
        "The slippage assumption was 5bps.",
        "The slippage assumption was 5 bps.",
        "El supuesto de deslizamiento fue 5bps.",
        "El supuesto de deslizamiento fue 5 bps.",
        "The slippage assumption was 5basis points.",
        "El supuesto de deslizamiento fue 5puntos básicos.",
        "The starting capital was $10K.",
        "El capital inicial fue $10k.",
    ],
)
async def test_compact_suffix_does_not_consume_the_start_of_a_unit(
    surface, text, stored_result, monkeypatch
):
    stored_result["config_snapshot"]["slippage_bps"] = 5
    rendered, _ = await compose(surface, text, stored_result, monkeypatch)
    assert rendered == text
