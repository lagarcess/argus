"""A question the interpreter resolved to a stored run fact is answered from the run.

It makes no research call and claims no research attempt, and its reply is accepted
only when it declares the requested fact with a value the typed fact sheet holds.
A reply that does not is declined, logged, and the turn keeps the recovery.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from functools import partial
from typing import Any

import pytest
from argus.agent_runtime import result_conversation as conversation
from argus.agent_runtime import result_followup_answers as answers_module
from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.runtime import run_agent_turn
from argus.agent_runtime.stages.interpret_actions import (
    artifact_followup_stage_result_if_applicable,
)
from argus.agent_runtime.stages.interpret_internal import (
    latest_result_answer as latest_result_answer_module,
)
from argus.agent_runtime.stages.interpret_internal.latest_result_answer import (
    LatestResultFactComposerDeclined,
    latest_result_answer_stage_result_if_applicable,
)
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import TaskSnapshot, UserState
from argus.domain.research.admission import (
    ResearchAttemptAdmission,
    research_attempt_admission_context,
)
from langgraph.checkpoint.memory import MemorySaver
from loguru import logger as loguru_logger

from tests.agent_runtime.test_latest_result_fact_answers import (
    _decision,
    _snapshot,
    _StaticInterpreter,
)
from tests.agent_runtime.test_result_conversation import _Agent, _ChatModel

PEAK_DATE = "Highest portfolio value reached"
PEAK_VALUE = "Highest portfolio value"
CLOSE_TIME = "Time of a nominal equity close"
LOWEST_VALUE = "Lowest account balance at a recorded close, including deposits"
FACT_QUESTIONS = [
    pytest.param("en", "When did it peak?", id="english"),
    pytest.param("es-419", "¿Cuándo alcanzó su máximo?", id="spanish"),
]
WHY_QUESTIONS = [
    pytest.param("en", "Why did it fall so much?", id="english"),
    pytest.param("es-419", "¿Por qué cayó tanto?", id="spanish"),
]


class _Claims:
    """The API's atomic research claim, counted."""

    def __init__(self) -> None:
        self.count = 0

    def __call__(self) -> ResearchAttemptAdmission:
        self.count += 1
        return ResearchAttemptAdmission(available=True)


@pytest.fixture(autouse=True)
def _history_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "argus.domain.market_data.asset_history_start",
        lambda symbol, asset_class: date(2020, 1, 2),
    )


@contextmanager
def _logs() -> Iterator[list[str]]:
    lines: list[str] = []
    handler = loguru_logger.add(lambda message: lines.append(str(message)), level="INFO")
    try:
        yield lines
    finally:
        loguru_logger.remove(handler)


def _reply(language: str, figures: list[dict[str, Any]]) -> dict[str, Any]:
    text = (
        "Alcanzó su valor más alto el 9 de noviembre de 2021."
        if language.startswith("es")
        else "It reached its highest value on November 9, 2021."
    )
    return {"language": language, "text": text, "figures": figures, "next_steps": []}


def _composer(agent: _Agent, chat: _ChatModel) -> Any:
    return partial(
        conversation.compose_result_conversation_answer,
        client=agent,
        invoke_json_schema_func=chat,
    )


def _fact_answer(
    language: str, message: str, composer: Any, *, fact: str = "peak_date",
    snapshot: TaskSnapshot | None = None,
) -> Any:
    decision = _decision("result_card_fact").model_copy(
        update={"result_followup_fact_key": fact, "detected_user_language": language}
    )
    return asyncio.run(
        latest_result_answer_stage_result_if_applicable(
            decision=decision,
            snapshot=snapshot or _snapshot(),
            current_user_message=message,
            language=language,
            compose_response_func=composer,
        )
    )


@pytest.mark.parametrize(("language", "message"), FACT_QUESTIONS)
def test_a_stored_fact_question_makes_no_research_call_and_claims_no_attempt(
    language: str, message: str
) -> None:
    agent = _Agent(draft=_reply(language, []))
    chat = _ChatModel(_reply(language, [{"fact_key": PEAK_DATE, "value": "2021-11-09"}]))
    claims = _Claims()

    with research_attempt_admission_context(claims):
        result = _fact_answer(language, message, _composer(agent, chat))

    assert agent.calls == []
    assert claims.count == 0
    assert result.patch["assistant_response"] == chat.draft["text"]
    prompt = chat.calls[0]["messages"][1]["content"]
    assert f"{PEAK_DATE}:" in prompt
    assert f"{PEAK_VALUE}:" in prompt


