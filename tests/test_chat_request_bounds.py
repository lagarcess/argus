"""#235 — chat request bounds and unexpected-failure correlation."""

from __future__ import annotations

import pytest
from argus.api import state as api_state
from argus.api.main import app
from argus.api.schemas import ChatStreamRequest
from fastapi.testclient import TestClient
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def _memory_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    api_state.store.reset()


def _request(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "conversation_id": "conv-1",
        "message": "test AAPL",
    }
    payload.update(overrides)
    return payload


def test_exact_boundary_values_remain_valid() -> None:
    ChatStreamRequest.model_validate(
        _request(message="m" * 16_000, conversation_id="c" * 128)
    )
    ChatStreamRequest.model_validate(
        _request(
            message=None,
            action={
                "type": "run_backtest",
                "label": "l" * 120,
                "labelKey": "k" * 160,
                "payload": {"value": "s" * 4_096},
            },
        )
    )


@pytest.mark.parametrize(
    ("overrides", "rule"),
    [
        ({"message": "m" * 16_001}, "message_too_long"),
        ({"conversation_id": "c" * 129}, "conversation_id_too_long"),
        (
            {
                "mentions": [
                    {
                        "id": f"mention-{index}",
                        "type": "asset",
                        "label": "AAPL",
                        "insert_text": "AAPL",
                        "provider": "alpaca",
                    }
                    for index in range(11)
                ]
            },
            "too_many_mentions",
        ),
        (
            {
                "mentions": [
                    {
                        "id": "mention-1",
                        "type": "asset",
                        "label": "l" * 121,
                        "insert_text": "AAPL",
                        "provider": "alpaca",
                    }
                ]
            },
            "mention_label_too_long",
        ),
        (
            {
                "message": None,
                "action": {
                    "type": "run_backtest",
                    "label": "l" * 121,
                    "payload": {},
                },
            },
            "action_label_too_long",
        ),
        (
            {
                "message": None,
                "action": {
                    "type": "run_backtest",
                    "payload": {"value": "s" * 4_097},
                },
            },
            "action_payload_string_too_long",
        ),
        (
            {
                "message": None,
                "action": {
                    "type": "run_backtest",
                    "payload": {"a": {"b": {"c": {"d": {"e": {"f": {"g": 1}}}}}}},
                },
            },
            "action_payload_too_deep",
        ),
        (
            {
                "message": None,
                "action": {
                    "type": "run_backtest",
                    "payload": {f"key_{index}": index for index in range(51)},
                },
            },
            "action_payload_too_many_keys",
        ),
        (
            {
                "message": None,
                "action": {
                    "type": "run_backtest",
                    "payload": {"items": list(range(51))},
                },
            },
            "action_payload_too_many_items",
        ),
        (
            {
                "message": None,
                "action": {
                    "type": "run_backtest",
                    "payload": {f"key_{index}": "x" * 400 for index in range(45)},
                },
            },
            "action_payload_too_large",
        ),
    ],
)
def test_bound_violations_reject_with_named_rule(
    overrides: dict[str, object], rule: str
) -> None:
    with pytest.raises(ValidationError) as excinfo:
        ChatStreamRequest.model_validate(_request(**overrides))
    assert rule in str(excinfo.value)


def test_endpoint_returns_422_with_correlated_errors() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/chat/stream",
        json=_request(message="m" * 16_001),
        headers={"X-Request-Id": "corr-422"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["request_id"] == "corr-422"
    assert response.headers["X-Request-Id"] == "corr-422"
    assert "message_too_long" in str(body["context"]["errors"])


def test_oversized_body_rejects_413_before_parsing() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/chat/stream",
        content=b"x" * 70_000,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    body = response.json()
    assert body["code"] == "request_body_too_large"
    assert body["request_id"]
    assert response.headers["X-Request-Id"]


def test_declared_content_length_above_ceiling_rejects_immediately() -> None:
    import anyio
    from argus.api.chat_request_bounds import ChatStreamBodyLimitMiddleware

    sent: list[dict[str, object]] = []

    async def inner_app(scope, receive, send):  # pragma: no cover - must not run
        raise AssertionError("request must reject before reaching the app")

    middleware = ChatStreamBodyLimitMiddleware(inner_app)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/chat/stream",
        "headers": [
            (b"content-length", b"70000"),
            (b"x-request-id", b"corr-413"),
        ],
    }

    async def receive():  # pragma: no cover - must not be awaited
        raise AssertionError("body must not be read for a declared overage")

    async def send(message):
        sent.append(message)

    anyio.run(middleware, scope, receive, send)

    start = sent[0]
    assert start["status"] == 413
    headers = dict(start["headers"])
    assert headers[b"x-request-id"] == b"corr-413"


def test_other_routes_bypass_the_chat_ingress_ceiling() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/feedback",
        json={"type": "general", "message": "fine"},
    )
    assert response.status_code != 413


def test_unexpected_exception_returns_safe_correlated_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ExplodingGateway:
        def list_history_rows(self, **kwargs: object) -> object:
            raise RuntimeError("secret provider detail must not leak")

    monkeypatch.setattr(api_state, "supabase_gateway", _ExplodingGateway())
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/v1/history", headers={"X-Request-Id": "corr-500"})

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "internal_error"
    assert body["request_id"] == "corr-500"
    assert "secret provider detail" not in response.text
    assert "Traceback" not in response.text
    assert response.headers["X-Request-Id"] == "corr-500"
