from __future__ import annotations

import json
import os
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from argus.api import state as api_state
from argus.api.schemas import User


async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("x-request-id") or api_state.store.new_id()
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
    headers: dict[str, str] | None = None,
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
    return HTTPException(status_code=status_code, detail=body, headers=headers)


def private_alpha_access_problem(request: Request) -> HTTPException:
    return problem(
        request,
        status_code=403,
        code="private_alpha_access_required",
        title="Private Alpha Access",
        detail=(
            "Argus is in private alpha right now. Use the email that was "
            "invited, or ask the Argus team for access."
        ),
    )


def auth_response(request: Request, payload: dict[str, Any]) -> JSONResponse:
    response = JSONResponse(payload)
    session = payload.get("session")
    if not isinstance(session, dict):
        return response

    access_token = session.get("access_token")
    refresh_token = session.get("refresh_token")
    max_age = session.get("expires_in")
    cookie_kwargs: dict[str, Any] = {
        "httponly": True,
        "path": "/",
        "samesite": "lax",
        "secure": request.url.scheme == "https",
    }
    if isinstance(max_age, int):
        cookie_kwargs["max_age"] = max_age

    if isinstance(access_token, str) and access_token:
        response.set_cookie("sb-auth-token", access_token, **cookie_kwargs)
    if isinstance(refresh_token, str) and refresh_token:
        response.set_cookie("sb-refresh-token", refresh_token, **cookie_kwargs)
    return response


def dev_memory_fallback_enabled() -> bool:
    return os.getenv("ARGUS_DEV_MEMORY_FALLBACK", "").strip().lower() == "true"


def current_user(request: Request) -> User:
    if (
        os.getenv("NEXT_PUBLIC_MOCK_AUTH", "").strip().lower() == "true"
        or os.getenv("ARGUS_MOCK_AUTH", "").strip().lower() == "true"
    ):
        if api_state.supabase_gateway is not None:
            try:
                return api_state.supabase_gateway.get_or_create_mock_user()
            except Exception:
                if not dev_memory_fallback_enabled():
                    raise
        return api_state.store.get_or_create_dev_user()

    if api_state.supabase_gateway is None:
        raise problem(
            request,
            status_code=500,
            code="internal_error",
            title="Internal Error",
            detail="Supabase persistence is required for non-mock authentication.",
        )

    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ")
    else:
        potential_tokens = []
        for key, value in request.cookies.items():
            if key.startswith("sb-") and ("auth-token" in key or "access-token" in key):
                try:
                    clean_value = value.strip('"')
                    if clean_value.startswith("{") or clean_value.startswith("["):
                        token_data = json.loads(clean_value)
                        extracted = (
                            token_data.get("access_token")
                            if isinstance(token_data, dict)
                            else None
                        )
                        if extracted:
                            potential_tokens.append(extracted)
                    else:
                        potential_tokens.append(clean_value)
                except Exception:
                    potential_tokens.append(value)

        for token_value in potential_tokens:
            if token_value:
                token = token_value
                break

    if not token:
        raise problem(
            request,
            status_code=401,
            code="unauthorized",
            title="Unauthorized",
            detail="Missing or invalid Authorization header or session cookie.",
        )

    try:
        auth_user = api_state.supabase_gateway.get_auth_user_from_token(token)
    except Exception:
        raise problem(
            request,
            status_code=401,
            code="unauthorized",
            title="Unauthorized",
            detail="Invalid or expired access token.",
        ) from None

    auth_email = str(auth_user.get("email") or "")
    if not api_state.supabase_gateway.private_alpha_email_allowed(auth_email):
        raise private_alpha_access_problem(request)

    return api_state.supabase_gateway.get_or_create_profile_for_auth_user(auth_user)
