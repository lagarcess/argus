from __future__ import annotations

import functools
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from argus.api import pagination, search_utils
from argus.api import state as api_state
from argus.api.chat.breakdown import llm_result_breakdown_message
from argus.api.chat.confirmation import runtime_confirmation_card
from argus.api.dependencies import request_id_middleware
from argus.api.routers import (
    agent,
    auth,
    backtest,
    collections,
    conversations,
    dev,
    discovery,
    feedback,
    history,
    ops,
    profile,
    search,
    strategies,
)

DEFAULT_CORS_ALLOW_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
)


@functools.lru_cache(maxsize=16)
def _cors_allow_origins_for(configured: str) -> tuple[str, ...]:
    extra_origins = [
        origin.strip()
        for origin in configured.replace("\n", ",").split(",")
        if origin.strip()
    ]
    return tuple(dict.fromkeys([*DEFAULT_CORS_ALLOW_ORIGINS, *extra_origins]))


def cors_allow_origins() -> list[str]:
    configured = os.getenv("ARGUS_CORS_ALLOW_ORIGINS", "")
    return list(_cors_allow_origins_for(configured))


@asynccontextmanager
async def lifespan(app: FastAPI):
    checkpointer_cm = None
    if api_state.CHECKPOINTER_MODE == "postgres":
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        checkpointer_cm = AsyncPostgresSaver.from_conn_string(
            api_state.DATABASE_URL,
            serde=api_state.build_agent_runtime_checkpoint_serde(),
        )
        checkpointer = await checkpointer_cm.__aenter__()
        await checkpointer.setup()
    else:
        if api_state.PERSISTENCE_MODE == "supabase":
            logger.info(
                "Using Supabase product persistence with memory LangGraph checkpointer",
                checkpointer_mode=api_state.CHECKPOINTER_MODE,
            )
        checkpointer = api_state.build_agent_runtime_checkpointer()

    app.state.agent_runtime_checkpointer = checkpointer
    app.state.agent_runtime_checkpointer_cm = checkpointer_cm
    app.state.agent_runtime_workflow = api_state.build_agent_runtime_workflow(
        checkpointer=checkpointer
    )
    try:
        yield
    finally:
        if checkpointer_cm is not None:
            await checkpointer_cm.__aexit__(None, None, None)


app = FastAPI(title="Argus Alpha API", version="1.0.0-alpha", lifespan=lifespan)
app.middleware("http")(request_id_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):  # type: ignore[no-untyped-def]
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        body = exc.detail
    else:
        body = {
            "type": "https://api.argus.app/problems/http-error",
            "title": "Request Failed",
            "status": exc.status_code,
            "detail": str(exc.detail),
            "code": "http_error",
            "request_id": request.state.request_id,
        }

    origin = request.headers.get("origin")
    headers = dict(exc.headers or {})
    if origin in cors_allow_origins():
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(body, status_code=exc.status_code, headers=headers)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "version": "1.0.0-alpha"}


for api_router in (
    auth.router,
    profile.router,
    conversations.router,
    strategies.router,
    collections.router,
    backtest.router,
    agent.router,
    history.router,
    search.router,
    discovery.router,
    feedback.router,
    ops.router,
    dev.router,
):
    app.include_router(api_router)


store = api_state.store
supabase_gateway = api_state.supabase_gateway
_encode_cursor = pagination.encode_cursor
_decode_cursor = pagination.decode_cursor
_search_type_rank = search_utils.search_type_rank
_score_search_item = search_utils.score_search_item
_runtime_confirmation_card = runtime_confirmation_card
_llm_result_breakdown_message = llm_result_breakdown_message
