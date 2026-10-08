"""Dump per-turn provider receipts for the #600 DCA replays with and without the turn allowance."""

from __future__ import annotations

import contextlib
import json
import os

import pytest

from tests.agent_runtime.test_issue_600_measurement_replay import PESOS, replay_case
from tests.evals import measurement_eval_harness as harness
from tests.evals.measurement_eval_harness import load_eval_cases

OUT = os.environ.get("ALLOWANCE_DUMP", "/tmp/allowance_dump.jsonl")


@pytest.mark.parametrize("allowance", ["on", "off"])
@pytest.mark.parametrize(
    "case_id",
    [PESOS, "dca_capital_semantics_prebaked_chip_bare_amount_reaches_ready_to_run"],
)
@pytest.mark.parametrize("audit_role", ["starting", "recurring"])
def test_dump(monkeypatch, case_id, audit_role, allowance):
    turns = []
    real_scope = harness.turn_execution_scope

    @contextlib.contextmanager
    def recording_scope(*, entry_state):
        with real_scope(entry_state=entry_state) as execution:
            yield execution
            turns.append(
                {
                    "calls_reserved": execution.calls_reserved,
                    "call_allowance": execution.call_allowance,
                    "blocked_tasks": list(execution.blocked_tasks),
                    "last_resort_grant_used": execution.last_resort_repair_grant_used,
                }
            )

    if allowance == "on":
        monkeypatch.setattr(harness, "turn_execution_scope", recording_scope)
    else:
        monkeypatch.setattr(
            harness, "turn_execution_scope", lambda **_: contextlib.nullcontext()
        )
    case = next(c for c in load_eval_cases() if c.id == case_id)
    result = replay_case(case, monkeypatch, audit_role=audit_role)
    with open(OUT, "a") as handle:
        handle.write(
            json.dumps(
                {
                    "case": case_id,
                    "audit_role": audit_role,
                    "allowance": allowance,
                    "turns": turns,
                    "failed_check_codes": result["failed_check_codes"],
                    "typed": result["typed"],
                    "clarification_code": result["clarification_code"],
                    "receipts": [
                        {
                            k: r[k]
                            for k in ("task", "schema_name", "model", "outcome", "failure_mode")
                        }
                        for r in result["receipts"]
                    ],
                }
            )
            + "\n"
        )
