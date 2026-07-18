from __future__ import annotations

import functools
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from argus.api import state as api_state
from argus.api.dependencies import request_id_middleware

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
    app.state.agent_runtime_workflow = None
    try:
        yield
    finally:
        if checkpointer_cm is not None:
            await checkpointer_cm.__aexit__(None, None, None)


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


def _json_safe_validation_error(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, BaseException):
        return str(value)
    if isinstance(value, dict):
        return {
            str(key): _json_safe_validation_error(nested) for key, nested in value.items()
        }
    if isinstance(value, list | tuple):
        return [_json_safe_validation_error(nested) for nested in value]
    return str(value)


def _json_safe_validation_errors(
    errors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {str(key): _json_safe_validation_error(value) for key, value in error.items()}
        for error in errors
    ]


async def unexpected_exception_handler(  # type: ignore[no-untyped-def]
    request: Request,
    exc: Exception,
):
    """#235: unexpected failures return safe RFC 9457 with the request's
    correlation id and no request body, secret, provider detail, or trace."""

    request_id = getattr(request.state, "request_id", None) or api_state.store.new_id()
    # Ops correlation only: the exception class and route, never the message
    # (which can embed provider or secret material), body, or a traceback.
    logger.error(
        "Unhandled request failure",
        request_id=request_id,
        error_type=type(exc).__name__,
        method=request.method,
        path=request.url.path,
    )
    body = {
        "type": "https://api.argus.app/problems/internal-error",
        "title": "Internal Error",
        "status": 500,
        "detail": "The request failed unexpectedly. Retry in a moment.",
        "code": "internal_error",
        "request_id": request_id,
    }
    origin = request.headers.get("origin")
    headers: dict[str, str] = {"X-Request-Id": request_id}
    if origin in cors_allow_origins():
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(body, status_code=500, headers=headers)


async def validation_exception_handler(  # type: ignore[no-untyped-def]
    request: Request,
    exc: RequestValidationError,
):
    body = {
        "type": "https://api.argus.app/problems/validation-error",
        "title": "Validation Error",
        "status": 422,
        "detail": "The request body or parameters did not match the API contract.",
        "code": "validation_error",
        "request_id": getattr(request.state, "request_id", api_state.store.new_id()),
        "context": {"errors": _json_safe_validation_errors(exc.errors())},
    }

    origin = request.headers.get("origin")
    headers: dict[str, str] = {}
    if origin in cors_allow_origins():
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(body, status_code=422, headers=headers)


def add_core_middleware_and_handlers(app: FastAPI) -> None:
    from argus.api.chat_request_bounds import ChatStreamBodyLimitMiddleware

    app.middleware("http")(request_id_middleware)
    app.add_middleware(ChatStreamBodyLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allow_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unexpected_exception_handler)
