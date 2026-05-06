from __future__ import annotations

import json
import os
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
        self.model_name = (
            model_name or os.getenv("AGENT_MODEL") or "google/gemini-2.0-flash-001"
        )
        self.last_status: str | None = None

    def __call__(self, request: ClarificationRequest) -> str | None:
        model = build_openrouter_model("clarification", model_name=self.model_name)
        if model is None:
            self.last_status = "missing_api_key"
            return None
        try:
            structured = model.with_structured_output(ClarificationResponse)
            response = structured.invoke(self._messages(request))
        except Exception as exc:
            self.last_status = "failed"
            log_openrouter_failure(
                task="clarification",
                model_name=self.model_name,
                exc=exc,
                message="LLM clarification failed",
            )
            return None
        if not isinstance(response, ClarificationResponse):
            self.last_status = "invalid_response"
            return None
        self.last_status = "used"
        return response.question.strip() or None

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
