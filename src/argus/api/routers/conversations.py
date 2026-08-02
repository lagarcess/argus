from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from loguru import logger

from argus.api import state as api_state
from argus.api.chat.confirmation import public_confirmation_projection
from argus.api.chat.legacy_onboarding_markers import is_legacy_onboarding_marker
from argus.api.chat.turn_lifecycle_projection import (
    reconcile_and_project_chat_turns,
)
from argus.api.conversation_activity import conversation_activity_service
from argus.api.dependencies import (
    current_user,
    dev_memory_fallback_enabled,
    problem,
    require_account_capability,
)
from argus.api.guest_access import account_context
from argus.api.memory_run_dossiers import list_memory_run_dossier_source_rows
from argus.api.message_store import (
    memory_conversation,
    reconcile_reload_message_metadata,
)
from argus.api.pagination import decode_cursor, encode_cursor, invalid_cursor_problem
from argus.api.schemas import (
    BulkConversationDeleteResponse,
    Conversation,
    ConversationCreate,
    ConversationPatch,
    ConversationResponse,
    Message,
    PaginatedConversations,
    PaginatedMessages,
    PaginatedRunDossiers,
    SuccessResponse,
    User,
)
from argus.domain.backtest_admission import CHAT_RUN_SCOPE
from argus.domain.backtest_message_projection import (
    backtest_job_action_confirmation_ids,
    hydrate_backtest_job_action_messages,
    represented_backtest_job_request_ids,
)
from argus.domain.postgres_run_dossier_reader import RunDossierCursorError
from argus.domain.run_dossiers import project_run_dossier
from argus.domain.store import utcnow
from argus.domain.supabase_gateway import (
    ConversationCursorError,
    MessageAnchorError,
    MessageCursorError,
)

router = APIRouter(prefix="/api/v1", tags=["conversations"])


def _with_activity(
    conversation: Conversation,
    *,
    user_id: str,
    reconcile: bool = False,
) -> Conversation:
    activity = conversation_activity_service.project(
        user_id=user_id,
        conversation_ids=[conversation.id],
        reconcile=reconcile,
    )[conversation.id]
    return conversation.model_copy(update={"activity": activity})


def _memory_conversation_owned_by(
    conversation_id: str,
    user_id: str,
    *,
    allow_unowned: bool,
) -> bool:
    owner_id = api_state.store.conversation_owners.get(conversation_id)
    if owner_id is None:
        return allow_unowned
    return owner_id == user_id


def _public_message_projection(messages: list[Message]) -> list[Message]:
    return [
        message.model_copy(
            update={"metadata": public_confirmation_projection(message.metadata)}
        )
        for message in messages
        if not (message.role == "user" and is_legacy_onboarding_marker(message.content))
    ]


def _project_backtest_job_actions(
    *,
    user_id: str,
    conversation_id: str,
    messages: list[Message],
    represented_request_ids: set[str],
) -> list[Message]:
    gateway = api_state.supabase_gateway
    list_reservations = getattr(gateway, "list_backtest_job_reservations", None)
    if gateway is None or list_reservations is None:
        return messages

    confirmation_ids = backtest_job_action_confirmation_ids(
        messages,
        represented_request_ids=represented_request_ids,
    )
    if not confirmation_ids:
        return messages
    jobs = list_reservations(
        user_id=user_id,
        conversation_id=conversation_id,
        operation_scope=CHAT_RUN_SCOPE,
        idempotency_keys=confirmation_ids,
    )
    jobs_by_action = {
        str(job.get("idempotency_key") or "").strip(): job
        for job in jobs
        if isinstance(job, dict) and str(job.get("idempotency_key") or "").strip()
    }

    return hydrate_backtest_job_action_messages(
        messages,
        jobs_by_action=jobs_by_action,
        represented_request_ids=represented_request_ids,
    )


