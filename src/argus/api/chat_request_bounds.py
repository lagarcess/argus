"""#235 — approved chat request-size boundaries for POST /api/v1/chat/stream.

Field, list, payload-size, and depth rules reject with ``422
validation_error`` before quota, persistence, providers, or the interpreter.
The raw ingress byte ceiling is enforced separately by
``ChatStreamBodyLimitMiddleware`` before JSON parsing or auth. Exact
boundary-sized values remain valid.
"""

from __future__ import annotations

import json
from typing import Any

MAX_REQUEST_BODY_BYTES = 65_536
MAX_CONVERSATION_ID_CODE_POINTS = 128
MAX_MESSAGE_CODE_POINTS = 16_000
MAX_MENTIONS = 10
MAX_MENTION_ID_CODE_POINTS = 128
MAX_MENTION_LABEL_CODE_POINTS = 120
MAX_MENTION_SYMBOL_CODE_POINTS = 32
MAX_MENTION_DESCRIPTION_CODE_POINTS = 256
MAX_MENTION_INSERT_TEXT_CODE_POINTS = 64
MAX_MENTION_PROVIDER_CODE_POINTS = 64
MAX_ACTION_LABEL_CODE_POINTS = 120
MAX_ACTION_LABEL_KEY_CODE_POINTS = 160
MAX_ACTION_PAYLOAD_BYTES = 16_384
MAX_ACTION_PAYLOAD_DEPTH = 6
MAX_ACTION_PAYLOAD_KEYS = 50
MAX_ACTION_PAYLOAD_ITEMS = 50
MAX_ACTION_PAYLOAD_STRING_CODE_POINTS = 4_096


def _check_length(value: Any, maximum: int, rule: str) -> None:
    if isinstance(value, str) and len(value) > maximum:
        raise ValueError(rule)


def _payload_depth_and_shape(value: Any, depth: int) -> None:
    """Container depth: the top-level payload object is depth 1; each nested
    object or array adds 1; scalars add none."""

    if depth > MAX_ACTION_PAYLOAD_DEPTH:
        raise ValueError("action_payload_too_deep")
    if isinstance(value, dict):
        if len(value) > MAX_ACTION_PAYLOAD_KEYS:
            raise ValueError("action_payload_too_many_keys")
        for item in value.values():
            _check_scalar_string(item)
            if isinstance(item, (dict, list)):
                _payload_depth_and_shape(item, depth + 1)
        return
    if isinstance(value, list):
        if len(value) > MAX_ACTION_PAYLOAD_ITEMS:
            raise ValueError("action_payload_too_many_items")
        for item in value:
            _check_scalar_string(item)
            if isinstance(item, (dict, list)):
                _payload_depth_and_shape(item, depth + 1)


def _check_scalar_string(value: Any) -> None:
    if isinstance(value, str) and len(value) > MAX_ACTION_PAYLOAD_STRING_CODE_POINTS:
        raise ValueError("action_payload_string_too_long")


def validate_chat_stream_bounds(
    *,
    conversation_id: str,
    message: str | None,
    mentions: list[Any],
    action_label: str | None,
    action_label_key: str | None,
    action_payload: dict[str, Any] | None,
) -> None:
    _check_length(
        conversation_id, MAX_CONVERSATION_ID_CODE_POINTS, "conversation_id_too_long"
    )
    _check_length(message, MAX_MESSAGE_CODE_POINTS, "message_too_long")

    if len(mentions) > MAX_MENTIONS:
        raise ValueError("too_many_mentions")
    for mention in mentions:
        _check_length(
            getattr(mention, "id", None),
            MAX_MENTION_ID_CODE_POINTS,
            "mention_id_too_long",
        )
        _check_length(
            getattr(mention, "label", None),
            MAX_MENTION_LABEL_CODE_POINTS,
            "mention_label_too_long",
        )
        _check_length(
            getattr(mention, "symbol", None),
            MAX_MENTION_SYMBOL_CODE_POINTS,
            "mention_symbol_too_long",
        )
        _check_length(
            getattr(mention, "description", None),
            MAX_MENTION_DESCRIPTION_CODE_POINTS,
            "mention_description_too_long",
        )
        _check_length(
            getattr(mention, "insert_text", None),
            MAX_MENTION_INSERT_TEXT_CODE_POINTS,
            "mention_insert_text_too_long",
        )
        _check_length(
            getattr(mention, "provider", None),
            MAX_MENTION_PROVIDER_CODE_POINTS,
            "mention_provider_too_long",
        )

    _check_length(action_label, MAX_ACTION_LABEL_CODE_POINTS, "action_label_too_long")
    _check_length(
        action_label_key,
        MAX_ACTION_LABEL_KEY_CODE_POINTS,
        "action_label_key_too_long",
    )
    if action_payload is not None:
        encoded = json.dumps(
            action_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )
        if len(encoded.encode("utf-8")) > MAX_ACTION_PAYLOAD_BYTES:
            raise ValueError("action_payload_too_large")
        _payload_depth_and_shape(action_payload, 1)


class ChatStreamBodyLimitMiddleware:
    """Raw ingress ceiling for the chat stream: reject before JSON, auth,
    quota, persistence, providers, or the interpreter. A valid declared
    Content-Length above the ceiling rejects immediately; missing, invalid, or
    chunked lengths use the same cumulative received-byte counter."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if (
            scope.get("type") != "http"
            or scope.get("method") != "POST"
            or scope.get("path") != "/api/v1/chat/stream"
        ):
            await self.app(scope, receive, send)
            return

        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        declared = headers.get("content-length", "")
        if declared.isdigit() and int(declared) > MAX_REQUEST_BODY_BYTES:
            await self._reject(scope, send)
            return

        received = 0
        rejected = False

        async def bounded_receive() -> dict[str, Any]:
            nonlocal received, rejected
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body") or b"")
                if received > MAX_REQUEST_BODY_BYTES:
                    rejected = True
                    raise _BodyTooLarge()
            return message

        try:
            await self.app(scope, bounded_receive, send)
        except _BodyTooLarge:
            if rejected:
                await self._reject(scope, send)

    async def _reject(self, scope: Any, send: Any) -> None:
        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        request_id = headers.get("x-request-id") or _new_request_id()
        body = json.dumps(
            {
                "type": "https://api.argus.app/problems/request-body-too-large",
                "title": "Request Body Too Large",
                "status": 413,
                "detail": (
                    "The chat request body exceeds the 65,536-byte ingress " "ceiling."
                ),
                "code": "request_body_too_large",
                "request_id": request_id,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("latin-1")),
                    (b"x-request-id", request_id.encode("latin-1")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


class _BodyTooLarge(Exception):
    pass


def _new_request_id() -> str:
    from argus.api import state as api_state

    return api_state.store.new_id()
