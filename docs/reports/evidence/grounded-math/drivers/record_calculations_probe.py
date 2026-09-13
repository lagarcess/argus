"""Record one real typed research answer under the calculations schema through
the repository's own client, so the schema that carries one calculation per
option the reader weighs is frozen by a recording the way the other retrieval
texts are (tests/research/test_retrieval_contract_probe.py). The request is byte
for byte what production sends for a concept question on the balanced
configuration. Paid.
Usage: GM_TREE=<repo> [GM_ENV_FILE=<.env>] python record_calculations_probe.py <out.json>"""
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


question = os.environ.get(
    "GM_QUESTION",
    "Is 20,000 dollars better kept for a year in a 12-month CD at 4.1% or in a savings account at 3.8%?",
)
prompt = _research_prompt(
    message=question, subjects=[], period=None, language="en", question_kind="concept"
)
spec = retrieval_spec("balanced", question_kind="concept", language_tag="en", country=None)
transport = RecordingHTTPTransport()
client = PerplexityAgentClient(os.environ["PERPLEXITY_API_KEY"], transport=transport)
started = time.monotonic()
record: dict[str, Any] = {
    "probe": "typed_answer_calculations_options",
    "purpose": "any grounded math: one calculation per option under the calculations schema, balanced configuration",
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
print(json.dumps({"elapsed_s": record["elapsed_s"], "error": record["error"], "calculations": packet.get("calculations"), "source_urls": packet.get("source_urls"), "usage": packet.get("usage")}, indent=1, default=str))
print((packet.get("answer_markdown") or "")[:1500])
