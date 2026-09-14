"""Drive the live route check: a card, an input change, a run, a result question.

Talks to the route check server over HTTP. Before every step it compares the
billed spend so far (each unpriced call counted at a conservative flat amount)
plus that step's reserve against the cap, and stops before crossing it.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

API = os.environ.get("ROUTE_CHECK_API", "http://127.0.0.1:8618/api/v1")
OUT = Path(os.environ["ROUTE_CHECK_OUT"]).resolve()
CAP_USD = float(os.environ.get("ROUTE_CHECK_CAP_USD", "0.50"))
SPENT_BEFORE_USD = float(os.environ.get("ROUTE_CHECK_SPENT_BEFORE_USD", "0"))
LANGUAGES = [code for code in os.environ.get("ROUTE_CHECK_LANGUAGES", "en,es-419").split(",") if code]
UNPRICED_CALL_USD = 0.02
RESERVE_USD = {"card": 0.06, "change": 0.06, "run": 0.06, "result_question": 0.10}

SCRIPTS = {
    "en": {
        "card": "Backtest buying and holding Apple from January 2023 through December 2024 with $10000.",
        "change": "Actually, make it $5000 instead.",
        "result_question": "How did that do compared to SPY?",
    },
    "es-419": {
        "card": "Haz un backtest de comprar y mantener Apple desde enero de 2023 hasta diciembre de 2024 con 10000 dólares.",
        "change": "Mejor que sean 5000 dólares.",
        "result_question": "¿Cómo le fue frente a SPY?",
    },
}


def _jsonl(name: str) -> list[dict[str, Any]]:
    path = OUT / f"{name}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def spend() -> dict[str, Any]:
    receipts = [row["receipt"] for row in _jsonl("receipts")]
    research = _jsonl("research_costs")
    requests = _jsonl("model_requests")
    priced = [r["usage_cost_usd"] for r in receipts if r.get("usage_cost_usd") is not None]
    unpriced_receipts = sum(1 for r in receipts if r.get("usage_cost_usd") is None)
    research_priced = [r["cost_usd"] for r in research if r.get("cost_usd") is not None]
    research_requests = sum(1 for r in requests if str(r.get("host", "")).endswith("perplexity.ai"))
    unpriced_research = max(0, research_requests - len(research_priced))
    billed = sum(priced) + sum(research_priced)
    ceiling = SPENT_BEFORE_USD + billed + (unpriced_receipts + unpriced_research) * UNPRICED_CALL_USD
    return {
        "billed_usd": round(billed, 6),
        "unpriced_receipts": unpriced_receipts,
        "unpriced_research_calls": unpriced_research,
        "ceiling_usd": round(ceiling, 6),
        "spent_before_usd": SPENT_BEFORE_USD,
    }


def record(entry: dict[str, Any]) -> None:
    with (OUT / "driver.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def stream_turn(
    client: httpx.Client,
    conversation_id: str,
    language: str,
    *,
    message: str | None = None,
    action: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"conversation_id": conversation_id, "language": language}
    if message is not None:
        body["message"] = message
    if action is not None:
        body["action"] = action
    started = time.time()
    final = None
    stages: list[dict[str, Any]] = []
    with client.stream("POST", f"{API}/chat/stream", json=body, headers=headers or {}, timeout=300) as response:
        if response.status_code != 200:
            return {"status": response.status_code, "error": response.read().decode("utf-8"), "started": started, "finished": time.time()}
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            raw = line[len("data: "):].strip()
            if raw == "[DONE]":
                break
            event = json.loads(raw)
            if event.get("type") == "final":
                final = event.get("payload")
            elif event.get("type") != "token":
                stages.append({key: event.get(key) for key in ("type", "stage", "outcome") if event.get(key)})
    return {"status": 200, "started": started, "finished": time.time(), "final": final, "stages": stages}


def messages(client: httpx.Client, conversation_id: str) -> list[dict[str, Any]]:
    return client.get(f"{API}/conversations/{conversation_id}/messages").json()["items"]


def title(client: httpx.Client, conversation_id: str, wait_seconds: float = 0) -> dict[str, Any]:
    deadline = time.time() + wait_seconds
    while True:
        items = client.get(f"{API}/conversations", params={"limit": 50}).json()["items"]
        item = next((row for row in items if row["id"] == conversation_id), {})
        if item.get("title_source") != "system_default" or time.time() >= deadline:
            return {"title": item.get("title"), "title_source": item.get("title_source")}
        time.sleep(3)


def latest_card(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    cards = [row for row in items if row["role"] == "assistant" and (row.get("metadata") or {}).get("confirmation_card")]
    return cards[-1] if cards else None


def card_facts(card_message: dict[str, Any] | None) -> dict[str, Any] | None:
    if card_message is None:
        return None
    metadata = card_message["metadata"]
    card = metadata["confirmation_card"]
    strategy = (metadata.get("confirmation_payload") or {}).get("strategy") or {}
    launch = (metadata.get("confirmation_payload") or {}).get("launch_payload") or {}
    return {
        "message_id": card_message["id"],
        "confirmation_id": card.get("confirmation_id"),
        "strategy_type": card.get("strategy_type"),
        "symbols": strategy.get("asset_universe"),
        "date_range": {key: (card.get("date_range") or {}).get(key) for key in ("start", "end")},
        "capital": launch.get("capital_amount", strategy.get("capital_amount")),
        "status": card.get("status"),
    }


def reply_text(final: dict[str, Any] | None, items: list[dict[str, Any]]) -> str:
    text = (final or {}).get("assistant_response") or (final or {}).get("assistant_prompt") or ""
    if text:
        return text
    assistant = [row for row in items if row["role"] == "assistant"]
    return assistant[-1]["content"] if assistant else ""


def within_cap(step: str) -> tuple[bool, dict[str, Any]]:
    current = spend()
    return current["ceiling_usd"] + RESERVE_USD[step] <= CAP_USD, current


def run_language(client: httpx.Client, language: str) -> dict[str, Any]:
    script = SCRIPTS[language]
    patched = client.patch(f"{API}/me", json={"language": language})
    patched.raise_for_status()
    conversation_id = client.post(f"{API}/conversations", json={"language": language}).json()["conversation"]["id"]
    summary: dict[str, Any] = {"language": language, "conversation_id": conversation_id, "steps": {}}

    def step(name: str, **turn: Any) -> dict[str, Any] | None:
        allowed, before = within_cap(name)
        if not allowed:
            summary["stopped_for_cap"] = {"step": name, "spend": before}
            record({"language": language, "step": name, "stopped_for_cap": True, "spend": before})
            return None
        result = stream_turn(client, conversation_id, language, **turn)
        items = messages(client, conversation_id)
        entry = {
            "language": language,
            "step": name,
            "request": {key: value for key, value in turn.items() if key != "headers"},
            **result,
            "reply": reply_text(result.get("final"), items),
            "latest_card": card_facts(latest_card(items)),
            "title": title(client, conversation_id, wait_seconds=60 if name == "card" else 8),
            "messages": items,
            "spend_after": spend(),
        }
        record(entry)
        summary["steps"][name] = {key: entry[key] for key in ("status", "reply", "latest_card", "title", "spend_after")}
        return entry

    first = step("card", message=script["card"])
    if first is None or first.get("latest_card") is None:
        return summary
    changed = step("change", message=script["change"])
    if changed is None or changed.get("latest_card") is None:
        return summary
    run_card = latest_card(changed["messages"])
    run_action = next(
        action for action in run_card["metadata"]["confirmation_card"]["actions"] if action["type"] == "run_backtest"
    )
    ran = step(
        "run",
        action={
            "type": "run_backtest",
            "label": run_action.get("label", "Run backtest"),
            "labelKey": run_action.get("labelKey"),
            "presentation": "confirmation",
            "payload": run_action["payload"],
        },
        headers={"Idempotency-Key": run_action["payload"]["confirmation_id"]},
    )
    if ran is None:
        return summary
    step("result_question", message=script["result_question"])
    return summary


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    with httpx.Client(timeout=60) as client:
        for language in LANGUAGES:
            results.append(run_language(client, language))
    (OUT / "summary.json").write_text(
        json.dumps({"cap_usd": CAP_USD, "spend": spend(), "conversations": results}, ensure_ascii=False, indent=2, default=str)
    )
    print(json.dumps({"spend": spend(), "conversations": [{"language": r["language"], "steps": list(r["steps"]), "stopped": r.get("stopped_for_cap")} for r in results]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
