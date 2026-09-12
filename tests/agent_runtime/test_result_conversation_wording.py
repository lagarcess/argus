"""What an answer after a result may say: only what the stored results or a cited
source give, in plain words, in the reader's language."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from argus.agent_runtime import result_conversation as conversation

from tests.agent_runtime.test_result_conversation import (
    _ChatModel,
    _compose,
    _draft,
    _metadata,
)

LANGUAGES = ("en", "es-419")


@pytest.fixture(autouse=True)
def _history_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "argus.domain.market_data.asset_history_start",
        lambda symbol, asset_class: date(2021, 3, 24),
    )


def _request(language: str, **kwargs: Any) -> tuple[str, str]:
    chat = _ChatModel(_draft(language))
    _compose(
        _metadata(),
        language,
        invoke_json_schema_func=chat,
        client=None,
        **kwargs,
    )
    messages = chat.calls[0]["messages"]
    return messages[0]["content"], messages[1]["content"]


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("can_search", [True, False])
def test_an_answer_never_invents_what_the_stored_results_do_not_give(
    language: str, can_search: bool
) -> None:
    instructions = conversation.result_conversation_instructions(
        language=language, can_search=can_search
    )

    assert (
        "Never state or estimate a date, an order of events or a cause that the "
        "stored results or a cited source do not give." in instructions
    )
    assert "say plainly that this test does not store it" in instructions
    assert "never asking for a fact this test does not store" in instructions
    assert "A comparison states both figures or neither." in instructions
    assert "in Spanish say prueba and referencia" in instructions
    assert "never run facts" in instructions
    assert "run facts own" not in instructions


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_request_names_its_facts_in_plain_words(
    monkeypatch: pytest.MonkeyPatch, language: str
) -> None:
    monkeypatch.setattr(conversation, "perplexity_api_key", lambda: "")

    _, prompt = _request(language, unavailable_fact="drawdown_date")

    assert "Stored results:" in prompt
    assert "Run facts:" not in prompt
    assert "Not stored for this test" in prompt
