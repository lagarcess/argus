from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from argus.api import state as api_state
from argus.api.dependencies import (
    auth_response,
    current_user,
    problem,
)
from argus.api.guest_access import (
    account_context,
    guest_access_enabled,
    guest_account_context,
    permanent_account_access_allowed,
    store_account_context,
)
from argus.api.schemas import GuestBootstrapRequest, LoginRequest, SignupRequest, User

router = APIRouter(prefix="/api/v1", tags=["auth"])

AUTH_LOGIN_ATTEMPT_LIMIT = 8
AUTH_SIGNUP_ATTEMPT_LIMIT = 5
AUTH_GUEST_ATTEMPT_LIMIT = 5
_AUTH_ATTEMPT_WINDOW_SECONDS = 10 * 60
_AUTH_ATTEMPT_RETRY_FLOOR_SECONDS = 1
_AUTH_ATTEMPT_COMPACT_THRESHOLD = 2048
_AuthAction = Literal["login", "signup"]


class _AuthAttemptLimiter:
    def __init__(self) -> None:
        self._attempts: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def record_or_retry_after(
        self,
        *,
        keys: tuple[str, ...],
        limit: int,
        window_seconds: int,
    ) -> int | None:
        now = monotonic()
        with self._lock:
            if len(self._attempts) >= _AUTH_ATTEMPT_COMPACT_THRESHOLD:
                self._compact(now=now, window_seconds=window_seconds)
            retry_after = 0
            for key in keys:
                attempts = self._attempts[key]
                self._prune(attempts, now=now, window_seconds=window_seconds)
                if len(attempts) >= limit:
                    retry_after = max(
                        retry_after,
                        int(window_seconds - (now - attempts[0])),
                    )
            if retry_after > 0:
                return max(retry_after, _AUTH_ATTEMPT_RETRY_FLOOR_SECONDS)
            for key in keys:
                self._attempts[key].append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._attempts.clear()

    @staticmethod
    def _prune(
        attempts: deque[float],
        *,
        now: float,
        window_seconds: int,
    ) -> None:
        while attempts and now - attempts[0] >= window_seconds:
            attempts.popleft()

    def _compact(self, *, now: float, window_seconds: int) -> None:
        stale_keys: list[str] = []
        for key, attempts in self._attempts.items():
            self._prune(attempts, now=now, window_seconds=window_seconds)
            if not attempts:
                stale_keys.append(key)
        for key in stale_keys:
            self._attempts.pop(key, None)


_AUTH_ATTEMPT_LIMITER = _AuthAttemptLimiter()


def reset_auth_attempt_limiter_for_tests() -> None:
    _AUTH_ATTEMPT_LIMITER.reset()


def _login_auth_problem(request: Request) -> HTTPException:
    return problem(
        request,
        status_code=401,
        code="unauthorized",
        title="Unauthorized",
        detail="Invalid email or password.",
    )


def _signup_auth_problem(request: Request) -> HTTPException:
    return problem(
        request,
        status_code=400,
        code="auth_signup_failed",
        title="Signup Failed",
        detail="Signup failed. Please try again.",
    )


def _enforce_auth_attempt_limit(
    request: Request,
    *,
    action: _AuthAction,
    email: str,
) -> None:
    limit = AUTH_LOGIN_ATTEMPT_LIMIT if action == "login" else AUTH_SIGNUP_ATTEMPT_LIMIT
    retry_after = _AUTH_ATTEMPT_LIMITER.record_or_retry_after(
        keys=(
            f"{action}:ip:{_client_identity(request)}",
            f"{action}:email:{email.strip().casefold()}",
        ),
        limit=limit,
        window_seconds=_AUTH_ATTEMPT_WINDOW_SECONDS,
    )
    if retry_after is None:
        return
    raise problem(
        request,
        status_code=429,
        code="too_many_requests",
        title="Too Many Requests",
        detail=("Too many authentication attempts. Please wait before trying again."),
        headers={"Retry-After": str(retry_after)},
    )


