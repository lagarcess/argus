from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from argus.agent_runtime.resolution import mention_to_provenance
from argus.agent_runtime.runtime import run_agent_turn, stream_agent_turn_events
from argus.agent_runtime.state.models import UserState
from argus.api import state as api_state
from argus.api.chat_service import (
    RuntimeFallbackContext,
    chat_display_message,
    chat_request_message,
    checkpoint_has_latest_result,
    checkpoint_has_pending_confirmation,
    confirmation_metadata_fallback_context,
    is_confirmation_action,
    latest_result_fallback_context,
    parse_onboarding_control_message,
    persist_onboarding_update,
    persist_runtime_backtest_run,
    result_breakdown_message,
    run_for_result_action,
    runtime_checkpoint_values,
    runtime_confirmation_card,
    runtime_result_card,
    runtime_result_envelope,
    runtime_result_message,
    runtime_stage_status,
    save_strategy_from_run,
    sse_data,
    sse_done,
)
from argus.api.dependencies import current_user, dev_memory_fallback_enabled, problem
from argus.api.message_store import create_message, load_runtime_thread_history
from argus.api.naming import get_starter_prompts, resolve_language
from argus.api.schemas import ChatStreamRequest, StarterPromptsResponse, User
from argus.domain.supabase_gateway import QuotaExceededError

router = APIRouter(tags=["agent"])


class InternalAgentRuntimeTurnRequest(BaseModel):
    user_id: str
    thread_id: str
    message: str


@router.post("/internal/agent-runtime/turn")
async def internal_agent_runtime_turn(
    payload: InternalAgentRuntimeTurnRequest,
) -> dict[str, Any]:
    return await run_agent_turn(
        workflow=api_state.get_agent_runtime_workflow(),
        user=UserState(user_id=payload.user_id),
        thread_id=payload.thread_id,
        message=payload.message,
    )


@router.get("/api/v1/chat/starter-prompts", response_model=StarterPromptsResponse)
def list_starter_prompts(
    user: User = Depends(current_user),  # noqa: B008
) -> StarterPromptsResponse:
    prompts = get_starter_prompts(user.onboarding.primary_goal)
    return StarterPromptsResponse(prompts=prompts)


