from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request

from argus.api import state as api_state
from argus.api.dependencies import current_user
from argus.api.guest_access import account_context
from argus.api.memory_ownership import memory_object_visible
from argus.api.pagination import decode_cursor, encode_cursor, invalid_cursor_problem
from argus.api.schemas import (
    BacktestRun,
    Conversation,
    HistoryItem,
    PaginatedHistory,
    User,
)
from argus.api.search_utils import search_type_rank
from argus.domain.postgres_history_reader import HistoryCursorError

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
    context = account_context(request)
    if context.kind == "guest":
        if api_state.supabase_gateway is None:
            return PaginatedHistory(items=[], next_cursor=None)
        workspace = api_state.supabase_gateway.get_active_guest_workspace(
            user_id=user.id,
            at=datetime.now(timezone.utc),
        )
        if workspace is None or workspace.conversation_id is None:
            return PaginatedHistory(items=[], next_cursor=None)
        conversation = api_state.supabase_gateway.get_conversation(
            user_id=user.id,
            conversation_id=workspace.conversation_id,
        )
        if (
            conversation is None
            or conversation.deleted_at is not None
            or conversation.archived is not archived
            or deleted
        ):
            return PaginatedHistory(items=[], next_cursor=None)
        return PaginatedHistory(
            items=[
                HistoryItem(
                    type="chat",
                    id=conversation.id,
                    title=conversation.title,
                    title_source=conversation.title_source,
                    subtitle=conversation.last_message_preview or "No messages yet",
                    pinned=False,
                    created_at=conversation.updated_at,
                    conversation_id=conversation.id,
                    expires_at=workspace.expires_at,
                )
            ],
            next_cursor=None,
        )
    cursor_dt: datetime | None = None
    cursor_id: str | None = None
    if cursor:
        cursor_created_at, cursor_id = decode_cursor(cursor, request)
        try:
            cursor_dt = datetime.fromisoformat(cursor_created_at)
        except ValueError:
            raise invalid_cursor_problem(request) from None

    gateway = api_state.supabase_gateway
    persistent_history = gateway is not None
    if gateway is not None:
        try:
            raw = gateway.list_history_rows(
                user_id=user.id,
                limit=limit + 1,
                cursor_activity_at=cursor_dt,
                cursor_id=cursor_id,
                archived=archived,
                deleted=deleted,
            )
        except HistoryCursorError:
            raise invalid_cursor_problem(request) from None
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
        for conversation_row in raw["conversations"]:
            items.append(
                HistoryItem(
                    type="chat",
                    id=conversation_row["id"],
                    title=conversation_row["title"],
                    title_source=conversation_row["title_source"],
                    subtitle=conversation_row["last_message_preview"]
                    or "No messages yet",
                    pinned=conversation_row["pinned"],
                    created_at=conversation_row["updated_at"],
                )
            )
        for strategy_row in raw["strategies"]:
            items.append(
                HistoryItem(
                    type="strategy",
                    id=strategy_row["id"],
                    title=strategy_row["name"],
                    subtitle=", ".join(strategy_row["symbols"]),
                    pinned=strategy_row["pinned"],
                    created_at=strategy_row["updated_at"],
                )
            )
        for collection_row in raw["collections"]:
            items.append(
                HistoryItem(
                    type="collection",
                    id=collection_row["id"],
                    title=collection_row["name"],
                    subtitle=(
                        f"{collection_row.get('strategy_count', 0)} strategies"
                    ),
                    pinned=collection_row["pinned"],
                    created_at=collection_row["updated_at"],
                )
            )
    else:
        items = []
        for run_id, run in api_state.store.backtest_runs.items():
            if not memory_object_visible(
                owner_map=api_state.store.backtest_run_owners,
                object_id=run_id,
                user_id=user.id,
            ):
                continue
            if _run_matches_history_filters(
                run,
                api_state.store.conversations,
                archived=archived,
                deleted=deleted,
            ):
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
        for stored_conversation in api_state.store.conversations.values():
            if not memory_object_visible(
                owner_map=api_state.store.conversation_owners,
                object_id=stored_conversation.id,
                user_id=user.id,
            ):
                continue
            if (
                stored_conversation.deleted_at is not None
                if deleted
                else stored_conversation.deleted_at is None
            ) and stored_conversation.archived is archived:
                items.append(
                    HistoryItem(
                        type="chat",
                        id=stored_conversation.id,
                        title=stored_conversation.title,
                        title_source=stored_conversation.title_source,
                        subtitle=stored_conversation.last_message_preview
                        or "No messages yet",
                        pinned=stored_conversation.pinned,
                        created_at=stored_conversation.updated_at,
                    )
                )
        for stored_strategy in api_state.store.strategies.values():
            if not memory_object_visible(
                owner_map=api_state.store.strategy_owners,
                object_id=stored_strategy.id,
                user_id=user.id,
            ):
                continue
            if (
                stored_strategy.deleted_at is not None
                if deleted
                else stored_strategy.deleted_at is None
            ):
                items.append(
                    HistoryItem(
                        type="strategy",
                        id=stored_strategy.id,
                        title=stored_strategy.name,
                        subtitle=", ".join(stored_strategy.symbols),
                        pinned=stored_strategy.pinned,
                        created_at=stored_strategy.updated_at,
                    )
                )
        for stored_collection in api_state.store.collections.values():
            if not memory_object_visible(
                owner_map=api_state.store.collection_owners,
                object_id=stored_collection.id,
                user_id=user.id,
            ):
                continue
            if (
                stored_collection.deleted_at is not None
                if deleted
                else stored_collection.deleted_at is None
            ):
                items.append(
                    HistoryItem(
                        type="collection",
                        id=stored_collection.id,
                        title=stored_collection.name,
                        subtitle=f"{stored_collection.strategy_count} strategies",
                        pinned=stored_collection.pinned,
                        created_at=stored_collection.updated_at,
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
    if cursor and not persistent_history:
        assert cursor_dt is not None
        assert cursor_id is not None
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


def _conversation_matches_history_filters(
    conversation: Conversation,
    *,
    archived: bool,
    deleted: bool,
) -> bool:
    deleted_matches = (
        conversation.deleted_at is not None
        if deleted
        else conversation.deleted_at is None
    )
    return deleted_matches and conversation.archived == archived


def _run_matches_history_filters(
    run: BacktestRun,
    conversations: Mapping[str, Conversation],
    *,
    archived: bool,
    deleted: bool,
) -> bool:
    if not run.conversation_id:
        return not archived and not deleted
    conversation = conversations.get(run.conversation_id)
    if conversation is None:
        return not archived and not deleted
    return _conversation_matches_history_filters(
        conversation,
        archived=archived,
        deleted=deleted,
    )
