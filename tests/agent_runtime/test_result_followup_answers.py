"""Answers about the latest result are written by the model; Argus keeps the
Try next rows, the returned sources, the Agent's invoice and the offered
questions typed, on every follow-up path, in both workspace languages. A turn
no model answered is the retryable recovery, still carrying the rows."""

from __future__ import annotations

from typing import Any

import pytest
from argus.agent_runtime import result_followup_answers as answers_module
from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.next_experiments import (
    NEXT_EXPERIMENTS_ROW_CAP,
    NEXT_EXPERIMENTS_VERSION,
)
from argus.agent_runtime.profile.response_profile import (
    resolve_effective_response_profile,
)
from argus.agent_runtime.response_style import result_followup_response_intent
from argus.agent_runtime.result_conversation import ResultConversationAnswer
from argus.agent_runtime.result_followup_answers import (
    SUGGESTED_QUESTIONS_VERSION,
    answered_result_followup_patch,
    ordered_next_experiments,
    result_next_experiments,
    unavailable_result_followup_patch,
)
from argus.agent_runtime.runtime import run_agent_turn
from argus.agent_runtime.stages import interpret as interpret_module
from argus.agent_runtime.stages import interpret_actions as interpret_actions_module
from argus.agent_runtime.stages.interpret_types import (
    InterpretDecision,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import (
    ArtifactReference,
    ConversationMessage,
    StrategySummary,
    TaskSnapshot,
    UserState,
)
from argus.domain.engine_launch.result_facts import structured_next_experiments
from argus.domain.research.contracts import ResearchSource, ResearchUsage
from faker import Faker
from langgraph.checkpoint.memory import MemorySaver

LANGUAGES = ("en", "es-419")
RECOVERY_CODE = "latest_result_followup_unavailable"
# One completed run per supported family; the rows must come from the family
# that actually ran, never from the oldest shape.
FAMILY_CONFIGS: dict[str, dict[str, Any]] = {
    "buy_and_hold": {"symbols": ["AAPL"], "initial_capital": 1000},
    "dca_accumulation": {
        "symbols": ["COST"],
        "initial_capital": 1000,
        "cadence": "monthly",
        "recurring_contribution": 500,
    },
    "indicator_threshold": {
        "symbols": ["TSLA"],
        "initial_capital": 1000,
        "resolved_parameters": {
            "indicator": "rsi",
            "indicator_period": 14,
            "entry_threshold": 30,
            "exit_threshold": 70,
        },
    },
}
fake = Faker()


def _result_metadata(template: str) -> dict[str, Any]:
    config = dict(FAMILY_CONFIGS[template])
    return {
        "run_id": f"run-{template}",
        "asset_class": "equity",
        "symbols": list(config["symbols"]),
        "benchmark_symbol": "SPY",
        "config_snapshot": {
            "template": template,
            "date_range": {"start": "2024-01-02", "end": "2024-12-31"},
            **config,
        },
        "metrics": {
            "aggregate": {
                "performance": {
                    "total_return_pct": 30.7,
                    "benchmark_return_pct": 24.9,
                    "delta_vs_benchmark_pct": 5.8,
                }
            }
        },
    }


def _snapshot(template: str) -> TaskSnapshot:
    return TaskSnapshot(
        latest_task_type="results_explanation",
        completed=True,
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id=f"run-{template}",
            artifact_status="completed",
            metadata=_result_metadata(template),
        ),
    )


def _decision(user: UserState, *, focus: str) -> InterpretDecision:
    return InterpretDecision(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks about the latest result.",
        candidate_strategy_draft=StrategySummary(),
        confidence=0.9,
        reason_codes=["llm_interpreter_used"],
        effective_response_profile=resolve_effective_response_profile(
            user=user,
            explicit_overrides=None,
        ),
        semantic_turn_act="result_followup",
        result_followup_focus=focus,
        artifact_target="latest_result",
    )


def _researched_answer(**changes: Any) -> ResultConversationAnswer:
    values: dict[str, Any] = {
        "text": fake.paragraph(),
        "source": "research_agent",
        "suggested_questions": (fake.sentence() + "?", fake.sentence() + "?"),
        "sources": (
            ResearchSource(url=f"https://{fake.domain_name()}/story", title=fake.sentence()),
        ),
        "research_usage": ResearchUsage(
            model="openai/gpt-5.6-luna", cost_usd=0.012, web_search_invocations=1
        ),
    }
    values.update(changes)
    return ResultConversationAnswer(**values)


class _RecordingComposer:
    def __init__(self, answer: ResultConversationAnswer) -> None:
        self.answer = answer
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> ResultConversationAnswer:
        self.calls.append(kwargs)
        return self.answer


def _install(
    monkeypatch: pytest.MonkeyPatch, answer: ResultConversationAnswer
) -> _RecordingComposer:
    composer = _RecordingComposer(answer)
    monkeypatch.setattr(answers_module, "compose_result_conversation_answer", composer)
    return composer


