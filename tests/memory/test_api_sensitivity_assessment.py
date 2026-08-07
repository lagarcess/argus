"""Backend sensitivity assessment owns storage eligibility at the API.

Clients cannot claim a status (contract 422s any attempt, covered elsewhere);
here we prove the assessor is the only path in: clear verdicts store, any
flagged or restricted verdict suppresses before a candidate write, the two
never-storable flags block even when claimed alongside "clear", and every
failure mode fails closed without touching the service.
"""

from __future__ import annotations

from typing import cast

import pytest
from api_matrix import ENDPOINT_CALLS
from argus.api.personalization_memory import configure_memory_service
from argus.api.personalization_memory_assessor import (
    NEVER_STORABLE_FLAGS,
    configure_sensitivity_classifier,
)
from argus.llm.memory_sensitivity import MemorySensitivityVerdict
from argus.memory.service import MemoryService
from argus.memory.store import InMemoryCanonicalMemoryStore

PROPOSE_PAYLOAD = {
    "category": "workflow_preference",
    "value": "Show assumptions before results.",
    "label": "Assumptions first",
    "future_benefit": "Argus can keep the preferred review order.",
    "provenance": [
        {
            "source_kind": "message",
            "source_id": "message-1",
            "source_version": "1",
        }
    ],
}


class _ExplodingMemoryService:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"MemoryService.{name} must not be touched")


class _RejectingCandidateWriteStore(InMemoryCanonicalMemoryStore):
    def add_candidate_with_prompt(self, *args: object, **kwargs: object) -> bool:
        raise AssertionError("suppressed proposals must not reach candidate storage")


def _clear_verdict(_content: str) -> MemorySensitivityVerdict:
    return MemorySensitivityVerdict(status="clear")


def _configure_live_service(
    store: InMemoryCanonicalMemoryStore | None = None,
) -> MemoryService:
    service = MemoryService(store=store or InMemoryCanonicalMemoryStore())
    configure_memory_service(service)
    return service


@pytest.fixture
def flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", "true")


