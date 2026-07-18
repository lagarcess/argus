"""Memory proposal policy: enablement, allowlist, sensitivity, cooldown.

Policy operates on typed candidate fields only; content flagging quality is
owned by extraction and its evaluations, never by text heuristics here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel

from argus.memory.contracts import MemoryCandidate, MemoryCategory

DEFAULT_PROPOSAL_COOLDOWN = timedelta(days=7)

ALL_CATEGORIES: frozenset[MemoryCategory] = frozenset(MemoryCategory)


class UserMemorySettings(BaseModel):
    """Per-user memory switches. Memory is off until the user opts in."""

    enabled: bool = False


class PolicyOutcome(str, Enum):
    ALLOWED = "allowed"
    DENIED_DISABLED = "denied_disabled"
    DENIED_CATEGORY = "denied_category"
    SUPPRESSED_SENSITIVE = "suppressed_sensitive"
    SUPPRESSED_COOLDOWN = "suppressed_cooldown"


class PolicyDecision(BaseModel):
    allowed: bool
    outcome: PolicyOutcome
    reasons: list[str]


@dataclass(frozen=True)
class MemoryPolicy:
    """Evaluates whether a candidate may be offered for confirmation."""

    allowed_categories: frozenset[MemoryCategory] = field(default=ALL_CATEGORIES)
    proposal_cooldown: timedelta = DEFAULT_PROPOSAL_COOLDOWN

    def evaluate(
        self,
        candidate: MemoryCandidate,
        settings: UserMemorySettings,
        *,
        last_prompted_at: datetime | None,
        now: datetime,
    ) -> PolicyDecision:
        if not settings.enabled:
            return PolicyDecision(
                allowed=False,
                outcome=PolicyOutcome.DENIED_DISABLED,
                reasons=["memory is disabled for this user"],
            )
        if candidate.category not in self.allowed_categories:
            return PolicyDecision(
                allowed=False,
                outcome=PolicyOutcome.DENIED_CATEGORY,
                reasons=[
                    f"category {candidate.category.value} is outside the"
                    " active allowlist"
                ],
            )
        if candidate.sensitivity_flags:
            flags = ", ".join(flag.value for flag in candidate.sensitivity_flags)
            return PolicyDecision(
                allowed=False,
                outcome=PolicyOutcome.SUPPRESSED_SENSITIVE,
                reasons=[f"sensitive content is never stored: {flags}"],
            )
        if (
            last_prompted_at is not None
            and now - last_prompted_at < self.proposal_cooldown
        ):
            return PolicyDecision(
                allowed=False,
                outcome=PolicyOutcome.SUPPRESSED_COOLDOWN,
                reasons=["a recent memory prompt is inside the cooldown"],
            )
        return PolicyDecision(
            allowed=True,
            outcome=PolicyOutcome.ALLOWED,
            reasons=["candidate passed enablement, category, and sensitivity"],
        )
