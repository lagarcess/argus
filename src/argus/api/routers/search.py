from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request

from argus.api import state as api_state
from argus.api.dependencies import current_user
from argus.api.guest_access import account_context
from argus.api.pagination import decode_cursor, encode_cursor, invalid_cursor_problem
from argus.api.schemas import (
    DecisionState,
    PaginatedSearch,
    SearchItem,
    SearchLedgerGroup,
    User,
)
from argus.api.search_assembly import (
    scored_memory_search_items,
    scored_supabase_search_items,
)
from argus.api.search_utils import search_rank_key
from argus.domain.postgres_search_reader import (
    SearchCursorError,
    SearchReadResult,
)
from argus.domain.search_text import search_has_indexable_token
from argus.observability.product_events import capture_product_event

router = APIRouter(prefix="/api/v1", tags=["search"])

LEDGER_DECISION_STATE_ORDER: tuple[DecisionState, ...] = (
    "promising",
    "watching",
    "rejected",
    "revisit_later",
)


@router.get("/search", response_model=PaginatedSearch)
def search(
    q: str,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    decision_state: DecisionState | None = Query(None),  # noqa: B008
    include_ledger_groups: bool = Query(False),  # noqa: B008
    user: User = Depends(current_user),  # noqa: B008
) -> PaginatedSearch:
    context = account_context(request)
    query = q.strip().lower()

    cursor_dt: datetime | None = None
    cursor_id: str | None = None
    if cursor:
        cursor_updated_at, cursor_id = decode_cursor(cursor, request)
        try:
            cursor_dt = datetime.fromisoformat(cursor_updated_at)
        except ValueError:
            raise invalid_cursor_problem(request) from None
        if cursor_dt.tzinfo is None or cursor_dt.utcoffset() is None:
            raise invalid_cursor_problem(request)

    workspace_conversation_id: str | None = None
    if context.kind == "guest" and api_state.supabase_gateway is not None:
        workspace = api_state.supabase_gateway.get_active_guest_workspace(
            user_id=user.id,
            at=datetime.now(timezone.utc),
        )
        workspace_conversation_id = (
            workspace.conversation_id if workspace is not None else None
        )

    if query and not search_has_indexable_token(query):
        if cursor:
            raise invalid_cursor_problem(request)
        ledger_groups = (
            []
            if context.kind == "guest" and include_ledger_groups
            else _ledger_groups_from_counts(None)
            if include_ledger_groups
            else None
        )
        capture_product_event(
            "recall_usage",
            user_id=user.id,
            status="completed",
            attributes={
                "query_present": True,
                "decision_state_filter_present": decision_state is not None,
                "result_count": 0,
                "returned_types": [],
                "has_more": False,
                "source": (
                    "supabase" if api_state.supabase_gateway is not None else "memory"
                ),
            },
        )
        return PaginatedSearch(
            items=[],
            next_cursor=None,
            ledger_groups=ledger_groups,
        )

    scored_items: list[tuple[int, SearchItem]] = []
    search_read: SearchReadResult | None = None
    if api_state.supabase_gateway is not None:
        try:
            read_result = api_state.supabase_gateway.search_rows(
                user_id=user.id,
                query=query,
                source_limit=limit + 1,
                cursor_updated_at=cursor_dt,
                cursor_id=cursor_id,
                decision_state=decision_state,
                include_ledger_groups=include_ledger_groups,
                guest_scope=context.kind == "guest",
                guest_conversation_id=workspace_conversation_id,
            )
        except SearchCursorError:
            raise invalid_cursor_problem(request) from None
        if isinstance(read_result, SearchReadResult):
            search_read = read_result
            raw = read_result.rows
        else:
            # Keep injected test gateways compatible while the production
            # Supabase gateway always returns the typed reader result.
            raw = read_result
        scored_items.extend(scored_supabase_search_items(raw=raw, query=query))
    else:
        scored_items.extend(scored_memory_search_items(user=user, query=query))

    if context.kind == "guest":
        # Defense in depth: the persistent reader applies this scope before
        # each source limit; this keeps non-production injected gateways safe.
        scored_items = [
            pair
            for pair in scored_items
            if workspace_conversation_id is not None
            and pair[1].conversation_id == workspace_conversation_id
        ]

    scored_items.sort(
        key=lambda pair: search_rank_key(
            score=pair[0],
            kind=pair[1].type,
            updated_at=pair[1].updated_at,
            item_id=pair[1].id,
        ),
        reverse=True,
    )
    ledger_groups = (
        []
        if context.kind == "guest" and include_ledger_groups
        else _ledger_groups_from_counts(search_read.ledger_counts)
        if include_ledger_groups and search_read is not None
        else _ledger_groups_from_items(scored_items)
        if include_ledger_groups
        else None
    )
    if decision_state is not None:
        scored_items = [
            pair
            for pair in scored_items
            if decision_state in pair[1].decision_states
        ]
    filtered = scored_items
    if cursor and search_read is None:
        assert cursor_dt is not None
        assert cursor_id is not None
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
        cursor_key = search_rank_key(
            score=cursor_score,
            kind=cursor_item.type,
            updated_at=cursor_dt,
            item_id=cursor_id,
        )
        filtered = [
            pair
            for pair in scored_items
            if search_rank_key(
                score=pair[0],
                kind=pair[1].type,
                updated_at=pair[1].updated_at,
                item_id=pair[1].id,
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
    capture_product_event(
        "recall_usage",
        user_id=user.id,
        status="completed",
        attributes={
            "query_present": bool(query),
            "decision_state_filter_present": decision_state is not None,
            "result_count": len(page_items),
            "returned_types": _returned_types(page_items),
            "has_more": has_more,
            "source": "supabase" if api_state.supabase_gateway is not None else "memory",
        },
    )
    return PaginatedSearch(
        items=[item for _, item in page_items],
        next_cursor=next_cursor,
        ledger_groups=ledger_groups,
    )


def _ledger_groups_from_items(
    scored_items: list[tuple[int, SearchItem]],
) -> list[SearchLedgerGroup]:
    counts: dict[DecisionState, int] = {state: 0 for state in LEDGER_DECISION_STATE_ORDER}
    for _, item in scored_items:
        for state in item.decision_states:
            counts[state] += 1
    return [
        SearchLedgerGroup(decision_state=state, count=counts[state])
        for state in LEDGER_DECISION_STATE_ORDER
    ]


def _ledger_groups_from_counts(
    counts: dict[str, int] | None,
) -> list[SearchLedgerGroup]:
    values = counts or {}
    return [
        SearchLedgerGroup(decision_state=state, count=int(values.get(state, 0)))
        for state in LEDGER_DECISION_STATE_ORDER
    ]


def _returned_types(page_items: list[tuple[int, SearchItem]]) -> list[str]:
    returned: list[str] = []
    for _, item in page_items:
        if item.type not in returned:
            returned.append(item.type)
    return returned
