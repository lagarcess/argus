"""The writer gets the current decision; the interpreter keeps the transcript."""

from __future__ import annotations

import json
from typing import get_args

import pytest
from argus.agent_runtime import llm_clarifier
from argus.agent_runtime.llm_clarifier import ClarificationResponse
from argus.agent_runtime.stages.clarify import _generate_clarifying_question_result
from argus.agent_runtime.state.models import ResponseIntentKind, RunState, StrategySummary


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", get_args(ResponseIntentKind))
@pytest.mark.parametrize("language", ["en", "es-419"])
@pytest.mark.parametrize("fallback", [False, True])
async def test_every_reply_kind_sends_only_current_decision_to_both_writers(
    monkeypatch,
    faker,
    kind,
    language,
    fallback,
) -> None:
    old_reason = faker.sentence()
    old_question = faker.sentence()
    current_message = faker.sentence()
    state = RunState.new(
        current_user_message=current_message,
        recent_thread_history=[
            {"role": "user", "content": old_reason},
            {"role": "assistant", "content": old_question},
        ],
    )
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="buy_and_hold",
        asset_universe=["MRNA"],
        asset_class="equity",
        date_range={"start": "2026-08-16", "end": "2026-08-19"},
    )
    options = [
        {
            "id": "edit_capital",
            "replacement_values": {"requested_field": "capital_amount"},
        }
    ]
    intent = {
        "kind": kind,
        "semantic_needs": ["sizing_amount"],
        "requested_fields": ["capital_amount"],
        "options": options,
    }
    calls = []

    async def writer(**kwargs):
        calls.append(kwargs)
        if fallback and len(calls) == 1:
            return None
        return ClarificationResponse(
            question=faker.sentence(),
            question_targets=["sizing_amount"],
            directly_asks_user=True,
        )

    monkeypatch.setattr(llm_clarifier, "invoke_openrouter_json_schema", writer)
    monkeypatch.setattr(
        llm_clarifier,
        "resolve_openrouter_model",
        lambda **kw: "fallback" if kw.get("fallback") else "primary",
    )
    result = await _generate_clarifying_question_result(
        state=state,
        response_intent=intent,
        missing_required_fields=["capital_amount"],
        ambiguous_fields=[],
        unsupported_constraints=[],
        optional_parameter_choices=[],
        clarification_generator=llm_clarifier.OpenRouterClarificationGenerator(),
        language=language,
    )

    assert not result.used_degraded_fallback
    assert len(calls) == (2 if fallback else 1)
    for call in calls:
        messages = call["messages"]
        assert old_reason not in json.dumps(messages)
        assert old_question not in json.dumps(messages)
        assert [m for m in messages if m["role"] == "user"] == [
            {"role": "user", "content": current_message}
        ]
        context = json.loads(messages[1]["content"])
        assert context["language"] == language
        assert context["response_intent"] == intent
        assert context["missing_required_fields"] == ["capital_amount"]
    # History is still available to interpretation and durable conversation.
    assert len(state.recent_thread_history) == 2


@pytest.mark.asyncio
async def test_supplied_date_to_capital_recovery_replay(monkeypatch):
    """Replay the two supplied user messages and the intervening wrong reply.

    This replays the reported stored blockers, not today's capital validation:
    integration now accepts $100. The unspecified middle user turn is not invented.
    """
    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )
    from argus.agent_runtime.stages.clarify import clarify_stage_async
    from argus.domain.backtesting.config import MAX_STARTING_CAPITAL, MIN_STARTING_CAPITAL

    date_question = (
        "August 16 to 19, 2026 is in the future. Which historical dates should I use?"
    )
    capital_question = "What starting capital amount in the supported range should I use?"
    prompts = [
        "Test $100 bucks on @mrna stock from August 16 to August 19 just a few days this year",
        "August 16, 2026 to August 19, 2026",
    ]
    requests = []

    async def writer(**kwargs):
        messages = kwargs["messages"]
        context = json.loads(messages[1]["content"])
        requests.append(context)
        # Script the observed anchoring failure if a prior answer is supplied.
        prior = [m["content"] for m in messages if m["role"] == "assistant"]
        reason = context["unsupported_constraints"][0]["category"]
        return ClarificationResponse(
            question=prior[-1]
            if prior
            else capital_question
            if reason == "unsupported_starting_capital"
            else date_question,
            question_targets=["simplification_choice"],
            directly_asks_user=True,
        )

    async def no_history_start(*args, **kwargs):
        return {}

    monkeypatch.setattr(llm_clarifier, "invoke_openrouter_json_schema", writer)
    monkeypatch.setattr(
        "argus.agent_runtime.stages.clarify._asset_history_starts", no_history_start
    )
    history = []
    for index, (prompt, category, requested) in enumerate(
        zip(
            prompts,
            ["data_window_unavailable", "unsupported_starting_capital"],
            ["date_range", "capital_amount"],
            strict=True,
        )
    ):
        option = {
            "id": f"change_{requested}",
            "label": "Choose another value",
            "replacement_values": {"requested_field": requested},
        }
        constraint = {"category": category, "simplification_options": [option]}
        if requested == "capital_amount":
            constraint.update(minimum=MIN_STARTING_CAPITAL, maximum=MAX_STARTING_CAPITAL)
        state = RunState.new(current_user_message=prompt, recent_thread_history=history)
        state.candidate_strategy_draft = StrategySummary(
            strategy_type="buy_and_hold",
            asset_class="equity",
            asset_universe=["MRNA"],
            capital_amount=100,
            date_range={
                "start": "2026-08-16",
                "end": "2026-12-31" if index == 0 else "2026-08-19",
            },
        )
        state.optional_parameter_status = {"unsupported_constraints": [constraint]}
        state.requested_field = requested
        result = await clarify_stage_async(
            state=state,
            contract=build_default_capability_contract(),
            clarification_generator=llm_clarifier.OpenRouterClarificationGenerator(),
        )
        patch = result.patch
        assert patch["clarification"]["reason_code"] == category
        assert patch["assistant_prompt"] == (
            date_question if index == 0 else capital_question
        )
        assert patch["clarification"]["options"][0]["replacement_values"] == option["replacement_values"]
        assert (
            requests[-1]["response_intent"]["options"]
            == patch["response_intent"]["options"]
        )
        assert requests[-1]["unsupported_constraints"][0]["category"] == category
        history.extend(
            [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": patch["assistant_prompt"]},
            ]
        )
