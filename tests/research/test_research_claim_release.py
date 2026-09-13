"""A failed provider attempt never costs a guest a research question (#609).

Every research provider call a turn claims capacity for runs under
``admitted_provider_work``: a call that returns keeps the claim, and a call
that fails with no usable response gives it back, unless a call earlier in the
turn was served. These tests hold that at the admission scope, in the
process-local twin of the database functions, and at every provider path that
claims. The database functions themselves are proven in
``tests/test_research_allowance_postgres.py``.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from argus.api import state as api_state
from argus.api.chat import research_evidence as evidence
from argus.domain.research.admission import (
    ResearchAttemptAdmission,
    admitted_provider_work,
    claim_current_research_attempt,
    research_attempt_admission_context,
)
from argus.domain.research.contracts import ResearchUnavailableError
from argus.domain.usage_limits import (
    GLOBAL_RESEARCH_CEILING_SUBJECT,
    GUEST_RESEARCH_ALLOWANCE,
    read_memory_usage,
)

GUEST = "visitor:release-guest"
QUESTION = "What is Apple trading at right now?"
ADMITTED = ResearchAttemptAdmission(
    available=True, period_start="2026-09-13T00:00:00+00:00"
)


class _Turn:
    """The API's claim and release for one turn, recorded."""

    def __init__(self, admission: ResearchAttemptAdmission = ADMITTED) -> None:
        self.admission = admission
        self.claims = 0
        self.released: list[ResearchAttemptAdmission] = []

    def claim(self) -> ResearchAttemptAdmission:
        self.claims += 1
        return self.admission

    def release(self, admission: ResearchAttemptAdmission) -> None:
        self.released.append(admission)

    def scope(self):
        return research_attempt_admission_context(self.claim, release=self.release)


class _ProviderDown(Exception):
    pass


# --- The admission scope ------------------------------------------------------


def test_a_failed_call_gives_its_claim_back_and_the_next_path_claims_again() -> None:
    turn = _Turn()
    with turn.scope():
        claim_current_research_attempt()
        with pytest.raises(_ProviderDown), admitted_provider_work():
            raise _ProviderDown
        assert turn.released == [ADMITTED]
        claim_current_research_attempt()
    assert turn.claims == 2


def test_a_served_call_keeps_the_claim_when_a_later_call_fails() -> None:
    turn = _Turn()
    with turn.scope():
        claim_current_research_attempt()
        with admitted_provider_work():
            pass
        with pytest.raises(_ProviderDown), admitted_provider_work():
            raise _ProviderDown
    assert turn.released == []
    assert turn.claims == 1


def test_a_refused_claim_has_nothing_to_give_back() -> None:
    turn = _Turn(ResearchAttemptAdmission(available=False, guest_exhausted=True))
    with turn.scope():
        claim_current_research_attempt()
        with pytest.raises(_ProviderDown), admitted_provider_work():
            raise _ProviderDown
    assert turn.released == []


def test_provider_work_with_no_claim_gives_nothing_back() -> None:
    with pytest.raises(_ProviderDown), admitted_provider_work():
        raise _ProviderDown
    turn = _Turn()
    with turn.scope():
        with pytest.raises(_ProviderDown), admitted_provider_work():
            raise _ProviderDown
    assert turn.released == []
    assert turn.claims == 0


# --- The process-local twin of the database functions ------------------------


