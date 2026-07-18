"""Regression tests for the consent/opt-in lifecycle fix.

Covers: earned opt-in offers are the only proposals allowed while memory is
off; confirming an offer creates the scoped opt-in; disabling invalidates
pending candidates; confirmation rechecks current consent; retrieval honors
the consented scope.
"""

from datetime import datetime, timedelta, timezone

from argus.memory.contracts import (
    ConsentGrant,
    ConsentState,
    MemoryCandidate,
    MemoryCategory,
    MemoryRecord,
    MemorySourceRef,
    ProposalReason,
    SensitivityFlag,
)
from argus.memory.policy import (
    MemoryPolicy,
    PolicyOutcome,
    UserMemorySettings,
)
from argus.memory.provider import DeterministicFakeMemoryProvider
from argus.memory.service import (
    ExplicitMemoryRequest,
    MemoryService,
    MemoryServiceConfig,
    ProposalStatus,
    SavedDecisionSource,
)
from argus.memory.store import InMemoryCanonicalMemoryStore

NOW = datetime(2026, 7, 18, 3, 0, 0, tzinfo=timezone.utc)

DECISION_SCOPE = [
    MemoryCategory.EXPLICIT_DECISION_NOTE,
    MemoryCategory.PAST_SESSION_ANCHOR,
]


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


def _service() -> tuple[MemoryService, InMemoryCanonicalMemoryStore]:
    store = InMemoryCanonicalMemoryStore()
    ticker = iter(range(1, 1000))
    service = MemoryService(
        store=store,
        provider=DeterministicFakeMemoryProvider(),
        config=MemoryServiceConfig(globally_enabled=True),
        clock=lambda: NOW,
        id_factory=lambda: f"id-{next(ticker)}",
    )
    return service, store


def _decision_source() -> SavedDecisionSource:
    return SavedDecisionSource(
        decision_note_id="dn-1",
        evidence_artifact_id="ev-1",
        decision_state="rejected",
        note="Too much drawdown for me",
        label="Avoids high-drawdown leveraged ideas",
    )


class TestPolicyOptIn:
    def test_disabled_plus_approved_reason_is_an_opt_in_offer(self) -> None:
        decision = MemoryPolicy().evaluate(
            _candidate(), UserMemorySettings(), last_prompted_at=None, now=NOW
        )
        assert decision.allowed is True
        assert decision.outcome is PolicyOutcome.ALLOWED_OPT_IN_OFFER

    def test_disabled_plus_unapproved_reason_stays_denied(self) -> None:
        narrowed = MemoryPolicy(
            opt_in_proposal_reasons=frozenset({ProposalReason.SAVED_DECISION})
        )
        decision = narrowed.evaluate(
            _candidate(proposal_reason=ProposalReason.EXPLICIT_REQUEST),
            UserMemorySettings(),
            last_prompted_at=None,
            now=NOW,
        )
        assert decision.allowed is False
        assert decision.outcome is PolicyOutcome.DENIED_DISABLED

    def test_sensitivity_still_suppresses_an_opt_in_offer(self) -> None:
        decision = MemoryPolicy().evaluate(
            _candidate(sensitivity_flags=[SensitivityFlag.ACCOUNT_BALANCE]),
            UserMemorySettings(),
            last_prompted_at=None,
            now=NOW,
        )
        assert decision.outcome is PolicyOutcome.SUPPRESSED_SENSITIVE

    def test_cooldown_still_suppresses_an_opt_in_offer(self) -> None:
        decision = MemoryPolicy().evaluate(
            _candidate(),
            UserMemorySettings(),
            last_prompted_at=NOW - timedelta(days=1),
            now=NOW,
        )
        assert decision.outcome is PolicyOutcome.SUPPRESSED_COOLDOWN

    def test_enabled_user_outside_consented_scope_is_denied_scope(self) -> None:
        settings = UserMemorySettings(
            enabled=True, enabled_categories=list(DECISION_SCOPE)
        )
        decision = MemoryPolicy().evaluate(
            _candidate(
                category=MemoryCategory.WORKFLOW_PREFERENCE,
                proposal_reason=ProposalReason.EXPLICIT_REQUEST,
            ),
            settings,
            last_prompted_at=None,
            now=NOW,
        )
        assert decision.allowed is False
        assert decision.outcome is PolicyOutcome.DENIED_SCOPE


