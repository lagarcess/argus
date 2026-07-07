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

from argus.agent_runtime.recovery_messages import recovery_message, recovery_state
from argus.agent_runtime.resolution import mention_to_provenance
from argus.agent_runtime.runtime import stream_agent_turn_events
from argus.agent_runtime.state.models import UserState
from argus.api import state as api_state
from argus.api.chat.actions import (
    chat_display_message,
    chat_request_message,
    confirmation_action_id,
    is_cancel_confirmation_action,
    is_confirmation_action,
    is_result_action,
    missing_run_confirmation_action_id_message,
    recent_metadata_invalidates_confirmation,
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
from argus.api.chat.measurement_events import (
    schedule_runtime_measurement_events_after_stream,
)
from argus.api.chat.onboarding import (
    parse_onboarding_control_message,
    persist_onboarding_update,
)
from argus.api.chat.recovery import (
    RuntimeFallbackContext,
    _recent_messages_for_conversation,
    checkpoint_has_pending_confirmation,
    confirmation_metadata_fallback_context,
    failed_action_metadata_fallback_context,
    latest_result_fallback_context,
    mark_terminal_runtime_failure_checkpoint,
    pending_strategy_metadata_fallback_context,
    runtime_checkpoint_values,
)
from argus.api.chat.retry import retry_last_turn_metadata
from argus.api.chat.route_receipts import persist_route_receipts
from argus.api.chat.runtime_worker import (
    runtime_worker_enabled,
    threaded_runtime_event_source,
)
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
from argus.api.message_store import (
    create_message,
    latest_unresolved_terminal_runtime_failure_metadata,
    load_runtime_thread_history,
)
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


class RuntimeEventTimeoutError(asyncio.TimeoutError):
    def __init__(self, diagnostics: dict[str, Any]) -> None:
        super().__init__("agent_runtime_event_timeout")
        self.diagnostics = diagnostics


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
    last_event: dict[str, str] | None = None
    event_count = 0

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
                    elapsed_seconds = time.monotonic() - next_runtime_event_started
                    await _cancel_runtime_event_task(next_runtime_event)
                    next_runtime_event = None
                    raise RuntimeEventTimeoutError(
                        {
                            "code": "agent_runtime_event_timeout",
                            "timeout_seconds": runtime_timeout_seconds,
                            "elapsed_seconds": round(elapsed_seconds, 3),
                            "keepalive_seconds": runtime_keepalive_seconds,
                            "event_count": event_count,
                            "last_event": last_event,
                        }
                    ) from None
                yield None
                continue
            except StopAsyncIteration:
                break
            event_count += 1
            last_event = _runtime_event_boundary(runtime_event)
            yield runtime_event
    finally:
        if next_runtime_event is not None and not next_runtime_event.done():
            await _cancel_runtime_event_task(next_runtime_event)


def _runtime_event_boundary(runtime_event: dict[str, Any]) -> dict[str, str]:
    boundary = {"type": str(runtime_event.get("type") or "unknown")}
    stage = runtime_event.get("stage")
    if stage not in (None, "", [], {}):
        boundary["stage"] = str(stage)
    outcome = runtime_event.get("outcome")
    if outcome not in (None, "", [], {}):
        boundary["outcome"] = str(outcome)
    return boundary


def _runtime_failure_diagnostics(exc: BaseException) -> dict[str, Any] | None:
    diagnostics = getattr(exc, "diagnostics", None)
    return dict(diagnostics) if isinstance(diagnostics, dict) else None


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
    from argus.agent_runtime.confirmation_artifacts import confirmation_id_from_payload

    payload = runtime_result.get("confirmation_payload")
    fallback = _confirmation_artifact_id_from_runtime_result(runtime_result)
    if isinstance(payload, dict):
        return confirmation_id_from_payload(payload, fallback=fallback)
    return fallback or api_state.store.new_id()


async def compose_private_alpha_save_response(**kwargs: Any) -> str | None:
    from argus.agent_runtime.result_followups import (
        compose_private_alpha_save_response as _compose_private_alpha_save_response,
    )

    return await _compose_private_alpha_save_response(**kwargs)


def fallback_private_alpha_save_response(language: str | None = None) -> str:
    from argus.agent_runtime.result_followups import (
        fallback_private_alpha_save_response as _fallback_private_alpha_save_response,
    )

    return _fallback_private_alpha_save_response(language=language)


def result_breakdown_message(run: BacktestRun | None, *, language: str = "en") -> str:
    from argus.api.chat.breakdown import (
        result_breakdown_message as _result_breakdown_message,
    )

    return _result_breakdown_message(run, language=language)


def result_breakdown_message_with_metadata(
    run: BacktestRun | None,
    *,
    language: str = "en",
) -> Any:
    from argus.api.chat.breakdown import (
        result_breakdown_message_with_metadata as _result_breakdown_message_with_metadata,
    )

    return _result_breakdown_message_with_metadata(run, language=language)


def _result_action_request_type(runtime_result: dict[str, Any]) -> str | None:
    request = runtime_result.get("result_action_request")
    if not isinstance(request, dict):
        return None
    action_type = request.get("type")
    if action_type in {"show_breakdown", "save_strategy"}:
        return str(action_type)
    return None


def _missing_result_action_run_message(
    *,
    action_type: str,
    language: str | None,
) -> str:
    is_es = str(language or "").lower().startswith("es")
    if action_type == "save_strategy":
        if is_es:
            return (
                "No pude encontrar el backtest completado para guardarlo. "
                "Ejecuta la estrategia de nuevo y luego guárdala desde la "
                "tarjeta de resultado."
            )
        return (
            "I could not find the completed backtest to save. Run the strategy "
            "again, then save it from the result card."
        )
    if is_es:
        return (
            "No pude encontrar el backtest completado para explicarlo. Ejecuta "
            "la estrategia de nuevo y luego usa Explicar resultado desde la "
            "tarjeta de resultado."
        )
    return (
        "I could not find the completed backtest to explain. Run the strategy "
        "again, then explain it from the result card."
    )


@router.get("/api/v1/chat/starter-prompts", response_model=StarterPromptsResponse)
def list_starter_prompts(
    user: User = Depends(current_user),  # noqa: B008
) -> StarterPromptsResponse:
    prompts = get_starter_prompts(user.onboarding.primary_goal, user.language)
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
        "X-Accel-Buffering": "no",
    }
    if api_state.supabase_gateway is not None:
        try:
            api_state.supabase_gateway.check_and_increment_usage_limits(
                user_id=user.id,
                resource="chat_messages",
                limits=[("day", 200), ("hour", 60)],
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

    language = payload.language or current_user_profile.language or "en"
    request_message = chat_request_message(payload, language=language)
    display_message = chat_display_message(payload, language=language)
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
    mention_provenance = [
        mention_to_provenance(mention.model_dump(mode="python"), index=index)
        for index, mention in enumerate(payload.mentions)
    ]
    cancel_confirmation_action = is_cancel_confirmation_action(payload)
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

    def persist_request_message() -> Any | None:
        if onboarding_goal is not None or cancel_confirmation_action:
            return None
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
        return create_message(
            user_id=user.id,
            conversation_id=conversation.id,
            role="user",
            content=display_message,
            metadata=user_metadata,
        )

    workflow: Any | None = None
    try:
        workflow = api_state.get_agent_runtime_workflow(request)
        terminal_failure_metadata = latest_unresolved_terminal_runtime_failure_metadata(
            user_id=user.id,
            conversation_id=conversation.id,
        )
        if terminal_failure_metadata is not None:
            await mark_terminal_runtime_failure_checkpoint(
                workflow=workflow,
                conversation_id=conversation.id,
                user=runtime_user,
                message=request_message,
                recent_thread_history=recent_thread_history,
                failure_metadata=terminal_failure_metadata,
            )
        checkpoint_values = await runtime_checkpoint_values(
            workflow=workflow,
            conversation_id=conversation.id,
        )
    except Exception:
        logger.exception(
            "Agent runtime initialization failed",
            conversation_id=conversation.id,
        )
        persist_request_message()
        language = payload.language or conversation.language or current_user_profile.language
        assistant_text = recovery_message("runtime_failure", language=language)
        retry_metadata = retry_last_turn_metadata(
            payload=payload,
            request_message=request_message,
        )
        recovery = recovery_state(
            "runtime_failure",
            language=language,
            retryable=retry_metadata is not None,
        )
        failure_metadata: dict[str, Any] = {
            "conversation_mode": "recovery",
            "agent_runtime_stage_outcome": "agent_runtime_failure",
            "agent_runtime_turn": {
                "status": "failed",
                "terminal": True,
                "conversation_id": conversation.id,
                "request_id": request.state.request_id,
            },
            "recovery": recovery,
        }
        if retry_metadata is not None:
            failure_metadata.update(retry_metadata)
        if workflow is not None:
            await mark_terminal_runtime_failure_checkpoint(
                workflow=workflow,
                conversation_id=conversation.id,
                user=runtime_user,
                message=request_message,
                recent_thread_history=recent_thread_history,
                failure_metadata=failure_metadata,
            )
        retry_last_turn = (
            retry_metadata.get("retry_last_turn")
            if isinstance(retry_metadata, dict)
            else None
        )
        assistant_message = create_message(
            user_id=user.id,
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_text,
            metadata=failure_metadata,
        )

        async def initialization_failure_events() -> AsyncIterator[str]:
            yield sse_data(
                {
                    "type": "error",
                    "code": "agent_runtime_failure",
                    "message": assistant_text,
                    "message_id": assistant_message.id,
                    "recovery": recovery,
                    **(
                        {"retry_last_turn": retry_last_turn}
                        if isinstance(retry_last_turn, dict)
                        else {}
                    ),
                }
            )
            yield sse_done()

        return StreamingResponse(
            initialization_failure_events(),
            media_type="text/event-stream",
            headers=headers,
        )
    runtime_fallback = RuntimeFallbackContext()
    confirmation_action_messages = (
        _recent_messages_for_conversation(
            user_id=user.id,
            conversation_id=conversation.id,
            limit=20,
        )
        if is_confirmation_action(payload)
        else None
    )
    stale_confirmation_message = stale_confirmation_action_message(
        payload=payload,
        user_id=user.id,
        conversation_id=conversation.id,
        recent_messages=confirmation_action_messages,
        language=language,
    )
    if stale_confirmation_message is not None:
        runtime_fallback = RuntimeFallbackContext(
            recovery_message=stale_confirmation_message,
            recovery=recovery_state(
                "confirmation_action_stale_card",
                language=language,
                retryable=False,
            ),
        )
    elif is_confirmation_action(payload):
        metadata_fallback = confirmation_metadata_fallback_context(
            user_id=user.id,
            conversation_id=conversation.id,
            recent_messages=confirmation_action_messages,
            language=language,
        )
        missing_run_confirmation_action_id = (
            payload.action is not None
            and payload.action.type == "run_backtest"
            and confirmation_action_id(payload) is None
        )
        if metadata_fallback is not None and metadata_fallback.recovery_message:
            runtime_fallback = metadata_fallback
        elif metadata_fallback is None and not checkpoint_has_pending_confirmation(
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
        elif metadata_fallback is None and recent_metadata_invalidates_confirmation(
            confirmation_action_messages
        ):
            raise problem(
                request,
                status_code=409,
                code="confirmation_required",
                title="Confirmation Required",
                detail=(
                    "That confirmation is no longer active. Describe the idea again "
                    "and I will prepare a fresh confirmation."
                ),
            )
        elif missing_run_confirmation_action_id:
            runtime_fallback = RuntimeFallbackContext(
                recovery_message=missing_run_confirmation_action_id_message(language),
                recovery=recovery_state(
                    "confirmation_action_missing_identity",
                    language=language,
                    retryable=False,
                ),
            )
        elif metadata_fallback is not None:
            runtime_fallback = metadata_fallback
    elif is_result_action(payload):
        result_fallback = latest_result_fallback_context(
            user_id=user.id,
            conversation_id=conversation.id,
        )
        if result_fallback is not None:
            runtime_fallback = result_fallback
    elif payload.action is not None and payload.action.type == "retry_failed_action":
        failed_fallback = failed_action_metadata_fallback_context(
            user_id=user.id,
            conversation_id=conversation.id,
        )
        if failed_fallback is not None:
            runtime_fallback = failed_fallback
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
                language=language,
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
    request_message_record = persist_request_message()

    # Onboarding feature flag on the API service. Default enabled so prod/QA/tests keep the
    # flow; dev mode sets it false. The deployed API must set this to match the web
    # service's NEXT_PUBLIC_PRIVATE_ALPHA_ONBOARDING_ENABLED — enforced by the API release
    # env audit in .github/render-env-sync.sh — so onboarding-off is honored on the API,
    # not just the frontend. (Deliberately NOT read from the NEXT_PUBLIC_* var: that frontend
    # flag is false in .env, which would disable the onboarding flow in dev/QA and tests.)
    onboarding_enabled = (
        os.getenv("ARGUS_PRIVATE_ALPHA_ONBOARDING_ENABLED", "true").strip().lower()
        != "false"
    )
    onboarding_required = onboarding_enabled and (
        current_user_profile.onboarding.stage
        in {"language_selection", "primary_goal_selection"}
    )

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
                        "walk through an asset in plain language, or set up a simple historical test. "
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
            if runtime_fallback.recovery is not None:
                metadata["recovery"] = dict(runtime_fallback.recovery)
            assistant_message = create_message(
                user_id=user.id,
                conversation_id=conversation.id,
                role="assistant",
                content=assistant_text,
                metadata=metadata,
            )
            yield sse_data({"type": "stage_start", "stage": "clarify"})
            if runtime_fallback.recovery is None:
                yield sse_data({"type": "token", "content": assistant_text})
            yield sse_data(
                {
                    "type": "final",
                    "payload": {
                        "stage_outcome": "await_user_reply",
                        "assistant_response": assistant_text,
                        "message_id": assistant_message.id,
                        **(
                            {"recovery": runtime_fallback.recovery}
                            if runtime_fallback.recovery is not None
                            else {}
                        ),
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
            def runtime_event_source(
                active_workflow: Any,
            ) -> AsyncIterator[dict[str, Any]]:
                return stream_agent_turn_events(
                    workflow=active_workflow,
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

            async def isolated_runtime_event_source() -> AsyncIterator[dict[str, Any]]:
                async with api_state.isolated_agent_runtime_workflow() as active_workflow:
                    async for event in runtime_event_source(active_workflow):
                        yield event

            runtime_events = (
                threaded_runtime_event_source(isolated_runtime_event_source)
                if runtime_worker_enabled()
                else runtime_event_source(workflow)
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
                from argus.api.chat.confirmation import runtime_confirmation_card

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
                result_action_run = None
                saved_strategy_id_for_naming: str | None = None
                result_action_type = _result_action_request_type(runtime_result)
                if (
                    result_action_type is None
                    and payload.action is not None
                    and payload.action.presentation == "result"
                    and payload.action.type in {"show_breakdown", "save_strategy"}
                    and (not assistant_text or stage_status == "await_approval")
                ):
                    result_action_type = payload.action.type

                if result_card is not None:
                    from argus.api.chat.persistence import persist_runtime_backtest_run

                    run = persist_runtime_backtest_run(
                        user=user,
                        conversation=conversation,
                        result_card=result_card,
                        envelope=envelope,
                        quick_take=assistant_text,
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
                        if result_card is not None or result_action_type is not None
                        else "confirm"
                        if stage_status == "await_approval"
                        else "setup"
                        if stage_status == "await_user_reply"
                        else "guide"
                    ),
                    "agent_runtime_stage_outcome": stage_status,
                    "agent_runtime_turn": {
                        "status": "succeeded",
                        "terminal": True,
                        "conversation_id": conversation.id,
                        "request_id": request.state.request_id,
                    },
                }
                if payload.action is not None:
                    metadata["chat_action"] = payload.action.model_dump(mode="python")
                if result_action_type is not None and payload.action is not None:
                    confirmation_card = None
                    confirmation_anchor_text = None
                    runtime_result.pop("confirmation", None)
                    runtime_result.pop("confirmation_payload", None)
                    runtime_result.pop("active_confirmation_reference", None)
                    result_action_run = run_for_result_action(
                        payload=payload,
                        user=user,
                        conversation_id=conversation.id,
                        require_run_id=True,
                    )
                    if result_action_type == "show_breakdown":
                        yield sse_data({"type": "stage_start", "stage": "explain"})
                        breakdown_message = result_breakdown_message_with_metadata(
                            result_action_run,
                            language=runtime_user.language_preference,
                        )
                        assistant_text = breakdown_message.text
                        metadata["result_breakdown_source"] = breakdown_message.source
                        metadata["result_breakdown_fallback_used"] = (
                            breakdown_message.fallback_used
                        )
                        if breakdown_message.failure_mode is not None:
                            metadata["result_breakdown_failure_mode"] = (
                                breakdown_message.failure_mode
                            )
                    elif result_action_type == "save_strategy":
                        yield sse_data({"type": "stage_start", "stage": "next_step"})
                        if result_action_run is None:
                            assistant_text = _missing_result_action_run_message(
                                action_type=result_action_type,
                                language=runtime_user.language_preference,
                            )
                        elif not _strategies_enabled():
                            assistant_text = await compose_private_alpha_save_response(
                                metadata=result_followup_metadata_from_run(
                                    result_action_run
                                ),
                                user_message=request_message,
                            )
                            if assistant_text is None:
                                assistant_text = fallback_private_alpha_save_response(
                                    language=runtime_user.language_preference
                                )
                        else:
                            strategy = save_strategy_from_run(
                                user=user,
                                run=result_action_run,
                            )
                            saved_strategy_id_for_naming = strategy.id
                            metadata.update(
                                saved_strategy_metadata(result_action_run, strategy.id)
                            )
                            assistant_text = f"Saved {strategy.name} to Strategies."
                    if assistant_text:
                        runtime_result["assistant_response"] = assistant_text
                    if result_action_run is not None:
                        receipt_run_id = result_action_run.id
                        metadata["latest_run_id"] = result_action_run.id
                        metadata["result_run_id"] = result_action_run.id
                        metadata["result_strategy_id"] = result_action_run.strategy_id
                        metadata["result_fact_bank"] = result_fact_bank(result_action_run)
                        runtime_result["latest_run_id"] = result_action_run.id
                        runtime_result["result_run_id"] = result_action_run.id
                        runtime_result["result_strategy_id"] = (
                            result_action_run.strategy_id
                        )
                        if saved_strategy_id_for_naming is not None:
                            runtime_result["saved_strategy_id"] = (
                                saved_strategy_id_for_naming
                            )
                            runtime_result["result_strategy_id"] = (
                                saved_strategy_id_for_naming
                            )
                for key in (
                    "latest_run_id",
                    "result_run_id",
                    "result_strategy_id",
                    "result_conversation_id",
                    "result_fact_bank",
                    "response_intent",
                ):
                    value = runtime_result.get(key)
                    if value is not None:
                        metadata[key] = value
                if runtime_result.get("resolution_provenance"):
                    metadata["resolution_provenance"] = runtime_result[
                        "resolution_provenance"
                    ]
                if isinstance(runtime_result.get("pending_strategy"), dict):
                    metadata["pending_strategy"] = runtime_result["pending_strategy"]
                if confirmation_card is not None:
                    metadata["confirmation_card"] = confirmation_card
                    if isinstance(runtime_result.get("confirmation_payload"), dict):
                        from argus.agent_runtime.confirmation_artifacts import (
                            confirmation_artifact_reference,
                        )

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
                retry_last_turn = runtime_result.get("retry_last_turn")
                if isinstance(retry_last_turn, dict):
                    metadata["retry_last_turn"] = dict(retry_last_turn)
                recovery = runtime_result.get("recovery")
                if isinstance(recovery, dict):
                    metadata["recovery"] = dict(recovery)
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
                if not (
                    persisted_text
                    or confirmation_card is not None
                    or run is not None
                    or backtest_job is not None
                ):
                    logger.warning(
                        "Agent runtime returned no visible terminal state",
                        conversation_id=conversation.id,
                        request_id=request.state.request_id,
                        stage_outcome=stage_status,
                        final_payload_keys=sorted(runtime_result.keys()),
                    )
                    raise RuntimeError("agent_runtime_empty_final")
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
                    "request_id": request.state.request_id,
                    "source": "api_turn",
                    "stage_outcome": stage_status,
                    "conversation_mode": metadata.get("conversation_mode"),
                }
                if result_action_type is not None:
                    receipt_metadata["chat_action"] = result_action_type

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
                schedule_runtime_measurement_events_after_stream(
                    user_id=user.id,
                    conversation_id=conversation.id,
                    runtime_result=runtime_result,
                    metadata=metadata,
                )
                schedule_artifact_naming(
                    assistant_message=persisted_text,
                    current_run=result_action_run or run,
                    saved_strategy_id=saved_strategy_id_for_naming,
                    message_id=(
                        assistant_message.id if assistant_message is not None else None
                    ),
                )
                return
            if not final_seen:
                raise RuntimeError("agent_runtime_missing_final")
        except Exception as exc:
            runtime_diagnostics = _runtime_failure_diagnostics(exc)
            logger.exception(
                "Agent runtime chat streaming failed",
                conversation_id=conversation.id,
                runtime_diagnostics=runtime_diagnostics,
            )
            assistant_text = recovery_message(
                "runtime_failure",
                language=runtime_user.language_preference,
            )
            failure_metadata: dict[str, Any] = {
                "conversation_mode": "recovery",
                "agent_runtime_stage_outcome": "agent_runtime_failure",
                "agent_runtime_turn": {
                    "status": "failed",
                    "terminal": True,
                    "conversation_id": conversation.id,
                    "request_id": request.state.request_id,
                },
            }
            if runtime_diagnostics is not None:
                failure_metadata["runtime_diagnostics"] = runtime_diagnostics
            retry_metadata = retry_last_turn_metadata(
                payload=payload,
                request_message=request_message,
            )
            recovery = recovery_state(
                "runtime_failure",
                language=runtime_user.language_preference,
                retryable=retry_metadata is not None,
            )
            failure_metadata["recovery"] = recovery
            if retry_metadata is not None:
                failure_metadata.update(retry_metadata)
            await mark_terminal_runtime_failure_checkpoint(
                workflow=workflow,
                conversation_id=conversation.id,
                user=runtime_user,
                message=request_message,
                recent_thread_history=recent_thread_history,
                failure_metadata=failure_metadata,
            )
            retry_last_turn = (
                retry_metadata.get("retry_last_turn")
                if isinstance(retry_metadata, dict)
                else None
            )
            assistant_message = create_message(
                user_id=user.id,
                conversation_id=conversation.id,
                role="assistant",
                content=assistant_text,
                metadata=failure_metadata,
            )
            receipt_message_id = assistant_message.id
            receipt_metadata = {
                "request_id": request.state.request_id,
                "source": "api_turn",
                "stage_outcome": "agent_runtime_failure",
                "conversation_mode": "recovery",
            }
            if runtime_diagnostics is not None:
                receipt_metadata["runtime_diagnostics"] = runtime_diagnostics
            yield sse_data(
                {
                    "type": "error",
                    "code": "agent_runtime_failure",
                    "message": assistant_text,
                    "message_id": assistant_message.id,
                    "recovery": recovery,
                    **(
                        {"retry_last_turn": retry_last_turn}
                        if isinstance(retry_last_turn, dict)
                        else {}
                    ),
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
