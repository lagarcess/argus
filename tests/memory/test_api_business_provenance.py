"""Memory is Personal: a proposal whose source is a Business chat is refused.

The source can be named as the conversation, one of its messages, or the
evidence, idea, idea version or decision note it produced. Each is refused before the assessor or the service runs, and the
same proposal from a Personal chat still reaches the service.
"""

from __future__ import annotations

from typing import cast

import pytest
from argus.api.personalization_memory import configure_memory_service
from argus.api.personalization_memory_assessor import configure_sensitivity_classifier
from argus.domain.owner_scope import PERSONAL, BusinessSpace
from argus.llm.memory_sensitivity import MemorySensitivityVerdict
from argus.memory.service import MemoryService
from argus.memory.store import InMemoryCanonicalMemoryStore

BUSINESS_CHAT = "00000000-0000-4000-8000-0000000000b1"
PERSONAL_CHAT = "00000000-0000-4000-8000-0000000000a1"
BUSINESS_MESSAGE = "00000000-0000-4000-8000-0000000000b2"
BUSINESS_ARTIFACTS = {
    "evidence_artifact": "00000000-0000-4000-8000-0000000000b3",
    "idea": "00000000-0000-4000-8000-0000000000b4",
    "idea_version": "00000000-0000-4000-8000-0000000000b5",
    "decision_note": "00000000-0000-4000-8000-0000000000b6",
}


def _propose(memory_api, source_kind: str, source_id: str):  # noqa: ANN001, ANN202
    return memory_api.client.post(
        "/api/v1/memory/candidates",
        json={
            "category": "workflow_preference",
            "value": "Show assumptions before results.",
            "label": "Assumptions first",
            "future_benefit": "Argus can keep the preferred review order.",
            "provenance": [
                {
                    "source_kind": source_kind,
                    "source_id": source_id,
                    "source_version": "1",
                }
            ],
        },
        headers=memory_api.registered_headers,
    )


@pytest.fixture
def live_memory(memory_api, monkeypatch: pytest.MonkeyPatch):  # noqa: ANN001, ANN201
    monkeypatch.setenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", "true")
    configure_memory_service(MemoryService(store=InMemoryCanonicalMemoryStore()))
    configure_sensitivity_classifier(
        lambda _content: MemorySensitivityVerdict(status="clear")
    )
    gateway = memory_api.gateway
    gateway.conversation_scope.side_effect = lambda *, user_id, conversation_id: (
        BusinessSpace("space-1") if conversation_id == BUSINESS_CHAT else PERSONAL
    )
    gateway.message_conversation_id.side_effect = lambda *, user_id, message_id: (
        BUSINESS_CHAT if message_id == BUSINESS_MESSAGE else PERSONAL_CHAT
    )
    gateway.artifact_source_conversation_id.side_effect = (
        lambda *, table, user_id, artifact_id: (
            BUSINESS_CHAT if artifact_id in BUSINESS_ARTIFACTS.values() else PERSONAL_CHAT
        )
    )
    return memory_api


@pytest.mark.parametrize(
    ("source_kind", "source_id"),
    [
        ("conversation", BUSINESS_CHAT),
        ("message", BUSINESS_MESSAGE),
        *BUSINESS_ARTIFACTS.items(),
    ],
)
def test_a_business_source_is_refused(live_memory, source_kind, source_id) -> None:  # noqa: ANN001
    response = _propose(live_memory, source_kind, source_id)

    assert response.status_code == 400, response.text
    assert response.json()["code"] == "invalid_memory_request"


@pytest.mark.parametrize(
    ("source_kind", "source_id"),
    [("conversation", PERSONAL_CHAT), ("idea", "00000000-0000-4000-8000-0000000000a4")],
)
def test_a_personal_source_still_reaches_the_service(
    live_memory,
    source_kind,
    source_id,  # noqa: ANN001
) -> None:
    response = _propose(live_memory, source_kind, source_id)

    assert response.status_code == 200, response.text
    assert response.json()["created"] is True


def test_the_saved_decision_proposal_refuses_a_business_source(live_memory) -> None:  # noqa: ANN001
    response = live_memory.client.post(
        "/api/v1/memory/candidates/saved-decision",
        json={
            "label": "Shop decision",
            "value": "Keep the larger supplier.",
            "provenance": {
                "source_kind": "message",
                "source_id": BUSINESS_MESSAGE,
                "source_version": "1",
            },
        },
        headers=live_memory.registered_headers,
    )

    assert response.status_code == 400, response.text
    assert cast(dict, response.json())["code"] == "invalid_memory_request"
