"""Provider-free control over the unchanged what-next fixture and real renderer."""

import json
import os
from pathlib import Path
import socket
import sys
from unittest.mock import patch

repo = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(repo / "src"), str(repo)]
os.environ["ARGUS_RESEARCH_RAIL_ENABLED"] = "false"
os.environ["ARGUS_MARKET_DATA_PROVIDER_MODE"] = "synthetic_unit_fixture"
os.environ["ARGUS_ASSET_PROVIDER_MODE"] = "synthetic_unit_fixture"

from loguru import logger

logger.remove()
from argus.agent_runtime import result_followups
from argus.agent_runtime.next_experiments import next_experiments_sidecar
from argus.agent_runtime.stages import interpret_actions
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from tests.evals import measurement_eval_harness as harness

assert Path(result_followups.__file__).resolve().is_relative_to(repo)
assert Path(harness.__file__).resolve().is_relative_to(repo)
case = next(c for c in harness.load_eval_cases() if c.id == "asset_discovery_not_result_followup_issue_244")
response = StructuredInterpretation(
    intent="conversation_followup", task_relation="continue",
    requires_clarification=False, user_goal_summary=case.prompt,
    semantic_turn_act="result_followup", result_followup_focus="next_experiment",
    artifact_target="latest_result", confidence=.9,
)
observed = []


async def authored_provider(**kwargs):
    payload = json.loads(kwargs["messages"][1]["content"])
    observed.append({"focus": payload["focus"], "required_fact_ids": payload["required_fact_ids"]})
    return kwargs["schema_model"](
        relative_performance_claim="unknown",
        answer="Try a supported adjustment to the saved AAPL test.",
        fact_ids=payload["required_fact_ids"],
    )


async def actual_composer(**kwargs):
    return await result_followups.compose_result_followup_response(
        **kwargs, invoke_json_schema_func=authored_provider
    )


def no_network(*args, **kwargs):
    raise AssertionError("Network forbidden in read-only reconstruction")


with patch.object(socket.socket, "connect", no_network), patch.object(socket, "create_connection", no_network), patch.object(harness, "OpenRouterStructuredInterpreter", lambda **_: lambda request: response), patch.object(interpret_actions, "compose_result_followup_response", actual_composer):
    measured = harness.run_eval_case(case, run_prose_judge=False)
    metadata = dict(case.snapshot.latest_backtest_result_reference.metadata)
    sidecar = next_experiments_sidecar(metadata)
    print(json.dumps({
        "source_root": str(repo), "source_verified": True,
        "case_id": case.id,
        "controlled_interpretation": {"focus": response.result_followup_focus, "target": response.artifact_target},
        "authored_provider_reads": observed,
        "status": measured["status"], "failed_checks": measured["failed_checks"],
        "recovery": measured["typed_outcome"]["offered"]["recovery_code"],
        "actual_rows": measured["typed_outcome"]["offered"]["next_experiment_kinds"],
        "existing_row_owner_kinds": [r["kind"] for r in sidecar["rows"]],
    }, sort_keys=True))
