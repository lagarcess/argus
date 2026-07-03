from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Iterable
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Literal, TypeVar

import httpx
from dotenv import load_dotenv
from langchain_openrouter import ChatOpenRouter
from loguru import logger
from pydantic import BaseModel

load_dotenv()

OpenRouterTask = Literal[
    "interpretation",
    "interpretation_repair",
    "field_fidelity",
    "capability_conflict",
    "clarification",
    "chat_composer",
    "result_summary",
    "result_breakdown",
    "name_suggestion",
]
OpenRouterModelTier = Literal["utility", "chat", "structured", "context"]
OpenRouterReasoningEffort = Literal[
    "xhigh", "high", "medium", "low", "minimal", "none"
]

SchemaModelT = TypeVar("SchemaModelT", bound=BaseModel)


@dataclass(frozen=True)
class OpenRouterProfile:
    task: OpenRouterTask
    temperature: float
    max_tokens: int
    timeout_seconds: int = 12
    max_retries: int = 1
    reasoning_effort: OpenRouterReasoningEffort = "none"


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
    token_usage: dict[str, int] | None = None
    context_packet_ids: list[str] = field(default_factory=list)
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
            "token_usage": self.token_usage,
            "context_packet_ids": list(self.context_packet_ids),
            "created_at": self.created_at,
        }


_ROUTE_RECEIPTS: list[OpenRouterRouteReceipt] = []
_ROUTE_RECEIPTS_LOCK = Lock()
_ROUTE_RECEIPT_CAPTURE: ContextVar[list[OpenRouterRouteReceipt] | None] = ContextVar(
    "openrouter_route_receipt_capture",
    default=None,
)


OPENROUTER_PROFILES: dict[OpenRouterTask, OpenRouterProfile] = {
    "interpretation": OpenRouterProfile(
        "interpretation",
        temperature=0,
        max_tokens=3200,
        # 3200 tokens + structured + reasoning needs more than the 12s default (its peers
        # get 20-30s); proportionate bump so interpretation isn't the next timeout.
        timeout_seconds=20,
        reasoning_effort="medium",
    ),
    "interpretation_repair": OpenRouterProfile(
        "interpretation_repair",
        temperature=0,
        max_tokens=2200,
        timeout_seconds=20,
    ),
    "field_fidelity": OpenRouterProfile(
        "field_fidelity",
        temperature=0,
        max_tokens=900,
        timeout_seconds=20,
    ),
    "capability_conflict": OpenRouterProfile(
        "capability_conflict",
        temperature=0,
        max_tokens=700,
        timeout_seconds=15,
        reasoning_effort="medium",
    ),
    "clarification": OpenRouterProfile("clarification", temperature=0, max_tokens=360),
    "chat_composer": OpenRouterProfile(
        "chat_composer", temperature=0.2, max_tokens=1200, timeout_seconds=25
    ),
    "result_summary": OpenRouterProfile(
        "result_summary", temperature=0.2, max_tokens=700, timeout_seconds=30
    ),
    "result_breakdown": OpenRouterProfile(
        "result_breakdown",
        temperature=0.2,
        max_tokens=2400,
        timeout_seconds=25,
        max_retries=0,
    ),
    "name_suggestion": OpenRouterProfile(
        "name_suggestion", temperature=0, max_tokens=400
    ),
}