class TestOptInOfferLifecycle:
    def test_offer_carries_the_decision_grounded_scope(self) -> None:
        service, _store = _service()
        result = service.propose_from_saved_decision("user-a", _decision_source())
        assert result.status is ProposalStatus.PROPOSED
        assert result.policy is not None
        assert result.policy.outcome is PolicyOutcome.ALLOWED_OPT_IN_OFFER
        assert result.candidate is not None
        assert result.candidate.opt_in_scope == DECISION_SCOPE

    def test_confirming_the_offer_creates_the_scoped_opt_in(self) -> None:
        service, store = _service()
        offered = service.propose_from_saved_decision("user-a", _decision_source())
        assert offered.candidate is not None
        record = service.confirm("user-a", offered.candidate.id)
        assert record is not None
        settings = store.get_settings("user-a")
        assert settings.enabled is True
        assert settings.enabled_categories == DECISION_SCOPE
        assert not settings.consents_to(MemoryCategory.PERSONALIZATION_PREFERENCE)

    def test_scope_binds_later_proposals(self) -> None:
        service, store = _service()
        offered = service.propose_from_saved_decision("user-a", _decision_source())
        assert offered.candidate is not None
        assert service.confirm("user-a", offered.candidate.id) is not None
        preference = service.propose_from_explicit_request(
            "user-a",
            ExplicitMemoryRequest(
                text="Remember I prefer SPY",
                label="Prefers SPY",
                category=MemoryCategory.PERSONALIZATION_PREFERENCE,
            ),
        )
        assert preference.status is ProposalStatus.REJECTED_POLICY
        assert preference.policy is not None
        assert preference.policy.outcome is PolicyOutcome.DENIED_SCOPE
        store.mark_prompted(
            "user-a",
            MemoryCategory.EXPLICIT_DECISION_NOTE,
            NOW - timedelta(days=30),
        )
        in_scope = service.propose_from_saved_decision("user-a", _decision_source())
        assert in_scope.status is ProposalStatus.PROPOSED
        assert in_scope.candidate is not None
        assert in_scope.candidate.opt_in_scope is None

    def test_ordinary_confirmed_record_has_no_opt_in_side_effect(self) -> None:
        service, store = _service()
        service.enable("user-a", [MemoryCategory.PERSONALIZATION_PREFERENCE])
        before = store.get_settings("user-a")
        result = service.propose_from_explicit_request(
            "user-a",
            ExplicitMemoryRequest(
                text="Remember I prefer SPY",
                label="Prefers SPY",
                category=MemoryCategory.PERSONALIZATION_PREFERENCE,
            ),
        )
        assert result.candidate is not None
        assert result.candidate.opt_in_scope is None
        assert service.confirm("user-a", result.candidate.id) is not None
        assert store.get_settings("user-a") == before


class TestExplicitRequestOptIn:
    """An explicit "remember this" while memory is off is an approved offer
    (memo §15.3) granting only the requested category on confirmation."""

    def _request(self) -> ExplicitMemoryRequest:
        return ExplicitMemoryRequest(
            text="Remember that I prefer SPY as my default benchmark",
            label="Prefers SPY benchmark",
            category=MemoryCategory.PERSONALIZATION_PREFERENCE,
            conversation_id="conv-1",
        )

    def test_policy_treats_disabled_explicit_request_as_offer(self) -> None:
        decision = MemoryPolicy().evaluate(
            _candidate(proposal_reason=ProposalReason.EXPLICIT_REQUEST),
            UserMemorySettings(),
            last_prompted_at=None,
            now=NOW,
        )
        assert decision.allowed is True
        assert decision.outcome is PolicyOutcome.ALLOWED_OPT_IN_OFFER

    def test_offer_grants_only_the_requested_category(self) -> None:
        service, store = _service()
        offered = service.propose_from_explicit_request("user-a", self._request())
        assert offered.status is ProposalStatus.PROPOSED
        assert offered.candidate is not None
        assert offered.candidate.opt_in_scope == [
            MemoryCategory.PERSONALIZATION_PREFERENCE
        ]
        record = service.confirm("user-a", offered.candidate.id)
        assert record is not None
        settings = store.get_settings("user-a")
        assert settings.enabled is True
        assert settings.enabled_categories == [MemoryCategory.PERSONALIZATION_PREFERENCE]
        assert not settings.consents_to(MemoryCategory.EXPLICIT_DECISION_NOTE)

    def test_declining_the_offer_does_not_enable_memory(self) -> None:
        service, store = _service()
        offered = service.propose_from_explicit_request("user-a", self._request())
        assert offered.candidate is not None
        service.decline("user-a", offered.candidate.id)
        settings = store.get_settings("user-a")
        assert settings.enabled is False
        assert settings.enabled_categories == []
        assert store.list_records("user-a") == []
        assert store.get_candidate("user-a", offered.candidate.id) is None

    def test_offer_still_respects_sensitivity_suppression(self) -> None:
        service, store = _service()
        request = self._request().model_copy(
            update={"sensitivity_flags": [SensitivityFlag.ACCOUNT_BALANCE]}
        )
        result = service.propose_from_explicit_request("user-a", request)
        assert result.status is ProposalStatus.REJECTED_POLICY
        assert result.policy is not None
        assert result.policy.outcome is PolicyOutcome.SUPPRESSED_SENSITIVE
        assert store.list_candidates("user-a") == []

    def test_offer_still_respects_cooldown(self) -> None:
        service, _store = _service()
        first = service.propose_from_explicit_request("user-a", self._request())
        assert first.status is ProposalStatus.PROPOSED
        second = service.propose_from_explicit_request("user-a", self._request())
        assert second.status is ProposalStatus.REJECTED_POLICY
        assert second.policy is not None
        assert second.policy.outcome is PolicyOutcome.SUPPRESSED_COOLDOWN

    def test_offer_still_respects_the_category_allowlist(self) -> None:
        narrowed = MemoryPolicy(
            allowed_categories=frozenset({MemoryCategory.EXPLICIT_DECISION_NOTE})
        )
        decision = narrowed.evaluate(
            _candidate(
                proposal_reason=ProposalReason.EXPLICIT_REQUEST,
                category=MemoryCategory.PERSONALIZATION_PREFERENCE,
            ),
            UserMemorySettings(),
            last_prompted_at=None,
            now=NOW,
        )
        assert decision.allowed is False
        assert decision.outcome is PolicyOutcome.DENIED_CATEGORY

    def test_global_flag_still_gates_explicit_offers(self) -> None:
        store = InMemoryCanonicalMemoryStore()
        service = MemoryService(
            store=store,
            provider=DeterministicFakeMemoryProvider(),
            config=MemoryServiceConfig(globally_enabled=False),
            clock=lambda: NOW,
        )
        result = service.propose_from_explicit_request("user-a", self._request())
        assert result.status is ProposalStatus.REJECTED_GLOBAL_DISABLED


