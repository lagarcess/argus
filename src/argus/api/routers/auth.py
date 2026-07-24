from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from argus.api import state as api_state
from argus.api.dependencies import (
    _session_cookie_secure,
    auth_response,
    current_user,
    problem,
)
from argus.api.guest_access import (
    account_context,
    guest_access_enabled,
    guest_account_context,
    permanent_account_access_allowed,
    public_account_access_enabled,
    store_account_context,
)
from argus.api.schemas import (
    GuestBootstrapRequest,
    GuestHandoffClaimResponse,
    GuestHandoffCreateRequest,
    GuestHandoffCreateResponse,
    GuestIdentityLinkRequest,
    GuestPendingAction,
    LoginRequest,
    SignupRequest,
    User,
)

router = APIRouter(prefix="/api/v1", tags=["auth"])

AUTH_LOGIN_ATTEMPT_LIMIT = 8
AUTH_SIGNUP_ATTEMPT_LIMIT = 5
AUTH_GUEST_ATTEMPT_LIMIT = 5
_AUTH_ATTEMPT_WINDOW_SECONDS = 10 * 60
_AUTH_ATTEMPT_RETRY_FLOOR_SECONDS = 1
_AUTH_ATTEMPT_COMPACT_THRESHOLD = 2048
_AuthAction = Literal["login", "signup"]
_GUEST_HANDOFF_COOKIE = "argus-guest-handoff"
_GUEST_HANDOFF_MAX_AGE_SECONDS = 10 * 60


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


@router.post(
    "/auth/guest/handoffs",
    response_model=GuestHandoffCreateResponse,
    status_code=201,
)
def create_guest_handoff(
    request: Request,
    body: GuestHandoffCreateRequest,
    user: User = Depends(current_user),  # noqa: B008
) -> JSONResponse:
    _enforce_browser_auth_origin(request)
    if api_state.supabase_gateway is None:
        raise problem(
            request,
            status_code=500,
            code="internal_error",
            title="Internal Error",
            detail="Supabase persistence is required for guest conversion.",
        )
    context = account_context(request)
    if context.kind != "guest":
        raise problem(
            request,
            status_code=409,
            code="account_already_registered",
            title="Account Already Registered",
            detail="This session already belongs to a permanent account.",
        )
    if not permanent_account_access_allowed(
        api_state.supabase_gateway,
        body.destination_email,
    ):
        raise _login_auth_problem(request)
    try:
        destination_user_id = api_state.supabase_gateway.resolve_permanent_auth_user_id(
            body.destination_email
        )
        if not destination_user_id:
            raise RuntimeError("Destination account was not found.")
        created = api_state.supabase_gateway.create_guest_workspace_handoff(
            source_user_id=user.id,
            destination_user_id=destination_user_id,
            source_conversation_id=body.source_conversation_id,
            pending_action=(
                body.pending_action.model_dump(mode="json", exclude_none=True)
                if body.pending_action is not None
                else None
            ),
            created_at=datetime.now(timezone.utc),
        )
        opaque_secret = str(created.pop("opaque_secret"))
        payload = GuestHandoffCreateResponse(
            handoff_id=str(created["id"]),
            expires_at=created["expires_at"],
        )
    except HTTPException:
        raise
    except Exception:
        raise _login_auth_problem(request) from None

    response = JSONResponse(
        status_code=201,
        content=jsonable_encoder(payload.model_dump(mode="json")),
    )
    response.set_cookie(
        _GUEST_HANDOFF_COOKIE,
        opaque_secret,
        httponly=True,
        secure=_session_cookie_secure(request),
        samesite="lax",
        max_age=_GUEST_HANDOFF_MAX_AGE_SECONDS,
        path="/api/v1/auth/guest/handoffs",
    )
    return response


