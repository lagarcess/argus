from __future__ import annotations

from typing import Annotated

from fastapi import Header

from argus.api.schemas import DecisionActionAvailability

CLIENT_CAPABILITIES_HEADER = "X-Argus-Client-Capabilities"
MAX_CLIENT_CAPABILITIES_HEADER_LENGTH = 1024
DOSSIER_DECISION_CONVERSION_CAPABILITY = "dossier_decision_conversion_v1"

ClientCapabilitiesHeader = Annotated[
    str | None,
    Header(
        alias=CLIENT_CAPABILITIES_HEADER,
        max_length=MAX_CLIENT_CAPABILITIES_HEADER_LENGTH,
    ),
]


def dossier_decision_action_availability(
    *,
    can_save_decision: bool,
    raw_client_capabilities: str | None,
) -> DecisionActionAvailability | None:
    """Combine server policy with an additive client presentation handshake."""
    if can_save_decision:
        return "available"
    if _supports_client_capability(
        raw_client_capabilities,
        DOSSIER_DECISION_CONVERSION_CAPABILITY,
    ):
        return "account_conversion_required"
    return None


def _supports_client_capability(
    raw_client_capabilities: str | None,
    capability: str,
) -> bool:
    if (
        not raw_client_capabilities
        or len(raw_client_capabilities) > MAX_CLIENT_CAPABILITIES_HEADER_LENGTH
    ):
        return False
    return capability in {
        token.strip()
        for token in raw_client_capabilities.split(",")
        if token.strip()
    }
