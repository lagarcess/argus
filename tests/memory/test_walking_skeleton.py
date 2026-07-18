"""End-to-end proof of the personalization-memory walking skeleton.

Walks the full authorized lifecycle in order: saved-decision fixture ->
candidate -> policy -> explicit confirmation -> canonical record -> bounded
retrieval with provenance/why -> explain -> edit -> delete -> disable/reset.
Also proves the disabled configuration is inert end to end.
"""

from datetime import datetime, timedelta, timezone

from argus.memory.contracts import ConsentState, MemoryCategory
from argus.memory.policy import PolicyOutcome
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

DECISION_FIXTURE = SavedDecisionSource(
    decision_note_id="dn-eth-rsi",
    evidence_artifact_id="ev-eth-rsi",
    decision_state="promising",
    note="RSI entry beat buy-and-hold drawdown",
    label="ETH RSI idea looked promising",
    locale="es-419",
)


def _build() -> (
    tuple[MemoryService, InMemoryCanonicalMemoryStore, DeterministicFakeMemoryProvider]
):
    store = InMemoryCanonicalMemoryStore()
    provider = DeterministicFakeMemoryProvider()
    ticker = iter(range(1, 1000))
    service = MemoryService(
        store=store,
        provider=provider,
        config=MemoryServiceConfig(globally_enabled=True),
        clock=lambda: NOW,
        id_factory=lambda: f"id-{next(ticker)}",
    )
    return service, store, provider


class TestWalkingSkeleton:
    def test_full_lifecycle_from_saved_decision_fixture(self) -> None:
        service, store, provider = _build()
        user = "user-founder-qa"

        # Off by default: nothing retrieves. An explicit request while off is
        # itself an earned opt-in offer; declining it must not enable memory.
        assert service.retrieve(user, "ETH idea") == []
        cold = service.propose_from_explicit_request(
            user,
            ExplicitMemoryRequest(
                text="Remember I prefer SPY",
                label="Prefers SPY",
                category=MemoryCategory.PERSONALIZATION_PREFERENCE,
            ),
        )
        assert cold.status is ProposalStatus.PROPOSED
        assert cold.policy is not None
        assert cold.policy.outcome is PolicyOutcome.ALLOWED_OPT_IN_OFFER
        assert cold.candidate is not None
        service.decline(user, cold.candidate.id)
        assert store.get_settings(user).enabled is False
        assert service.retrieve(user, "SPY") == []

        # The saved-decision moment is the one approved earned opt-in offer.
        proposed = service.propose_from_saved_decision(user, DECISION_FIXTURE)
        assert proposed.status is ProposalStatus.PROPOSED
        candidate = proposed.candidate
        assert candidate is not None
        assert candidate.category is MemoryCategory.EXPLICIT_DECISION_NOTE
        assert candidate.locale == "es-419"
        assert candidate.opt_in_scope is not None

        # Explicit confirmation creates the scoped opt-in and the record.
        record = service.confirm(user, candidate.id)
        assert record is not None
        assert record.consent.state is ConsentState.CONFIRMED
        assert record.provider_ref is not None
        settings = store.get_settings(user)
        assert settings.enabled is True
        assert settings.enabled_categories == candidate.opt_in_scope
        assert not settings.consents_to(MemoryCategory.PERSONALIZATION_PREFERENCE)

        # Bounded retrieval returns it with provenance and why.
        results = service.retrieve(user, "what did I decide about ETH RSI")
        assert [item.record.id for item in results] == [record.id]
        assert "matched" in results[0].why_selected
        assert {ref.kind for ref in results[0].provenance} == {
            "decision_note",
            "evidence_artifact",
        }

        # "Why was this remembered?" is answerable from canonical fields.
        explanation = service.explain(user, record.id)
        assert explanation is not None
        assert "revisit and compare" in explanation.stored_reason
        assert explanation.last_used_at == NOW

        # Edit, then delete.
        edited = service.edit(user, record.id, label="ETH RSI: sigue promising")
        assert edited is not None
        assert edited.label == "ETH RSI: sigue promising"
        assert service.delete(user, record.id) is True
        assert service.retrieve(user, "ETH RSI") == []
        assert provider.indexed_refs(user) == set()

        # Rebuild one memory, then disable and reset for the user.
        store.mark_prompted(
            user,
            MemoryCategory.EXPLICIT_DECISION_NOTE,
            NOW - timedelta(days=30),
        )
        again = service.propose_from_saved_decision(user, DECISION_FIXTURE)
        assert again.candidate is not None
        assert service.confirm(user, again.candidate.id) is not None
        service.disable(user)
        assert service.retrieve(user, "ETH RSI") == []
        assert service.reset(user) == 1
        assert store.list_records(user) == []
        assert provider.indexed_refs(user) == set()

    def test_disabled_configuration_is_inert_end_to_end(self) -> None:
        store = InMemoryCanonicalMemoryStore()
        service = MemoryService(
            store=store,
            provider=DeterministicFakeMemoryProvider(),
            config=MemoryServiceConfig(globally_enabled=False),
            clock=lambda: NOW,
        )
        user = "user-a"
        store.set_enabled(user, True)  # even an opted-in user stays inert
        assert (
            service.propose_from_saved_decision(user, DECISION_FIXTURE).status
            is ProposalStatus.REJECTED_GLOBAL_DISABLED
        )
        assert (
            service.propose_from_explicit_request(
                user,
                ExplicitMemoryRequest(
                    text="Remember I prefer SPY",
                    label="Prefers SPY",
                    category=MemoryCategory.PERSONALIZATION_PREFERENCE,
                ),
            ).status
            is ProposalStatus.REJECTED_GLOBAL_DISABLED
        )
        assert service.confirm(user, "cand-anything") is None
        assert service.retrieve(user, "anything") == []
        assert store.list_records(user) == []