@pytest.mark.parametrize(("language", "message"), WHY_QUESTIONS)
def test_a_question_that_needs_the_world_still_researches(
    monkeypatch: pytest.MonkeyPatch, language: str, message: str
) -> None:
    agent = _Agent(draft=_reply(language, []))
    chat = _ChatModel(fail=True)
    claims = _Claims()
    monkeypatch.setattr(
        answers_module, "compose_result_conversation_answer", _composer(agent, chat)
    )

    with research_attempt_admission_context(claims):
        result = asyncio.run(
            artifact_followup_stage_result_if_applicable(
                decision=_decision("general"),
                snapshot=_snapshot(),
                current_user_message=message,
                language=language,
            )
        )

    assert len(agent.calls) == 1
    assert claims.count == 1
    assert chat.calls == []
    assert result.patch["assistant_response"] == agent.draft["text"]


@pytest.mark.parametrize(("language", "message"), FACT_QUESTIONS)
@pytest.mark.parametrize(
    ("figures", "reason"),
    [
        ([{"fact_key": PEAK_DATE, "value": "2021-11-09"}], None),
        ([], "requested_fact_undeclared"),
        ([{"fact_key": PEAK_DATE, "value": "2021-11-10"}], "invalid_figure_reference"),
    ],
    ids=["declared", "omitted", "wrong_date"],
)
def test_a_fact_reply_is_accepted_only_when_it_declares_the_fact_correctly(
    language: str, message: str, figures: list[dict[str, Any]], reason: str | None
) -> None:
    chat = _ChatModel(_reply(language, figures))

    with _logs() as lines:
        result = _fact_answer(language, message, _composer(_Agent(), chat))

    declined = [line for line in lines if "Result fact reply declined" in line]
    if reason is None:
        assert result.patch["assistant_response"] == chat.draft["text"]
        assert declined == []
    else:
        assert isinstance(result, LatestResultFactComposerDeclined)
        assert result.fact_key == "peak_date"
        assert len(declined) == 1
        assert f"fact_key=peak_date reason={reason}" in declined[0]


def _lowest_snapshot(stored_lowest: float) -> TaskSnapshot:
    snapshot = _snapshot()
    reference = snapshot.latest_backtest_result_reference
    assert reference is not None
    performance = reference.metadata["metrics"]["aggregate"]["performance"]
    performance["portfolio_value_range"]["lowest_value"] = stored_lowest
    return snapshot


@pytest.mark.parametrize(("language", "message"), FACT_QUESTIONS)
def test_the_lowest_date_is_the_typed_close_at_the_stored_lowest_value(
    language: str, message: str
) -> None:
    chat = _ChatModel(_reply(language, [{"fact_key": CLOSE_TIME, "value": "2020-02-03"}]))

    result = _fact_answer(
        language,
        message,
        _composer(_Agent(), chat),
        fact="lowest_date",
        snapshot=_lowest_snapshot(10000.0),
    )

    assert result.patch["assistant_response"] == chat.draft["text"]
    prompt = chat.calls[0]["messages"][1]["content"]
    assert f"{CLOSE_TIME}:" in prompt
    assert f"{LOWEST_VALUE}:" in prompt


@pytest.mark.parametrize(("language", "message"), FACT_QUESTIONS)
def test_a_lowest_value_no_close_matches_is_not_stated_as_a_date(
    language: str, message: str
) -> None:
    chat = _ChatModel(_reply(language, []))

    result = _fact_answer(
        language,
        message,
        _composer(_Agent(), chat),
        fact="lowest_date",
        snapshot=_lowest_snapshot(9100.0),
    )

    assert result.patch["response_intent"]["kind"] == "unsupported_recovery"
    assert "latest_result_fact_limitation" in result.decision.reason_codes


