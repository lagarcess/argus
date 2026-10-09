"""Pair offline request bodies with committed receipts to prove the input bound.

Runs every Personal measurement case with no network: each OpenRouter post is
captured (its exact UTF-8 body, as httpx sends it) and then failed, so the case
moves on to its fallbacks. A case's first post of each schema and model does
not depend on any model reply, so it is the request the accepted measurement
sent, minus context a successful earlier read would have added; its bytes are
therefore at most the real request's. Each is paired with the accepted
measurement's first billed receipt of the same case, schema and model.

    python -m tests.evals.input_bound_proof docs/reports/evidence/live-eval-per-call-guard/input-bound-pairs.json
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ACCEPTED = Path(
    "docs/reports/evidence/current-reason-date-range/accepted-measurement/"
    "live-measurement.json"
)
OFFLINE_ENV = {
    "OPENROUTER_API_KEY": "offline",
    "ARGUS_RUN_LIVE_EVALS": "0",
    "ARGUS_ASSET_PROVIDER_MODE": "synthetic_unit_fixture",
    "ARGUS_MARKET_DATA_PROVIDER_MODE": "synthetic_unit_fixture",
    "ARGUS_STRUCTURED_MODEL": "x-ai/grok-4.3",
    "ARGUS_STRUCTURED_FALLBACK_MODEL": "anthropic/claude-haiku-4.5",
    "ARGUS_CHAT_MODEL": "deepseek/deepseek-v4-flash",
    "ARGUS_CHAT_FALLBACK_MODEL": "qwen/qwen3.5-9b",
    "ARGUS_CONTEXT_MODEL": "openai/gpt-oss-120b",
    "ARGUS_CONTEXT_FALLBACK_MODEL": "deepseek/deepseek-v4-flash",
    "ARGUS_RESEARCH_RAIL_ENABLED": "false",
}
_TITLE = re.compile(r'"title": ?"([A-Z][A-Za-z]+)"')


def _schema(payload: dict[str, Any]) -> str | None:
    named = ((payload.get("response_format") or {}).get("json_schema") or {}).get("name")
    if named:
        return str(named)
    # Anthropic posts carry the schema in their first system message; the
    # schema's own title is its last.
    messages = payload.get("messages") or []
    if not messages or messages[0].get("role") != "system":
        return None
    content = messages[0].get("content")
    text = (
        content
        if isinstance(content, str)
        else "".join(str(block.get("text") or "") for block in content or [])
    )
    titles = _TITLE.findall(text)
    return titles[-1] if titles else None


def capture_first_posts() -> dict[tuple[str, str | None, str], int]:
    os.environ.update(OFFLINE_ENV)
    import httpx

    from tests.evals.measurement_eval_harness import load_eval_cases, run_eval_case

    first: dict[tuple[str, str | None, str], int] = {}
    current = {"id": ""}

    def offline(self: Any, request: httpx.Request, **_: Any) -> httpx.Response:
        if request.url.host.endswith("openrouter.ai"):
            payload = json.loads(request.content)
            key = (current["id"], _schema(payload), str(payload.get("model")))
            first.setdefault(key, len(request.content))
        raise httpx.ConnectError("offline", request=request)

    async def offline_async(
        self: Any, request: httpx.Request, **_: Any
    ) -> httpx.Response:
        return offline(self, request)

    httpx.Client.send = offline  # type: ignore[method-assign]
    httpx.AsyncClient.send = offline_async  # type: ignore[method-assign]
    for case in load_eval_cases():
        current["id"] = case.id
        try:
            run_eval_case(case, run_prose_judge=False)
        except Exception:  # noqa: BLE001
            continue
    return first


def pair(first: dict[tuple[str, str | None, str], int]) -> list[dict[str, Any]]:
    accepted = json.loads(ACCEPTED.read_text(encoding="utf-8"))
    pairs = []
    for result in accepted["results"]:
        seen = set()
        for receipt in result.get("route_receipts") or []:
            tokens = (receipt.get("token_usage") or {}).get("prompt_tokens")
            key = (result["id"], receipt.get("schema_name"), receipt.get("model"))
            if receipt.get("outcome") == "skipped" or not tokens or key in seen:
                continue
            seen.add(key)
            if key in first:
                pairs.append(
                    {
                        "case": key[0],
                        "schema": key[1],
                        "model": key[2],
                        "body_bytes": first[key],
                        "billed_prompt_tokens": tokens,
                    }
                )
    return pairs


if __name__ == "__main__":
    rows = pair(capture_first_posts())
    Path(sys.argv[1]).write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    print(len(rows), min(r["body_bytes"] / r["billed_prompt_tokens"] for r in rows))
