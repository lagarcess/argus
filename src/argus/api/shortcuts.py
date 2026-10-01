"""Process wiring and request gates for the Apple Shortcuts connector.

The connector exists whenever the ingestion hub exists; it stores no provider
credential, so it does not need ``ARGUS_INGESTION_SECRET_KEY``. Its local
``revoke`` is registered with the hub so disconnect deletes the device token.
Event intake has no user session: it answers 404 while the surface is off and
otherwise authenticates only by the device token.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from loguru import logger

from argus.api import state as api_state
from argus.api.dependencies import problem
from argus.api.ingestion import (
    IngestionContext,
    require_ingestion_context,
    require_ingestion_surface,
    unavailable_problem,
)
from argus.api.rate_limits import SlidingWindowLimiter
from argus.domain.ingestion.connections import SourceConnection
from argus.domain.ingestion.hub import IngestionHub
from argus.domain.ingestion.shortcuts.connector import ShortcutsConnector
from argus.domain.ingestion.shortcuts.store import (
    DeviceTokenStore,
    InMemoryDeviceTokenStore,
)

# A person taps a card a few times an hour and a pending-captures batch is one
# request; these bound a leaked token, not normal use.
RATE_LIMITS = ((20, 60), (300, 24 * 60 * 60))

_connector: ShortcutsConnector | None = None
_limiter = SlidingWindowLimiter()


def shortcuts_connector() -> ShortcutsConnector | None:
    return _connector


def configure_shortcuts_connector(connector: ShortcutsConnector | None) -> None:
    global _connector
    _connector = connector
    _limiter.reset()


def start_shortcuts(app, hub: IngestionHub | None) -> None:  # noqa: ANN001
    if hub is None:
        configure_shortcuts_connector(None)
        return
    store: DeviceTokenStore
    if api_state.PERSISTENCE_MODE == "supabase":
        pool = getattr(app.state, "financial_accounts_pool", None)
        if pool is None:
            configure_shortcuts_connector(None)
            return
        from argus.domain.ingestion.shortcuts.store import PostgresDeviceTokenStore

        store = PostgresDeviceTokenStore(pool)
    else:
        store = InMemoryDeviceTokenStore()
    connector = ShortcutsConnector(hub, store)
    hub.register(connector.adapter)
    configure_shortcuts_connector(connector)
    logger.info("Shortcuts connector ready")


def stop_shortcuts() -> None:
    configure_shortcuts_connector(None)


@dataclass(frozen=True)
class ShortcutsContext:
    connector: ShortcutsConnector
    user_id: str


def require_shortcuts_context(
    request: Request,
    context: IngestionContext = Depends(require_ingestion_context),  # noqa: B008
) -> ShortcutsContext:
    connector = shortcuts_connector()
    if connector is None or connector.hub is not context.hub:
        raise unavailable_problem(request)
    return ShortcutsContext(connector=connector, user_id=context.user_id)


@dataclass(frozen=True)
class DeviceContext:
    connector: ShortcutsConnector
    connection: SourceConnection


def require_shortcuts_device(
    request: Request,
    hub: IngestionHub = Depends(require_ingestion_surface),  # noqa: B008
) -> DeviceContext:
    """Flag first; then the device token is the only accepted credential."""

    connector = shortcuts_connector()
    if connector is None or connector.hub is not hub:
        raise unavailable_problem(request)
    connection = connector.authenticate(request.headers.get("Authorization"))
    if connection is None:
        raise problem(
            request,
            status_code=401,
            code="shortcuts_device_unauthorized",
            title="Unauthorized",
            detail="This device is not connected. Set it up again in Cuadrao.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    for limit, window in RATE_LIMITS:
        wait = _limiter.record_or_retry_after(
            keys=(f"shortcuts-device:{connection.id}:{window}",),
            limit=limit,
            window_seconds=window,
        )
        if wait is not None:
            raise problem(
                request,
                status_code=429,
                code="too_many_requests",
                title="Too Many Requests",
                detail="This device sent many captures recently. Try again shortly.",
                headers={"Retry-After": str(wait)},
            )
    return DeviceContext(connector=connector, connection=connection)


def intake_unavailable_problem(request: Request) -> HTTPException:
    return problem(
        request,
        status_code=503,
        code="shortcuts_intake_unavailable",
        title="Service Unavailable",
        detail="Captures cannot be saved right now. Nothing was saved; try again later.",
        context={"retryable": True},
        headers={"Retry-After": "300"},
    )
