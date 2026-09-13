"""One chat turn through the local Argus API; records the stream, the persisted
assistant message with its research sidecar, and the share candidates.
Usage: python ask.py <label> <language> <question> <out.json>"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

import httpx

label, language, question, out = sys.argv[1:5]
API = f"http://127.0.0.1:{os.getenv('OTG_API_PORT', '8590')}/api/v1"
record = {
    "label": label,
    "language": language,
    "question": question,
    "asked_at": datetime.now(timezone.utc).isoformat(),
    "source": "local Argus API (memory persistence, mock auth), real interpreter and research provider",
    "events": [],
}
started = time.monotonic()
with httpx.Client(base_url=API, timeout=300) as client:
    me = client.get("/me"); me.raise_for_status()
    record["account_kind"] = me.json().get("account_kind")
    if language == "es-419":
        client.patch("/me", json={"language": "es-419"}).raise_for_status()
    created = client.post("/conversations", json={"title": question[:60], "language": language})
    created.raise_for_status()
    conversation_id = created.json()["conversation"]["id"]
    record["conversation_id"] = conversation_id
    with client.stream("POST", "/chat/stream", json={"conversation_id": conversation_id, "message": question, "language": language, "memory_opt_out": True}) as stream:
        stream.raise_for_status()
        for line in stream.iter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                record["done"] = True
                break
            record["events"].append(json.loads(data))
    messages = client.get(f"/conversations/{conversation_id}/messages", params={"limit": 50}); messages.raise_for_status()
    record["messages"] = messages.json()
    candidates = client.get(f"/conversations/{conversation_id}/public-excerpt-candidates")
    record["candidates_status"] = candidates.status_code
    record["candidates"] = candidates.json() if candidates.status_code == 200 else candidates.text
record["elapsed_seconds"] = round(time.monotonic() - started, 2)
payload = record["messages"]
items = payload.get("items") or payload.get("messages") or [] if isinstance(payload, dict) else payload
assistant = [m for m in items if isinstance(m, dict) and m.get("role") == "assistant"]
final = assistant[-1] if assistant else {}
research = (final.get("metadata") or {}).get("research") or {}
summary = {
    "label": label,
    "elapsed_seconds": record["elapsed_seconds"],
    "assistant_text": final.get("content"),
    "shape": research.get("shape"),
    "degraded": research.get("degraded"),
    "rows": research.get("rows"),
    "sources": research.get("sources"),
    "usage": research.get("usage"),
    "candidates": record["candidates"],
}
record["summary"] = summary
with open(out, "w") as f:
    json.dump(record, f, indent=2, ensure_ascii=False)
print(json.dumps(summary, indent=2, ensure_ascii=False))
