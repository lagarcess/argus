"""Complete endpoint matrix for the personalization-memory API surface.

One row per MemoryService public operation so table-driven tests fail when an
endpoint or a service method is added without the other.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

GUEST_TOKEN = "verified-guest-token"
REGISTERED_TOKEN = "verified-registered-token"
GUEST_USER_ID = "9d9ec96b-6fd7-4d8f-b092-b518701674f8"
REGISTERED_USER_ID = "00000000-0000-0000-0000-000000000041"
REGISTERED_EMAIL = "registered-memory@example.com"


@dataclass(frozen=True)
class EndpointCall:
    operation: str
    method: str
    path: str
    json: dict[str, Any] | None = None


_CLEAR_SENSITIVITY = {"status": "clear"}
_MESSAGE_PROVENANCE = {
    "source_kind": "message",
    "source_id": "message-api-test",
    "source_version": "1",
}
_DECISION_PROVENANCE = {
    "source_kind": "decision_note",
    "source_id": "decision-note-api-test",
    "source_version": "1",
}


ENDPOINT_CALLS: tuple[EndpointCall, ...] = (
    EndpointCall(
        operation="enable",
        method="POST",
        path="/api/v1/memory/enable",
        json={"categories": ["workflow_preference"]},
    ),
    EndpointCall(
        operation="propose",
        method="POST",
        path="/api/v1/memory/candidates",
        json={
            "category": "workflow_preference",
            "value": "Show assumptions before results.",
            "label": "Assumptions first",
            "future_benefit": "Argus can keep the preferred review order.",
            "provenance": [_MESSAGE_PROVENANCE],
            "sensitivity": _CLEAR_SENSITIVITY,
        },
    ),
    EndpointCall(
        operation="propose_saved_decision",
        method="POST",
        path="/api/v1/memory/candidates/saved-decision",
        json={
            "label": "Keep the lower-drawdown version",
            "value": "The user rejected the higher-drawdown version.",
            "provenance": _DECISION_PROVENANCE,
            "sensitivity": _CLEAR_SENSITIVITY,
        },
    ),
    EndpointCall(
        operation="confirm",
        method="POST",
        path="/api/v1/memory/candidates/candidate-1/confirm",
        json={"sensitivity": _CLEAR_SENSITIVITY},
    ),
    EndpointCall(
        operation="decline",
        method="POST",
        path="/api/v1/memory/candidates/candidate-1/decline",
    ),
    EndpointCall(
        operation="inspect",
        method="GET",
        path="/api/v1/memory/records",
    ),
    EndpointCall(
        operation="explain",
        method="GET",
        path="/api/v1/memory/records/record-1/explanation",
    ),
    EndpointCall(
        operation="retrieve",
        method="POST",
        path="/api/v1/memory/retrieval",
        json={"query": "drawdown", "purpose": "revisit_saved_decision"},
    ),
    EndpointCall(
        operation="edit",
        method="PATCH",
        path="/api/v1/memory/records/record-1",
        json={"label": "Assumptions first, always", "sensitivity": _CLEAR_SENSITIVITY},
    ),
    EndpointCall(
        operation="delete",
        method="DELETE",
        path="/api/v1/memory/records/record-1",
    ),
    EndpointCall(
        operation="disable",
        method="POST",
        path="/api/v1/memory/disable",
    ),
    EndpointCall(
        operation="reset",
        method="POST",
        path="/api/v1/memory/reset",
    ),
)