OPENROUTER_TASK_MODEL_TIERS: dict[OpenRouterTask, OpenRouterModelTier] = {
    "interpretation": "structured",
    "interpretation_repair": "structured",
    "field_fidelity": "structured",
    "capability_conflict": "context",
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
    candidates = openrouter_model_candidates(model_name, task=task)
    return candidates[0] if candidates else ""


def openrouter_model_candidates(
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


def openrouter_structured_model_candidates(
    model_name: str | None = None,
    *,
    task: OpenRouterTask = "interpretation",
) -> list[str]:
    return openrouter_model_candidates(model_name, task=task)


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

    profile = openrouter_profile_for_task(task)
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
    return float(openrouter_profile_for_task(task).timeout_seconds)


def openrouter_profile_for_task(task: OpenRouterTask) -> OpenRouterProfile:
    profile = OPENROUTER_PROFILES[task]
    timeout_override = _task_timeout_override_seconds(task)
    if timeout_override is None:
        return profile
    return OpenRouterProfile(
        task=profile.task,
        temperature=profile.temperature,
        max_tokens=profile.max_tokens,
        timeout_seconds=timeout_override,
        max_retries=profile.max_retries,
        reasoning_effort=profile.reasoning_effort,
    )


def _task_timeout_override_seconds(task: OpenRouterTask) -> int | None:
    raw_value = os.getenv(f"ARGUS_OPENROUTER_{task.upper()}_TIMEOUT_SECONDS", "")
    if not raw_value.strip():
        return None
    try:
        timeout_seconds = int(raw_value)
    except ValueError:
        logger.warning(
            "Ignoring invalid OpenRouter task timeout override",
            llm_task=task,
            timeout_env_value=raw_value,
        )
        return None
    if timeout_seconds <= 0:
        logger.warning(
            "Ignoring non-positive OpenRouter task timeout override",
            llm_task=task,
            timeout_env_value=raw_value,
        )
        return None
    return timeout_seconds


def record_openrouter_route_receipt(
    *,
    task: OpenRouterTask,
    model_name: str | None,
    mode: Literal["json_schema", "chat_model"],
    schema_name: str | None,
    latency_ms: int,
    outcome: Literal["succeeded", "failed", "skipped"],
    failure_mode: str | None = None,
    token_usage: dict[str, int] | None = None,
    context_packet_ids: list[str] | None = None,
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
        token_usage=normalize_openrouter_token_usage(token_usage),
        context_packet_ids=_normalized_context_packet_ids(context_packet_ids),
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
        token_usage=receipt.token_usage,
        context_packet_ids=receipt.context_packet_ids,
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


def summarize_openrouter_route_receipts(
    receipts: Iterable[OpenRouterRouteReceipt] | None = None,
) -> dict[str, object]:
    """
    Builds a small internal latency/failure waterfall from existing receipts.

    This is diagnostic only. It must not bypass semantic arbitration,
    capability validation, context replayability, or fallback observability.
    """

    active_receipts = list(receipts) if receipts is not None else get_openrouter_route_receipts()
    route_waterfall = [
        {
            "task": receipt.task,
            "tier": receipt.tier,
            "model": receipt.model,
            "fallback_model": receipt.fallback_model,
            "latency_ms": receipt.latency_ms,
            "outcome": receipt.outcome,
            "failure_mode": receipt.failure_mode,
            "fallback_used": receipt.fallback_used,
            "context_packet_ids": list(receipt.context_packet_ids),
        }
        for receipt in active_receipts
    ]
    slowest = max(active_receipts, key=lambda receipt: receipt.latency_ms, default=None)
    return {
        "receipt_count": len(active_receipts),
        "total_latency_ms": sum(receipt.latency_ms for receipt in active_receipts),
        "failure_count": sum(1 for receipt in active_receipts if receipt.outcome == "failed"),
        "fallback_count": sum(1 for receipt in active_receipts if receipt.fallback_used),
        "slowest_task": slowest.task if slowest is not None else None,
        "slowest_latency_ms": slowest.latency_ms if slowest is not None else 0,
        "context_packet_ids": _unique_context_packet_ids(active_receipts),
        "token_usage": _merged_receipt_token_usage(active_receipts),
        "route_waterfall": route_waterfall,
    }


async def invoke_openrouter_json_schema(
    *,
    task: OpenRouterTask,
    messages: list[dict[str, str]],
    schema_model: type[SchemaModelT],
    schema_name: str,
    model_name: str | None = None,
    context_packet_ids: list[str] | None = None,
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
            context_packet_ids=context_packet_ids,
        )
        return None

    candidate_models = openrouter_structured_model_candidates(model_name, task=task)
    if not candidate_models:
        logger.warning("OpenRouter unavailable; no model configured", llm_task=task)
        record_openrouter_route_receipt(
            task=task,
            model_name=model_name,
            mode="json_schema",
            schema_name=schema_name,
            latency_ms=_elapsed_ms(started_at),
            outcome="skipped",
            failure_mode="missing_model",
            context_packet_ids=context_packet_ids,
        )
        return None

    profile = openrouter_profile_for_task(task)
    last_exc: Exception | None = None
    for index, candidate_model in enumerate(candidate_models):
        attempt_started_at = time.perf_counter()
        payload = _json_schema_payload(
            model=candidate_model,
            messages=messages,
            schema_model=schema_model,
            schema_name=schema_name,
            profile=profile,
        )
        try:
            async with httpx.AsyncClient(timeout=profile.timeout_seconds) as client:
                response = await asyncio.wait_for(
                    _post_openrouter_json_schema(
                        client=client,
                        api_key=api_key,
                        payload=payload,
                    ),
                    timeout=profile.timeout_seconds,
                )
            data = response.json()
            _raise_openrouter_payload_error(data)
            content = _openrouter_message_content(data)
            if not content:
                raise ValueError(
                    "OpenRouter JSON schema response did not include content"
                )
            result = schema_model.model_validate_json(
                _json_content_without_code_fences(content)
            )
        except Exception as exc:
            last_exc = exc
            record_openrouter_route_receipt(
                task=task,
                model_name=candidate_model,
                mode="json_schema",
                schema_name=schema_name,
                latency_ms=_elapsed_ms(attempt_started_at),
                outcome="failed",
                failure_mode=type(exc).__name__,
                context_packet_ids=context_packet_ids,
            )
            if index + 1 < len(candidate_models):
                log_openrouter_failure(
                    task=task,
                    model_name=candidate_model,
                    exc=exc,
                    message="JSON schema completion failed; trying next configured model",
                )
                continue
            raise
        record_openrouter_route_receipt(
            task=task,
            model_name=candidate_model,
            mode="json_schema",
            schema_name=schema_name,
            latency_ms=_elapsed_ms(attempt_started_at),
            outcome="succeeded",
            token_usage=openrouter_token_usage_from_payload(data),
            context_packet_ids=context_packet_ids,
        )
        return result
    if last_exc is not None:
        raise last_exc
    return None


async def invoke_openrouter_chat_completion(
    *,
    task: OpenRouterTask,
    messages: list[dict[str, str]],
    model_name: str | None = None,
    context_packet_ids: list[str] | None = None,
) -> str | None:
    started_at = time.perf_counter()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("OpenRouter unavailable; missing API key", llm_task=task)
        record_openrouter_route_receipt(
            task=task,
            model_name=model_name,
            mode="chat_model",
            schema_name=None,
            latency_ms=_elapsed_ms(started_at),
            outcome="skipped",
            failure_mode="missing_api_key",
            context_packet_ids=context_packet_ids,
        )
        return None

    candidate_models = openrouter_model_candidates(model_name, task=task)
    if not candidate_models:
        logger.warning("OpenRouter unavailable; no model configured", llm_task=task)
        record_openrouter_route_receipt(
            task=task,
            model_name=model_name,
            mode="chat_model",
            schema_name=None,
            latency_ms=_elapsed_ms(started_at),
            outcome="skipped",
            failure_mode="missing_model",
            context_packet_ids=context_packet_ids,
        )
        return None

    profile = openrouter_profile_for_task(task)
    last_exc: Exception | None = None
    for index, candidate_model in enumerate(candidate_models):
        attempt_started_at = time.perf_counter()
        payload: dict[str, object] = {
            "model": candidate_model,
            "messages": messages,
            "temperature": profile.temperature,
            "max_tokens": profile.max_tokens,
        }
        try:
            async with httpx.AsyncClient(timeout=profile.timeout_seconds) as client:
                response = await asyncio.wait_for(
                    _post_openrouter_json_schema(
                        client=client,
                        api_key=api_key,
                        payload=payload,
                    ),
                    timeout=profile.timeout_seconds,
                )
                data = response.json()
                _raise_openrouter_payload_error(data)
        except Exception as exc:
            last_exc = exc
            record_openrouter_route_receipt(
                task=task,
                model_name=candidate_model,
                mode="chat_model",
                schema_name=None,
                latency_ms=_elapsed_ms(attempt_started_at),
                outcome="failed",
                failure_mode=type(exc).__name__,
                context_packet_ids=context_packet_ids,
            )
            if index + 1 < len(candidate_models):
                log_openrouter_failure(
                    task=task,
                    model_name=candidate_model,
                    exc=exc,
                    message="Chat completion failed; trying next configured model",
                )
                continue
            raise

        content = _openrouter_message_content(data).strip()
        token_usage = openrouter_token_usage_from_payload(data)
        if not content:
            record_openrouter_route_receipt(
                task=task,
                model_name=candidate_model,
                mode="chat_model",
                schema_name=None,
                latency_ms=_elapsed_ms(attempt_started_at),
                outcome="failed",
                failure_mode="empty_response",
                token_usage=token_usage,
                context_packet_ids=context_packet_ids,
            )
            if index + 1 < len(candidate_models):
                continue
            return None
        record_openrouter_route_receipt(
            task=task,
            model_name=candidate_model,
            mode="chat_model",
            schema_name=None,
            latency_ms=_elapsed_ms(attempt_started_at),
            outcome="succeeded",
            token_usage=token_usage,
            context_packet_ids=context_packet_ids,
        )
        return content
    if last_exc is not None:
        raise last_exc
    return None


def invoke_openrouter_json_schema_sync(
    *,
    task: OpenRouterTask,
    messages: list[dict[str, str]],
    schema_model: type[SchemaModelT],
    schema_name: str,
    model_name: str | None = None,
    context_packet_ids: list[str] | None = None,
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
            context_packet_ids=context_packet_ids,
        )
        return None

    candidate_models = openrouter_structured_model_candidates(model_name, task=task)
    if not candidate_models:
        logger.warning("OpenRouter unavailable; no model configured", llm_task=task)
        record_openrouter_route_receipt(
            task=task,
            model_name=model_name,
            mode="json_schema",
            schema_name=schema_name,
            latency_ms=_elapsed_ms(started_at),
            outcome="skipped",
            failure_mode="missing_model",
            context_packet_ids=context_packet_ids,
        )
        return None

    profile = openrouter_profile_for_task(task)
    last_exc: Exception | None = None
    for index, candidate_model in enumerate(candidate_models):
        attempt_started_at = time.perf_counter()
        payload = _json_schema_payload(
            model=candidate_model,
            messages=messages,
            schema_model=schema_model,
            schema_name=schema_name,
            profile=profile,
        )
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
                raise ValueError(
                    "OpenRouter JSON schema response did not include content"
                )
            result = schema_model.model_validate_json(
                _json_content_without_code_fences(content)
            )
        except Exception as exc:
            last_exc = exc
            record_openrouter_route_receipt(
                task=task,
                model_name=candidate_model,
                mode="json_schema",
                schema_name=schema_name,
                latency_ms=_elapsed_ms(attempt_started_at),
                outcome="failed",
                failure_mode=type(exc).__name__,
                context_packet_ids=context_packet_ids,
            )
            if index + 1 < len(candidate_models):
                log_openrouter_failure(
                    task=task,
                    model_name=candidate_model,
                    exc=exc,
                    message="JSON schema completion failed; trying next configured model",
                )
                continue
            raise
        record_openrouter_route_receipt(
            task=task,
            model_name=candidate_model,
            mode="json_schema",
            schema_name=schema_name,
            latency_ms=_elapsed_ms(attempt_started_at),
            outcome="succeeded",
            token_usage=openrouter_token_usage_from_payload(data),
            context_packet_ids=context_packet_ids,
        )
        return result
    if last_exc is not None:
        raise last_exc
    return None


def openrouter_token_usage_from_payload(data: dict[str, object]) -> dict[str, int] | None:
    usage = data.get("usage")
    return normalize_openrouter_token_usage(usage if isinstance(usage, dict) else None)


def openrouter_token_usage_from_message(message: object) -> dict[str, int] | None:
    usage_metadata = getattr(message, "usage_metadata", None)
    normalized = normalize_openrouter_token_usage(
        usage_metadata if isinstance(usage_metadata, dict) else None
    )
    if normalized is not None:
        return normalized
    response_metadata = getattr(message, "response_metadata", None)
    if not isinstance(response_metadata, dict):
        return None
    for key in ("token_usage", "usage"):
        value = response_metadata.get(key)
        normalized = normalize_openrouter_token_usage(
            value if isinstance(value, dict) else None
        )
        if normalized is not None:
            return normalized
    return None


def merge_openrouter_token_usage(
    current: dict[str, int] | None,
    incoming: dict[str, int] | None,
) -> dict[str, int] | None:
    if current is None:
        return dict(incoming) if incoming is not None else None
    if incoming is None:
        return dict(current)
    merged = dict(current)
    for key, value in incoming.items():
        merged[key] = value
    return merged


def normalize_openrouter_token_usage(
    value: dict[str, object] | None,
) -> dict[str, int] | None:
    if not value:
        return None
    normalized: dict[str, int] = {}
    for key, raw in value.items():
        if not isinstance(key, str) or isinstance(raw, bool):
            continue
        if isinstance(raw, int):
            normalized[key] = raw
        elif isinstance(raw, float) and raw.is_integer():
            normalized[key] = int(raw)
    return normalized or None


def _normalized_context_packet_ids(values: list[str] | None) -> list[str]:
    if not values:
        return []
    normalized: list[str] = []
    for value in values:
        packet_id = str(value or "").strip()
        if packet_id and packet_id not in normalized:
            normalized.append(packet_id)
    return normalized


def _unique_context_packet_ids(receipts: Iterable[OpenRouterRouteReceipt]) -> list[str]:
    normalized: list[str] = []
    for receipt in receipts:
        for packet_id in receipt.context_packet_ids:
            if packet_id and packet_id not in normalized:
                normalized.append(packet_id)
    return normalized


def _merged_receipt_token_usage(
    receipts: Iterable[OpenRouterRouteReceipt],
) -> dict[str, int] | None:
    merged: dict[str, int] | None = None
    for receipt in receipts:
        merged = merge_openrouter_token_usage(merged, receipt.token_usage)
    return merged


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _apply_reasoning_for_structured_artifact(
    payload: dict[str, object],
    profile: OpenRouterProfile,
) -> None:
    payload["reasoning"] = {"effort": profile.reasoning_effort}


_SCHEMA_IN_PROMPT_INSTRUCTION = (
    "Return a single JSON object that validates against this JSON Schema. "
    "Output only the JSON object, no prose, no code fences.\nJSON Schema:\n"
)


def _json_schema_payload(
    *,
    model: str,
    messages: list[dict[str, str]],
    schema_model: type[SchemaModelT],
    schema_name: str,
    profile: OpenRouterProfile,
) -> dict[str, object]:
    if model.startswith("anthropic/"):
        # Anthropic strict structured outputs reject core shapes of our
        # schemas (numeric bounds, any-typed values, open objects such as
        # extra_parameters), so every native json_schema call 400s. Embed the
        # schema in a system message instead; client-side pydantic validation
        # and the candidate retry loop own correctness either way.
        schema_message = {
            "role": "system",
            "content": (
                _SCHEMA_IN_PROMPT_INSTRUCTION
                + json.dumps(schema_model.model_json_schema())
            ),
        }
        payload: dict[str, object] = {
            "model": model,
            "messages": [schema_message, *messages],
            "temperature": profile.temperature,
            "max_tokens": profile.max_tokens,
        }
        _apply_reasoning_for_structured_artifact(payload, profile)
        return payload
    payload = {
        "model": model,
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": schema_model.model_json_schema(),
            },
        },
        "provider": {"require_parameters": True},
        "temperature": profile.temperature,
        "max_tokens": profile.max_tokens,
    }
    _apply_reasoning_for_structured_artifact(payload, profile)
    return payload


def _json_content_without_code_fences(content: str) -> str:
    """Strip a markdown code fence around a JSON body, if present.

    Schema-in-prompt providers occasionally fence their JSON despite
    instructions — sometimes on one line ("```json {...}```") or with prose
    after the closing fence; strict structured outputs never fence, so this
    is a no-op for them.
    """

    text = content.strip()
    if not text.startswith("```"):
        return text
    text = text[len("```") :]
    info_end = 0
    while info_end < len(text) and (
        text[info_end].isalnum() or text[info_end] in "_-"
    ):
        info_end += 1
    text = text[info_end:]
    closing = text.rfind("```")
    if closing != -1:
        text = text[:closing]
    return text.strip()


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
    profile = openrouter_profile_for_task(task)
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