def _offered_kinds(template: str, language: str) -> list[str]:
    sidecar = result_next_experiments(
        _result_metadata(template), language=language, source_run_id=None
    )
    assert sidecar is not None
    return [row["kind"] for row in sidecar["rows"]]


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("template", sorted(FAMILY_CONFIGS))
async def test_what_next_is_the_models_plan_with_the_results_rows_in_its_order(
    monkeypatch: pytest.MonkeyPatch, template: str, language: str
) -> None:
    recommended = list(reversed(_offered_kinds(template, language)))
    answer = _researched_answer(next_test_order=tuple(recommended))
    composer = _install(monkeypatch, answer)

    patch = await answered_result_followup_patch(
        metadata=_result_metadata(template),
        focus="next_experiment",
        user_message="ok what should I try next?",
        language=language,
        source_run_id=f"run-{template}",
    )

    assert patch["assistant_response"] == answer.text
    # The Try next section is the heading; no result chrome above the plan.
    assert "response_intent" not in patch
    assert "recovery" not in patch
    sidecar = patch["next_experiments"]
    assert sidecar["version"] == NEXT_EXPERIMENTS_VERSION
    assert sidecar["source_run_id"] == f"run-{template}"
    assert [row["kind"] for row in sidecar["rows"]] == recommended
    assert 1 <= len(sidecar["rows"]) <= NEXT_EXPERIMENTS_ROW_CAP
    supported = {
        option["kind"]
        for option in structured_next_experiments(_result_metadata(template))
    }
    assert {row["kind"] for row in sidecar["rows"]} <= supported
    # The model was told exactly the tests the rows offer, in the reader's language.
    call = composer.calls[0]
    assert [row["kind"] for row in call["next_test_rows"]] == _offered_kinds(
        template, language
    )
    assert call["language"] == language
    assert patch["suggested_questions"] == {
        "version": SUGGESTED_QUESTIONS_VERSION,
        "questions": list(answer.suggested_questions),
    }
    research = patch["research"]
    assert research["sources"][0]["url"] == answer.sources[0].url
    assert research["usage"]["cost_usd"] == answer.research_usage.cost_usd
    assert "degraded" not in research


@pytest.mark.asyncio
@pytest.mark.parametrize("focus", ["why_underperformed", "general", "what_tested"])
async def test_a_question_about_the_result_wears_its_heading_and_offers_no_rows(
    monkeypatch: pytest.MonkeyPatch, focus: str
) -> None:
    answer = _researched_answer()
    _install(monkeypatch, answer)

    patch = await answered_result_followup_patch(
        metadata=_result_metadata("buy_and_hold"),
        focus=focus,
        user_message=fake.sentence(),
        language="en",
    )

    assert patch["assistant_response"] == answer.text
    assert patch["response_intent"] == result_followup_response_intent(focus)
    assert "next_experiments" not in patch


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGUAGES)
async def test_an_unanswered_turn_is_the_recovery_with_rows_and_the_paid_invoice(
    monkeypatch: pytest.MonkeyPatch, language: str
) -> None:
    unanswered = ResultConversationAnswer(
        text=None,
        failure_mode="chat_model_unavailable",
        research_usage=ResearchUsage(model="openai/gpt-5.6-luna", cost_usd=0.004),
    )
    _install(monkeypatch, unanswered)

    patch = await answered_result_followup_patch(
        metadata=_result_metadata("dca_accumulation"),
        focus="next_experiment",
        user_message=fake.sentence(),
        language=language,
        source_run_id="run-dca_accumulation",
    )

    recovery = unavailable_result_followup_patch(language=language)
    assert patch["assistant_response"] == recovery["assistant_response"]
    assert patch["recovery"] == {"code": RECOVERY_CODE, "retryable": True}
    # Failure prose never wears result chrome (issue #249); the rows stay actions.
    assert "response_intent" not in patch
    assert patch["next_experiments"]["rows"]
    assert patch["research"]["degraded"] == {"code": "result_followup_research_unused"}
    assert patch["research"]["sources"] == []
    assert patch["research"]["usage"]["cost_usd"] == 0.004
    assert "suggested_questions" not in patch


@pytest.mark.asyncio
async def test_an_answer_without_search_carries_no_research_sidecar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answer = _researched_answer(source="chat_model", sources=(), research_usage=None)
    _install(monkeypatch, answer)

    patch = await answered_result_followup_patch(
        metadata=_result_metadata("buy_and_hold"),
        focus="general",
        user_message=fake.sentence(),
        language="en",
    )

    assert "research" not in patch
    assert patch["suggested_questions"]["questions"] == list(answer.suggested_questions)


