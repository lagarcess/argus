from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from typing import cast

import pytest
from argus.memory.contracts import (
    MemoryCandidate,
    MemoryCandidateDraft,
    MemoryCategory,
    MemoryConsentSettings,
    MemoryOperationContext,
    MemoryProposalTrigger,
    MemoryProvenance,
    MemorySensitivityFlag,
    MemorySourceKind,
    SavedDecisionSource,
    SensitivityAssessment,
    SensitivityStatus,
)
from argus.memory.policy import MemoryPolicy, PolicyOutcome
from argus.memory.service import (
    Clock,
    IdFactory,
    MemoryAvailability,
    MemoryService,
    MemoryServiceConfig,
)
from argus.memory.store import (
    CanonicalMemoryStore,
    InMemoryCanonicalMemoryStore,
    ProposalHistorySnapshot,
)
from argus.memory.subject import (
    MemoryAccountKind,
    MemorySubject,
    RegisteredMemoryOwner,
    require_registered,
)

OWNER_ID = "6f65d7c2-6d25-4da3-8e33-3010a9309b0e"
NOW = datetime(2026, 7, 29, 16, 0, tzinfo=timezone.utc)
RECENT = NOW - timedelta(hours=1)
SAVED_DECISION_SCOPE = frozenset(
    {
        MemoryCategory.EXPLICIT_DECISION_NOTE,
        MemoryCategory.PAST_SESSION_ANCHOR,
    }
)


def _subject() -> MemorySubject:
    return MemorySubject(owner_id=OWNER_ID, kind=MemoryAccountKind.REGISTERED)


def _provenance() -> tuple[MemoryProvenance, ...]:
    return (
        MemoryProvenance(
            source_kind=MemorySourceKind.DECISION_NOTE,
            source_id="decision-note-7",
            source_version="1",
        ),
    )


def _saved_decision_source() -> SavedDecisionSource:
    return SavedDecisionSource(
        label="Revisit lower drawdown",
        value="The lower-drawdown version is the one to revisit.",
        provenance=_provenance()[0],
    )


def _clear_sensitivity() -> SensitivityAssessment:
    return SensitivityAssessment(status=SensitivityStatus.CLEAR)


def _empty_history() -> ProposalHistorySnapshot:
    return ProposalHistorySnapshot(
        last_proactive_prompt_at=None,
        last_declined_at=None,
    )


def _draft(
    *,
    category: MemoryCategory = MemoryCategory.EXPLICIT_DECISION_NOTE,
    trigger: MemoryProposalTrigger = MemoryProposalTrigger.SAVED_DECISION,
    sensitivity: SensitivityAssessment | None = None,
) -> MemoryCandidateDraft:
    return MemoryCandidateDraft(
        category=category,
        value="The lower-drawdown version is the one to revisit.",
        label="Revisit lower drawdown",
        future_benefit="Argus can compare this saved decision later.",
        provenance=_provenance(),
        trigger=trigger,
        sensitivity=sensitivity or SensitivityAssessment(status=SensitivityStatus.CLEAR),
    )


def _service(
    store: InMemoryCanonicalMemoryStore,
    *,
    now: datetime = NOW,
    policy: MemoryPolicy | None = None,
) -> MemoryService:
    generated_ids = iter(
        (
            "candidate-1",
            "candidate-2",
            "candidate-3",
            "consent-1",
            "record-1",
        )
    )
    return MemoryService(
        store=store,
        config=MemoryServiceConfig(available=True),
        policy=policy,
        clock=lambda: now,
        id_factory=lambda: next(generated_ids),
    )


class _ExplodingDependency:
    @property
    def available(self) -> bool:
        raise AssertionError("preflight denial must not inspect config")

    def __call__(self) -> object:
        raise AssertionError("preflight denial must not call clock or id factory")

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"preflight denial must not inspect store.{name}")


def _exploding_service(*, policy: MemoryPolicy | None = None) -> MemoryService:
    exploding = _ExplodingDependency()
    return MemoryService(
        config=cast(MemoryAvailability, exploding),
        store=cast(CanonicalMemoryStore, exploding),
        clock=cast(Clock, exploding),
        id_factory=cast(IdFactory, exploding),
        policy=policy,
    )


