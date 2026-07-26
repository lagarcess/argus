from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid5

from fastapi import Request

from argus.agent_runtime.recovery_messages import recovery_message
from argus.agent_runtime.state.models import ResolutionProvenance
from argus.api.chat.actions import (
    ValidatedResponseOptionSource,
    _response_option_source_context,
    chat_display_message,
    confirmation_action_id,
    is_response_option_action,
    persisted_chat_action,
)
from argus.api.chat.turn_lifecycle_hooks import ChatTurnLifecycleHooks
from argus.api.dependencies import problem
from argus.api.message_store import (
    accept_chat_turn,
    accept_response_option_chat_turn,
    create_message,
    owned_conversation_message,
    prepare_message,
)
from argus.api.schemas import ChatStreamRequest, Message

AdmissionOwner = Literal["ordinary_turn", "message_only"]
_RUN_ACTION_MESSAGE_NAMESPACE = UUID("9ae3396d-9c69-41ab-9ffd-a40adf9d2fd1")
_RUN_ACTION_LABEL_KEY = "chat.confirmation.actions.run_backtest"
_NON_RUN_CONFIRMATION_ACTIONS = {
    "adjust_assumptions",
    "cancel_confirmation",
    "change_asset",
    "change_dates",
}


@dataclass
class ChatRequestAdmission:
    payload: ChatStreamRequest
    request: Request
    user_id: str
    conversation_id: str
    language: str | None
    request_message_candidate: Message | None
    owner: AdmissionOwner = "ordinary_turn"
    request_message_record: Message | None = None
    validated_option_source: ValidatedResponseOptionSource | None = None
    _lifecycle_hooks: ChatTurnLifecycleHooks | None = None

    def persist(self) -> Message | None:
        if self.request_message_candidate is None:
            return None
        if self.request_message_record is None:
            if is_response_option_action(self.payload):
                self.admit_response_option()
                return self.request_message_record
            candidate = self.request_message_candidate
            if self.owner == "ordinary_turn":
                self.request_message_record = accept_chat_turn(
                    user_id=self.user_id,
                    conversation_id=self.conversation_id,
                    request_id=self.request.state.request_id,
                    message=candidate,
                )
            else:
                self.request_message_record = create_message(
                    user_id=self.user_id,
                    conversation_id=self.conversation_id,
                    role=candidate.role,
                    content=candidate.content,
                    metadata=candidate.metadata,
                    message_id=candidate.id,
                )
        return self.request_message_record

    def lifecycle_hooks(self) -> ChatTurnLifecycleHooks:
        if self._lifecycle_hooks is None:
            request_message = self.persist()
            if request_message is None:
                raise RuntimeError("Chat request admission did not persist a message.")
            self._lifecycle_hooks = ChatTurnLifecycleHooks(
                owner=self.owner,
                user_id=self.user_id,
                conversation_id=self.conversation_id,
                request_id=self.request.state.request_id,
                request_message=request_message,
            )
        return self._lifecycle_hooks

    def admit_response_option(self) -> ValidatedResponseOptionSource | None:
        if not is_response_option_action(self.payload):
            return None
        if self.validated_option_source is not None:
            return self.validated_option_source
        if self.request_message_candidate is None:
            raise RuntimeError("Response-option request message was not prepared.")
        if self.owner != "ordinary_turn" or self.payload.action is None:
            raise RuntimeError("Response-option turns require ordinary admission.")
        request_message_id = str(
            self.payload.action.payload.get("request_message_id") or ""
        ).strip()
        source_assistant_id = str(
            self.payload.action.payload.get("source_assistant_id") or ""
        ).strip()
        option_id = self.payload.action.payload.get("option_id")
        replacement_values = self.payload.action.payload.get("replacement_values")
        source_message = (
            owned_conversation_message(
                user_id=self.user_id,
                conversation_id=self.conversation_id,
                message_id=source_assistant_id,
            )
            if not request_message_id and source_assistant_id
            else None
        )
        prevalidated_source = (
            _response_option_source_context(
                source_message,
                user_id=self.user_id,
                conversation_id=self.conversation_id,
                request_message=self.request_message_candidate,
            )
            if source_message is not None
            else None
        )
        is_retry = bool(request_message_id)
        is_new_selection = (
            bool(source_assistant_id)
            and isinstance(option_id, str)
            and isinstance(replacement_values, dict)
            and source_message is not None
            and isinstance(source_message.metadata, dict)
            and prevalidated_source is not None
        )
        claim = (
            accept_response_option_chat_turn(
                user_id=self.user_id,
                conversation_id=self.conversation_id,
                request_id=self.request.state.request_id,
                message=self.request_message_candidate,
                source_assistant_id=source_assistant_id,
                expected_source_metadata=(
                    source_message.metadata if source_message is not None else None
                ),
                option_id=option_id,
                replacement_values=replacement_values,
                request_message_id=request_message_id or None,
            )
            if is_retry or is_new_selection
            else None
        )
        validated_source = (
            _response_option_source_context(
                claim.source_message,
                user_id=self.user_id,
                conversation_id=self.conversation_id,
                request_message=claim.request_message,
            )
            if claim is not None
            else None
        )
        if validated_source is None or claim is None:
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
        self.request_message_record = claim.request_message
        return validated_source

    def runtime_action_context(self) -> dict[str, Any] | None:
        if self.payload.action is None:
            return None
        if self.payload.action.type == "select_discovery_candidate":
            # Discovery selections are provenance-only: the turn text carries
            # the full meaning and the runtime interprets it as ordinary
            # language; chat_action metadata persists for transcript chips.
            return None
        persisted_action = (
            self.request_message_record.metadata.get("chat_action")
            if self.request_message_record is not None
            and isinstance(self.request_message_record.metadata, dict)
            else None
        )
        action_context = (
            dict(persisted_action)
            if isinstance(persisted_action, dict)
            else self.payload.action.model_dump(mode="python")
        )
        if self.validated_option_source is not None:
            action_context["payload"] = {
                **action_context.get("payload", {}),
                "source_assistant_id": (
                    self.validated_option_source.assistant_id
                ),
                "validated_source_assistant_id": (
                    self.validated_option_source.assistant_id
                ),
            }
        return action_context


