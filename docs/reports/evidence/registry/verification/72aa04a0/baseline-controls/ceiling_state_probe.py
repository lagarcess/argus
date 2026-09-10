"""Reconstruct the retained canonical money state, not an unretained model reply."""

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
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import StrategySummary
from tests.evals import measurement_eval_harness as harness

assert Path(harness.__file__).resolve().is_relative_to(repo)
case_id = "dca_capital_semantics_only_have_amount_is_ceiling_issue_455"
recorded = next(r for r in json.loads(Path(sys.argv[2]).read_text())["results"] if r["id"] == case_id)
case = next(c for c in harness.load_eval_cases() if c.id == case_id)
raw = recorded["typed_outcome"]["clarification"]["payload"]["strategy"]
strategy = StrategySummary.model_validate(raw)
response = StructuredInterpretation(
    intent="strategy_drafting", task_relation="new_task", requires_clarification=True,
    user_goal_summary=case.prompt, candidate_strategy_draft=strategy,
    semantic_turn_act="new_idea", missing_required_fields=[], confidence=.9,
)


def no_network(*args, **kwargs):
    raise AssertionError("Network forbidden in read-only reconstruction")


with patch.object(socket.socket, "connect", no_network), patch.object(socket, "create_connection", no_network), patch.object(harness, "OpenRouterStructuredInterpreter", lambda **_: lambda request: response), patch.object(harness, "OpenRouterClarificationGenerator", lambda: lambda request: "Choose how to continue the monthly plan."):
    measured = harness.run_eval_case(case, run_prose_judge=False)
    outcome = measured["typed_outcome"]
    print(json.dumps({
        "source_root": str(repo), "source_verified": True, "case_id": case_id,
        "reconstruction_boundary": "retained canonical strategy after model/focused extraction",
        "unretained_primary_reply_reconstructed": False,
        "input_capital_amount": strategy.capital_amount,
        "input_extra_parameters": {k: strategy.extra_parameters.get(k) for k in ["recurring_contribution", "total_capital", "field_provenance"]},
        "status": measured["status"], "failed_checks": measured["failed_checks"],
        "missing_required_fields": outcome["missing_required_fields"],
        "clarification_reason": outcome["clarification"]["reason_code"],
    }, sort_keys=True))