def _candidate(
    *,
    candidate_id: str = "candidate-atomic",
    trigger: MemoryProposalTrigger = MemoryProposalTrigger.SAVED_DECISION,
) -> MemoryCandidate:
    source = _saved_decision_source()
    return MemoryCandidate(
        id=candidate_id,
        owner_id=OWNER_ID,
        category=MemoryCategory.EXPLICIT_DECISION_NOTE,
        source=source,
        future_benefit="Argus can compare this saved decision later.",
        provenance_refs=(source.provenance,),
        trigger=trigger,
        sensitivity=_clear_sensitivity(),
        proposed_context=MemoryOperationContext.ORDINARY,
        opt_in_scope=SAVED_DECISION_SCOPE,
        created_at=NOW,
    )


class _ExplodingWriteDict(dict[tuple[str, MemoryCategory], datetime]):
    def __setitem__(
        self,
        key: tuple[str, MemoryCategory],
        value: datetime,
    ) -> None:
        raise RuntimeError("injected history write failure")


class _BarrierHistoryStore(InMemoryCanonicalMemoryStore):
    """Forces two proposals to evaluate the same decline-history snapshot."""

    def __init__(self) -> None:
        super().__init__()
        self._history_barrier = Barrier(2)

    def last_declined_at(
        self,
        owner: RegisteredMemoryOwner,
        category: MemoryCategory,
    ) -> datetime | None:
        observed = super().last_declined_at(owner, category)
        self._history_barrier.wait()
        return observed


def test_saved_decision_opt_in_has_only_the_narrow_decision_scope() -> None:
    """Catches a first saved-decision prompt that grants broad personalization."""
    decision = MemoryPolicy().evaluate(
        _draft(),
        MemoryConsentSettings(),
        context=MemoryOperationContext.ORDINARY,
        last_proactive_prompt_at=None,
        last_declined_at=None,
        now=NOW,
    )

    assert decision.allowed is True
    assert decision.outcome is PolicyOutcome.ALLOWED_OPT_IN
    assert decision.opt_in_scope == SAVED_DECISION_SCOPE


def test_explicit_request_grants_only_its_requested_category() -> None:
    """Catches an explicit request that silently opts into unrelated categories."""
    category = MemoryCategory.WORKFLOW_PREFERENCE
    decision = MemoryPolicy().evaluate(
        _draft(
            category=category,
            trigger=MemoryProposalTrigger.EXPLICIT_REQUEST,
        ),
        MemoryConsentSettings(),
        context=MemoryOperationContext.ORDINARY,
        last_proactive_prompt_at=RECENT,
        last_declined_at=RECENT,
        now=NOW,
    )

    assert decision.allowed is True
    assert decision.outcome is PolicyOutcome.ALLOWED_OPT_IN
    assert decision.opt_in_scope == frozenset({category})


@pytest.mark.parametrize(
    "trigger",
    (
        MemoryProposalTrigger.SAVED_DECISION,
        MemoryProposalTrigger.ASSISTED_STABLE_PREFERENCE,
    ),
)
@pytest.mark.parametrize(
    ("last_prompted", "last_declined", "expected"),
    (
        (RECENT, None, PolicyOutcome.SUPPRESSED_COOLDOWN),
        (None, RECENT, PolicyOutcome.SUPPRESSED_DISMISSAL),
    ),
)
def test_proactive_proposals_obey_prompt_and_dismissal_history(
    trigger: MemoryProposalTrigger,
    last_prompted: datetime | None,
    last_declined: datetime | None,
    expected: PolicyOutcome,
) -> None:
    """Catches proactive proposal triggers that repeatedly nag after recent history."""
    settings = MemoryConsentSettings(
        enabled=True,
        enabled_categories=frozenset(MemoryCategory),
    )

    decision = MemoryPolicy().evaluate(
        _draft(trigger=trigger),
        settings,
        context=MemoryOperationContext.ORDINARY,
        last_proactive_prompt_at=last_prompted,
        last_declined_at=last_declined,
        now=NOW,
    )

    assert decision.allowed is False
    assert decision.outcome is expected
    assert decision.opt_in_scope == frozenset()


