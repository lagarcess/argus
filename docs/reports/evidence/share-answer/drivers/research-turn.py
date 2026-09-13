"""One paid research turn, without retries, against the isolated local API.

Usage: poetry run python <this file> en|es-419|en-focused
Only the closed preview payload and a small provenance summary are publishable.
Raw stream/session/source identities are retained in ignored temp/ for QA reuse.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[5]
PRIVATE = ROOT / "temp/share-answer-qa"
case = sys.argv[1]
questions = {
    "en": "What did Apple say in its most recent quarterly earnings report, and how did AAPL react this week?",
    "es-419": "Resume el informe de resultados trimestrales más reciente de Apple: ingresos, crecimiento interanual y lo que dijo la empresa sobre el iPhone.",
    "en-focused": "Summarize Apple's latest quarterly earnings report: revenue, year-over-year growth, and what the company said about iPhone.",
}
assert case in questions
language = "es-419" if case == "es-419" else "en"
output = PRIVATE / f"research-{case}.json"
assert not output.exists(), "Do not repeat a paid turn; inspect the saved evidence."
owner = json.loads((PRIVATE / "owner.json").read_text())
headers = {"Authorization": f"Bearer {owner['session']['access_token']}"}
record = {
    "candidate_sha": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip(),
    "started_at": datetime.now(timezone.utc).isoformat(),
    "language": language,
    "question": questions[case],
    "source": "real local Argus API, real configured research provider",
    "events": [],
}
started = time.monotonic()
try:
    with httpx.Client(
        base_url="http://127.0.0.1:8319/api/v1", headers=headers, timeout=240
    ) as client:
        response = client.get("/me")
        response.raise_for_status()
        me = response.json()
        assert me["account_kind"] == "registered"
        assert me["capabilities"]["can_save_decision"] is True
        record["me"] = me
        response = client.post(
            "/conversations",
            json={
                "title": "Apple research"
                if language == "en"
                else "Investigación de Apple",
                "language": language,
            },
        )
        response.raise_for_status()
        conversation_id = response.json()["conversation"]["id"]
        record["conversation_id"] = conversation_id
        with client.stream(
            "POST",
            "/chat/stream",
            json={
                "conversation_id": conversation_id,
                "message": questions[case],
                "language": language,
                "memory_opt_out": True,
            },
        ) as stream:
            stream.raise_for_status()
            for line in stream.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    record["done"] = True
                    break
                record["events"].append(json.loads(data))
        response = client.get(
            f"/conversations/{conversation_id}/messages", params={"limit": 100}
        )
        response.raise_for_status()
        record["messages"] = response.json()
        response = client.get(
            f"/conversations/{conversation_id}/public-excerpt-candidates"
        )
        response.raise_for_status()
        record["candidates"] = response.json()
        eligible = [item for item in record["candidates"]["items"] if item["eligible"]]
        if eligible:
            record["message_id"] = eligible[-1]["message_id"]
            response = client.post(
                f"/conversations/{conversation_id}/public-excerpt-preview",
                json={
                    "message_ids": [record["message_id"]],
                },
            )
            record["preview_status"] = response.status_code
            record["preview"] = response.json()
        else:
            record["preview_status"] = None
finally:
    record["elapsed_seconds"] = round(time.monotonic() - started, 2)
    output.write_text(json.dumps(record, indent=2, ensure_ascii=False))
    output.chmod(0o600)

print(
    json.dumps(
        {
            "language": language,
            "done": record.get("done", False),
            "elapsed_seconds": record["elapsed_seconds"],
            "candidate_results": [
                {key: item.get(key) for key in ("kind", "eligible", "reason", "field")}
                for item in record.get("candidates", {}).get("items", [])
            ],
            "preview_status": record.get("preview_status"),
        },
        ensure_ascii=False,
    )
)
