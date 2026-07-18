"""Contract tests for the personalization-memory walking skeleton."""

from datetime import datetime, timezone

import pytest
from argus.memory.contracts import (
    CONSENT_VERSION,
    ConsentGrant,
    ConsentState,
    MemoryCandidate,
    MemoryCategory,
    MemoryRecord,
    MemorySourceRef,
    ProposalReason,
    SensitivityFlag,
)
from pydantic import ValidationError

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


class TestMemoryCategory:
    def test_allowlist_is_exactly_the_five_canonical_categories(self) -> None:
        assert {category.value for category in MemoryCategory} == {
            "personalization_preference",
            "workflow_preference",
            "explicit_decision_note",
            "automation_intent",
            "past_session_anchor",
        }

    def test_unknown_category_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _candidate(category="broad_profile")


class TestMemoryCandidate:
    def test_valid_candidate_round_trips(self) -> None:
        candidate = _candidate()
        assert candidate.locale == "en"
        assert candidate.sensitivity_flags == []
        assert candidate.source_refs[0].kind == "decision_note"

    def test_confidence_is_bounded(self) -> None:
        with pytest.raises(ValidationError):
            _candidate(confidence=1.5)
        with pytest.raises(ValidationError):
            _candidate(confidence=-0.1)

    def test_label_must_not_be_empty(self) -> None:
        with pytest.raises(ValidationError):
            _candidate(label="")

    def test_whitespace_only_text_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _candidate(label="   ")
        with pytest.raises(ValidationError):
            _candidate(proposed_value=" \t ")

    def test_text_fields_are_stripped(self) -> None:
        candidate = _candidate(label="  Avoids leveraged ETFs  ")
        assert candidate.label == "Avoids leveraged ETFs"

    def test_sensitivity_flags_are_typed(self) -> None:
        candidate = _candidate(
            sensitivity_flags=[SensitivityFlag.ACCOUNT_BALANCE],
        )
        assert candidate.sensitivity_flags == [SensitivityFlag.ACCOUNT_BALANCE]
        with pytest.raises(ValidationError):
            _candidate(sensitivity_flags=["net_worth_gossip"])


class TestMemoryRecord:
    def _record(self, consent_state: ConsentState) -> MemoryRecord:
        return MemoryRecord.model_validate(
            {
                "id": "mem-1",
                "user_id": "user-a",
                "category": MemoryCategory.EXPLICIT_DECISION_NOTE,
                "value": "Rejected leveraged ETFs after drawdown evidence",
                "label": "Avoids leveraged ETFs",
                "source_refs": [MemorySourceRef(kind="decision_note", ref_id="dn-1")],
                "consent": ConsentGrant(state=consent_state, decided_at=NOW),
                "stored_reason": "User confirmed at decision-save moment",
                "created_at": NOW,
                "updated_at": NOW,
            }
        )

    def test_record_requires_confirmed_consent(self) -> None:
        record = self._record(ConsentState.CONFIRMED)
        assert record.consent.version == CONSENT_VERSION
        assert record.enabled is True
        assert record.provider_ref is None

    def test_unconfirmed_consent_cannot_become_a_record(self) -> None:
        for state in (ConsentState.PROPOSED, ConsentState.DECLINED):
            with pytest.raises(ValidationError):
                self._record(state)
