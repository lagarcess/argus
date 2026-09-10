"""Current real retrieval dispatch, with its retained provider facts replayed locally."""

import json
import os
from pathlib import Path
import socket
import sys
from unittest.mock import patch

repo = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(repo / "src"), str(repo)]
os.environ["ARGUS_RESEARCH_RAIL_ENABLED"] = "true"
os.environ["ARGUS_MARKET_DATA_PROVIDER_MODE"] = "synthetic_unit_fixture"
os.environ["ARGUS_ASSET_PROVIDER_MODE"] = "synthetic_unit_fixture"
from loguru import logger

logger.remove()
from argus.agent_runtime import research_grounded
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.domain.research.cache import cache_clear
from argus.domain.research.contracts import ResearchPacket, ResearchUsage
from argus.domain.tool_contracts import ToolCall
from tests.evals import measurement_eval_harness as harness

case_id = "ordinary_conversation_macro_curiosity_en"
case = next(c for c in harness.load_eval_cases() if c.id == case_id)
recorded = json.loads((repo / "docs/reports/evidence/registry/verification/262d670f/interleaved/27-candidate-r2.json").read_text())["results"][0]
raw = recorded["typed_outcome"]["tool_result_cards"][0]["outcome"]["result"]
packet = ResearchPacket(
    answer_markdown=raw["answer"], rows=raw["rows"], sources=raw["sources"],
    typed_answer=True, usage=ResearchUsage(invocations=1, finance_search_invocations=1),
    retrieved_at=raw["retrieved_at"],
)
calls = [ToolCall.model_validate(c) for c in recorded["typed_outcome"]["tool_calls"]]
response = StructuredInterpretation(
    uses_tool_catalog=True, intent="explain", task_relation="new_task",
    user_goal_summary=case.prompt, semantic_turn_act="educational_question", tool_calls=calls,
)
observed = []


class RetainedProvider:
    def run_research(self, prompt, spec):
        observed.append({"shape": spec.shape})
        return packet


def no_network(*args, **kwargs):
    raise AssertionError("Network forbidden in read-only reconstruction")


cache_clear()
with patch.object(socket.socket, "connect", no_network), patch.object(socket, "create_connection", no_network), patch.object(harness, "OpenRouterStructuredInterpreter", lambda **_: lambda request: response), patch.object(research_grounded, "_client", lambda: RetainedProvider()):
    measured = harness.run_eval_case(case, run_prose_judge=False)
    outcome = measured["typed_outcome"]
    print(json.dumps({
        "source_root": str(repo), "case_id": case_id,
        "probe_scope": "dispatch and effective intent; prose judge deliberately not run",
        "unchanged_fixture_allowed_intents": case.expected.intent,
        "primary_intent": outcome["primary_intent"], "effective_intent": outcome["intent"],
        "status": measured["status"], "failed_checks": measured["failed_checks"],
        "execution_trace": outcome["execution_trace"],
        "record_outcomes": [r["outcome"] for r in outcome["tool_call_records"]],
        "card_outcomes": [c["outcome"]["status"] for c in outcome["tool_result_cards"]],
        "retained_provider_reads": observed,
    }, sort_keys=True))
cache_clear()