@router.post("/conversations", response_model=ConversationResponse)
def create_conversation(
    payload: ConversationCreate,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> ConversationResponse:
    title = payload.title or "New idea"
    title_source = "user_renamed" if payload.title else "system_default"
    language = payload.language or user.language
    if api_state.supabase_gateway is not None:
        context = account_context(request)
        if context.kind == "guest":
            workspace = api_state.supabase_gateway.get_active_guest_workspace(
                user_id=user.id,
                at=datetime.now(timezone.utc),
            )
            if workspace is None:
                raise problem(
                    request,
                    status_code=403,
                    code="guest_session_expired",
                    title="Guest Session Expired",
                    detail="This temporary guest session is no longer available.",
                )
            if workspace.conversation_id is not None:
                existing = api_state.supabase_gateway.get_conversation(
                    user_id=user.id,
                    conversation_id=workspace.conversation_id,
                )
                if existing is not None:
                    has_user_message = (
                        api_state.supabase_gateway.conversation_has_user_message(
                            user_id=user.id,
                            conversation_id=workspace.conversation_id,
                        )
                    )
                    if not has_user_message:
                        return ConversationResponse(
                            conversation=_with_activity(existing, user_id=user.id)
                        )
                    require_account_capability(
                        request,
                        "can_create_additional_conversation",
                        detail=(
                            "Sign in to keep this temporary conversation "
                            "and start another."
                        ),
                        reason="new_conversation",
                    )
        try:
            conversation = api_state.supabase_gateway.create_conversation(
                user_id=user.id,
                title=title,
                title_source=title_source,
                language=language,
            )
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase conversation create failed; using dev memory fallback",
                error=str(exc),
            )
            conversation = memory_conversation(
                title=title,
                title_source=title_source,
                language=language,
                user_id=user.id,
            )
    else:
        conversation = memory_conversation(
            title=title,
            title_source=title_source,
            language=language,
            user_id=user.id,
        )
    return ConversationResponse(
        conversation=_with_activity(conversation, user_id=user.id)
    )


