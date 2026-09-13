"""Record one real scenario answer through the repository's own client, so
the scenario retrieval contract is frozen the way the other retrieval
recordings are (tests/research/test_retrieval_contract_probe.py). The request
is byte for byte what production sends for a scenario question on the
balanced configuration. Paid. Usage: python record_scenario_probe.py <out.json>"""
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

TREE = Path(os.environ["D10_TREE"]).resolve()
sys.path.insert(0, str(TREE / "src"))
load_dotenv(os.environ.get("D10_ENV_FILE") or TREE / ".env", override=False)

from argus.agent_runtime.research_grounded import _research_prompt  # noqa: E402
from argus.domain.research.config import retrieval_spec  # noqa: E402
from argus.domain.research.contracts import ResearchUnavailableError  # noqa: E402
from argus.domain.research.perplexity_agent import PerplexityAgentClient  # noqa: E402


class RecordingHTTPTransport(httpx.HTTPTransport):
    """The real transport, with every exchange kept for the record."""

    def __init__(self) -> None:
        super().__init__()
        self.exchanges: list[dict[str, Any]] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = super().handle_request(request)
        response.read()
        body: Any = json.loads(request.content.decode()) if request.content else None
        try:
            document: Any = json.loads(response.content.decode())
        except ValueError:
            document = response.content.decode(errors="replace")[:2000]
        self.exchanges.append(
            {
                "method": request.method,
                "url": str(request.url),
                "request": body,
                "http_status": response.status_code,
                "response": document,
            }
        )
        return response


question = os.environ.get("D10_QUESTION", "what will $10,000 in NVDA be worth in ten years?")
prompt = _research_prompt(
    message=question,
    subjects=[{"symbol": "NVDA", "name": "NVIDIA", "asset_class": "equity"}],
    period="ten years",
    language="en",
    question_kind="company_lookup",
    publisher_sources_required=True,
    scenario=True,
)
spec = retrieval_spec("balanced", question_kind="company_lookup", language_tag="en", country=None, scenario=True)
transport = RecordingHTTPTransport()
client = PerplexityAgentClient(os.environ["PERPLEXITY_API_KEY"], transport=transport)
started = time.monotonic()
record: dict[str, Any] = {
    "probe": "scenario_typed_balanced",
    "purpose": "decision 10: the scenario retrieval contract on the balanced configuration",
    "candidate_sha": subprocess.check_output(["git", "-C", str(TREE), "rev-parse", "HEAD"], text=True).strip(),
    "captured_at": datetime.now(timezone.utc).isoformat(),
    "question": question,
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
print(json.dumps({"elapsed_s": record["elapsed_s"], "error": record["error"], "rows": len(packet.get("rows") or []), "usage": packet.get("usage")}, indent=1, default=str))
print((packet.get("answer_markdown") or "")[:1800])