def reject_invalid_non_run_confirmation_action(
    *,
    payload: ChatStreamRequest,
    request: Request,
    active_confirmation_id: str | None,
    stale_confirmation_message: str | None,
    language: str | None,
) -> None:
    action = payload.action
    if action is None or action.type not in _NON_RUN_CONFIRMATION_ACTIONS:
        return
    action_confirmation_id = confirmation_action_id(payload)
    if (
        stale_confirmation_message is None
        and action_confirmation_id is not None
        and action_confirmation_id == active_confirmation_id
    ):
        return
    detail = recovery_message(
        (
            "confirmation_action_stale_card"
            if action_confirmation_id is not None
            else "confirmation_action_missing_identity"
        ),
        language=language,
    )
    raise problem(
        request,
        status_code=409,
        code="confirmation_required",
        title="Confirmation Required",
        detail=detail,
    )


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
    owner: AdmissionOwner = "ordinary_turn",
) -> ChatRequestAdmission:
    candidate = None
    if enabled:
        candidate = (
            _canonical_run_action_message(
                payload=payload,
                conversation_id=conversation_id,
                language=language,
            )
            if owner == "message_only"
            and payload.action is not None
            and payload.action.type == "run_backtest"
            else _ordinary_request_message(
                payload=payload,
                request=request,
                conversation_id=conversation_id,
                display_message=display_message,
                mention_provenance=mention_provenance,
            )
        )
    return ChatRequestAdmission(
        payload=payload,
        request=request,
        user_id=user_id,
        conversation_id=conversation_id,
        language=language,
        request_message_candidate=candidate,
        owner=owner,
    )


def _canonical_run_action_message(
    *,
    payload: ChatStreamRequest,
    conversation_id: str,
    language: str | None,
) -> Message:
    confirmation_id = confirmation_action_id(payload)
    if confirmation_id is None:
        raise RuntimeError("Run action admission requires a confirmation identity.")
    canonical_payload = ChatStreamRequest.model_validate(
        {
            "conversation_id": conversation_id,
            "language": language,
            "action": {
                "type": "run_backtest",
                "labelKey": _RUN_ACTION_LABEL_KEY,
                "payload": {"confirmation_id": confirmation_id},
                "presentation": "confirmation",
            },
        }
    )
    content = chat_display_message(canonical_payload, language=language or "en")
    assert canonical_payload.action is not None
    canonical_payload.action.label = content
    return prepare_message(
        conversation_id=conversation_id,
        role="user",
        content=content,
        metadata={"chat_action": persisted_chat_action(canonical_payload)},
        message_id=str(uuid5(_RUN_ACTION_MESSAGE_NAMESPACE, confirmation_id)),
    )


def _ordinary_request_message(
    *,
    payload: ChatStreamRequest,
    request: Request,
    conversation_id: str,
    display_message: str,
    mention_provenance: list[ResolutionProvenance],
) -> Message:
    user_metadata: dict[str, Any] = {
        "agent_runtime_turn": {
            "status": "started",
            "conversation_id": conversation_id,
            "request_id": request.state.request_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
    }
    if mention_provenance:
        user_metadata["mentions"] = [
            mention.model_dump(mode="python") for mention in payload.mentions
        ]
        user_metadata["resolution_provenance"] = [
            item.model_dump(mode="python") for item in mention_provenance
        ]
    if payload.action is not None:
        user_metadata["chat_action"] = persisted_chat_action(payload)
    return prepare_message(
        conversation_id=conversation_id,
        role="user",
        content=display_message,
        metadata=user_metadata,
    )