@pytest.mark.parametrize(("language", "message"), FACT_QUESTIONS)
@pytest.mark.asyncio
async def test_a_declined_fact_reply_keeps_the_recovery_without_research(
    monkeypatch: pytest.MonkeyPatch, language: str, message: str
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    agent = _Agent(draft=_reply(language, []))
    chat = _ChatModel(_reply(language, []))
    claims = _Claims()
    composer = _composer(agent, chat)
    monkeypatch.setattr(
        latest_result_answer_module, "compose_result_conversation_answer", composer
    )
    monkeypatch.setattr(answers_module, "compose_result_conversation_answer", composer)

    async def no_edit_plan(**kwargs: object) -> None:
        return None

    monkeypatch.setattr(interpret_module, "plan_artifact_assumption_edit", no_edit_plan)
    interpreter = _StaticInterpreter(
        StructuredInterpretation(
            intent="results_explanation",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User asked when the result peaked.",
            semantic_turn_act="result_followup",
            result_followup_focus="peak_date",
            result_followup_fact_key="peak_date",
            artifact_target="latest_result",
            confidence=0.9,
        )
    )
    workflow = build_workflow(structured_interpreter=interpreter, checkpointer=MemorySaver())

    with research_attempt_admission_context(claims), _logs() as lines:
        result = await run_agent_turn(
            workflow=workflow,
            user=UserState(user_id="u1", language_preference=language),
            thread_id=f"thread-fact-guard-{language}",
            message=message,
            fallback_latest_task_snapshot=_snapshot(),
            fallback_selected_thread_metadata={
                "latest_task_type": "results_explanation",
                "last_stage_outcome": "ready_to_respond",
            },
        )

    assert agent.calls == []
    assert claims.count == 0
    assert len(chat.calls) == 1
    assert "latest_result_followup_unavailable" in str(result)
    assert any("reason=requested_fact_undeclared" in line for line in lines)
    assert any("kept the recovery fact_key=peak_date" in line for line in lines)


NAME_QUESTIONS = [
    pytest.param("en", "Which assets and benchmark did it use?", id="english"),
    pytest.param("es-419", "¿Qué activos y qué referencia usó?", id="spanish"),
]
TICKER_CASES = [
    pytest.param(["COST", "TGT"], "SPY", "equity", "symbols", "COST y TGT", None, id="assets"),
    pytest.param(["BTC/USD"], "BTC", "crypto", "symbols", "(BTC/USD)", None, id="crypto_pair"),
    pytest.param(
        ["EUR/USD"], "EUR/USD", "currency_pair", "benchmark_symbol", "EUR/USD", None,
        id="currency_pair_benchmark",
    ),
    pytest.param(["COST"], "SPY", "equity", "benchmark_symbol", "¿SPY?", None, id="punctuated"),
    pytest.param(
        ["COST", "TGT"], "SPY", "equity", "symbols", "COST", "requested_ticker_unstated",
        id="an_asset_missing",
    ),
    pytest.param(
        ["COST"], "SPY", "equity", "benchmark_symbol", "SPYG", "requested_ticker_unstated",
        id="not_a_whole_word",
    ),
    pytest.param(
        ["BTC/USD"], "BTC", "crypto", "symbols", "BTC", "requested_ticker_unstated",
        id="pair_shortened",
    ),
]


def _naming_reply(language: str, names: str) -> dict[str, Any]:
    text = (
        f"Esta prueba usó {names}." if language.startswith("es") else f"This test used {names}."
    )
    return {"language": language, "text": text, "figures": [], "next_steps": []}


def _named_snapshot(symbols: list[str], benchmark: str, asset_class: str) -> TaskSnapshot:
    snapshot = _snapshot()
    reference = snapshot.latest_backtest_result_reference
    assert reference is not None
    reference.metadata.update(
        {"symbols": symbols, "benchmark_symbol": benchmark, "asset_class": asset_class}
    )
    reference.metadata["config_snapshot"].update(
        {"symbols": symbols, "benchmark_symbol": benchmark}
    )
    return snapshot


@pytest.mark.parametrize(("language", "message"), NAME_QUESTIONS)
@pytest.mark.parametrize(
    ("symbols", "benchmark_ticker", "asset_class", "fact", "names", "reason"),
    TICKER_CASES,
)
def test_an_asset_or_benchmark_reply_must_name_each_stored_ticker(
    language: str,
    message: str,
    symbols: list[str],
    benchmark_ticker: str,
    asset_class: str,
    fact: str,
    names: str,
    reason: str | None,
) -> None:
    snapshot = _named_snapshot(symbols, benchmark_ticker, asset_class)
    reference = snapshot.latest_backtest_result_reference
    assert reference is not None
    # The tickers are checked in exactly the form the answer's facts give the model.
    given = conversation.run_headline_facts(dict(reference.metadata))
    assert (given["symbols"], given["benchmark_symbol"]) == (symbols, benchmark_ticker)
    chat = _ChatModel(_naming_reply(language, names))

    with _logs() as lines:
        result = _fact_answer(
            language, message, _composer(_Agent(), chat), fact=fact, snapshot=snapshot
        )

    declined = [line for line in lines if "Result fact reply declined" in line]
    if reason is None:
        assert result.patch["assistant_response"] == chat.draft["text"]
        assert declined == []
    else:
        assert isinstance(result, LatestResultFactComposerDeclined)
        assert len(declined) == 1
        assert f"fact_key={fact} reason={reason}" in declined[0]


@pytest.mark.parametrize(("language", "message"), NAME_QUESTIONS)
def test_a_strategy_reply_is_not_checked(language: str, message: str) -> None:
    chat = _ChatModel(_naming_reply(language, "una estrategia"))

    result = _fact_answer(language, message, _composer(_Agent(), chat), fact="strategy")

    assert result.patch["assistant_response"] == chat.draft["text"]
