"""Every reader of a completed result states one benchmark gap and one cost drag (#533).

A stated difference is the difference of the two figures shown beside it. Returns
of 53.44% and 7.1% show as 53.4% and 7.1%, so every reader states a 46.3 point
gap, while the engine's stored 46.35, taken before rounding, would print 46.4.
``shown_benchmark_gap`` owns that rule, ``shown_cost_drag`` owns it for gross and
net returns, and stored runs are fixed when they are read.
"""

from __future__ import annotations

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from argus.agent_runtime.result_conversation import run_headline_facts
from argus.agent_runtime.result_followup_answers import result_next_experiments
from argus.agent_runtime.result_followups import result_followup_fact_bank
from argus.agent_runtime.stages import explain as explain_module
from argus.agent_runtime.stages.explain import explain_stage
from argus.agent_runtime.state.models import ResponseProfile, RunState
from argus.api.chat.breakdown import (
    _llm_result_breakdown_with_metadata,
    fallback_result_breakdown_message,
)
from argus.domain.backtesting.cards import build_result_card
from argus.domain.display_figure import display_difference, display_figure
from argus.domain.result_figures import result_display_figures
from argus.domain.result_readout_grounding import stored_readout_facts

from tests.result_readout_fixtures import readout_draft

# The issue's own shape: 53.4 - 7.1 shows a 46.3 gap; the stored 46.35 prints 46.4.
TOTAL_RETURN_PCT = 53.44
BENCHMARK_RETURN_PCT = 7.1
ENGINE_DELTA_PCT = 46.35
SHOWN_GAP = 46.3
# 269.7 - 269.2 shows a 0.5 drag; the stored 0.58 prints 0.6.
GROSS_RETURN_PCT = 269.74
NET_RETURN_PCT = 269.16
ENGINE_DRAG_PCT = 0.58
SHOWN_DRAG = 0.5
CONFIG = {
    "template": "buy_and_hold",
    "asset_class": "equity",
    "symbols": ["AAPL"],
    "start_date": "2023-01-03",
    "end_date": "2024-12-31",
    "starting_capital": 1_000,
    "benchmark_symbol": "SPY",
}


def _engine_metrics(
    delta: float | None = ENGINE_DELTA_PCT,
    *,
    total_return: float = TOTAL_RETURN_PCT,
    costs: bool = False,
) -> dict[str, object]:
    performance: dict[str, object] = {
        "total_return_pct": total_return,
        "benchmark_return_pct": BENCHMARK_RETURN_PCT,
        "profit": 534.4,
    }
    if delta is not None:
        performance["delta_vs_benchmark_pct"] = delta
    if costs:
        performance["execution_realism"] = {
            "enabled": True,
            "fee_bps": 5.0,
            "slippage_bps": 10.0,
            "gross_total_return_pct": GROSS_RETURN_PCT,
            "net_total_return_pct": NET_RETURN_PCT,
            "return_drag_pct": ENGINE_DRAG_PCT,
        }
    return {
        "aggregate": {
            "performance": performance,
            "risk": {"max_drawdown_pct": -8.35},
            "efficiency": {"win_rate": 0.0, "total_trades": 1},
        }
    }


def _explanation_context(metrics: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "metrics": _engine_metrics() if metrics is None else metrics,
        "benchmark_metrics": {"aggregate": {"total_return_pct": BENCHMARK_RETURN_PCT}},
        "benchmark_symbol": "SPY",
    }


def _card_comparison(metrics: dict[str, object]) -> str:
    card = build_result_card(CONFIG, deepcopy(metrics))
    return next(row["value"] for row in card["rows"] if row["key"] == "benchmark_delta")


def _completed_state(explanation_context: dict[str, object]) -> RunState:
    state = RunState.new(current_user_message="run it", recent_thread_history=[])
    state.effective_response_profile = ResponseProfile(
        effective_tone="concise",
        effective_verbosity="low",
        effective_expertise_mode="advanced",
    )
    state.confirmation_payload = {
        "strategy": {"strategy_thesis": "Hold AAPL"},
        "optional_parameters": {},
    }
    state.final_response_payload = {
        "result": {"metrics": explanation_context["metrics"]},
        "explanation_context": explanation_context,
    }
    return state


async def _composer_facts(monkeypatch, state: RunState) -> dict[str, object]:
    captured: dict[str, object] = {}
    text = "The ride was uneven."

    async def draft(**kwargs):
        captured.update(json.loads(kwargs["messages"][1]["content"])["run_facts"])
        return readout_draft(text)

    monkeypatch.setattr(explain_module, "invoke_openrouter_json_schema", draft)
    result = await explain_module.explain_stage_async(state=state)
    assert result.patch["assistant_response"] == text
    assert result.patch["assistant_response_fallback_used"] is False
    return captured


