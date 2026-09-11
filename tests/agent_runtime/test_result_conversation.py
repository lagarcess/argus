"""The model writes every answer about a completed run; Argus supplies the
facts, checks only what it owns, and keeps the Agent's invoice whatever
happens to the draft."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from argus.agent_runtime import result_conversation as conversation
from argus.agent_runtime.result_followup_answers import result_next_experiments
from argus.api.schemas import BacktestRun
from argus.domain.backtest_message_projection import result_fact_bank
from argus.domain.research.admission import (
    ResearchAttemptAdmission,
    research_attempt_admission_context,
)
from argus.domain.research.contracts import (
    ResearchSource,
    ResearchUnavailableError,
    ResearchUsage,
)
from argus.domain.research.perplexity_agent import StructuredAgentResult
from argus.domain.result_readout_quotes import readout_figure_keys
from argus.domain.result_readout_research import RESULT_RESEARCH_MODEL
from faker import Faker

FIXTURES = Path(__file__).resolve().parents[1] / "evals" / "result_readout_fixtures.json"
LANGUAGES = ("en", "es-419")
fake = Faker()


def _metadata(case_id: str = "docn_buyhold_test_only") -> dict[str, Any]:
    cases = json.loads(FIXTURES.read_text())["cases"]
    run = next(case["run"] for case in cases if case["id"] == case_id)
    return result_fact_bank(BacktestRun.model_validate(run))


def _rows(metadata: dict[str, Any], language: str) -> list[dict[str, Any]]:
    sidecar = result_next_experiments(metadata, language=language, source_run_id=None)
    assert sidecar is not None
    return sidecar["rows"]


def _draft(language: str, **changes: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "language": language,
        "text": fake.paragraph(),
        "figures": [],
        "suggested_questions": [],
        "next_test_order": [],
    }
    values.update(changes)
    return values


def _usage(cost: float = 0.01) -> ResearchUsage:
    return ResearchUsage(model=RESULT_RESEARCH_MODEL, cost_usd=cost, web_search_invocations=1)


class _Agent:
    def __init__(self, *, draft: dict[str, Any] | None = None, error: Exception | None = None,
                 sources: tuple[ResearchSource, ...] = ()) -> None:
        self.draft, self.error, self.sources = draft, error, sources
        self.calls: list[dict[str, Any]] = []

    def run_structured(self, prompt: str, spec: Any, **kwargs: Any) -> StructuredAgentResult:
        self.calls.append({"prompt": prompt, "spec": spec, **kwargs})
        if self.error is not None:
            raise self.error
        return StructuredAgentResult(
            draft=self.draft or {},
            sources=self.sources,
            usage=_usage(),
            tool_results=(),
            provider_response_id="test",
        )


class _ChatModel:
    def __init__(self, draft: dict[str, Any] | None = None, *, fail: bool = False) -> None:
        self.draft, self.fail = draft, fail
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.fail:
            raise TimeoutError("test")
        return kwargs["schema_model"].model_validate(self.draft)


@pytest.fixture(autouse=True)
def _history_starts(monkeypatch: pytest.MonkeyPatch) -> dict[str, date]:
    starts = {"DOCN": date(2021, 3, 24)}
    monkeypatch.setattr(
        "argus.domain.market_data.asset_history_start",
        lambda symbol, asset_class: starts.get(symbol),
    )
    return starts


def _compose(metadata: dict[str, Any], language: str, **kwargs: Any) -> conversation.ResultConversationAnswer:
    return asyncio.run(
        conversation.compose_result_conversation_answer(
            metadata=metadata,
            user_message=kwargs.pop("user_message", "what should I try next?"),
            language=language,
            next_test_rows=_rows(metadata, language),
            **kwargs,
        )
    )


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_researched_answer_keeps_returned_links_clean_questions_and_the_order(
    language: str,
) -> None:
    metadata = _metadata()
    kinds = [row["kind"] for row in _rows(metadata, language)]
    returned = f"https://{fake.domain_name()}/results"
    invented = f"https://{fake.domain_name()}/made-up"
    question = fake.sentence()
    agent = _Agent(
        sources=(ResearchSource(url=returned, title=fake.sentence()),),
        draft=_draft(
            language,
            text=f"See [the results]({returned}) and [a rumor]({invented}).",
            suggested_questions=[f"{question}?", f"{question}?", "Why — really?", "x" * 200],
            next_test_order=[kinds[-1], kinds[0]],
        ),
    )

    answer = _compose(metadata, language, client=agent)

    assert answer.source == "research_agent"
    assert f"[the results]({returned})" in answer.text
    assert invented not in answer.text and "a rumor" in answer.text
    assert answer.suggested_questions == (f"{question}?", "Why, really?")
    assert answer.next_test_order == (kinds[-1], kinds[0])
    assert answer.research_usage == _usage()
    call = agent.calls[0]
    assert call["spec"].models == (RESULT_RESEARCH_MODEL,)
    assert call["spec"].timeout_seconds == conversation.RESEARCH_TIMEOUT_SECONDS
    schema = call["schema_model"].model_json_schema()
    assert set(schema["properties"]["next_test_order"]["items"]["enum"]) == set(kinds)


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_request_carries_each_assets_own_history_start_and_never_a_floor_year(
    language: str,
) -> None:
    metadata = _metadata()
    history = [
        {"role": "user", "content": "Buy and hold DOCN since September 2023"},
        {"role": "assistant", "content": fake.paragraph()},
    ]
    agent = _Agent(draft=_draft(language))

    _compose(metadata, language, client=agent, recent_messages=history)

    prompt = agent.calls[0]["prompt"]
    assert f"product_language: {language}" in prompt
    assert "DOCN: 2021-03-24" in prompt
    # The benchmark's start was not established, so it is not stated at all.
    assert "SPY: " not in prompt
    assert "2016" not in prompt
    assert "Reader: Buy and hold DOCN since September 2023" in prompt
    for row in _rows(metadata, language):
        assert f"{row['kind']}: " in prompt


def test_a_figure_that_contradicts_the_run_is_rewritten_without_search() -> None:
    metadata = _metadata()
    facts = conversation.run_headline_facts(metadata)
    label = readout_figure_keys(facts)[0]
    wrong = _draft("en", figures=[{"fact_key": label, "value": 9999}])
    agent = _Agent(draft=wrong)
    chat = _ChatModel(_draft("en", suggested_questions=["What held it back?"]))

    answer = _compose(metadata, "en", client=agent, invoke_json_schema_func=chat)

    assert answer.source == "chat_model"
    assert answer.text == chat.draft["text"]
    assert answer.research_usage == _usage()
    assert chat.calls[0]["task"] == "chat_composer"
    assert "cannot search the web" in chat.calls[0]["messages"][0]["content"]


def test_exhausted_research_capacity_answers_without_search_and_calls_no_agent() -> None:
    agent = _Agent(draft=_draft("en"))
    chat = _ChatModel(_draft("en"))

    with research_attempt_admission_context(lambda: ResearchAttemptAdmission(available=False)):
        answer = _compose(_metadata(), "en", client=agent, invoke_json_schema_func=chat)

    assert agent.calls == []
    assert answer.source == "chat_model"
    assert answer.research_usage is None
    assert answer.failure_mode == "research_capacity_exhausted"


def test_no_research_key_answers_without_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(conversation, "perplexity_api_key", lambda: "")
    chat = _ChatModel(_draft("es-419"))

    answer = _compose(_metadata(), "es-419", invoke_json_schema_func=chat)

    assert answer.source == "chat_model"
    assert answer.failure_mode == "research_not_configured"


def test_when_no_model_answers_the_invoice_survives_for_the_ledger() -> None:
    agent = _Agent(error=ResearchUnavailableError("timeout", "test", usage=_usage(0.002)))

    answer = _compose(_metadata(), "en", client=agent, invoke_json_schema_func=_ChatModel(fail=True))

    assert answer.text is None
    assert answer.research_usage == _usage(0.002)
    assert answer.failure_mode == "chat_model_unavailable"


def test_a_draft_in_the_wrong_language_is_not_shown() -> None:
    agent = _Agent(draft=_draft("es-419"))
    chat = _ChatModel(_draft("es-419"))

    answer = _compose(_metadata(), "en", client=agent, invoke_json_schema_func=chat)

    assert answer.text is None
    assert answer.failure_mode == "language_mismatch"
    assert answer.research_usage == _usage()
