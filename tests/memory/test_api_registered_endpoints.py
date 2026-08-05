"""Registered sessions get the full memory lifecycle; the flag keeps it inert.

The default-off ARGUS_ENABLE_PERSONALIZATION_MEMORY flag and the injected
service are both required before any endpoint reaches the subsystem; with
either missing, an exploding service proves nothing is touched.

Sensitivity is backend truth: requests carry no sensitivity fields and the
backend assessor classifies content at the propose and edit boundaries. These
tests inject a clear-verdict classifier; assessor failure modes live in
tests/memory/test_api_sensitivity_assessment.py.
"""

from __future__ import annotations

from typing import cast

import pytest
from api_matrix import ENDPOINT_CALLS
from argus.api.personalization_memory import configure_memory_service
from argus.api.personalization_memory_assessor import configure_sensitivity_classifier
from argus.llm.memory_sensitivity import MemorySensitivityVerdict
from argus.memory.service import MemoryService
from argus.memory.store import InMemoryCanonicalMemoryStore


class _ExplodingMemoryService:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"MemoryService.{name} must not be touched")


def _configure_live_service() -> MemoryService:
    service = MemoryService(store=InMemoryCanonicalMemoryStore())
    configure_memory_service(service)
    configure_sensitivity_classifier(
        lambda _content: MemorySensitivityVerdict(status="clear")
    )
    return service


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
        if call.path.endswith("/availability"):
            assert response.status_code == 200, response.text
            assert response.json() == {"available": False}
            continue
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
        if call.path.endswith("/availability"):
            assert response.status_code == 200, response.text
            assert response.json() == {"available": False}
            continue
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


def test_registered_lifecycle_end_to_end(
    memory_api,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", "true")
    _configure_live_service()
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

    settings = client.get("/api/v1/memory/settings", headers=headers)
    assert settings.status_code == 200, settings.text
    assert settings.json() == {
        "enabled": True,
        "enabled_categories": ["workflow_preference"],
    }

    proposed = client.post(
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
    assert proposed.status_code == 200, proposed.text
    proposal = proposed.json()
    assert proposal["created"] is True
    candidate = proposal["candidate"]
    assert candidate["trigger"] == "explicit_request"
    assert "owner_id" not in candidate

    confirmed = client.post(
        f"/api/v1/memory/candidates/{candidate['id']}/confirm",
        json={},
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    confirmation = confirmed.json()
    assert confirmation["created"] is True
    record = confirmation["record"]
    assert record["category"] == "workflow_preference"
    assert record["revision"] == 1
    assert "owner_id" not in record
    assert confirmation["consent_receipt"]["action"] == "candidate_confirmation"

    records = client.get("/api/v1/memory/records", headers=headers)
    assert records.status_code == 200, records.text
    listed = records.json()["records"]
    assert [item["id"] for item in listed] == [record["id"]]

    explanation = client.get(
        f"/api/v1/memory/records/{record['id']}/explanation",
        headers=headers,
    )
    assert explanation.status_code == 200, explanation.text
    assert explanation.json()["record_id"] == record["id"]
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
    assert [memory["record"]["id"] for memory in memories] == [record["id"]]

    out_of_purpose = client.post(
        "/api/v1/memory/retrieval",
        json={"query": "assumptions", "purpose": "revisit_saved_decision"},
        headers=headers,
    )
    assert out_of_purpose.status_code == 200
    assert out_of_purpose.json()["memories"] == []

    edited = client.patch(
        f"/api/v1/memory/records/{record['id']}",
        json={"label": "Assumptions first, always"},
        headers=headers,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["changed"] is True
    assert edited.json()["record"]["revision"] == 2
    assert edited.json()["record"]["label"] == "Assumptions first, always"

    exported = client.get("/api/v1/memory/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-disposition"] == (
        'attachment; filename="argus-memory-export.json"'
    )
    export_document = exported.json()
    assert export_document["format"] == "argus.personalization-memory-export/v1"
    assert export_document["settings"]["enabled"] is True
    assert [item["id"] for item in export_document["records"]] == [record["id"]]
    assert export_document["records"][0]["label"] == "Assumptions first, always"
    assert "owner_id" not in export_document["records"][0]

    deleted = client.delete(
        f"/api/v1/memory/records/{record['id']}",
        headers=headers,
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["changed"] is True

    disabled = client.post("/api/v1/memory/disable", headers=headers)
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["changed"] is True

    reset = client.post("/api/v1/memory/reset", headers=headers)
    assert reset.status_code == 200, reset.text

    saved_decision = client.post(
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
    saved_proposal = saved_decision.json()
    assert saved_proposal["created"] is True
    assert saved_proposal["candidate"]["trigger"] == "saved_decision"
    assert saved_proposal["candidate"]["opt_in_scope"] == [
        "explicit_decision_note",
        "past_session_anchor",
    ]

    declined = client.post(
        f"/api/v1/memory/candidates/{saved_proposal['candidate']['id']}/decline",
        headers=headers,
    )
    assert declined.status_code == 200, declined.text
    assert declined.json() == {"declined": True}


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
