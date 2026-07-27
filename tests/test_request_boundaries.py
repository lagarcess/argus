"""Contract tests for the chat request and unexpected-error boundaries (#235)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable
from typing import Any

import pytest
from argus.api import dependencies as api_dependencies
from argus.api.dependencies import current_user
from argus.api.main import app
from argus.api.routers import agent as agent_router
from fastapi import Request
from fastapi.testclient import TestClient
from loguru import logger

CHAT_STREAM_PATH = "/api/v1/chat/stream"
MAX_INGRESS_BYTES = 65_536


def _valid_chat_payload() -> dict[str, Any]:
    return {"conversation_id": "conversation-1", "message": "Test Apple"}


def _valid_mention() -> dict[str, Any]:
    return {
        "id": "asset-aapl",
        "type": "asset",
        "label": "Apple",
        "symbol": "AAPL",
        "description": "Apple Inc.",
        "insert_text": "AAPL",
        "provider": "fixture",
    }


def _valid_action() -> dict[str, Any]:
    return {
        "type": "show_breakdown",
        "label": "Show breakdown",
        "labelKey": "chat.action.show_breakdown",
        "payload": {"run_id": "run-1"},
        "presentation": "result",
    }


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _asgi_post(
    body_chunks: Iterable[bytes],
    *,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes, int]:
    """Send chunks directly to ASGI so no client can add Content-Length."""

    chunks = list(body_chunks)
    raw_headers = [(b"content-type", b"application/json")]
    for name, value in (headers or {}).items():
        raw_headers.append((name.lower().encode("latin-1"), value.encode("latin-1")))
    scope: dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": CHAT_STREAM_PATH,
        "raw_path": CHAT_STREAM_PATH.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": raw_headers,
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "state": {},
    }
    sent: list[dict[str, Any]] = []
    chunk_index = 0
    receive_calls = 0

    async def receive() -> dict[str, Any]:
        nonlocal chunk_index, receive_calls
        receive_calls += 1
        if chunk_index >= len(chunks):
            return {"type": "http.disconnect"}
        body = chunks[chunk_index]
        chunk_index += 1
        return {
            "type": "http.request",
            "body": body,
            "more_body": chunk_index < len(chunks),
        }

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    asyncio.run(app(scope, receive, send))
    start = next(message for message in sent if message["type"] == "http.response.start")
    response_headers = {
        name.decode("latin-1").lower(): value.decode("latin-1")
        for name, value in start["headers"]
    }
    response_body = b"".join(
        message.get("body", b"")
        for message in sent
        if message["type"] == "http.response.body"
    )
    return start["status"], response_headers, response_body, receive_calls


def _assert_request_too_large(
    status: int,
    headers: dict[str, str],
    body: bytes,
    *,
    request_id: str,
) -> None:
    assert status == 413
    payload = json.loads(body)
    assert payload["type"] == "https://api.argus.app/problems/request-body-too-large"
    assert payload["title"] == "Request Body Too Large"
    assert payload["status"] == 413
    assert payload["code"] == "request_body_too_large"
    assert payload["request_id"] == request_id
    assert headers["x-request-id"] == request_id


@pytest.fixture
def forbid_expensive_chat_owners(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Tripwires prove rejected bodies do not reach durable/runtime owners."""

    calls: list[str] = []

    async def forbidden_gateway(_request: Request) -> None:
        calls.append("gateway")
        raise AssertionError("gateway/auth must not run for a rejected chat request")

    def forbidden_owner(name: str):
        def _forbidden(*_args: Any, **_kwargs: Any) -> None:
            calls.append(name)
            raise AssertionError(f"{name} must not run for a rejected chat request")

        return _forbidden

    monkeypatch.setitem(app.dependency_overrides, current_user, forbidden_gateway)
    monkeypatch.setattr(agent_router, "check_message_allowance", forbidden_owner("quota"))
    monkeypatch.setattr(
        agent_router, "reconcile_stale_chat_turns", forbidden_owner("persistence")
    )
    monkeypatch.setattr(
        agent_router, "stream_agent_turn_events", forbidden_owner("interpreter")
    )
    monkeypatch.setattr(
        agent_router,
        "begin_openrouter_route_receipt_capture",
        forbidden_owner("provider"),
    )
    monkeypatch.setattr(
        agent_router.api_state,
        "get_agent_runtime_workflow",
        forbidden_owner("runtime"),
    )
    return calls


def test_declared_oversize_chat_request_is_rejected_without_reading_or_owner_work(
    forbid_expensive_chat_owners: list[str],
) -> None:
    request_id = "declared-oversize"
    oversized = _json_bytes(
        {"conversation_id": "conversation-1", "message": "x" * MAX_INGRESS_BYTES}
    )
    status, headers, body, receive_calls = _asgi_post(
        [oversized],
        headers={
            "Content-Length": str(len(oversized)),
            "X-Request-Id": request_id,
        },
    )

    _assert_request_too_large(status, headers, body, request_id=request_id)
    assert receive_calls == 0
    assert forbid_expensive_chat_owners == []


