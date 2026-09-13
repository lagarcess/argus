"""Authored browser controls; real presenters, no interpreter or backtest call."""

import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import socket
import subprocess
import sys

SOURCE = Path("/Users/garces/.codex/worktrees/aa72/private-alpha-next")
ROOT = Path(__file__).resolve().parent
HEAD = "b17d25775028b7d7e2ea2f30ab35348291c973cc"
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
from argus.domain.tool_contracts import ToolCall, ToolOutcome
from tests.public_excerpt_factories import build_chart, generated_card_metrics, generated_card_snapshot

snapshot = generated_card_snapshot("signal_strategy", modeled_costs=True)
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
metrics = generated_card_metrics(modeled_costs=True)
declaration = get_backtest_declaration()
signal = {"cards": {}, "expected": {key: strategy.entry_rule[key] for key in ("fast_period", "slow_period", "signal_period")}}
for language in ("en", "es-419"):
    final = {
        "result": {
            "execution_status": "succeeded",
            "resolved_strategy": snapshot["resolved_strategy"],
            "resolved_parameters": {**snapshot["resolved_parameters"], "benchmark_symbol": snapshot["benchmark_symbol"]},
            "metrics": metrics,
        },
        "result_card": {**build_result_card(engine, metrics, language=language), "chart": build_chart()},
    }
    card = declaration.result_card(
        call=ToolCall(tool_name=declaration.name, call_id="signal-call", arguments={"strategy": strategy.model_dump(mode="json")}),
        outcome=ToolOutcome(status="succeeded", result=backtest_execution_result(final).model_dump(mode="json")),
        artifact_id="signal-artifact",
    )
    signal["cards"][language] = card.model_dump(mode="json")

fixture_dir = ROOT / "checkout/docs/reports/evidence/registry"
(fixture_dir / "signal-cards.json").write_text(json.dumps(signal, indent=2) + "\n")
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
}
provenance["fixture_files"]["tool-progress.json"] = hashlib.sha256((ROOT / "tool-progress.json").read_bytes()).hexdigest()
(ROOT / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
print(json.dumps({"source_sha": HEAD, "fixture_files": sorted(provenance["fixture_files"]), "network_attempts": len(attempts)}, indent=2))
