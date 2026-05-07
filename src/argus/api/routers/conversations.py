from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from loguru import logger

from argus.api import state as api_state
from argus.api.dependencies import current_user, dev_memory_fallback_enabled, problem
from argus.api.message_store import memory_conversation
from argus.api.pagination import decode_cursor, encode_cursor, invalid_cursor_problem
from argus.api.schemas import (
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
            )
    else:
        conversation = memory_conversation(
            title=title,
            title_source=title_source,
            language=language,
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
            if deleted:
                if conversation.deleted_at is None:
                    continue
            else:
                if conversation.deleted_at is not None:
                    continue

            if archived is not None and conversation.archived != archived:
                continue

            items.append(conversation)

    items.sort(key=lambda item: (int(item.pinned), item.updated_at, item.id), reverse=True)
    filtered = items
    if cursor:
        cursor_updated_at, cursor_id = decode_cursor(cursor, request)
        try:
            cursor_dt = datetime.fromisoformat(cursor_updated_at)
        except ValueError:
            raise invalid_cursor_problem(request) from None
        cursor_pinned = next((item.pinned for item in items if item.id == cursor_id), False)
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
    if not conversation:
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
    if not conversation:
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
    items: list[Message] | None = None
    if api_state.supabase_gateway is not None:
        try:
            items = api_state.supabase_gateway.list_messages(
                user_id=user.id,
                conversation_id=conversation_id,
                limit=None,
            )
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
        if not conversation:
            return PaginatedMessages(items=[])
        items = api_state.store.messages.get(conversation_id, [])

    items.sort(key=lambda item: (item.created_at, item.id))
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