@pytest.mark.asyncio
async def test_card_quick_take_and_figures_state_the_shown_gap(monkeypatch) -> None:
    metrics = _engine_metrics()
    facts = await _composer_facts(
        monkeypatch, _completed_state(_explanation_context(metrics))
    )
    figures = result_display_figures(metrics)

    assert display_figure(ENGINE_DELTA_PCT) != SHOWN_GAP
    assert _card_comparison(metrics) == f"Beat by {SHOWN_GAP} percentage points"
    assert {
        key: facts["facts"][key]["value"]
        for key in (
            "portfolio.benchmark_gap",
            "portfolio.total_return",
            "portfolio.benchmark_return",
        )
    } == {
        "portfolio.benchmark_gap": SHOWN_GAP,
        "portfolio.total_return": display_figure(TOTAL_RETURN_PCT),
        "portfolio.benchmark_return": display_figure(BENCHMARK_RETURN_PCT),
    }
    assert figures is not None
    assert figures["delta_vs_benchmark_pct"] == SHOWN_GAP
    assert SHOWN_GAP == display_difference(
        figures["total_return_pct"], figures["benchmark_return_pct"]
    )


def test_deterministic_readout_and_try_next_reason_state_the_shown_gap() -> None:
    result = explain_stage(state=_completed_state(_explanation_context()))

    readout = result.patch["assistant_response"]
    assert f"outperformed by {SHOWN_GAP} percentage points" in readout
    assert "46.4" not in readout
    assert result.patch["next_experiments"]["rows"][0]["why"] == {
        "code": "beat_benchmark",
        "params": {"points": SHOWN_GAP},
    }


@pytest.mark.parametrize(
    ("total_return", "stored_gap", "shown_gap", "claim", "card"),
    [
        (7.24, 0.14, 0.1, "beat_benchmark", "Beat by 0.1 percentage points"),
        (6.96, -0.14, -0.1, "lagged_benchmark", "Lagged by 0.1 percentage points"),
        (7.14, 0.04, 0.0, "matched_benchmark", "In line with benchmark"),
    ],
)
@pytest.mark.asyncio
async def test_the_claim_follows_the_shown_gap(
    monkeypatch,
    total_return: float,
    stored_gap: float,
    shown_gap: float,
    claim: str,
    card: str,
) -> None:
    # Beside a 7.1% benchmark each return shows the gap its claim is held to.
    metrics = _engine_metrics(stored_gap, total_return=total_return)
    facts = await _composer_facts(
        monkeypatch, _completed_state(_explanation_context(metrics))
    )
    figures = result_display_figures(metrics)

    assert facts["benchmark_comparison_claim"] == claim
    assert abs(facts["facts"]["portfolio.benchmark_gap"]["value"]) == abs(shown_gap)
    assert figures is not None
    assert figures["delta_vs_benchmark_pct"] == shown_gap
    assert figures["benchmark_comparison_claim"] == claim
    assert _card_comparison(metrics) == card


@pytest.mark.asyncio
async def test_an_engine_block_without_its_stored_gap_states_the_shown_gap(
    monkeypatch,
) -> None:
    context = _explanation_context(_engine_metrics(None))

    facts = await _composer_facts(monkeypatch, _completed_state(context))
    result = explain_stage(state=_completed_state(context))
    figures = result_display_figures(context["metrics"])

    assert facts["facts"]["portfolio.benchmark_gap"]["value"] == SHOWN_GAP
    assert facts["benchmark_comparison_claim"] == "beat_benchmark"
    readout = result.patch["assistant_response"]
    assert f"outperformed by {SHOWN_GAP} percentage points" in readout
    assert result.patch["next_experiments"]["rows"][0]["why"] == {
        "code": "beat_benchmark",
        "params": {"points": SHOWN_GAP},
    }
    assert figures is not None
    assert figures["delta_vs_benchmark_pct"] == SHOWN_GAP


@pytest.mark.asyncio
async def test_without_a_benchmark_return_no_gap_or_claim_is_stated(
    monkeypatch,
) -> None:
    metrics = _engine_metrics(None)
    del metrics["aggregate"]["performance"]["benchmark_return_pct"]
    context = {**_explanation_context(metrics), "benchmark_metrics": {}}

    facts = await _composer_facts(monkeypatch, _completed_state(context))
    result = explain_stage(state=_completed_state(context))
    figures = result_display_figures(metrics)

    assert facts["facts"].get("portfolio.benchmark_gap", {}).get("value") is None
    assert facts["benchmark_comparison_claim"] == "unknown"
    assert "percentage points" not in result.patch["assistant_response"]
    rows = (result.patch.get("next_experiments") or {}).get("rows", [])
    assert all("why" not in row for row in rows)
    assert figures is not None
    assert "delta_vs_benchmark_pct" not in figures
    assert "benchmark_comparison_claim" not in figures


