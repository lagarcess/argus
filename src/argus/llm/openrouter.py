from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from langchain_openrouter import ChatOpenRouter
from loguru import logger

OpenRouterTask = Literal[
    "interpretation",
    "clarification",
    "chat_composer",
    "result_summary",
    "result_breakdown",
    "name_suggestion",
]


@dataclass(frozen=True)
class OpenRouterProfile:
    task: OpenRouterTask
    temperature: float
    max_tokens: int


OPENROUTER_PROFILES: dict[OpenRouterTask, OpenRouterProfile] = {
    "interpretation": OpenRouterProfile("interpretation", temperature=0, max_tokens=1200),
    "clarification": OpenRouterProfile("clarification", temperature=0, max_tokens=1200),
    "chat_composer": OpenRouterProfile("chat_composer", temperature=0.2, max_tokens=1200),
    "result_summary": OpenRouterProfile(
        "result_summary", temperature=0.2, max_tokens=1600
    ),
    "result_breakdown": OpenRouterProfile(
        "result_breakdown", temperature=0.2, max_tokens=2400
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
        openrouter_api_key=api_key,
    )


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
