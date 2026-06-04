from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

ContextProvider = Literal["fred", "alpaca"]
ContextPacketType = Literal[
    "macro",
    "news",
    "corporate_actions",
    "market_movers",
    "most_actives",
]
ContextFreshness = Literal["fresh", "stale", "unknown"]


class ContextPacketFact(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: str
    label: str
    value: Any
    observed_at: date | datetime | None = None
    source_id: str | None = None


class ContextPacket(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    provider: ContextProvider
    packet_type: ContextPacketType
    scope: dict[str, Any] = Field(default_factory=dict)
    source_ids: tuple[str, ...] = ()
    retrieved_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    coverage_start: date | None = None
    coverage_end: date | None = None
    freshness: ContextFreshness = "unknown"
    facts: tuple[ContextPacketFact, ...] = ()
    limitations: tuple[str, ...] = ()
    not_for: Literal["simulation_truth"] = "simulation_truth"

    def storage_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ContextPacketAttachment(BaseModel):
    model_config = ConfigDict(frozen=True)

    packet_id: str
    run_id: str
    explanation_id: str | None = None
    attached_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    immutable_snapshot: bool = True


def attach_context_packet_to_run(
    packet: ContextPacket,
    *,
    run_id: str,
    explanation_id: str | None = None,
) -> ContextPacketAttachment:
    return ContextPacketAttachment(
        packet_id=packet.id,
        run_id=run_id,
        explanation_id=explanation_id,
    )
