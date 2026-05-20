from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from argus.agent_runtime.response_style import ARGUS_RESPONSE_STYLE_CONTRACT
from argus.agent_runtime.state.models import (
    ConversationMessage,
    PendingNeedName,
    StrategySummary,
)
from argus.llm.openrouter import (
    invoke_openrouter_json_schema,
    log_openrouter_failure,
    record_openrouter_route_receipt,
    resolve_openrouter_model,
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
    question: str = Field(
        description="The exact natural-language response the user should see."
    )
    question_targets: list[PendingNeedName] = Field(
        description=(
            "The semantic needs directly asked for by question. Copy "
            "expected_question_targets exactly when it is provided."
        )
    )
    directly_asks_user: bool = Field(
        description=(
            "True only when question clearly gives the user a recoverable next step."
        )
    )


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
        wire_messages = _openrouter_wire_messages(messages)

        try:
            response = await invoke_openrouter_json_schema(
                task="clarification",
                messages=wire_messages,
                schema_model=ClarificationResponse,
                schema_name="ClarificationResponse",
                model_name=self.model_name,
            )
            if response and _clarification_response_matches_request(
                response=response,
                request=request,
            ):
                yield response.question.strip()
                self.last_status = "used"
                return
            _record_invalid_clarification_response(
                model_name=self.model_name,
                failure_mode="contract_violation",
            )
        except Exception as exc:
            log_openrouter_failure(
                task="clarification",
                model_name=self.model_name,
                exc=exc,
                message="Primary LLM clarification failed; attempting fallback",
            )

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

        try:
            response = await invoke_openrouter_json_schema(
                task="clarification",
                messages=wire_messages,
                schema_model=ClarificationResponse,
                schema_name="ClarificationResponse",
                model_name=fallback_model_name,
            )
            if response and _clarification_response_matches_request(
                response=response,
                request=request,
            ):
                yield response.question.strip()
                self.last_status = "fallback_used"
                return
            _record_invalid_clarification_response(
                model_name=fallback_model_name,
                failure_mode="contract_violation",
            )
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
            "expected_question_targets": sorted(_expected_question_targets(request)),
        }
        return [
            SystemMessage(
                content=(
                    f"{ARGUS_RESPONSE_STYLE_CONTRACT}\n\n"
                    "Generate exactly one concise, context-aware assistant response "
                    "through the provided schema. "
                    "Target 45-90 words unless the user explicitly asks for depth. "
                    "Ask for only the next decision needed, or offer at most three "
                    "short runnable choices. "
                    "Do not expose field names such as asset_universe, capital_amount, "
                    "date_range, requested_field, or missing_required_fields. Do not "
                    "put JSON text inside the question. Do not use headings or "
                    "numbered lists. Respond in the user's preferred language (e.g., "
                    "Spanish if language is 'es-419'). Set question_targets to the "
                    "semantic needs directly answered by the question. If "
                    "expected_question_targets is present in the context, copy it "
                    "exactly and ask only for those needs. When it contains more "
                    "than one target, the user-facing question must visibly ask "
                    "for every target in one concise response. Set directly_asks_user "
                    "to true only when the question clearly gives the user a "
                    "recoverable next step.\n\n"
                    "For beginner or vague investing ideas, do not write a numbered "
                    "requirements list. Use one short paragraph and, when useful, "
                    "2-3 concrete next choices. Offer only executable Argus proxies: "
                    "buy-and-hold baseline, supported RSI threshold, supported moving "
                    "average crossover, DCA, or a simple date/asset clarification. Do "
                    "not ask the user to define a moving-average trigger again when "
                    "they used common shorthand such as 'the 50 crosses the 200' or "
                    "'50/200 cross'; treat that as a supported moving-average crossover "
                    "draft and ask only for missing run facts such as asset or dates. "
                    "Acknowledge valid finance concepts such as valuation, P/E, "
                    "sentiment, or news when the user means them. For example, P/E is "
                    "a valid way investors discuss whether a stock looks cheap, but "
                    "the current engine cannot execute P/E as a rule yet. Translate "
                    "that concept to the closest supported proxy and educate briefly "
                    "without making the user feel wrong. If the user says a stock "
                    "looked cheap, name P/E or valuation as valid context before "
                    "offering a runnable proxy. Keep date guidance aligned with data "
                    "availability truth: equity launch history starts in 2016, and "
                    "currency-pair intraday history has a bounded recent-data window. "
                    "For currency-pair tests, use 1h, 4h, or 1D rather than implying "
                    "every intermediate timeframe is available. If the user asks for an "
                    "hourly/intraday timeframe or a long historical window, do not "
                    "silently widen the timeframe, shorten the dates, or reshape the "
                    "request to make it runnable; ask for an available window or bar "
                    "size in product language. Do not mention provider "
                    "names, candle counts, or provider plumbing in the user-facing "
                    "response; translate those facts into product language such as "
                    "available equity history or current currency-data window.\n\n"
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


def _openrouter_wire_messages(messages: list[BaseMessage]) -> list[dict[str, str]]:
    wire_messages: list[dict[str, str]] = []
    for message in messages:
        role = "user"
        if isinstance(message, SystemMessage):
            role = "system"
        elif isinstance(message, AIMessage):
            role = "assistant"
        content = message.content
        if isinstance(content, str):
            text = content
        else:
            text = json.dumps(content, default=str)
        wire_messages.append({"role": role, "content": text})
    return wire_messages


def _clarification_response_matches_request(
    *,
    response: ClarificationResponse,
    request: ClarificationRequest,
) -> bool:
    question = response.question.strip()
    if not question or not response.directly_asks_user:
        return False
    expected_targets = _expected_question_targets(request)
    response_targets = set(response.question_targets)
    if expected_targets:
        return response_targets == expected_targets
    return not response_targets


def _expected_question_targets(request: ClarificationRequest) -> set[PendingNeedName]:
    raw_needs = request.response_intent.get("semantic_needs")
    if not isinstance(raw_needs, list):
        return set()
    valid_names = set(PendingNeedName.__args__)
    return {value for value in raw_needs if value in valid_names}


def _record_invalid_clarification_response(
    *,
    model_name: str | None,
    failure_mode: str,
) -> None:
    record_openrouter_route_receipt(
        task="clarification",
        model_name=model_name,
        mode="json_schema",
        schema_name="ClarificationResponse",
        latency_ms=0,
        outcome="failed",
        failure_mode=failure_mode,
    )
