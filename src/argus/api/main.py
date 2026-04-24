from __future__ import annotations

import json
import os
from collections.abc import Iterable
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

load_dotenv()

from argus.api.schemas import (
    BacktestRun,
    BacktestRunRequest,
    BacktestRunResponse,
    ChatStreamRequest,
    Collection,
    CollectionAttach,
    CollectionCreate,
    CollectionPatch,
    CollectionResponse,
    Conversation,
    ConversationCreate,
    ConversationPatch,
    ConversationResponse,
    FeedbackRequest,
    HistoryItem,
    Message,
    PaginatedCollections,
    PaginatedConversations,
    PaginatedHistory,
    PaginatedMessages,
    PaginatedSearch,
    PaginatedStrategies,
    ProfilePatch,
    SearchItem,
    Strategy,
    StrategyCreate,
    StrategyPatch,
    StrategyResponse,
    SuccessResponse,
    User,
    UserResponse,
)
from argus.domain.engine import (
    build_result_card,
    classify_symbol,
    compute_alpha_metrics,
    default_benchmark,
    normalize_backtest_config,
    validate_backtest_config,
)
from argus.domain.orchestrator import assistant_copy_for_result, extract_strategy_request
from argus.domain.store import AlphaStore, utcnow
from argus.domain.supabase_gateway import QuotaExceededError, SupabaseGateway

app = FastAPI(title="Argus Alpha API", version="1.0.0-alpha")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
store = AlphaStore()
PERSISTENCE_MODE = os.getenv("ARGUS_PERSISTENCE_MODE", "memory").strip().lower()
supabase_gateway = SupabaseGateway.from_env() if PERSISTENCE_MODE == "supabase" else None


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("x-request-id") or store.new_id()
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    response.headers.setdefault("X-RateLimit-Limit", "200")
    response.headers.setdefault("X-RateLimit-Remaining", "199")
    response.headers.setdefault("X-RateLimit-Reset", "3600")
    return response


def problem(
    request: Request,
    *,
    status_code: int,
    code: str,
    title: str,
    detail: str,
    context: dict[str, Any] | None = None,
) -> HTTPException:
    body = {
        "type": f"https://api.argus.app/problems/{code.replace('_', '-')}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "code": code,
        "request_id": request.state.request_id,
    }
    if context:
        body["context"] = context
    return HTTPException(status_code=status_code, detail=body)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):  # type: ignore[no-untyped-def]
    from fastapi.responses import JSONResponse

    if isinstance(exc.detail, dict) and "code" in exc.detail:
        return JSONResponse(exc.detail, status_code=exc.status_code)
    body = {
        "type": "https://api.argus.app/problems/http-error",
        "title": "Request Failed",
        "status": exc.status_code,
        "detail": str(exc.detail),
        "code": "http_error",
        "request_id": request.state.request_id,
    }
    return JSONResponse(body, status_code=exc.status_code)


def current_user() -> User:
    return store.get_or_create_dev_user()


@app.post("/api/v1/dev/reset", response_model=SuccessResponse)
def dev_reset() -> SuccessResponse:
    store.reset()
    store.get_or_create_dev_user()
    return SuccessResponse(success=True)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "version": "1.0.0-alpha"}


@app.get("/api/v1/auth/session")
def auth_session(user: User = Depends(current_user)) -> dict[str, Any]:  # noqa: B008
    return {"authenticated": True, "user": user.model_dump(mode="json")}


@app.post("/api/v1/auth/signup")
def signup(user: User = Depends(current_user)) -> dict[str, Any]:  # noqa: B008
    return {"user": user.model_dump(mode="json"), "session": {"mock": True}}


@app.post("/api/v1/auth/login")
def login(user: User = Depends(current_user)) -> dict[str, Any]:  # noqa: B008
    return {"user": user.model_dump(mode="json"), "session": {"mock": True}}


@app.post("/api/v1/auth/logout", response_model=SuccessResponse)
def logout() -> SuccessResponse:
    return SuccessResponse(success=True)


@app.get("/api/v1/me", response_model=UserResponse)
def get_me(user: User = Depends(current_user)) -> UserResponse:  # noqa: B008
    if supabase_gateway is not None:
        prof = supabase_gateway.get_user(user_id=user.id)
        if prof:
            return UserResponse(user=prof)
    return UserResponse(user=user)


