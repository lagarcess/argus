"""Authored browser controls; real presenters, no interpreter or backtest call."""

import hashlib
import json
import os
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import runpy
import shutil
import socket
import subprocess
import sys

SOURCE = Path("/Users/garces/.codex/worktrees/aa72/private-alpha-next")
ROOT = Path(__file__).resolve().parent
HEAD = "6b8d846e8543d532ecbfac73b9d744a3b1ac1ec2"
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=SOURCE, text=True).strip() == HEAD
subprocess.run(["git", "diff", "--quiet", HEAD, "--", "src", "tests", "web"], cwd=SOURCE, check=True)
sys.path[:0] = [str(SOURCE / "src"), str(SOURCE)]
attempts = []


def forbidden(*args, **kwargs):
    attempts.append("attempted")
    raise AssertionError("Fixture generation forbids providers and real API access")


socket.create_connection = forbidden
socket.socket.connect = forbidden
socket.getaddrinfo = forbidden
os.chdir(ROOT / "checkout")
runpy.run_path(str(SOURCE / "web/e2e/support/registry-fixture.py"), run_name="__main__")

from argus.agent_runtime.state.models import StrategySummary
from argus.agent_runtime.tools.registered_backtest import backtest_execution_result, get_backtest_declaration
from argus.domain.backtesting.cards import build_result_card
from argus.domain.dca_capital import dca_capital_plan_from_config
from argus.domain.tool_contracts import ToolCall, ToolOutcome
from tests.public_excerpt_factories import generated_card_metrics, generated_card_snapshot


def coherent_fixture(template):
    """Author money once; the real card owner formats the derived values.

    The chart is an explicit illustrative weekday path, not an engine result.
    DCA adds its existing monthly contribution on each month's first bar.
    """
    snapshot = generated_card_snapshot(template, modeled_costs=True)
    engine = snapshot["engine_config"]
    metrics = generated_card_metrics(modeled_costs=True)
    performance = metrics["aggregate"]["performance"]
    plan = None
    if template == "dca_accumulation":
        plan = dca_capital_plan_from_config(engine)
        assert len(engine["symbols"]) == 1
        contribution_count = metrics["aggregate"]["efficiency"]["total_trades"]
        principal = plan.total_invested(contribution_count)
        principal_owner = "DcaCapitalPlan.total_invested(authored contribution_count)"
    else:
        principal = engine["starting_capital"]
        principal_owner = "engine_config.starting_capital"
    net_return_pct = Decimal(str(performance["total_return_pct"]))
    profit = Decimal(str(principal)) * net_return_pct / 100
    ending_value = Decimal(str(principal)) + profit
    performance["profit"] = float(profit)
    performance["delta_vs_benchmark_pct"] = float(
        net_return_pct - Decimal(str(performance["benchmark_return_pct"]))
    )
    realism = performance["execution_realism"]
    realism["net_total_return_pct"] = float(net_return_pct)
    realism["gross_total_return_pct"] = float(
        net_return_pct + Decimal(str(realism["return_drag_pct"]))
    )
    performance.pop("annualized_return_pct", None)
    metrics["aggregate"]["risk"] = {"max_drawdown_pct": 0.0}

    start, end = (date.fromisoformat(engine[key]) for key in ("start_date", "end_date"))
    days = []
    day = start
    while day <= end:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    assert days[0] == start and days[-1] == end
    series = []
    for index, day in enumerate(days):
        if plan is None:
            invested = principal
        else:
            count = (day.year - start.year) * 12 + day.month - start.month + 1
            assert plan.period == "monthly" and count <= contribution_count
            invested = plan.total_invested(count)
        value = Decimal(str(invested)) + profit * index / (len(days) - 1)
        series.append({"time": day.isoformat(), "value": float(value)})
    assert Decimal(str(series[-1]["value"])) == ending_value
    assert all(a["value"] <= b["value"] for a, b in zip(series, series[1:]))
    chart = {
        "kind": "portfolio_equity", "currency": "USD",
        "base_value": series[0]["value"], "series": series,
    }
    ledger = {
        "principal_owner": principal_owner,
        "principal": principal,
        "net_return_pct": float(net_return_pct),
        "profit": float(profit),
        "ending_value": float(ending_value),
        "chart_start_value": series[0]["value"],
        "chart_end_value": series[-1]["value"],
        "chart_start_date": series[0]["time"],
        "chart_end_date": series[-1]["time"],
        "chart_semantics": "Authored linear profit accrual across weekdays, plus actual monthly DCA contribution facts; no engine execution",
        "cash_value_by_locale": {},
    }
    if plan is not None:
        ledger.update(
            starting_capital=plan.starting_capital,
            recurring_contribution=plan.contribution,
            contribution_count=contribution_count,
            cadence=plan.period,
        )
    return snapshot, metrics, chart, ledger


def completed_final(snapshot, metrics, chart, language):
    return {
        "result": {
            "execution_status": "succeeded",
            "resolved_strategy": snapshot["resolved_strategy"],
            "resolved_parameters": {**snapshot["resolved_parameters"], "benchmark_symbol": snapshot["benchmark_symbol"]},
            "metrics": metrics,
        },
        "result_card": build_result_card(snapshot["engine_config"], metrics, language=language, chart=chart),
    }


