"""Single-call local planner boundary; never imports Argus production bootstrap."""

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from langsmith import utils as tracing_utils
from pydantic import SecretStr, ValidationError
from server.platform import chat_model
from server.platform.chat_contracts import PlannedTurn


@pytest.mark.asyncio
async def test_model_uses_only_explicit_local_settings_one_admission_and_no_tracing(
    monkeypatch,
):
    calls = []
    monkeypatch.setenv("OPENROUTER_API_KEY", "unrelated-key-must-not-be-used")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    settings = SimpleNamespace(
        api_key=SecretStr("local-test-only"),
        model="local-model",
        base_url="https://example.invalid/v1",
    )
    monkeypatch.setattr(chat_model, "_LLMSettings", lambda: settings)

    @asynccontextmanager
    async def admission(store, context):
        calls.append("admitted")
        try:
            yield
        finally:
            calls.append("released")

    monkeypatch.setattr(chat_model, "model_admission", admission)

    class FakeModel:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def with_structured_output(self, schema, method):
            assert schema is PlannedTurn and method == "json_schema"
            return self

        async def ainvoke(self, messages, config):
            assert tracing_utils.tracing_is_enabled() is False
            calls.append("invoked")
            return PlannedTurn.model_validate(
                {"plan": {"kind": "clarify", "question": "Which account?"}}
            )

    monkeypatch.setattr(chat_model, "ChatOpenRouter", FakeModel)
    result = await chat_model.LocalStructuredPlanner().plan(
        {"message": "any language"}, store=object(), context=object()
    )
    assert result.plan.kind == "clarify"
    kwargs = calls[0]
    assert kwargs["api_key"].get_secret_value() == "local-test-only"
    assert kwargs["base_url"] == settings.base_url
    assert kwargs["max_retries"] == 0 and kwargs["timeout"] == 10_000
    assert calls[1:] == ["admitted", "invoked", "released"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message", ["crear presupuesto", "delete everything", "预算", "show net worth"]
)
async def test_keyless_arbitrary_text_never_becomes_a_prepared_action(
    monkeypatch, message
):
    monkeypatch.setattr(
        chat_model,
        "_LLMSettings",
        lambda: SimpleNamespace(api_key=None, model=None, base_url=None),
    )

    def forbidden(**kwargs):
        pytest.fail("keyless text instantiated a provider")

    monkeypatch.setattr(chat_model, "ChatOpenRouter", forbidden)
    with pytest.raises(chat_model.ModelUnavailable):
        await chat_model.LocalStructuredPlanner().plan(
            {"message": message}, store=object(), context=object()
        )


def test_semantic_schema_cannot_confirm_or_execute_a_write():
    with pytest.raises(ValidationError):
        PlannedTurn.model_validate(
            {"plan": {"kind": "confirm", "proposal_id": "untrusted"}}
        )
