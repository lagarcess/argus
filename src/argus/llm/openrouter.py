from __future__ import annotations

import json
import os
from dataclasses import dataclass
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

SchemaModelT = TypeVar("SchemaModelT", bound=BaseModel)


@dataclass(frozen=True)
class OpenRouterProfile:
    task: OpenRouterTask
    temperature: float
    max_tokens: int
    timeout_seconds: int = 12
    max_retries: int = 1


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


def resolve_openrouter_model(
    model_name: str | None = None, fallback: bool = False
) -> str:
    """
    Resolves the model name to use, preferring AGENT_MODEL or AGENT_FALLBACK_MODEL.
    """
    if model_name:
        return model_name

    if fallback:
        return os.getenv("AGENT_FALLBACK_MODEL", "").strip()

    return os.getenv("AGENT_MODEL", "").strip()


def resolve_openrouter_structured_model(model_name: str | None = None) -> str:
    candidates = openrouter_structured_model_candidates(model_name)
    return candidates[0] if candidates else ""


def openrouter_structured_model_candidates(model_name: str | None = None) -> list[str]:
    if model_name:
        return [model_name]
    return _unique_nonempty(
        [
            os.getenv("AGENT_STRUCTURED_MODEL", "").strip(),
            os.getenv("AGENT_MODEL", "").strip(),
            os.getenv("AGENT_FALLBACK_MODEL", "").strip(),
        ]
    )


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
    resolved_model = resolve_openrouter_model(model_name)
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


async def invoke_openrouter_json_schema(
    *,
    task: OpenRouterTask,
    messages: list[dict[str, str]],
    schema_model: type[SchemaModelT],
    schema_name: str,
    model_name: str | None = None,
) -> SchemaModelT | None:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("OpenRouter unavailable; missing API key", llm_task=task)
        return None

    resolved_model = resolve_openrouter_structured_model(model_name)
    if not resolved_model:
        logger.warning("OpenRouter unavailable; no model configured", llm_task=task)
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
    return schema_model.model_validate_json(content)


def invoke_openrouter_json_schema_sync(
    *,
    task: OpenRouterTask,
    messages: list[dict[str, str]],
    schema_model: type[SchemaModelT],
    schema_name: str,
    model_name: str | None = None,
) -> SchemaModelT | None:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("OpenRouter unavailable; missing API key", llm_task=task)
        return None

    resolved_model = resolve_openrouter_structured_model(model_name)
    if not resolved_model:
        logger.warning("OpenRouter unavailable; no model configured", llm_task=task)
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
    return schema_model.model_validate_json(content)


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
    resolved_model = resolve_openrouter_model(model_name)
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