def test_assisted_preference_cannot_open_the_first_opt_in() -> None:
    """Catches inferred stable preferences enabling memory before earned consent."""
    decision = MemoryPolicy().evaluate(
        _draft(
            category=MemoryCategory.PERSONALIZATION_PREFERENCE,
            trigger=MemoryProposalTrigger.ASSISTED_STABLE_PREFERENCE,
        ),
        MemoryConsentSettings(),
        context=MemoryOperationContext.ORDINARY,
        last_proactive_prompt_at=None,
        last_declined_at=None,
        now=NOW,
    )

    assert decision.allowed is False
    assert decision.outcome is PolicyOutcome.DENIED_ASSISTED_FIRST_OPT_IN


def test_enabled_scope_does_not_leak_to_an_unselected_category() -> None:
    """Catches category consent that behaves like an implicit all-categories grant."""
    settings = MemoryConsentSettings(
        enabled=True,
        enabled_categories=frozenset({MemoryCategory.WORKFLOW_PREFERENCE}),
    )

    decision = MemoryPolicy().evaluate(
        _draft(category=MemoryCategory.PERSONALIZATION_PREFERENCE),
        settings,
        context=MemoryOperationContext.ORDINARY,
        last_proactive_prompt_at=None,
        last_declined_at=None,
        now=NOW,
    )

    assert decision.allowed is False
    assert decision.outcome is PolicyOutcome.DENIED_SCOPE


@pytest.mark.parametrize(
    "status",
    (SensitivityStatus.UNASSESSED, SensitivityStatus.RESTRICTED),
)
def test_non_clear_sensitivity_fails_closed(status: SensitivityStatus) -> None:
    """Catches missing or restricted classification being treated as safe."""
    decision = MemoryPolicy().evaluate(
        _draft(sensitivity=SensitivityAssessment(status=status)),
        MemoryConsentSettings(),
        context=MemoryOperationContext.ORDINARY,
        last_proactive_prompt_at=None,
        last_declined_at=None,
        now=NOW,
    )

    assert decision.allowed is False
    assert decision.outcome is PolicyOutcome.SUPPRESSED_SENSITIVITY


@pytest.mark.parametrize("flag", tuple(MemorySensitivityFlag))
def test_every_restricted_flag_is_suppressed(flag: MemorySensitivityFlag) -> None:
    """Catches any restricted financial or personal flag bypassing suppression."""
    decision = MemoryPolicy().evaluate(
        _draft(
            sensitivity=SensitivityAssessment(
                status=SensitivityStatus.RESTRICTED,
                flags=frozenset({flag}),
            )
        ),
        MemoryConsentSettings(),
        context=MemoryOperationContext.ORDINARY,
        last_proactive_prompt_at=None,
        last_declined_at=None,
        now=NOW,
    )

    assert decision.allowed is False
    assert decision.outcome is PolicyOutcome.SUPPRESSED_SENSITIVITY


@pytest.mark.parametrize(
    "context",
    (
        MemoryOperationContext.BROKER,
        MemoryOperationContext.EXPORT,
        MemoryOperationContext.RESTRICTED_FINANCIAL,
    ),
)
def test_every_restricted_operation_context_is_suppressed(
    context: MemoryOperationContext,
) -> None:
    """Catches broker, export, or restricted-financial flows creating memory state."""
    decision = MemoryPolicy().evaluate(
        _draft(),
        MemoryConsentSettings(),
        context=context,
        last_proactive_prompt_at=None,
        last_declined_at=None,
        now=NOW,
    )

    assert decision.allowed is False
    assert decision.outcome is PolicyOutcome.SUPPRESSED_CONTEXT