def test_clear_verdict_lets_propose_confirm_and_edit_work(
    memory_api,
    flag_on,
) -> None:
    _configure_live_service()
    configure_sensitivity_classifier(_clear_verdict)
    headers = memory_api.registered_headers
    client = memory_api.client

    enabled = client.post(
        "/api/v1/memory/enable",
        json={"categories": ["workflow_preference"]},
        headers=headers,
    )
    assert enabled.status_code == 200, enabled.text

    proposed = client.post(
        "/api/v1/memory/candidates",
        json=PROPOSE_PAYLOAD,
        headers=headers,
    )
    assert proposed.status_code == 200, proposed.text
    assert proposed.json()["created"] is True
    candidate = proposed.json()["candidate"]
    assert candidate["sensitivity"] == {"status": "clear", "flags": []}

    confirmed = client.post(
        f"/api/v1/memory/candidates/{candidate['id']}/confirm",
        json={},
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["created"] is True
    record_id = confirmed.json()["record"]["id"]

    edited = client.patch(
        f"/api/v1/memory/records/{record_id}",
        json={"label": "Assumptions first, always"},
        headers=headers,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["changed"] is True
    assert edited.json()["record"]["revision"] == 2


def test_restricted_verdict_suppresses_before_candidate_storage(
    memory_api,
    flag_on,
) -> None:
    _configure_live_service(store=_RejectingCandidateWriteStore())
    configure_sensitivity_classifier(
        lambda _content: MemorySensitivityVerdict(
            status="restricted",
            flags=["account_balance"],
        )
    )
    headers = memory_api.registered_headers

    enabled = memory_api.client.post(
        "/api/v1/memory/enable",
        json={"categories": ["workflow_preference"]},
        headers=headers,
    )
    assert enabled.status_code == 200, enabled.text

    proposed = memory_api.client.post(
        "/api/v1/memory/candidates",
        json=PROPOSE_PAYLOAD,
        headers=headers,
    )
    assert proposed.status_code == 200, proposed.text
    assert proposed.json() == {"created": False, "candidate": None}


@pytest.mark.parametrize("flag", sorted(flag.value for flag in NEVER_STORABLE_FLAGS))
def test_never_storable_flags_block_even_when_claimed_clear(
    memory_api,
    flag_on,
    flag: str,
) -> None:
    """An adversarial classifier claiming clear alongside a never-storable
    flag must still be forced into restriction and suppressed."""
    _configure_live_service(store=_RejectingCandidateWriteStore())
    configure_sensitivity_classifier(
        lambda _content: MemorySensitivityVerdict(status="clear", flags=[flag])
    )
    headers = memory_api.registered_headers

    for path in (
        "/api/v1/memory/candidates",
        "/api/v1/memory/candidates/saved-decision",
    ):
        payload = (
            PROPOSE_PAYLOAD
            if path.endswith("candidates")
            else {
                "label": "Keep the lower-drawdown version",
                "value": "The user rejected the higher-drawdown version.",
                "provenance": {
                    "source_kind": "decision_note",
                    "source_id": "decision-note-1",
                    "source_version": "1",
                },
            }
        )
        response = memory_api.client.post(path, json=payload, headers=headers)
        assert response.status_code == 200, (path, response.text)
        assert response.json() == {"created": False, "candidate": None}

    records = memory_api.client.get("/api/v1/memory/records", headers=headers)
    assert records.json() == {"records": []}


def test_classifier_unavailable_fails_closed_without_touching_the_service(
    memory_api,
    flag_on,
) -> None:
    configure_memory_service(cast(MemoryService, _ExplodingMemoryService()))
    configure_sensitivity_classifier(lambda _content: None)

    response = memory_api.client.post(
        "/api/v1/memory/candidates",
        json=PROPOSE_PAYLOAD,
        headers=memory_api.registered_headers,
    )
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "memory_assessment_unavailable"


def test_classifier_exception_fails_closed_without_touching_the_service(
    memory_api,
    flag_on,
) -> None:
    def _raising(_content: str) -> MemorySensitivityVerdict:
        raise TimeoutError("classifier timed out")

    configure_memory_service(cast(MemoryService, _ExplodingMemoryService()))
    configure_sensitivity_classifier(_raising)

    response = memory_api.client.post(
        "/api/v1/memory/candidates",
        json=PROPOSE_PAYLOAD,
        headers=memory_api.registered_headers,
    )
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "memory_assessment_unavailable"


def test_default_classifier_without_api_key_fails_closed(
    memory_api,
    flag_on,
) -> None:
    """The real OpenRouter classifier skips without a key; storage stays
    unreachable rather than open."""
    configure_memory_service(cast(MemoryService, _ExplodingMemoryService()))

    response = memory_api.client.post(
        "/api/v1/memory/candidates",
        json=PROPOSE_PAYLOAD,
        headers=memory_api.registered_headers,
    )
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "memory_assessment_unavailable"


def test_edit_with_restricted_content_is_rejected_and_record_unchanged(
    memory_api,
    flag_on,
) -> None:
    _configure_live_service()
    configure_sensitivity_classifier(_clear_verdict)
    headers = memory_api.registered_headers
    client = memory_api.client

    client.post(
        "/api/v1/memory/enable",
        json={"categories": ["workflow_preference"]},
        headers=headers,
    )
    candidate = client.post(
        "/api/v1/memory/candidates",
        json=PROPOSE_PAYLOAD,
        headers=headers,
    ).json()["candidate"]
    record_id = client.post(
        f"/api/v1/memory/candidates/{candidate['id']}/confirm",
        json={},
        headers=headers,
    ).json()["record"]["id"]

    configure_sensitivity_classifier(
        lambda _content: MemorySensitivityVerdict(
            status="restricted",
            flags=["account_balance"],
        )
    )
    rejected = client.patch(
        f"/api/v1/memory/records/{record_id}",
        json={"value": "My balance is 250000."},
        headers=headers,
    )
    assert rejected.status_code == 400, rejected.text
    assert rejected.json()["code"] == "memory_sensitivity_restricted"

    configure_sensitivity_classifier(lambda _content: None)
    unavailable = client.patch(
        f"/api/v1/memory/records/{record_id}",
        json={"label": "Anything"},
        headers=headers,
    )
    assert unavailable.status_code == 503, unavailable.text

    configure_sensitivity_classifier(_clear_verdict)
    records = client.get("/api/v1/memory/records", headers=headers).json()["records"]
    assert records[0]["revision"] == 1
    assert records[0]["value"] == "Show assumptions before results."


def test_guest_denial_still_precedes_assessment(memory_api, flag_on) -> None:
    """The account gate runs before the assessor for every endpoint."""

    def _exploding_classifier(_content: str) -> MemorySensitivityVerdict:
        raise AssertionError("classifier must not run for a guest")

    configure_memory_service(cast(MemoryService, _ExplodingMemoryService()))
    configure_sensitivity_classifier(_exploding_classifier)

    for call in ENDPOINT_CALLS:
        response = memory_api.client.request(
            call.method,
            call.path,
            json=call.json,
            headers=memory_api.guest_headers,
        )
        assert response.status_code == 403, (call.operation, response.text)
