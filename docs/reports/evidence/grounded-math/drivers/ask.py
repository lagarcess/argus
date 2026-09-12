"""Chat turns through the local Argus API, one conversation, recording what
each turn stored: the card, its marker, the clarification and the research
sidecar. A later reply continues the same conversation.
Usage: python ask.py <label> <language> <country> <out.json> <message> [<reply> ...]
Set GM_CONVERSATION_ID to continue an existing conversation; its turns append to <out.json>. Paid."""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

import httpx

label, language, country, out, *messages = sys.argv[1:]
API = f"http://127.0.0.1:{os.getenv('GM_API_PORT', '8620')}/api/v1"


def summarize(metadata: dict, content: str) -> dict:
    cards = metadata.get("tool_result_cards") or []
    card = cards[0] if cards else {}
    presentation = card.get("presentation") or {}
    answer = presentation.get("answer") or {}
    research = metadata.get("research") or {}
    clarification = metadata.get("clarification") or {}
    turn = metadata.get("agent_runtime_turn") or {}
    return {
        "content": content,
        "tool": card.get("tool_name"),
        "status": (card.get("outcome") or {}).get("status"),
        "failure": ((card.get("outcome") or {}).get("failure") or {}).get("code"),
        "answer": {"label": (answer.get("label") or {}).get("locale_key"), "value": answer.get("value")} if answer else None,
        "inputs": [
            {"name": fact.get("name"), "value": fact.get("value"), "source": (fact.get("source") or {}).get("kind")}
            for fact in presentation.get("inputs") or []
        ],
        "currency": (card.get("arguments") or {}).get("currency"),
        "computation": bool(metadata.get("computation")),
        "requested_field": clarification.get("requested_field"),
        "clarification_reason": clarification.get("reason_code"),
        "next_steps": ((metadata.get("next_steps") or {}).get("items")),
        "next_experiments": [row.get("label") for row in ((metadata.get("next_experiments") or {}).get("rows") or [])],
        "research": {"shape": research.get("shape"), "degraded": research.get("degraded"), "rows": len(research.get("rows") or []), "sources": len(research.get("sources") or []), "cost_usd": (research.get("usage") or {}).get("cost_usd")} if research else None,
        "reason_codes": turn.get("reason_codes") if isinstance(turn, dict) else None,
        "intent": turn.get("intent") if isinstance(turn, dict) else None,
    }


record = {"label": label, "language": language, "country": country, "asked_at": datetime.now(timezone.utc).isoformat(), "turns": []}
if os.getenv("GM_CONVERSATION_ID") and os.path.exists(out):
    with open(out) as handle:
        record = json.load(handle)
with httpx.Client(base_url=API, timeout=600) as client:
    profile = client.patch("/me", json={"language": language, "country": country})
    if profile.status_code >= 400:
        client.patch("/me", json={"language": language}).raise_for_status()
    conversation_id = os.getenv("GM_CONVERSATION_ID")
    if not conversation_id:
        created = client.post("/conversations", json={"title": messages[0][:60], "language": language})
        created.raise_for_status()
        conversation_id = created.json()["conversation"]["id"]
    record["conversation_id"] = conversation_id
    for message in messages:
        started = time.monotonic()
        events = []
        with client.stream("POST", "/chat/stream", json={"conversation_id": conversation_id, "message": message, "language": language, "memory_opt_out": True}) as stream:
            stream.raise_for_status()
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    events.append(json.loads(data))
        items = client.get(f"/conversations/{conversation_id}/messages", params={"limit": 50}).json()["items"]
        final = [item for item in items if item.get("role") == "assistant"][-1]
        turn = {"message": message, "message_id": final["id"], "elapsed_seconds": round(time.monotonic() - started, 2), "summary": summarize(final.get("metadata") or {}, final.get("content") or ""), "metadata": final.get("metadata")}
        record["turns"].append(turn)
        print(json.dumps({"label": label, "message": message, **turn["summary"]}, ensure_ascii=False, indent=1))
with open(out, "w") as handle:
    json.dump(record, handle, indent=2, ensure_ascii=False, default=str)