def test_chunked_oversize_chat_request_is_rejected_before_owner_work(
    forbid_expensive_chat_owners: list[str],
) -> None:
    request_id = "chunked-oversize"
    oversized = _json_bytes(
        {"conversation_id": "conversation-1", "message": "x" * MAX_INGRESS_BYTES}
    )
    status, headers, body, receive_calls = _asgi_post(
        [oversized[:20_000], oversized[20_000:40_000], oversized[40_000:]],
        headers={"X-Request-Id": request_id},
    )

    _assert_request_too_large(status, headers, body, request_id=request_id)
    assert receive_calls == 3
    assert forbid_expensive_chat_owners == []


@pytest.mark.parametrize(
    ("name", "payload"),
    [
        (
            "conversation id",
            {**_valid_chat_payload(), "conversation_id": "c" * 129},
        ),
        ("message", {**_valid_chat_payload(), "message": "m" * 16_001}),
        (
            "mention list",
            {**_valid_chat_payload(), "mentions": [_valid_mention() for _ in range(11)]},
        ),
        (
            "mention id",
            {
                **_valid_chat_payload(),
                "mentions": [{**_valid_mention(), "id": "i" * 129}],
            },
        ),
        (
            "mention label",
            {
                **_valid_chat_payload(),
                "mentions": [{**_valid_mention(), "label": "l" * 121}],
            },
        ),
        (
            "mention symbol",
            {
                **_valid_chat_payload(),
                "mentions": [{**_valid_mention(), "symbol": "s" * 33}],
            },
        ),
        (
            "mention description",
            {
                **_valid_chat_payload(),
                "mentions": [{**_valid_mention(), "description": "d" * 257}],
            },
        ),
        (
            "mention insert text",
            {
                **_valid_chat_payload(),
                "mentions": [{**_valid_mention(), "insert_text": "t" * 65}],
            },
        ),
        (
            "mention provider",
            {
                **_valid_chat_payload(),
                "mentions": [{**_valid_mention(), "provider": "p" * 65}],
            },
        ),
        (
            "action label",
            {**_valid_chat_payload(), "action": {**_valid_action(), "label": "a" * 121}},
        ),
        (
            "action label key",
            {
                **_valid_chat_payload(),
                "action": {**_valid_action(), "labelKey": "k" * 161},
            },
        ),
    ],
)
def test_chat_field_and_list_bounds_reject_before_expensive_owners(
    name: str,
    payload: dict[str, Any],
    forbid_expensive_chat_owners: list[str],
) -> None:
    response = TestClient(app, raise_server_exceptions=False).post(
        CHAT_STREAM_PATH,
        json=payload,
        headers={"X-Request-Id": f"invalid-{name.replace(' ', '-')}"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert response.headers["x-request-id"] == response.json()["request_id"]
    assert forbid_expensive_chat_owners == []


def _nested_payload(depth: int) -> dict[str, Any]:
    payload: dict[str, Any] = {"leaf": "value"}
    for _ in range(depth - 1):
        payload = {"nested": payload}
    return payload


@pytest.mark.parametrize(
    ("name", "action_payload"),
    [
        ("depth", _nested_payload(7)),
        ("object keys", {f"key_{index}": index for index in range(51)}),
        ("array items", {"items": list(range(51))}),
        ("string", {"value": "s" * 4097}),
        (
            "serialized size",
            {f"value_{index}": "v" * 4096 for index in range(5)},
        ),
    ],
)
def test_chat_structured_action_bounds_reject_before_expensive_owners(
    name: str,
    action_payload: dict[str, Any],
    forbid_expensive_chat_owners: list[str],
) -> None:
    response = TestClient(app, raise_server_exceptions=False).post(
        CHAT_STREAM_PATH,
        json={
            **_valid_chat_payload(),
            "action": {**_valid_action(), "payload": action_payload},
        },
        headers={"X-Request-Id": f"invalid-payload-{name.replace(' ', '-')}"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert response.headers["x-request-id"] == response.json()["request_id"]
    assert forbid_expensive_chat_owners == []


def test_exact_typed_boundaries_remain_valid() -> None:
    from argus.api.schemas import ChatStreamRequest

    exact_serialized_payload = {
        "p0": "x" * 4096,
        "p1": "x" * 4096,
        "p2": "x" * 4096,
        "p3": "x" * 4063,
    }
    assert len(_json_bytes(exact_serialized_payload)) == 16_384

    request = ChatStreamRequest.model_validate(
        {
            "conversation_id": "c" * 128,
            "message": "m" * 16_000,
            "mentions": [
                {
                    "id": "i" * 128,
                    "type": "asset",
                    "label": "l" * 120,
                    "symbol": "s" * 32,
                    "description": "d" * 256,
                    "insert_text": "t" * 64,
                    "provider": "p" * 64,
                }
                for _ in range(10)
            ],
            "action": {
                **_valid_action(),
                "label": "a" * 120,
                "labelKey": "k" * 160,
                "payload": exact_serialized_payload,
            },
        }
    )

    assert request.message == "m" * 16_000
    assert len(request.mentions) == 10

    payload_at_depth_and_container_limits = ChatStreamRequest.model_validate(
        {
            **_valid_chat_payload(),
            "action": {
                **_valid_action(),
                "payload": {
                    "nested": _nested_payload(5),
                    "items": list(range(50)),
                    **{f"key_{index}": index for index in range(48)},
                },
            },
        }
    )
    assert payload_at_depth_and_container_limits.action is not None


def test_exact_ingress_limit_remains_accepted_with_compatibly_ignored_padding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _events(**_kwargs: Any):
        yield {"type": "stage_start", "stage": "interpret"}
        yield {"type": "stage_outcome", "outcome": "ready_to_respond"}
        yield {"type": "token", "content": "ok"}
        yield {
            "type": "final",
            "payload": {"stage_outcome": "ready_to_respond", "assistant_response": "ok"},
        }

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _events)
    monkeypatch.setattr(
        agent_router, "schedule_artifact_naming_after_stream", lambda **_kwargs: None
    )
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]
    body = {"conversation_id": conversation["id"], "message": "hi", "padding": ""}
    body["padding"] = "x" * (MAX_INGRESS_BYTES - len(_json_bytes(body)))
    encoded = _json_bytes(body)
    assert len(encoded) == MAX_INGRESS_BYTES

    response = client.post(
        CHAT_STREAM_PATH,
        content=encoded,
        headers={"Content-Type": "application/json", "X-Request-Id": "exact-ingress"},
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "exact-ingress"
    assert [
        event["type"]
        for event in (
            json.loads(line.removeprefix("data: "))
            for line in response.text.splitlines()
            if line.startswith("data: {")
        )
    ] == ["stage_start", "stage_outcome", "token", "final"]
    assert response.text.rstrip().endswith("data: [DONE]")


def test_unexpected_error_is_generic_correlated_and_cors_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records: list[dict[str, Any]] = []

    async def _boom(_request: Request) -> None:
        raise RuntimeError("provider credential private failure detail")

    sink_id = logger.add(lambda message: records.append(message.record), level="ERROR")
    monkeypatch.setitem(app.dependency_overrides, current_user, _boom)
    try:
        response = TestClient(app, raise_server_exceptions=False).get(
            "/api/v1/me",
            headers={
                "Origin": "http://localhost:3000",
                "X-Request-Id": "unexpected-request-id",
            },
        )
    finally:
        logger.remove(sink_id)

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["x-request-id"] == "unexpected-request-id"
    assert response.json() == {
        "type": "https://api.argus.app/problems/internal-error",
        "title": "Internal Error",
        "status": 500,
        "detail": "An unexpected error occurred. Please try again.",
        "code": "internal_error",
        "request_id": "unexpected-request-id",
    }
    assert "private failure detail" not in response.text
    matching_records = [
        record
        for record in records
        if record["extra"].get("request_id") == "unexpected-request-id"
    ]
    assert len(matching_records) == 1
    assert "private failure detail" not in matching_records[0]["message"]


def test_unexpected_ingress_preflight_failure_is_generic_and_correlated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(_body: bytes) -> None:
        raise RuntimeError("preflight implementation detail")

    monkeypatch.setattr(api_dependencies, "_chat_stream_validation_errors", _boom)
    response = TestClient(app, raise_server_exceptions=False).post(
        CHAT_STREAM_PATH,
        json=_valid_chat_payload(),
        headers={
            "Origin": "http://localhost:3000",
            "X-Request-Id": "preflight-request-id",
        },
    )

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["x-request-id"] == "preflight-request-id"
    assert response.json()["request_id"] == "preflight-request-id"
    assert "preflight implementation detail" not in response.text


def test_existing_validation_and_http_errors_keep_their_problem_contract() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    validation = client.post(
        CHAT_STREAM_PATH,
        json={"conversation_id": "conversation-1"},
        headers={"X-Request-Id": "normal-validation"},
    )
    missing = client.get(
        "/api/v1/conversations/missing-conversation/messages",
        headers={"X-Request-Id": "normal-http-error"},
    )

    assert validation.status_code == 422
    assert validation.json()["code"] == "validation_error"
    assert validation.headers["x-request-id"] == "normal-validation"
    assert missing.status_code == 404
    assert missing.json()["code"] == "not_found"
    assert missing.headers["x-request-id"] == "normal-http-error"
