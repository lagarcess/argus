"""Connected sources: what is connected, how fresh it is, and disconnect.

Thin transport over ``IngestionHub``. Credentials, cursors and leases are never
part of a response. Connector-specific routes (Plaid Link, Gmail OAuth,
Shortcuts device setup) live with their connector packages.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict

from argus.api.ingestion import (
    IngestionContext,
    connection_problem,
    require_ingestion_context,
)
from argus.domain.ingestion.connections import SourceConnection

router = APIRouter(prefix="/financial-connections", tags=["financial-connections"])


class FinancialConnectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source: Literal["plaid", "gmail", "shortcuts", "statement"]
    status: Literal["active", "needs_reauth", "error", "disconnected"]
    label: str | None
    last_success_at: datetime | None
    last_attempt_at: datetime | None
    last_error_code: str | None
    attention_code: str | None
    attention_at: datetime | None
    created_at: datetime
    disconnected_at: datetime | None


class FinancialConnectionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[FinancialConnectionResponse]


class DisconnectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connection: FinancialConnectionResponse
    provider_revocation: Literal["revoked", "failed", "not_applicable"]
    unreviewed_removed: int


def connection_response(row: SourceConnection) -> FinancialConnectionResponse:
    return FinancialConnectionResponse(
        id=row.id,
        source=row.source,
        status=row.status,
        label=row.label,
        last_success_at=row.last_success_at,
        last_attempt_at=row.last_attempt_at,
        last_error_code=row.last_error_code,
        attention_code=row.attention_code,
        attention_at=row.attention_at,
        created_at=row.created_at,
        disconnected_at=row.disconnected_at,
    )


@router.get("", response_model=FinancialConnectionListResponse)
def list_financial_connections(
    context: IngestionContext = Depends(require_ingestion_context),  # noqa: B008
) -> FinancialConnectionListResponse:
    rows = context.hub.list(user_id=context.user_id)
    return FinancialConnectionListResponse(items=[connection_response(r) for r in rows])


@router.post("/{connection_id}/disconnect", response_model=DisconnectResponse)
def disconnect_financial_connection(
    request: Request,
    connection_id: str,
    context: IngestionContext = Depends(require_ingestion_context),  # noqa: B008
) -> DisconnectResponse:
    """Idempotent: disconnecting an ended connection returns it unchanged."""

    try:
        outcome = context.hub.disconnect(
            user_id=context.user_id, connection_id=connection_id
        )
    except Exception as error:
        raise connection_problem(request, error) from None
    return DisconnectResponse(
        connection=connection_response(outcome.connection),
        provider_revocation=outcome.provider_revocation,
        unreviewed_removed=outcome.unreviewed_removed,
    )


# Connector sub-routers import the response shapes above, so they are
# included after those definitions.
from argus.api.routers.financial_connections_plaid import (  # noqa: E402
    router as plaid_router,
)

router.include_router(plaid_router)
from argus.api.routers.financial_connections_gmail import (  # noqa: E402
    router as gmail_router,
)

router.include_router(gmail_router)