def _client_identity(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        first_hop = forwarded_for.split(",", 1)[0].strip()
        if first_hop:
            return first_hop
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _enforce_guest_attempt_limit(request: Request) -> None:
    retry_after = _AUTH_ATTEMPT_LIMITER.record_or_retry_after(
        keys=(f"guest:ip:{_client_identity(request)}",),
        limit=AUTH_GUEST_ATTEMPT_LIMIT,
        window_seconds=_AUTH_ATTEMPT_WINDOW_SECONDS,
    )
    if retry_after is None:
        return
    raise problem(
        request,
        status_code=429,
        code="too_many_requests",
        title="Too Many Requests",
        detail="Too many guest session attempts. Please wait before trying again.",
        headers={"Retry-After": str(retry_after)},
    )


@router.get("/auth/session")
def auth_session(user: User = Depends(current_user)) -> dict[str, object]:  # noqa: B008
    return {"authenticated": True, "user": user.model_dump(mode="json")}


@router.post("/auth/guest")
def guest_bootstrap(
    request: Request,
    body: GuestBootstrapRequest,
) -> JSONResponse:
    _enforce_browser_auth_origin(request)
    if not guest_access_enabled():
        raise problem(
            request,
            status_code=403,
            code="guest_access_unavailable",
            title="Guest Access Unavailable",
            detail="Guest access is not available.",
        )
    if api_state.supabase_gateway is None:
        raise problem(
            request,
            status_code=500,
            code="internal_error",
            title="Internal Error",
            detail="Supabase persistence is required for guest authentication.",
        )

    try:
        existing = current_user(request)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        expired_guest = (
            exc.status_code == 403 and detail.get("code") == "guest_session_expired"
        )
        if exc.status_code != 401 and not expired_guest:
            raise
    else:
        context = account_context(request)
        if context.kind != "guest":
            raise problem(
                request,
                status_code=409,
                code="account_already_registered",
                title="Account Already Registered",
                detail="This browser already has a permanent account session.",
            )
        return JSONResponse(
            jsonable_encoder(
                {
                    "authenticated": True,
                    "reused": True,
                    "user": existing.model_dump(mode="json"),
                    "account_kind": "guest",
                }
            )
        )

    _enforce_guest_attempt_limit(request)
    auth_user_id: str | None = None
    try:
        result = api_state.supabase_gateway.sign_in_anonymously(
            captcha_token=body.captcha_token,
            language=body.language,
        )
        auth_user = result.get("user")
        if not isinstance(auth_user, dict) or auth_user.get("is_anonymous") is not True:
            raise RuntimeError("Provider did not return a verified anonymous user.")
        auth_user_id = str(auth_user.get("id") or "")
        if not auth_user_id:
            raise RuntimeError("Provider anonymous user is missing an id.")
        profile = api_state.supabase_gateway.get_or_create_profile_for_auth_user(
            auth_user
        )
        workspace = api_state.supabase_gateway.create_guest_workspace(
            user_id=profile.id,
            created_at=profile.created_at,
        )
        store_account_context(request, guest_account_context(workspace))
        payload = dict(result)
        payload.update(
            {
                "authenticated": True,
                "reused": False,
                "account_kind": "guest",
            }
        )
        return auth_response(request, payload)
    except HTTPException:
        raise
    except Exception:
        if auth_user_id:
            try:
                api_state.supabase_gateway.delete_auth_user(auth_user_id)
            except Exception:
                pass
        raise problem(
            request,
            status_code=503,
            code="guest_bootstrap_failed",
            title="Guest Session Unavailable",
            detail="Argus could not start a guest session. Please try again.",
        ) from None


@router.post("/auth/signup")
def signup(request: Request, body: SignupRequest) -> JSONResponse:
    if api_state.supabase_gateway is None:
        raise problem(
            request,
            status_code=500,
            code="internal_error",
            title="Internal Error",
            detail="Supabase persistence is required for authentication.",
        )
    _enforce_auth_attempt_limit(request, action="signup", email=body.email)
    if not permanent_account_access_allowed(api_state.supabase_gateway, body.email):
        raise _signup_auth_problem(request)
    try:
        result = api_state.supabase_gateway.signup(
            email=body.email,
            password=body.password,
            display_name=body.display_name,
            username=body.username,
            language=body.language,
        )
        return auth_response(request, result)
    except Exception:
        raise _signup_auth_problem(request) from None


@router.post("/auth/login")
def login(request: Request, body: LoginRequest) -> JSONResponse:
    if api_state.supabase_gateway is None:
        raise problem(
            request,
            status_code=500,
            code="internal_error",
            title="Internal Error",
            detail="Supabase persistence is required for authentication.",
        )
    _enforce_auth_attempt_limit(request, action="login", email=body.email)
    if not permanent_account_access_allowed(api_state.supabase_gateway, body.email):
        raise _login_auth_problem(request)
    try:
        result = api_state.supabase_gateway.login(
            email=body.email, password=body.password
        )
        return auth_response(request, result)
    except Exception:
        raise _login_auth_problem(request) from None


def _enforce_browser_auth_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin:
        return
    from argus.api.app_setup import cors_allow_origins

    if origin in cors_allow_origins():
        return
    raise problem(
        request,
        status_code=403,
        code="csrf_origin_rejected",
        title="Request Rejected",
        detail="This authentication request did not come from an allowed origin.",
    )


@router.post("/auth/logout")
def logout(request: Request) -> JSONResponse:
    _enforce_browser_auth_origin(request)
    response = JSONResponse({"success": True})
    response.delete_cookie("sb-auth-token", path="/")
    response.delete_cookie("sb-refresh-token", path="/")
    return response
