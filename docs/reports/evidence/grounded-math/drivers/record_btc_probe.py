"""Capture the request production builds for the BTC future-performance case
(#599) and every provider response status, through the repository's own
client: web search and fetched pages without the finance tool, on the
balanced configuration under the input retrieval contract. The calculation
read is given on the command line, so the capture replays the read the model
actually made. Paid.
Usage: GM_TREE=<repo> [GM_ENV_FILE=<.env>] python record_btc_probe.py <out.json> <kind> '<inputs json>' '<retrieve json>'"""
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
sys.path.insert(0, str(TREE / "src"))
load_dotenv(os.environ.get("GM_ENV_FILE") or TREE / ".env", override=False)

from argus.agent_runtime.research_grounded import _research_prompt  # noqa: E402
from argus.domain.research.config import retrieval_spec  # noqa: E402
from argus.domain.research.contracts import ResearchUnavailableError  # noqa: E402
from argus.domain.research.perplexity_agent import PerplexityAgentClient  # noqa: E402


class RecordingHTTPTransport(httpx.HTTPTransport):
    """The real transport, with every exchange's status and timing kept."""

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
        self.exchanges.append(
            {
                "url": str(request.url),
                "request": json.loads(request.content.decode()) if request.content else None,
                "http_status": response.status_code,
                "elapsed_s": round(time.monotonic() - started, 2),
                "response": document,
            }
        )
        return response


out = sys.argv[1]
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
    "probe": "btc_future_performance_inputs",
    "issue": 599,
    "candidate_sha": subprocess.check_output(["git", "-C", str(TREE), "rev-parse", "HEAD"], text=True).strip(),
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
Path(out).write_text(json.dumps(record, indent=2, ensure_ascii=False, default=str) + "\n")
packet = record.get("packet") or {}
print(json.dumps({"elapsed_s": record["elapsed_s"], "error": record["error"], "statuses": [exchange.get("http_status") or exchange.get("error") for exchange in transport.exchanges], "calculation": packet.get("calculation"), "cost_usd": (packet.get("usage") or {}).get("cost_usd")}, indent=1, default=str))
