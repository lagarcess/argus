"""Read-side compatibility filter for retired onboarding control messages.

Private alpha once persisted hidden ``__ONBOARDING_SKIP__`` and
``__ONBOARDING_GOAL__:<goal>`` user messages. The onboarding product is
removed; these markers survive only as legacy rows in existing conversations.
This helper exists solely so read surfaces (history, previews, retry
projections) keep those rows invisible. It must never create, accept, route,
or persist an onboarding turn.
"""

from __future__ import annotations

_LEGACY_SKIP_MARKER = "__ONBOARDING_SKIP__"
_LEGACY_GOAL_PREFIX = "__ONBOARDING_GOAL__:"


def is_legacy_onboarding_marker(content: str) -> bool:
    return content == _LEGACY_SKIP_MARKER or content.startswith(_LEGACY_GOAL_PREFIX)


def legacy_onboarding_sql_filters() -> tuple[str, str]:
    """Return exact and escaped LIKE filters for persistent read surfaces."""
    escaped_goal_prefix = (
        _LEGACY_GOAL_PREFIX.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    return _LEGACY_SKIP_MARKER, f"{escaped_goal_prefix}%"
