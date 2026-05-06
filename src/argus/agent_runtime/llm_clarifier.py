from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from argus.agent_runtime.state.models import ConversationMessage, StrategySummary
from argus.llm.openrouter import build_openrouter_model, log_openrouter_failure


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
        """
        Executes the clarification turn.
        """
        messages = self._messages(request)

        model = build_openrouter_model("clarification", model_name=self.model_name)
        if model:
            try:
                structured = model.with_structured_output(ClarificationResponse)
                response = structured.invoke(messages)
                if isinstance(response, ClarificationResponse):
                    self.last_status = "used"
                    return response.question.strip() or None
            except Exception as exc:
                log_openrouter_failure(
                    task="clarification",
                    model_name=self.model_name,
                    exc=exc,
                    message="Primary LLM clarification failed; attempting fallback",
                )

        from argus.llm.openrouter import resolve_openrouter_model
        fallback_model_name = resolve_openrouter_model(fallback=True)

        primary_model_name = resolve_openrouter_model(model_name=self.model_name)
        if fallback_model_name == primary_model_name:
            self.last_status = "failed"
            return None

        fallback_model = build_openrouter_model("clarification", model_name=fallback_model_name)
        if fallback_model:
            try:
                structured = fallback_model.with_structured_output(ClarificationResponse)
                response = structured.invoke(messages)
                if isinstance(response, ClarificationResponse):
                    self.last_status = "fallback_used"
                    return response.question.strip() or None
            except Exception as exc:
                self.last_status = "failed"
                log_openrouter_failure(
                    task="clarification",
                    model_name=fallback_model_name,
                    exc=exc,
                    message="Fallback LLM clarification failed",
                )

        return None

    def _messages(self, request: ClarificationRequest) -> list[dict[str, str]]:
        history = [
            {"role": item.role, "content": item.content}
            for item in request.recent_thread_history[-6:]
            if hasattr(item, "role") and hasattr(item, "content")
        ]
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
            {
                "role": "system",
                "content": (
                    "Generate exactly one concise, context-aware clarifying question. "
                    "Do not expose field names such as asset_universe, capital_amount, "
                    "date_range, requested_field, or missing_required_fields. Do not "
                    "output JSON. Respond in the user's preferred language (e.g., "
                    "Spanish if language is 'es-419')."
                ),
            },
            {
                "role": "system",
                "content": json.dumps(context, default=str, sort_keys=True),
            },
            *history,
            {"role": "user", "content": request.current_user_message},
        ]