SAVED_DECISION_PREFLIGHT_CASES = (
    (
        SensitivityAssessment(status=SensitivityStatus.UNASSESSED),
        MemoryOperationContext.ORDINARY,
    ),
    (
        SensitivityAssessment(status=SensitivityStatus.RESTRICTED),
        MemoryOperationContext.ORDINARY,
    ),
    *tuple(
        (
            SensitivityAssessment(
                status=SensitivityStatus.RESTRICTED,
                flags=frozenset({flag}),
            ),
            MemoryOperationContext.ORDINARY,
        )
        for flag in MemorySensitivityFlag
    ),
    *tuple(
        (
            SensitivityAssessment(status=SensitivityStatus.CLEAR),
            context,
        )
        for context in (
            MemoryOperationContext.BROKER,
            MemoryOperationContext.EXPORT,
            MemoryOperationContext.RESTRICTED_FINANCIAL,
        )
    ),
)


@pytest.mark.parametrize(
    ("sensitivity", "context"),
    SAVED_DECISION_PREFLIGHT_CASES,
)
def test_saved_decision_public_path_denies_before_every_dependency(
    sensitivity: SensitivityAssessment,
    context: MemoryOperationContext,
) -> None:
    """Catches saved-decision helpers that invent safe classification or context."""
    service = _exploding_service()

    result = service.propose_saved_decision(
        _subject(),
        _saved_decision_source(),
        sensitivity=sensitivity,
        context=context,
    )

    assert result is None


def test_forbidden_category_is_denied_before_every_dependency() -> None:
    """Catches category allowlist checks that happen after stateful dependencies."""
    policy = MemoryPolicy(
        allowed_categories=frozenset({MemoryCategory.WORKFLOW_PREFERENCE})
    )
    service = _exploding_service(policy=policy)

    result = service.propose(
        _subject(),
        _draft(category=MemoryCategory.PERSONALIZATION_PREFERENCE),
        MemoryOperationContext.ORDINARY,
    )

    assert result is None


def test_enable_rejects_empty_scope_without_changing_settings() -> None:
    """Catches empty consent being persisted as enabled or interpreted as all."""
    store = InMemoryCanonicalMemoryStore()
    service = _service(store)
    subject = _subject()
    owner = require_registered(subject)

    with pytest.raises(ValueError, match="at least one category"):
        service.enable(subject, frozenset())

    assert store.get_settings(owner) == MemoryConsentSettings()


def test_enable_rejects_categories_outside_policy_without_mutation() -> None:
    """Catches enablement that persists a category outside the active allowlist."""
    store = InMemoryCanonicalMemoryStore()
    policy = MemoryPolicy(
        allowed_categories=frozenset({MemoryCategory.WORKFLOW_PREFERENCE})
    )
    service = _service(store, policy=policy)
    subject = _subject()
    owner = require_registered(subject)
    service.enable(
        subject,
        frozenset({MemoryCategory.WORKFLOW_PREFERENCE}),
    )
    before = store.get_settings(owner).model_dump_json()

    with pytest.raises(ValueError, match="outside the active allowlist"):
        service.enable(
            subject,
            frozenset({MemoryCategory.PERSONALIZATION_PREFERENCE}),
        )

    assert store.get_settings(owner).model_dump_json() == before


def test_enable_unions_only_the_explicitly_named_categories() -> None:
    """Catches scope extension that enables categories the user did not name."""
    store = InMemoryCanonicalMemoryStore()
    service = _service(store)
    subject = _subject()

    first = service.enable(
        subject,
        frozenset({MemoryCategory.WORKFLOW_PREFERENCE}),
    )
    second = service.enable(
        subject,
        frozenset({MemoryCategory.PAST_SESSION_ANCHOR}),
    )

    assert first.enabled_categories == frozenset({MemoryCategory.WORKFLOW_PREFERENCE})
    assert second.enabled_categories == frozenset(
        {
            MemoryCategory.WORKFLOW_PREFERENCE,
            MemoryCategory.PAST_SESSION_ANCHOR,
        }
    )
    assert MemoryCategory.PERSONALIZATION_PREFERENCE not in second.enabled_categories
    assert MemoryCategory.EXPLICIT_DECISION_NOTE not in second.enabled_categories


