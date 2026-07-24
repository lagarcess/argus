from __future__ import annotations

import os
from typing import Any

from loguru import logger

from argus.api import state as api_state
from argus.api.dependencies import dev_memory_fallback_enabled
from argus.api.guest_access import AccountContext
from argus.api.schemas import User
from argus.domain.store import utcnow

SUPPORTED_ONBOARDING_GOALS = {
    "learn_basics",
    "test_stock_idea",
    "build_passive_strategy",
    "explore_crypto",
    "surprise_me",
}


def parse_onboarding_control_message(message: str) -> str | None:
    if message == "__ONBOARDING_SKIP__":
        return "surprise_me"
    prefix = "__ONBOARDING_GOAL__:"
    if not message.startswith(prefix):
        return None
    goal = message.removeprefix(prefix)
    if goal in SUPPORTED_ONBOARDING_GOALS:
        return goal
    return None


def account_uses_registered_onboarding(
    account: AccountContext,
    *,
    configured_enabled: bool,
) -> bool:
    return account.kind == "registered" and configured_enabled


def onboarding_goal_for_account(
    account: AccountContext,
    message: str,
) -> str | None:
    if account.kind != "registered":
        return None
    return parse_onboarding_control_message(message)


def registered_onboarding_required(
    account: AccountContext,
    stage: str,
) -> bool:
    configured_enabled = (
        os.getenv("ARGUS_PRIVATE_ALPHA_ONBOARDING_ENABLED", "true").strip().lower()
        != "false"
    )
    return account_uses_registered_onboarding(
        account,
        configured_enabled=configured_enabled,
    ) and stage in {"language_selection", "primary_goal_selection"}


def primary_goal_for_account(account: AccountContext, user: User) -> str | None:
    return user.onboarding.primary_goal if account.kind == "registered" else None


def persist_registered_onboarding_update(
    account: AccountContext,
    user: User,
    patch: dict[str, Any],
) -> User:
    if account.kind != "registered":
        return user

    current = (
        api_state.supabase_gateway.get_user(user_id=user.id)
        if api_state.supabase_gateway is not None
        else api_state.store.users.get(user.id, user)
    )
    if current is None:
        current = user

    onboarding = current.onboarding.model_copy(update=patch)
    updated = current.model_copy(
        update={
            "onboarding": onboarding,
            "updated_at": utcnow(),
        }
    )
    if api_state.supabase_gateway is not None:
        try:
            updated = api_state.supabase_gateway.update_user(
                user.id, updated.model_dump(mode="json")
            )
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase profile update failed; using dev memory fallback",
                error=str(exc),
                user_id=user.id,
            )
    api_state.store.users[user.id] = updated
    return updated
