"""Chat turns through the local Argus API, one conversation, recording what
each turn stored (the card, its marker, the clarification, the research
sidecar, the next steps) and how long the reader waited: seconds to the first
answer text on the stream, and to the final answer, which for a background
research job is the message the job posts later. Each record's full answers are
also written as markdown beside it (turns/ becomes answers/) for side-by-side
reading.
Usage: python ask.py <label> <language> <country> <out.json> <message> [<reply> ...]
A reply written @action:<type>:<label> is sent as that typed chat action with its label, the way a tapped row sends it.
Set GM_CONVERSATION_ID to continue an existing conversation; its turns append to <out.json>. Paid."""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

label, language, country, out, *messages = sys.argv[1:]
API = f"http://127.0.0.1:{os.getenv('GM_API_PORT', '8620')}/api/v1"
JOB_TIMEOUT_SECONDS = 600
TERMINAL_JOB_STATUSES = {"failed", "canceled", "expired"}


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


def answer_markdown(record: dict) -> str:
    lines = [f"# {record['label']} ({record['language']})", ""]
    for turn in record["turns"]:
        metadata = turn.get("metadata") or {}
        lines += [
            f"**Asked:** {turn['message']}",
            "",
            f"**Seconds to first answer:** {turn.get('first_answer_seconds')}. "
            f"**Seconds to final answer:** {turn.get('final_answer_seconds')}.",
            "",
            turn["summary"]["content"] or "(no answer text)",
            "",
        ]
        sources = (metadata.get("research") or {}).get("sources") or []
        if sources:
            lines += ["## Sources", ""]
            for source in sources:
                host = urlparse(source.get("url") or "").hostname or ""
                dated = source.get("date") or source.get("source_date") or source.get("published_at")
                lines.append(f"- {source.get('title') or host} ({host}{', ' + str(dated) if dated else ''}): {source.get('url')}")
            lines.append("")
        rows = {row.get("kind"): row for row in ((metadata.get("next_experiments") or {}).get("rows") or [])}
        items = ((metadata.get("next_steps") or {}).get("items")) or [{"type": "test", "kind": kind} for kind in rows]
        if items:
            lines += ["## Next steps", ""]
            for item in items:
                if item.get("type") == "question":
                    lines.append(f"- Question: {item.get('text')}")
                else:
                    lines.append(f"- {item.get('kind')}: {(rows.get(item.get('kind')) or {}).get('label') or ''}")
            lines.append("")
        cards = metadata.get("tool_result_cards") or []
        if cards:
            card = cards[0]
            presentation = card.get("presentation") or {}
            answer = presentation.get("answer") or {}
            lines += ["## Calculation", "", f"- {card.get('tool_name')}: {(card.get('outcome') or {}).get('status')}"]
            if answer:
                lines.append(f"- Result {answer.get('name')}: {answer.get('value')}")
            for fact in presentation.get("inputs") or []:
                lines.append(f"- Input {fact.get('name')}: {fact.get('value')} ({(fact.get('source') or {}).get('kind')})")
            lines.append("")
    return "\n".join(lines)


def research_job_id(tool_jobs: list) -> str | None:
    for entry in tool_jobs:
        job = entry.get("job") if isinstance(entry, dict) else None
        if isinstance(job, dict) and (job.get("id") or job.get("job_id")):
            return str(job.get("id") or job.get("job_id"))
    return None


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
        action = None
        if message.startswith("@action:"):
            _, action_type, message = message.split(":", 2)
            action = {"type": action_type, "label": message}
        body = {"conversation_id": conversation_id, "message": message, "language": language, "memory_opt_out": True}
        if action is not None:
            body["action"] = action
        started = time.monotonic()
        timeline: list[dict] = []
        first_answer = final_at = None
        tool_jobs: list = []
        with client.stream("POST", "/chat/stream", json=body) as stream:
            stream.raise_for_status()
            for line in stream.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                event = json.loads(data)
                at = round(time.monotonic() - started, 2)
                kind = event.get("type")
                timeline.append({"at": at, "type": kind, **{key: event[key] for key in ("stage", "detail", "outcome") if isinstance(event.get(key), str)}})
                if kind == "token" and first_answer is None and str(event.get("content") or "").strip():
                    first_answer = at
                if kind == "final":
                    final_at = at
                    tool_jobs = (event.get("payload") or {}).get("tool_jobs") or []
        items = client.get(f"/conversations/{conversation_id}/messages", params={"limit": 50}).json()["items"]
        final = [item for item in items if item.get("role") == "assistant"][-1]
        answered_at = final_at
        job_id = research_job_id(tool_jobs)
        if job_id:
            deadline = time.monotonic() + JOB_TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                status = client.get(f"/backtest-jobs/{job_id}")
                if status.status_code >= 400:
                    break
                body = status.json()
                if body.get("result_message"):
                    final = body["result_message"]
                    answered_at = round(time.monotonic() - started, 2)
                    break
                if (body.get("job") or {}).get("status") in TERMINAL_JOB_STATUSES:
                    break
                time.sleep(3)
        turn = {
            "message": message,
            "action": action,
            "message_id": final["id"],
            "first_answer_seconds": first_answer,
            "final_answer_seconds": answered_at,
            "research_job_id": job_id,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "timeline": timeline,
            "summary": summarize(final.get("metadata") or {}, final.get("content") or ""),
            "metadata": final.get("metadata"),
        }
        record["turns"].append(turn)
        print(json.dumps({"label": label, "message": message, "first_answer_seconds": first_answer, "final_answer_seconds": answered_at, **turn["summary"]}, ensure_ascii=False, indent=1))
with open(out, "w") as handle:
    json.dump(record, handle, indent=2, ensure_ascii=False, default=str)
answers = out.replace("/turns/", "/answers/")
answers = (answers[: -len(".json")] if answers.endswith(".json") else answers) + ".md"
os.makedirs(os.path.dirname(answers) or ".", exist_ok=True)
with open(answers, "w") as handle:
    handle.write(answer_markdown(record))
