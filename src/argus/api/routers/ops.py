from __future__ import annotations

import asyncio
import hmac
import json
import os
import time
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import ValidationError

from argus.api import state as api_state
from argus.api.guest_access import permanent_account_access_allowed
from argus.api.schemas import AccessApprovalRequest, AccessApprovalResponse, Language
from argus.domain.access_approval_email import send_access_approval_email
from argus.domain.market_data import warm_asset_universe

router = APIRouter(tags=["ops"])


def _ops_token() -> str:
    return (os.getenv("ARGUS_OPS_TOKEN") or "").strip()


def _require_ops_token(authorization: str | None) -> None:
    expected = _ops_token()
    if not expected:
        raise HTTPException(status_code=404, detail="Not found")
    expected_header = f"Bearer {expected}"
    if authorization is None or not hmac.compare_digest(authorization, expected_header):
        raise HTTPException(status_code=404, detail="Not found")


def _require_ops_authorization(
    authorization: str | None = Header(default=None),
) -> None:
    _require_ops_token(authorization)


def _check(name: str, status: str, duration_ms: int, **extra: Any) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "duration_ms": duration_ms,
        **extra,
    }


def _readiness_timeout_seconds() -> float:
    raw = (os.getenv("ARGUS_READINESS_ASSET_TIMEOUT_SECONDS") or "25").strip()
    try:
        value = float(raw)
    except ValueError:
        return 25.0
    return max(value, 1.0)


async def run_readiness_checks(request: Request, *, force: bool) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    started = time.perf_counter()
    try:
        api_state.get_agent_runtime_workflow(request)
        checks.append(
            _check(
                "agent_runtime_workflow",
                "ready",
                int((time.perf_counter() - started) * 1000),
            )
        )
    except Exception:
        checks.append(
            _check(
                "agent_runtime_workflow",
                "degraded",
                int((time.perf_counter() - started) * 1000),
            )
        )

    started = time.perf_counter()
    if api_state.supabase_gateway is None:
        checks.append(_check("supabase", "degraded", 0, reason="gateway_unavailable"))
    else:
        try:
            result = await asyncio.to_thread(api_state.supabase_gateway.health_check)
            checks.append(_check("supabase", result["status"], result["duration_ms"]))
        except Exception:
            checks.append(
                _check(
                    "supabase",
                    "degraded",
                    int((time.perf_counter() - started) * 1000),
                )
            )

    started = time.perf_counter()
    try:
        asset_result = await asyncio.wait_for(
            asyncio.to_thread(warm_asset_universe, force=force),
            timeout=_readiness_timeout_seconds(),
        )
        checks.append(
            _check(
                "asset_universe",
                asset_result.status,
                asset_result.duration_ms,
                provider_mode=asset_result.provider_mode,
                alias_count=asset_result.alias_count,
                required_symbols=list(asset_result.required_symbols),
                resolved_symbols=list(asset_result.resolved_symbols),
                missing_symbols=list(asset_result.missing_symbols),
            )
        )
    except Exception:
        checks.append(
            _check(
                "asset_universe",
                "degraded",
                int((time.perf_counter() - started) * 1000),
            )
        )

    status = (
        "ready" if all(check["status"] == "ready" for check in checks) else "degraded"
    )
    return {"status": status, "checks": checks}


@router.get("/internal/readiness")
async def readiness(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    force: bool = False,
) -> dict[str, Any]:
    _require_ops_token(authorization)
    payload = await run_readiness_checks(request, force=force)
    if payload.get("status") != "ready":
        response.status_code = 503
    return payload


@router.post(
    "/internal/canary/requested-signup-denial",
    dependencies=[Depends(_require_ops_authorization)],
)
async def requested_signup_denial(request: Request) -> dict[str, bool]:
    try:
        body = AccessApprovalRequest.model_validate(await request.json())
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError):
        raise HTTPException(status_code=422, detail="Invalid request body.") from None
    if api_state.supabase_gateway is None:
        raise HTTPException(status_code=503, detail="Canary probe is unavailable.")
    return {
        "denied": not permanent_account_access_allowed(
            api_state.supabase_gateway,
            body.email,
        )
    }


def _approval_signup_url() -> str:
    origin = (os.getenv("ARGUS_APP_ORIGIN") or "").strip().rstrip("/")
    if not origin:
        raise RuntimeError("Approval signup origin is unavailable.")
    return f"{origin}/?auth=signup"


@router.post(
    "/internal/access-requests/approve",
    response_model=AccessApprovalResponse,
    dependencies=[Depends(_require_ops_authorization)],
)
async def approve_access_request(request: Request) -> AccessApprovalResponse:
    try:
        body = AccessApprovalRequest.model_validate(await request.json())
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError):
        raise HTTPException(status_code=422, detail="Invalid request body.") from None
    if api_state.supabase_gateway is None:
        raise HTTPException(status_code=503, detail="Approval is unavailable.")
    try:
        requested = api_state.supabase_gateway.get_requested_private_alpha_access(
            body.email
        )
    except Exception:
        raise HTTPException(status_code=503, detail="Approval is unavailable.") from None
    if requested is None:
        raise HTTPException(
            status_code=409,
            detail="Access request is not eligible for approval.",
        )

    language: Language = (
        "es-419" if requested.get("language") == "es-419" else "en"
    )
    try:
        signup_url = _approval_signup_url()
        send_access_approval_email(
            recipient=body.email,
            language=language,
            signup_url=signup_url,
        )
    except Exception:
        raise HTTPException(status_code=503, detail="Approval is unavailable.") from None

    try:
        approved = api_state.supabase_gateway.approve_requested_private_alpha_access(
            email=body.email
        )
    except Exception:
        raise HTTPException(status_code=503, detail="Approval is unavailable.") from None
    if not approved:
        raise HTTPException(
            status_code=409,
            detail="Access request is not eligible for approval.",
        )
    return AccessApprovalResponse()
