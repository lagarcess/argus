from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from langchain_openrouter import ChatOpenRouter
from loguru import logger

OpenRouterTask = Literal[
    "interpretation",
    "chat_composer",
    "result_summary",
    "result_breakdown",
    "name_suggestion",
]

DEFAULT_MODEL = "google/gemini-2.0-flash-001"


@dataclass(frozen=True)
class OpenRouterProfile:
    task: OpenRouterTask
    temperature: float
    max_tokens: int


OPENROUTER_PROFILES: dict[OpenRouterTask, OpenRouterProfile] = {
    "interpretation": OpenRouterProfile("interpretation", temperature=0, max_tokens=1200),
    "chat_composer": OpenRouterProfile("chat_composer", temperature=0.2, max_tokens=1200),
    "result_summary": OpenRouterProfile("result_summary", temperature=0.2, max_tokens=1600),
    "result_breakdown": OpenRouterProfile("result_breakdown", temperature=0.2, max_tokens=2400),
    "name_suggestion": OpenRouterProfile("name_suggestion", temperature=0, max_tokens=400),
}


def resolve_openrouter_model(model_name: str | None = None) -> str:
    return model_name or os.getenv("AGENT_MODEL") or DEFAULT_MODEL


def build_openrouter_model(
    task: OpenRouterTask,
    *,
    model_name: str | None = None,
) -> ChatOpenRouter | None:
    if not os.getenv("OPENROUTER_API_KEY"):
        logger.warning("OpenRouter unavailable; missing API key", llm_task=task)
        return None

    profile = OPENROUTER_PROFILES[task]
    return ChatOpenRouter(
        model=resolve_openrouter_model(model_name),
        temperature=profile.temperature,
        max_tokens=profile.max_tokens,
    )


def log_openrouter_failure(
    *,
    task: OpenRouterTask,
    model_name: str | None,
    exc: Exception,
    message: str,
) -> None:
    profile = OPENROUTER_PROFILES[task]
    logger.warning(
        message,
        llm_task=task,
        model=resolve_openrouter_model(model_name),
        max_tokens=profile.max_tokens,
        error_type=type(exc).__name__,
        error=str(exc),
    )
