from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from loguru import logger
from pydantic import ValidationError

from argus.api import state as api_state
from argus.api.dependencies import current_user, dev_memory_fallback_enabled, problem
from argus.api.schemas import (
    ProfilePatch,
    UsageAllowance,
    UsageAllowanceResponse,
    UsageAllowances,
    UsageWindow,
    User,
    UserResponse,
)
from argus.domain.store import utcnow
from argus.domain.usage_counter_reader import align_usage_period
from argus.domain.usage_limits import (
    MESSAGE_ALLOWANCE_LIMITS,
    MESSAGE_USAGE_RESOURCE,
    SIMULATION_ALLOWANCE_LIMITS,
    SIMULATION_USAGE_RESOURCE,
    read_memory_usage,
)

router = APIRouter(prefix="/api/v1", tags=["profile"])

_ALLOWANCE_POLICIES: dict[str, tuple[str, dict[str, int]]] = {
    "messages": (MESSAGE_USAGE_RESOURCE, dict(MESSAGE_ALLOWANCE_LIMITS)),
    "backtests": (SIMULATION_USAGE_RESOURCE, dict(SIMULATION_ALLOWANCE_LIMITS)),
}


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(current_user)) -> UserResponse:  # noqa: B008
    if api_state.supabase_gateway is not None:
        try:
            profile = api_state.supabase_gateway.get_user(user_id=user.id)
            if profile:
                return UserResponse(user=profile)
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase profile read failed; using dev memory fallback",
                error=str(exc),
                user_id=user.id,
            )
    return UserResponse(user=user)


@router.get("/me/usage", response_model=UsageAllowanceResponse)
def get_me_usage(
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> UsageAllowanceResponse:
    now = datetime.now(timezone.utc)
    resources = tuple(resource for resource, _ in _ALLOWANCE_POLICIES.values())
    rows_by_period: dict[str, dict[str, dict]] = {"hour": {}, "day": {}}
    if api_state.supabase_gateway is not None:
        try:
            for period in ("hour", "day"):
                rows = api_state.supabase_gateway.list_current_usage_counters(
                    user_id=user.id,
                    resources=resources,
                    period=period,
                    at=now,
                )
                rows_by_period[period] = {str(row.get("resource")): row for row in rows}
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                logger.error(
                    "Supabase usage read failed",
                    error=str(exc),
                    user_id=user.id,
                )
                raise problem(
                    request,
                    status_code=500,
                    code="usage_read_failed",
                    title="Usage Read Failed",
                    detail="Current allowance information is unavailable.",
                ) from exc
            logger.warning(
                "Supabase usage read failed; using dev zero-state fallback",
                error=str(exc),
                user_id=user.id,
            )
    else:
        for resource in resources:
            for period in ("hour", "day"):
                row = read_memory_usage(
                    api_state.store.usage_counters,
                    user_id=user.id,
                    resource=resource,
                    period=period,
                    at=now,
                )
                if row is not None:
                    rows_by_period[period][resource] = {
                        "resource": resource,
                        "used_count": row.get("used_count", 0),
                        "limit_count": row.get("limit_count"),
                        "period_end": row.get("period_end"),
                    }

    def window(resource: str, period: str, policy_limit: int) -> UsageWindow:
        row = rows_by_period[period].get(resource, {})
        _, default_period_end = align_usage_period(now, period)
        limit = max(int(row.get("limit_count") or policy_limit), 0)
        used = max(int(row.get("used_count", 0)), 0)
        return UsageWindow(
            limit=limit,
            used=used,
            remaining=max(limit - used, 0),
            period_end=row.get("period_end") or default_period_end,
        )

    def allowance(policy_key: str) -> UsageAllowance:
        resource, limits = _ALLOWANCE_POLICIES[policy_key]
        hour = window(resource, "hour", limits["hour"])
        day = window(resource, "day", limits["day"])
        return UsageAllowance(
            hour=hour,
            day=day,
            available_now=hour.remaining > 0 and day.remaining > 0,
            limiting_window="hour" if hour.remaining < day.remaining else "day",
        )

    return UsageAllowanceResponse(
        allowances=UsageAllowances(
            messages=allowance("messages"),
            backtests=allowance("backtests"),
        )
    )


@router.patch("/me", response_model=UserResponse)
def patch_me(
    patch: ProfilePatch,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> UserResponse:
    current = (
        api_state.supabase_gateway.get_user(user_id=user.id)
        if api_state.supabase_gateway is not None
        else api_state.store.users.get(user.id, user)
    )
    if current is None:
        current = user

    data = current.model_dump()
    updates = patch.model_dump(exclude_unset=True)
    updated_fields = sorted(updates)
    onboarding_patch = updates.pop("onboarding", None)
    data.update(updates)
    if onboarding_patch:
        onboarding = current.onboarding.model_dump()
        onboarding.update(onboarding_patch)
        data["onboarding"] = onboarding
    data["updated_at"] = utcnow()
    try:
        updated = User.model_validate(data)
    except ValidationError as exc:
        raise problem(
            request,
            status_code=422,
            code="invalid_profile_patch",
            title="Invalid Profile Patch",
            detail="The profile update could not be applied.",
            context={"errors": exc.errors()},
        ) from exc

    if api_state.supabase_gateway is not None:
        try:
            updated = api_state.supabase_gateway.update_user(
                user.id, updated.model_dump(mode="json")
            )
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase profile patch failed; using dev memory fallback",
                error=str(exc),
                user_id=user.id,
            )
    api_state.store.users[user.id] = updated
    logger.info(
        "Profile updated",
        user_id=user.id,
        fields=updated_fields,
        onboarding_fields=sorted(onboarding_patch or {}),
    )
    return UserResponse(user=updated)
