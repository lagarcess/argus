"""A Business chat turn runs no Personal tool and no research; Personal is unchanged.

The surface comes from the stored conversation. Business sees an empty tool
catalog today, so research, calculations, backtest confirmations and runs,
recomputes and Personal artifact routes are each refused, and each gate logs
when it fires. The Personal catalog and the runtime-built model-facing text
are pinned to the hashes they had before Business chat existed. No test here
calls a model: the interpreter is scripted and no provider key is set.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Iterator
from typing import Any

import pytest
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.stages.clarify import clarify_stage
from argus.agent_runtime.stages.interpret import (
    InterpretationRequest,
    StageResult,
    StructuredInterpretation,
)
from argus.agent_runtime.stages.interpret_types import AssetDiscoveryRequest
from argus.agent_runtime.stages.tool_execution import execute_tool_calls_async
from argus.agent_runtime.state.models import RunState, StrategySummary, UserState
from argus.api import state as api_state
from argus.api.chat.memory_recall import memory_recalls_for_turn
from argus.api.guest_access import registered_account_context
from argus.api.main import app
from argus.api.message_store import create_message
from argus.api.personalization_memory import configure_memory_service
from argus.domain.calculations.answer_request import calculation_kinds_clause
from argus.domain.capability_registry import get_tool_catalog
from argus.domain.chat_surface import turn_surface_scope
from argus.domain.research import config as research_config
from argus.domain.tool_contracts import ToolCall
from fastapi.testclient import TestClient
from loguru import logger

from tests.domain.calculations.support import run_calculation
from tests.test_chat_stream_contract import _final_payload
from tests.test_conversation_surfaces import (  # noqa: F401
    ALICE,
    _as,
    _CountingMemoryService,
    _create,
    _start_space,
    _user_object,
    client,
)

PERSONAL_TOOLS = [
    "backtest",
    "time_value",
    "growth_projection",
    "bond_value",
    "discounted_cash_flow",
    "price_multiple",
    "income_yield",
    "effective_rate",
    "debt_to_income",
    "expense_ratio",
    "ranked_comparison",
    "valuation_scenarios",
]
RESEARCH_TOOLS = [
    "fast_quote",
    "balanced_lookup",
    "thorough_research",
    "screening",
    "peer_expansion",
]
# sha256 of each text at f5a2007cd, before Business chat had restrictions. A
# catalog hashes in canonical form: Python caches equal Literal types, so an
# enum's order in the schema depends on import order.
PERSONAL_TEXT_SHA256 = {
    "calculation_kinds_clause": (
        "a2abe87fdef4d02145aa33430e6bfdf585a3126107c5215be507709310e27329"
    ),
    "retrieval_instructions": (
        "7e13e148bba3547887dc87f98594b2afa786f38f428d4651fcf05f4a00950fca"
    ),
    "scenario_retrieval_instructions": (
        "f8d8c15d954bebeac0161b9a21bbe14ba2c41e59f6f19e37fb7919fb3a3d3823"
    ),
    "catalog_research_off": (
        "e30d240846001019ea433a7185b0c167077148a735e82048364772bea696f5af"
    ),
    "catalog_research_on": (
        "058d134096093b947449184c6a4d71ca1124239a998580a90dc9001f6ce582b2"
    ),
}


@pytest.fixture
def gates() -> Iterator[list[dict[str, Any]]]:
    fired: list[dict[str, Any]] = []
    sink = logger.add(
        lambda message: fired.append(dict(message.record["extra"])),
        filter=lambda record: "surface_gate" in record["extra"],
        level="INFO",
    )
    try:
        yield fired
    finally:
        logger.remove(sink)


@pytest.fixture(autouse=True)
def _no_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("OPENROUTER_API_KEY", "PERPLEXITY_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: sorted(map(json.dumps, item)) if key == "enum" else _canonical(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    return value


def _catalog_sha(text: str) -> str:
    return _sha(json.dumps(_canonical(json.loads(text)), sort_keys=True))


def _gate_names(fired: list[dict[str, Any]]) -> list[str]:
    return [item["surface_gate"] for item in fired]


@pytest.mark.parametrize("scope", [None, "personal"])
def test_personal_model_facing_text_and_catalog_are_unchanged(
    monkeypatch: pytest.MonkeyPatch, gates: list[dict[str, Any]], scope: str | None
) -> None:
    def observed() -> dict[str, str]:
        monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")
        off = get_tool_catalog(surface="personal").capability_text()
        monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
        on = get_tool_catalog(surface="personal").capability_text()
        return {
            "calculation_kinds_clause": _sha(calculation_kinds_clause()),
            "retrieval_instructions": _sha(research_config.RETRIEVAL_INSTRUCTIONS),
            "scenario_retrieval_instructions": _sha(
                research_config.SCENARIO_RETRIEVAL_INSTRUCTIONS
            ),
            "catalog_research_off": _catalog_sha(off),
            "catalog_research_on": _catalog_sha(on),
        }

    if scope is None:
        assert observed() == PERSONAL_TEXT_SHA256
    else:
        with turn_surface_scope("personal"):
            assert observed() == PERSONAL_TEXT_SHA256
            assert research_config.research_rail_enabled() is True
    assert gates == []


def test_a_business_turn_sees_no_tool_and_no_research(
    monkeypatch: pytest.MonkeyPatch, gates: list[dict[str, Any]]
) -> None:
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")

    with turn_surface_scope("business"):
        assert get_tool_catalog(surface="business").declarations == ()
        assert research_config.research_rail_enabled() is False
        assert research_config.research_rail_enabled() is False
        # The kinds text is a constant; the gate keeps it from any Business call.
        assert (
            _sha(calculation_kinds_clause())
            == PERSONAL_TEXT_SHA256["calculation_kinds_clause"]
        )

    assert _gate_names(gates) == ["research", "tool_catalog"]
    assert gates[1]["withheld"] == len(PERSONAL_TOOLS)


def test_a_personal_turn_beside_it_keeps_every_tool(
    monkeypatch: pytest.MonkeyPatch, gates: list[dict[str, Any]]
) -> None:
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    with turn_surface_scope("business"):
        research_config.research_rail_enabled()
    with turn_surface_scope("personal"):
        names = [item.name for item in get_tool_catalog(surface="personal").declarations]
        assert names == PERSONAL_TOOLS + RESEARCH_TOOLS
        assert research_config.research_rail_enabled() is True
    assert _gate_names(gates) == ["research"]


def test_the_execute_stage_refuses_a_call_outside_the_business_catalog(
    gates: list[dict[str, Any]],
) -> None:
    calls = [ToolCall(tool_name="time_value", call_id="call-1", arguments={})]
    state = RunState.new(current_user_message="calculate", recent_thread_history=[])
    state.tool_calls = calls

    with turn_surface_scope("business"):
        result = asyncio.run(
            execute_tool_calls_async(state=state, tool=None, language="es-419")
        )

    assert result.outcome == "ready_to_respond"
    assert result.patch["recovery"] == {
        "code": "business_chat_tool_unavailable",
        "retryable": False,
    }
    assert result.patch["tool_call_records"] == []
    assert [(g["surface_gate"], g.get("tools")) for g in gates] == [
        ("tool_catalog", None),
        ("tool_call", ["time_value"]),
    ]


def test_a_business_backtest_draft_gets_no_clarifying_question(
    gates: list[dict[str, Any]],
) -> None:
    state = RunState.new(
        current_user_message="Prueba comprar bitcoin cada mes durante 2024",
        recent_thread_history=[],
    )
    state.intent = "backtest_execution"
    asked: list[object] = []

    class Clarifier:
        async def ainvoke(self, request: object) -> str:
            asked.append(request)
            return "¿Con cuánto quieres empezar?"

    with turn_surface_scope("business"):
        result = clarify_stage(
            state=state,
            contract=build_default_capability_contract(),
            clarification_generator=Clarifier(),  # type: ignore[arg-type]
            language="es-419",
        )

    assert result.outcome == "ready_to_respond"
    assert result.patch["recovery"]["code"] == "business_chat_tool_unavailable"
    assert asked == []
    assert _gate_names(gates) == ["tool_catalog", "backtest_clarification"]


def test_a_business_turn_voices_no_calculation(
    monkeypatch: pytest.MonkeyPatch, gates: list[dict[str, Any]]
) -> None:
    from argus.agent_runtime import calculated_answer as module

    voiced: list[object] = []
    monkeypatch.setattr(module, "resolve_openrouter_api_key", lambda: "test-key")
    monkeypatch.setattr(module, "_voice", lambda messages: voiced.append(messages))
    user = UserState(user_id=ALICE, language_preference="en")

    with turn_surface_scope("business"):
        answer = module.calculated_answer(
            message="200 cupcakes at $3, $1.20 each to make: my profit?",
            language="en",
            user=user,
            notes=[],
        )

    assert answer is None
    assert voiced == []
    assert _gate_names(gates) == ["calculation"]


class _ScriptedInterpreter:
    def __init__(self, interpretation: StructuredInterpretation) -> None:
        self.interpretation = interpretation

    async def ainvoke(self, request: InterpretationRequest) -> StructuredInterpretation:
        del request
        return self.interpretation.model_copy(deep=True)


def _install_runtime(
    monkeypatch: pytest.MonkeyPatch, interpretation: StructuredInterpretation
) -> None:
    checkpointer = api_state.build_agent_runtime_checkpointer()
    workflow = build_workflow(
        contract=build_default_capability_contract(),
        structured_interpreter=_ScriptedInterpreter(interpretation),
        checkpointer=checkpointer,
    )
    monkeypatch.setattr(
        app.state, "agent_runtime_checkpointer", checkpointer, raising=False
    )
    monkeypatch.setattr(app.state, "agent_runtime_workflow", workflow, raising=False)


def _turn(client: TestClient, conversation_id: str, message: str) -> dict[str, Any]:  # noqa: F811
    response = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": conversation_id, "message": message},
        headers=_as(ALICE),
    )
    assert response.status_code == 200, response.text
    return _final_payload(response.text)


BACKTEST = StructuredInterpretation(
    intent="backtest_execution",
    task_relation="new_task",
    requires_clarification=False,
    user_goal_summary="Buy and hold Apple for a year.",
    candidate_strategy_draft=StrategySummary(
        raw_user_phrasing="Buy and hold Apple for the last year with $10,000",
        strategy_type="buy_and_hold",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2023-01-02", "end": "2023-12-29"},
        capital_amount=10000,
        extra_parameters={
            "date_range_intent": {
                "kind": "explicit_range",
                "start": "2023-01-02",
                "end": "2023-12-29",
            },
            "field_provenance": {"date_range": "explicit_user"},
        },
    ),
    semantic_turn_act="new_idea",
)


def test_a_business_turn_gets_no_backtest_card_where_personal_does(
    client: TestClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    gates: list[dict[str, Any]],
) -> None:
    _install_runtime(monkeypatch, BACKTEST)
    _start_space(ALICE)
    business = _create(client, ALICE, "Shop ledger", surface="business")
    personal = _create(client, ALICE, "Household ledger")
    message = "Buy and hold Apple for the last year with $10,000"

    refused = _turn(client, business, message)
    assert _gate_names(gates) == ["tool_catalog", "backtest_confirmation"]
    offered = _turn(client, personal, message)

    assert refused["stage_outcome"] == "ready_to_respond"
    assert refused["recovery"] == {
        "code": "business_chat_tool_unavailable",
        "retryable": False,
    }
    assert not refused.get("confirmation")
    assert offered["stage_outcome"] == "await_approval"
    assert offered["confirmation"]
    assert _gate_names(gates) == ["tool_catalog", "backtest_confirmation"]
    assert api_state.store.backtest_runs == {}


QUESTION = StructuredInterpretation(
    intent="conversation_followup",
    task_relation="new_task",
    requires_clarification=False,
    user_goal_summary="What is Tesla's price now?",
    candidate_strategy_draft=StrategySummary(),
    semantic_turn_act="educational_question",
    research_query={"question_kind": "company_lookup", "symbols": ["TSLA"]},
)


def test_a_business_question_never_reaches_research(
    client: TestClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    gates: list[dict[str, Any]],
) -> None:
    from argus.agent_runtime import research_answer

    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    researched: list[str] = []

    async def fake_research(*, interpretation, state, user) -> StageResult:  # noqa: ANN001
        researched.append(state.current_user_message)
        return StageResult(
            outcome="ready_to_respond",
            stage_patch={"assistant_response": "Tesla closed at a cited price."},
        )

    monkeypatch.setattr(research_answer, "research_answer_stage_result", fake_research)
    _install_runtime(monkeypatch, QUESTION)
    _start_space(ALICE)
    business = _create(client, ALICE, "Shop ledger", surface="business")
    personal = _create(client, ALICE, "Household ledger")

    _turn(client, business, "What is Tesla's price now?")
    assert researched == []
    assert "research" in _gate_names(gates)
    _turn(client, personal, "What is Tesla's price now?")
    assert researched == ["What is Tesla's price now?"]


def test_a_business_conversation_starts_no_direct_run(
    client: TestClient,  # noqa: F811
    gates: list[dict[str, Any]],
) -> None:
    _start_space(ALICE)
    business = _create(client, ALICE, "Shop ledger", surface="business")

    response = client.post(
        "/api/v1/backtests/run",
        json={
            "conversation_id": business,
            "template": "buy_and_hold",
            "symbols": ["AAPL"],
            "timeframe": "1Day",
            "start_date": "2023-01-03",
            "end_date": "2023-12-29",
        },
        headers={**_as(ALICE), "Idempotency-Key": "business-direct-run-0001"},
    )

    assert (response.status_code, response.json()["detail"]) == (
        404,
        "Conversation not found.",
    )
    assert [(g["surface_gate"], g.get("tools")) for g in gates][-1] == (
        "tool_call",
        ["backtest"],
    )
    assert api_state.store.backtest_runs == {}


def test_a_business_card_cannot_be_recomputed(
    client: TestClient,  # noqa: F811
    gates: list[dict[str, Any]],
) -> None:
    _start_space(ALICE)
    business = _create(client, ALICE, "Shop ledger", surface="business")
    card = run_calculation(
        "time_value",
        {
            "direction": "borrow",
            "currency": "USD",
            "present_value": 200_000,
            "payment": None,
            "future_value": 0,
            "annual_rate_pct": 6,
            "periods": 360,
        },
    ).model_copy(update={"artifact_id": "00000000-0000-4000-8000-00000000c4d0"})
    message = create_message(
        user_id=ALICE,
        conversation_id=business,
        role="assistant",
        content="",
        metadata={"tool_result_cards": [card.model_dump(mode="json")]},
    )

    response = client.post(
        f"/api/v1/conversations/{business}/tool-results/{card.artifact_id}/recompute",
        json={
            "message_id": message.id,
            "input_revision": 0,
            "arguments": {"annual_rate_pct": 5},
        },
        headers=_as(ALICE),
    )

    assert (response.status_code, response.json()["code"]) == (
        422,
        "tool_inputs_not_editable",
    )
    assert [(g["surface_gate"], g.get("tools")) for g in gates][-1] == (
        "tool_call",
        ["time_value"],
    )


@pytest.mark.parametrize("path", ["peer-assets", "direct-edit"])
def test_business_confirmation_edits_answer_404_and_log(
    client: TestClient,  # noqa: F811
    gates: list[dict[str, Any]],
    path: str,
) -> None:
    _start_space(ALICE)
    business = _create(client, ALICE, "Shop ledger", surface="business")

    response = client.post(
        f"/api/v1/conversations/{business}/confirmations/c-1/{path}",
        json={},
        headers=_as(ALICE),
    )

    assert (response.status_code, response.json()["detail"]) == (
        404,
        "Conversation not found.",
    )
    assert _gate_names(gates) == ["personal_route"]


def test_a_business_turn_logs_the_memory_recall_it_skips(
    client: TestClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    gates: list[dict[str, Any]],
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", "true")
    service = _CountingMemoryService()
    configure_memory_service(service)  # type: ignore[arg-type]
    try:
        _start_space(ALICE)
        business = _create(client, ALICE, "Shop ledger", surface="business")

        recalled = memory_recalls_for_turn(
            user=_user_object(ALICE),
            account=registered_account_context(ALICE),
            conversation_id=business,
            user_message="what did I decide?",
            memory_opt_out=False,
        )
    finally:
        configure_memory_service(None)

    assert recalled is None
    assert service.calls == 0
    assert _gate_names(gates) == ["memory_recall"]


def test_a_business_turn_runs_no_asset_discovery(
    client: TestClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    gates: list[dict[str, Any]],
) -> None:
    from argus.agent_runtime.discovery import composer

    searched: list[object] = []

    async def fake_find(**kwargs: object) -> StageResult:
        searched.append(kwargs)
        return StageResult(
            outcome="ready_to_respond",
            stage_patch={"assistant_response": "Rivian, Lucid."},
        )

    monkeypatch.setattr(composer, "discovery_operation_result", fake_find)
    _install_runtime(
        monkeypatch,
        StructuredInterpretation(
            intent="conversation_followup",
            task_relation="new_task",
            requires_clarification=False,
            user_goal_summary="Companies like Tesla.",
            candidate_strategy_draft=StrategySummary(),
            semantic_turn_act="asset_discovery",
            asset_discovery=AssetDiscoveryRequest(
                relationship="peer", anchor_symbols=["TSLA"]
            ),
        ),
    )
    _start_space(ALICE)
    business = _create(client, ALICE, "Shop ledger", surface="business")
    personal = _create(client, ALICE, "Household ledger")

    refused = _turn(client, business, "¿Qué empresas parecidas a Tesla puedo mirar?")
    assert refused["recovery"]["code"] == "business_chat_tool_unavailable"
    assert searched == []
    assert _gate_names(gates) == ["asset_discovery"]
    _turn(client, personal, "Companies like Tesla?")
    assert len(searched) == 1
