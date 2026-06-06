from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from loguru import logger

TRUE_VALUES = {"1", "true", "yes", "on"}
SHADOW_JOB_SCHEMA_VERSION = "backtest_job_launch/v1"


@dataclass(frozen=True)
class BacktestJobShadowContext:
    user_id: str
    conversation_id: str
    request_message_id: str | None = None
    confirmation_message_id: str | None = None
    idempotency_key: str | None = None
    request_id: str | None = None
    chat_action: dict[str, Any] | None = None


_shadow_context: ContextVar[BacktestJobShadowContext | None] = ContextVar(
    "argus_backtest_job_shadow_context",
    default=None,
)


def backtest_jobs_shadow_enabled() -> bool:
    return (
        os.getenv("ARGUS_BACKTEST_JOBS_SHADOW_ENABLED", "").strip().lower()
        in TRUE_VALUES
    )


@contextmanager
def backtest_job_shadow_context(
    context: BacktestJobShadowContext | None,
) -> Iterator[None]:
    token = _shadow_context.set(context)
    try:
        yield
    finally:
        _shadow_context.reset(token)


def current_backtest_job_shadow_context() -> BacktestJobShadowContext | None:
    return _shadow_context.get()


def set_backtest_job_shadow_context(
    context: BacktestJobShadowContext | None,
) -> Token[BacktestJobShadowContext | None]:
    return _shadow_context.set(context)


def reset_backtest_job_shadow_context(
    token: Token[BacktestJobShadowContext | None],
) -> None:
    _shadow_context.reset(token)


def payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def shadow_launch_payload(
    *,
    payload: dict[str, Any],
    context: BacktestJobShadowContext,
) -> dict[str, Any]:
    launch_payload: dict[str, Any] = {
        "schema_version": SHADOW_JOB_SCHEMA_VERSION,
        "source": "chat_runtime",
        "request": _json_safe_payload(payload),
    }
    if context.chat_action is not None:
        launch_payload["chat_action"] = _json_safe_payload(context.chat_action)
    return launch_payload


def _json_safe_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(deepcopy(payload), sort_keys=True, default=str))


class ShadowBacktestJobTool:
    def __init__(
        self,
        *,
        delegate: Any,
        gateway_getter: Callable[[], Any | None],
        dev_memory_fallback_getter: Callable[[], bool],
    ) -> None:
        self._delegate = delegate
        self._gateway_getter = gateway_getter
        self._dev_memory_fallback_getter = dev_memory_fallback_getter

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._maybe_create_shadow_job(payload)
        return self._delegate.run(payload)

    def _maybe_create_shadow_job(self, payload: dict[str, Any]) -> None:
        if not backtest_jobs_shadow_enabled():
            return

        context = current_backtest_job_shadow_context()
        if context is None:
            logger.warning(
                "Backtest job shadow flag enabled without request context; skipping",
            )
            return

        try:
            gateway = self._gateway_getter()
            if gateway is None:
                raise RuntimeError(
                    "Supabase persistence is required for shadow backtest jobs."
                )
            payload_digest = payload_hash(payload)
            gateway.create_backtest_job(
                user_id=context.user_id,
                conversation_id=context.conversation_id,
                request_message_id=context.request_message_id,
                confirmation_message_id=context.confirmation_message_id,
                idempotency_key=context.idempotency_key,
                payload_hash=payload_digest,
                launch_payload=shadow_launch_payload(
                    payload=payload,
                    context=context,
                ),
                execution_metadata={
                    "shadow_mode": True,
                    "source": "api_chat",
                    "request_id": context.request_id,
                    "payload_hash": payload_digest,
                },
            )
        except Exception as exc:
            if not self._dev_memory_fallback_getter():
                raise
            logger.warning(
                "Shadow backtest job creation failed; continuing in-process execution",
                error=str(exc),
                user_id=context.user_id,
                conversation_id=context.conversation_id,
            )
