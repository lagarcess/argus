"""Exposure gate and process wiring for connected-source ingestion.

Default-off behind ``ARGUS_INGESTION_ENABLED`` and nested inside the financial
accounts surface: imports only ever feed that canonical ledger, so ingestion
cannot be on while it is off. Durable mode reuses the financial accounts pool
rather than opening a second one. Connector packages register their adapters
with the hub at startup; reconciliation provides the candidate sink.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from loguru import logger

from argus.api import state as api_state
from argus.api.dependencies import problem
from argus.api.financial_accounts import (
    TRUE_VALUES,
    FinancialAccountsContext,
    financial_accounts_service,
    require_financial_accounts_context,
)
from argus.domain.ingestion.connections import (
    ConnectionNotFound,
    InMemoryConnectionRepository,
)
from argus.domain.ingestion.hub import IngestionHub
from argus.domain.ingestion.secrets import SecretBox, SecretBoxUnavailable

FLAG = "ARGUS_INGESTION_ENABLED"

_hub: IngestionHub | None = None


def ingestion_enabled() -> bool:
    return os.getenv(FLAG, "").strip().lower() in TRUE_VALUES


def ingestion_hub() -> IngestionHub | None:
    return _hub


def configure_ingestion_hub(hub: IngestionHub | None) -> None:
    global _hub
    _hub = hub


def _clock() -> datetime:
    return datetime.now(timezone.utc)


def start_ingestion(app) -> None:  # noqa: ANN001
    """Build the hub after financial accounts; any missing piece keeps it off."""

    if not ingestion_enabled() or financial_accounts_service() is None:
        configure_ingestion_hub(None)
        return
    try:
        box: SecretBox | None
        try:
            box = SecretBox.from_env()
        except SecretBoxUnavailable:
            # Connectors that store provider credentials refuse to start
            # without a key; credential-free surfaces still list/disconnect.
            box = None
        pool = getattr(app.state, "financial_accounts_pool", None)
        if api_state.PERSISTENCE_MODE == "supabase":
            if pool is None:
                configure_ingestion_hub(None)
                return
            from argus.domain.ingestion.connections_postgres import (
                PostgresConnectionRepository,
            )

            connections = PostgresConnectionRepository(pool)
        else:
            connections = InMemoryConnectionRepository()
        configure_ingestion_hub(
            IngestionHub(connections, box=box, sink=None, clock=_clock)
        )
        from argus.api.gmail import start_gmail

        start_gmail(ingestion_hub(), pool)
    except Exception as exc:
        logger.warning(
            "Ingestion hub construction failed; surface stays off",
            failure_mode=type(exc).__name__,
        )
        configure_ingestion_hub(None)


def stop_ingestion(app) -> None:  # noqa: ANN001
    from argus.api.gmail import stop_gmail

    stop_gmail()
    configure_ingestion_hub(None)


@dataclass(frozen=True)
class IngestionContext:
    hub: IngestionHub
    user_id: str


def require_ingestion_surface(request: Request) -> IngestionHub:
    """Flag first, before authentication, so an off surface looks absent."""

    hub = ingestion_hub()
    if not ingestion_enabled() or hub is None:
        raise unavailable_problem(request)
    return hub


def require_ingestion_context(
    hub: IngestionHub = Depends(require_ingestion_surface),  # noqa: B008
    accounts: FinancialAccountsContext = Depends(require_financial_accounts_context),  # noqa: B008
) -> IngestionContext:
    return IngestionContext(hub=hub, user_id=accounts.user_id)


def unavailable_problem(request: Request) -> HTTPException:
    return problem(
        request,
        status_code=404,
        code="financial_connections_unavailable",
        title="Not Found",
        detail="Financial connections are not available.",
    )


def connection_problem(request: Request, error: Exception) -> HTTPException:
    if isinstance(error, ConnectionNotFound):
        return problem(
            request,
            status_code=404,
            code="financial_connection_not_found",
            title="Not Found",
            detail="No such financial connection.",
        )
    raise error
