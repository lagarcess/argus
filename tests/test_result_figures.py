"""Display figures are rounded once, by the backend, at every reader boundary (#533).

The engine keeps two decimals. Readers show one. That rounding is Python's own
float rounding, applied in ``display_figure`` and shipped as ``figures`` beside
the metrics on every public result payload, run, and dossier, so the client
prints digits it never computed and backend prose carries the same digits.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest
from argus.agent_runtime.next_experiments import next_experiments_sidecar
from argus.api.artifact_presentation import reader_payload, reader_run
from argus.api.schemas import BacktestJob, BacktestJobResponse, BacktestRun
from argus.domain.benchmark_comparison import benchmark_comparison_from_delta
from argus.domain.display_figure import display_figure
from argus.domain.result_figures import result_display_figures
from argus.domain.run_dossiers import project_run_dossier

# The issue's own numbers: 53.44 - 7.1 prints 46.3, the engine gap 46.35 prints 46.4.
PERFORMANCE = {
    "return_basis": "fixed_capital",
    "total_return_pct": 53.44,
    "benchmark_return_pct": 7.1,
    "delta_vs_benchmark_pct": 46.35,
    "profit": 534.4,
}
METRICS = {
    "aggregate": {
        "performance": PERFORMANCE,
        "risk": {"max_drawdown_pct": -18.35, "volatility_pct": 21.7},
        "efficiency": {"win_rate": 0.0, "total_trades": 1},
    },
    "by_symbol": {},
}
FIGURES = {
    "total_return_pct": 53.4,
    "benchmark_return_pct": 7.1,
    "delta_vs_benchmark_pct": 46.4,
    "benchmark_comparison_claim": "beat_benchmark",
    "max_drawdown_pct": -18.4,
}


def _run() -> BacktestRun:
    return BacktestRun(
        id="run-533",
        conversation_id="conversation-533",
        strategy_id=None,
        status="completed",
        asset_class="equity",
        symbols=["AAPL"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics=deepcopy(METRICS),
        config_snapshot={"template": "buy_and_hold"},
        conversation_result_card={"title": "AAPL", "quick_take": "PRIVATE", "rows": []},
        created_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
    )


@pytest.mark.parametrize(
    "value",
    [46.35, 46.34, 46.25, -46.25, 46.15, 0.15, 0.05, 0.049, -18.35, 315.64, 1234.56],
)
def test_display_figure_is_the_rounding_backend_prose_already_uses(value: float) -> None:
    # One implementation: round() and fixed-point formatting agree, ties to even.
    assert f"{display_figure(value):.1f}" == f"{value:.1f}"


def test_benchmark_prose_derives_its_digits_from_the_same_rounding() -> None:
    comparison = benchmark_comparison_from_delta(46.25)
    assert comparison.magnitude_points == f"{display_figure(46.25):.1f} percentage points"
    assert comparison.signed_delta_percent == "+46.2%"


def test_result_display_figures_project_the_engine_block_only() -> None:
    assert result_display_figures(METRICS) == FIGURES
    assert result_display_figures({"aggregate": {}}) is None
    assert result_display_figures(None) is None


def test_result_display_figures_keep_legacy_drawdown_and_modeled_costs() -> None:
    metrics = deepcopy(METRICS)
    del metrics["aggregate"]["risk"]
    metrics["aggregate"]["performance"]["max_drawdown_pct"] = -9.96
    metrics["aggregate"]["performance"]["execution_realism"] = {
        "enabled": True,
        "gross_total_return_pct": 12.04,
        "net_total_return_pct": 11.75,
    }
    figures = result_display_figures(metrics)
    assert figures is not None
    assert figures["max_drawdown_pct"] == -10.0
    assert figures["gross_total_return_pct"] == 12.0
    assert figures["net_total_return_pct"] == 11.8


def test_in_line_claim_is_the_gap_rounding_to_nothing() -> None:
    metrics = deepcopy(METRICS)
    metrics["aggregate"]["performance"]["delta_vs_benchmark_pct"] = 0.03
    figures = result_display_figures(metrics)
    assert figures is not None
    assert figures["delta_vs_benchmark_pct"] == 0.0
    assert figures["benchmark_comparison_claim"] == "matched_benchmark"


def test_reader_payload_attaches_figures_from_the_banks_own_metrics() -> None:
    bank = {"symbols": ["AAPL"], "metrics": deepcopy(METRICS), "config_snapshot": {}}
    payload = {"content": "PRIVATE", "result_fact_bank": deepcopy(bank)}
    original = deepcopy(payload)

    public = reader_payload(payload)

    assert public["result_fact_bank"]["figures"] == FIGURES
    assert public["result_fact_bank"]["metrics"] == METRICS
    assert payload == original


def test_reader_payload_attaches_figures_to_a_typed_breakdown_bank() -> None:
    intent = {
        "kind": "result_breakdown",
        "facts": {
            "result_fact_bank": {"symbols": ["AAPL"], "metrics": deepcopy(METRICS)}
        },
    }
    public = reader_payload({"content": "PRIVATE", "response_intent": intent})
    assert public["response_intent"]["facts"]["result_fact_bank"]["figures"] == FIGURES


def test_reader_payload_leaves_banks_without_engine_metrics_alone() -> None:
    payload = {
        "content": "PRIVATE",
        "chat_action": {"type": "show_breakdown"},
        "result_fact_bank": {"symbols": ["SPY"]},
    }
    assert "figures" not in reader_payload(payload)["result_fact_bank"]


def test_public_runs_carry_figures_and_job_responses_serialize_them() -> None:
    run = _run()
    assert run.figures is None
    public = reader_run(run)
    assert public.figures == FIGURES
    assert public.conversation_result_card == {"title": "AAPL", "rows": []}
    assert run.conversation_result_card["quick_take"] == "PRIVATE"

    response = BacktestJobResponse(
        job=BacktestJob(id="job-533", status="succeeded", result_run_id=run.id),
        run=run,
    ).model_dump(mode="json")
    assert response["run"]["figures"] == FIGURES
    assert "quick_take" not in response["run"]["conversation_result_card"]


def test_dossier_grid_and_bank_carry_the_same_figures() -> None:
    run = _run().model_dump(mode="python")
    dossier = project_run_dossier(
        run=run,
        artifact={"id": "artifact-533", "source_run_id": run["id"]},
        decision=None,
        result_message_id=None,
        decision_action_availability=None,
    )
    grid = {metric.name: metric.value for metric in dossier.outcome.metrics}
    # The grid summary reads the performance block; drawdown lives under risk.
    assert grid["total_return_pct"] == 53.4
    assert grid["benchmark_return_pct"] == 7.1
    assert grid["delta_vs_benchmark_pct"] == 46.4
    assert dossier.outcome.result_fact_bank is not None
    assert dossier.outcome.result_fact_bank["figures"] == FIGURES
    # The bank keeps the engine metrics untouched beside the figures.
    assert dossier.outcome.result_fact_bank["metrics"]["aggregate"]["performance"] == (
        PERFORMANCE
    )


def test_try_next_reason_params_are_display_figures() -> None:
    facts = {"config_snapshot": {"template": "buy_and_hold"}, "symbols": ["AAPL"]}
    beat = next_experiments_sidecar(facts, benchmark_delta=46.35)
    assert beat is not None
    assert beat["rows"][0]["why"] == {
        "code": "beat_benchmark",
        "params": {"points": 46.4},
    }
    drop = next_experiments_sidecar(facts, benchmark_delta=46.35, max_drawdown=-22.35)
    assert drop is not None
    assert drop["rows"][0]["why"] == {
        "code": "deep_drawdown",
        "params": {"drawdown": -22.4},
    }
