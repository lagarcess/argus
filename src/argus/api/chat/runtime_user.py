"""The runtime's view of the asking user, read from their profile."""

from __future__ import annotations

from argus.agent_runtime.state.models import UserState
from argus.api.schemas import User


def runtime_user_for(
    *, user_id: str, profile: User, turn_language: str | None
) -> UserState:
    """Settings reach a turn from the profile; the turn may only name its language."""
    return UserState(
        user_id=user_id,
        display_name=profile.display_name,
        language_preference=turn_language or profile.language or "en",
    )
