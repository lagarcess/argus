"""Issue #541 reproduction: a finance-only market survey whose provider
response carries a finance_results item but no usage block.

Runs the real research answer stage against a recording transport that can
serve the same document twice, then prints how many paid requests were made,
whether the answer was delivered or replaced, and what the sidecar reports.
"""

from __future__ import annotations

import asyncio
import json
import sys
from copy import deepcopy

import pytest
from argus.agent_runtime import research_answer as ra
from argus.agent_runtime import research_grounded as grounded
from argus.domain.research.cache import cache_clear
from argus.domain.research.perplexity_agent import PerplexityAgentClient

from tests.research import test_research_shapes as shapes
from tests.research.conftest import RecordingTransport, agent_response, set_research_query


def survey_without_invoice() -> dict:
    document = agent_response(
        text="NVDA +2.3%, TSLA -1.1% as of 3:15pm ET.",
        tickers=["NVDA"],
        lookup_rows=[("NVIDIA", "NVDA", "NVIDIA Corporation")],
        invocations=1,
    )
    del document["usage"]
    return document


def main() -> int:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
    cache_clear()
    set_research_query(
        monkeypatch, vars(shapes), question_kind="market_pulse", symbols=[]
    )
    document = survey_without_invoice()
    transport = RecordingTransport([deepcopy(document), deepcopy(document)])
    monkeypatch.setattr(
        grounded, "_client", lambda: PerplexityAgentClient("k", transport=transport)
    )
    result = asyncio.run(
        ra.research_answer_stage_result(
            interpretation=shapes._interpretation(),
            state=shapes._state("What's moving in the market?"),
            user=shapes.USER,
        )
    )
    monkeypatch.undo()
    assert result is not None
    sidecar = result.stage_patch["research"]
    report = {
        "provider_output_types": [item["type"] for item in document["output"]],
        "usage_block_present": "usage" in document,
        "paid_requests": len(transport.requests),
        "degraded": sidecar.get("degraded"),
        "sidecar_usage": sidecar["usage"],
        "answer": result.stage_patch["assistant_response"],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
