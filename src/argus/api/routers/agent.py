from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from argus.agent_runtime.confirmation_artifacts import (
    confirmation_artifact_reference,
    confirmation_id_from_payload,
)
from argus.agent_runtime.resolution import mention_to_provenance
from argus.agent_runtime.result_followups import (
    compose_private_alpha_save_response,
    fallback_private_alpha_save_response,
)
from argus.agent_runtime.runtime import stream_agent_turn_events
from argus.agent_runtime.state.models import UserState
from argus.api import state as api_state
from argus.api.chat.actions import (
    chat_display_message,
    chat_request_message,
    is_cancel_confirmation_action,
    is_confirmation_action,
    is_result_action,
    run_for_result_action,
    stale_confirmation_action_message,
)
from argus.api.chat.artifacts import (
    result_fact_bank,
    result_followup_metadata_from_run,
    saved_strategy_metadata,
)
from argus.api.chat.backtest_jobs import (
    BacktestJobShadowContext,
    link_shadow_backtest_job_result,
    reset_backtest_job_shadow_context,
    set_backtest_job_shadow_context,
)
from argus.api.chat.breakdown import result_breakdown_message
from argus.api.chat.confirmation import runtime_confirmation_card
from argus.api.chat.onboarding import (
    parse_onboarding_control_message,
    persist_onboarding_update,
)
from argus.api.chat.persistence import persist_runtime_backtest_run
from argus.api.chat.recovery import (
    RuntimeFallbackContext,
    checkpoint_has_pending_confirmation,
    confirmation_metadata_fallback_context,
    failed_action_metadata_fallback_context,
    latest_result_fallback_context,
    pending_strategy_metadata_fallback_context,
    runtime_checkpoint_values,
)
from argus.api.chat.result_actions import (
    missing_refine_strategy_action_turn,
    refine_strategy_action_turn,
)
from argus.api.chat.retry import retry_last_turn_metadata
from argus.api.chat.route_receipts import persist_route_receipts
from argus.api.chat.strategies import save_strategy_from_run
from argus.api.chat.streaming import (
    runtime_result_card,
    runtime_result_envelope,
    runtime_result_message,
    runtime_stage_status,
    sse_data,
    sse_done,
    sse_keepalive,
)
from argus.api.chat.title_finalization import schedule_artifact_naming_after_stream
from argus.api.dependencies import current_user, dev_memory_fallback_enabled, problem
from argus.api.message_store import create_message, load_runtime_thread_history
from argus.api.naming import get_starter_prompts, resolve_language
from argus.api.schemas import BacktestRun, ChatStreamRequest, StarterPromptsResponse, User
from argus.domain.supabase_gateway import QuotaExceededError
from argus.llm.openrouter import (
    begin_openrouter_route_receipt_capture,
    end_openrouter_route_receipt_capture,
)

router = APIRouter(tags=["agent"])
RUNTIME_EVENT_TIMEOUT_SECONDS = 120.0
RUNTIME_EVENT_KEEPALIVE_SECONDS = 15.0


def _runtime_event_timeout_seconds() -> float:
    return _positive_float_env(
        "ARGUS_RUNTIME_EVENT_TIMEOUT_SECONDS",
        RUNTIME_EVENT_TIMEOUT_SECONDS,
        min_value=1.0,
    )


def _runtime_event_keepalive_seconds() -> float:
    timeout_seconds = _runtime_event_timeout_seconds()
    return min(
        timeout_seconds,
        _positive_float_env(
            "ARGUS_RUNTIME_EVENT_KEEPALIVE_SECONDS",
            RUNTIME_EVENT_KEEPALIVE_SECONDS,
            min_value=0.1,
        ),
    )