def test_rows_follow_the_answers_order_and_unranked_rows_keep_theirs_after() -> None:
    sidecar = {"version": NEXT_EXPERIMENTS_VERSION, "rows": [{"kind": k} for k in "abcd"]}

    assert [row["kind"] for row in ordered_next_experiments(sidecar, ["c", "a"])["rows"]] == [
        "c",
        "a",
        "b",
        "d",
    ]
    assert ordered_next_experiments(sidecar, [])["rows"] == sidecar["rows"]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["action", "recovery", "interpreter_unavailable"])
async def test_every_follow_up_path_answers_from_the_conversation(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    composer = _install(monkeypatch, _researched_answer())
    user = UserState(user_id=fake.uuid4(), language_preference="es-419")
    history = [
        ConversationMessage(role="user", content=fake.sentence()),
        ConversationMessage(role="assistant", content=fake.paragraph()),
    ]
    message = "¿por qué quedó por debajo?"
    if path == "action":
        result = await interpret_actions_module.artifact_followup_stage_result_if_applicable(
            decision=_decision(user, focus="why_underperformed"),
            snapshot=_snapshot("buy_and_hold"),
            current_user_message=message,
            language=user.language_preference,
            recent_messages=history,
        )
    elif path == "recovery":
        result = await interpret_module._latest_result_followup_recovery_if_applicable(
            user=user,
            snapshot=_snapshot("buy_and_hold"),
            current_user_message=message,
            decision=_decision(user, focus="why_underperformed"),
            assistant_response=None,
            recent_messages=history,
        )
    else:
        result = await interpret_module._latest_result_followup_when_interpreter_unavailable(
            user=user,
            snapshot=_snapshot("buy_and_hold"),
            current_user_message=message,
            recent_messages=history,
        )

    assert result is not None
    assert result.outcome == "ready_to_respond"
    assert result.decision.semantic_turn_act == "result_followup"
    assert composer.calls[0]["recent_messages"] == history
    assert composer.calls[0]["user_message"] == message
    assert composer.calls[0]["language"] == "es-419"


class _StaticInterpreter:
    def __init__(self, response: StructuredInterpretation) -> None:
        self.response = response

    def __call__(self, request: Any) -> StructuredInterpretation:
        return self.response


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("language", "message"),
    [
        ("en", "ok what should I try next?"),
        ("es-419", "ok, ¿qué debería probar después?"),
    ],
)
async def test_full_turn_carries_the_plan_rows_sources_and_questions(
    monkeypatch: pytest.MonkeyPatch, language: str, message: str
) -> None:
    """A buy-and-hold result explained, then the what-next ask. The reference
    carries only the config snapshot, as the persisted reference does when the
    follow-up turn is hydrated."""

    answer = _researched_answer()
    composer = _install(monkeypatch, answer)
    reference = ArtifactReference(
        artifact_kind="backtest_result",
        artifact_id="eval-run-244-next",
        artifact_status="completed",
        metadata={
            "run_id": "eval-run-244-next",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "benchmark_symbol": "SPY",
            "config_snapshot": {
                "template": "buy_and_hold",
                "symbols": ["AAPL"],
                "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
            },
        },
    )
    workflow = build_workflow(
        structured_interpreter=_StaticInterpreter(
            StructuredInterpretation(
                intent="conversation_followup",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="User asks what to try next.",
                semantic_turn_act="result_followup",
                result_followup_focus="next_experiment",
                artifact_target="latest_result",
                confidence=0.9,
            )
        ),
        checkpointer=MemorySaver(),
    )
    history = [
        {"role": "user", "content": "What if I just bought and held Apple through 2024?"},
        {
            "role": "assistant",
            "content": "Here is your completed buy-and-hold result for AAPL over 2024.",
        },
    ]

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u-after-result", language_preference=language),
        thread_id=f"thread-after-result-{language}",
        message=message,
        recent_thread_history=history,
        fallback_latest_task_snapshot=TaskSnapshot(
            latest_task_type="results_explanation",
            completed=True,
            latest_backtest_result_reference=reference,
        ),
        fallback_selected_thread_metadata={
            "latest_task_type": "results_explanation",
            "last_stage_outcome": "ready_to_respond",
            # The first explanation already offered rows; an explicit ask
            # still gets the result's full offer.
            "next_experiments_offered_kinds": [
                "change_date_range",
                "same_setup_peer_asset",
                "recurring_monthly_buys",
            ],
        },
    )

    assert result["assistant_response"] == answer.text
    assert len(result["next_experiments"]["rows"]) >= 1
    assert result["next_experiments"]["source_run_id"] == "eval-run-244-next"
    assert result["suggested_questions"]["questions"] == list(answer.suggested_questions)
    assert result["research"]["sources"][0]["url"] == answer.sources[0].url
    assert [m.content for m in composer.calls[0]["recent_messages"]] == [
        turn["content"] for turn in history
    ]
    assert RECOVERY_CODE not in str(result)
    assert "result_followup_chrome" not in str(result)
