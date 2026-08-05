"""Registered-only API gate for the personalization-memory subsystem.

Every personalization-memory endpoint passes through one request-scoped gate:
verified session, canonical account kind, Guest denial, then availability.
A Guest is denied before any memory code, state, or event can exist. No
production service is configured here; endpoints stay unavailable until a
later authorized slice wires a store-backed service at startup.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.exceptions import HTTPException

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


@dataclass(frozen=True)
class MemoryApiContext:
    """Proof that one verified registered session may enter the subsystem."""

    service: MemoryService
    owner: RegisteredMemoryOwner
    subject: MemorySubject


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
    if not personalization_memory_enabled() or service is None:
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
