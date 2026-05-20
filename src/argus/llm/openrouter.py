from __future__ import annotations

import json
import os
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Literal, TypeVar

import httpx
from langchain_openrouter import ChatOpenRouter
from loguru import logger
from pydantic import BaseModel

OpenRouterTask = Literal[
    "interpretation",
    "clarification",
    "chat_composer",
    "result_summary",
    "result_breakdown",
    "name_suggestion",
]
OpenRouterModelTier = Literal["utility", "chat", "structured", "context"]

SchemaModelT = TypeVar("SchemaModelT", bound=BaseModel)


@dataclass(frozen=True)
class OpenRouterProfile:
    task: OpenRouterTask
    temperature: float
    max_tokens: int
    timeout_seconds: int = 12
    max_retries: int = 1


@dataclass(frozen=True)
class OpenRouterRouteReceipt:
    task: OpenRouterTask
    tier: OpenRouterModelTier
    model: str
    fallback_model: str
    mode: Literal["json_schema", "chat_model"]
    schema_name: str | None
    latency_ms: int
    outcome: Literal["succeeded", "failed", "skipped"]
    failure_mode: str | None = None
    fallback_used: bool = False
    created_at: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "task": self.task,
            "tier": self.tier,
            "model": self.model,
            "fallback_model": self.fallback_model,
            "mode": self.mode,
            "schema_name": self.schema_name,
            "latency_ms": self.latency_ms,
            "outcome": self.outcome,
            "failure_mode": self.failure_mode,
            "fallback_used": self.fallback_used,
            "created_at": self.created_at,
        }


_ROUTE_RECEIPTS: list[OpenRouterRouteReceipt] = []
_ROUTE_RECEIPTS_LOCK = Lock()
_ROUTE_RECEIPT_CAPTURE: ContextVar[list[OpenRouterRouteReceipt] | None] = ContextVar(
    "openrouter_route_receipt_capture",
    default=None,
)


OPENROUTER_PROFILES: dict[OpenRouterTask, OpenRouterProfile] = {
    "interpretation": OpenRouterProfile("interpretation", temperature=0, max_tokens=3200),
    "clarification": OpenRouterProfile("clarification", temperature=0, max_tokens=1200),
    "chat_composer": OpenRouterProfile("chat_composer", temperature=0.2, max_tokens=1200),
    "result_summary": OpenRouterProfile(
        "result_summary", temperature=0.2, max_tokens=1600
    ),
    "result_breakdown": OpenRouterProfile(
        "result_breakdown",
        temperature=0.2,
        max_tokens=2400,
        timeout_seconds=6,
        max_retries=0,
    ),
    "name_suggestion": OpenRouterProfile(
        "name_suggestion", temperature=0, max_tokens=400
    ),
}

OPENROUTER_TASK_MODEL_TIERS: dict[OpenRouterTask, OpenRouterModelTier] = {
    "interpretation": "structured",
    "clarification": "chat",
    "chat_composer": "chat",
    "result_summary": "chat",
    "result_breakdown": "context",
    "name_suggestion": "utility",
}

_TIER_PRIMARY_ENV: dict[OpenRouterModelTier, tuple[str, ...]] = {
    "utility": ("ARGUS_UTILITY_MODEL",),
    "chat": ("ARGUS_CHAT_MODEL",),
    "structured": ("ARGUS_STRUCTURED_MODEL",),
    "context": ("ARGUS_CONTEXT_MODEL",),
}

_TIER_FALLBACK_ENV: dict[OpenRouterModelTier, tuple[str, ...]] = {
    "utility": ("ARGUS_UTILITY_FALLBACK_MODEL",),
    "chat": ("ARGUS_CHAT_FALLBACK_MODEL",),
    "structured": ("ARGUS_STRUCTURED_FALLBACK_MODEL",),
    "context": ("ARGUS_CONTEXT_FALLBACK_MODEL",),
}

