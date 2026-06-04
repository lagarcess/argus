from __future__ import annotations

SUPPORTED_DCA_CADENCE_VALUES: tuple[str, ...] = (
    "daily",
    "weekly",
    "biweekly",
    "monthly",
    "quarterly",
)
SUPPORTED_DCA_CADENCES: frozenset[str] = frozenset(SUPPORTED_DCA_CADENCE_VALUES)
