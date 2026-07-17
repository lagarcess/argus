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
    User,
    UserResponse,
)
from argus.domain.store import utcnow
from argus.domain.usage_counter_reader import align_usage_period

router = APIRouter(prefix="/api/v1", tags=["profile"])

_DAILY_ALLOWANCE_POLICIES = {
    "messages": ("chat_messages", 200),
    "backtests": ("backtest_runs", 50),
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
    user: User = Depends(current_user),  # noqa: B008
) -> UsageAllowanceResponse:
    now = datetime.now(timezone.utc)
    _, default_period_end = align_usage_period(now, "day")
    rows: list[dict] = []
    if api_state.supabase_gateway is not None:
        try:
            rows = api_state.supabase_gateway.list_current_usage_counters(
                user_id=user.id,
                resources=tuple(
                    resource for resource, _ in _DAILY_ALLOWANCE_POLICIES.values()
                ),
                period="day",
                at=now,
            )
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase usage read failed; using dev zero-state fallback",
                error=str(exc),
                user_id=user.id,
            )

    rows_by_resource = {str(row.get("resource")): row for row in rows}

    def allowance(policy_key: str) -> UsageAllowance:
        resource, default_limit = _DAILY_ALLOWANCE_POLICIES[policy_key]
        row = rows_by_resource.get(resource, {})
        limit = max(int(row.get("limit_count", default_limit)), 0)
        used = max(int(row.get("used_count", 0)), 0)
        return UsageAllowance(
            limit=limit,
            used=used,
            remaining=max(limit - used, 0),
            period_end=row.get("period_end") or default_period_end,
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
