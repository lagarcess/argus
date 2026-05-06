"""Retired deterministic turn-signal parsing.

The LLM interpreter owns routing, extraction, and turn-level response preferences.
This module remains only so older imports fail less abruptly during migration.
"""

from __future__ import annotations

from argus.agent_runtime.state.models import ResponseProfileOverrides


def resolve_response_profile_overrides(_: str) -> ResponseProfileOverrides:
    return ResponseProfileOverrides()
