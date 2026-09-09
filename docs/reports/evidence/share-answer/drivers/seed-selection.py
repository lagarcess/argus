"""Local presentation fixtures, distinct from the saved real research turns.

The DCA result is computed offline from synthetic prices through the production
metrics, signals, chart, card and finalization owners. Research examples are
explicitly authored fixtures. Nothing here is a live market-data claim.
"""

from __future__ import annotations

import json
import os
import runpy
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
PRIVATE = ROOT / "temp/share-answer-qa"
output = PRIVATE / "selection-fixture.json"
assert not output.exists(), "Reuse the existing fixture instead of duplicating it."
runpy.run_path(str(Path(__file__).with_name("start-api.py")))
os.environ["ARGUS_ENABLE_EXECUTION_REALISM"] = "true"

import httpx  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from argus.api.schemas import BacktestRun  # noqa: E402
from argus.domain.backtest_finalization import (  # noqa: E402
    BacktestFinalizationInput,
    finalize_backtest_completion,
)
from argus.domain.backtest_message_projection import result_fact_bank  # noqa: E402
from argus.domain.backtest_run_builder import enrich_result_card_actions  # noqa: E402
from argus.domain.backtesting.cards import build_result_card  # noqa: E402
from argus.domain.backtesting.charts import build_result_chart  # noqa: E402
from argus.domain.backtesting.signals import _build_signals  # noqa: E402
from argus.domain.supabase_gateway import SupabaseGateway  # noqa: E402

from tests.domain.test_dca_flow_adjusted_metrics import (  # noqa: E402
    _bars,
    _dca_config,
    _run_dca,
)

owner = json.loads((PRIVATE / "owner.json").read_text())
gateway = SupabaseGateway.from_env()
conversation = gateway.create_conversation(
    user_id=owner["owner_id"],
    title="Authored sharing examples",
    title_source="user_renamed",
    language="en",
)
record = {"conversation_id": conversation.id, "source": __doc__, "messages": {}}
output.write_text(json.dumps(record, indent=2))
output.chmod(0o600)


def append(name: str, question: str, answer: str, metadata: dict) -> None:
    gateway.create_message(
        user_id=owner["owner_id"],
        conversation_id=conversation.id,
        role="user",
        content=question,
    )
    message = gateway.create_message(
        user_id=owner["owner_id"],
        conversation_id=conversation.id,
        role="assistant",
        content=answer,
        metadata=metadata,
    )
    record["messages"][name] = message.id
    output.write_text(json.dumps(record, indent=2))


# Seeded scenario from the existing DCA metrics evidence, with the current
# production benchmark path. Every curve and figure uses this one input set.
index = pd.bdate_range("2025-01-02", "2025-06-30", tz="UTC")
random = np.random.RandomState(456)
prices = 240.0 * np.exp(np.cumsum(random.normal(-0.0008, 0.012, len(index))))
benchmark = 580.0 * np.exp(np.cumsum(random.normal(0.0004, 0.008, len(index))))
config = _dca_config(index, contribution=200.0, fee_bps=10.0, slippage_bps=5.0)
bars = _bars(prices.tolist(), index)
entries, exits = _build_signals(config, bars)
metrics = _run_dca(
    config,
    prices=prices.tolist(),
    benchmark_prices=benchmark.tolist(),
    entries=entries.tolist(),
    index=index,
)
chart = build_result_chart(
    config,
    fetch_ohlcv_func=lambda **_: bars,
    build_signals_func=lambda *_: (entries, exits),
)
card = build_result_card(config, metrics, language="en", chart=chart)
card["title"] = "Synthetic example: AAPL monthly"
run_id = str(uuid4())
card = enrich_result_card_actions(
    result_card=card,
    run_id=run_id,
    strategy_id=None,
    conversation_id=conversation.id,
)
now = datetime.now(timezone.utc)
run = BacktestRun(
    id=run_id,
    conversation_id=conversation.id,
    strategy_id=None,
    status="completed",
    asset_class="equity",
    symbols=config["symbols"],
    allocation_method="equal_weight",
    benchmark_symbol=config["benchmark_symbol"],
    config_snapshot=config,
    metrics=metrics,
    chart=chart,
    conversation_result_card=card,
    created_at=now,
)
finalized = finalize_backtest_completion(
    gateway,
    BacktestFinalizationInput(
        user_id=owner["owner_id"],
        execution_identity=f"sharing-fixture:{uuid4()}",
        run=run,
        result_card=card,
        idea_id=str(uuid4()),
        idea_version_id=str(uuid4()),
        evidence_artifact_id=str(uuid4()),
        finalized_at=now,
    ),
)
record["artifact_id"] = finalized.identity.evidence_artifact_id
record["run_id"] = finalized.run.id
record["dca_source"] = {
    "config": config,
    "metrics": metrics,
    "chart": chart,
    "provenance": "Production engine over injected synthetic prices; no provider calls",
}
terminal = {"agent_runtime_turn": {"terminal": True, "status": "completed"}}
append(
    "dca",
    "Synthetic example: buy $200 of AAPL monthly with modeled costs.",
    "This is an offline example using synthetic prices to check the sharing display.",
    {
        **terminal,
        "conversation_mode": "result_review",
        "agent_runtime_stage_outcome": "ready_to_respond",
        "result_run_id": finalized.run.id,
        "latest_run_id": finalized.run.id,
        "result_conversation_id": conversation.id,
        "result_card": finalized.run.conversation_result_card,
        "result_fact_bank": result_fact_bank(finalized.run),
    },
)


