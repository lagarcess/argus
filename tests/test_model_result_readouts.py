"""Composers preserve run truth and accept plain prose without quote bookkeeping."""

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
                    draft=readout_draft(text, figures, language=language),
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
    "language,text",
    [
        (
            "en",
            "The strong finish followed an uneven ride. There were 17 fills, not 17 completed round trips.",
        ),
        (
            "es-419",
            "El buen cierre llegó tras un recorrido irregular. Hubo 17 ejecuciones, no 17 operaciones completas.",
        ),
    ],
)
async def test_readouts_accept_repeated_and_unreferenced_numbers(
    surface, language, text, stored_result, monkeypatch
):
    key = "Purchases and sales" if surface == "breakdown" else "portfolio.executed_fills"
    rendered, _ = await compose(
        surface, text, stored_result, monkeypatch, language, figures=[(key, 17)]
    )
    assert rendered == text


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize("language", ["en", "es-419"])
@pytest.mark.parametrize("value", [15.1, 99.9])
async def test_readouts_check_declared_value_against_run_with_display_rounding(
    surface, language, value, stored_result, monkeypatch
):
    key = (
        "Total return on starting capital"
        if surface == "breakdown"
        else "portfolio.total_return"
    )
    text = f"{value}%."
    rendered, _ = await compose(
        surface, text, stored_result, monkeypatch, language, figures=[(key, value)]
    )
    assert rendered == (text if value == 15.1 else None)


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["en", "es-419"])
async def test_breakdown_sends_headline_facts_without_chart_or_internal_paths(
    language, stored_result, monkeypatch
):
    result = deepcopy(stored_result)
    result["chart"] = {
        "kind": "portfolio_equity",
        "series": [{"time": "2023-09-01", "value": 10000}],
        "markers": [{"time": "2023-09-01", "price": 32.45}],
    }
    before = deepcopy(result)
    rendered, captured = await compose(
        "breakdown", "A complete readout.", result, monkeypatch, language
    )
    prompt = captured["prompt"]
    assert rendered == "A complete readout."
    assert "DOCN" in prompt and "SPY" in prompt
    assert (
        "September 1, 2023" if language == "en" else "1 de septiembre de 2023"
    ) in prompt
    assert (
        "September 9, 2026" if language == "en" else "9 de septiembre de 2026"
    ) in prompt
    assert "15.1%" in prompt and "15.126" not in prompt
    assert "Total return on starting capital" in prompt
    assert "Purchases and sales" in prompt
    for internal in (
        "series",
        "markers",
        "portfolio.total_return",
        "total_return_pct",
        "provenance",
        "provider_metadata",
    ):
        assert internal not in prompt
    assert result == before


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take"])
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
    assert facts["facts"]["portfolio.total_return"]["display"] == "15.1%"
    assert facts["facts"]["portfolio.max_drawdown"]["display"] == "31.2%"
    assert facts["facts"]["configuration.starting_capital"]["display"] == "$10,000"
    assert facts["facts"]["configuration.fee_bps"]["value"] == 5
    assert facts["facts"]["portfolio.executed_fills"]["value"] == 17
    assert facts["series"]["portfolio_equity"]["points"] == chart["series"]
    assert facts["series"]["execution_markers"]["points"] == chart["markers"]
    assert all(
        "provenance" not in row and "basis" not in row for row in facts["facts"].values()
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
        return readout_draft(text, [("portfolio.ending_equity", 11512.6)])

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
        assert facts["series"]["portfolio_equity"]["points"][-1]["value"] == 11513
        assert card["chart"]["series"][-1]["value"] == 11512.6
    else:
        assert "portfolio_equity" not in facts["series"]
        assert response.failure_mode == "invalid_figure_reference"


def test_breakdown_context_retains_optional_chart_for_headline_derivation(
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