def test_suppression_creates_no_candidate_record_or_prompt_history() -> None:
    """Catches a suppressed proposal leaving hidden memory or nag state behind."""
    store = InMemoryCanonicalMemoryStore()

    def explode_id() -> str:
        raise AssertionError("suppression must not allocate a candidate id")

    service = MemoryService(
        store=store,
        config=MemoryServiceConfig(available=True),
        clock=lambda: NOW,
        id_factory=explode_id,
    )
    subject = _subject()
    owner = require_registered(subject)

    result = service.propose(
        subject,
        _draft(
            sensitivity=SensitivityAssessment(
                status=SensitivityStatus.RESTRICTED,
                flags=frozenset({MemorySensitivityFlag.ACCOUNT_BALANCE}),
            )
        ),
        MemoryOperationContext.ORDINARY,
    )

    assert result is None
    assert store.list_candidates(owner) == ()
    assert store.list_records(owner) == ()
    assert store.list_consent_receipts(owner) == ()
    assert (
        store.last_proactive_prompt_at(
            owner,
            MemoryCategory.EXPLICIT_DECISION_NOTE,
        )
        is None
    )
    assert (
        store.last_declined_at(
            owner,
            MemoryCategory.EXPLICIT_DECISION_NOTE,
        )
        is None
    )


def test_explicit_request_bypasses_service_prompt_and_decline_cooldowns() -> None:
    """Catches direct user intent being blocked by proactive anti-nag history."""
    store = InMemoryCanonicalMemoryStore()
    service = _service(store)
    subject = _subject()
    owner = require_registered(subject)
    category = MemoryCategory.WORKFLOW_PREFERENCE
    store.mark_proactive_prompt(owner, category, RECENT)
    store.mark_declined(owner, category, RECENT)

    result = service.propose(
        subject,
        _draft(
            category=category,
            trigger=MemoryProposalTrigger.EXPLICIT_REQUEST,
        ),
        MemoryOperationContext.ORDINARY,
    )

    assert result is not None
    assert result.candidate.opt_in_scope == frozenset({category})
    assert store.get_candidate(owner, result.candidate.id) == result.candidate


def test_confirmation_rechecks_current_context_before_record_creation() -> None:
    """Catches a safe proposal being stored after confirmation enters broker context."""
    store = InMemoryCanonicalMemoryStore()
    service = _service(store)
    subject = _subject()
    owner = require_registered(subject)
    proposal = service.propose(
        subject,
        _draft(trigger=MemoryProposalTrigger.EXPLICIT_REQUEST),
        MemoryOperationContext.ORDINARY,
    )
    assert proposal is not None

    confirmation = service.confirm(
        subject,
        proposal.candidate.id,
        sensitivity=_clear_sensitivity(),
        context=MemoryOperationContext.BROKER,
    )

    assert confirmation.created is False
    assert store.get_candidate(owner, proposal.candidate.id) == proposal.candidate
    assert store.list_records(owner) == ()
    assert store.list_consent_receipts(owner) == ()
    assert store.enabled_categories(owner) == frozenset()


@pytest.mark.parametrize(
    "current_sensitivity",
    (
        SensitivityAssessment(status=SensitivityStatus.UNASSESSED),
        SensitivityAssessment(
            status=SensitivityStatus.RESTRICTED,
            flags=frozenset({MemorySensitivityFlag.EXACT_HOLDINGS}),
        ),
    ),
)
def test_confirmation_requires_current_clear_sensitivity(
    current_sensitivity: SensitivityAssessment,
) -> None:
    """Catches confirmation trusting a stale clear-at-proposal assessment."""
    store = InMemoryCanonicalMemoryStore()
    subject = _subject()
    owner = require_registered(subject)
    generated = iter(("candidate-current-sensitivity",))

    def id_factory() -> str:
        try:
            return next(generated)
        except StopIteration as error:
            raise AssertionError(
                "restricted confirmation must not allocate consent or record ids"
            ) from error

    service = MemoryService(
        store=store,
        config=MemoryServiceConfig(available=True),
        clock=lambda: NOW,
        id_factory=id_factory,
    )
    proposal = service.propose(
        subject,
        _draft(trigger=MemoryProposalTrigger.EXPLICIT_REQUEST),
        MemoryOperationContext.ORDINARY,
    )
    assert proposal is not None

    confirmation = service.confirm(
        subject,
        proposal.candidate.id,
        sensitivity=current_sensitivity,
        context=MemoryOperationContext.ORDINARY,
    )

    assert confirmation.created is False
    assert store.get_candidate(owner, proposal.candidate.id) == proposal.candidate
    assert store.list_records(owner) == ()
    assert store.list_consent_receipts(owner) == ()
    assert store.enabled_categories(owner) == frozenset()


