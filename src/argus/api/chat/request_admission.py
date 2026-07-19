from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import Request

from argus.agent_runtime.recovery_messages import recovery_message
from argus.agent_runtime.state.models import ResolutionProvenance
from argus.api.chat.actions import (
    ValidatedResponseOptionSource,
    is_response_option_action,
    persisted_chat_action,
    validated_response_option_source,
)
from argus.api.dependencies import problem
from argus.api.message_store import create_message, prepare_message
from argus.api.schemas import ChatStreamRequest, Message


@dataclass
class ChatRequestAdmission:
    payload: ChatStreamRequest
    request: Request
    user_id: str
    conversation_id: str
    language: str | None
    request_message_candidate: Message | None
    request_message_record: Message | None = None
    validated_option_source: ValidatedResponseOptionSource | None = None

    def persist(self) -> Message | None:
        if self.request_message_candidate is None:
            return None
        if self.request_message_record is None:
            candidate = self.request_message_candidate
            self.request_message_record = create_message(
                user_id=self.user_id,
                conversation_id=self.conversation_id,
                role=candidate.role,
                content=candidate.content,
                metadata=candidate.metadata,
            )
        return self.request_message_record

    def admit_response_option(self) -> ValidatedResponseOptionSource | None:
        if not is_response_option_action(self.payload):
            return None
        if self.validated_option_source is not None:
            return self.validated_option_source
        if self.request_message_candidate is None:
            raise RuntimeError("Response-option request message was not prepared.")
        validated_source = validated_response_option_source(
            payload=self.payload,
            user_id=self.user_id,
            conversation_id=self.conversation_id,
            request_message=self.request_message_candidate,
        )
        if validated_source is None:
            raise problem(
                self.request,
                status_code=409,
                code="artifact_action_invalid_state",
                title="Action No Longer Active",
                detail=recovery_message(
                    "artifact_action_invalid_state",
                    language=self.language,
                ),
            )
        self.validated_option_source = validated_source
        self.request_message_record = validated_source.request_message
        return validated_source

    def runtime_action_context(self) -> dict[str, Any] | None:
        if self.payload.action is None:
            return None
        action_context = self.payload.action.model_dump(mode="python")
        if self.validated_option_source is not None:
            action_context["payload"] = {
                **action_context.get("payload", {}),
                "validated_source_assistant_id": (
                    self.validated_option_source.assistant_id
                ),
            }
        return action_context


def prepare_chat_request_admission(
    *,
    payload: ChatStreamRequest,
    request: Request,
    user_id: str,
    conversation_id: str,
    display_message: str,
    mention_provenance: list[ResolutionProvenance],
    enabled: bool,
    language: str | None,
    onboarding_control: dict[str, Any] | None = None,
) -> ChatRequestAdmission:
    candidate = None
    if enabled:
        user_metadata: dict[str, Any] = {
            "agent_runtime_turn": {
                "status": "started",
                "conversation_id": conversation_id,
                "request_id": request.state.request_id,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
        }
        if onboarding_control is not None:
            # Owned protocol state: runtime filtering and preview
            # suppression key off this, never a raw-text prefix.
            user_metadata["onboarding_control"] = dict(onboarding_control)
        if mention_provenance:
            user_metadata["mentions"] = [
                mention.model_dump(mode="python") for mention in payload.mentions
            ]
            user_metadata["resolution_provenance"] = [
                item.model_dump(mode="python") for item in mention_provenance
            ]
        if payload.action is not None:
            user_metadata["chat_action"] = persisted_chat_action(payload)
        candidate = prepare_message(
            conversation_id=conversation_id,
            role="user",
            content=display_message,
            metadata=user_metadata,
        )
    return ChatRequestAdmission(
        payload=payload,
        request=request,
        user_id=user_id,
        conversation_id=conversation_id,
        language=language,
        request_message_candidate=candidate,
    )
