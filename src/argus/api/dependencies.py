from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from argus.api import state as api_state
from argus.api.auth_sessions import (
    AuthSessionVerificationUnavailable,
    auth_session_is_active,
)
from argus.api.guest_access import (
    guest_access_enabled,
    guest_account_context,
    permanent_account_access_allowed,
    registered_account_context,
    store_account_context,
)
from argus.api.schemas import User


async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("x-request-id") or api_state.store.new_id()
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
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
        "secure": _session_cookie_secure(request),
    }
    if isinstance(max_age, int):
        cookie_kwargs["max_age"] = max_age

    if isinstance(access_token, str) and access_token:
        response.set_cookie("sb-auth-token", access_token, **cookie_kwargs)
    if isinstance(refresh_token, str) and refresh_token:
        response.set_cookie("sb-refresh-token", refresh_token, **cookie_kwargs)
    return response


def _session_cookie_secure(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    forwarded_scheme = forwarded_proto.split(",", 1)[0].strip().lower()
    return (
        request.url.scheme == "https"
        or forwarded_scheme == "https"
        or _production_like_environment()
    )


def _production_like_environment() -> bool:
    for name in ("APP_ENV", "ENVIRONMENT", "ARGUS_ENV", "ARGUS_APP_ENV"):
        value = os.getenv(name, "").strip().lower()
        if value in {"production", "prod", "staging"}:
            return True
    return False


def dev_memory_fallback_enabled() -> bool:
    return os.getenv("ARGUS_DEV_MEMORY_FALLBACK", "").strip().lower() == "true"


def current_user(request: Request) -> User:
    if (
        os.getenv("NEXT_PUBLIC_MOCK_AUTH", "").strip().lower() == "true"
        or os.getenv("ARGUS_MOCK_AUTH", "").strip().lower() == "true"
    ):
        if api_state.supabase_gateway is not None:
            try:
                user = api_state.supabase_gateway.get_or_create_mock_user()
                store_account_context(request, registered_account_context(user.id))
                return user
            except Exception:
                if not dev_memory_fallback_enabled():
                    raise
        user = api_state.store.get_or_create_dev_user()
        store_account_context(request, registered_account_context(user.id))
        return user

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

    auth_user_id = str(auth_user.get("id") or "")
    try:
        session_is_active = auth_session_is_active(
            database_url=api_state.DATABASE_URL,
            token=token,
            user_id=auth_user_id,
        )
    except AuthSessionVerificationUnavailable:
        raise problem(
            request,
            status_code=503,
            code="auth_session_verification_unavailable",
            title="Session Verification Unavailable",
            detail="Argus could not verify this session. Please try again.",
        ) from None
    if not session_is_active:
        raise problem(
            request,
            status_code=401,
            code="unauthorized",
            title="Unauthorized",
            detail="Invalid or expired access token.",
        )

    if auth_user.get("is_anonymous") is True:
        if not guest_access_enabled():
            raise problem(
                request,
                status_code=403,
                code="guest_access_unavailable",
                title="Guest Access Unavailable",
                detail="Guest access is not available.",
            )
        workspace = api_state.supabase_gateway.get_active_guest_workspace(
            user_id=auth_user_id,
            at=datetime.now(timezone.utc),
        )
        if workspace is None:
            raise problem(
                request,
                status_code=403,
                code="guest_session_expired",
                title="Guest Session Expired",
                detail="This temporary guest session is no longer available.",
            )
        user = api_state.supabase_gateway.get_or_create_profile_for_auth_user(auth_user)
        store_account_context(request, guest_account_context(workspace))
        return user

    auth_email = str(auth_user.get("email") or "")
    if not permanent_account_access_allowed(api_state.supabase_gateway, auth_email):
        raise private_alpha_access_problem(request)

    user = api_state.supabase_gateway.get_or_create_profile_for_auth_user(auth_user)
    store_account_context(request, registered_account_context(user.id))
    return user