@app.patch("/api/v1/me", response_model=UserResponse)
def patch_me(
    patch: ProfilePatch,
    user: User = Depends(current_user),  # noqa: B008
) -> UserResponse:
    data = user.model_dump()
    updates = patch.model_dump(exclude_unset=True)
    onboarding_patch = updates.pop("onboarding", None)
    data.update(updates)
    if onboarding_patch:
        onboarding = user.onboarding.model_dump()
        onboarding.update(onboarding_patch)
        data["onboarding"] = onboarding
    data["updated_at"] = utcnow()
    updated = User.model_validate(data)
    store.users[user.id] = updated
    return UserResponse(user=updated)


@app.post("/api/v1/conversations", response_model=ConversationResponse)
def create_conversation(
    payload: ConversationCreate,
    user: User = Depends(current_user),  # noqa: B008
) -> ConversationResponse:
    now = utcnow()
    title = payload.title or "New idea"
    conversation = Conversation(
        id=store.new_id(),
        title=title,
        title_source="user_renamed" if payload.title else "system_default",
        language=payload.language or user.language,
        created_at=now,
        updated_at=now,
    )
    store.conversations[conversation.id] = conversation
    store.messages[conversation.id] = []
    return ConversationResponse(conversation=conversation)


@app.get("/api/v1/conversations", response_model=PaginatedConversations)
def list_conversations(
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedConversations:
    items = [
        conversation
        for conversation in store.conversations.values()
        if conversation.deleted_at is None
    ]
    items.sort(key=lambda item: (item.pinned, item.updated_at), reverse=True)
    return PaginatedConversations(items=items[:limit])


@app.patch("/api/v1/conversations/{conversation_id}", response_model=ConversationResponse)
def patch_conversation(
    conversation_id: str,
    payload: ConversationPatch,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
):
    conversation = (
        supabase_gateway.get_conversation(
            user_id=user.id, conversation_id=conversation_id
        )
        if supabase_gateway
        else store.conversations.get(conversation_id)
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
    if supabase_gateway is not None:
        updated = supabase_gateway.patch_conversation(
            user_id=user.id, conversation_id=conversation_id, patch=patch
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
        store.conversations[conversation_id] = updated
    return ConversationResponse(conversation=updated)


@app.delete("/api/v1/conversations/{conversation_id}", response_model=SuccessResponse)
def delete_conversation(
    conversation_id: str,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
):
    conversation = store.conversations.get(conversation_id)
    if not conversation:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Conversation not found.",
        )
    if supabase_gateway is not None:
        supabase_gateway.soft_delete_conversation(
            user_id=user.id, conversation_id=conversation_id
        )
    else:
        store.conversations[conversation_id] = conversation.model_copy(
            update={"deleted_at": utcnow(), "updated_at": utcnow()}
        )
    return SuccessResponse(success=True)


@app.get(
    "/api/v1/conversations/{conversation_id}/messages", response_model=PaginatedMessages
)
def list_messages(conversation_id: str, limit: int = Query(50, ge=1, le=100)):
    return PaginatedMessages(items=store.messages.get(conversation_id, [])[:limit])


def ensure_same_asset_or_raise(symbols: list[str], request: Request) -> str:
    classified = [classify_symbol(symbol) for symbol in symbols]
    classes = {entry.asset_class for entry in classified}
    if len(classes) > 1:
        raise problem(
            request,
            status_code=422,
            code="mixed_asset_not_supported",
            title="Mixed Asset Simulation Not Supported",
            detail="Alpha supports grouped symbols within the same asset class only.",
            context={
                "conflicting_symbols": [
                    {"symbol": entry.symbol, "asset_class": entry.asset_class}
                    for entry in classified
                ]
            },
        )
    return classified[0].asset_class


def create_run_from_payload(
    payload: dict[str, Any],
    request: Request,
    *,
    strategy_id: str | None = None,
    conversation_id: str | None = None,
) -> BacktestRun:
    symbols = payload.get("symbols") or []
    if not symbols:
        raise problem(
            request,
            status_code=400,
            code="validation_error",
            title="Validation Error",
            detail="Symbol is required.",
        )
    inferred_asset_class = ensure_same_asset_or_raise(symbols, request)
    payload["asset_class"] = payload.get("asset_class") or inferred_asset_class
    if payload["asset_class"] != inferred_asset_class:
        ensure_same_asset_or_raise(symbols, request)
    payload["benchmark_symbol"] = payload.get("benchmark_symbol") or default_benchmark(
        payload["asset_class"]
    )
    config = normalize_backtest_config(payload)
    try:
        validate_backtest_config(config)
    except ValueError as exc:
        code = str(exc)
        raise problem(
            request,
            status_code=422,
            code=code,
            title="Invalid Backtest Request",
            detail=f"Backtest request failed Alpha validation: {code}.",
        ) from exc
    metrics = compute_alpha_metrics(config)
    now = utcnow()
    run = BacktestRun(
        id=store.new_id(),
        conversation_id=conversation_id or payload.get("conversation_id"),
        strategy_id=strategy_id or payload.get("strategy_id"),
        status="completed",
        asset_class=config["asset_class"],
        symbols=config["symbols"],
        allocation_method="equal_weight",
        benchmark_symbol=config["benchmark_symbol"],
        metrics=metrics,
        config_snapshot=config,
        conversation_result_card=build_result_card(config, metrics),
        created_at=now,
        chart={
            "equity_curve": [
                config["starting_capital"],
                config["starting_capital"]
                + metrics["aggregate"]["performance"]["profit"],
            ]
        },
        trades=[],
    )
    store.backtest_runs[run.id] = run
    return run


@app.post("/api/v1/backtests/run", response_model=BacktestRunResponse)
def run_backtest(
    payload: BacktestRunRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(current_user),  # noqa: B008
) -> BacktestRunResponse:
    endpoint = "/api/v1/backtests/run"
    if idempotency_key:
        cached = store.idempotency.get((user.id, endpoint, idempotency_key))
        if cached:
            return BacktestRunResponse(run=cached)

    if supabase_gateway is not None:
        try:
            supabase_gateway.check_and_increment_usage(
                user_id=user.id, resource="backtest_runs", period="day", limit_count=50
            )
            supabase_gateway.check_and_increment_usage(
                user_id=user.id, resource="backtest_runs", period="hour", limit_count=10
            )
        except QuotaExceededError as e:
            raise problem(
                request,
                status_code=429,
                code="too_many_requests",
                title="Quota Exceeded",
                detail=str(e),
            ) from e

    data = payload.model_dump(exclude_none=True)
    if payload.strategy_id:
        strategy = store.strategies.get(payload.strategy_id)
        if not strategy:
            raise problem(
                request,
                status_code=404,
                code="not_found",
                title="Not Found",
                detail="Strategy not found.",
            )
        strategy_data = strategy.model_dump()
        data = {
            **strategy_data,
            **data,
            "template": strategy.template,
            "asset_class": strategy.asset_class,
            "symbols": data.get("symbols") or strategy.symbols,
            "parameters": strategy.parameters,
            "benchmark_symbol": strategy.benchmark_symbol,
        }
    if not data.get("template"):
        data["template"] = "rsi_mean_reversion"
    run = create_run_from_payload(data, request)
    if idempotency_key:
        store.idempotency[(user.id, endpoint, idempotency_key)] = run
    return BacktestRunResponse(run=run)


@app.get("/api/v1/backtests/{run_id}", response_model=BacktestRunResponse)
def get_backtest(run_id: str, request: Request) -> BacktestRunResponse:
    run = store.backtest_runs.get(run_id)
    if not run:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Backtest run not found.",
        )
    return BacktestRunResponse(run=run)


@app.post("/api/v1/strategies", response_model=StrategyResponse)
def create_strategy(
    payload: StrategyCreate, user: User = Depends(current_user)
) -> StrategyResponse:
    if supabase_gateway is not None:
        strategy = supabase_gateway.create_strategy(user_id=user.id, payload=payload)
    else:
        now = utcnow()
        benchmark = payload.benchmark_symbol or default_benchmark(payload.asset_class)
        strategy = Strategy(
            id=store.new_id(),
            name=payload.name or f"{', '.join(payload.symbols)} idea",
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
        store.strategies[strategy.id] = strategy
    return StrategyResponse(strategy=strategy)


@app.get("/api/v1/strategies", response_model=PaginatedStrategies)
def list_strategies(
    limit: int = Query(20, ge=1, le=100), user: User = Depends(current_user)
) -> PaginatedStrategies:
    if supabase_gateway is not None:
        items = supabase_gateway.list_strategies(user_id=user.id, limit=limit)
    else:
        items = [item for item in store.strategies.values() if item.deleted_at is None]
        items.sort(key=lambda item: (item.pinned, item.updated_at), reverse=True)
        items = items[:limit]
    return PaginatedStrategies(items=items)


@app.patch("/api/v1/strategies/{strategy_id}", response_model=StrategyResponse)
def patch_strategy(strategy_id: str, payload: StrategyPatch, request: Request):
    strategy = store.strategies.get(strategy_id)
    if not strategy:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Strategy not found.",
        )
    data = strategy.model_dump()
    patch = payload.model_dump(exclude_unset=True)
    if patch.get("name"):
        patch["name_source"] = "user_renamed"
    data.update(patch)
    data["updated_at"] = utcnow()
    updated = Strategy.model_validate(data)
    store.strategies[strategy_id] = updated
    return StrategyResponse(strategy=updated)


@app.delete("/api/v1/strategies/{strategy_id}", response_model=SuccessResponse)
def delete_strategy(strategy_id: str, request: Request) -> SuccessResponse:
    strategy = store.strategies.get(strategy_id)
    if not strategy:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Strategy not found.",
        )
    store.strategies[strategy_id] = strategy.model_copy(
        update={"deleted_at": utcnow(), "updated_at": utcnow()}
    )
    return SuccessResponse(success=True)


