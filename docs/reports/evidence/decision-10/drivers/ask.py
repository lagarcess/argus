"""One chat turn through the local Argus API; records the stream, the persisted
assistant message with its research sidecar and clarification contract, and a
summary row for the before/after table.
Usage: python ask.py <label> <language> <question> <out.json>"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

import httpx

label, language, question, out = sys.argv[1:5]
API = f"http://127.0.0.1:{os.getenv('D10_API_PORT', '8610')}/api/v1"
record = {
    "label": label,
    "language": language,
    "question": question,
    "asked_at": datetime.now(timezone.utc).isoformat(),
    "tree": os.getenv("D10_TREE_LABEL"),
    "source": "local Argus API (memory persistence, mock auth), real interpreter and research provider",
    "events": [],
}
started = time.monotonic()
with httpx.Client(base_url=API, timeout=600) as client:
    me = client.get("/me"); me.raise_for_status()
    client.patch("/me", json={"language": language}).raise_for_status()
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
    # A thorough research turn answers through a background job; wait for it.
    deadline = time.monotonic() + 420
    while True:
        messages = client.get(f"/conversations/{conversation_id}/messages", params={"limit": 50}); messages.raise_for_status()
        payload = messages.json()
        items = payload.get("items") or payload.get("messages") or [] if isinstance(payload, dict) else payload
        assistant = [m for m in items if isinstance(m, dict) and m.get("role") == "assistant"]
        final = assistant[-1] if assistant else {}
        metadata = final.get("metadata") or {}
        job = metadata.get("research_job") or {}
        if not job or job.get("status") in ("completed", "failed", "cancelled") or time.monotonic() > deadline:
            break
        time.sleep(5)
    record["messages"] = payload
record["elapsed_seconds"] = round(time.monotonic() - started, 2)
research = metadata.get("research") or {}
clarification = metadata.get("clarification") or {}
recovery = metadata.get("recovery") or {}
turn = metadata.get("agent_runtime_turn") or {}
outcomes = [e.get("outcome") or e.get("stage") for e in record["events"] if e.get("type") == "stage_outcome"]
summary = {
    "label": label,
    "language": language,
    "elapsed_seconds": record["elapsed_seconds"],
    "stage_outcomes": outcomes,
    # Answered means a real answer reached the user: prose with neither a
    # clarification contract nor a recovery code beside it.
    "answered": bool(final.get("content")) and not clarification and not recovery.get("code"),
    "recovery_code": recovery.get("code"),
    "clarification_kind": clarification.get("kind"),
    "clarification_reason_code": clarification.get("reason_code"),
    "reason_codes": turn.get("reason_codes") if isinstance(turn, dict) else None,
    "intent": turn.get("intent") if isinstance(turn, dict) else None,
    "semantic_turn_act": turn.get("semantic_turn_act") if isinstance(turn, dict) else None,
    "assistant_text": final.get("content"),
    "shape": research.get("shape"),
    "degraded": research.get("degraded"),
    "rows": len(research.get("rows") or []),
    "sources": [s.get("url") or s.get("domain") for s in (research.get("sources") or [])],
    "research_usage": research.get("usage"),
    "next_experiments": [row.get("label") for row in ((metadata.get("next_experiments") or {}).get("rows") or [])],
}
record["summary"] = summary
with open(out, "w") as f:
    json.dump(record, f, indent=2, ensure_ascii=False)
print(json.dumps(summary, indent=2, ensure_ascii=False))
