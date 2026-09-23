"""Exercise the installed LangChain/OpenRouter transport without external requests."""

import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr
from server.platform import chat_model


@pytest.fixture
def transport(monkeypatch):
    monkeypatch.setattr(chat_model, "_LLMSettings", lambda: SimpleNamespace(
        api_key=SecretStr("explicit-local-fixture"),
        model="fixture/model", base_url="https://fixture.invalid/api/v1",
    ))
    monkeypatch.setenv("OPENROUTER_API_KEY", "ambient-key-must-not-be-used")
    monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "ambient-private-attribution")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    admissions = []

    @asynccontextmanager
    async def admission(store, context):
        admissions.append("admitted")
        try:
            yield
        finally:
            admissions.append("released")

    monkeypatch.setattr(chat_model, "model_admission", admission)
    return admissions


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 500, 429])
async def test_actual_sdk_makes_one_request_and_closes_client(monkeypatch, transport, status):
    calls = []
    clients = []

    async def send(client, request, **kwargs):
        calls.append(request)
        clients.append(client)
        if len(calls) > 1:
            raise AssertionError("Unexpected second model request")
        response = {
            "id": "fixture-completion", "object": "chat.completion", "created": 1,
            "model": "fixture/model", "system_fingerprint": None,
            "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps({
                    "plan": {"kind": "clarify", "question": "Which account?"},
                }),
            }}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 12, "total_tokens": 32},
        } if status == 200 else {"error": {"message": "Fixture failure", "code": status}}
        return httpx.Response(status, json=response, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    planner = chat_model.LocalStructuredPlanner()
    if status == 200:
        result = await planner.plan({"message": "Which account?"}, store=object(), context=object())
        assert result.plan.kind == "clarify"
    else:
        with pytest.raises(chat_model.ModelUnavailable):
            await planner.plan({"message": "Which account?"}, store=object(), context=object())
    assert len(calls) == 1
    assert calls[0].url == "https://fixture.invalid/api/v1/chat/completions"
    assert calls[0].headers["authorization"] == "Bearer explicit-local-fixture"
    assert "ambient-private-attribution" not in str(calls[0].headers)
    payload = json.loads(calls[0].content)
    assert payload["model"] == "fixture/model"
    assert payload["response_format"]["type"] == "json_schema"
    assert all(client.is_closed for client in clients)
    assert transport == ["admitted", "released"]


@pytest.mark.asyncio
async def test_actual_sdk_timeout_is_not_retried(monkeypatch, transport):
    calls = []

    async def send(client, request, **kwargs):
        calls.append(client)
        if len(calls) > 1:
            raise AssertionError("Unexpected timeout retry")
        raise httpx.ReadTimeout("Fixture timeout", request=request)

    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    with pytest.raises(chat_model.ModelUnavailable):
        await chat_model.LocalStructuredPlanner().plan(
            {"message": "Any text"}, store=object(), context=object(),
        )
    assert len(calls) == 1
    assert calls[0].is_closed
    assert transport == ["admitted", "released"]