@app.post("/api/v1/collections", response_model=CollectionResponse)
def create_collection(payload: CollectionCreate) -> CollectionResponse:
    now = utcnow()
    collection = Collection(
        id=store.new_id(),
        name=payload.name or "New collection",
        name_source="user_renamed" if payload.name else "ai_generated",
        created_at=now,
        updated_at=now,
    )
    store.collections[collection.id] = collection
    store.collection_strategies[collection.id] = set()
    return CollectionResponse(collection=collection)


@app.get("/api/v1/collections", response_model=PaginatedCollections)
def list_collections(limit: int = Query(20, ge=1, le=100)) -> PaginatedCollections:
    items = [item for item in store.collections.values() if item.deleted_at is None]
    items.sort(key=lambda item: (item.pinned, item.updated_at), reverse=True)
    return PaginatedCollections(items=items[:limit])


@app.patch("/api/v1/collections/{collection_id}", response_model=CollectionResponse)
def patch_collection(collection_id: str, payload: CollectionPatch, request: Request):
    collection = store.collections.get(collection_id)
    if not collection:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Collection not found.",
        )
    data = collection.model_dump()
    patch = payload.model_dump(exclude_unset=True)
    if patch.get("name"):
        patch["name_source"] = "user_renamed"
    data.update(patch)
    data["updated_at"] = utcnow()
    updated = Collection.model_validate(data)
    store.collections[collection_id] = updated
    return CollectionResponse(collection=updated)


