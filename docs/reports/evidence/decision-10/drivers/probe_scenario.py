"""How long a scenario answer takes on the balanced configuration when the
client ceiling is lifted: the exact prompt and spec Argus builds for a
forward-looking question, through the repository's own client, with
timeout_seconds raised. Paid. Usage: python probe_scenario.py <out.json>"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

TREE = Path(os.environ["D10_TREE"]).resolve()
sys.path.insert(0, str(TREE / "src"))
load_dotenv(os.environ.get("D10_ENV_FILE") or TREE / ".env", override=False)

from argus.agent_runtime.research_grounded import _research_prompt  # noqa: E402
from argus.domain.research.config import retrieval_spec  # noqa: E402
from argus.domain.research.contracts import ResearchUnavailableError  # noqa: E402
from argus.domain.research.perplexity_agent import PerplexityAgentClient  # noqa: E402

question = os.environ.get("D10_QUESTION", "what will $10,000 in NVDA be worth in ten years?")
ceiling = float(os.environ.get("D10_TIMEOUT", "180"))
prompt = _research_prompt(
    message=question,
    subjects=[{"symbol": "NVDA", "name": "NVIDIA", "asset_class": "equity"}],
    period="in ten years",
    language="en",
    question_kind="company_lookup",
    publisher_sources_required=True,
)
spec = retrieval_spec("balanced", question_kind="company_lookup", language_tag="en").model_copy(
    update={"timeout_seconds": ceiling}
)
client = PerplexityAgentClient(os.environ["PERPLEXITY_API_KEY"])
started = time.monotonic()
record = {"question": question, "asked_at": datetime.now(timezone.utc).isoformat(), "ceiling_seconds": ceiling, "spec": spec.model_dump(mode="json")}
try:
    packet = client.run_research(prompt, spec)
    record.update(
        {
            "outcome": "packet",
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "answer_markdown": packet.answer_markdown,
            "rows": [row.model_dump(mode="json") for row in packet.rows],
            "sources": [str(s.get("url") if isinstance(s, dict) else s) for s in (packet.sources or [])][:12],
            "usage": packet.usage.model_dump(mode="json"),
        }
    )
except ResearchUnavailableError as exc:
    record.update({"outcome": f"unavailable:{exc.reason}", "detail": exc.detail, "elapsed_seconds": round(time.monotonic() - started, 2)})
Path(sys.argv[1]).write_text(json.dumps(record, indent=2, ensure_ascii=False, default=str) + "\n")
print(json.dumps({k: record.get(k) for k in ("outcome", "elapsed_seconds", "usage")}, indent=1, default=str))
print((record.get("answer_markdown") or record.get("detail") or "")[:1500])
