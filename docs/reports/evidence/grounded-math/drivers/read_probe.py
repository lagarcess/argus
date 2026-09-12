"""The interpreter's typed read for the smoke questions and a few prompts that
must not become calculations, through the production interpreter only: no
stage, no research, no persistence. Paid, interpreter calls only.
Usage: GM_TREE=<repo> [GM_ENV_FILE=<.env>] python read_probe.py <out.json>"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

TREE = Path(os.environ["GM_TREE"]).resolve()
sys.path.insert(0, str(TREE / "src"))
load_dotenv(os.environ.get("GM_ENV_FILE") or TREE / ".env", override=False)
os.environ["ARGUS_RESEARCH_RAIL_ENABLED"] = "true"
os.environ["ARGUS_MARKET_DATA_PROVIDER_MODE"] = "live_provider"
os.environ["ARGUS_ASSET_PROVIDER_MODE"] = "live_provider"

from argus.agent_runtime.capabilities.contract import (  # noqa: E402
    build_default_capability_contract,  # noqa: E402
)
from argus.agent_runtime.interpreter.calculation_focused_read import (  # noqa: E402
    focused_calculation_request,
    focused_calculation_trigger,
)
from argus.agent_runtime.llm_interpreter import (  # noqa: E402
    OpenRouterStructuredInterpreter,  # noqa: E402
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest  # noqa: E402
from argus.agent_runtime.state.models import UserState  # noqa: E402

QUESTIONS = json.loads((TREE / "docs/reports/evidence/grounded-math/drivers/questions.json").read_text())
NOT_CALCULATIONS = [
    ("backtest", "en", "Buy and hold Apple for the last year with $10,000."),
    ("concept", "en", "What is compound interest?"),
    ("counterfactual", "en", "What if I had bought Coca-Cola every month for five years?"),
    ("discovery", "en", "find me cryptos that are trending"),
    ("dca", "es-419", "Invierte $200 al mes en SPY desde enero hasta diciembre de 2024."),
]


async def main() -> None:
    interpreter = OpenRouterStructuredInterpreter(contract=build_default_capability_contract())
    prompts = [
        (row["id"], language, row[language])
        for row in QUESTIONS
        if row["id"] not in ("q9", "q10")
        for language in ("en", "es-419")
    ] + NOT_CALCULATIONS
    rows = []
    for label, language, text in prompts:
        user = UserState(
            user_id="read-probe",
            language_preference=language,
            country="DO" if language == "es-419" else "US",
            currency="DOP" if language == "es-419" else "USD",
        )
        read = await interpreter.ainvoke(
            InterpretationRequest(
                current_user_message=text,
                recent_thread_history=[],
                latest_task_snapshot=None,
                selected_thread_metadata={},
                user=user,
            )
        )
        row = {"label": label, "language": language, "text": text}
        if read is None:
            row["read"] = None
        else:
            row.update(
                intent=read.intent,
                act=read.semantic_turn_act,
                requires_clarification=read.requires_clarification,
                missing=read.missing_required_fields,
                calculation=read.calculation.model_dump(mode="json") if read.calculation else None,
                research_query=read.research_query.question_kind if read.research_query else None,
                strategy_assets=list(read.candidate_strategy_draft.asset_universe or []),
                strategy_type=read.candidate_strategy_draft.strategy_type,
                unsupported=[item.category for item in read.unsupported_constraints],
                lead=read.assistant_response,
            )
            trigger = focused_calculation_trigger(read)
            recovered = await focused_calculation_request(interpretation=read, message=text, history=[]) if trigger else None
            row.update(focused_trigger=trigger, recovered=recovered.model_dump(mode="json") if recovered else None)
        rows.append(row)
        calc = row.get("recovered") or row.get("calculation") or {}
        print(json.dumps({"label": f"{label}-{language}", "kind": calc.get("kind"), "inputs": calc.get("inputs"), "retrieve": calc.get("retrieve"), "follow_ups": len(calc.get("follow_up_questions") or []), "trigger": row.get("focused_trigger"), "clarify": row.get("requires_clarification"), "missing": row.get("missing"), "intent": row.get("intent"), "strategy": row.get("strategy_type"), "unsupported": row.get("unsupported")}, ensure_ascii=False))
    Path(sys.argv[1]).write_text(json.dumps({"captured_at": datetime.now(timezone.utc).isoformat(), "rows": rows}, indent=2, ensure_ascii=False) + "\n")


asyncio.run(main())
