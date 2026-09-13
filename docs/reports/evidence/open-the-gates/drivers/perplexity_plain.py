"""The same question asked of Perplexity directly: the Agent API with the
question as typed, no Argus instructions or schema, finance and web tools on.
Usage: python perplexity_plain.py <label> <question> <out.json>"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(os.environ["OTG_TREE"]) / ".env", override=False)
label, question, out = sys.argv[1:4]
body = {
    "models": ["openai/gpt-5.6-sol"],
    "input": question,
    "tools": [{"type": "finance_search"}, {"type": "web_search"}],
    "max_steps": 5,
}
started = time.monotonic()
response = httpx.post(
    "https://api.perplexity.ai/v1/agent",
    headers={"Authorization": f"Bearer {os.environ['PERPLEXITY_API_KEY']}", "Content-Type": "application/json"},
    json=body,
    timeout=180,
)
elapsed = round(time.monotonic() - started, 2)
document = response.json()
text = "\n\n".join(
    chunk.get("text", "")
    for item in document.get("output", []) if item.get("type") == "message"
    for chunk in item.get("content", []) if chunk.get("type") == "output_text"
)
record = {
    "label": label,
    "question": question,
    "asked_at": datetime.now(timezone.utc).isoformat(),
    "source": "Perplexity Agent API, question as typed, no Argus instructions or schema",
    "request": body,
    "http_status": response.status_code,
    "elapsed_seconds": elapsed,
    "answer_text": text,
    "tool_results": [item.get("type") for item in document.get("output", []) if item.get("type") not in ("message", "skill_loaded")],
    "usage": document.get("usage"),
    "response": document,
}
with open(out, "w") as f:
    json.dump(record, f, indent=2, ensure_ascii=False)
print(json.dumps({k: record[k] for k in ("label", "http_status", "elapsed_seconds", "answer_text", "tool_results")}, indent=2, ensure_ascii=False))
print("cost:", (document.get("usage") or {}).get("cost", {}).get("total_cost"))
