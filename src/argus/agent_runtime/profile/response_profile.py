from __future__ import annotations

from argus.agent_runtime.state.models import (
    ResponseProfile,
    ResponseProfileOverrides,
    UserState,
)


def resolve_effective_response_profile(
    *,
    user: UserState,
    explicit_overrides: ResponseProfileOverrides | None = None,
) -> ResponseProfile:
    overrides = explicit_overrides or ResponseProfileOverrides()
    return ResponseProfile(
        effective_tone=overrides.tone or user.preferred_tone,
        effective_verbosity=overrides.verbosity or user.response_verbosity,
        effective_expertise_mode=overrides.expertise_mode or user.expertise_level,
    )
