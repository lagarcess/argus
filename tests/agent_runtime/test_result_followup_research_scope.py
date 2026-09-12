"""A question the stored results answer never claims research, and a stored dollar
cost is answered from the run's typed fact sheet, in both workspace languages."""

from __future__ import annotations

import asyncio
from datetime import date
from functools import partial
from typing import Any

import pytest
from argus.agent_runtime import result_conversation as conversation
from argus.agent_runtime.result_followup_answers import answered_result_followup_patch
from argus.agent_runtime.stages.interpret_internal.latest_result_answer import (
    LatestResultFactComposerDeclined,
    latest_result_answer_stage_result_if_applicable,
)
from argus.agent_runtime.state.models import ArtifactReference, TaskSnapshot
from argus.domain.research.admission import research_attempt_admission_context

from tests.agent_runtime.test_latest_result_fact_answers import _decision
from tests.agent_runtime.test_result_conversation import _Agent, _ChatModel, _metadata
from tests.agent_runtime.test_result_fact_answer_guard import _Claims
from tests.agent_runtime.test_result_followup_answers import (
    QUESTIONS,
    _install,
    _researched_answer,
    _result_metadata,
)

LANGUAGES = ("en", "es-419")
LOCAL_QUESTIONS = {
    "en": "What should I try next?",
    "es-419": "¿Qué debería probar después?",
}
LOCAL_REPLIES = {
    "en": "Try a different date range next.",
    "es-419": "Prueba otro rango de fechas.",
}
FEE_QUESTIONS = {
    "en": "How many dollars did fees cost?",
    "es-419": "¿Cuántos dólares costaron las comisiones?",
}
FEE_REPLIES = {
    "en": "Fees cost $2.35 in this test.",
    "es-419": "Las comisiones costaron $2.35 en esta prueba.",
}
NOT_STORED_REPLIES = {
    "en": "This test does not store the fees in dollars.",
    "es-419": "Esta prueba no guarda las comisiones en dólares.",
}
FEES_IN_MONEY = "Modeled fees in money"


@pytest.fixture(autouse=True)
def _history_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "argus.domain.market_data.asset_history_start",
        lambda symbol, asset_class: date(2020, 1, 2),
    )


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize(
    ("focus", "research"),
    [
        ("what_tested", False),
        ("next_experiment", False),
        ("assumptions", False),
        ("general", True),
        ("why_underperformed", True),
    ],
)
def test_only_a_question_that_may_need_the_world_can_research(
    monkeypatch: pytest.MonkeyPatch, language: str, focus: str, research: bool
) -> None:
    composer = _install(monkeypatch, _researched_answer())

    asyncio.run(
        answered_result_followup_patch(
            metadata=_result_metadata("buy_and_hold"),
            focus=focus,
            user_message=QUESTIONS[language],
            language=language,
            source_run_id="run-buy_and_hold",
        )
    )

    assert composer.calls[0]["research"] is research


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_local_question_makes_no_research_call_and_claims_no_attempt(
    language: str,
) -> None:
    reply = {
        "language": language,
        "text": LOCAL_REPLIES[language],
        "figures": [],
        "next_steps": [],
    }
    agent = _Agent(draft=reply)
    chat = _ChatModel(reply)
    claims = _Claims()

    with research_attempt_admission_context(claims):
        answer = asyncio.run(
            conversation.compose_result_conversation_answer(
                metadata=_metadata(),
                user_message=LOCAL_QUESTIONS[language],
                language=language,
                client=agent,
                invoke_json_schema_func=chat,
                research=False,
            )
        )

    assert agent.calls == []
    assert claims.count == 0
    assert answer.text == reply["text"]


def _cost_snapshot(*, dollars: bool) -> TaskSnapshot:
    metadata = _metadata("dca_costs_test_only")
    if dollars:
        metadata["metrics"]["aggregate"]["performance"].setdefault(
            "execution_realism", {}
        ).update(
            modeled_fee_cost=2.35, modeled_slippage_cost=4.7, modeled_cost_total=7.05
        )
    return TaskSnapshot(
        latest_task_type="results_explanation",
        completed=True,
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-costs",
            artifact_status="completed",
            metadata=metadata,
        ),
    )


def _fee_answer(language: str, chat: _ChatModel, *, dollars: bool) -> Any:
    decision = _decision("result_card_fact").model_copy(
        update={
            "result_followup_fact_key": "modeled_fee_cost",
            "detected_user_language": language,
        }
    )
    return asyncio.run(
        latest_result_answer_stage_result_if_applicable(
            decision=decision,
            snapshot=_cost_snapshot(dollars=dollars),
            current_user_message=FEE_QUESTIONS[language],
            language=language,
            compose_response_func=partial(
                conversation.compose_result_conversation_answer,
                client=_Agent(),
                invoke_json_schema_func=chat,
            ),
        )
    )


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_stored_dollar_cost_is_answered_from_the_fact_sheet(language: str) -> None:
    chat = _ChatModel(
        {
            "language": language,
            "text": FEE_REPLIES[language],
            "figures": [{"fact_key": FEES_IN_MONEY, "value": 2.35}],
            "next_steps": [],
        }
    )

    result = _fee_answer(language, chat, dollars=True)

    assert not isinstance(result, LatestResultFactComposerDeclined)
    assert result.patch["assistant_response"] == FEE_REPLIES[language]
    assert result.patch["response_intent"]["kind"] == "beginner_guidance"
    assert result.patch["response_intent"]["facts"]["fact_key"] == "modeled_fee_cost"
    prompt = chat.calls[0]["messages"][1]["content"]
    assert "Stored value asked about:" in prompt
    assert f"{FEES_IN_MONEY}: " in prompt


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_run_stored_before_dollar_costs_says_not_stored(language: str) -> None:
    chat = _ChatModel(
        {
            "language": language,
            "text": NOT_STORED_REPLIES[language],
            "figures": [],
            "next_steps": [],
        }
    )

    result = _fee_answer(language, chat, dollars=False)

    assert result.patch["response_intent"]["kind"] == "unsupported_recovery"
    assert (
        result.patch["response_intent"]["facts"]["requested_metric"] == "modeled_fee_cost"
    )
