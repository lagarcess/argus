from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request

from argus.api import state as api_state
from argus.api.dependencies import current_user
from argus.api.pagination import decode_cursor, encode_cursor, invalid_cursor_problem
from argus.api.schemas import PaginatedSearch, SearchItem, User
from argus.api.search_assembly import (
    scored_memory_search_items,
    scored_supabase_search_items,
)
from argus.api.search_utils import search_type_rank

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
        scored_items.extend(scored_supabase_search_items(raw=raw, query=query))
    else:
        scored_items.extend(scored_memory_search_items(user=user, query=query))

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