def research() -> dict:
    return {
        **deepcopy(terminal),
        "research": {
            "schema_version": "argus_research/v1",
            "shape": "balanced",
            "sources": [
                {
                    "title": "Authored sharing example",
                    "domain": "example.org",
                    "url": "https://example.org/sharing-example",
                    "source_date": None,
                }
            ],
            "retrieved_at": now.isoformat(),
            "anchor_symbols": ["AAPL"],
            "asset_class": "equity",
        },
    }


for ordinal in range(1, 4):
    append(
        f"research_{ordinal}",
        f"Authored sharing example {ordinal}: what does this record explain?",
        f"This authored example {ordinal} checks the immutable receipt display. It makes no market claim.",
        research(),
    )

disabled = [
    (
        "missing_sources",
        "Authored example without typed sources",
        "This prose has a publisher URL: https://example.org/sharing-example",
        "missing_sources",
    ),
    (
        "unlisted_url",
        "Authored example with an unlisted URL",
        "Read https://example.org/absent-source for this authored example.",
        "unlisted_url",
    ),
    (
        "memory_used",
        "Authored example shaped by memory",
        "This authored answer used a remembered preference.",
        "memory_used",
    ),
    (
        "clarification",
        "Authored clarification example",
        "Which period would you like to use?",
        "unsupported_turn",
    ),
    (
        "confirmation",
        "Authored confirmation example",
        "Please confirm this example before continuing.",
        "unsupported_turn",
    ),
    (
        "degraded",
        "Authored degraded example",
        "The sources were unavailable for this example.",
        "degraded",
    ),
    (
        "unsafe_question",
        f"Authored example: include record {uuid4()}",
        "This authored example checks refusal on the question.",
        "unsafe_text",
    ),
    (
        "unsafe_answer",
        "Authored example: which answer field is refused?",
        f"The example record is {uuid4()}.",
        "unsafe_text",
    ),
]
for name, question, answer, _expected in disabled:
    metadata = research()
    if name == "missing_sources":
        metadata["research"]["sources"] = []
    elif name == "memory_used":
        metadata["memory_recalls"] = [{"id": str(uuid4())}]
    elif name == "clarification":
        metadata["conversation_mode"] = "clarification"
        metadata["clarification"] = {"question": answer}
    elif name == "confirmation":
        metadata["confirmation"] = {"title": "Authored confirmation example"}
    elif name == "degraded":
        metadata["research"]["degraded"] = {"code": "research_unavailable_timeout"}
    append(name, question, answer, metadata)

with httpx.Client(
    base_url="http://127.0.0.1:8319/api/v1",
    headers={"Authorization": f"Bearer {owner['session']['access_token']}"},
) as client:
    response = client.get(f"/conversations/{conversation.id}/public-excerpt-candidates")
    response.raise_for_status()
    record["candidates"] = response.json()
    by_id = {item["message_id"]: item for item in record["candidates"]["items"]}
    assert sum(item["eligible"] for item in by_id.values()) == 4
    for name, _question, _answer, expected in disabled:
        assert by_id[record["messages"][name]]["reason"] == expected, name
output.write_text(json.dumps(record, indent=2))
print(json.dumps({"eligible": 4, "disabled": len(disabled), "provider_calls": 0}))
