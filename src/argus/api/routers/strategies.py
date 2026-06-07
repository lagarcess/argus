from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request

from argus.api import state as api_state
from argus.api.dependencies import current_user, problem
from argus.api.naming import suggest_entity_name
from argus.api.pagination import decode_cursor, encode_cursor, invalid_cursor_problem
from argus.api.schemas import (
    PaginatedStrategies,
    Strategy,
    StrategyCreate,
    StrategyPatch,
    StrategyResponse,
    SuccessResponse,
    User,
)
from argus.domain.store import utcnow

router = APIRouter(prefix="/api/v1", tags=["strategies"])


@router.post("/strategies", response_model=StrategyResponse)
def create_strategy(
    payload: StrategyCreate,
    user: User = Depends(current_user),  # noqa: B008
) -> StrategyResponse:
    strategy_name = payload.name
    if not strategy_name:
        suggested = suggest_entity_name(
            entity_type="strategy",
            context=f"Template: {payload.template}\nSymbols: {', '.join(payload.symbols)}",
            language=user.language,
        )
        strategy_name = suggested or f"{', '.join(payload.symbols)} idea"

    if api_state.supabase_gateway is not None:
        strategy_payload = payload.model_dump(mode="json")
        strategy_payload["name"] = strategy_name
        strategy_payload["name_source"] = (
            "user_renamed" if payload.name else "ai_generated"
        )
        strategy = api_state.supabase_gateway.create_strategy(
            user_id=user.id,
            payload=strategy_payload,
        )
    else:
        from argus.domain.engine import classify_symbol, default_benchmark

        now = utcnow()
        benchmark = payload.benchmark_symbol or default_benchmark(payload.asset_class)
        strategy = Strategy(
            id=api_state.store.new_id(),
            name=strategy_name,
            name_source="user_renamed" if payload.name else "ai_generated",
            template=payload.template,
            asset_class=payload.asset_class,
            symbols=[classify_symbol(symbol).symbol for symbol in payload.symbols],
            parameters=payload.parameters,
            metrics_preferences=payload.metrics_preferences,
            benchmark_symbol=benchmark,
            created_at=now,
            updated_at=now,
        )
        api_state.store.strategies[strategy.id] = strategy
    return StrategyResponse(strategy=strategy)


@router.get("/strategies", response_model=PaginatedStrategies)
def list_strategies(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    deleted: bool = Query(False),
    user: User = Depends(current_user),  # noqa: B008
) -> PaginatedStrategies:
    if api_state.supabase_gateway is not None:
        items = api_state.supabase_gateway.list_strategies(
            user_id=user.id,
            limit=None,
            deleted=deleted,
        )
    else:
        items = []
        for item in api_state.store.strategies.values():
            if deleted:
                if item.deleted_at is None:
                    continue
            else:
                if item.deleted_at is not None:
                    continue
            items.append(item)

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
    return PaginatedStrategies(items=page_items, next_cursor=next_cursor)


@router.patch("/strategies/{strategy_id}", response_model=StrategyResponse)
def patch_strategy(
    strategy_id: str,
    payload: StrategyPatch,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> StrategyResponse:
    strategy = None
    if api_state.supabase_gateway is not None:
        strategy = api_state.supabase_gateway.get_strategy(
            user_id=user.id,
            strategy_id=strategy_id,
        )
    else:
        strategy = api_state.store.strategies.get(strategy_id)

    if not strategy:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Strategy not found.",
        )

    patch = payload.model_dump(exclude_unset=True)
    if patch.get("name"):
        patch["name_source"] = "user_renamed"

    if api_state.supabase_gateway is not None:
        updated = api_state.supabase_gateway.patch_strategy(
            user_id=user.id,
            strategy_id=strategy_id,
            patch=patch,
        )
    else:
        data = strategy.model_dump()
        data.update(patch)
        data["updated_at"] = utcnow()
        updated = Strategy.model_validate(data)
        api_state.store.strategies[strategy_id] = updated
    return StrategyResponse(strategy=updated)


@router.delete("/strategies/{strategy_id}", response_model=SuccessResponse)
def delete_strategy(
    strategy_id: str,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> SuccessResponse:
    strategy = None
    if api_state.supabase_gateway is not None:
        strategy = api_state.supabase_gateway.get_strategy(
            user_id=user.id,
            strategy_id=strategy_id,
        )
    else:
        strategy = api_state.store.strategies.get(strategy_id)

    if not strategy:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Strategy not found.",
        )

    if api_state.supabase_gateway is not None:
        api_state.supabase_gateway.soft_delete_strategy(
            user_id=user.id,
            strategy_id=strategy_id,
        )
    else:
        api_state.store.strategies[strategy_id] = strategy.model_copy(
            update={"deleted_at": utcnow(), "updated_at": utcnow()}
        )
    return SuccessResponse(success=True)
