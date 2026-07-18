"""Lifecycle tests: propose (both sources), policy gate, confirm, decline."""

from datetime import datetime, timedelta, timezone

from argus.memory.contracts import (
    ConsentState,
    MemoryCategory,
    ProposalReason,
    SensitivityFlag,
)
from argus.memory.policy import MemoryPolicy, PolicyOutcome
from argus.memory.provider import DeterministicFakeMemoryProvider
from argus.memory.service import (
    ExplicitMemoryRequest,
    MemoryService,
    MemoryServiceConfig,
    ProposalStatus,
    SavedDecisionSource,
    memory_globally_enabled,
)
from argus.memory.store import InMemoryCanonicalMemoryStore

NOW = datetime(2026, 7, 18, 3, 0, 0, tzinfo=timezone.utc)


class ExplodingProvider:
    """Provider double that fails on every call."""

    def project(self, record: object) -> str:
        raise RuntimeError("provider down")

    def search(self, user_id: str, query: str, limit: int) -> list[object]:
        raise RuntimeError("provider down")

    def delete(self, user_id: str, provider_ref: str) -> None:
        raise RuntimeError("provider down")

    def reset(self, user_id: str) -> None:
        raise RuntimeError("provider down")


def _service(
    *,
    globally_enabled: bool = True,
    provider: object | None = None,
    store: InMemoryCanonicalMemoryStore | None = None,
) -> tuple[MemoryService, InMemoryCanonicalMemoryStore]:
    store = store or InMemoryCanonicalMemoryStore()
    ticker = iter(range(1, 1000))
    service = MemoryService(
        store=store,
        provider=provider or DeterministicFakeMemoryProvider(),
        config=MemoryServiceConfig(globally_enabled=globally_enabled),
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
        locale="en",
    )


def _explicit_request() -> ExplicitMemoryRequest:
    return ExplicitMemoryRequest(
        text="Remember that I prefer SPY as my default benchmark",
        label="Prefers SPY benchmark",
        category=MemoryCategory.PERSONALIZATION_PREFERENCE,
        conversation_id="conv-1",
        locale="en",
    )


class TestGlobalFlag:
    def test_flag_defaults_off(self, monkeypatch) -> None:
        monkeypatch.delenv("ARGUS_MEMORY_ENABLED", raising=False)
        assert memory_globally_enabled() is False

    def test_flag_reads_true_only_when_explicit(self, monkeypatch) -> None:
        monkeypatch.setenv("ARGUS_MEMORY_ENABLED", "true")
        assert memory_globally_enabled() is True
        monkeypatch.setenv("ARGUS_MEMORY_ENABLED", "1")
        assert memory_globally_enabled() is False

    def test_globally_disabled_service_proposes_nothing(self) -> None:
        service, store = _service(globally_enabled=False)
        store.set_enabled("user-a", True)
        result = service.propose_from_saved_decision("user-a", _decision_source())
        assert result.status is ProposalStatus.REJECTED_GLOBAL_DISABLED
        assert result.candidate is None


class TestPropose:
    def test_saved_decision_yields_decision_grounded_candidate(self) -> None:
        service, store = _service()
        store.set_enabled("user-a", True)
        result = service.propose_from_saved_decision("user-a", _decision_source())
        assert result.status is ProposalStatus.PROPOSED
        candidate = result.candidate
        assert candidate is not None
        assert candidate.category is MemoryCategory.EXPLICIT_DECISION_NOTE
        assert candidate.proposal_reason is ProposalReason.SAVED_DECISION
        assert {ref.kind for ref in candidate.source_refs} == {
            "decision_note",
            "evidence_artifact",
        }
        assert candidate.future_benefit

    def test_explicit_request_yields_candidate_with_request_provenance(
        self,
    ) -> None:
        service, store = _service()
        store.set_enabled("user-a", True)
        result = service.propose_from_explicit_request("user-a", _explicit_request())
        assert result.status is ProposalStatus.PROPOSED
        candidate = result.candidate
        assert candidate is not None
        assert candidate.proposal_reason is ProposalReason.EXPLICIT_REQUEST
        kinds = {ref.kind for ref in candidate.source_refs}
        assert "explicit_request" in kinds
        assert "conversation" in kinds

    def test_disabled_user_gets_policy_rejection_for_ordinary_requests(
        self,
    ) -> None:
        service, _store = _service()
        result = service.propose_from_explicit_request("user-a", _explicit_request())
        assert result.status is ProposalStatus.REJECTED_POLICY
        assert result.policy is not None
        assert result.policy.outcome is PolicyOutcome.DENIED_DISABLED

    def test_sensitive_request_is_suppressed_and_not_stored(self) -> None:
        service, store = _service()
        store.set_enabled("user-a", True)
        request = _explicit_request().model_copy(
            update={
                "sensitivity_flags": [SensitivityFlag.ACCOUNT_BALANCE],
            }
        )
        result = service.propose_from_explicit_request("user-a", request)
        assert result.status is ProposalStatus.REJECTED_POLICY
        assert result.policy is not None
        assert result.policy.outcome is PolicyOutcome.SUPPRESSED_SENSITIVE
        assert store.list_candidates("user-a") == []

    def test_second_proposal_inside_cooldown_is_suppressed(self) -> None:
        service, store = _service()
        store.set_enabled("user-a", True)
        first = service.propose_from_saved_decision("user-a", _decision_source())
        assert first.status is ProposalStatus.PROPOSED
        second = service.propose_from_saved_decision("user-a", _decision_source())
        assert second.status is ProposalStatus.REJECTED_POLICY
        assert second.policy is not None
        assert second.policy.outcome is PolicyOutcome.SUPPRESSED_COOLDOWN