@pytest.fixture
def guest_store(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    api_state.store.usage_counters.clear()
    api_state.store.visitor_usage_counters.clear()
    yield api_state.store
    api_state.store.usage_counters.clear()
    api_state.store.visitor_usage_counters.clear()


def _guest_used() -> int:
    row = api_state.store.visitor_usage_counters.get(
        (GUEST, evidence.RESEARCH_USAGE_RESOURCE, "day")
    )
    return int(row["used_count"]) if row else 0


def _ceiling_used() -> int:
    row = read_memory_usage(
        api_state.store.usage_counters,
        user_id=GLOBAL_RESEARCH_CEILING_SUBJECT,
        resource=evidence.RESEARCH_USAGE_RESOURCE,
        period="day",
    )
    return int(row["used_count"]) if row else 0


def test_a_release_gives_the_guest_question_back_and_keeps_the_ceiling(
    guest_store,
) -> None:
    admission = evidence.claim_research_provider_attempt(guest_visitor_key=GUEST)
    assert admission.available
    assert admission.period_start
    assert (_guest_used(), _ceiling_used()) == (1, 1)

    evidence.release_research_provider_claim(admission, guest_visitor_key=GUEST)
    assert (_guest_used(), _ceiling_used()) == (0, 1)

    evidence.release_research_provider_claim(admission, guest_visitor_key=GUEST)
    assert _guest_used() == 0


def test_a_released_question_can_be_asked_again_at_the_daily_limit(guest_store) -> None:
    claims = [
        evidence.claim_research_provider_attempt(guest_visitor_key=GUEST)
        for _ in range(GUEST_RESEARCH_ALLOWANCE)
    ]
    assert all(claim.available for claim in claims)
    assert evidence.claim_research_provider_attempt(
        guest_visitor_key=GUEST
    ).guest_exhausted

    evidence.release_research_provider_claim(claims[-1], guest_visitor_key=GUEST)

    assert evidence.claim_research_provider_attempt(guest_visitor_key=GUEST).available


def test_a_release_returns_only_the_day_the_claim_charged(guest_store) -> None:
    admission = evidence.claim_research_provider_attempt(guest_visitor_key=GUEST)
    day_before = datetime.fromisoformat(admission.period_start) - timedelta(days=1)

    evidence.release_research_provider_claim(
        ResearchAttemptAdmission(available=True, period_start=day_before.isoformat()),
        guest_visitor_key=GUEST,
    )

    assert _guest_used() == 1


def test_a_signed_in_claim_has_no_guest_question_to_return(guest_store) -> None:
    admission = evidence.claim_research_provider_attempt(guest_visitor_key=None)

    evidence.release_research_provider_claim(admission, guest_visitor_key=None)

    assert _ceiling_used() == 1


def test_the_database_claim_and_release_carry_the_charged_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict]] = []

    class _Client:
        def rpc(self, name: str, params: dict):
            calls.append((name, params))
            data = (
                {"available": True, "guest_exhausted": False, "period_start": ADMITTED.period_start}
                if name == "claim_research_usage"
                else {"released": True}
            )
            return SimpleNamespace(execute=lambda: SimpleNamespace(data=data))

    monkeypatch.setattr(api_state, "supabase_gateway", SimpleNamespace(client=_Client()))

    admission = evidence.claim_research_provider_attempt(guest_visitor_key=GUEST)
    evidence.release_research_provider_claim(admission, guest_visitor_key=GUEST)

    assert admission == ADMITTED
    assert calls[-1] == (
        "release_research_usage",
        {
            "p_guest_visitor_key": GUEST,
            "p_resource": evidence.RESEARCH_USAGE_RESOURCE,
            "p_global_visitor_key": evidence.GLOBAL_CEILING_KEY,
            "p_period_start": ADMITTED.period_start,
        },
    )


def test_a_release_that_cannot_be_written_leaves_the_charge_and_never_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Down:
        def rpc(self, *_args, **_kwargs):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(api_state, "supabase_gateway", SimpleNamespace(client=_Down()))

    evidence.release_research_provider_claim(ADMITTED, guest_visitor_key=GUEST)


# --- Every provider path that claims gives the claim back when it fails ------


def _inline_research(monkeypatch: pytest.MonkeyPatch) -> None:
    from argus.agent_runtime import research_grounded as grounded

    from tests.research.conftest import run_research_turn, set_research_query

    class _Down:
        def run_research(self, prompt, spec):
            raise ResearchUnavailableError("http_error", "http 503", status=503)

    set_research_query(
        monkeypatch, globals(), question_kind="live_quote", symbols=["AAPL"]
    )
    monkeypatch.setattr(grounded, "_client", lambda: _Down())
    result = run_research_turn(QUESTION)
    assert result is not None
    assert result.stage_patch["recovery"]["code"] == "research_lookup_failed"


def _thorough_submission(monkeypatch: pytest.MonkeyPatch) -> None:
    from argus.api.chat import research_jobs

    from tests.research.test_research_jobs import _job_request, _JobGateway

    class _Down:
        def submit_background(self, prompt, spec):
            raise ResearchUnavailableError("timeout")

    monkeypatch.setattr(api_state, "supabase_gateway", _JobGateway())
    monkeypatch.setattr(research_jobs, "_client", lambda: _Down())
    with pytest.raises(ResearchUnavailableError):
        research_jobs.start_research_job(
            job_request=_job_request(),
            user_id="u1",
            conversation_id="c1",
            request_message_id="m1",
            request_id="r1",
        )


