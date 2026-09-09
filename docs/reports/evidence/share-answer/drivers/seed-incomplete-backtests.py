"""Create two intentionally incomplete historical fixtures, without calculating.

Copy the saved synthetic engine run, omit typed return evidence, then persist
through production finalization. Original runs and frozen receipts stay intact.
These examples exist only to prove that owner selection refuses publication.
"""

from __future__ import annotations

import json
import runpy
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[5]
PRIVATE = ROOT / "temp/share-answer-qa"
runpy.run_path(str(Path(__file__).with_name("start-api.py")))

from argus.domain.backtest_finalization import (  # noqa: E402
    BacktestFinalizationInput,
    finalize_backtest_completion,
)
from argus.domain.backtest_message_projection import result_fact_bank  # noqa: E402
from argus.domain.backtest_run_builder import enrich_result_card_actions  # noqa: E402
from argus.domain.supabase_gateway import SupabaseGateway  # noqa: E402

output = PRIVATE / "incomplete-backtests.json"
assert not output.exists(), "Reuse the incomplete examples."
owner = json.loads((PRIVATE / "owner.json").read_text())
fixture = json.loads((PRIVATE / "selection-fixture.json").read_text())
gateway = SupabaseGateway.from_env()
source = gateway.get_backtest_run(user_id=owner["owner_id"], run_id=fixture["run_id"])
assert source is not None
records = []
for name, keys, question in [
    (
        "missing_headline",
        ("total_return_pct",),
        "Authored incomplete historical example: headline return is missing.",
    ),
    (
        "missing_benchmark",
        ("benchmark_return_pct", "delta_vs_benchmark_pct"),
        "Authored incomplete historical example: benchmark evidence is missing.",
    ),
]:
    metrics = deepcopy(source.metrics)
    performance = metrics["aggregate"]["performance"]
    for key in keys:
        assert key in performance
        performance.pop(key)
    run_id = str(uuid4())
    now = datetime.now(timezone.utc)
    card = enrich_result_card_actions(
        result_card=deepcopy(source.conversation_result_card),
        run_id=run_id,
        strategy_id=None,
        conversation_id=source.conversation_id,
    )
    run = source.model_copy(
        update={
            "id": run_id,
            "metrics": metrics,
            "created_at": now,
            "conversation_result_card": card,
            "figures": None,
        },
        deep=True,
    )
    finalized = finalize_backtest_completion(
        gateway,
        BacktestFinalizationInput(
            user_id=owner["owner_id"],
            execution_identity=f"incomplete-sharing-fixture:{uuid4()}",
            run=run,
            result_card=card,
            idea_id=str(uuid4()),
            idea_version_id=str(uuid4()),
            evidence_artifact_id=str(uuid4()),
            finalized_at=now,
        ),
    )
    common = {"user_id": owner["owner_id"], "conversation_id": source.conversation_id}
    gateway.create_message(**common, role="user", content=question)
    message = gateway.create_message(
        **common,
        role="assistant",
        content="This authored incomplete record checks publication refusal. It is not a new calculation.",
        metadata={
            "agent_runtime_turn": {"terminal": True, "status": "completed"},
            "conversation_mode": "result_review",
            "agent_runtime_stage_outcome": "ready_to_respond",
            "result_run_id": finalized.run.id,
            "latest_run_id": finalized.run.id,
            "result_conversation_id": source.conversation_id,
            "result_card": finalized.run.conversation_result_card,
            "result_fact_bank": result_fact_bank(finalized.run),
        },
    )
    records.append(
        {
            "case": name,
            "question": question,
            "message_id": message.id,
            "run_id": finalized.run.id,
            "artifact_id": finalized.identity.evidence_artifact_id,
        }
    )
    output.write_text(json.dumps({"records": records}, indent=2))
    output.chmod(0o600)
print(
    json.dumps(
        {"incomplete_fixtures": len(records), "calculations": 0, "publications": 0}
    )
)
