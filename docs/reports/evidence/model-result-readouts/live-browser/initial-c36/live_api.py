"""Approved local real-provider browser proof, bounded to four backtests/$1."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path.cwd()
OUT = Path(__file__).parent
EXPECTED = os.environ.get("READOUT_LIVE_SHA", "")
HEAD = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
if os.environ.get("READOUT_LIVE_GO") != "1" or not EXPECTED or EXPECTED != HEAD:
    raise SystemExit("Explicit go and exact committed candidate required")
if subprocess.check_output(["git", "status", "--porcelain", "--", "src", "web"], text=True).strip():
    raise SystemExit("Runtime source must be clean")
if (OUT / "fee-ledger.json").exists():
    raise SystemExit("Existing fee ledger: do not silently reset a paid run")

load_dotenv(ROOT / ".env", override=True)
for name in tuple(os.environ):
    if any(part in name.upper() for part in ("SUPABASE", "DATABASE", "POSTHOG", "PERPLEXITY", "LANGSMITH")):
        os.environ[name] = ""
os.environ.update({
    "PYTHON_DOTENV_DISABLED": "1", "ARGUS_PERSISTENCE_MODE": "memory", "ARGUS_DEV_MEMORY_FALLBACK": "true", "ARGUS_CHECKPOINTER_MODE": "memory", "ARGUS_MOCK_AUTH": "true",
    "ARGUS_MARKET_DATA_PROVIDER_MODE": "live_provider", "ARGUS_ASSET_PROVIDER_MODE": "live_provider", "ENABLE_MARKET_DATA_CACHE": "false",
    "ARGUS_BACKTEST_JOBS_SHADOW_ENABLED": "false", "ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED": "false", "ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED": "false",
    "ARGUS_CORS_ALLOW_ORIGINS": "http://127.0.0.1:3220,http://localhost:3220", "ARGUS_APP_ORIGIN": "http://127.0.0.1:3220",
})
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(1, str(ROOT))
from budget import Budget, RATES, install_http_budget  # noqa: E402

BUDGET = Budget(OUT / "fee-ledger.json")
PROVIDER_REQUESTS: list[dict[str, Any]] = []
install_http_budget(BUDGET, PROVIDER_REQUESTS)
from argus.api.main import app  # noqa: E402
from argus.api import state  # noqa: E402
from argus.agent_runtime.tools.real_backtest import RealBacktestTool  # noqa: E402
from argus.llm.openrouter import get_openrouter_route_receipts, openrouter_model_candidates  # noqa: E402
from argus.llm.openrouter_tasks import OPENROUTER_TASK_MODEL_TIERS  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402

for task in OPENROUTER_TASK_MODEL_TIERS:
    if any(model not in RATES for model in openrouter_model_candidates(task=task)):
        raise SystemExit("Configured model missing approved rate envelope")

_run = RealBacktestTool.run
RUN_ATTEMPTS: list[dict[str, Any]] = []
RUN_CASES: dict[str, str] = {}


def run(tool: Any, payload: dict[str, Any]) -> Any:
    if len(RUN_ATTEMPTS) >= 4 or BUDGET.halted:
        raise RuntimeError("Live browser backtest/budget cap reached")
    RUN_ATTEMPTS.append({"case": BUDGET.case, "payload_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()})
    result = _run(tool, payload)
    RUN_ATTEMPTS[-1]["success"] = result.get("success")
    return result


RealBacktestTool.run = run


def seed_old_run() -> str | None:
    source = Path("/private/tmp/model-result-readouts-recorded-docn.json")
    if not source.exists():
        return None
    from argus.api.schemas import BacktestRun, Conversation, Message
    from argus.domain.backtest_message_projection import result_fact_bank
    payload = json.loads(source.read_text())["run"]
    stored = BacktestRun.model_validate(payload)
    conversation_id = "00000000-0000-4000-8000-000000005499"
    stored = stored.model_copy(update={"conversation_id": conversation_id})
    # The supplied genuine run has only its saved date-range card. Reconstruct
    # a local control to request a Breakdown without inventing any run figure.
    card = {**stored.conversation_result_card, "symbols": stored.symbols, "actions": [{"id": "show-breakdown", "type": "show_breakdown", "label": "Explain result", "labelKey": "chat.result_card.explain_result", "presentation": "result", "payload": {"run_id": stored.id, "conversation_id": conversation_id}}]}
    stored = stored.model_copy(update={"conversation_result_card": card})
    user = state.store.get_or_create_dev_user()
    state.store.backtest_runs[stored.id] = stored
    state.store.backtest_run_owners[stored.id] = user.id
    state.store.conversation_owners[conversation_id] = user.id
    state.store.messages[conversation_id] = [Message(id="00000000-0000-4000-8000-000000005498", conversation_id=conversation_id, role="assistant", content="", created_at=stored.created_at, metadata={"result_card": stored.conversation_result_card, "result_fact_bank": result_fact_bank(stored), "result_run_id": stored.id, "result_conversation_id": conversation_id})]
    state.store.conversations[conversation_id] = Conversation(id=conversation_id, title="Saved DOCN run: new Breakdown proof", title_source="user_renamed", language="en", created_at=stored.created_at, updated_at=stored.created_at, last_message_preview="Saved DOCN result")
    RUN_CASES[stored.id] = "old-run-new-breakdown"
    return conversation_id


OLD_CONVERSATION_ID = seed_old_run()


def sanitized(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: sanitized(item) for key, item in value.items() if key.lower() not in {"user_id", "owner_id", "email", "authorization", "api_key", "access_token", "refresh_token", "secret", "password"}}
    if isinstance(value, list):
        return [sanitized(item) for item in value]
    return value


def export() -> dict[str, Any]:
    runs = {}
    for run_id, stored in state.store.backtest_runs.items():
        RUN_CASES.setdefault(run_id, BUDGET.case)
        row = sanitized(stored.model_dump(mode="json") if hasattr(stored, "model_dump") else stored)
        label = RUN_CASES[run_id]
        target = OUT / "stored-runs" / f"{label}.json"
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(row, indent=2) + "\n")
        runs[run_id] = {"case": label, "path": str(target.relative_to(ROOT)), "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "symbols": row.get("symbols"), "template": row.get("config_snapshot", {}).get("template")}
    messages = {key: [sanitized(message.model_dump(mode="json")) for message in rows] for key, rows in state.store.messages.items()}
    (OUT / "messages.json").write_text(json.dumps(messages, indent=2) + "\n")
    receipts = [receipt.as_dict() for receipt in get_openrouter_route_receipts()]
    (OUT / "route-receipts.json").write_text(json.dumps(receipts, indent=2) + "\n")
    report = {"candidate_sha": HEAD, "runtime_source_clean": not subprocess.check_output(["git", "status", "--porcelain", "--", "src", "web"], text=True).strip(), "budget": BUDGET.summary(), "run_attempts": RUN_ATTEMPTS, "stored_runs": runs, "provider_requests": PROVIDER_REQUESTS, "route_receipt_count": len(receipts), "hosted_database_calls": 0, "persistence": "memory", "provider_mode": "live_provider", "old_conversation_id": OLD_CONVERSATION_ID}
    (OUT / "environment.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


@app.middleware("http")
async def qa_routes(request: Any, call_next: Any) -> Any:
    if request.url.path == "/qa/state":
        return JSONResponse(export())
    if request.url.path == "/qa/case" and request.method == "POST":
        body = await request.json()
        label = body.get("case")
        if label not in {"docn-en", "docn-es", "dca-costs", "indicator", "old-run-new-breakdown"}:
            return JSONResponse({"error": "unapproved_case"}, status_code=400)
        export()
        BUDGET.case = label
        return JSONResponse({"case": label, "budget": BUDGET.summary()})
    if BUDGET.halted and request.method == "POST" and "/chat" in request.url.path:
        return JSONResponse({"detail": "Browser QA budget halted"}, status_code=409)
    return await call_next(request)


if __name__ == "__main__":
    # This sanctioned free market-data probe must pass before any model request.
    from tests.evals.measurement_eval_scorecard import verify_live_market_data_environment
    probe = verify_live_market_data_environment()
    (OUT / "market-data-probe.json").write_text(json.dumps(probe.as_dict(), indent=2) + "\n")
    export()
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8540)
