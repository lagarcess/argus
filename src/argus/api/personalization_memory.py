"""Registered-only API gate for the personalization-memory subsystem.

Every personalization-memory endpoint passes through one request-scoped gate:
verified session, canonical account kind, Guest denial, then availability.
A Guest is denied before any memory code, state, or event can exist.
Availability requires all three of the default-off flag, an injected service,
and an admin or developer private_alpha_allowlist role, so the surface stays
invisible to ordinary registered accounts even in a flag-on environment.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.exceptions import HTTPException
from loguru import logger

from argus.api import state as api_state
from argus.api.dependencies import current_user, problem
from argus.api.guest_access import account_context
from argus.api.schemas import User
from argus.memory.service import MemoryService, MemoryServiceConfig
from argus.memory.subject import (
    MemoryAccountKind,
    MemorySubject,
    RegisteredMemoryOwner,
    require_registered,
)

MEMORY_EXPOSURE_ROLES = frozenset({"admin", "developer"})

_memory_service: MemoryService | None = None


def configure_memory_service(service: MemoryService | None) -> None:
    """Inject the process-wide memory service; None keeps endpoints inert."""

    global _memory_service
    _memory_service = service


def memory_service() -> MemoryService | None:
    return _memory_service


def personalization_memory_enabled() -> bool:
    # Single flag truth: the service config's default-off env switch.
    return MemoryServiceConfig().available


def memory_exposure_role_allowed(user: User) -> bool:
    """Canonical allowlist role decides exposure; anything else fails closed.

    The in-memory persistence mode has no allowlist and never runs hosted, so
    it exposes the surface to the local developer.
    """

    gateway = api_state.supabase_gateway
    if gateway is None:
        return True
    email = (user.email or "").strip()
    if not email:
        return False
    try:
        role = gateway.private_alpha_role_for_email(email)
    except Exception as exc:
        logger.warning(
            "Memory exposure role lookup failed closed",
            failure_mode=type(exc).__name__,
        )
        return False
    return role in MEMORY_EXPOSURE_ROLES


def personalization_memory_exposed(user: User) -> bool:
    """One exposure truth for the gate, the availability probe, and runtime."""

    return (
        personalization_memory_enabled()
        and memory_service() is not None
        and memory_exposure_role_allowed(user)
    )


@dataclass(frozen=True)
class MemoryApiContext:
    """Proof that one verified registered session may enter the subsystem."""

    service: MemoryService
    owner: RegisteredMemoryOwner
    subject: MemorySubject


def start_personalization_memory(app) -> None:  # noqa: ANN001
    """Construct the process service at startup; flag off constructs nothing.

    Store choice follows persistence mode: the canonical Postgres adapter on
    Supabase deployments, the deterministic in-memory store in dev memory
    mode. Any construction failure leaves the surface unavailable instead of
    blocking boot.
    """

    if not personalization_memory_enabled():
        configure_memory_service(None)
        return
    try:
        if api_state.PERSISTENCE_MODE == "supabase" and api_state.DATABASE_URL:
            from psycopg_pool import ConnectionPool

            from argus.memory.postgres_store import PostgresCanonicalMemoryStore

            pool = ConnectionPool(
                api_state.DATABASE_URL,
                min_size=0,
                max_size=4,
                open=True,
            )
            app.state.personalization_memory_pool = pool
            configure_memory_service(
                MemoryService(store=PostgresCanonicalMemoryStore(pool))
            )
            return
        from argus.memory.store import InMemoryCanonicalMemoryStore

        configure_memory_service(MemoryService(store=InMemoryCanonicalMemoryStore()))
    except Exception as exc:
        logger.warning(
            "Personalization memory service construction failed; surface stays off",
            failure_mode=type(exc).__name__,
        )
        configure_memory_service(None)


def stop_personalization_memory(app) -> None:  # noqa: ANN001
    configure_memory_service(None)
    pool = getattr(app.state, "personalization_memory_pool", None)
    if pool is not None:
        try:
            pool.close()
        except Exception:
            logger.warning("Personalization memory pool close failed")
        app.state.personalization_memory_pool = None


def personalization_memory_unavailable_problem(request: Request) -> HTTPException:
    return problem(
        request,
        status_code=404,
        code="personalization_memory_unavailable",
        title="Not Found",
        detail="Personalization memory is not available.",
    )


def require_memory_api_context(
    request: Request,
    _user: User = Depends(current_user),  # noqa: B008
) -> MemoryApiContext:
    account = account_context(request)
    if account.kind != "registered":
        raise problem(
            request,
            status_code=403,
            code="account_conversion_required",
            title="Account Required",
            detail="Create an account to use personalization memory.",
        )
    service = memory_service()
    if (
        not personalization_memory_enabled()
        or service is None
        or not memory_exposure_role_allowed(_user)
    ):
        raise personalization_memory_unavailable_problem(request)
    subject = MemorySubject(
        owner_id=account.user_id,
        kind=MemoryAccountKind.REGISTERED,
    )
    return MemoryApiContext(
        service=service,
        owner=require_registered(subject),
        subject=subject,
    )
