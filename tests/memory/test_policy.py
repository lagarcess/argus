"""Policy tests: allowlist, sensitivity suppression, enablement, cooldown."""

from datetime import datetime, timedelta, timezone

from argus.memory.contracts import (
    MemoryCandidate,
    MemoryCategory,
    MemorySourceRef,
    ProposalReason,
    SensitivityFlag,
)
from argus.memory.policy import (
    MemoryPolicy,
    PolicyOutcome,
    UserMemorySettings,
)

NOW = datetime(2026, 7, 18, 3, 0, 0, tzinfo=timezone.utc)


def _candidate(**overrides: object) -> MemoryCandidate:
    payload: dict[str, object] = {
        "id": "cand-1",
        "user_id": "user-a",
        "category": MemoryCategory.EXPLICIT_DECISION_NOTE,
        "proposed_value": "Rejected leveraged ETFs after drawdown evidence",
        "label": "Avoids leveraged ETFs",
        "future_benefit": "Argus can skip re-suggesting leveraged ETF ideas",
        "source_refs": [MemorySourceRef(kind="decision_note", ref_id="dn-1")],
        "confidence": 0.9,
        "proposal_reason": ProposalReason.SAVED_DECISION,
        "created_at": NOW,
    }
    payload.update(overrides)
    return MemoryCandidate.model_validate(payload)


ENABLED = UserMemorySettings(enabled=True)


class TestEnablement:
    def test_memory_is_off_by_default(self) -> None:
        assert UserMemorySettings().enabled is False

    def test_disabled_user_is_denied(self) -> None:
        decision = MemoryPolicy().evaluate(
            _candidate(), UserMemorySettings(), last_prompted_at=None, now=NOW
        )
        assert decision.allowed is False
        assert decision.outcome is PolicyOutcome.DENIED_DISABLED

    def test_disabled_wins_over_every_other_rule(self) -> None:
        decision = MemoryPolicy().evaluate(
            _candidate(sensitivity_flags=[SensitivityFlag.ACCOUNT_BALANCE]),
            UserMemorySettings(),
            last_prompted_at=NOW,
            now=NOW,
        )
        assert decision.outcome is PolicyOutcome.DENIED_DISABLED


class TestCategoryAllowlist:
    def test_allowlisted_category_passes(self) -> None:
        decision = MemoryPolicy().evaluate(
            _candidate(), ENABLED, last_prompted_at=None, now=NOW
        )
        assert decision.allowed is True
        assert decision.outcome is PolicyOutcome.ALLOWED

    def test_policy_can_narrow_to_the_decision_grounded_milestone(self) -> None:
        policy = MemoryPolicy(
            allowed_categories=frozenset(
                {
                    MemoryCategory.EXPLICIT_DECISION_NOTE,
                    MemoryCategory.PAST_SESSION_ANCHOR,
                }
            )
        )
        allowed = policy.evaluate(_candidate(), ENABLED, last_prompted_at=None, now=NOW)
        denied = policy.evaluate(
            _candidate(category=MemoryCategory.WORKFLOW_PREFERENCE),
            ENABLED,
            last_prompted_at=None,
            now=NOW,
        )
        assert allowed.allowed is True
        assert denied.allowed is False
        assert denied.outcome is PolicyOutcome.DENIED_CATEGORY


class TestSensitivitySuppression:
    def test_any_sensitivity_flag_suppresses(self) -> None:
        for flag in SensitivityFlag:
            decision = MemoryPolicy().evaluate(
                _candidate(sensitivity_flags=[flag]),
                ENABLED,
                last_prompted_at=None,
                now=NOW,
            )
            assert decision.allowed is False, flag
            assert decision.outcome is PolicyOutcome.SUPPRESSED_SENSITIVE


class TestCooldown:
    def test_repeat_prompt_inside_cooldown_is_suppressed(self) -> None:
        policy = MemoryPolicy(proposal_cooldown=timedelta(days=7))
        decision = policy.evaluate(
            _candidate(),
            ENABLED,
            last_prompted_at=NOW - timedelta(days=2),
            now=NOW,
        )
        assert decision.allowed is False
        assert decision.outcome is PolicyOutcome.SUPPRESSED_COOLDOWN

    def test_prompt_after_cooldown_is_allowed(self) -> None:
        policy = MemoryPolicy(proposal_cooldown=timedelta(days=7))
        decision = policy.evaluate(
            _candidate(),
            ENABLED,
            last_prompted_at=NOW - timedelta(days=8),
            now=NOW,
        )
        assert decision.allowed is True

    def test_decision_carries_a_reason_string(self) -> None:
        decision = MemoryPolicy(proposal_cooldown=timedelta(days=7)).evaluate(
            _candidate(),
            ENABLED,
            last_prompted_at=NOW - timedelta(days=1),
            now=NOW,
        )
        assert decision.reasons
        assert all(isinstance(reason, str) for reason in decision.reasons)
