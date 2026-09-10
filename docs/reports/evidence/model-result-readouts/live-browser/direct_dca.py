"""One authorized fourth engine fixture, without model interpretation or prose."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path.cwd()
OUT = Path(__file__).parent
HEAD = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
if os.environ.get("READOUT_DIRECT_DCA_GO") != "1" or os.environ.get("READOUT_LIVE_SHA") != HEAD:
    raise SystemExit("Explicit one-fixture authorization and exact clean source required")
if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
    raise SystemExit("Whole checkout, including evidence, must be clean before the fourth fixture")
with socket.socket() as sock:
    if sock.connect_ex(("127.0.0.1", 8540)) == 0:
        raise SystemExit("Stop the memory API first so it cannot overwrite cumulative accounting")

prior = json.loads((OUT / "fee-ledger.json").read_text())
if len(prior["backtest_attempts"]) != 3 or any(row["case"] == "dca-costs" for row in prior["backtest_attempts"]):
    raise SystemExit("Exactly three prior backtests and one unused DCA allowance required")
if prior.get("in_flight_reservation_usd") != "0":
    raise SystemExit("All provider requests must be settled or conservatively charged")
if (OUT / "stored-runs/dca-costs.json").exists():
    raise SystemExit("Never repeat a DCA engine fixture")

load_dotenv(ROOT / ".env", override=True)
for name in tuple(os.environ):
    if any(part in name.upper() for part in ("SUPABASE", "DATABASE", "POSTHOG", "PERPLEXITY", "LANGSMITH", "OPENROUTER")):
        os.environ[name] = ""
os.environ.update({"PYTHON_DOTENV_DISABLED": "1", "ARGUS_PERSISTENCE_MODE": "memory", "ARGUS_DEV_MEMORY_FALLBACK": "true", "ARGUS_CHECKPOINTER_MODE": "memory", "ARGUS_MOCK_AUTH": "true", "ARGUS_MARKET_DATA_PROVIDER_MODE": "live_provider", "ARGUS_ASSET_PROVIDER_MODE": "live_provider", "ENABLE_MARKET_DATA_CACHE": "false"})
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(1, str(ROOT))
from budget import Budget, install_http_budget

class NoModelsBudget(Budget):
    def reserve(self, payload):
        raise RuntimeError("No model requests authorized for the direct DCA fixture")

budget = NoModelsBudget(OUT / "fee-ledger.json", cap=prior["cap_usd"])
(OUT / "fee-ledger-before-direct-dca.json").write_text(json.dumps(prior, indent=2) + "\n")
budget.restore(prior, prior["backtest_attempts"], HEAD)
budget.candidate_sha = HEAD
budget.case = "dca-costs"
provider_requests = []
install_http_budget(budget, provider_requests)
from argus.agent_runtime.tools.real_backtest import RealBacktestTool
from argus.domain.backtest_run_builder import build_backtest_run_from_result
from argus.domain.backtesting.confirmation_preflight import prepare_confirmation_launch
from argus.domain.engine_launch.models import LaunchBacktestRequest
from argus.domain.backtesting.config import _execution_realism_feature_enabled
from argus.domain.dca_capital import dca_capital_plan_from_config

if not _execution_realism_feature_enabled():
    raise SystemExit("Configured execution-cost capability is disabled; do not silently remove costs")

payload = {
    "strategy_type": "dca_accumulation", "symbol": "DOCN", "symbols": ["DOCN"], "asset_class": "equity", "timeframe": "1D",
    "date_range": {"start": "2025-09-10", "end": "2026-09-09"}, "sizing_mode": "capital_amount", "capital_amount": 100.0,
    "starting_capital": 1000.0, "recurring_contribution": 100.0, "cadence": "monthly", "benchmark_symbol": "SPY", "language": "en",
    "_execution_realism": {"enabled": True, "fee_bps": 10.0, "slippage_bps": 5.0},
}
LaunchBacktestRequest.model_validate(payload)
prepared = prepare_confirmation_launch(payload)
if prepared.outcome != "ready_to_confirm" or not prepared.launch_payload:
    (OUT / "direct-dca-preflight-failure.json").write_text(json.dumps({"outcome": prepared.outcome, "error_code": prepared.error_code}) + "\n")
    raise SystemExit("Canonical live coverage preflight failed; no engine attempt issued")
(OUT / "direct-dca-launch.json").write_text(json.dumps(prepared.launch_payload, indent=2) + "\n")
index = budget.reserve_backtest(prepared.launch_payload)
budget.backtest_attempts[index]["execution_path"] = "direct typed engine fixture; blocked DCA chat journey is preserved"
budget._flush()
result = RealBacktestTool().run(prepared.launch_payload)
budget.finish_backtest(index, result.get("success"))
raw_result = json.dumps(result, indent=2, default=str).encode()
(OUT / "direct-dca-engine-result.json.gz").write_bytes(gzip.compress(raw_result, mtime=0))
if result.get("success") is not True:
    raise SystemExit("Fourth engine attempt failed; preserved without retry")
run = build_backtest_run_from_result(conversation_id="117afaa2-1fb5-492e-a151-46ae4eba936f", result_card=result["payload"]["result_card"], envelope=result["payload"]["envelope"])
if run is None:
    raise SystemExit("Canonical stored-run builder failed; do not invent a record")
record = run.model_dump(mode="json")
target = OUT / "stored-runs/dca-costs.json"
target.write_text(json.dumps(record, indent=2) + "\n")
config = record["config_snapshot"]["engine_config"]
capital_plan = dca_capital_plan_from_config(config)
assert capital_plan.starting_capital == 1000.0
assert capital_plan.contribution == 100.0
assert config["parameters"]["dca_cadence"] == "monthly"
assert config["_execution_realism"]["fee_bps"] == 10.0
assert config["_execution_realism"]["slippage_bps"] == 5.0
assert config["symbols"] == ["DOCN"] and config["benchmark_symbol"] == "SPY"
report = {"candidate_sha": HEAD, "execution_path": "canonical prepare_confirmation_launch -> RealBacktestTool -> build_backtest_run_from_result", "successful_chat_or_browser_journey": False, "history_rewrites": 0, "models_disabled": True, "before_model_attempt_count": len(prior["attempts"]), "after_model_attempt_count": len(budget.attempts), "total_backtest_attempts": len(budget.backtest_attempts), "provider_requests": provider_requests, "stored_run": str(target.relative_to(ROOT)), "stored_run_sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "raw_engine_result_uncompressed_sha256": hashlib.sha256(raw_result).hexdigest(), "approved_inputs_verified": True, "accounted_cost_usd": budget.summary()["accounted_cost_usd"]}
(OUT / "direct-dca-proof.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