def test_confirmation_rechecks_scope_and_candidate_expiry() -> None:
    """Catches stale or newly descoped candidates becoming durable records."""
    store = InMemoryCanonicalMemoryStore()
    subject = _subject()
    owner = require_registered(subject)
    service = _service(store)
    service.enable(
        subject,
        frozenset({MemoryCategory.WORKFLOW_PREFERENCE}),
    )
    proposal = service.propose(
        subject,
        _draft(
            category=MemoryCategory.WORKFLOW_PREFERENCE,
            trigger=MemoryProposalTrigger.ASSISTED_STABLE_PREFERENCE,
        ),
        MemoryOperationContext.ORDINARY,
    )
    assert proposal is not None
    store.set_settings(owner, MemoryConsentSettings())

    descoped = service.confirm(
        subject,
        proposal.candidate.id,
        sensitivity=_clear_sensitivity(),
        context=MemoryOperationContext.ORDINARY,
    )

    assert descoped.created is False
    assert store.list_records(owner) == ()

    stale_service = _service(store, now=NOW + timedelta(days=2))
    stale_proposal_service = _service(store)
    stale = stale_proposal_service.propose(
        subject,
        _draft(trigger=MemoryProposalTrigger.EXPLICIT_REQUEST),
        MemoryOperationContext.ORDINARY,
    )
    assert stale is not None

    expired = stale_service.confirm(
        subject,
        stale.candidate.id,
        sensitivity=_clear_sensitivity(),
        context=MemoryOperationContext.ORDINARY,
    )

    assert expired.created is False
    assert store.get_candidate(owner, stale.candidate.id) is None
    assert store.list_records(owner) == ()


def test_candidate_and_prompt_history_roll_back_on_injected_write_failure() -> None:
    """Catches candidate creation surviving a failed proactive-history write."""
    store = InMemoryCanonicalMemoryStore()
    owner = RegisteredMemoryOwner(owner_id=OWNER_ID)
    store._proactive_prompts = _ExplodingWriteDict()

    with pytest.raises(RuntimeError, match="injected history write failure"):
        store.add_candidate_with_prompt(
            owner,
            _candidate(),
            proactive_prompt_at=NOW,
            expected_history=_empty_history(),
        )

    assert store.list_candidates(owner) == ()


def test_candidate_validation_failure_creates_no_candidate_or_prompt() -> None:
    """Catches an invalid candidate contract partially entering canonical state."""
    store = InMemoryCanonicalMemoryStore()
    owner = RegisteredMemoryOwner(owner_id=OWNER_ID)
    invalid = _candidate().model_copy(update={"trigger": "invalid-trigger"})

    with pytest.raises(ValueError):
        store.add_candidate_with_prompt(
            owner,
            invalid,
            proactive_prompt_at=NOW,
            expected_history=_empty_history(),
        )

    assert store.list_candidates(owner) == ()
    assert (
        store.last_proactive_prompt_at(
            owner,
            MemoryCategory.EXPLICIT_DECISION_NOTE,
        )
        is None
    )


def test_candidate_and_prompt_history_are_one_race_safe_transition() -> None:
    """Catches concurrent proposals producing duplicate or half-written state."""
    store = InMemoryCanonicalMemoryStore()
    owner = RegisteredMemoryOwner(owner_id=OWNER_ID)
    candidate = _candidate()
    barrier = Barrier(2)

    def attempt() -> bool:
        barrier.wait()
        try:
            store.add_candidate_with_prompt(
                owner,
                candidate,
                proactive_prompt_at=NOW,
                expected_history=_empty_history(),
            )
        except ValueError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(lambda _: attempt(), range(2)))

    assert sorted(results) == [False, True]
    assert store.list_candidates(owner) == (candidate,)
    assert (
        store.last_proactive_prompt_at(
            owner,
            MemoryCategory.EXPLICIT_DECISION_NOTE,
        )
        == NOW
    )


