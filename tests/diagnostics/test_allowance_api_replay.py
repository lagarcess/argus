"""Replay the #600 DCA prebaked-chip scripts through /api/v1/chat/stream.

The model transport is the only seam: the production route opens
turn_execution_scope, the default workflow runs the real interpreter, audits,
repairs and clarifier, and every permit decision is logged.

Two scripts per case:
- "authored": the replay test's script (underfilled follow-up, focused repair).
- "recorded": the follow-up's primary times out and the fallback reads the
  whole answer, matching the accepted measurement's recorded receipts for
  the bare-amount case (preflight, timeout, fallback, two DCA audits,
  continuity, contribution role, field fidelity).
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import socket
from typing import Any

import httpx
import pytest
from argus.agent_runtime import turn_execution
from argus.api import state as api_state
from argus.api.main import app
from argus.domain.market_data import assets
from argus.llm import openrouter

from tests.evals.measurement_eval_harness import load_eval_cases
from tests.test_chat_stream_contract import _data_events
from tests.test_confirmation_direct_edit import _client, _conversation

OUT = os.environ.get("ALLOWANCE_API_DUMP", "/tmp/allowance_api_dump.jsonl")
PESOS = "dca_capital_semantics_prebaked_chip_spanish_pesos_reaches_ready_to_run"
BARE = "dca_capital_semantics_prebaked_chip_bare_amount_reaches_ready_to_run"


def scripted_post(case: Any, script: str, audit_role: str, calls: list) -> Any:
    amount = case.expected.capital_amount
    pending = case.snapshot.pending_strategy_summary.model_dump(mode="json")
    draft = {
        "strategy_type": "dca_accumulation",
        "asset_universe": list(case.expected.assets),
        "asset_class": "equity",
        "capital_amount": amount,
        "initial_capital": None,
        "cadence": case.expected.contribution_period,
        "date_range": pending.get("date_range"),
    }
    focused = {
        **draft,
        "is_testable_strategy": True,
        "requires_clarification": False,
        "language": case.user_language,
        "user_goal_summary": case.followup_prompt,
        "confidence": 0.9,
        "comparison_baseline": "SPY",
    }
    state = {"followup": False, "primary": 0, "followup_primary": 0, "followup_dca": 0}

    async def post(*, client, api_key, payload, retry_attempt):
        task, _, _, _, schema, _ = retry_attempt
        calls.append({"task": task, "schema": schema, "model": payload["model"]})
        messages = payload["messages"]
        human = [m["content"] for m in messages if m["role"] == "user"]
        followup = state["followup"]
        if schema == "LLMAssetMentionExtraction":
            followup = state["followup"] = bool(
                human and case.followup_prompt in human[-1]
            )
            result = {
                "all_traded_asset_mentions_included": True,
                "asset_mentions": []
                if followup
                else [
                    {
                        "raw_text": draft["asset_universe"][0],
                        "role": "traded_asset",
                        "mention_kind": "ticker",
                        "confidence": 0.9,
                    }
                ],
            }
        elif schema == "LLMInterpretationResponse":
            state["primary"] += 1
            if followup:
                state["followup_primary"] += 1
            result = {
                "intent": "backtest_execution",
                "task_relation": "continue" if followup else "new_task",
                "semantic_turn_act": "answer_pending_need" if followup else "new_idea",
                "requires_clarification": not followup,
                "missing_required_fields": [] if followup else ["capital_amount"],
                "user_goal_summary": case.followup_prompt if followup else case.prompt,
                "candidate_strategy_draft": copy.deepcopy(draft),
            }
            if state["primary"] == 1:
                raise asyncio.TimeoutError()
            if script in {"recorded", "recorded8", "recorded8ff"} and followup and state["followup_primary"] == 1:
                raise asyncio.TimeoutError()
            if not followup:
                result["candidate_strategy_draft"]["capital_amount"] = None
            elif script == "authored":
                result["candidate_strategy_draft"]["date_range"] = None
        elif schema == "FocusedStrategyExtraction":
            result = copy.deepcopy(focused)
        elif schema == "DcaContractAudit":
            if followup:
                state["followup_dca"] += 1
            settles = followup and not (script in {"recorded8", "recorded8ff"} and state["followup_dca"] == 1)
            result = {
                "is_recurring_buy_request": True,
                "cadence": draft["cadence"],
                "recurring_contribution_amount": amount if settles else None,
                "confidence": 0.9 if settles or not followup else 0.3,
            }
        elif schema == "StrategyFamilyContinuityAudit":
            result = {"should_rebind_strategy_family": False, "confidence": 0.9}
        elif schema == "DcaContributionRoleAudit":
            result = {
                "recurring_contribution_explicit": True,
                "total_budget_not_recurring": False,
                "confidence": 0.9,
            }
        elif schema == "FocusedDateWindowExtraction":
            result = {"has_date_window": False, "confidence": 0.9}
        elif schema == "StatedRunFieldFidelityAudit":
            role = (
                "capital_amount"
                if audit_role == "starting"
                else "recurring_contribution_amount"
            )
            result = {role: amount if followup else None, "confidence": 0.9}
        elif schema == "ClarificationResponse":
            context = next(
                json.loads(m["content"])
                for m in messages
                if m["role"] == "system" and m["content"].startswith("{")
            )
            result = {
                "question": "¿Qué supuesto quieres usar?"
                if followup
                else "¿Cuánto debería usar?",
                "direct_question": "¿Cuánto debería usar?",
                "question_targets": context["expected_question_targets"],
                "directly_asks_user": True,
                "detail_targets": context["expected_detail_targets"],
            }
        else:
            raise AssertionError(f"unexpected_schema:{schema}")
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(result)}}]}
        )

    return post


@pytest.mark.parametrize("allowance", ["7", "off"])
@pytest.mark.parametrize("script", ["authored", "recorded", "recorded8", "recorded8ff"])
@pytest.mark.parametrize("audit_role", ["starting", "recurring"])
@pytest.mark.parametrize("case_id", [PESOS, BARE])
def test_api_replay(monkeypatch, case_id, audit_role, script, allowance):
    case = next(c for c in load_eval_cases() if c.id == case_id)
    calls: list[dict] = []
    permits: list[dict] = []
    real_reserve = turn_execution.reserve_provider_call

    def logged_reserve(task, task_timeout_seconds=None):
        permit = real_reserve(task, task_timeout_seconds)
        execution = turn_execution.active_turn_execution()
        permits.append(
            {
                "task": str(task),
                "granted": permit is not None,
                "in_scope": execution is not None,
                "reserved": execution.calls_reserved if execution else None,
                "grant_used": execution.last_resort_repair_grant_used
                if execution
                else None,
            }
        )
        return permit

    for key in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY", "PERPLEXITY_API_KEY"):
        monkeypatch.setenv(key, "")
    for key, value in dict(
        OPENROUTER_API_KEY="hermetic-test-key",
        ARGUS_ASSET_PROVIDER_MODE="synthetic_unit_fixture",
        ARGUS_MARKET_DATA_PROVIDER_MODE="synthetic_unit_fixture",
        ARGUS_STRUCTURED_MODEL="x-ai/grok-4.3",
        ARGUS_STRUCTURED_FALLBACK_MODEL="anthropic/claude-haiku-4.5",
        ARGUS_CHAT_MODEL="deepseek/deepseek-v4-flash",
        ARGUS_CHAT_FALLBACK_MODEL="qwen/qwen3.5-9b",
        ARGUS_RESEARCH_RAIL_ENABLED="false",
        ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED="false",
        ARGUS_RUNTIME_STREAM_WORKER="false",
        ARGUS_ENABLE_SPANISH="true",
    ).items():
        monkeypatch.setenv(key, value)
    if allowance == "off":
        monkeypatch.setattr(turn_execution, "_turn_call_allowance", lambda: 10_000)
    monkeypatch.setattr(turn_execution, "reserve_provider_call", logged_reserve)
    monkeypatch.setattr(socket.socket, "connect", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network_forbidden")))
    monkeypatch.setattr(
        openrouter,
        "_post_openrouter_json_schema",
        scripted_post(case, script, audit_role, calls),
    )
    monkeypatch.setattr(
        "argus.agent_runtime.stages.confirm.fetch_alpaca_market_clock", lambda: None
    )
    monkeypatch.setitem(assets.SYNTHETIC_UNIT_ASSETS, "KO", ("equity", "Coca-Cola", "KO"))
    monkeypatch.setattr(assets, "_ASSET_ALIAS_MAP", None)

    if script == "recorded8ff":
        # The recorded turn's eighth call was a field-fidelity audit whose
        # trigger depends on reply bodies the measurement did not keep.
        from argus.agent_runtime import llm_interpreter

        real_needs = llm_interpreter._response_needs_stated_run_field_fidelity_audit

        def needs(*, response, request=None):
            if request is not None and case.followup_prompt in request.current_user_message:
                return True
            return real_needs(response=response, request=request)

        monkeypatch.setattr(
            llm_interpreter, "_response_needs_stated_run_field_fidelity_audit", needs
        )
    client = _client()
    api_state.reset_agent_runtime_workflow(app)
    conversation = _conversation(client)
    turns = []
    for message in (case.prompt, case.followup_prompt):
        start = len(permits)
        response = client.post(
            "/api/v1/chat/stream",
            json={
                "conversation_id": conversation["id"],
                "message": message,
                "ui_language": case.ui_language,
            },
        )
        events = _data_events(response.text)
        final = next((e["payload"] for e in events if e.get("type") == "final"), None)
        errors = [e for e in events if e.get("type") == "error"]
        turns.append(
            {
                "message": message,
                "http": response.status_code,
                "stage_outcome": (final or {}).get("stage_outcome"),
                "has_confirmation": bool((final or {}).get("confirmation")),
                "card_rows": [
                    (row.get("key"), row.get("value"))
                    for row in ((final or {}).get("confirmation") or {}).get("rows", [])
                ],
                "assistant": ((final or {}).get("assistant_message") or {}).get("content")
                or (final or {}).get("content")
                or (final or {}).get("message"),
                "errors": errors,
                "permits": permits[start:],
            }
        )
    messages = client.get(
        f"/api/v1/conversations/{conversation['id']}/messages"
    ).json()["items"]
    for turn, assistant in zip(
        turns, [m for m in messages if m["role"] == "assistant"], strict=False
    ):
        turn["persisted_content"] = assistant["content"]
        turn["turn_execution"] = (assistant.get("metadata") or {}).get(
            "turn_execution"
        ) or ((assistant.get("metadata") or {}).get("runtime_receipt") or {}).get(
            "turn_execution"
        )
    with open(OUT, "a") as handle:
        handle.write(
            json.dumps(
                {
                    "case": case_id,
                    "audit_role": audit_role,
                    "script": script,
                    "allowance": allowance,
                    "turns": turns,
                    "calls": calls,
                },
                default=str,
            )
            + "\n"
        )
