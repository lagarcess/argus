from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from argus.api import state as api_state
from argus.api.dependencies import auth_response, current_user, problem
from argus.api.schemas import LoginRequest, SignupRequest, User

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.get("/auth/session")
def auth_session(user: User = Depends(current_user)) -> dict[str, object]:  # noqa: B008
    return {"authenticated": True, "user": user.model_dump(mode="json")}


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
    try:
        result = api_state.supabase_gateway.signup(
            email=body.email,
            password=body.password,
            display_name=body.display_name,
            username=body.username,
        )
        return auth_response(request, result)
    except Exception as exc:
        raise problem(
            request,
            status_code=400,
            code="auth_signup_failed",
            title="Signup Failed",
            detail=str(exc),
        ) from None


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
    try:
        result = api_state.supabase_gateway.login(email=body.email, password=body.password)
        return auth_response(request, result)
    except Exception:
        raise problem(
            request,
            status_code=401,
            code="unauthorized",
            title="Unauthorized",
            detail="Invalid email or password.",
        ) from None


@router.post("/auth/logout")
def logout() -> JSONResponse:
    response = JSONResponse({"success": True})
    response.delete_cookie("sb-auth-token", path="/")
    response.delete_cookie("sb-refresh-token", path="/")
    return response
