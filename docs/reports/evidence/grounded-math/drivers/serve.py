"""Local Argus API for the Any grounded math browser evidence.

Memory persistence, mock auth, the real interpreter and research provider,
live asset and market data so any ticker resolves, and receipt sharing on.
Provider keys come from GM_ENV_FILE, which is only read. Scenes a live turn
cannot produce on demand are seeded from real code, never hand-written JSON:
a long transcript for the conversation rail, a provider outage card, a
decision whose stored inputs no longer run, and a withheld retrieval with its
inputs typeable. Their ids are written to GM_SEED_OUT. API on 8620; the web
dev server runs on 3620.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

TREE = Path(os.environ["GM_TREE"]).resolve()
sys.path.insert(0, str(TREE / "src"))
sys.path.insert(0, str(TREE))
load_dotenv(os.environ.get("GM_ENV_FILE") or TREE / ".env", override=False)
API_PORT = int(os.getenv("GM_API_PORT", "8620"))
WEB_PORT = int(os.getenv("GM_WEB_PORT", "3620"))
WEB_ORIGIN = f"http://127.0.0.1:{WEB_PORT}"
os.environ.update(
    {
        "ARGUS_PERSISTENCE_MODE": "memory",
        "ARGUS_DEV_MEMORY_FALLBACK": "true",
        "ARGUS_CHECKPOINTER_MODE": "memory",
        "ARGUS_MOCK_AUTH": "true",
        "ARGUS_MARKET_DATA_PROVIDER_MODE": "live_provider",
        "ARGUS_ASSET_PROVIDER_MODE": "live_provider",
        "ARGUS_RESEARCH_RAIL_ENABLED": "true",
        "ARGUS_EVIDENCE_RECEIPT_SHARING_ENABLED": "true",
        "ARGUS_ENABLE_PERSONALIZATION_MEMORY": "false",
        "ARGUS_CORS_ALLOW_ORIGINS": f"{WEB_ORIGIN},http://localhost:{WEB_PORT}",
        "ARGUS_APP_ORIGIN": WEB_ORIGIN,
        "ARGUS_BACKTEST_JOBS_SHADOW_ENABLED": "false",
        "ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED": "false",
        "ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED": "false",
        "ENABLE_MARKET_DATA_CACHE": "false",
        "DATABASE_URL": "",
        "POSTHOG_PROJECT_TOKEN": "",
    }
)
import httpx  # noqa: E402
import uvicorn  # noqa: E402
from argus.api.main import app  # noqa: E402


def _seed() -> None:
    base = f"http://127.0.0.1:{API_PORT}/api/v1"
    for _ in range(120):
        try:
            if httpx.get(f"{base}/me", timeout=2).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    from argus.agent_runtime import research_grounded as grounded
    from argus.agent_runtime.interpreter.calculation_request import CalculationRequest
    from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
    from argus.agent_runtime.state.models import StrategySummary, UserState
    from argus.api import state as api_state
    from argus.api.message_store import create_message, memory_conversation
    from argus.domain.capability_registry import get_tool_catalog
    from argus.domain.computation_marker import computation_from_tool_card, computation_from_tool_cards
    from argus.domain.research.contracts import ResearchPacket
    from argus.domain.tool_contracts import ToolCall, ToolFailure, ToolOutcome, ToolResultCard

    from tests.domain.calculations.support import run_calculation

    owner = httpx.get(f"{base}/me", timeout=5).json()["user"]["id"]
    catalog = get_tool_catalog()
    seeds: dict[str, dict[str, str]] = {}

    def conversation(title: str, language: str) -> str:
        return memory_conversation(title=title, title_source="user_renamed", language=language, user_id=owner).id

    def say(conversation_id: str, role: str, content: str, metadata: dict | None = None) -> str:
        return create_message(user_id=owner, conversation_id=conversation_id, role=role, content=content, metadata=metadata or {}).id

    def answer(conversation_id: str, card: ToolResultCard, content: str, extra: dict | None = None) -> str:
        card = card.model_copy(update={"artifact_id": str(uuid4())})
        metadata = {
            "tool_result_cards": [card.model_dump(mode="json")],
            "computation": computation_from_tool_card(card).model_dump(mode="json"),
            "agent_runtime_turn": {"terminal": True, "status": "completed"},
            **(extra or {}),
        }
        return say(conversation_id, "assistant", content, metadata)

    loan = {"direction": "borrow", "currency": "USD", "present_value": 30000, "payment": None, "future_value": 0, "annual_rate_pct": 7, "periods": 60}
    multiple = {"currency": "USD", "symbol": "AAPL", "price": 230, "per_share": 6.5, "multiple": None}
    growth = {"currency": "USD", "start_value": 10000, "contribution": 200, "end_value": None, "annual_rate_pct": 5, "periods": 120, "inflation_rate_pct": 3}
    below_interest = {"direction": "borrow", "currency": "USD", "present_value": 180000, "payment": 2000, "future_value": 0, "annual_rate_pct": 14, "periods": None}

    for language, lead in (("en", "Here is that calculation."), ("es-419", "Aquí está ese cálculo.")):
        rail = conversation("Rail: three computed answers" if language == "en" else "Riel: tres cálculos", language)
        turns = [
            ("What would a 30,000 car loan at 7% for five years cost a month?", run_calculation("time_value", loan)),
            ("And is Apple expensive at 230 with 6.50 in earnings?", run_calculation("price_multiple", multiple)),
            ("If I keep 10,000 and add 200 a month at 5% for ten years?", run_calculation("growth_projection", growth)),
            ("I owe 180,000 at 14% and pay 2,000 a month. When is it paid?", run_calculation("time_value", below_interest)),
        ]
        for question, card in turns:
            say(rail, "user", question)
            answer(rail, card, lead)
            say(rail, "user", "Thanks, that helps.")
            say(rail, "assistant", "Glad it helps. Change any input on the card to recompute it.")
        seeds[f"rail-{language}"] = {"conversation_id": rail}

        outage = conversation("Outage card" if language == "en" else "Tarjeta con falla del proveedor", language)
        say(outage, "user", "What would a 30,000 car loan at 7% for five years cost a month?")
        declaration = catalog.get("time_value")
        card = declaration.result_card(
            call=ToolCall(tool_name="time_value", call_id=f"seed-{uuid4()}", arguments=loan),
            outcome=ToolOutcome(status="unavailable", failure=ToolFailure(code="tool_execution_failed")),
            artifact_id=str(uuid4()),
        )
        seeds[f"outage-{language}"] = {"conversation_id": outage, "message_id": answer(outage, card, lead)}

        stale = conversation("Decision that cannot re-run" if language == "en" else "Decisión que no se puede recalcular", language)
        say(stale, "user", "What would a 30,000 car loan at 7% for five years cost a month?")
        stale_message = answer(stale, run_calculation("time_value", loan), lead)
        decided = httpx.post(f"{base}/conversations/{stale}/messages/{stale_message}/decision", json={"decision_state": "watching"}, timeout=10).json()["decision"]
        stored = api_state.store.decision_notes[decided["id"]]
        broken = stored.computation.model_copy(update={"inputs": {**stored.computation.inputs, "periods": 0}})
        api_state.store.decision_notes[decided["id"]] = stored.model_copy(update={"computation": broken})
        seeds[f"stale-decision-{language}"] = {"conversation_id": stale, "message_id": stale_message, "decision_id": decided["id"]}

        withheld = conversation("Withheld retrieval" if language == "en" else "Recuperación retenida", language)
        question = "What will $10,000 in NVDA be worth in ten years?" if language == "en" else "¿Cuánto valdrán $10,000 en NVDA dentro de diez años?"
        say(withheld, "user", question)
        interpretation = StructuredInterpretation(
            intent="conversation_followup", task_relation="new_task", user_goal_summary="scenario",
            semantic_turn_act="educational_question", candidate_strategy_draft=StrategySummary(),
            calculation=CalculationRequest(kind="valuation_scenarios", inputs={"amount": 10000, "horizon_years": 10}),
        )
        result = grounded._packet_stage_result(
            packet=ResearchPacket(answer_markdown=""),
            subjects=[{"symbol": "NVDA", "name": "NVIDIA", "asset_class": "equity"}],
            shape="balanced", capability_class="balanced_lookup", language=language,
            interpretation=interpretation,
            user=UserState(user_id=owner, language_preference=language, currency="USD"),
            cache_status="miss", question_kind="company_lookup",
            scenario=True, computation=grounded._scenario_computation(interpretation),
        )
        patch = result.stage_patch
        cards = patch["final_response_payload"]["tool_result_cards"]
        marker = computation_from_tool_cards([ToolResultCard.model_validate(card) for card in cards])
        metadata = {
            "tool_result_cards": cards,
            "computation": marker.model_dump(mode="json"),
            "research": patch["research"],
            "agent_runtime_turn": {"terminal": True, "status": "completed"},
            **({"next_experiments": patch["next_experiments"]} if patch.get("next_experiments") else {}),
        }
        seeds[f"withheld-{language}"] = {"conversation_id": withheld, "message_id": say(withheld, "assistant", patch["assistant_response"], metadata)}

    Path(os.environ.get("GM_SEED_OUT", "seeds.json")).write_text(json.dumps(seeds, indent=2) + "\n")
    print("seeded", json.dumps(seeds), flush=True)


threading.Thread(target=_seed, daemon=True).start()
uvicorn.run(app, host="127.0.0.1", port=API_PORT, log_level="info")
