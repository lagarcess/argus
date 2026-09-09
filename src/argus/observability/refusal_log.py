"""Private, unclassified observations of chat outcomes and rejected actions."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import uuid4

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class RefusalObservation(BaseModel):
    """Link a terminal message pair, or retain a request rejected before storage."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    conversation_id: str | None = None
    request_message_id: str | None = None
    response_message_id: str | None = None
    asked: str | None = None
    action: dict[str, JsonValue] | None = None
    outcome: dict[str, JsonValue] | None = None
    status_code: int = Field(default=200, ge=200, le=599)

    @model_validator(mode="after")
    def validate_record_shape(self) -> RefusalObservation:
        if self.request_message_id is not None or self.response_message_id is not None:
            if not all(
                (self.request_message_id, self.response_message_id, self.conversation_id)
            ):
                raise ValueError("Linked observations require an exact message pair.")
            if any(
                value is not None for value in (self.asked, self.action, self.outcome)
            ):
                raise ValueError("Linked observations derive content from messages.")
            if self.status_code != 200:
                raise ValueError("Linked observations use the accepted stream status.")
        elif self.asked is None or self.outcome is None or self.status_code < 400:
            raise ValueError("Rejected observations require the request and problem.")
        return self


class RefusalObservationGateway(Protocol):
    @property
    def client(self) -> Any:
        """Return the server-owned Supabase client."""


def persist_refusal_observation(
    *, gateway: RefusalObservationGateway | None, observation: RefusalObservation
) -> bool:
    """Attempt the private write before returning, preserving response behavior."""
    if gateway is None:
        return False
    try:
        table = gateway.client.table("refusal_observations")
        try:
            table.insert(observation.model_dump(mode="json")).execute()
        except Exception as exc:
            if (
                getattr(exc, "code", None) != "23505"
                or not observation.response_message_id
            ):
                raise
            rows = (
                table.select(
                    "user_id,conversation_id,request_message_id,response_message_id"
                )
                .eq("response_message_id", observation.response_message_id)
                .limit(1)
                .execute()
                .data
            )
            expected = observation.model_dump(
                include={
                    "user_id",
                    "conversation_id",
                    "request_message_id",
                    "response_message_id",
                }
            )
            if not rows or rows[0] != expected:
                raise ValueError("Conflicting terminal observation identity.") from None
        return True
    except Exception as exc:
        logger.warning("Refusal observation persistence failed ({})", type(exc).__name__)
        return False
