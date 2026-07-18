from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from loguru import logger

from argus.api import state as api_state
from argus.api.chat import turn_lifecycle_hooks
from argus.api.chat.turn_lifecycle_projection import project_turn_lifecycle
from argus.api.dependencies import current_user, dev_memory_fallback_enabled, problem
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
    SuccessResponse,
    User,
)
from argus.domain.store import utcnow

router = APIRouter(prefix="/api/v1", tags=["conversations"])


def _lifecycle_rows_for(conversation_id: str, turn_ids: set[str]) -> list[dict]:
    from argus.domain.chat_turn_lifecycle import list_projectable_turns_memory

    if not turn_ids:
        return []
    try:
        if api_state.supabase_gateway is not None:
            return api_state.supabase_gateway.list_projectable_chat_turns(
                conversation_id=conversation_id,
                turn_ids=sorted(turn_ids),
            )
        return list_projectable_turns_memory(
            api_state.store, conversation_id=conversation_id, turn_ids=turn_ids
        )
    except Exception as exc:
        logger.warning(
            "Turn lifecycle projection lookup failed open",
            error_type=type(exc).__name__,
            conversation_id=conversation_id,
        )
        return []


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


@router.post("/conversations", response_model=ConversationResponse)
def create_conversation(
    payload: ConversationCreate,
    user: User = Depends(current_user),  # noqa: B008
) -> ConversationResponse:
    title = payload.title or "New idea"
    title_source = "user_renamed" if payload.title else "system_default"
    language = payload.language or user.language
    if api_state.supabase_gateway is not None:
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
    return ConversationResponse(conversation=conversation)


@router.get("/conversations", response_model=PaginatedConversations)
def list_conversations(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    archived: bool | None = Query(None),
    deleted: bool = Query(False),
    user: User = Depends(current_user),  # noqa: B008
) -> PaginatedConversations:
    if api_state.supabase_gateway is not None:
        items = api_state.supabase_gateway.list_conversations(
            user_id=user.id,
            limit=None,
            archived=archived,
            deleted=deleted,
        )
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
        key=lambda item: (int(item.pinned), item.updated_at, item.id), reverse=True
    )
    filtered = items
    if cursor:
        cursor_updated_at, cursor_id = decode_cursor(cursor, request)
        try:
            cursor_dt = datetime.fromisoformat(cursor_updated_at)
        except ValueError:
            raise invalid_cursor_problem(request) from None
        cursor_pinned = next(
            (item.pinned for item in items if item.id == cursor_id), False
        )
        cursor_key = (int(bool(cursor_pinned)), cursor_dt, cursor_id)
        filtered = [
            item
            for item in items
            if (int(item.pinned), item.updated_at, item.id) < cursor_key
        ]
    page = filtered[: limit + 1]
    has_more = len(page) > limit
    page_items = page[:limit]
    next_cursor = None
    if has_more and page_items:
        last = page_items[-1]
        next_cursor = encode_cursor(last.updated_at.isoformat(), last.id)
    return PaginatedConversations(items=page_items, next_cursor=next_cursor)


@router.delete("/conversations", response_model=BulkConversationDeleteResponse)
def delete_all_conversations(
    user: User = Depends(current_user),  # noqa: B008
) -> BulkConversationDeleteResponse:
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
    return ConversationResponse(conversation=updated)


@router.delete("/conversations/{conversation_id}", response_model=SuccessResponse)
def delete_conversation(
    conversation_id: str,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> SuccessResponse:
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


@router.get("/conversations/{conversation_id}/messages", response_model=PaginatedMessages)
def list_messages(
    conversation_id: str,
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None),
    user: User = Depends(current_user),  # noqa: B008
) -> PaginatedMessages:
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
    # #240: reconcile stale turns before returning conversation messages —
    # only after route ownership succeeded, scoped to the requesting user.
    turn_lifecycle_hooks.reconcile_conversation_turns(
        conversation_id=conversation_id,
        user_id=user.id,
    )

    items: list[Message] | None = None
    if api_state.supabase_gateway is not None:
        try:
            items = api_state.supabase_gateway.list_messages(
                user_id=user.id,
                conversation_id=conversation_id,
                limit=None,
            )
            if (
                dev_memory_fallback_enabled()
                and conversation_id in api_state.store.conversations
                and api_state.store.messages.get(conversation_id)
            ):
                items = api_state.store.messages.get(conversation_id, [])
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
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
    # #240: terminal lifecycle truth projects into the read — typed retry
    # recovery directly after the owning user message, and reconciled
    # status/outcome onto the linked assistant copy — without mutating
    # immutable messages. Scoping by the page's user turns removes any
    # historical row ceiling.
    items = project_turn_lifecycle(
        items,
        _lifecycle_rows_for(
            conversation_id,
            {item.id for item in items if item.role == "user"},
        ),
        language=conversation.language if conversation else None,
    )
    filtered = items
    if cursor:
        cursor_created_at, cursor_id = decode_cursor(cursor, request)
        try:
            cursor_dt = datetime.fromisoformat(cursor_created_at)
        except ValueError:
            raise invalid_cursor_problem(request) from None
        cursor_key = (cursor_dt, cursor_id)
        filtered = [item for item in items if (item.created_at, item.id) > cursor_key]
    page = filtered[: limit + 1]
    has_more = len(page) > limit
    page_items = page[:limit]
    next_cursor = None
    if has_more and page_items:
        last = page_items[-1]
        next_cursor = encode_cursor(last.created_at.isoformat(), last.id)
    return PaginatedMessages(items=page_items, next_cursor=next_cursor)
