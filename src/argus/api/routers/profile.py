from __future__ import annotations

from fastapi import APIRouter, Depends
from loguru import logger

from argus.api import state as api_state
from argus.api.dependencies import current_user, dev_memory_fallback_enabled
from argus.api.schemas import ProfilePatch, User, UserResponse
from argus.domain.store import utcnow

router = APIRouter(prefix="/api/v1", tags=["profile"])


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


@router.patch("/me", response_model=UserResponse)
def patch_me(
    patch: ProfilePatch,
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
    updated = User.model_validate(data)

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