def _positive_float_env(name: str, default: float, *, min_value: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(value, min_value)


async def _cancel_runtime_event_task(
    runtime_event_task: asyncio.Task[dict[str, Any]],
) -> None:
    runtime_event_task.cancel()
    with suppress(asyncio.CancelledError, StopAsyncIteration):
        await runtime_event_task


async def _runtime_events_with_keepalive(
    runtime_events: AsyncIterator[dict[str, Any]],
) -> AsyncIterator[dict[str, Any] | None]:
    next_runtime_event: asyncio.Task[dict[str, Any]] | None = None
    next_runtime_event_started = time.monotonic()
    runtime_timeout_seconds = _runtime_event_timeout_seconds()
    runtime_keepalive_seconds = _runtime_event_keepalive_seconds()

    try:
        while True:
            if next_runtime_event is None:
                next_runtime_event = asyncio.create_task(anext(runtime_events))
                next_runtime_event_started = time.monotonic()
            try:
                elapsed_seconds = time.monotonic() - next_runtime_event_started
                remaining_seconds = runtime_timeout_seconds - elapsed_seconds
                if remaining_seconds <= 0:
                    raise asyncio.TimeoutError
                runtime_event = await asyncio.wait_for(
                    asyncio.shield(next_runtime_event),
                    timeout=min(runtime_keepalive_seconds, remaining_seconds),
                )
                next_runtime_event = None
            except asyncio.TimeoutError:
                if (
                    time.monotonic() - next_runtime_event_started
                    >= runtime_timeout_seconds
                ):
                    await _cancel_runtime_event_task(next_runtime_event)
                    next_runtime_event = None
                    raise asyncio.TimeoutError("agent_runtime_event_timeout") from None
                yield None
                continue
            except StopAsyncIteration:
                break
            yield runtime_event
    finally:
        if next_runtime_event is not None and not next_runtime_event.done():
            await _cancel_runtime_event_task(next_runtime_event)


def _strategies_enabled() -> bool:
    raw = os.getenv("ARGUS_STRATEGIES_ENABLED", "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _clean_optional_header(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _confirmation_artifact_id_from_runtime_result(
    runtime_result: dict[str, Any],
) -> str | None:
    references = runtime_result.get("artifact_references")
    if not isinstance(references, list):
        return None
    for reference in references:
        if not isinstance(reference, dict):
            continue
        if reference.get("artifact_kind") != "confirmation":
            continue
        artifact_id = reference.get("artifact_id")
        if isinstance(artifact_id, str) and artifact_id.strip():
            return artifact_id.strip()
    return None


def _confirmation_id_for_runtime_card(runtime_result: dict[str, Any]) -> str:
    payload = runtime_result.get("confirmation_payload")
    fallback = _confirmation_artifact_id_from_runtime_result(runtime_result)
    if isinstance(payload, dict):
        return confirmation_id_from_payload(payload, fallback=fallback)
    return fallback or api_state.store.new_id()


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
    clean_idempotency_key = _clean_optional_header(idempotency_key)
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
        except QuotaExceededError as exc:
            raise problem(
                request,
                status_code=429,
                code="too_many_requests",
                title="Quota Exceeded",
                detail=str(exc),
                headers={"Retry-After": "60"},
            ) from exc
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase usage counter failed; using dev memory fallback",
                error=str(exc),
                user_id=user.id,
                resource="chat_messages",
            )

    current_user_profile = None
    if api_state.supabase_gateway is not None:
        try:
            current_user_profile = api_state.supabase_gateway.get_user(user_id=user.id)
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase user read failed; using dev memory fallback",
                error=str(exc),
                user_id=user.id,
            )
    else:
        current_user_profile = api_state.store.users.get(user.id, user)
    if current_user_profile is None:
        current_user_profile = user

    request_message = chat_request_message(payload)
    display_message = chat_display_message(payload)
    onboarding_goal = parse_onboarding_control_message(request_message)

    conversation = None
    if api_state.supabase_gateway is not None:
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
            conversation = api_state.store.conversations.get(payload.conversation_id)
    else:
        conversation = api_state.store.conversations.get(payload.conversation_id)
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
    stale_confirmation_message = stale_confirmation_action_message(
        payload=payload,
        user_id=user.id,
        conversation_id=conversation.id,
    )
    if stale_confirmation_message is not None:
        runtime_fallback = RuntimeFallbackContext(
            recovery_message=stale_confirmation_message
        )
    elif is_confirmation_action(payload):
        metadata_fallback = confirmation_metadata_fallback_context(
            user_id=user.id,
            conversation_id=conversation.id,
        )
        if metadata_fallback is None and not checkpoint_has_pending_confirmation(
            checkpoint_values
        ):
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
        if metadata_fallback is not None:
            runtime_fallback = metadata_fallback
    elif is_result_action(payload):
        result_fallback = latest_result_fallback_context(
            user_id=user.id,
            conversation_id=conversation.id,
        )
        if result_fallback is not None:
            runtime_fallback = result_fallback
    elif payload.action is None:
        failed_fallback = failed_action_metadata_fallback_context(
            user_id=user.id,
            conversation_id=conversation.id,
        )
        if failed_fallback is not None:
            runtime_fallback = failed_fallback
        else:
            confirmation_fallback = confirmation_metadata_fallback_context(
                user_id=user.id,
                conversation_id=conversation.id,
            )
            if confirmation_fallback is not None:
                runtime_fallback = confirmation_fallback
            else:
                pending_fallback = pending_strategy_metadata_fallback_context(
                    user_id=user.id,
                    conversation_id=conversation.id,
                )
                if pending_fallback is not None:
                    runtime_fallback = pending_fallback
                else:
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
    cancel_confirmation_action = is_cancel_confirmation_action(payload)
    request_message_record = None
    if onboarding_goal is None and not cancel_confirmation_action:
        user_metadata: dict[str, Any] = {
            "agent_runtime_turn": {
                "status": "started",
                "conversation_id": conversation.id,
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
            user_metadata["chat_action"] = payload.action.model_dump(mode="python")
        request_message_record = create_message(
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
        naming_language = (
            payload.language
            or conversation.language
            or current_user_profile.language
            or "en"
        )

        def schedule_artifact_naming(
            *,
            assistant_message: str | None,
            current_run: BacktestRun | None = None,
            saved_strategy_id: str | None = None,
            message_id: str | None = None,
        ) -> None:
            try:
                schedule_artifact_naming_after_stream(
                    user_id=user.id,
                    conversation_id=conversation.id,
                    language=naming_language,
                    current_run=current_run,
                    saved_strategy_id=saved_strategy_id,
                    user_message=display_message,
                    assistant_message=assistant_message,
                    message_id=message_id,
                    run_id=current_run.id if current_run is not None else None,
                )
            except Exception:
                logger.opt(exception=True).warning(
                    "Artifact naming scheduling failed",
                    user_id=user.id,
                    conversation_id=conversation.id,
                    saved_strategy_id=saved_strategy_id,
                )

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

        if cancel_confirmation_action and payload.action is not None:
            action_payload = payload.action.payload
            raw_confirmation_id = action_payload.get(
                "confirmation_id"
            ) or action_payload.get("confirmationId")
            confirmation_id = (
                str(raw_confirmation_id).strip()
                if raw_confirmation_id is not None
                else ""
            )
            confirmation_cancelled = {
                "confirmation_id": confirmation_id,
            }
            artifact_event = {
                "type": "confirmation_cancelled",
                "confirmation_id": confirmation_id,
            }
            metadata = {
                "conversation_mode": "confirm",
                "agent_runtime_stage_outcome": "ready_to_respond",
                "chat_action": payload.action.model_dump(mode="python"),
                "artifact_event": artifact_event,
            }
            assistant_message = create_message(
                user_id=user.id,
                conversation_id=conversation.id,
                role="assistant",
                content="",
                metadata=metadata,
            )
            yield sse_data(
                {
                    "type": "final",
                    "payload": {
                        "stage_outcome": "ready_to_respond",
                        "assistant_response": "",
                        "message_id": assistant_message.id,
                        "confirmation_cancelled": confirmation_cancelled,
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
            elif not _strategies_enabled():
                run_fact_bank = result_fact_bank(run)
                metadata["result_fact_bank"] = run_fact_bank
                metadata["latest_run_id"] = run.id
                metadata["result_run_id"] = run.id
                metadata["result_strategy_id"] = run.strategy_id
                assistant_text = await compose_private_alpha_save_response(
                    metadata=result_followup_metadata_from_run(run),
                    user_message=chat_request_message(payload),
                )
                if assistant_text is None:
                    assistant_text = fallback_private_alpha_save_response()
            else:
                strategy = save_strategy_from_run(user=user, run=run)
                metadata.update(saved_strategy_metadata(run, strategy.id))
                metadata["result_fact_bank"] = result_fact_bank(run)
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
                        "latest_run_id": metadata.get("latest_run_id"),
                        "result_run_id": metadata.get("result_run_id"),
                        "result_strategy_id": metadata.get("result_strategy_id"),
                        "saved_strategy_id": metadata.get("saved_strategy_id"),
                    },
                }
            )
            yield sse_done()
            schedule_artifact_naming(
                assistant_message=assistant_text,
                current_run=run,
                saved_strategy_id=(
                    str(metadata["saved_strategy_id"])
                    if metadata.get("saved_strategy_id")
                    else None
                ),
                message_id=assistant_message.id,
            )
            return

        if payload.action is not None and payload.action.type == "show_breakdown":
            run = run_for_result_action(
                payload=payload,
                user=user,
                conversation_id=conversation.id,
            )
            yield sse_data({"type": "stage_start", "stage": "explain"})
            receipt_token = begin_openrouter_route_receipt_capture()
            try:
                assistant_text = result_breakdown_message(run)
            finally:
                route_receipts = end_openrouter_route_receipt_capture(receipt_token)
            metadata = {
                "conversation_mode": "result_review",
                "chat_action": payload.action.model_dump(mode="python"),
            }
            if run is not None:
                metadata["latest_run_id"] = run.id
                metadata["result_run_id"] = run.id
                metadata["result_strategy_id"] = run.strategy_id
                metadata["result_fact_bank"] = result_fact_bank(run)
            assistant_message = create_message(
                user_id=user.id,
                conversation_id=conversation.id,
                role="assistant",
                content=assistant_text,
                metadata=metadata,
            )
            persist_route_receipts(
                receipts=route_receipts,
                user_id=user.id,
                conversation_id=conversation.id,
                run_id=run.id if run is not None else None,
                message_id=assistant_message.id,
                metadata={"chat_action": payload.action.type},
            )
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
            schedule_artifact_naming(
                assistant_message=assistant_text,
                current_run=run,
                message_id=assistant_message.id,
            )
            return

        if payload.action is not None and payload.action.type == "refine_strategy":
            run = run_for_result_action(
                payload=payload,
                user=user,
                conversation_id=conversation.id,
                require_run_id=True,
            )
            turn = (
                missing_refine_strategy_action_turn(action=payload.action)
                if run is None
                else refine_strategy_action_turn(run=run, action=payload.action)
            )
            assistant_message = create_message(
                user_id=user.id,
                conversation_id=conversation.id,
                role="assistant",
                content=turn.assistant_text,
                metadata=turn.metadata,
            )
            final_payload = dict(turn.final_payload)
            final_payload["message_id"] = assistant_message.id
            yield sse_data({"type": "stage_start", "stage": turn.stage})
            yield sse_data({"type": "token", "content": turn.assistant_text})
            yield sse_data({"type": "final", "payload": final_payload})
            yield sse_done()
            schedule_artifact_naming(
                assistant_message=turn.assistant_text,
                current_run=run,
                message_id=assistant_message.id,
            )
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
        receipt_run_id: str | None = None
        receipt_message_id: str | None = None
        receipt_metadata: dict[str, Any] = {}

        receipt_token = begin_openrouter_route_receipt_capture()
        shadow_context_token = set_backtest_job_shadow_context(
            BacktestJobShadowContext(
                user_id=user.id,
                conversation_id=conversation.id,
                request_message_id=(
                    request_message_record.id if request_message_record else None
                ),
                confirmation_message_id=runtime_fallback.confirmation_message_id,
                idempotency_key=clean_idempotency_key,
                request_id=request.state.request_id,
                chat_action=action_context,
            )
        )
        try:
            runtime_events = stream_agent_turn_events(
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
            )
            final_seen = False
            async for runtime_event in _runtime_events_with_keepalive(runtime_events):
                if runtime_event is None:
                    yield sse_keepalive()
                    continue
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

                final_seen = True
                runtime_result = dict(runtime_event.get("payload") or {})
                stage_status = runtime_stage_status(runtime_result)
                assistant_text = runtime_result_message(runtime_result)
                confirmation_card = runtime_confirmation_card(
                    runtime_result,
                    confirmation_id=_confirmation_id_for_runtime_card(runtime_result),
                    conversation_id=conversation.id,
                    language=runtime_user.language_preference,
                )
                confirmation_anchor_text: str | None = None
                if confirmation_card is not None:
                    confirmation_anchor_text = str(confirmation_card["summary"])
                    assistant_text = None
                    runtime_result.pop("assistant_response", None)
                    runtime_result.pop("assistant_prompt", None)
                result_card = runtime_result_card(runtime_result)
                envelope = runtime_result_envelope(runtime_result)
                backtest_job = None
                raw_backtest_job = runtime_result.get("backtest_job")
                if isinstance(raw_backtest_job, dict):
                    backtest_job = dict(raw_backtest_job)
                final_response_payload = runtime_result.get("final_response_payload")
                if (
                    backtest_job is None
                    and isinstance(final_response_payload, dict)
                    and isinstance(final_response_payload.get("backtest_job"), dict)
                ):
                    backtest_job = dict(final_response_payload["backtest_job"])
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
                if payload.action is not None:
                    metadata["chat_action"] = payload.action.model_dump(mode="python")
                if runtime_result.get("resolution_provenance"):
                    metadata["resolution_provenance"] = runtime_result[
                        "resolution_provenance"
                    ]
                if isinstance(runtime_result.get("pending_strategy"), dict):
                    metadata["pending_strategy"] = runtime_result["pending_strategy"]
                if confirmation_card is not None:
                    metadata["confirmation_card"] = confirmation_card
                    if isinstance(runtime_result.get("confirmation_payload"), dict):
                        metadata["confirmation_payload"] = runtime_result[
                            "confirmation_payload"
                        ]
                        confirmation_reference = confirmation_artifact_reference(
                            confirmation_id=str(
                                confirmation_card.get("confirmation_id")
                                or confirmation_card.get("confirmationId")
                                or api_state.store.new_id()
                            ),
                            confirmation_payload=runtime_result["confirmation_payload"],
                            confirmation_card=confirmation_card,
                        )
                        metadata["active_confirmation_reference"] = (
                            confirmation_reference.model_dump(mode="python")
                        )
                        metadata["artifact_references"] = [
                            confirmation_reference.model_dump(mode="python")
                        ]
                        runtime_result["active_confirmation_reference"] = (
                            confirmation_reference.model_dump(mode="python")
                        )
                        runtime_result["artifact_references"] = [
                            confirmation_reference.model_dump(mode="python")
                        ]
                    runtime_result["confirmation"] = confirmation_card
                if result_card is not None:
                    metadata["result_card"] = result_card
                if backtest_job is not None:
                    metadata["backtest_job"] = backtest_job
                    metadata["backtest_job_id"] = backtest_job.get("id")
                    runtime_result["backtest_job"] = backtest_job
                latest_failed_action_reference = runtime_result.get(
                    "latest_failed_action_reference"
                )
                if isinstance(latest_failed_action_reference, dict):
                    metadata["latest_failed_action_reference"] = (
                        latest_failed_action_reference
                    )
                    failed_action_metadata = latest_failed_action_reference.get(
                        "metadata"
                    )
                    if isinstance(failed_action_metadata, dict):
                        metadata["failed_action"] = dict(failed_action_metadata)
                if run is not None:
                    link_shadow_backtest_job_result(
                        user_id=user.id,
                        run_id=run.id,
                        gateway=api_state.supabase_gateway,
                        dev_memory_fallback_enabled=dev_memory_fallback_enabled(),
                    )
                    receipt_run_id = run.id
                    result_card = run.conversation_result_card
                    metadata["result_card"] = result_card
                    runtime_result["result_card"] = result_card
                    final_response_payload = runtime_result.get("final_response_payload")
                    if isinstance(final_response_payload, dict):
                        final_response_payload["result_card"] = result_card
                    metadata["latest_run_id"] = run.id
                    metadata["result_run_id"] = run.id
                    metadata["result_strategy_id"] = run.strategy_id
                    metadata["result_conversation_id"] = run.conversation_id
                    metadata["result_fact_bank"] = result_fact_bank(run)
                    context_packets = run.conversation_result_card.get("context_packets")
                    if isinstance(context_packets, list):
                        metadata["context_packets"] = context_packets
                    runtime_result["run"] = run.model_dump(mode="json")

                streamed_text = "".join(streamed_text_parts).strip()
                if (
                    streamed_text
                    and confirmation_card is None
                    and run is None
                    and not assistant_text
                ):
                    assistant_text = streamed_text
                    runtime_result["assistant_response"] = streamed_text

                persisted_text = (
                    confirmation_anchor_text or assistant_text or streamed_text
                )
                assistant_message = None
                if persisted_text:
                    assistant_message = create_message(
                        user_id=user.id,
                        conversation_id=conversation.id,
                        role="assistant",
                        content=persisted_text,
                        metadata=metadata,
                    )
                    receipt_message_id = assistant_message.id
                receipt_metadata = {
                    "stage_outcome": stage_status,
                    "conversation_mode": metadata.get("conversation_mode"),
                }

                runtime_result["message_id"] = (
                    assistant_message.id if assistant_message is not None else None
                )
                if assistant_text and not runtime_result.get("assistant_response"):
                    runtime_result["assistant_response"] = assistant_text
                if (
                    not streamed_text_parts
                    and confirmation_card is None
                    and run is None
                    and assistant_text
                ):
                    yield sse_data({"type": "token", "content": assistant_text})
                yield sse_data({"type": "final", "payload": runtime_result})
                yield sse_done()
                schedule_artifact_naming(
                    assistant_message=persisted_text,
                    current_run=run,
                    message_id=(
                        assistant_message.id if assistant_message is not None else None
                    ),
                )
                return
            if not final_seen:
                raise RuntimeError("agent_runtime_missing_final")
        except Exception:
            logger.exception(
                "Agent runtime chat streaming failed",
                conversation_id=conversation.id,
            )
            assistant_text = (
                "Something went wrong. Your conversation is saved. " "Please try again."
            )
            failure_metadata: dict[str, Any] = {
                "conversation_mode": "recovery",
                "agent_runtime_stage_outcome": "agent_runtime_failure",
            }
            retry_metadata = retry_last_turn_metadata(
                payload=payload,
                request_message=request_message,
            )
            if retry_metadata is not None:
                failure_metadata.update(retry_metadata)
            assistant_message = create_message(
                user_id=user.id,
                conversation_id=conversation.id,
                role="assistant",
                content=assistant_text,
                metadata=failure_metadata,
            )
            receipt_message_id = assistant_message.id
            receipt_metadata = {
                "stage_outcome": "agent_runtime_failure",
                "conversation_mode": "recovery",
            }
            yield sse_data(
                {
                    "type": "error",
                    "code": "agent_runtime_failure",
                    "message": assistant_text,
                    "message_id": assistant_message.id,
                }
            )
            yield sse_done()
            return
        finally:
            reset_backtest_job_shadow_context(shadow_context_token)
            persist_route_receipts(
                receipts=end_openrouter_route_receipt_capture(receipt_token),
                user_id=user.id,
                conversation_id=conversation.id,
                run_id=receipt_run_id,
                message_id=receipt_message_id,
                metadata=receipt_metadata,
            )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers=headers,
    )
