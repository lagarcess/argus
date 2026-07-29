"""Deterministic consent, sensitivity, context, and cooldown policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel, ConfigDict

from argus.memory.contracts import (
    MemoryCandidateDraft,
    MemoryCategory,
    MemoryConsentSettings,
    MemoryOperationContext,
    MemoryProposalTrigger,
    SensitivityAssessment,
    SensitivityStatus,
)

DEFAULT_PROACTIVE_COOLDOWN = timedelta(days=7)
DEFAULT_DECLINE_COOLDOWN = timedelta(days=30)
SAFE_MEMORY_CATEGORIES = frozenset(MemoryCategory)
SAVED_DECISION_OPT_IN_SCOPE = frozenset(
    {
        MemoryCategory.EXPLICIT_DECISION_NOTE,
        MemoryCategory.PAST_SESSION_ANCHOR,
    }
)
RESTRICTED_CONTEXTS = frozenset(
    {
        MemoryOperationContext.BROKER,
        MemoryOperationContext.EXPORT,
        MemoryOperationContext.RESTRICTED_FINANCIAL,
    }
)


class PolicyOutcome(str, Enum):
    ALLOWED = "allowed"
    ALLOWED_OPT_IN = "allowed_opt_in"
    DENIED_CATEGORY = "denied_category"
    DENIED_SCOPE = "denied_scope"
    DENIED_ASSISTED_FIRST_OPT_IN = "denied_assisted_first_opt_in"
    SUPPRESSED_CONTEXT = "suppressed_context"
    SUPPRESSED_SENSITIVITY = "suppressed_sensitivity"
    SUPPRESSED_COOLDOWN = "suppressed_cooldown"
    SUPPRESSED_DISMISSAL = "suppressed_dismissal"


class PolicyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed: bool
    outcome: PolicyOutcome
    opt_in_scope: frozenset[MemoryCategory] = frozenset()


@dataclass(frozen=True)
class MemoryPolicy:
    """Evaluates typed candidates without inspecting natural-language content."""

    allowed_categories: frozenset[MemoryCategory] = field(default=SAFE_MEMORY_CATEGORIES)
    proactive_cooldown: timedelta = DEFAULT_PROACTIVE_COOLDOWN
    decline_cooldown: timedelta = DEFAULT_DECLINE_COOLDOWN

    def evaluate(
        self,
        draft: MemoryCandidateDraft,
        settings: MemoryConsentSettings,
        *,
        context: MemoryOperationContext,
        last_proactive_prompt_at: datetime | None,
        last_declined_at: datetime | None,
        now: datetime,
    ) -> PolicyDecision:
        preflight = self.preflight(draft, context=context)
        if not preflight.allowed:
            return preflight

        if draft.trigger is MemoryProposalTrigger.EXPLICIT_REQUEST:
            if settings.enabled and draft.category in settings.enabled_categories:
                return PolicyDecision(
                    allowed=True,
                    outcome=PolicyOutcome.ALLOWED,
                )
            return PolicyDecision(
                allowed=True,
                outcome=PolicyOutcome.ALLOWED_OPT_IN,
                opt_in_scope=frozenset({draft.category}),
            )

        if (
            draft.trigger is MemoryProposalTrigger.ASSISTED_STABLE_PREFERENCE
            and not settings.enabled
        ):
            return PolicyDecision(
                allowed=False,
                outcome=PolicyOutcome.DENIED_ASSISTED_FIRST_OPT_IN,
            )

        if self._inside_cooldown(
            last_declined_at,
            now=now,
            cooldown=self.decline_cooldown,
        ):
            return PolicyDecision(
                allowed=False,
                outcome=PolicyOutcome.SUPPRESSED_DISMISSAL,
            )
        if self._inside_cooldown(
            last_proactive_prompt_at,
            now=now,
            cooldown=self.proactive_cooldown,
        ):
            return PolicyDecision(
                allowed=False,
                outcome=PolicyOutcome.SUPPRESSED_COOLDOWN,
            )

        if not settings.enabled:
            if (
                draft.trigger is MemoryProposalTrigger.SAVED_DECISION
                and draft.category is MemoryCategory.EXPLICIT_DECISION_NOTE
            ):
                return PolicyDecision(
                    allowed=True,
                    outcome=PolicyOutcome.ALLOWED_OPT_IN,
                    opt_in_scope=SAVED_DECISION_OPT_IN_SCOPE,
                )
            return PolicyDecision(
                allowed=False,
                outcome=PolicyOutcome.DENIED_SCOPE,
            )
        if draft.category not in settings.enabled_categories:
            return PolicyDecision(
                allowed=False,
                outcome=PolicyOutcome.DENIED_SCOPE,
            )
        return PolicyDecision(
            allowed=True,
            outcome=PolicyOutcome.ALLOWED,
        )

    def preflight(
        self,
        draft: MemoryCandidateDraft,
        *,
        context: MemoryOperationContext,
    ) -> PolicyDecision:
        context_decision = self.preflight_context(
            sensitivity=draft.sensitivity,
            context=context,
        )
        if not context_decision.allowed:
            return context_decision
        if draft.category not in self.allowed_categories:
            return PolicyDecision(
                allowed=False,
                outcome=PolicyOutcome.DENIED_CATEGORY,
            )
        return PolicyDecision(
            allowed=True,
            outcome=PolicyOutcome.ALLOWED,
        )

    @staticmethod
    def preflight_context(
        *,
        sensitivity: SensitivityAssessment,
        context: MemoryOperationContext,
    ) -> PolicyDecision:
        if context in RESTRICTED_CONTEXTS:
            return PolicyDecision(
                allowed=False,
                outcome=PolicyOutcome.SUPPRESSED_CONTEXT,
            )
        if sensitivity.status is not SensitivityStatus.CLEAR or sensitivity.flags:
            return PolicyDecision(
                allowed=False,
                outcome=PolicyOutcome.SUPPRESSED_SENSITIVITY,
            )
        return PolicyDecision(
            allowed=True,
            outcome=PolicyOutcome.ALLOWED,
        )

    def validate_enable_scope(
        self,
        categories: frozenset[MemoryCategory],
    ) -> None:
        if not categories:
            raise ValueError("enable requires at least one category")
        if not categories <= self.allowed_categories:
            raise ValueError(
                "enable request includes a category outside the active allowlist"
            )

    @staticmethod
    def _inside_cooldown(
        occurred_at: datetime | None,
        *,
        now: datetime,
        cooldown: timedelta,
    ) -> bool:
        return occurred_at is not None and now - occurred_at < cooldown
