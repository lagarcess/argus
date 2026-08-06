from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from argus.api import state as api_state
from argus.api.dependencies import (
    _apply_auth_session_cookies,
    _session_cookie_secure,
    auth_response,
    current_user,
    private_alpha_access_problem,
    problem,
)
from argus.api.guest_access import (
    account_context,
    client_identity,
    guest_access_enabled,
    guest_account_context,
    permanent_account_access_allowed,
    public_account_access_enabled,
    store_account_context,
)
from argus.api.guest_observability import (
    emit_guest_funnel_event,
    emit_verified_guest_funnel_event,
)
from argus.api.rate_limits import SlidingWindowLimiter
from argus.api.schemas import (
    AccessRequestAccepted,
    AccessRequestCreate,
    GuestBootstrapRequest,
    GuestHandoffClaimResponse,
    GuestHandoffCreateRequest,
    GuestHandoffCreateResponse,
    GuestIdentityLinkRequest,
    GuestPendingAction,
    LoginRequest,
    SignupRequest,
    User,
    guest_safe_user,
)
from argus.domain.supabase_guest_accounts import EmailAlreadyRegisteredError
from argus.domain.username_signup import serialized_username_signup

router = APIRouter(prefix="/api/v1", tags=["auth"])

AUTH_LOGIN_ATTEMPT_LIMIT = 8
AUTH_SIGNUP_ATTEMPT_LIMIT = 5
AUTH_ACCESS_REQUEST_ATTEMPT_LIMIT = 5
AUTH_GUEST_ATTEMPT_LIMIT = 5
AUTH_GUEST_HANDOFF_ATTEMPT_LIMIT = 5
_AUTH_ATTEMPT_WINDOW_SECONDS = 10 * 60
_AuthAction = Literal["login", "signup", "access_request", "handoff"]
_GUEST_HANDOFF_COOKIE = "argus-guest-handoff"
_GUEST_HANDOFF_ID_COOKIE = "argus-guest-handoff-id"
_GUEST_HANDOFF_MAX_AGE_SECONDS = 10 * 60

_AUTH_ATTEMPT_LIMITER = SlidingWindowLimiter()


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


def _username_taken_problem(request: Request) -> HTTPException:
    return problem(
        request,
        status_code=409,
        code="username_taken",
        title="Username Taken",
        detail="That username is already taken.",
    )


def _enforce_auth_attempt_limit(
    request: Request,
    *,
    action: _AuthAction,
    email: str,
) -> None:
    limits = {
        "login": AUTH_LOGIN_ATTEMPT_LIMIT,
        "signup": AUTH_SIGNUP_ATTEMPT_LIMIT,
        "access_request": AUTH_ACCESS_REQUEST_ATTEMPT_LIMIT,
        "handoff": AUTH_GUEST_HANDOFF_ATTEMPT_LIMIT,
    }
    limit = limits[action]
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
    return client_identity(request)


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


def _auth_user_payload(user: User, *, account_kind: str) -> dict[str, object]:
    response_user = guest_safe_user(user) if account_kind == "guest" else user
    return response_user.model_dump(mode="json")


