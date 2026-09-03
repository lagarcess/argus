# ruff: noqa: E402, I001 -- load the explicit eval environment before Argus imports
"""Issue #411 live interpreter acceptance with a recorded rail-dispatch seam.

Real model and asset-provider calls; downstream research execution is stubbed.
This proves interpretation and handoff, not research-answer quality or deployment.
The full measurement suite separately measures the shared schema's other routes.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv
import pytest

if os.getenv("ARGUS_EVAL_ENV_FILE"):
    load_dotenv(Path(os.environ["ARGUS_EVAL_ENV_FILE"]), override=False)

from argus.agent_runtime import research_answer
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.llm_interpreter import OpenRouterStructuredInterpreter
from argus.agent_runtime.stages.interpret import interpret_stage_async
from argus.agent_runtime.stages.interpret_types import StageResult
from argus.agent_runtime.state.models import RunState, UserState
from argus.llm.openrouter import (
    begin_openrouter_route_receipt_capture,
    end_openrouter_route_receipt_capture,
)
from tests.evals.measurement_eval_scorecard import build_scorecard_provenance


CASES = (
    ("build_es", "Buy and hold de meta", "es-419", "buy_and_hold"),
    ("build_en", "Buy and hold META", "en", "buy_and_hold"),
    (
        "dca",
        "Invest $100 in SPY every month from 2020 through 2024",
        "en",
        "dca_accumulation",
    ),
    ("compare", "Compare PLTR to LMT", "en", "research"),
    ("compare_period", "Compare PLTR to LMT over the last 3 years", "en", "research"),
    (
        "compare_es",
        "Compara el crecimiento de ingresos de NVDA y AMD en los últimos 5 años",
        "es-419",
        "research",
    ),
)


def test_research_routing_live(monkeypatch):
    if os.getenv("ARGUS_RUN_LIVE_RESEARCH_ROUTING_EVALS") != "1":
        pytest.skip("set ARGUS_RUN_LIVE_RESEARCH_ROUTING_EVALS=1 for paid acceptance")
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    provenance = build_scorecard_provenance(evaluation_mode="live")
    results = []

    async def run_case(case):
        case_id, message, language, expected = case
        interpreter = OpenRouterStructuredInterpreter(
            contract=build_default_capability_contract()
        )
        captured = {}

        class RecordingInterpreter:
            async def ainvoke(self, request):
                captured["interpretation"] = await interpreter.ainvoke(request)
                return captured["interpretation"]

        async def dispatch(query, **kwargs):
            captured["dispatched_query"] = query
            return StageResult(outcome="ready_to_respond")

        monkeypatch.setattr(research_answer, "_dispatch", dispatch)
        token = begin_openrouter_route_receipt_capture()
        try:
            result = await interpret_stage_async(
                state=RunState.new(
                    current_user_message=message, recent_thread_history=[]
                ),
                user=UserState(user_id="issue-411-eval", language_preference=language),
                latest_task_snapshot=None,
                structured_interpreter=RecordingInterpreter(),
            )
        finally:
            receipts = [r.as_dict() for r in end_openrouter_route_receipt_capture(token)]
        interpretation = captured.get("interpretation")
        query = interpretation.research_query if interpretation else None
        draft = interpretation.candidate_strategy_draft if interpretation else None
        failed = []
        if interpretation is None:
            failed.append("interpretation_missing")
        elif expected == "research":
            if query is None or query.question_kind != "cross_company":
                failed.append("primary_question_shape")
            if captured.get("dispatched_query") != query or query is None:
                failed.append("primary_question_handoff")
            if result.outcome != "ready_to_respond":
                failed.append("research_outcome")
        else:
            if draft.strategy_type != expected:
                failed.append("strategy_type")
            if captured.get("dispatched_query") is not None:
                failed.append("builder_sent_to_research")
            if query is not None and query.question_kind != "none":
                failed.append("builder_has_research_query")
            if expected == "dca_accumulation" and (
                draft.cadence != "monthly"
                or draft.extra_parameters.get("recurring_contribution") != 100
            ):
                failed.append("dca_contribution_or_cadence")
        if any(r.get("task") == "knowledge_route" for r in receipts):
            failed.append("secondary_classifier_called")
        return {
            "id": case_id,
            "expected": expected,
            "failed_checks": failed,
            "stage_outcome": result.outcome,
            "research_query": query.model_dump(mode="json") if query else None,
            "strategy_type": draft.strategy_type if draft else None,
            "route_receipts": receipts,
        }

    for case in CASES:
        results.append(asyncio.run(run_case(case)))
    output = Path("temp/issue-411-live-routing.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "evidence_kind": "live_interpreter_with_stubbed_research_dispatch",
                "provenance": provenance,
                "acceptance_source_sha256": hashlib.sha256(
                    Path(__file__).read_bytes()
                ).hexdigest(),
                "results": results,
            },
            indent=2,
        )
        + "\n"
    )
    assert not [r for r in results if r["failed_checks"]], f"routing failures: {output}"
