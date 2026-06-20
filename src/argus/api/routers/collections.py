from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request

from argus.api import state as api_state
from argus.api.dependencies import current_user, problem
from argus.api.memory_ownership import memory_object_visible
from argus.api.naming import suggest_entity_name
from argus.api.pagination import decode_cursor, encode_cursor, invalid_cursor_problem
from argus.api.schemas import (
    Collection,
    CollectionAttach,
    CollectionCreate,
    CollectionPatch,
    CollectionResponse,
    PaginatedCollections,
    SuccessResponse,
    User,
)
from argus.domain.store import utcnow

router = APIRouter(prefix="/api/v1", tags=["collections"])


@router.post("/collections", response_model=CollectionResponse)
def create_collection(
    payload: CollectionCreate,
    user: User = Depends(current_user),  # noqa: B008
) -> CollectionResponse:
    collection_name = payload.name
    if not collection_name:
        suggested = suggest_entity_name(
            entity_type="collection",
            context="User asked to create a new strategy collection.",
            language=user.language,
        )
        collection_name = suggested or "New collection"

    if api_state.supabase_gateway is not None:
        collection = api_state.supabase_gateway.create_collection(
            user_id=user.id,
            payload={
                "name": collection_name,
                "name_source": "user_renamed" if payload.name else "ai_generated",
                "created_at": utcnow().isoformat(),
                "updated_at": utcnow().isoformat(),
            },
        )
    else:
        now = utcnow()
        collection = Collection(
            id=api_state.store.new_id(),
            name=collection_name,
            name_source="user_renamed" if payload.name else "ai_generated",
            created_at=now,
            updated_at=now,
        )
        api_state.store.collections[collection.id] = collection
        api_state.store.collection_owners[collection.id] = user.id
        api_state.store.collection_strategies[collection.id] = set()
    return CollectionResponse(collection=collection)


@router.get("/collections", response_model=PaginatedCollections)
def list_collections(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    user: User = Depends(current_user),  # noqa: B008
) -> PaginatedCollections:
    if api_state.supabase_gateway is not None:
        items = api_state.supabase_gateway.list_collections(user_id=user.id, limit=None)
    else:
        items = [
            item
            for item in api_state.store.collections.values()
            if memory_object_visible(
                owner_map=api_state.store.collection_owners,
                object_id=item.id,
                user_id=user.id,
            )
            if item.deleted_at is None
        ]
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
    return PaginatedCollections(items=page_items, next_cursor=next_cursor)


@router.patch("/collections/{collection_id}", response_model=CollectionResponse)
def patch_collection(
    collection_id: str,
    payload: CollectionPatch,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> CollectionResponse:
    collection = None
    if api_state.supabase_gateway is not None:
        collection = api_state.supabase_gateway.get_collection(
            user_id=user.id,
            collection_id=collection_id,
        )
    else:
        if memory_object_visible(
            owner_map=api_state.store.collection_owners,
            object_id=collection_id,
            user_id=user.id,
        ):
            collection = api_state.store.collections.get(collection_id)

    if not collection:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Collection not found.",
        )

    patch = payload.model_dump(exclude_unset=True)
    if patch.get("name"):
        patch["name_source"] = "user_renamed"

    if api_state.supabase_gateway is not None:
        updated = api_state.supabase_gateway.patch_collection(
            user_id=user.id,
            collection_id=collection_id,
            patch=patch,
        )
    else:
        data = collection.model_dump()
        data.update(patch)
        data["updated_at"] = utcnow()
        updated = Collection.model_validate(data)
        api_state.store.collections[collection_id] = updated
    return CollectionResponse(collection=updated)


@router.delete("/collections/{collection_id}", response_model=SuccessResponse)
def delete_collection(
    collection_id: str,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> SuccessResponse:
    collection = None
    if api_state.supabase_gateway is not None:
        collection = api_state.supabase_gateway.get_collection(
            user_id=user.id,
            collection_id=collection_id,
        )
    else:
        if memory_object_visible(
            owner_map=api_state.store.collection_owners,
            object_id=collection_id,
            user_id=user.id,
        ):
            collection = api_state.store.collections.get(collection_id)

    if not collection:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Collection not found.",
        )

    if api_state.supabase_gateway is not None:
        api_state.supabase_gateway.soft_delete_collection(
            user_id=user.id,
            collection_id=collection_id,
        )
    else:
        api_state.store.collections[collection_id] = collection.model_copy(
            update={"deleted_at": utcnow(), "updated_at": utcnow()}
        )
    return SuccessResponse(success=True)


@router.post(
    "/collections/{collection_id}/strategies",
    response_model=CollectionResponse,
)
def attach_strategies(
    collection_id: str,
    payload: CollectionAttach,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> CollectionResponse:
    if api_state.supabase_gateway is not None:
        try:
            updated = api_state.supabase_gateway.attach_strategies(
                user_id=user.id,
                collection_id=collection_id,
                strategy_ids=payload.strategy_ids,
            )
            if not updated:
                raise problem(
                    request,
                    status_code=404,
                    code="not_found",
                    title="Not Found",
                    detail="Collection not found.",
                )
            return CollectionResponse(collection=updated)
        except ValueError as exc:
            raise problem(
                request,
                status_code=400,
                code="bad_request",
                title="Bad Request",
                detail=str(exc),
            ) from exc

    collection = None
    if memory_object_visible(
        owner_map=api_state.store.collection_owners,
        object_id=collection_id,
        user_id=user.id,
    ):
        collection = api_state.store.collections.get(collection_id)
    if not collection:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Collection not found.",
        )
    attached = api_state.store.collection_strategies.setdefault(collection_id, set())
    for strategy_id in payload.strategy_ids:
        if strategy_id in api_state.store.strategies and memory_object_visible(
            owner_map=api_state.store.strategy_owners,
            object_id=strategy_id,
            user_id=user.id,
        ):
            attached.add(strategy_id)
    updated = collection.model_copy(
        update={"strategy_count": len(attached), "updated_at": utcnow()}
    )
    api_state.store.collections[collection_id] = updated
    return CollectionResponse(collection=updated)


@router.delete(
    "/collections/{collection_id}/strategies/{strategy_id}",
    response_model=SuccessResponse,
)
def detach_strategy(
    collection_id: str,
    strategy_id: str,
    user: User = Depends(current_user),  # noqa: B008
) -> SuccessResponse:
    if api_state.supabase_gateway is not None:
        api_state.supabase_gateway.detach_strategy(
            user_id=user.id,
            collection_id=collection_id,
            strategy_id=strategy_id,
        )
    else:
        if not memory_object_visible(
            owner_map=api_state.store.collection_owners,
            object_id=collection_id,
            user_id=user.id,
        ):
            return SuccessResponse(success=True)
        api_state.store.collection_strategies.setdefault(collection_id, set()).discard(
            strategy_id
        )
        collection = api_state.store.collections.get(collection_id)
        if collection:
            api_state.store.collections[collection_id] = collection.model_copy(
                update={
                    "strategy_count": len(
                        api_state.store.collection_strategies[collection_id]
                    ),
                    "updated_at": utcnow(),
                }
            )
    return SuccessResponse(success=True)