@router.post(
    "/auth/guest/handoffs/{handoff_id}/claim",
    response_model=GuestHandoffClaimResponse,
)
def claim_guest_handoff(
    handoff_id: str,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> JSONResponse:
    _enforce_browser_auth_origin(request)
    if api_state.supabase_gateway is None:
        raise problem(
            request,
            status_code=500,
            code="internal_error",
            title="Internal Error",
            detail="Supabase persistence is required for guest conversion.",
        )
    context = account_context(request)
    if context.kind != "registered":
        raise problem(
            request,
            status_code=403,
            code="registered_account_required",
            title="Account Required",
            detail="Sign in to claim this temporary conversation.",
        )
    opaque_secret = request.cookies.get(_GUEST_HANDOFF_COOKIE, "").strip()
    if not opaque_secret:
        raise _guest_handoff_problem(request, "guest_handoff_invalid")
    try:
        claimed = api_state.supabase_gateway.claim_guest_workspace_handoff(
            handoff_id=handoff_id,
            opaque_secret=opaque_secret,
            destination_user_id=user.id,
        )
    except Exception as exc:
        raise _guest_handoff_problem(request, str(exc)) from None

    source_user_id = str(claimed.get("source_user_id") or "")
    if not source_user_id:
        raise _guest_handoff_problem(request, "guest_handoff_invalid")
    try:
        api_state.supabase_gateway.delete_anonymous_auth_user(source_user_id)
    except Exception:
        # The product graph is already safe and owned by the destination.
        # Cleanup is idempotent and may be retried independently.
        pass

    pending_raw = claimed.get("pending_action")
    pending_action = (
        GuestPendingAction.model_validate(pending_raw)
        if isinstance(pending_raw, dict)
        else None
    )
    payload = GuestHandoffClaimResponse(
        conversation_id=str(claimed["conversation_id"]),
        pending_action=pending_action,
    )
    response = JSONResponse(
        content=jsonable_encoder(payload.model_dump(mode="json")),
    )
    response.delete_cookie(
        _GUEST_HANDOFF_COOKIE,
        path="/api/v1/auth/guest/handoffs",
        secure=_session_cookie_secure(request),
        httponly=True,
        samesite="lax",
    )
    return response


def _guest_handoff_problem(request: Request, raw_code: str) -> HTTPException:
    known = {
        "guest_handoff_consumed": (
            409,
            "Handoff Already Used",
            "This guest handoff has already been used.",
        ),
        "guest_handoff_expired": (
            410,
            "Handoff Expired",
            "This guest handoff has expired.",
        ),
        "guest_handoff_wrong_destination": (
            403,
            "Handoff Denied",
            "This guest handoff does not belong to the signed-in account.",
        ),
        "guest_handoff_unsafe_product_graph": (
            409,
            "Handoff Unsafe",
            "This temporary workspace could not be transferred safely.",
        ),
        "guest_handoff_workspace_unavailable": (
            409,
            "Workspace Unavailable",
            "This temporary workspace is no longer available.",
        ),
    }
    code = next((value for value in known if value in raw_code), "guest_handoff_invalid")
    status, title, detail = known.get(
        code,
        (400, "Invalid Handoff", "This guest handoff is invalid."),
    )
    return problem(
        request,
        status_code=status,
        code=code,
        title=title,
        detail=detail,
    )


@router.post("/auth/guest/link")
def link_guest_identity(
    request: Request,
    body: GuestIdentityLinkRequest,
    user: User = Depends(current_user),  # noqa: B008
) -> JSONResponse:
    _enforce_browser_auth_origin(request)
    if not public_account_access_enabled():
        raise problem(
            request,
            status_code=403,
            code="public_account_access_unavailable",
            title="Account Creation Unavailable",
            detail="Public account creation is not available.",
        )
    if api_state.supabase_gateway is None:
        raise problem(
            request,
            status_code=500,
            code="internal_error",
            title="Internal Error",
            detail="Supabase persistence is required for guest conversion.",
        )
    if account_context(request).kind != "guest":
        raise problem(
            request,
            status_code=409,
            code="account_already_registered",
            title="Account Already Registered",
            detail="This session already belongs to a permanent account.",
        )
    access_token = _request_access_token(request)
    refresh_token = request.cookies.get("sb-refresh-token", "").strip()
    if not access_token or not refresh_token:
        raise problem(
            request,
            status_code=401,
            code="unauthorized",
            title="Unauthorized",
            detail="The guest session could not be verified for account creation.",
        )
    try:
        result = api_state.supabase_gateway.link_anonymous_identity(
            access_token=access_token,
            refresh_token=refresh_token,
            email=body.email,
            password=body.password,
        )
        auth_user = result.get("user")
        if (
            not isinstance(auth_user, dict)
            or str(auth_user.get("id") or "") != user.id
            or auth_user.get("is_anonymous") is not False
        ):
            raise RuntimeError("Provider linked a different identity.")
        api_state.supabase_gateway.mark_guest_identity_linked(
            user.id,
            at=datetime.now(timezone.utc),
        )
        profile = api_state.supabase_gateway.get_or_create_profile_for_auth_user(
            auth_user
        )
        payload = dict(result)
        payload.update(
            {
                "authenticated": True,
                "account_kind": "registered",
                "user": profile.model_dump(mode="json"),
            }
        )
        return auth_response(request, payload)
    except HTTPException:
        raise
    except Exception:
        raise problem(
            request,
            status_code=400,
            code="guest_identity_link_failed",
            title="Account Creation Failed",
            detail="Argus could not create this account. Your temporary chat is unchanged.",
        ) from None


def _request_access_token(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    if authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    return request.cookies.get("sb-auth-token", "").strip()


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
