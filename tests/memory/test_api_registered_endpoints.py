"""Registered sessions get the full memory lifecycle; the flag keeps it inert.

The default-off ARGUS_ENABLE_PERSONALIZATION_MEMORY flag and the injected
service are both required before any endpoint reaches the subsystem; with
either missing, an exploding service proves nothing is touched.

Sensitivity is backend truth: requests carry no sensitivity fields, every API
entry is unassessed, and policy suppresses unassessed content before storage.
Stored state therefore enters only through the domain service with a real
clear assessment, standing in for the future backend proposal boundary.
"""

from __future__ import annotations

from typing import cast

import pytest
from api_matrix import ENDPOINT_CALLS, REGISTERED_USER_ID
from argus.api.personalization_memory import configure_memory_service
from argus.memory.contracts import (
    MemoryCandidateDraft,
    MemoryCategory,
    MemoryOperationContext,
    MemoryProposalTrigger,
    MemoryProvenance,
    MemoryRecord,
    MemorySourceKind,
    SensitivityAssessment,
    SensitivityStatus,
)
from argus.memory.service import MemoryService
from argus.memory.store import InMemoryCanonicalMemoryStore
from argus.memory.subject import MemoryAccountKind, MemorySubject

REGISTERED_SUBJECT = MemorySubject(
    owner_id=REGISTERED_USER_ID,
    kind=MemoryAccountKind.REGISTERED,
)


class _ExplodingMemoryService:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"MemoryService.{name} must not be touched")


class _RejectingCandidateWriteStore(InMemoryCanonicalMemoryStore):
    def add_candidate_with_prompt(self, *args: object, **kwargs: object) -> bool:
        raise AssertionError("suppressed proposals must not reach candidate storage")


def _configure_live_service(
    store: InMemoryCanonicalMemoryStore | None = None,
) -> MemoryService:
    service = MemoryService(store=store or InMemoryCanonicalMemoryStore())
    configure_memory_service(service)
    return service


def _clear_assessment() -> SensitivityAssessment:
    return SensitivityAssessment(status=SensitivityStatus.CLEAR)


def _seed_confirmed_record(service: MemoryService) -> MemoryRecord:
    """Store one record the way the future assessed proposal boundary would."""
    proposal = service.propose(
        REGISTERED_SUBJECT,
        _seed_draft("Show assumptions before results.", "Assumptions first"),
        MemoryOperationContext.ORDINARY,
    )
    assert proposal is not None
    confirmation = service.confirm(
        REGISTERED_SUBJECT,
        proposal.candidate.id,
        sensitivity=_clear_assessment(),
        context=MemoryOperationContext.ORDINARY,
    )
    assert confirmation.record is not None
    return confirmation.record


def _seed_draft(value: str, label: str) -> MemoryCandidateDraft:
    return MemoryCandidateDraft(
        category=MemoryCategory.WORKFLOW_PREFERENCE,
        value=value,
        label=label,
        future_benefit="Argus can keep the preferred review order.",
        provenance=(
            MemoryProvenance(
                source_kind=MemorySourceKind.MESSAGE,
                source_id="message-seed",
                source_version="1",
            ),
        ),
        trigger=MemoryProposalTrigger.EXPLICIT_REQUEST,
        sensitivity=_clear_assessment(),
    )


def test_flag_off_keeps_every_endpoint_inert_for_registered_users(
    memory_api,
) -> None:
    configure_memory_service(cast(MemoryService, _ExplodingMemoryService()))

    for call in ENDPOINT_CALLS:
        response = memory_api.client.request(
            call.method,
            call.path,
            json=call.json,
            headers=memory_api.registered_headers,
        )
        assert response.status_code == 404, (call.operation, response.text)
        assert response.json()["code"] == "personalization_memory_unavailable"


