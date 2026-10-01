"""Exposure gate for household membership and account grants.

Default-off behind ``ARGUS_HOUSEHOLDS_ENABLED``. While off, or when durable mode
has no database, routes answer 404 so the surface does not exist. Guests are
refused after authentication. Household sharing requires financial accounts in
memory mode so grants can resolve owned accounts.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from loguru import logger

from argus.api import state as api_state
from argus.api.dependencies import current_user, problem
from argus.api.guest_access import account_context
from argus.api.schemas import User
from argus.domain.household.errors import HouseholdError
from argus.domain.household.service import HouseholdService

FLAG = "ARGUS_HOUSEHOLDS_ENABLED"
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})

_service: HouseholdService | None = None


def households_enabled() -> bool:
    return os.getenv(FLAG, "").strip().lower() in TRUE_VALUES


def households_service() -> HouseholdService | None:
    return _service


def configure_households_service(service: HouseholdService | None) -> None:
    global _service
    _service = service


def start_households(app) -> None:  # noqa: ANN001
    if not households_enabled():
        configure_households_service(None)
        return
    from argus.api.financial_accounts import financial_accounts_service
    from argus.domain.household.repository import (
        FinancialAccountLookup,
        InMemoryHouseholdRepository,
    )
    from argus.domain.recording.repository import InMemoryFinancialAccountRepository

    accounts_service = financial_accounts_service()
    try:
        if api_state.PERSISTENCE_MODE == "supabase":
            if not api_state.DATABASE_URL:
                logger.warning(
                    "Households need DATABASE_URL in supabase mode; surface stays off"
                )
                configure_households_service(None)
                return
            if accounts_service is None:
                logger.warning(
                    "Households need financial accounts enabled; surface stays off"
                )
                configure_households_service(None)
                return
            from psycopg_pool import ConnectionPool

            from argus.domain.household.postgres import PostgresHouseholdRepository

            pool = ConnectionPool(
                api_state.DATABASE_URL, min_size=0, max_size=4, open=True
            )
            app.state.households_pool = pool
            lookup = FinancialAccountLookup(accounts_service._repository)  # noqa: SLF001
            configure_households_service(
                HouseholdService(PostgresHouseholdRepository(pool, lookup))
            )
            return

        # Memory mode: share the financial accounts in-memory repository when
        # present; otherwise attach a private twin so grant tests can inject one.
        if accounts_service is not None:
            repository = accounts_service._repository  # noqa: SLF001
        else:
            repository = InMemoryFinancialAccountRepository()
            app.state.households_private_accounts = repository
        lookup = FinancialAccountLookup(repository)
        configure_households_service(
            HouseholdService(InMemoryHouseholdRepository(lookup))
        )
    except Exception:
        logger.exception("Household surface failed to start; leaving off")
        configure_households_service(None)


def stop_households(app) -> None:  # noqa: ANN001
    configure_households_service(None)
    pool = getattr(app.state, "households_pool", None)
    if pool is not None:
        try:
            pool.close()
        except Exception:
            logger.warning("Households pool close failed")
        app.state.households_pool = None


def unavailable_problem(request: Request) -> HTTPException:
    return problem(
        request,
        status_code=404,
        code="households_unavailable",
        title="Not Found",
        detail="Households are not available.",
    )


def require_households_surface(request: Request) -> HouseholdService:
    service = households_service()
    if not households_enabled() or service is None:
        raise unavailable_problem(request)
    return service


@dataclass(frozen=True)
class HouseholdsContext:
    service: HouseholdService
    user_id: str


def require_households_context(
    request: Request,
    service: HouseholdService = Depends(require_households_surface),  # noqa: B008
    _user: User = Depends(current_user),  # noqa: B008
) -> HouseholdsContext:
    account = account_context(request)
    if account.kind != "registered":
        raise problem(
            request,
            status_code=403,
            code="account_conversion_required",
            title="Account Required",
            detail="Create an account to use households.",
        )
    return HouseholdsContext(service=service, user_id=account.user_id)


def domain_problem(request: Request, error: Exception) -> HTTPException:
    if isinstance(error, HouseholdError):
        status = 404 if error.code.endswith("not_found") else 409
        if error.code in {
            "account_not_owned",
            "household_admin_required",
            "not_a_member",
        }:
            status = 403
        if error.code == "must_transfer_or_close":
            status = 409
        return problem(
            request,
            status_code=status,
            code=error.code,
            title=error.code.replace("_", " ").capitalize(),
            detail=error.detail,
        )
    from argus.api.financial_accounts import domain_problem as financial_problem

    return financial_problem(request, error)
