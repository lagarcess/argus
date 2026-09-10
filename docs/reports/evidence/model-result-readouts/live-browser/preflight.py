"""Read-only live browser preflight. Fetches public prices, never completions."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path.cwd()
OUT = Path(__file__).parent
load_dotenv(ROOT / ".env", override=True)
sys.path.insert(0, str(ROOT / "src"))
from argus.llm.openrouter import openrouter_model_candidates, openrouter_profile_for_task  # noqa: E402
from argus.llm.openrouter_tasks import OPENROUTER_TASK_MODEL_TIERS  # noqa: E402

tasks = {
    task: {"tier": tier, "models": openrouter_model_candidates(task=task), "profile": asdict(openrouter_profile_for_task(task))}
    for task, tier in OPENROUTER_TASK_MODEL_TIERS.items()
}
models = sorted({model for row in tasks.values() for model in row["models"]})
catalog_url = "https://openrouter.ai/api/v1/models"
with urllib.request.urlopen(catalog_url, timeout=30) as response:
    catalog = json.load(response)
rates = {
    model["id"]: {key: model.get(key) for key in ("id", "canonical_slug", "context_length", "pricing", "top_provider")}
    for model in catalog["data"] if model["id"] in models
}
report = {
    "checked_at": datetime.now(timezone.utc).isoformat(),
    "candidate_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "source": catalog_url,
    "catalog_request_authenticated": False,
    "completion_requests": 0,
    "tasks": tasks,
    "models": rates,
    "unpriced_models": sorted(set(models) - set(rates)),
    "credentials_present": {name: bool(os.getenv(name)) for name in ("ARGUS_PROD_OPENROUTER_API_KEY", "ARGUS_GUEST_ACCESS_OPENROUTER_API_KEY", "ALPACA_API_KEY", "ALPACA_SECRET_KEY")},
    "browser_spend_cap_usd": "1.00",
    "real_backtest_cap": 4,
    "run_authorized": False,
}
(OUT / "preflight.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({"models": {name: row["pricing"] for name, row in rates.items()}, "unpriced_models": report["unpriced_models"], "credentials_present": report["credentials_present"], "completion_requests": 0}, indent=2))
