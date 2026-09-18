"""Replay, once, the request the step 8 merge (9ee081d1) built for the BTC
future-performance case (#599): the decision 10 scenario contract, where the
provider computes scenario values, on the balanced configuration with web
search and fetched pages and no finance tool. The code comes from a detached
checkout of that commit named by GM_BASE_TREE. Paid.
Usage: GM_TREE=<repo> GM_BASE_TREE=<checkout> [GM_ENV_FILE=<.env>] python record_btc_old_request.py <out.json>"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

TREE = Path(os.environ["GM_TREE"]).resolve()
BASE = Path(os.environ["GM_BASE_TREE"]).resolve()
sys.path.insert(0, str(BASE / "src"))
load_dotenv(os.environ.get("GM_ENV_FILE") or TREE / ".env", override=False)

import argus  # noqa: E402
from argus.agent_runtime.research_grounded import _research_prompt  # noqa: E402
from argus.domain.research.config import retrieval_spec  # noqa: E402
from argus.domain.research.contracts import ResearchUnavailableError  # noqa: E402
from argus.domain.research.perplexity_agent import PerplexityAgentClient  # noqa: E402

assert str(Path(argus.__file__).resolve()).startswith(str(BASE)), argus.__file__


class RecordingHTTPTransport(httpx.HTTPTransport):
    def __init__(self) -> None:
        super().__init__()
        self.exchanges: list[dict[str, Any]] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        started = time.monotonic()
        try:
            response = super().handle_request(request)
            response.read()
        except httpx.HTTPError as exc:
            self.exchanges.append({"url": str(request.url), "error": type(exc).__name__, "elapsed_s": round(time.monotonic() - started, 2)})
            raise
        try:
            document: Any = json.loads(response.content.decode())
        except ValueError:
            document = response.content.decode(errors="replace")[:2000]
        self.exchanges.append({"url": str(request.url), "request": json.loads(request.content.decode()) if request.content else None, "http_status": response.status_code, "elapsed_s": round(time.monotonic() - started, 2), "response": document})
        return response


question = "If I invest $10,000 in Bitcoin and just hold it, what will it be worth in ten years?"
prompt = _research_prompt(
    message=question,
    subjects=[{"symbol": "BTC-USD", "name": "Bitcoin", "asset_class": "crypto"}],
    period="ten years",
    language="en",
    question_kind=None,
    publisher_sources_required=True,
    scenario=True,
)
spec = retrieval_spec("balanced", question_kind="company_lookup", language_tag="en", country=None, scenario=True)
spec = spec.model_copy(update={"tools": tuple(tool for tool in spec.tools if tool != "finance_search")})
transport = RecordingHTTPTransport()
client = PerplexityAgentClient(os.environ["PERPLEXITY_API_KEY"], transport=transport)
started = time.monotonic()
record: dict[str, Any] = {
    "probe": "btc_future_performance_old_request",
    "issue": 599,
    "base_sha": subprocess.check_output(["git", "-C", str(BASE), "rev-parse", "HEAD"], text=True).strip(),
    "captured_at": datetime.now(timezone.utc).isoformat(),
    "question": question,
    "tools": list(spec.tools),
    "timeout_seconds": spec.timeout_seconds,
}
try:
    packet = client.run_research(prompt, spec)
    record["packet"] = packet.model_dump(mode="json")
    record["error"] = None
except ResearchUnavailableError as exc:
    record["packet"] = None
    record["error"] = {"reason": exc.reason, "detail": exc.detail}
record["elapsed_s"] = round(time.monotonic() - started, 2)
record["exchanges"] = transport.exchanges
Path(sys.argv[1]).write_text(json.dumps(record, indent=2, ensure_ascii=False, default=str) + "\n")
packet = record.get("packet") or {}
print(json.dumps({"base_sha": record["base_sha"], "elapsed_s": record["elapsed_s"], "error": record["error"], "statuses": [e.get("http_status") or e.get("error") for e in transport.exchanges], "rows": len(packet.get("rows") or []), "cost_usd": (packet.get("usage") or {}).get("cost_usd")}, indent=1, default=str))
