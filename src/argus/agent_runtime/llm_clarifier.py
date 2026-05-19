from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from argus.agent_runtime.state.models import ConversationMessage, StrategySummary
from argus.llm.openrouter import (
    build_openrouter_model,
    log_openrouter_failure,
    openrouter_task_timeout_seconds,
)


class ClarificationRequest(BaseModel):
    current_user_message: str
    recent_thread_history: list[ConversationMessage] = Field(default_factory=list)
    candidate_strategy_draft: StrategySummary = Field(default_factory=StrategySummary)
    missing_required_fields: list[str] = Field(default_factory=list)
    ambiguous_fields: list[dict[str, Any]] = Field(default_factory=list)
    unsupported_constraints: list[dict[str, Any]] = Field(default_factory=list)
    optional_parameter_choices: list[str] = Field(default_factory=list)
    response_intent: dict[str, Any] = Field(default_factory=dict)
    language: str = "en"


class ClarificationResponse(BaseModel):
    question: str


class OpenRouterClarificationGenerator:
    request_model = ClarificationRequest

    def __init__(self, *, model_name: str | None = None) -> None:
        self.model_name = model_name
        self.last_status: str | None = None

    def __call__(self, request: ClarificationRequest) -> str | None:
        return asyncio.run(self.ainvoke(request))

    async def ainvoke(self, request: ClarificationRequest) -> str | None:
        chunks = [chunk async for chunk in self.astream(request)]
        question = "".join(chunks).strip()
        return question or None

    async def astream(self, request: ClarificationRequest) -> AsyncIterator[str]:
        """
        Executes the clarification turn.
        """
        messages = self._messages(request)

        model = build_openrouter_model("clarification", model_name=self.model_name)
        if model:
            try:
                chunks = await asyncio.wait_for(
                    _collect_stream_chunks(model, messages),
                    timeout=openrouter_task_timeout_seconds("clarification"),
                )
                if chunks:
                    for content in chunks:
                        yield content
                    self.last_status = "used"
                    return
            except Exception as exc:
                log_openrouter_failure(
                    task="clarification",
                    model_name=self.model_name,
                    exc=exc,
                    message="Primary LLM clarification failed; attempting fallback",
                )

        from argus.llm.openrouter import resolve_openrouter_model

        fallback_model_name = resolve_openrouter_model(
            fallback=True,
            task="clarification",
        )

        primary_model_name = resolve_openrouter_model(
            model_name=self.model_name,
            task="clarification",
        )
        if not fallback_model_name or fallback_model_name == primary_model_name:
            self.last_status = "failed"
            return

        fallback_model = build_openrouter_model(
            "clarification", model_name=fallback_model_name
        )
        if fallback_model:
            try:
                chunks = await asyncio.wait_for(
                    _collect_stream_chunks(fallback_model, messages),
                    timeout=openrouter_task_timeout_seconds("clarification"),
                )
                if chunks:
                    for content in chunks:
                        yield content
                    self.last_status = "fallback_used"
                    return
            except Exception as exc:
                self.last_status = "failed"
                log_openrouter_failure(
                    task="clarification",
                    model_name=fallback_model_name,
                    exc=exc,
                    message="Fallback LLM clarification failed",
                )

        return

    def _messages(self, request: ClarificationRequest) -> list[BaseMessage]:
        history: list[BaseMessage] = []
        for item in request.recent_thread_history[-6:]:
            if not hasattr(item, "role") or not hasattr(item, "content"):
                continue
            content = str(item.content)
            if item.role == "assistant":
                history.append(AIMessage(content=content))
            elif item.role == "user":
                history.append(HumanMessage(content=content))
        context = {
            "language": request.language,
            "current_user_message": request.current_user_message,
            "candidate_strategy_draft": request.candidate_strategy_draft.model_dump(
                mode="python"
            ),
            "missing_required_fields": request.missing_required_fields,
            "ambiguous_fields": request.ambiguous_fields,
            "unsupported_constraints": request.unsupported_constraints,
            "optional_parameter_choices": request.optional_parameter_choices,
            "response_intent": request.response_intent,
        }
        return [
            SystemMessage(
                content=(
                    "Generate exactly one concise, context-aware assistant response. "
                    "Do not expose field names such as asset_universe, capital_amount, "
                    "date_range, requested_field, or missing_required_fields. Do not "
                    "output JSON. Respond in the user's preferred language (e.g., "
                    "Spanish if language is 'es-419').\n\n"
                    "If response_intent.kind is unsupported_recovery, do not write a "
                    "bare generic question. Acknowledge the exact idea using the "
                    "candidate strategy's asset, period, and unsupported rule when "
                    "available; name the limitation in product language; then offer "
                    "the provided simplification_options as concrete runnable next "
                    "moves. Ask which direction to use. Do not claim the unsupported "
                    "part is executable."
                )
            ),
            SystemMessage(content=json.dumps(context, default=str, sort_keys=True)),
            *history,
            HumanMessage(content=request.current_user_message),
        ]


async def _collect_stream_chunks(model: Any, messages: list[BaseMessage]) -> list[str]:
    chunks: list[str] = []
    async for chunk in model.astream(messages):
        content = _chunk_content(chunk)
        if content:
            chunks.append(content)
    return chunks


def _chunk_content(chunk: Any) -> str:
    content = getattr(chunk, "content", "")
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
    return ""
