"""Provider health gate: a plain company question on the balanced
configuration at its documented 75s ceiling, through the repository's own
client. Exit 0 when a packet comes back, 1 otherwise. Paid, about $0.10.
Usage: python probe_health.py"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

TREE = Path(os.environ["D10_TREE"]).resolve()
sys.path.insert(0, str(TREE / "src"))
load_dotenv(os.environ.get("D10_ENV_FILE") or TREE / ".env", override=False)

from argus.agent_runtime.research_grounded import _research_prompt  # noqa: E402
from argus.domain.research.config import retrieval_spec  # noqa: E402
from argus.domain.research.contracts import ResearchUnavailableError  # noqa: E402
from argus.domain.research.perplexity_agent import PerplexityAgentClient  # noqa: E402

prompt = _research_prompt(
    message="How has Netflix's revenue changed over the last year?",
    subjects=[{"symbol": "NFLX", "name": "Netflix", "asset_class": "equity"}],
    period="the last year",
    language="en",
    question_kind="company_lookup",
    publisher_sources_required=True,
)
spec = retrieval_spec("balanced", question_kind="company_lookup", language_tag="en").model_copy(
    update={"timeout_seconds": 75.0}
)
started = time.monotonic()
try:
    packet = PerplexityAgentClient(os.environ["PERPLEXITY_API_KEY"]).run_research(prompt, spec)
    print(f"healthy elapsed={time.monotonic() - started:.1f}s rows={len(packet.rows)} cost={packet.usage.cost_usd}")
    sys.exit(0)
except ResearchUnavailableError as exc:
    print(f"unhealthy reason={exc.reason} detail={exc.detail} elapsed={time.monotonic() - started:.1f}s")
    sys.exit(1)
