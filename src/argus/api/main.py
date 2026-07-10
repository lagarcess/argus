from __future__ import annotations

from fastapi import FastAPI

from argus.api import app_setup, pagination, search_utils
from argus.api import state as api_state
from argus.api.routers import (
    agent,
    auth,
    backtest,
    collections,
    conversations,
    dev,
    discovery,
    evidence,
    feedback,
    history,
    ops,
    profile,
    search,
    strategies,
)

cors_allow_origins = app_setup.cors_allow_origins
app = FastAPI(
    title="Argus Alpha API",
    version="1.0.0-alpha",
    lifespan=app_setup.lifespan,
)
app_setup.add_core_middleware_and_handlers(app)


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
    evidence.router,
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