def test_flag_on_without_a_wired_service_stays_unavailable(
    memory_api,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", "true")
    configure_memory_service(None)

    for call in ENDPOINT_CALLS:
        response = memory_api.client.request(
            call.method,
            call.path,
            json=call.json,
            headers=memory_api.registered_headers,
        )
        assert response.status_code == 404, (call.operation, response.text)
        assert response.json()["code"] == "personalization_memory_unavailable"


def test_client_sensitivity_claims_are_rejected_by_the_contract(
    memory_api,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No request schema accepts a sensitivity claim in any form."""
    monkeypatch.setenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", "true")
    _configure_live_service()
    headers = memory_api.registered_headers
    claims = (
        {"status": "clear"},
        {"status": "clear", "flags": []},
        {"status": "restricted", "flags": ["account_balance"]},
        {"status": "unassessed"},
    )

    for claim in claims:
        propose = memory_api.client.post(
            "/api/v1/memory/candidates",
            json={
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
                "sensitivity": claim,
            },
            headers=headers,
        )
        assert propose.status_code == 422, propose.text

        saved_decision = memory_api.client.post(
            "/api/v1/memory/candidates/saved-decision",
            json={
                "label": "Keep the lower-drawdown version",
                "value": "The user rejected the higher-drawdown version.",
                "provenance": {
                    "source_kind": "decision_note",
                    "source_id": "decision-note-1",
                    "source_version": "1",
                },
                "sensitivity": claim,
            },
            headers=headers,
        )
        assert saved_decision.status_code == 422, saved_decision.text

        confirm = memory_api.client.post(
            "/api/v1/memory/candidates/candidate-1/confirm",
            json={"sensitivity": claim},
            headers=headers,
        )
        assert confirm.status_code == 422, confirm.text

        edit = memory_api.client.patch(
            "/api/v1/memory/records/record-1",
            json={"label": "New label", "sensitivity": claim},
            headers=headers,
        )
        assert edit.status_code == 422, edit.text


def test_api_proposals_are_suppressed_before_candidate_storage(
    memory_api,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unassessed entries fail closed before any candidate write, even with
    consent enabled, so no API payload can store a candidate at all."""
    monkeypatch.setenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", "true")
    _configure_live_service(store=_RejectingCandidateWriteStore())
    headers = memory_api.registered_headers

    enabled = memory_api.client.post(
        "/api/v1/memory/enable",
        json={"categories": ["workflow_preference", "explicit_decision_note"]},
        headers=headers,
    )
    assert enabled.status_code == 200, enabled.text

    propose = memory_api.client.post(
        "/api/v1/memory/candidates",
        json={
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
        },
        headers=headers,
    )
    assert propose.status_code == 200, propose.text
    assert propose.json() == {"created": False, "candidate": None}

    saved_decision = memory_api.client.post(
        "/api/v1/memory/candidates/saved-decision",
        json={
            "label": "Keep the lower-drawdown version",
            "value": "The user rejected the higher-drawdown version.",
            "provenance": {
                "source_kind": "decision_note",
                "source_id": "decision-note-1",
                "source_version": "1",
            },
        },
        headers=headers,
    )
    assert saved_decision.status_code == 200, saved_decision.text
    assert saved_decision.json() == {"created": False, "candidate": None}


def test_api_confirmation_of_a_pending_candidate_stays_unassessed_and_inert(
    memory_api,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Confirming without a backend assessment cannot mint a record."""
    monkeypatch.setenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", "true")
    service = _configure_live_service()
    headers = memory_api.registered_headers

    service.enable(
        REGISTERED_SUBJECT,
        frozenset({MemoryCategory.WORKFLOW_PREFERENCE}),
    )
    proposal = service.propose(
        REGISTERED_SUBJECT,
        _seed_draft("Show assumptions before results.", "Assumptions first"),
        MemoryOperationContext.ORDINARY,
    )
    assert proposal is not None

    confirmed = memory_api.client.post(
        f"/api/v1/memory/candidates/{proposal.candidate.id}/confirm",
        json={},
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json() == {
        "created": False,
        "record": None,
        "consent_receipt": None,
    }

    records = memory_api.client.get("/api/v1/memory/records", headers=headers)
    assert records.json() == {"records": []}


def test_registered_lifecycle_end_to_end(
    memory_api,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", "true")
    service = _configure_live_service()
    client = memory_api.client
    headers = memory_api.registered_headers

    enabled = client.post(
        "/api/v1/memory/enable",
        json={"categories": ["workflow_preference"]},
        headers=headers,
    )
    assert enabled.status_code == 200, enabled.text
    assert enabled.json() == {
        "enabled": True,
        "enabled_categories": ["workflow_preference"],
    }

    record = _seed_confirmed_record(service)

    records = client.get("/api/v1/memory/records", headers=headers)
    assert records.status_code == 200, records.text
    listed = records.json()["records"]
    assert [item["id"] for item in listed] == [record.id]
    assert "owner_id" not in listed[0]

    explanation = client.get(
        f"/api/v1/memory/records/{record.id}/explanation",
        headers=headers,
    )
    assert explanation.status_code == 200, explanation.text
    assert explanation.json()["record_id"] == record.id
    assert explanation.json()["consent_schema_version"] == "argus.memory-consent/v1"

    missing_explanation = client.get(
        "/api/v1/memory/records/absent-record/explanation",
        headers=headers,
    )
    assert missing_explanation.status_code == 404
    assert missing_explanation.json()["code"] == "not_found"

    retrieved = client.post(
        "/api/v1/memory/retrieval",
        json={"query": "assumptions", "purpose": "inspect_memory"},
        headers=headers,
    )
    assert retrieved.status_code == 200, retrieved.text
    memories = retrieved.json()["memories"]
    assert [memory["record"]["id"] for memory in memories] == [record.id]

    out_of_purpose = client.post(
        "/api/v1/memory/retrieval",
        json={"query": "assumptions", "purpose": "revisit_saved_decision"},
        headers=headers,
    )
    assert out_of_purpose.status_code == 200
    assert out_of_purpose.json()["memories"] == []

    edited = client.patch(
        f"/api/v1/memory/records/{record.id}",
        json={"label": "Assumptions first, always"},
        headers=headers,
    )
    assert edited.status_code == 400, edited.text
    assert edited.json()["code"] == "invalid_memory_request"

    unchanged = client.get("/api/v1/memory/records", headers=headers)
    assert unchanged.json()["records"][0]["revision"] == 1
    assert unchanged.json()["records"][0]["label"] == "Assumptions first"

    pending = service.propose(
        REGISTERED_SUBJECT,
        _seed_draft("Compare drawdown before returns.", "Drawdown first"),
        MemoryOperationContext.ORDINARY,
    )
    assert pending is not None
    declined = client.post(
        f"/api/v1/memory/candidates/{pending.candidate.id}/decline",
        headers=headers,
    )
    assert declined.status_code == 200, declined.text
    assert declined.json() == {"declined": True}

    deleted = client.delete(f"/api/v1/memory/records/{record.id}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["changed"] is True

    disabled = client.post("/api/v1/memory/disable", headers=headers)
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["changed"] is True

    reset = client.post("/api/v1/memory/reset", headers=headers)
    assert reset.status_code == 200, reset.text


def test_edit_without_backend_assessment_is_rejected(
    memory_api,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", "true")
    _configure_live_service()

    response = memory_api.client.patch(
        "/api/v1/memory/records/record-1",
        json={"label": "New label"},
        headers=memory_api.registered_headers,
    )
    assert response.status_code == 400, response.text
    assert response.json()["code"] == "invalid_memory_request"


def test_enable_requires_at_least_one_category(
    memory_api,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", "true")
    _configure_live_service()

    response = memory_api.client.post(
        "/api/v1/memory/enable",
        json={"categories": []},
        headers=memory_api.registered_headers,
    )
    assert response.status_code == 422, response.text