@router.get("/auth/session")
def auth_session(
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> dict[str, object]:
    context = account_context(request)
    return {
        "authenticated": True,
        "user": _auth_user_payload(user, account_kind=context.kind),
    }


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

    expired_guest = False
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
                    "renewed_after_expiry": False,
                    "public_account_access_enabled": public_account_access_enabled(),
                    "user": _auth_user_payload(existing, account_kind=context.kind),
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
        guest_context = guest_account_context(workspace)
        store_account_context(request, guest_context)
        emit_guest_funnel_event(
            account=guest_context,
            kind="guest_session_started",
            user_id=profile.id,
            language=profile.language,
            surface="guest_entry",
            capability_category="account",
            terminal_outcome="started",
        )
        payload = dict(result)
        payload.update(
            {
                "authenticated": True,
                "reused": False,
                "renewed_after_expiry": expired_guest,
                "public_account_access_enabled": public_account_access_enabled(),
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
    _enforce_auth_attempt_limit(
        request,
        action="handoff",
        email=body.destination_email,
    )
    if not permanent_account_access_allowed(
        api_state.supabase_gateway,
        body.destination_email,
    ):
        raise _login_auth_problem(request)
    try:
        created = api_state.supabase_gateway.create_guest_workspace_handoff(
            source_user_id=user.id,
            destination_email=body.destination_email,
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
        path="/api/v1/auth",
    )
    response.set_cookie(
        _GUEST_HANDOFF_ID_COOKIE,
        payload.handoff_id,
        httponly=True,
        secure=_session_cookie_secure(request),
        samesite="lax",
        max_age=_GUEST_HANDOFF_MAX_AGE_SECONDS,
        path="/api/v1/auth",
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
        return _guest_handoff_failure_response(
            request,
            "guest_handoff_invalid",
        )
    try:
        claimed = api_state.supabase_gateway.claim_guest_workspace_handoff(
            handoff_id=handoff_id,
            opaque_secret=opaque_secret,
            destination_user_id=user.id,
            allow_same_destination_replay=False,
        )
    except Exception as exc:
        return _guest_handoff_failure_response(request, str(exc))

    source_user_id, payload = _guest_handoff_claim_payload(request, claimed)
    emit_verified_guest_funnel_event(
        "existing_account_sign_in_completed",
        user_id=source_user_id,
        conversation_id=payload.conversation_id,
        language=user.language,
        surface="account_conversion",
        capability_category="account",
        terminal_outcome="completed",
    )
    emit_verified_guest_funnel_event(
        "temporary_workspace_claimed",
        user_id=source_user_id,
        conversation_id=payload.conversation_id,
        language=user.language,
        surface="account_conversion",
        capability_category="history",
        terminal_outcome="claimed",
    )
    response = JSONResponse(
        content=jsonable_encoder(payload.model_dump(mode="json")),
    )
    _clear_guest_handoff_cookies(request, response)
    return response


def _guest_handoff_claim_payload(
    request: Request,
    claimed: dict[str, object],
) -> tuple[str, GuestHandoffClaimResponse]:
    source_user_id = str(claimed.get("source_user_id") or "")
    if not source_user_id:
        raise _guest_handoff_problem(request, "guest_handoff_invalid")
    pending_raw = claimed.get("pending_action")
    pending_action = (
        GuestPendingAction.model_validate(pending_raw)
        if isinstance(pending_raw, dict)
        else None
    )
    return source_user_id, GuestHandoffClaimResponse(
        conversation_id=str(claimed["conversation_id"]),
        pending_action=pending_action,
    )


def _clear_guest_handoff_cookies(request: Request, response: JSONResponse) -> None:
    for cookie_name in (_GUEST_HANDOFF_COOKIE, _GUEST_HANDOFF_ID_COOKIE):
        response.delete_cookie(
            cookie_name,
            path="/api/v1/auth",
            secure=_session_cookie_secure(request),
            httponly=True,
            samesite="lax",
        )


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
        "guest_handoff_claim_unavailable": (
            503,
            "Handoff Temporarily Unavailable",
            "The temporary workspace could not be claimed right now.",
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


_TERMINAL_GUEST_HANDOFF_CODES = frozenset(
    {
        "guest_handoff_invalid",
        "guest_handoff_expired",
        "guest_handoff_consumed",
        "guest_handoff_wrong_destination",
        "guest_handoff_source_not_anonymous",
        "guest_handoff_workspace_unavailable",
    }
)


def _guest_handoff_failure_response(
    request: Request,
    raw_code: str,
    *,
    auth_payload: dict[str, object] | None = None,
) -> JSONResponse:
    handoff_problem = _guest_handoff_problem(request, raw_code)
    detail = handoff_problem.detail
    body = detail if isinstance(detail, dict) else {}
    response = JSONResponse(
        content=jsonable_encoder(body),
        status_code=handoff_problem.status_code,
        headers=handoff_problem.headers,
    )
    if auth_payload is not None:
        _apply_auth_session_cookies(request, response, auth_payload)
    code = str(body.get("code") or "")
    if code in _TERMINAL_GUEST_HANDOFF_CODES:
        _clear_guest_handoff_cookies(request, response)
    return response


@router.post("/auth/guest/link")
def link_guest_identity(
    request: Request,
    body: GuestIdentityLinkRequest,
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
    guest_context = account_context(request)
    if guest_context.kind != "guest":
        same_linked_identity = (
            user.email is not None
            and user.email.strip().lower() == body.email
            and api_state.supabase_gateway.guest_identity_link_completed(user.id)
        )
        if same_linked_identity:
            return JSONResponse(
                jsonable_encoder(
                    {
                        "authenticated": True,
                        "account_kind": "registered",
                        "user": user.model_dump(mode="json"),
                        "reconciled": True,
                    }
                )
            )
        raise problem(
            request,
            status_code=409,
            code="account_already_registered",
            title="Account Already Registered",
            detail="This session already belongs to a permanent account.",
        )
    if not permanent_account_access_allowed(api_state.supabase_gateway, body.email):
        raise problem(
            request,
            status_code=400,
            code="guest_identity_link_failed",
            title="Account Creation Failed",
            detail=(
                "Argus could not finish this account request. Your conversation "
                "remains stored; retry to reconcile the account state."
            ),
        )
    access_token = _request_access_token(request)
    refresh_token = (body.refresh_token or "").strip() or request.cookies.get(
        "sb-refresh-token", ""
    ).strip()
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
        emit_guest_funnel_event(
            account=guest_context,
            kind="account_creation_completed",
            user_id=user.id,
            language=profile.language,
            surface="account_conversion",
            capability_category="account",
            terminal_outcome="completed",
        )
        return auth_response(request, payload)
    except HTTPException:
        raise
    except EmailAlreadyRegisteredError:
        raise problem(
            request,
            status_code=409,
            code="account_exists_use_login",
            title="Account Already Exists",
            detail=(
                "This email already has an Argus account. Sign in instead; "
                "your conversation comes with you."
            ),
        ) from None
    except Exception:
        raise problem(
            request,
            status_code=400,
            code="guest_identity_link_failed",
            title="Account Creation Failed",
            detail=(
                "Argus could not finish this account request. Your conversation "
                "remains stored; retry to reconcile the account state."
            ),
        ) from None


def _request_access_token(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    if authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    return request.cookies.get("sb-auth-token", "").strip()


@router.post(
    "/auth/signup",
    responses={
        403: {
            "description": "Private alpha access is required for this signup.",
            "content": {
                "application/json": {"schema": {"$ref": "#/components/schemas/Error"}}
            },
        }
    },
)
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
        raise private_alpha_access_problem(request)
    try:
        with serialized_username_signup(
            api_state.DATABASE_URL,
            body.email,
            body.username,
        ) as prevalidation:
            if (
                body.username is not None
                and not prevalidation.auth_user_exists
                and not prevalidation.username_available
            ):
                raise _username_taken_problem(request)
            result = api_state.supabase_gateway.signup(
                email=body.email,
                password=body.password,
                captcha_token=body.captcha_token,
                display_name=body.display_name,
                username=body.username,
                language=body.language,
            )
            auth_user = result.get("user")
            if not isinstance(auth_user, dict):
                raise RuntimeError("Provider signup did not return an Auth user.")
            identities = auth_user.get("identities")
            # Supabase uses an empty identity list for its obfuscated existing-user
            # response. Persisting that fake user would reveal the account exists.
            if identities != []:
                api_state.supabase_gateway.get_or_create_profile_for_auth_user(
                    auth_user
                )
            return auth_response(request, result)
    except HTTPException:
        raise
    except Exception:
        raise _signup_auth_problem(request) from None


@router.post(
    "/auth/access-requests",
    response_model=AccessRequestAccepted,
    status_code=202,
)
def request_access(
    request: Request,
    body: AccessRequestCreate,
) -> AccessRequestAccepted:
    _enforce_browser_auth_origin(request)
    _enforce_auth_attempt_limit(
        request,
        action="access_request",
        email=body.email,
    )
    if api_state.supabase_gateway is None:
        raise problem(
            request,
            status_code=503,
            code="access_request_unavailable",
            title="Access Request Unavailable",
            detail="Argus could not record this access request. Please try again.",
        )
    try:
        api_state.supabase_gateway.request_private_alpha_access(
            email=body.email,
            language=body.language,
        )
    except Exception:
        raise problem(
            request,
            status_code=503,
            code="access_request_unavailable",
            title="Access Request Unavailable",
            detail="Argus could not record this access request. Please try again.",
        ) from None
    return AccessRequestAccepted(accepted=True)


@router.post("/auth/login")
def login(request: Request, body: LoginRequest) -> JSONResponse:
    _enforce_browser_auth_origin(request)
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
            email=body.email,
            password=body.password,
            captcha_token=body.captcha_token,
        )
    except Exception:
        raise _login_auth_problem(request) from None
    handoff_id = request.cookies.get(_GUEST_HANDOFF_ID_COOKIE, "").strip()
    opaque_secret = request.cookies.get(_GUEST_HANDOFF_COOKIE, "").strip()
    if bool(handoff_id) is not bool(opaque_secret):
        return _guest_handoff_failure_response(
            request,
            "guest_handoff_invalid",
            auth_payload=result,
        )
    if not handoff_id:
        return auth_response(request, result)

    auth_user = result.get("user")
    destination_user_id = (
        str(auth_user.get("id") or "") if isinstance(auth_user, dict) else ""
    )
    if not destination_user_id:
        return _guest_handoff_failure_response(
            request,
            "guest_handoff_invalid",
            auth_payload=result,
        )
    try:
        claimed = api_state.supabase_gateway.claim_guest_workspace_handoff(
            handoff_id=handoff_id,
            opaque_secret=opaque_secret,
            destination_user_id=destination_user_id,
            allow_same_destination_replay=True,
        )
    except Exception as exc:
        return _guest_handoff_failure_response(
            request,
            str(exc),
            auth_payload=result,
        )

    source_user_id, claim_payload = _guest_handoff_claim_payload(request, claimed)
    result["guest_claim"] = claim_payload.model_dump(mode="json")
    if claimed.get("replayed") is not True:
        emit_verified_guest_funnel_event(
            "existing_account_sign_in_completed",
            user_id=source_user_id,
            conversation_id=claim_payload.conversation_id,
            surface="account_conversion",
            capability_category="account",
            terminal_outcome="completed",
        )
        emit_verified_guest_funnel_event(
            "temporary_workspace_claimed",
            user_id=source_user_id,
            conversation_id=claim_payload.conversation_id,
            surface="account_conversion",
            capability_category="history",
            terminal_outcome="claimed",
        )
    response = auth_response(request, result)
    _clear_guest_handoff_cookies(request, response)
    return response


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
