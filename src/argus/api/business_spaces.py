"""The process's Business space store, built beside the ingestion hub.

Postgres in ``supabase`` persistence, in memory otherwise. The Business routes
and WhatsApp intake read it through ``business_spaces`` and resolve a person's
space only with ``resolve_business_scope``.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from argus.api import state as api_state
from argus.api.dependencies import problem
from argus.api.documents import NO_STORE
from argus.domain.business.spaces import (
    InMemorySpaceStore,
    PostgresSpaceStore,
    SpaceStore,
)

_spaces: SpaceStore | None = None


def space_missing_problem(request: Request) -> HTTPException:
    return problem(
        request,
        status_code=404,
        code="business_space_missing",
        title="Not Found",
        detail="Start your business space first.",
        headers=NO_STORE,
    )


def business_spaces() -> SpaceStore | None:
    return _spaces


def configure_business_spaces(store: SpaceStore | None) -> None:
    global _spaces
    _spaces = store


def start_business_spaces(app: object) -> None:
    if api_state.PERSISTENCE_MODE != "supabase":
        configure_business_spaces(InMemorySpaceStore())
        return
    pool = getattr(getattr(app, "state", None), "financial_accounts_pool", None)
    configure_business_spaces(PostgresSpaceStore(pool) if pool is not None else None)