@app.delete("/api/v1/collections/{collection_id}", response_model=SuccessResponse)
def delete_collection(collection_id: str, request: Request) -> SuccessResponse:
    collection = store.collections.get(collection_id)
    if not collection:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Collection not found.",
        )
    store.collections[collection_id] = collection.model_copy(
        update={"deleted_at": utcnow(), "updated_at": utcnow()}
    )
    return SuccessResponse(success=True)


@app.post(
    "/api/v1/collections/{collection_id}/strategies", response_model=CollectionResponse
)
def attach_strategies(
    collection_id: str, payload: CollectionAttach, request: Request
) -> CollectionResponse:
    collection = store.collections.get(collection_id)
    if not collection:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Collection not found.",
        )
    attached = store.collection_strategies.setdefault(collection_id, set())
    for strategy_id in payload.strategy_ids:
        if strategy_id in store.strategies:
            attached.add(strategy_id)
    updated = collection.model_copy(
        update={"strategy_count": len(attached), "updated_at": utcnow()}
    )
    store.collections[collection_id] = updated
    return CollectionResponse(collection=updated)


@app.delete(
    "/api/v1/collections/{collection_id}/strategies/{strategy_id}",
    response_model=SuccessResponse,
)
def detach_strategy(collection_id: str, strategy_id: str) -> SuccessResponse:
    store.collection_strategies.setdefault(collection_id, set()).discard(strategy_id)
    collection = store.collections.get(collection_id)
    if collection:
        store.collections[collection_id] = collection.model_copy(
            update={
                "strategy_count": len(store.collection_strategies[collection_id]),
                "updated_at": utcnow(),
            }
        )
    return SuccessResponse(success=True)


@app.get("/api/v1/history", response_model=PaginatedHistory)
def history(limit: int = Query(20, ge=1, le=100)) -> PaginatedHistory:
    items: list[HistoryItem] = []
    for run in store.backtest_runs.values():
        items.append(
            HistoryItem(
                type="run",
                id=run.id,
                title=run.conversation_result_card["title"],
                subtitle=run.conversation_result_card["rows"][0]["value"],
                created_at=run.created_at,
            )
        )
    for conversation in store.conversations.values():
        if conversation.deleted_at is None:
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
    for strategy in store.strategies.values():
        if strategy.deleted_at is None:
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
    for collection in store.collections.values():
        if collection.deleted_at is None:
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
    items.sort(key=lambda item: (item.pinned, item.created_at), reverse=True)
    return PaginatedHistory(items=items[:limit])


