from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request

from argus.api import state as api_state
from argus.api.dependencies import current_user
from argus.api.pagination import decode_cursor, encode_cursor, invalid_cursor_problem
from argus.api.schemas import PaginatedSearch, SearchItem, User
from argus.api.search_utils import score_search_item, search_type_rank

router = APIRouter(prefix="/api/v1", tags=["search"])


@router.get("/search", response_model=PaginatedSearch)
def search(
    q: str,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    user: User = Depends(current_user),  # noqa: B008
) -> PaginatedSearch:
    query = q.strip().lower()
    if not query:
        return PaginatedSearch(items=[], next_cursor=None)
    scored_items: list[tuple[int, SearchItem]] = []
    if api_state.supabase_gateway is not None:
        raw = api_state.supabase_gateway.search_rows(
            user_id=user.id,
            query=query,
            limit=None,
        )
        conversations = raw.get("conversations", [])
        strategies = raw.get("strategies", [])
        collections = raw.get("collections", [])
        runs = raw.get("runs", [])
        for row in conversations:
            item = SearchItem(
                type="chat",
                id=row["id"],
                title=row["title"],
                matched_text=row.get("last_message_preview") or row["title"],
                updated_at=row["updated_at"],
            )
            score = score_search_item(
                query=query,
                title=row["title"],
                matched_text=item.matched_text,
                pinned=bool(row.get("pinned", False)),
            )
            scored_items.append((score, item))
        for row in strategies:
            symbols = row.get("symbols") or []
            matched_text = ", ".join(symbols) or row["name"]
            symbol_exact_match = any(query == str(symbol).lower() for symbol in symbols)
            item = SearchItem(
                type="strategy",
                id=row["id"],
                title=row["name"],
                matched_text=matched_text,
                updated_at=row["updated_at"],
            )
            score = score_search_item(
                query=query,
                title=row["name"],
                matched_text=matched_text,
                pinned=bool(row.get("pinned", False)),
                symbol_exact_match=symbol_exact_match,
            )
            scored_items.append((score, item))
        for row in collections:
            item = SearchItem(
                type="collection",
                id=row["id"],
                title=row["name"],
                matched_text=row["name"],
                updated_at=row["updated_at"],
            )
            score = score_search_item(
                query=query,
                title=row["name"],
                matched_text=row["name"],
                pinned=bool(row.get("pinned", False)),
            )
            scored_items.append((score, item))
        for row in runs:
            card = row.get("conversation_result_card") or {}
            title = card.get("title") or "Backtest run"
            item = SearchItem(
                type="run",
                id=row["id"],
                title=title,
                matched_text=title,
                updated_at=row["created_at"],
                conversation_id=row.get("conversation_id"),
            )
            score = score_search_item(
                query=query,
                title=title,
                matched_text=title,
                pinned=False,
            )
            scored_items.append((score, item))
    else:
        for conversation in api_state.store.conversations.values():
            if conversation.deleted_at:
                continue
            haystack = f"{conversation.title} {conversation.last_message_preview or ''}"
            if query in haystack.lower():
                item = SearchItem(
                    type="chat",
                    id=conversation.id,
                    title=conversation.title,
                    matched_text=conversation.last_message_preview or conversation.title,
                    updated_at=conversation.updated_at,
                )
                score = score_search_item(
                    query=query,
                    title=conversation.title,
                    matched_text=item.matched_text,
                    pinned=conversation.pinned,
                )
                scored_items.append((score, item))
        for strategy in api_state.store.strategies.values():
            if strategy.deleted_at:
                continue
            haystack = f"{strategy.name} {' '.join(strategy.symbols)} {strategy.template}"
            if query in haystack.lower():
                matched_text = ", ".join(strategy.symbols) or strategy.name
                item = SearchItem(
                    type="strategy",
                    id=strategy.id,
                    title=strategy.name,
                    matched_text=matched_text,
                    updated_at=strategy.updated_at,
                )
                score = score_search_item(
                    query=query,
                    title=strategy.name,
                    matched_text=matched_text,
                    pinned=strategy.pinned,
                    symbol_exact_match=any(
                        query == symbol.lower() for symbol in strategy.symbols
                    ),
                )
                scored_items.append((score, item))
        for collection in api_state.store.collections.values():
            if collection.deleted_at:
                continue
            if query in collection.name.lower():
                item = SearchItem(
                    type="collection",
                    id=collection.id,
                    title=collection.name,
                    matched_text=collection.name,
                    updated_at=collection.updated_at,
                )
                score = score_search_item(
                    query=query,
                    title=collection.name,
                    matched_text=collection.name,
                    pinned=collection.pinned,
                )
                scored_items.append((score, item))
        for run in api_state.store.backtest_runs.values():
            title = run.conversation_result_card.get("title", "Backtest run")
            haystack = (
                f"{title} {' '.join(run.symbols)} "
                f"{run.config_snapshot.get('template', '')}"
            )
            if query in haystack.lower():
                item = SearchItem(
                    type="run",
                    id=run.id,
                    title=title,
                    matched_text=title,
                    updated_at=run.created_at,
                    conversation_id=run.conversation_id,
                )
                score = score_search_item(
                    query=query,
                    title=title,
                    matched_text=title,
                    pinned=False,
                    symbol_exact_match=any(
                        query == symbol.lower() for symbol in run.symbols
                    ),
                )
                scored_items.append((score, item))

    scored_items.sort(
        key=lambda pair: (
            pair[0],
            pair[1].updated_at,
            search_type_rank(pair[1].type),
            pair[1].id,
        ),
        reverse=True,
    )
    filtered = scored_items
    if cursor:
        cursor_updated_at, cursor_id = decode_cursor(cursor, request)
        try:
            cursor_dt = datetime.fromisoformat(cursor_updated_at)
        except ValueError:
            raise invalid_cursor_problem(request) from None
        cursor_pair = next(
            (
                pair
                for pair in scored_items
                if pair[1].id == cursor_id and pair[1].updated_at == cursor_dt
            ),
            None,
        )
        if cursor_pair is None:
            raise invalid_cursor_problem(request)
        cursor_score, cursor_item = cursor_pair
        cursor_key = (
            cursor_score,
            cursor_dt,
            search_type_rank(cursor_item.type),
            cursor_id,
        )
        filtered = [
            pair
            for pair in scored_items
            if (
                pair[0],
                pair[1].updated_at,
                search_type_rank(pair[1].type),
                pair[1].id,
            )
            < cursor_key
        ]

    page = filtered[: limit + 1]
    has_more = len(page) > limit
    page_items = page[:limit]
    next_cursor = None
    if has_more and page_items:
        _, last_item = page_items[-1]
        next_cursor = encode_cursor(last_item.updated_at.isoformat(), last_item.id)
    return PaginatedSearch(
        items=[item for _, item in page_items],
        next_cursor=next_cursor,
    )