_TIER_CANDIDATE_ENV: dict[OpenRouterModelTier, tuple[str, ...]] = {
    "utility": (
        "ARGUS_UTILITY_MODEL",
        "ARGUS_UTILITY_FALLBACK_MODEL",
    ),
    "chat": (
        "ARGUS_CHAT_MODEL",
        "ARGUS_CHAT_FALLBACK_MODEL",
    ),
    "structured": (
        "ARGUS_STRUCTURED_MODEL",
        "ARGUS_STRUCTURED_FALLBACK_MODEL",
    ),
    "context": (
        "ARGUS_CONTEXT_MODEL",
        "ARGUS_CONTEXT_FALLBACK_MODEL",
    ),
}


def openrouter_model_tier_for_task(task: OpenRouterTask | None) -> OpenRouterModelTier:
    if task is None:
        return "chat"
    return OPENROUTER_TASK_MODEL_TIERS[task]


def resolve_openrouter_model(
    model_name: str | None = None,
    fallback: bool = False,
    *,
    task: OpenRouterTask | None = None,
) -> str:
    """
    Resolves the model name to use for the task-specific model tier.
    """
    if model_name:
        return model_name

    tier = openrouter_model_tier_for_task(task)
    env_names = _TIER_FALLBACK_ENV[tier] if fallback else _TIER_PRIMARY_ENV[tier]
    return _first_configured_model(env_names)


def resolve_openrouter_structured_model(
    model_name: str | None = None,
    *,
    task: OpenRouterTask = "interpretation",
) -> str:
    candidates = openrouter_structured_model_candidates(model_name, task=task)
    return candidates[0] if candidates else ""


def openrouter_structured_model_candidates(
    model_name: str | None = None,
    *,
    task: OpenRouterTask = "interpretation",
) -> list[str]:
    if model_name:
        return [model_name]
    tier = openrouter_model_tier_for_task(task)
    return _unique_nonempty(
        [_env_model_value(name) for name in _TIER_CANDIDATE_ENV[tier]]
    )


def _env_model_value(name: str) -> str:
    return os.getenv(name, "").strip()


def _first_configured_model(env_names: tuple[str, ...]) -> str:
    for name in env_names:
        value = _env_model_value(name)
        if value:
            return value
    return ""


