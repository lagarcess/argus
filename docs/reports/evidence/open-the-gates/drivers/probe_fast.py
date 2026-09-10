"""Sample what the provider cites on the fast shape for the Nike question,
through the repository's own prompt builder, spec and parser. Usage:
python probe_fast.py <label> <tools:finance|finance+web> <out.json>"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

TREE = Path(os.environ["OTG_TREE"]).resolve()
sys.path.insert(0, str(TREE / "src"))
load_dotenv(TREE / ".env", override=False)
os.environ["ARGUS_RESEARCH_RAIL_ENABLED"] = "true"
from argus.agent_runtime import research_grounded as grounded  # noqa: E402
from argus.domain.research.config import retrieval_spec  # noqa: E402
from argus.domain.research.perplexity_agent import (  # noqa: E402
    PERPLEXITY_AGENT_URL,
    PerplexityAgentClient,
    _packet_from_response,
)

label, tools, out = sys.argv[1:4]
spec = retrieval_spec("fast", question_kind="live_quote", closed_period=False, language_tag="en")
if tools == "finance+web":
    spec = spec.model_copy(update={"tools": ("finance_search", "web_search"), "max_steps": 3})
prompt = grounded._research_prompt(
    message="what's the price of nike today",
    subjects=[{"symbol": "NKE", "name": "NIKE, Inc.", "asset_class": "equity"}],
    period=None, language="en", question_kind="live_quote",
)
client = PerplexityAgentClient(os.environ["PERPLEXITY_API_KEY"])
body = client._request_body(prompt, spec)
started = time.monotonic()
response = httpx.post(PERPLEXITY_AGENT_URL, headers={"Authorization": f"Bearer {os.environ['PERPLEXITY_API_KEY']}", "Content-Type": "application/json"}, json=body, timeout=spec.timeout_seconds)
elapsed = round(time.monotonic() - started, 2)
document = response.json()
packet = _packet_from_response(document, latency_ms=int(elapsed * 1000), on_unpriced=lambda _: None)
summary = {
    "label": label, "tools": list(spec.tools), "http_status": response.status_code, "elapsed_seconds": elapsed,
    "answer_markdown": packet.answer_markdown,
    "rows": [row.model_dump() for row in packet.rows],
    "rejected_rows": [row.model_dump() for row in packet.rejected_rows],
    "sources": [source.model_dump() for source in packet.sources],
    "tool_results": list(packet.tool_results),
    "cost_usd": (document.get("usage") or {}).get("cost", {}).get("total_cost"),
}
record = {"captured_at": datetime.now(timezone.utc).isoformat(), "candidate_sha": os.popen(f"git -C {TREE} rev-parse HEAD").read().strip(), "request": body, "response": document, "summary": summary}
Path(out).write_text(json.dumps(record, indent=2, ensure_ascii=False))
print(json.dumps(summary, indent=2, ensure_ascii=False))