@router.post(
    "/conversations/guest/replace",
    response_model=ConversationResponse,
)
def replace_guest_conversation(
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> ConversationResponse:
    context = account_context(request)
    if context.kind != "guest" or api_state.supabase_gateway is None:
        raise problem(
            request,
            status_code=403,
            code="guest_account_required",
            title="Guest Account Required",
            detail="Only an active guest workspace can be replaced.",
        )
    try:
        conversation = api_state.supabase_gateway.replace_guest_conversation(
            user_id=user.id,
            title="New idea",
            title_source="system_default",
            language=user.language,
        )
    except Exception as exc:
        logger.warning("Guest conversation replacement failed", error=type(exc).__name__)
        raise problem(
            request,
            status_code=409,
            code="guest_start_over_failed",
            title="Could Not Start Over",
            detail="The temporary conversation was left unchanged.",
        ) from exc
    return ConversationResponse(
        conversation=_with_activity(conversation, user_id=user.id)
    )


@router.get("/conversations", response_model=PaginatedConversations)
def list_conversations(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    archived: bool | None = Query(None),
    deleted: bool = Query(False),
    user: User = Depends(current_user),  # noqa: B008
) -> PaginatedConversations:
    cursor_updated_at: datetime | None = None
    cursor_id: str | None = None
    if cursor:
        raw_cursor_updated_at, cursor_id = decode_cursor(cursor, request)
        try:
            cursor_updated_at = datetime.fromisoformat(raw_cursor_updated_at)
        except ValueError:
            raise invalid_cursor_problem(request) from None

    if api_state.supabase_gateway is not None:
        try:
            items = api_state.supabase_gateway.list_conversations(
                user_id=user.id,
                limit=limit,
                archived=archived,
                deleted=deleted,
                cursor_updated_at=cursor_updated_at,
                cursor_id=cursor_id,
            )
        except ConversationCursorError:
            raise invalid_cursor_problem(request) from None
    else:
        items = []
        for conversation in api_state.store.conversations.values():
            if not _memory_conversation_owned_by(
                conversation.id,
                user.id,
                allow_unowned=True,
            ):
                continue
            if deleted:
                if conversation.deleted_at is None:
                    continue
            else:
                if conversation.deleted_at is not None:
                    continue

            if archived is not None and conversation.archived != archived:
                continue

            items.append(conversation)

        items.sort(
            key=lambda item: (int(item.pinned), item.updated_at, item.id),
            reverse=True,
        )
        if cursor_updated_at is not None and cursor_id is not None:
            cursor_pinned = next(
                (item.pinned for item in items if item.id == cursor_id), False
            )
            cursor_key = (int(bool(cursor_pinned)), cursor_updated_at, cursor_id)
            items = [
                item
                for item in items
                if (int(item.pinned), item.updated_at, item.id) < cursor_key
            ]

    page = items[: limit + 1]
    has_more = len(page) > limit
    page_items = page[:limit]
    activities = conversation_activity_service.project(
        user_id=user.id,
        conversation_ids=[item.id for item in page_items],
        reconcile=True,
    )
    page_items = [
        item.model_copy(update={"activity": activities[item.id]})
        for item in page_items
    ]
    next_cursor = None
    if has_more and page_items:
        last = page_items[-1]
        next_cursor = encode_cursor(last.updated_at.isoformat(), last.id)
    return PaginatedConversations(items=page_items, next_cursor=next_cursor)


@router.delete("/conversations", response_model=BulkConversationDeleteResponse)
def delete_all_conversations(
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> BulkConversationDeleteResponse:
    require_account_capability(
        request,
        "can_manage_conversation",
        detail="Sign in to manage saved conversations.",
        reason="keep_history",
    )
    if api_state.supabase_gateway is not None:
        deleted_count = api_state.supabase_gateway.soft_delete_all_conversations(
            user_id=user.id,
        )
    else:
        now = utcnow()
        deleted_count = 0
        for conversation_id, conversation in list(api_state.store.conversations.items()):
            if not _memory_conversation_owned_by(
                conversation_id,
                user.id,
                allow_unowned=False,
            ):
                continue
            if conversation.deleted_at is not None:
                continue
            api_state.store.conversations[conversation_id] = conversation.model_copy(
                update={"deleted_at": now, "updated_at": now},
            )
            deleted_count += 1
    return BulkConversationDeleteResponse(success=True, deleted_count=deleted_count)


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
def patch_conversation(
    conversation_id: str,
    payload: ConversationPatch,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> ConversationResponse:
    require_account_capability(
        request,
        "can_manage_conversation",
        detail="Sign in to manage saved conversations.",
        reason="keep_history",
    )
    conversation = (
        api_state.supabase_gateway.get_conversation(
            user_id=user.id,
            conversation_id=conversation_id,
        )
        if api_state.supabase_gateway
        else api_state.store.conversations.get(conversation_id)
    )
    if not conversation or not _memory_conversation_owned_by(
        conversation_id,
        user.id,
        allow_unowned=True,
    ):
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Conversation not found.",
        )
    data = conversation.model_dump()
    patch = payload.model_dump(exclude_unset=True)
    if "title" in patch and patch["title"]:
        patch["title_source"] = "user_renamed"
    if api_state.supabase_gateway is not None:
        updated = api_state.supabase_gateway.patch_conversation(
            user_id=user.id,
            conversation_id=conversation_id,
            patch=patch,
        )
        if not updated:
            raise problem(
                request,
                status_code=404,
                code="not_found",
                title="Not Found",
                detail="Conversation not found.",
            )
    else:
        data.update(patch)
        data["updated_at"] = utcnow()
        updated = Conversation.model_validate(data)
        api_state.store.conversations[conversation_id] = updated
    return ConversationResponse(
        conversation=_with_activity(updated, user_id=user.id)
    )


@router.delete("/conversations/{conversation_id}", response_model=SuccessResponse)
def delete_conversation(
    conversation_id: str,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> SuccessResponse:
    require_account_capability(
        request,
        "can_manage_conversation",
        detail="Sign in to manage saved conversations.",
        reason="keep_history",
    )
    conversation = (
        api_state.supabase_gateway.get_conversation(
            user_id=user.id,
            conversation_id=conversation_id,
        )
        if api_state.supabase_gateway
        else api_state.store.conversations.get(conversation_id)
    )
    if not conversation or not _memory_conversation_owned_by(
        conversation_id,
        user.id,
        allow_unowned=True,
    ):
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Conversation not found.",
        )
    if api_state.supabase_gateway is not None:
        api_state.supabase_gateway.soft_delete_conversation(
            user_id=user.id,
            conversation_id=conversation_id,
        )
    else:
        api_state.store.conversations[conversation_id] = conversation.model_copy(
            update={"deleted_at": utcnow(), "updated_at": utcnow()}
        )
    return SuccessResponse(success=True)


@router.get(
    "/conversations/{conversation_id}/run-dossiers",
    response_model=PaginatedRunDossiers,
    responses={
        400: {
            "description": "The pagination cursor is invalid or stale.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/Error"}
                }
            },
        },
        404: {
            "description": "The conversation was not found.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/Error"}
                }
            },
        },
    },
)
def list_run_dossiers(
    conversation_id: str,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    user: User = Depends(current_user),  # noqa: B008
) -> PaginatedRunDossiers:
    context = account_context(request)
    conversation = (
        api_state.supabase_gateway.get_conversation(
            user_id=user.id,
            conversation_id=conversation_id,
        )
        if api_state.supabase_gateway is not None
        else api_state.store.conversations.get(conversation_id)
    )
    memory_owned = (
        api_state.supabase_gateway is not None
        or _memory_conversation_owned_by(
            conversation_id,
            user.id,
            allow_unowned=False,
        )
    )
    if (
        conversation is None
        or conversation.deleted_at is not None
        or not memory_owned
    ):
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Conversation not found.",
        )

    if context.kind == "guest":
        if api_state.supabase_gateway is None:
            raise problem(
                request,
                status_code=404,
                code="not_found",
                title="Not Found",
                detail="Conversation not found.",
            )
        workspace = api_state.supabase_gateway.get_active_guest_workspace(
            user_id=user.id,
            at=datetime.now(timezone.utc),
        )
        if workspace is None or workspace.conversation_id != conversation_id:
            raise problem(
                request,
                status_code=404,
                code="not_found",
                title="Not Found",
                detail="Conversation not found.",
            )

    cursor_completed_at: datetime | None = None
    cursor_run_id: str | None = None
    if cursor is not None:
        raw_completed_at, cursor_run_id = decode_cursor(cursor, request)
        try:
            cursor_completed_at = datetime.fromisoformat(raw_completed_at)
        except ValueError:
            raise invalid_cursor_problem(request) from None
        if (
            cursor_completed_at.tzinfo is None
            or cursor_completed_at.utcoffset() is None
        ):
            raise invalid_cursor_problem(request)

    try:
        page = (
            api_state.supabase_gateway.list_run_dossier_source_rows(
                user_id=user.id,
                conversation_id=conversation_id,
                limit=limit + 1,
                cursor_completed_at=cursor_completed_at,
                cursor_run_id=cursor_run_id,
            )
            if api_state.supabase_gateway is not None
            else list_memory_run_dossier_source_rows(
                store=api_state.store,
                user_id=user.id,
                conversation_id=conversation_id,
                limit=limit + 1,
                cursor_completed_at=cursor_completed_at,
                cursor_run_id=cursor_run_id,
            )
        )
    except RunDossierCursorError:
        raise invalid_cursor_problem(request) from None

    selected_rows = page.rows[:limit]
    items = [
        project_run_dossier(
            run=row.run,
            artifact=row.artifact,
            decision=row.decision,
            result_message_id=row.result_message_id,
            decision_action_availability=(
                "available"
                if context.capabilities.can_save_decision
                else "account_conversion_required"
            ),
            language=user.language,
        )
        for row in selected_rows
    ]
    next_cursor = (
        encode_cursor(items[-1].completed_at.isoformat(), items[-1].run_id)
        if len(page.rows) > limit and items
        else None
    )
    return PaginatedRunDossiers(
        items=items,
        next_cursor=next_cursor,
        total_runs=page.total_runs,
        decided_runs=page.decided_runs,
    )