def _unique_nonempty(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def build_openrouter_model(
    task: OpenRouterTask,
    *,
    model_name: str | None = None,
) -> ChatOpenRouter | None:
    """
    Builds a ChatOpenRouter instance for the given task.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("OpenRouter unavailable; missing API key", llm_task=task)
        return None

    profile = OPENROUTER_PROFILES[task]
    resolved_model = resolve_openrouter_model(model_name, task=task)
    if not resolved_model:
        logger.warning("OpenRouter unavailable; no model configured", llm_task=task)
        return None

    return ChatOpenRouter(
        model_name=resolved_model,
        temperature=profile.temperature,
        max_tokens=profile.max_tokens,
        timeout=profile.timeout_seconds,
        max_retries=profile.max_retries,
        openrouter_api_key=api_key,
    )


def openrouter_task_timeout_seconds(task: OpenRouterTask) -> float:
    return float(OPENROUTER_PROFILES[task].timeout_seconds)


def record_openrouter_route_receipt(
    *,
    task: OpenRouterTask,
    model_name: str | None,
    mode: Literal["json_schema", "chat_model"],
    schema_name: str | None,
    latency_ms: int,
    outcome: Literal["succeeded", "failed", "skipped"],
    failure_mode: str | None = None,
) -> OpenRouterRouteReceipt:
    tier = openrouter_model_tier_for_task(task)
    fallback_model = resolve_openrouter_model(fallback=True, task=task)
    resolved_model = resolve_openrouter_model(model_name, task=task)
    receipt = OpenRouterRouteReceipt(
        task=task,
        tier=tier,
        model=resolved_model,
        fallback_model=fallback_model,
        mode=mode,
        schema_name=schema_name,
        latency_ms=max(0, int(latency_ms)),
        outcome=outcome,
        failure_mode=failure_mode,
        fallback_used=bool(
            fallback_model and resolved_model == fallback_model and resolved_model != ""
        ),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    with _ROUTE_RECEIPTS_LOCK:
        _ROUTE_RECEIPTS.append(receipt)
    capture = _ROUTE_RECEIPT_CAPTURE.get()
    if capture is not None:
        capture.append(receipt)
    logger.bind(
        llm_task=task,
        llm_tier=tier,
        model=resolved_model,
        fallback_model=fallback_model,
        schema_name=schema_name,
        outcome=outcome,
        failure_mode=failure_mode,
        latency_ms=receipt.latency_ms,
        fallback_used=receipt.fallback_used,
    ).info("OpenRouter route receipt")
    return receipt


def get_openrouter_route_receipts() -> list[OpenRouterRouteReceipt]:
    with _ROUTE_RECEIPTS_LOCK:
        return list(_ROUTE_RECEIPTS)


def clear_openrouter_route_receipts() -> None:
    with _ROUTE_RECEIPTS_LOCK:
        _ROUTE_RECEIPTS.clear()


def begin_openrouter_route_receipt_capture() -> Token[list[OpenRouterRouteReceipt] | None]:
    return _ROUTE_RECEIPT_CAPTURE.set([])


def end_openrouter_route_receipt_capture(
    token: Token[list[OpenRouterRouteReceipt] | None],
) -> list[OpenRouterRouteReceipt]:
    receipts = list(_ROUTE_RECEIPT_CAPTURE.get() or [])
    _ROUTE_RECEIPT_CAPTURE.reset(token)
    return receipts


async def invoke_openrouter_json_schema(
    *,
    task: OpenRouterTask,
    messages: list[dict[str, str]],
    schema_model: type[SchemaModelT],
    schema_name: str,
    model_name: str | None = None,
) -> SchemaModelT | None:
    started_at = time.perf_counter()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("OpenRouter unavailable; missing API key", llm_task=task)
        record_openrouter_route_receipt(
            task=task,
            model_name=model_name,
            mode="json_schema",
            schema_name=schema_name,
            latency_ms=_elapsed_ms(started_at),
            outcome="skipped",
            failure_mode="missing_api_key",
        )
        return None

    resolved_model = resolve_openrouter_structured_model(model_name, task=task)
    if not resolved_model:
        logger.warning("OpenRouter unavailable; no model configured", llm_task=task)
        record_openrouter_route_receipt(
            task=task,
            model_name=model_name,
            mode="json_schema",
            schema_name=schema_name,
            latency_ms=_elapsed_ms(started_at),
            outcome="skipped",
            failure_mode="missing_model",
        )
        return None

    profile = OPENROUTER_PROFILES[task]
    payload = {
        "model": resolved_model,
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": schema_model.model_json_schema(),
            },
        },
        "temperature": profile.temperature,
        "max_tokens": profile.max_tokens,
    }
    _disable_reasoning_for_structured_artifact(payload)
    try:
        async with httpx.AsyncClient(timeout=profile.timeout_seconds) as client:
            response = await _post_openrouter_json_schema(
                client=client,
                api_key=api_key,
                payload=payload,
            )
        data = response.json()
        _raise_openrouter_payload_error(data)
        content = _openrouter_message_content(data)
        if not content:
            raise ValueError("OpenRouter JSON schema response did not include content")
        result = schema_model.model_validate_json(content)
    except Exception as exc:
        record_openrouter_route_receipt(
            task=task,
            model_name=resolved_model,
            mode="json_schema",
            schema_name=schema_name,
            latency_ms=_elapsed_ms(started_at),
            outcome="failed",
            failure_mode=type(exc).__name__,
        )
        raise
    record_openrouter_route_receipt(
        task=task,
        model_name=resolved_model,
        mode="json_schema",
        schema_name=schema_name,
        latency_ms=_elapsed_ms(started_at),
        outcome="succeeded",
    )
    return result


def invoke_openrouter_json_schema_sync(
    *,
    task: OpenRouterTask,
    messages: list[dict[str, str]],
    schema_model: type[SchemaModelT],
    schema_name: str,
    model_name: str | None = None,
) -> SchemaModelT | None:
    started_at = time.perf_counter()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("OpenRouter unavailable; missing API key", llm_task=task)
        record_openrouter_route_receipt(
            task=task,
            model_name=model_name,
            mode="json_schema",
            schema_name=schema_name,
            latency_ms=_elapsed_ms(started_at),
            outcome="skipped",
            failure_mode="missing_api_key",
        )
        return None

    resolved_model = resolve_openrouter_structured_model(model_name, task=task)
    if not resolved_model:
        logger.warning("OpenRouter unavailable; no model configured", llm_task=task)
        record_openrouter_route_receipt(
            task=task,
            model_name=model_name,
            mode="json_schema",
            schema_name=schema_name,
            latency_ms=_elapsed_ms(started_at),
            outcome="skipped",
            failure_mode="missing_model",
        )
        return None

    profile = OPENROUTER_PROFILES[task]
    payload = {
        "model": resolved_model,
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": schema_model.model_json_schema(),
            },
        },
        "temperature": profile.temperature,
        "max_tokens": profile.max_tokens,
    }
    _disable_reasoning_for_structured_artifact(payload)
    try:
        with httpx.Client(timeout=profile.timeout_seconds) as client:
            response = _post_openrouter_json_schema_sync(
                client=client,
                api_key=api_key,
                payload=payload,
            )
        data = response.json()
        _raise_openrouter_payload_error(data)
        content = _openrouter_message_content(data)
        if not content:
            raise ValueError("OpenRouter JSON schema response did not include content")
        result = schema_model.model_validate_json(content)
    except Exception as exc:
        record_openrouter_route_receipt(
            task=task,
            model_name=resolved_model,
            mode="json_schema",
            schema_name=schema_name,
            latency_ms=_elapsed_ms(started_at),
            outcome="failed",
            failure_mode=type(exc).__name__,
        )
        raise
    record_openrouter_route_receipt(
        task=task,
        model_name=resolved_model,
        mode="json_schema",
        schema_name=schema_name,
        latency_ms=_elapsed_ms(started_at),
        outcome="succeeded",
    )
    return result


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _disable_reasoning_for_structured_artifact(payload: dict[str, object]) -> None:
    payload["reasoning"] = {"effort": "none"}


async def _post_openrouter_json_schema(
    *,
    client: httpx.AsyncClient,
    api_key: str,
    payload: dict[str, object],
) -> httpx.Response:
    response = await client.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 400 or "reasoning" not in payload:
            raise
        fallback_payload = dict(payload)
        fallback_payload.pop("reasoning", None)
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=fallback_payload,
        )
        response.raise_for_status()
    return response


def _post_openrouter_json_schema_sync(
    *,
    client: httpx.Client,
    api_key: str,
    payload: dict[str, object],
) -> httpx.Response:
    response = client.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 400 or "reasoning" not in payload:
            raise
        fallback_payload = dict(payload)
        fallback_payload.pop("reasoning", None)
        response = client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=fallback_payload,
        )
        response.raise_for_status()
    return response


def _raise_openrouter_payload_error(data: dict[str, object]) -> None:
    error = data.get("error")
    if isinstance(error, dict):
        message = str(error.get("message") or "OpenRouter returned an error payload")
        code = error.get("code")
        raise ValueError(f"{message} code={code}")


def _openrouter_message_content(data: dict[str, object]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    if isinstance(content, dict):
        return json.dumps(content)
    return ""


def log_openrouter_failure(
    *,
    task: OpenRouterTask,
    model_name: str | None,
    exc: Exception,
    message: str,
) -> None:
    profile = OPENROUTER_PROFILES[task]
    resolved_model = resolve_openrouter_model(model_name, task=task)
    error_type = type(exc).__name__
    logger.warning(
        (
            f"{message} "
            f"task={task} model={resolved_model} "
            f"max_tokens={profile.max_tokens} error_type={error_type}"
        ),
        llm_task=task,
        model=resolved_model,
        max_tokens=profile.max_tokens,
        error_type=error_type,
        error=str(exc),
    )