@app.get("/api/v1/search", response_model=PaginatedSearch)
def search(q: str, limit: int = Query(20, ge=1, le=100)) -> PaginatedSearch:
    query = q.lower()
    items: list[SearchItem] = []
    for conversation in store.conversations.values():
        haystack = f"{conversation.title} {conversation.last_message_preview or ''}"
        if query in haystack.lower():
            items.append(
                SearchItem(
                    type="chat",
                    id=conversation.id,
                    title=conversation.title,
                    matched_text=conversation.last_message_preview or conversation.title,
                    updated_at=conversation.updated_at,
                )
            )
    for strategy in store.strategies.values():
        haystack = f"{strategy.name} {' '.join(strategy.symbols)} {strategy.template}"
        if query in haystack.lower():
            items.append(
                SearchItem(
                    type="strategy",
                    id=strategy.id,
                    title=strategy.name,
                    matched_text=", ".join(strategy.symbols),
                    updated_at=strategy.updated_at,
                )
            )
    for collection in store.collections.values():
        if query in collection.name.lower():
            items.append(
                SearchItem(
                    type="collection",
                    id=collection.id,
                    title=collection.name,
                    matched_text=collection.name,
                    updated_at=collection.updated_at,
                )
            )
    items.sort(key=lambda item: item.updated_at, reverse=True)
    return PaginatedSearch(items=items[:limit])


def sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


@app.post("/api/v1/chat/stream")
def chat_stream(
    payload: ChatStreamRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(current_user),
):
    if supabase_gateway is not None:
        try:
            supabase_gateway.check_and_increment_usage(
                user_id=user.id, resource="chat_messages", period="day", limit_count=200
            )
            supabase_gateway.check_and_increment_usage(
                user_id=user.id, resource="chat_messages", period="minute", limit_count=10
            )
        except QuotaExceededError as e:
            raise problem(
                request,
                status_code=429,
                code="too_many_requests",
                title="Quota Exceeded",
                detail=str(e),
            ) from e

    conversation = (
        supabase_gateway.get_conversation(
            user_id=user.id, conversation_id=payload.conversation_id
        )
        if supabase_gateway
        else store.conversations.get(payload.conversation_id)
    )
    if not conversation:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Conversation not found.",
        )
    now = utcnow()
    user_message = Message(
        id=store.new_id(),
        conversation_id=conversation.id,
        role="user",
        content=payload.message,
        created_at=now,
    )
    store.messages.setdefault(conversation.id, []).append(user_message)
    extracted = extract_strategy_request(payload.message)

    def events() -> Iterable[str]:
        yield sse("status", {"status": "extracting_strategy"})
        yield sse("token", {"text": "I can test that as a supported Alpha strategy. "})
        yield sse("status", {"status": "running_backtest"})
        run = create_run_from_payload(
            {
                **extracted,
                "conversation_id": conversation.id,
                "timeframe": "1D",
            },
            request,
            conversation_id=conversation.id,
        )
        assistant_text = assistant_copy_for_result(
            run.symbols, payload.language or conversation.language or "en"
        )
        assistant_message = Message(
            id=store.new_id(),
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_text,
            created_at=utcnow(),
        )
        store.messages[conversation.id].append(assistant_message)
        title = f"{run.symbols[0]} dip idea"
        if conversation.title_source == "system_default":
            updated = conversation.model_copy(
                update={
                    "title": title,
                    "title_source": "ai_generated",
                    "last_message_preview": payload.message[:120],
                    "updated_at": utcnow(),
                }
            )
            store.conversations[conversation.id] = updated
            yield sse("title", {"conversation_id": conversation.id, "title": title})
        yield sse("token", {"text": assistant_text})
        yield sse("result", {"run": run.model_dump(mode="json")})
        yield sse("done", {"message_id": assistant_message.id})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )


@app.post("/api/v1/feedback", response_model=SuccessResponse)
def feedback(payload: FeedbackRequest, user: User = Depends(current_user)):  # noqa: B008
    store.feedback.append(
        {
            "id": store.new_id(),
            "user_id": user.id,
            "type": payload.type,
            "message": payload.message,
            "context": payload.context,
            "created_at": utcnow(),
        }
    )
    return SuccessResponse(success=True)