def cash_value(final):
    return next(row["value"] for row in final["result_card"]["rows"] if row["key"] == "cash_value")


declaration = get_backtest_declaration()
fixture_dir = ROOT / "checkout/docs/reports/evidence/registry"
coherence = {}
dca_snapshot, dca_metrics, dca_chart, coherence["dca_accumulation"] = coherent_fixture("dca_accumulation")
backtests = {}
for language in ("en", "es-419"):
    final = completed_final(dca_snapshot, dca_metrics, dca_chart, language)
    card = declaration.result_card(
        call=ToolCall(tool_name=declaration.name, call_id="backtest-call", arguments={"strategy": {"asset_universe": final["result_card"]["symbols"]}}),
        outcome=ToolOutcome(status="succeeded", result=backtest_execution_result(final).model_dump(mode="json")),
        artifact_id="backtest-artifact",
    )
    backtests[language] = {"card": card.model_dump(mode="json")}
    coherence["dca_accumulation"]["cash_value_by_locale"][language] = cash_value(final)
(fixture_dir / "backtest-cards.json").write_text(json.dumps(backtests, indent=2) + "\n")

snapshot, metrics, chart, coherence["signal_strategy"] = coherent_fixture("signal_strategy")
engine = snapshot["engine_config"]
strategy = StrategySummary(
    strategy_type=engine["template"],
    asset_universe=engine["symbols"],
    asset_class=engine["asset_class"],
    timeframe=engine["timeframe"],
    date_range={"start": engine["start_date"], "end": engine["end_date"]},
    capital_amount=engine["starting_capital"],
    comparison_baseline=engine["benchmark_symbol"],
    entry_rule=snapshot["resolved_strategy"]["entry_rule"],
)
signal = {"cards": {}, "expected": {key: strategy.entry_rule[key] for key in ("fast_period", "slow_period", "signal_period")}}
for language in ("en", "es-419"):
    final = completed_final(snapshot, metrics, chart, language)
    card = declaration.result_card(
        call=ToolCall(tool_name=declaration.name, call_id="signal-call", arguments={"strategy": strategy.model_dump(mode="json")}),
        outcome=ToolOutcome(status="succeeded", result=backtest_execution_result(final).model_dump(mode="json")),
        artifact_id="signal-artifact",
    )
    signal["cards"][language] = card.model_dump(mode="json")
    coherence["signal_strategy"]["cash_value_by_locale"][language] = cash_value(final)

(fixture_dir / "signal-cards.json").write_text(json.dumps(signal, indent=2) + "\n")
(ROOT / "fixture-coherence.json").write_text(json.dumps(coherence, indent=2) + "\n")
for file in fixture_dir.glob("*.json"):
    shutil.copy2(file, ROOT / file.name)
assert not attempts
paths = [
    "web/e2e/support/registry-fixture.py", "web/e2e/tool-registry.spec.ts",
    "web/e2e/support/mobile-shell-fixture.ts", "tests/public_excerpt_factories.py",
    "tests/agent_runtime/test_registered_backtest_presentation.py",
    "src/argus/agent_runtime/state/models.py", "src/argus/agent_runtime/tools/registered_backtest.py",
    "src/argus/agent_runtime/tools/backtest_presentation.py", "src/argus/agent_runtime/tools/backtest_result_facts.py",
    "src/argus/domain/tool_declaration.py", "src/argus/domain/tool_contracts.py",
    "src/argus/domain/dca_capital.py", "src/argus/domain/backtesting/cards.py",
    "web/components/chat/ChatInterface.tsx",
    "web/components/chat/ToolResultCard.tsx", "web/components/chat/ToolCardPresentation.tsx",
    "web/lib/tool-result-card.ts", "web/public/locales/en/common.json", "web/public/locales/es-419/common.json",
]
provenance = {
    "source_sha": HEAD,
    "source_clean_before_generation": True,
    "evidence_kind": "authored_rendered_fixture",
    "generator_network_attempts": len(attempts),
    "provider_calls": 0, "interpreter_calls": 0, "backtest_handler_calls": 0,
    "real_api_calls": 0,
    "source_files": {path: hashlib.sha256((SOURCE / path).read_bytes()).hexdigest() for path in paths},
    "fixture_files": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in ROOT.glob("*-cards.json")},
    "wrapper": "Existing test-only echo declaration; actual registered backtest result projector and presenter consume authored DCA/MACD engine fixtures. No backtest handler or model was invoked.",
    "numeric_fixture_owner": "fixture-coherence.json: principal from engine config or DcaCapitalPlan; profit and ending value from that principal and authored net return; chart endpoints derived from the same values",
}
provenance["fixture_files"]["tool-progress.json"] = hashlib.sha256((ROOT / "tool-progress.json").read_bytes()).hexdigest()
provenance["fixture_files"]["fixture-coherence.json"] = hashlib.sha256((ROOT / "fixture-coherence.json").read_bytes()).hexdigest()
(ROOT / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
print(json.dumps({"source_sha": HEAD, "fixture_files": sorted(provenance["fixture_files"]), "network_attempts": len(attempts)}, indent=2))