def test_concurrent_proactive_proposals_admit_only_one_distinct_candidate() -> None:
    """Catches two stale policy snapshots both entering the proactive cooldown."""
    store = _BarrierHistoryStore()

    def service(candidate_id: str) -> MemoryService:
        return MemoryService(
            store=store,
            config=MemoryServiceConfig(available=True),
            clock=lambda: NOW,
            id_factory=lambda: candidate_id,
        )

    services = (service("candidate-race-a"), service("candidate-race-b"))

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            executor.map(
                lambda memory_service: memory_service.propose(
                    _subject(),
                    _draft(),
                    MemoryOperationContext.ORDINARY,
                ),
                services,
            )
        )

    assert sum(result is not None for result in results) == 1
    candidates = store.list_candidates(require_registered(_subject()))
    assert len(candidates) == 1
    assert candidates[0].id in {"candidate-race-a", "candidate-race-b"}
    assert (
        store.last_proactive_prompt_at(
            require_registered(_subject()),
            MemoryCategory.EXPLICIT_DECISION_NOTE,
        )
        == NOW
    )


def test_concurrent_explicit_requests_bypass_proactive_history_admission() -> None:
    """Catches proactive history CAS being applied to direct user intent."""
    store = _BarrierHistoryStore()

    def service(candidate_id: str) -> MemoryService:
        return MemoryService(
            store=store,
            config=MemoryServiceConfig(available=True),
            clock=lambda: NOW,
            id_factory=lambda: candidate_id,
        )

    services = (service("candidate-explicit-a"), service("candidate-explicit-b"))

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            executor.map(
                lambda memory_service: memory_service.propose(
                    _subject(),
                    _draft(trigger=MemoryProposalTrigger.EXPLICIT_REQUEST),
                    MemoryOperationContext.ORDINARY,
                ),
                services,
            )
        )

    assert all(result is not None for result in results)
    assert {
        candidate.id
        for candidate in store.list_candidates(require_registered(_subject()))
    } == {"candidate-explicit-a", "candidate-explicit-b"}
    assert (
        store.last_proactive_prompt_at(
            require_registered(_subject()),
            MemoryCategory.EXPLICIT_DECISION_NOTE,
        )
        is None
    )


def test_candidate_and_decline_history_roll_back_on_injected_failure() -> None:
    """Catches candidate consumption surviving a failed decline-history write."""
    store = InMemoryCanonicalMemoryStore()
    owner = RegisteredMemoryOwner(owner_id=OWNER_ID)
    candidate = _candidate()
    store.add_candidate_with_prompt(
        owner,
        candidate,
        proactive_prompt_at=NOW,
        expected_history=_empty_history(),
    )
    store._declines = _ExplodingWriteDict()

    with pytest.raises(RuntimeError, match="injected history write failure"):
        store.decline_candidate_with_history(
            owner,
            candidate.id,
            declined_at=NOW,
        )

    assert store.get_candidate(owner, candidate.id) == candidate


def test_candidate_consumption_and_decline_history_are_race_safe() -> None:
    """Catches concurrent declines recording history without one consumption."""
    store = InMemoryCanonicalMemoryStore()
    owner = RegisteredMemoryOwner(owner_id=OWNER_ID)
    candidate = _candidate()
    store.add_candidate_with_prompt(
        owner,
        candidate,
        proactive_prompt_at=NOW,
        expected_history=_empty_history(),
    )
    barrier = Barrier(2)

    def attempt() -> bool:
        barrier.wait()
        return store.decline_candidate_with_history(
            owner,
            candidate.id,
            declined_at=NOW,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(lambda _: attempt(), range(2)))

    assert sorted(results) == [False, True]
    assert store.get_candidate(owner, candidate.id) is None
    assert (
        store.last_declined_at(
            owner,
            MemoryCategory.EXPLICIT_DECISION_NOTE,
        )
        == NOW
    )
