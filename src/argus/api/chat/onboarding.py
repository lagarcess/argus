from __future__ import annotations

from typing import Any

from loguru import logger

from argus.api import state as api_state
from argus.api.dependencies import dev_memory_fallback_enabled
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


def onboarding_prompt_text(*, is_spanish: bool) -> str:
    if is_spanish:
        return (
            "¿Cuál es tu objetivo principal ahora? No te preocupes, "
            "podrás cambiarlo después en Settings."
        )
    return (
        "What is your current primary goal? Don't worry, "
        "you can change it later in Settings."
    )


def onboarding_goal_followup_text(goal: str, *, is_spanish: bool) -> str:
    if is_spanish:
        mapping = {
            "learn_basics": (
                "Perfecto. Te ayudaré con ideas simples para empezar. "
                "¿Qué activo te interesa?"
            ),
            "test_stock_idea": (
                "Perfecto. Cuéntame tu idea de acción y la probamos."
            ),
            "build_passive_strategy": (
                "Perfecto. Podemos empezar con una idea pasiva tipo DCA."
            ),
            "explore_crypto": (
                "Perfecto. Empecemos con una idea de cripto que quieras validar."
            ),
            "surprise_me": (
                "Genial. Te propondré una idea inicial guiada para comenzar."
            ),
        }
    else:
        mapping = {
            "learn_basics": (
                "I'll keep this beginner-friendly. You can ask me to explain an investing term, "
                "walk through an asset in plain language, or set up a simple historical test. "
                "If you name an asset like Apple or Bitcoin, I'll help you choose a sensible next step."
            ),
            "test_stock_idea": (
                "Great. Share the stock idea you want to test and I'll run it."
            ),
            "build_passive_strategy": (
                "Great. We can start with a passive DCA-style idea."
            ),
            "explore_crypto": (
                "Great. Let's start with a crypto idea you want to validate."
            ),
            "surprise_me": "Great. I'll guide you with a starter idea to begin.",
        }
    return mapping.get(goal, mapping["surprise_me"])


def persist_onboarding_update(user: User, patch: dict[str, Any]) -> User:
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