@router.get("/conversations/{conversation_id}/messages", response_model=PaginatedMessages)
def list_messages(
    conversation_id: str,
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None),
    anchor_message_id: str | None = Query(None),
    user: User = Depends(current_user),  # noqa: B008
) -> PaginatedMessages:
    if cursor is not None and anchor_message_id is not None:
        raise problem(
            request,
            status_code=422,
            code="invalid_message_anchor",
            title="Invalid Message Anchor",
            detail="A message anchor cannot be combined with a cursor.",
        )
    conversation = (
        api_state.supabase_gateway.get_conversation(
            user_id=user.id,
            conversation_id=conversation_id,
        )
        if api_state.supabase_gateway
        else api_state.store.conversations.get(conversation_id)
    )
    if (
        not conversation
        or conversation.deleted_at is not None
        or not _memory_conversation_owned_by(
            conversation_id,
            user.id,
            allow_unowned=True,
        )
    ):
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Conversation not found.",
        )

    cursor_created_at: datetime | None = None
    cursor_id: str | None = None
    if cursor:
        raw_cursor_created_at, cursor_id = decode_cursor(cursor, request)
        try:
            cursor_created_at = datetime.fromisoformat(raw_cursor_created_at)
        except ValueError:
            raise invalid_cursor_problem(request) from None
        if api_state.supabase_gateway is not None:
            try:
                normalized_cursor_id = str(UUID(cursor_id))
            except (AttributeError, TypeError, ValueError):
                raise invalid_cursor_problem(request) from None
            if normalized_cursor_id != cursor_id:
                raise invalid_cursor_problem(request)

    items: list[Message] | None = None
    database_page = False
    database_page_ids: set[str] = set()
    transcript_represented_request_ids: set[str] = set()
    if api_state.supabase_gateway is not None:
        try:
            message_page_options = {
                "user_id": user.id,
                "conversation_id": conversation_id,
                "limit": limit,
                "cursor_created_at": cursor_created_at,
                "cursor_id": cursor_id,
                "page": True,
            }
            if anchor_message_id is not None:
                message_page_options["anchor_message_id"] = anchor_message_id
            items = api_state.supabase_gateway.list_messages(**message_page_options)
            database_page = True
            database_page_ids = {message.id for message in items}
            if (
                dev_memory_fallback_enabled()
                and conversation_id in api_state.store.conversations
                and api_state.store.messages.get(conversation_id)
            ):
                items = api_state.store.messages.get(conversation_id, [])
                database_page = False
                database_page_ids = set()
            elif items:
                later_work, transcript_represented_request_ids = (
                    api_state.supabase_gateway.list_message_page_context(
                        user_id=user.id,
                        conversation_id=conversation_id,
                        page_messages=items,
                    )
                )
                items = [*items, *later_work]
        except MessageCursorError:
            raise invalid_cursor_problem(request) from None
        except MessageAnchorError:
            raise problem(
                request,
                status_code=404,
                code="not_found",
                title="Not Found",
                detail="Message anchor not found.",
            ) from None
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
            items = None
            database_page = False
            database_page_ids = set()
            transcript_represented_request_ids = set()
            logger.warning(
                "Supabase message list failed; using dev memory fallback",
                error=str(exc),
                conversation_id=conversation_id,
            )

    if items is None:
        conversation = api_state.store.conversations.get(conversation_id)
        if conversation is not None and not _memory_conversation_owned_by(
            conversation_id,
            user.id,
            allow_unowned=True,
        ):
            conversation = None
        if conversation is not None and conversation.deleted_at is not None:
            raise problem(
                request,
                status_code=404,
                code="not_found",
                title="Not Found",
                detail="Conversation not found.",
            )
        if not conversation:
            return PaginatedMessages(items=[])
        items = api_state.store.messages.get(conversation_id, [])

    items.sort(key=lambda item: (item.created_at, item.id))
    items = reconcile_reload_message_metadata(items)
    items = reconcile_and_project_chat_turns(
        user_id=user.id,
        conversation_id=conversation_id,
        messages=items,
    )
    represented_request_ids = represented_backtest_job_request_ids(items)
    represented_request_ids.update(transcript_represented_request_ids)
    items = _public_message_projection(items)
    if database_page:
        items = [item for item in items if item.id in database_page_ids]
    if not database_page and cursor_created_at is not None and cursor_id is not None:
        cursor_key = (cursor_created_at, cursor_id)
        items = [item for item in items if (item.created_at, item.id) > cursor_key]
    if not database_page and anchor_message_id is not None:
        anchors = [item for item in items if item.id == anchor_message_id]
        if len(anchors) != 1:
            raise problem(
                request,
                status_code=404,
                code="not_found",
                title="Not Found",
                detail="Message anchor not found.",
            )
        anchor = anchors[0]
        anchor_key = (anchor.created_at, anchor.id)
        items = [item for item in items if (item.created_at, item.id) >= anchor_key]
    page = items[: limit + 1]
    has_more = len(page) > limit
    page_items = page[:limit]
    page_items = _project_backtest_job_actions(
        user_id=user.id,
        conversation_id=conversation_id,
        messages=page_items,
        represented_request_ids=represented_request_ids,
    )
    next_cursor = None
    if has_more and page_items:
        last = page_items[-1]
        next_cursor = encode_cursor(last.created_at.isoformat(), last.id)
    return PaginatedMessages(items=page_items, next_cursor=next_cursor)
