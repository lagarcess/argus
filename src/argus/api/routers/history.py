from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request

from argus.api import state as api_state
from argus.api.dependencies import current_user
from argus.api.pagination import decode_cursor, encode_cursor, invalid_cursor_problem
from argus.api.schemas import HistoryItem, PaginatedHistory, User
from argus.api.search_utils import search_type_rank

router = APIRouter(prefix="/api/v1", tags=["history"])


@router.get("/history", response_model=PaginatedHistory)
def history(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    archived: bool = Query(False),
    deleted: bool = Query(False),
    user: User = Depends(current_user),  # noqa: B008
) -> PaginatedHistory:
    if api_state.supabase_gateway is not None:
        raw = api_state.supabase_gateway.list_history_rows(
            user_id=user.id,
            limit=None,
            archived=archived,
            deleted=deleted,
        )
        items: list[HistoryItem] = []
        for run in raw["runs"]:
            items.append(
                HistoryItem(
                    type="run",
                    id=run["id"],
                    title=run["conversation_result_card"]["title"],
                    subtitle=run["conversation_result_card"]["rows"][0]["value"],
                    created_at=run["created_at"],
                    conversation_id=run.get("conversation_id"),
                )
            )
        for conversation in raw["conversations"]:
            items.append(
                HistoryItem(
                    type="chat",
                    id=conversation["id"],
                    title=conversation["title"],
                    subtitle=conversation["last_message_preview"] or "No messages yet",
                    pinned=conversation["pinned"],
                    created_at=conversation["updated_at"],
                )
            )
        for strategy in raw["strategies"]:
            items.append(
                HistoryItem(
                    type="strategy",
                    id=strategy["id"],
                    title=strategy["name"],
                    subtitle=", ".join(strategy["symbols"]),
                    pinned=strategy["pinned"],
                    created_at=strategy["updated_at"],
                )
            )
        for collection in raw["collections"]:
            items.append(
                HistoryItem(
                    type="collection",
                    id=collection["id"],
                    title=collection["name"],
                    subtitle=f"{collection.get('strategy_count', 0)} strategies",
                    pinned=collection["pinned"],
                    created_at=collection["updated_at"],
                )
            )
    else:
        items = []
        for run in api_state.store.backtest_runs.values():
            if not deleted:
                items.append(
                    HistoryItem(
                        type="run",
                        id=run.id,
                        title=run.conversation_result_card["title"],
                        subtitle=run.conversation_result_card["rows"][0]["value"],
                        created_at=run.created_at,
                        conversation_id=run.conversation_id,
                    )
                )
        for conversation in api_state.store.conversations.values():
            if (
                conversation.deleted_at is not None
                if deleted
                else conversation.deleted_at is None
            ) and conversation.archived is archived:
                items.append(
                    HistoryItem(
                        type="chat",
                        id=conversation.id,
                        title=conversation.title,
                        subtitle=conversation.last_message_preview or "No messages yet",
                        pinned=conversation.pinned,
                        created_at=conversation.updated_at,
                    )
                )
        for strategy in api_state.store.strategies.values():
            if (
                strategy.deleted_at is not None
                if deleted
                else strategy.deleted_at is None
            ):
                items.append(
                    HistoryItem(
                        type="strategy",
                        id=strategy.id,
                        title=strategy.name,
                        subtitle=", ".join(strategy.symbols),
                        pinned=strategy.pinned,
                        created_at=strategy.updated_at,
                    )
                )
        for collection in api_state.store.collections.values():
            if (
                collection.deleted_at is not None
                if deleted
                else collection.deleted_at is None
            ):
                items.append(
                    HistoryItem(
                        type="collection",
                        id=collection.id,
                        title=collection.name,
                        subtitle=f"{collection.strategy_count} strategies",
                        pinned=collection.pinned,
                        created_at=collection.updated_at,
                    )
                )

    items.sort(
        key=lambda item: (
            int(item.pinned),
            item.created_at,
            search_type_rank(item.type),
            item.id,
        ),
        reverse=True,
    )
    filtered = items
    if cursor:
        cursor_created_at, cursor_id = decode_cursor(cursor, request)
        try:
            cursor_dt = datetime.fromisoformat(cursor_created_at)
        except ValueError:
            raise invalid_cursor_problem(request) from None
        cursor_item = next(
            (
                item
                for item in items
                if item.id == cursor_id and item.created_at == cursor_dt
            ),
            None,
        )
        if cursor_item is None:
            raise invalid_cursor_problem(request)
        cursor_key = (
            int(cursor_item.pinned),
            cursor_dt,
            search_type_rank(cursor_item.type),
            cursor_id,
        )
        filtered = [
            item
            for item in items
            if (
                int(item.pinned),
                item.created_at,
                search_type_rank(item.type),
                item.id,
            )
            < cursor_key
        ]
    page = filtered[: limit + 1]
    has_more = len(page) > limit
    page_items = page[:limit]
    next_cursor = None
    if has_more and page_items:
        last = page_items[-1]
        next_cursor = encode_cursor(last.created_at.isoformat(), last.id)
    return PaginatedHistory(items=page_items, next_cursor=next_cursor)