def _thorough_synchronous_run(monkeypatch: pytest.MonkeyPatch) -> None:
    from argus.api.chat import research_jobs

    from tests.research.test_research_jobs import _job_request

    class _Down:
        def run_research(self, prompt, spec):
            raise ResearchUnavailableError("malformed_response")

    monkeypatch.setattr(api_state, "supabase_gateway", None)
    monkeypatch.setattr(research_jobs, "_client", lambda: _Down())
    with pytest.raises(ResearchUnavailableError):
        research_jobs.start_research_job(
            job_request=_job_request(),
            user_id="u1",
            conversation_id="c1",
            request_message_id="m1",
            request_id="r1",
        )


def _result_follow_up(monkeypatch: pytest.MonkeyPatch) -> None:
    from argus.agent_runtime import result_conversation as conversation

    class _Down:
        def run_structured(self, *_args, **_kwargs):
            raise ResearchUnavailableError("http_error", "http 500", status=500)

    answer = asyncio.run(
        conversation._research_answer(
            "Why did it fall so much?",
            schema=conversation.ResultConversationDraft,
            facts={},
            language="en",
            test_kinds=(),
            client=_Down(),
        )
    )
    assert answer.text is None


def _result_breakdown(monkeypatch: pytest.MonkeyPatch) -> None:
    from argus.api.chat import breakdown

    from tests.test_backtest_message_projection import _completed_run

    class _Down:
        def run_structured(self, *_args, **_kwargs):
            raise ResearchUnavailableError("timeout")

    monkeypatch.setattr(breakdown, "_client", lambda: _Down())
    monkeypatch.setattr(
        api_state,
        "supabase_gateway",
        SimpleNamespace(create_cost_ledger_entry=lambda *, entry: None),
    )
    run = _completed_run()
    result = breakdown.result_breakdown_action(
        run,
        language="en",
        user_id="owner",
        conversation_id=run.conversation_id,
        request_id="request",
    )
    assert result.fallback_used


def _discovery_search(monkeypatch: pytest.MonkeyPatch) -> None:
    from argus.agent_runtime.discovery import composer
    from argus.domain.research.search import SearchUnavailableError

    from tests.agent_runtime.discovery.test_discovery_composer import (
        _decision,
        _extraction,
        _FakeProvider,
        _wire,
    )

    monkeypatch.setenv("ARGUS_GROUNDED_DISCOVERY_ENABLED", "true")
    _wire(
        monkeypatch,
        provider=_FakeProvider(SearchUnavailableError(reason="timeout")),
        extraction=_extraction(),
    )
    decision = _decision()
    result = asyncio.run(
        composer.discovery_operation_result(
            decision=decision,
            request=decision.asset_discovery,
            current_user_message="What cybersecurity stocks could I test?",
            language="en",
            provider_admission=claim_current_research_attempt,
        )
    )
    assert result is not None
    assert result.stage_patch["recovery"]["code"] == "discovery_search_failed"


CLAIMED_PROVIDER_PATHS = {
    "inline_research": _inline_research,
    "thorough_submission": _thorough_submission,
    "thorough_synchronous_run": _thorough_synchronous_run,
    "result_follow_up": _result_follow_up,
    "result_breakdown": _result_breakdown,
    "discovery_search": _discovery_search,
}


@pytest.mark.parametrize("path", sorted(CLAIMED_PROVIDER_PATHS))
def test_every_claimed_provider_path_gives_the_claim_back_when_it_fails(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    turn = _Turn()

    with turn.scope():
        CLAIMED_PROVIDER_PATHS[path](monkeypatch)

    assert turn.claims == 1
    assert turn.released == [ADMITTED]


def test_a_served_research_turn_keeps_its_claim(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.research.conftest import (
        agent_response,
        run_research_turn,
        set_research_query,
        wire_grounded_client,
    )

    set_research_query(
        monkeypatch, globals(), question_kind="live_quote", symbols=["AAPL"]
    )
    wire_grounded_client(monkeypatch, [agent_response()])
    turn = _Turn()

    with turn.scope():
        result = run_research_turn(QUESTION)

    assert result is not None
    assert "recovery" not in result.stage_patch
    assert turn.claims == 1
    assert turn.released == []