class TestConfirmAndDecline:
    def test_confirm_creates_confirmed_record_and_consumes_candidate(
        self,
    ) -> None:
        service, store = _service()
        store.set_enabled("user-a", True)
        proposed = service.propose_from_saved_decision("user-a", _decision_source())
        assert proposed.candidate is not None
        record = service.confirm("user-a", proposed.candidate.id)
        assert record is not None
        assert record.consent.state is ConsentState.CONFIRMED
        assert record.stored_reason
        assert record.provider_ref is not None
        assert store.get_candidate("user-a", proposed.candidate.id) is None
        assert [row.id for row in store.list_records("user-a")] == [record.id]

    def test_confirm_is_owner_scoped(self) -> None:
        service, store = _service()
        store.set_enabled("user-a", True)
        proposed = service.propose_from_saved_decision("user-a", _decision_source())
        assert proposed.candidate is not None
        assert service.confirm("user-b", proposed.candidate.id) is None
        assert store.list_records("user-b") == []

    def test_decline_discards_candidate_without_a_record(self) -> None:
        service, store = _service()
        store.set_enabled("user-a", True)
        proposed = service.propose_from_saved_decision("user-a", _decision_source())
        assert proposed.candidate is not None
        service.decline("user-a", proposed.candidate.id)
        assert store.get_candidate("user-a", proposed.candidate.id) is None
        assert store.list_records("user-a") == []

    def test_provider_failure_does_not_block_confirmation(self) -> None:
        service, store = _service(provider=ExplodingProvider())
        store.set_enabled("user-a", True)
        proposed = service.propose_from_saved_decision("user-a", _decision_source())
        assert proposed.candidate is not None
        record = service.confirm("user-a", proposed.candidate.id)
        assert record is not None
        assert record.provider_ref is None

    def test_cooldown_state_survives_decline(self) -> None:
        service, store = _service()
        store.set_enabled("user-a", True)
        proposed = service.propose_from_saved_decision("user-a", _decision_source())
        assert proposed.candidate is not None
        service.decline("user-a", proposed.candidate.id)
        again = service.propose_from_saved_decision("user-a", _decision_source())
        assert again.status is ProposalStatus.REJECTED_POLICY

    def test_cooldown_expires_with_time(self) -> None:
        later = {"now": NOW}
        store = InMemoryCanonicalMemoryStore()
        ticker = iter(range(1, 1000))
        service = MemoryService(
            store=store,
            provider=DeterministicFakeMemoryProvider(),
            config=MemoryServiceConfig(
                globally_enabled=True,
                policy=MemoryPolicy(proposal_cooldown=timedelta(days=7)),
            ),
            clock=lambda: later["now"],
            id_factory=lambda: f"id-{next(ticker)}",
        )
        store.set_enabled("user-a", True)
        first = service.propose_from_saved_decision("user-a", _decision_source())
        assert first.status is ProposalStatus.PROPOSED
        later["now"] = NOW + timedelta(days=8)
        second = service.propose_from_saved_decision("user-a", _decision_source())
        assert second.status is ProposalStatus.PROPOSED