@router.post("/api/v1/chat/stream")
async def chat_stream(
    payload: ChatStreamRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(current_user),  # noqa: B008
) -> StreamingResponse:
    del idempotency_key
    headers = {
        "X-Request-Id": request.state.request_id,
        "X-RateLimit-Limit": "200",
        "X-RateLimit-Remaining": "199",
        "X-RateLimit-Reset": "3600",
        "X-Accel-Buffering": "no",
    }
    if api_state.supabase_gateway is not None:
        try:
            api_state.supabase_gateway.check_and_increment_usage(
                user_id=user.id,
                resource="chat_messages",
                period="day",
                limit_count=200,
            )
            api_state.supabase_gateway.check_and_increment_usage(
                user_id=user.id,
                resource="chat_messages",
                period="minute",
                limit_count=10,
            )
        except QuotaExceededError as exc:
            raise problem(
                request,
                status_code=429,
                code="too_many_requests",
                title="Quota Exceeded",
                detail=str(exc),
                headers={"Retry-After": "60"},
            ) from exc

    current_user_profile = (
        api_state.supabase_gateway.get_user(user_id=user.id)
        if api_state.supabase_gateway is not None
        else api_state.store.users.get(user.id, user)
    )
    if current_user_profile is None:
        current_user_profile = user

    request_message = chat_request_message(payload)
    display_message = chat_display_message(payload)
    onboarding_goal = parse_onboarding_control_message(request_message)

    conversation = api_state.store.conversations.get(payload.conversation_id)
    if conversation is None and api_state.supabase_gateway is not None:
        try:
            conversation = api_state.supabase_gateway.get_conversation(
                user_id=user.id,
                conversation_id=payload.conversation_id,
            )
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase conversation read failed; using dev memory fallback",
                error=str(exc),
                conversation_id=payload.conversation_id,
            )
    if not conversation:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Conversation not found.",
        )
    recent_thread_history = load_runtime_thread_history(
        user_id=user.id,
        conversation_id=conversation.id,
    )
    workflow = api_state.get_agent_runtime_workflow(request)
    checkpoint_values = await runtime_checkpoint_values(
        workflow=workflow,
        conversation_id=conversation.id,
    )
    runtime_fallback = RuntimeFallbackContext()
    if is_confirmation_action(payload):
        if not checkpoint_has_pending_confirmation(checkpoint_values):
            metadata_fallback = confirmation_metadata_fallback_context(
                user_id=user.id,
                conversation_id=conversation.id,
            )
            if metadata_fallback is None:
                raise problem(
                    request,
                    status_code=409,
                    code="confirmation_required",
                    title="Confirmation Required",
                    detail=(
                        "There is no pending strategy confirmation to approve. "
                        "Describe the idea again and I will prepare a fresh confirmation."
                    ),
                )
            runtime_fallback = metadata_fallback
    elif not checkpoint_has_latest_result(checkpoint_values):
        result_fallback = latest_result_fallback_context(
            user_id=user.id,
            conversation_id=conversation.id,
        )
        if result_fallback is not None:
            runtime_fallback = result_fallback

    mention_provenance = [
        mention_to_provenance(mention.model_dump(mode="python"), index=index)
        for index, mention in enumerate(payload.mentions)
    ]
    if onboarding_goal is None:
        user_metadata = (
            {
                "mentions": [
                    mention.model_dump(mode="python") for mention in payload.mentions
                ],
                "resolution_provenance": [
                    item.model_dump(mode="python") for item in mention_provenance
                ],
            }
            if mention_provenance
            else None
        )
        create_message(
            user_id=user.id,
            conversation_id=conversation.id,
            role="user",
            content=display_message,
            metadata=user_metadata,
        )

    onboarding_required = current_user_profile.onboarding.stage in {
        "language_selection",
        "primary_goal_selection",
    }

    async def events() -> AsyncIterator[str]:
        if onboarding_required and onboarding_goal is None:
            lang = (
                payload.language
                or conversation.language
                or current_user_profile.language
                or "en"
            )
            is_es = resolve_language(lang) == "es-419"
            msg = (
                "\u00bfCu\u00e1l es tu objetivo principal ahora? No te preocupes, "
                "podr\u00e1s cambiarlo despu\u00e9s en Settings."
                if is_es
                else "What is your current primary goal? Don't worry, "
                "you can change it later in Settings."
            )
            yield sse_data({"type": "stage_start", "stage": "clarify"})
            assistant_message = create_message(
                user_id=user.id,
                conversation_id=conversation.id,
                role="assistant",
                content=msg,
            )
            yield sse_data({"type": "token", "content": msg})
            yield sse_data(
                {
                    "type": "final",
                    "payload": {
                        "stage_outcome": "await_user_reply",
                        "assistant_response": msg,
                        "message_id": assistant_message.id,
                    },
                }
            )
            yield sse_done()
            return

        if onboarding_goal is not None:
            persist_onboarding_update(
                current_user_profile,
                {
                    "stage": "ready",
                    "language_confirmed": True,
                    "primary_goal": onboarding_goal,
                    "completed": False,
                },
            )
            lang = (
                payload.language
                or conversation.language
                or current_user_profile.language
                or "en"
            )
            is_es = resolve_language(lang) == "es-419"
            if is_es:
                mapping = {
                    "learn_basics": (
                        "Perfecto. Te ayudar\u00e9 con ideas simples para empezar. "
                        "\u00bfQu\u00e9 activo te interesa?"
                    ),
                    "test_stock_idea": (
                        "Perfecto. Cu\u00e9ntame tu idea de acci\u00f3n y la probamos."
                    ),
                    "build_passive_strategy": (
                        "Perfecto. Podemos empezar con una idea pasiva tipo DCA."
                    ),
                    "explore_crypto": (
                        "Perfecto. Empecemos con una idea de cripto que quieras validar."
                    ),
                    "surprise_me": (
                        "Genial. Te propondr\u00e9 una idea inicial guiada para comenzar."
                    ),
                }
            else:
                mapping = {
                    "learn_basics": (
                        "I'll keep this beginner-friendly. You can ask me to explain an investing term, "
                        "walk through an asset in plain English, or set up a simple historical test. "
                        "If you name an asset like Apple or Bitcoin, I'll help you choose a sensible next step."
                    ),
                    "test_stock_idea": (
                        "Great. Share the stock idea you want to test and I'll run it."
                    ),
                    "build_passive_strategy": (
                        "Great. We can start with a passive DCA-style idea."
                    ),
                    "explore_crypto": (
                        "Great. Let's start with a crypto idea you want to validate."
                    ),
                    "surprise_me": "Great. I'll guide you with a starter idea to begin.",
                }
            follow_up = mapping.get(onboarding_goal, mapping["surprise_me"])
            assistant_message = create_message(
                user_id=user.id,
                conversation_id=conversation.id,
                role="assistant",
                content=follow_up,
            )
            yield sse_data({"type": "stage_start", "stage": "next_step"})
            yield sse_data({"type": "token", "content": follow_up})
            yield sse_data(
                {
                    "type": "final",
                    "payload": {
                        "stage_outcome": "ready_to_respond",
                        "assistant_response": follow_up,
                        "message_id": assistant_message.id,
                    },
                }
            )
            yield sse_done()
            return

        if runtime_fallback.recovery_message:
            assistant_text = runtime_fallback.recovery_message
            metadata = {
                "conversation_mode": "confirm",
                "agent_runtime_stage_outcome": "await_user_reply",
                "recovery_reason": "missing_confirmation_checkpoint",
            }
            if payload.action is not None:
                metadata["chat_action"] = payload.action.model_dump(mode="python")
            assistant_message = create_message(
                user_id=user.id,
                conversation_id=conversation.id,
                role="assistant",
                content=assistant_text,
                metadata=metadata,
            )
            yield sse_data({"type": "stage_start", "stage": "clarify"})
            yield sse_data({"type": "token", "content": assistant_text})
            yield sse_data(
                {
                    "type": "final",
                    "payload": {
                        "stage_outcome": "await_user_reply",
                        "assistant_response": assistant_text,
                        "message_id": assistant_message.id,
                    },
                }
            )
            yield sse_done()
            return

        if payload.action is not None and payload.action.type == "save_strategy":
            run = run_for_result_action(
                payload=payload,
                user=user,
                conversation_id=conversation.id,
                require_run_id=True,
            )
            metadata: dict[str, Any] = {
                "conversation_mode": "result_review",
                "chat_action": payload.action.model_dump(mode="python"),
            }
            if run is None:
                assistant_text = (
                    "I could not find the completed backtest to save. Run the "
                    "strategy again, then save it from the result card."
                )
            else:
                strategy = save_strategy_from_run(user=user, run=run)
                metadata["latest_run_id"] = run.id
                metadata["result_run_id"] = run.id
                metadata["result_strategy_id"] = strategy.id
                assistant_text = f"Saved {strategy.name} to Strategies."
            assistant_message = create_message(
                user_id=user.id,
                conversation_id=conversation.id,
                role="assistant",
                content=assistant_text,
                metadata=metadata,
            )
            yield sse_data({"type": "stage_start", "stage": "next_step"})
            yield sse_data({"type": "token", "content": assistant_text})
            yield sse_data(
                {
                    "type": "final",
                    "payload": {
                        "stage_outcome": "ready_to_respond",
                        "assistant_response": assistant_text,
                        "message_id": assistant_message.id,
                    },
                }
            )
            yield sse_done()
            return

        if payload.action is not None and payload.action.type == "show_breakdown":
            run = run_for_result_action(
                payload=payload,
                user=user,
                conversation_id=conversation.id,
            )
            assistant_text = result_breakdown_message(run)
            metadata = {
                "conversation_mode": "result_review",
                "chat_action": payload.action.model_dump(mode="python"),
            }
            if run is not None:
                metadata["latest_run_id"] = run.id
                metadata["result_run_id"] = run.id
                metadata["result_strategy_id"] = run.strategy_id
            assistant_message = create_message(
                user_id=user.id,
                conversation_id=conversation.id,
                role="assistant",
                content=assistant_text,
                metadata=metadata,
            )
            yield sse_data({"type": "stage_start", "stage": "explain"})
            yield sse_data({"type": "token", "content": assistant_text})
            yield sse_data(
                {
                    "type": "final",
                    "payload": {
                        "stage_outcome": "ready_to_respond",
                        "assistant_response": assistant_text,
                        "message_id": assistant_message.id,
                    },
                }
            )
            yield sse_done()
            return

        runtime_user = UserState(
            user_id=user.id,
            display_name=current_user_profile.display_name,
            language_preference=(
                payload.language
                or conversation.language
                or current_user_profile.language
                or "en"
            ),
        )
        action_context = (
            payload.action.model_dump(mode="python")
            if payload.action is not None
            else None
        )
        streamed_text_parts: list[str] = []

        try:
            async for runtime_event in stream_agent_turn_events(
                workflow=workflow,
                user=runtime_user,
                thread_id=conversation.id,
                message=request_message,
                recent_thread_history=recent_thread_history,
                context_hints=[
                    item.model_dump(mode="python") for item in mention_provenance
                ],
                action_context=action_context,
                fallback_latest_task_snapshot=runtime_fallback.latest_task_snapshot,
                fallback_selected_thread_metadata=(
                    runtime_fallback.selected_thread_metadata
                ),
                fallback_artifact_references=runtime_fallback.artifact_references,
                fallback_confirmation_payload=runtime_fallback.confirmation_payload,
            ):
                event_type = runtime_event.get("type")
                if event_type == "token":
                    content = str(runtime_event.get("content") or "")
                    if content:
                        streamed_text_parts.append(content)
                    yield sse_data(runtime_event)
                    continue
                if event_type in {"stage_start", "stage_outcome"}:
                    yield sse_data(runtime_event)
                    continue
                if event_type != "final":
                    continue

                runtime_result = dict(runtime_event.get("payload") or {})
                stage_status = runtime_stage_status(runtime_result)
                assistant_text = runtime_result_message(runtime_result)
                confirmation_card = runtime_confirmation_card(runtime_result)
                if confirmation_card is not None:
                    assistant_text = str(confirmation_card["summary"])
                result_card = runtime_result_card(runtime_result)
                envelope = runtime_result_envelope(runtime_result)
                run = None

                if result_card is not None:
                    run = persist_runtime_backtest_run(
                        user=user,
                        conversation=conversation,
                        result_card=result_card,
                        envelope=envelope,
                    )
                    persist_onboarding_update(
                        current_user_profile,
                        {
                            "stage": "completed",
                            "completed": True,
                            "language_confirmed": True,
                            "primary_goal": (
                                current_user_profile.onboarding.primary_goal
                                or "surprise_me"
                            ),
                        },
                    )

                metadata = {
                    "conversation_mode": (
                        "result_review"
                        if result_card is not None
                        else "confirm"
                        if stage_status == "await_approval"
                        else "setup"
                        if stage_status == "await_user_reply"
                        else "guide"
                    ),
                    "agent_runtime_stage_outcome": stage_status,
                }
                if runtime_result.get("resolution_provenance"):
                    metadata["resolution_provenance"] = runtime_result[
                        "resolution_provenance"
                    ]
                if confirmation_card is not None:
                    metadata["confirmation_card"] = confirmation_card
                    if isinstance(
                        runtime_result.get("confirmation_payload"), dict
                    ):
                        metadata["confirmation_payload"] = runtime_result[
                            "confirmation_payload"
                        ]
                    runtime_result["confirmation"] = confirmation_card
                if result_card is not None:
                    metadata["result_card"] = result_card
                if run is not None:
                    result_card = run.conversation_result_card
                    metadata["result_card"] = result_card
                    metadata["latest_run_id"] = run.id
                    metadata["result_run_id"] = run.id
                    metadata["result_strategy_id"] = run.strategy_id
                    metadata["result_conversation_id"] = run.conversation_id
                    runtime_result["run"] = run.model_dump(mode="json")

                persisted_text = assistant_text or "".join(streamed_text_parts).strip()
                assistant_message = None
                if persisted_text:
                    assistant_message = create_message(
                        user_id=user.id,
                        conversation_id=conversation.id,
                        role="assistant",
                        content=persisted_text,
                        metadata=metadata,
                    )

                runtime_result["message_id"] = (
                    assistant_message.id if assistant_message is not None else None
                )
                if (
                    not streamed_text_parts
                    and confirmation_card is None
                    and run is None
                    and assistant_text
                ):
                    yield sse_data({"type": "token", "content": assistant_text})
                yield sse_data({"type": "final", "payload": runtime_result})
                yield sse_done()
                return
        except Exception:
            logger.exception(
                "Agent runtime chat streaming failed",
                conversation_id=conversation.id,
            )
            yield sse_data(
                {
                    "type": "error",
                    "code": "agent_runtime_failure",
                    "message": (
                        "Something went wrong. Your conversation is saved. "
                        "Please try again."
                    ),
                }
            )
            yield sse_done()
            return

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers=headers,
    )