@pytest.mark.asyncio
async def test_legacy_fraction_payloads_still_derive_their_only_comparison(
    monkeypatch,
) -> None:
    # Offline tools publish two fractions and no engine block; their
    # difference is the only comparison that shape carries.
    state = _completed_state(_explanation_context())
    state.final_response_payload = {
        "result": {"total_return": 0.14, "benchmark_return": 0.09},
        "explanation_context": {"benchmark_symbol": "SPY"},
    }
    facts = await _composer_facts(monkeypatch, state)

    assert facts["facts"]["portfolio.benchmark_gap"]["value"] == pytest.approx(5)
    assert facts["benchmark_comparison_claim"] == "beat_benchmark"


def _stored_run_metadata() -> dict[str, object]:
    """A run persisted before one owner stated its gap and its cost drag."""
    config = {
        **CONFIG,
        "date_range": {"start": CONFIG["start_date"], "end": CONFIG["end_date"]},
    }
    return {
        "symbols": ["AAPL"],
        "benchmark_symbol": "SPY",
        "config_snapshot": config,
        "metrics": _engine_metrics(costs=True),
        "result_card": {
            "rows": [
                {"key": "total_return_pct", "label": "Total return", "value": "+53.4%"},
                {
                    "key": "benchmark_delta",
                    "label": "Compared with SPY",
                    "value": "Beat by 46.4 percentage points",
                },
            ],
            "execution_costs": {
                "fee_bps": 5.0,
                "slippage_bps": 10.0,
                "gross_total_return_pct": GROSS_RETURN_PCT,
                "net_total_return_pct": NET_RETURN_PCT,
                "return_drag_pct": ENGINE_DRAG_PCT,
                "benchmark_treatment": "same_modeled_costs",
            },
        },
    }


@pytest.mark.asyncio
async def test_a_stored_run_reads_one_gap_and_one_cost_drag_everywhere(
    monkeypatch,
) -> None:
    metadata = _stored_run_metadata()
    metrics = metadata["metrics"]
    breakdown_context = {
        "raw_metrics": metrics,
        "metrics": metadata["result_card"]["rows"],
        "config_snapshot": metadata["config_snapshot"],
        "symbols": metadata["symbols"],
        "benchmark_symbol": "SPY",
        "date_range": metadata["config_snapshot"]["date_range"],
        "chart": None,
    }
    requests: list[str] = []

    def run_structured(prompt, *args, **kwargs):
        requests.append(prompt)
        draft = {"language": "en", "text": "The ride was uneven.", "figures": []}
        return SimpleNamespace(draft=draft, sources=(), usage=None)

    card = build_result_card(CONFIG, deepcopy(metrics))
    quick_take = await _composer_facts(
        monkeypatch, _completed_state(_explanation_context(deepcopy(metrics)))
    )
    explained = explain_stage(state=_completed_state(_explanation_context(metrics)))
    _llm_result_breakdown_with_metadata(
        breakdown_context, client=SimpleNamespace(run_structured=run_structured)
    )
    breakdown_sheet = stored_readout_facts(
        metrics=breakdown_context["raw_metrics"],
        config_snapshot=breakdown_context["config_snapshot"],
        symbols=breakdown_context["symbols"],
        benchmark_symbol="SPY",
        date_range=breakdown_context["date_range"],
    )
    answer = run_headline_facts(metadata)["facts"]
    try_next = result_next_experiments(metadata, language="en", source_run_id=None)
    bank = result_followup_fact_bank(metadata)
    figures = result_display_figures(metrics)
    beat_reason = {"code": "beat_benchmark", "params": {"points": SHOWN_GAP}}

    assert display_figure(ENGINE_DRAG_PCT) != SHOWN_DRAG
    assert _card_comparison(metrics) == f"Beat by {SHOWN_GAP} percentage points"
    assert card["execution_costs"]["return_drag_pct"] == SHOWN_DRAG
    assert quick_take["facts"]["portfolio.benchmark_gap"]["value"] == SHOWN_GAP
    assert quick_take["facts"]["portfolio.cost_drag"]["value"] == SHOWN_DRAG
    assert f"Return difference versus benchmark: {SHOWN_GAP} pp" in requests[0]
    assert breakdown_sheet["facts"]["portfolio.cost_drag"]["value"] == SHOWN_DRAG
    assert f"Beat by {SHOWN_GAP} percentage points" in (
        fallback_result_breakdown_message(breakdown_context)
    )
    assert answer["Return difference versus benchmark"]["value"] == SHOWN_GAP
    assert answer["Return given up to modeled costs"]["value"] == SHOWN_DRAG
    assert explained.patch["next_experiments"]["rows"][0]["why"] == beat_reason
    assert try_next is not None
    assert try_next["rows"][0]["why"] == beat_reason
    assert bank["benchmark_delta"] == f"+{SHOWN_GAP} percentage points"
    assert bank["benchmark_comparison"] == f"Beat by {SHOWN_GAP} percentage points"
    assert f"by {SHOWN_GAP} percentage points" in bank["relative_performance"]
    assert bank["return_drag"] == f"{SHOWN_DRAG} percentage points"
    assert figures is not None
    assert figures["delta_vs_benchmark_pct"] == SHOWN_GAP
    assert figures["return_drag_pct"] == SHOWN_DRAG