class TestDisableInvalidatesPending:
    def test_disable_discards_pending_candidates(self) -> None:
        service, store = _service()
        service.enable("user-a", [MemoryCategory.PERSONALIZATION_PREFERENCE])
        proposed = service.propose_from_explicit_request(
            "user-a",
            ExplicitMemoryRequest(
                text="Remember I prefer SPY",
                label="Prefers SPY",
                category=MemoryCategory.PERSONALIZATION_PREFERENCE,
            ),
        )
        assert proposed.candidate is not None
        service.disable("user-a")
        assert store.list_candidates("user-a") == []
        assert service.confirm("user-a", proposed.candidate.id) is None
        assert store.list_records("user-a") == []


class TestConfirmRechecksConsent:
    def test_stale_candidate_after_disable_cannot_confirm(self) -> None:
        service, store = _service()
        stale = _candidate(
            id="cand-stale",
            proposal_reason=ProposalReason.EXPLICIT_REQUEST,
            category=MemoryCategory.PERSONALIZATION_PREFERENCE,
        )
        store.add_candidate(stale)  # simulates consent changing after proposal
        assert service.confirm("user-a", "cand-stale") is None
        assert store.list_records("user-a") == []
        assert store.get_candidate("user-a", "cand-stale") is None

    def test_descoped_candidate_cannot_confirm(self) -> None:
        service, store = _service()
        store.set_settings(
            "user-a",
            UserMemorySettings(enabled=True, enabled_categories=list(DECISION_SCOPE)),
        )
        stale = _candidate(
            id="cand-descoped",
            proposal_reason=ProposalReason.EXPLICIT_REQUEST,
            category=MemoryCategory.PERSONALIZATION_PREFERENCE,
        )
        store.add_candidate(stale)
        assert service.confirm("user-a", "cand-descoped") is None
        assert store.list_records("user-a") == []


class TestRetrievalHonorsScope:
    def test_out_of_scope_records_are_not_retrieved(self) -> None:
        store = InMemoryCanonicalMemoryStore()
        provider = DeterministicFakeMemoryProvider()
        service = MemoryService(
            store=store,
            provider=provider,
            config=MemoryServiceConfig(globally_enabled=True),
            clock=lambda: NOW,
        )
        record = MemoryRecord(
            id="mem-pref",
            user_id="user-a",
            category=MemoryCategory.PERSONALIZATION_PREFERENCE,
            value="Prefers SPY as the default benchmark",
            label="Prefers SPY benchmark",
            source_refs=[MemorySourceRef(kind="explicit_request", ref_id="req-1")],
            consent=ConsentGrant(state=ConsentState.CONFIRMED, decided_at=NOW),
            stored_reason="confirmed under an earlier broader scope",
            created_at=NOW,
            updated_at=NOW,
        )
        store.add_record(record)
        provider.project(record)  # the provider WOULD match it
        store.set_settings(
            "user-a",
            UserMemorySettings(enabled=True, enabled_categories=list(DECISION_SCOPE)),
        )
        assert service.retrieve("user-a", "SPY benchmark") == []
        store.set_settings(
            "user-a",
            UserMemorySettings(
                enabled=True,
                enabled_categories=[MemoryCategory.PERSONALIZATION_PREFERENCE],
            ),
        )
        assert [
            item.record.id for item in service.retrieve("user-a", "SPY benchmark")
        ] == ["mem-pref"]
