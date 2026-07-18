"""Memory proposal policy: consent scope, allowlist, sensitivity, cooldown.

Policy operates on typed candidate fields only; content flagging quality is
owned by extraction and its evaluations, never by text heuristics here.

Consent model: memory is off until the user opts in, and an opt-in covers an
explicit category scope. While memory is off, only approved earned opt-in
proposal reasons may still offer a proposal (decision memo §15.3); everything
else is denied. Sensitivity and cooldown suppression apply to opt-in offers
too.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel, Field

from argus.memory.contracts import (
    MemoryCandidate,
    MemoryCategory,
    ProposalReason,
)

DEFAULT_PROPOSAL_COOLDOWN = timedelta(days=7)

ALL_CATEGORIES: frozenset[MemoryCategory] = frozenset(MemoryCategory)

# Earned opt-in moments approved by decision memo §15.3: the saved-decision
# invite and the user's own explicit "remember this" request.
DEFAULT_OPT_IN_PROPOSAL_REASONS: frozenset[ProposalReason] = frozenset(
    {ProposalReason.SAVED_DECISION, ProposalReason.EXPLICIT_REQUEST}
)

# The scope a saved-decision opt-in offer grants when confirmed (memo §15.3:
# the first opt-in is decision-grounded, not broad personalization).
OPT_IN_SCOPE_BY_REASON: dict[ProposalReason, tuple[MemoryCategory, ...]] = {
    ProposalReason.SAVED_DECISION: (
        MemoryCategory.EXPLICIT_DECISION_NOTE,
        MemoryCategory.PAST_SESSION_ANCHOR,
    ),
}


def opt_in_scope_for(candidate: MemoryCandidate) -> list[MemoryCategory]:
    """The category scope an opt-in offer grants when confirmed.

    An explicit request grants only the category the user asked to remember.
    """
    if candidate.proposal_reason is ProposalReason.EXPLICIT_REQUEST:
        return [candidate.category]
    return list(OPT_IN_SCOPE_BY_REASON[candidate.proposal_reason])


class UserMemorySettings(BaseModel):
    """Per-user consent state. Memory is off until the user opts in."""

    enabled: bool = False
    enabled_categories: list[MemoryCategory] = Field(default_factory=list)

    def consents_to(self, category: MemoryCategory) -> bool:
        return self.enabled and category in self.enabled_categories


class PolicyOutcome(str, Enum):
    ALLOWED = "allowed"
    ALLOWED_OPT_IN_OFFER = "allowed_opt_in_offer"
    DENIED_DISABLED = "denied_disabled"
    DENIED_CATEGORY = "denied_category"
    DENIED_SCOPE = "denied_scope"
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
    opt_in_proposal_reasons: frozenset[ProposalReason] = field(
        default=DEFAULT_OPT_IN_PROPOSAL_REASONS
    )

    def evaluate(
        self,
        candidate: MemoryCandidate,
        settings: UserMemorySettings,
        *,
        last_prompted_at: datetime | None,
        now: datetime,
    ) -> PolicyDecision:
        opt_in_offer = False
        if not settings.enabled:
            if candidate.proposal_reason not in self.opt_in_proposal_reasons:
                return PolicyDecision(
                    allowed=False,
                    outcome=PolicyOutcome.DENIED_DISABLED,
                    reasons=["memory is disabled for this user"],
                )
            opt_in_offer = True
        if candidate.category not in self.allowed_categories:
            return PolicyDecision(
                allowed=False,
                outcome=PolicyOutcome.DENIED_CATEGORY,
                reasons=[
                    f"category {candidate.category.value} is outside the"
                    " active allowlist"
                ],
            )
        if not opt_in_offer and not settings.consents_to(candidate.category):
            return PolicyDecision(
                allowed=False,
                outcome=PolicyOutcome.DENIED_SCOPE,
                reasons=[f"user consent does not cover {candidate.category.value}"],
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
        if opt_in_offer:
            return PolicyDecision(
                allowed=True,
                outcome=PolicyOutcome.ALLOWED_OPT_IN_OFFER,
                reasons=["approved earned opt-in moment while memory is off"],
            )
        return PolicyDecision(
            allowed=True,
            outcome=PolicyOutcome.ALLOWED,
            reasons=["candidate passed consent, category, and sensitivity"],
        )
