"""In-app account deletion (Lane 6).

``POST /api/v1/account/delete`` runs the whole deletion command for the signed-in
person. It is off unless ``ARGUS_ACCOUNT_DELETION_ENABLED`` is on, and while off
it answers 404 before any authentication. The user id comes only from the
verified session, never from the request body. A guest session is deleted
the same way.
"""

from __future__ import annotations

import os
from typing import Literal

from fastapi import APIRouter, Depends, Request
from loguru import logger
from pydantic import BaseModel, ConfigDict

from argus.api import state as api_state
from argus.api.dependencies import current_user, problem
from argus.api.schemas import User
from argus.domain.account_deletion.service import (
    AccountDeletionIncomplete,
    AccountDeletionRejected,
    AccountDeletionService,
)

FLAG = "ARGUS_ACCOUNT_DELETION_ENABLED"

router = APIRouter(prefix="/api/v1", tags=["account"])


def account_deletion_enabled() -> bool:
    return os.getenv(FLAG, "").strip().lower() in {"1", "true", "yes", "on"}


class AccountDeletionRequest(BaseModel):
    # A JSON body is required, so a cross-site form post can't reach this route.
    # Nothing else is accepted: whose account it is comes from the session.
    model_config = ConfigDict(extra="forbid")

    confirm: Literal[True]


class AccountDeletionResponse(BaseModel):
    status: Literal["done", "auth_deleted"]
    # Provider revocations still owed (for example "gmail"). The account is
    # already gone; these are retried by the run, not by the person. Apple is
    # never here: it is revoked before the account delete, which waits for it.
    pending: list[str]


def account_deletion_service() -> AccountDeletionService | None:
    """Built per request from the running surfaces; None when one is missing."""

    from argus.api.apple_sign_in import apple_credentials_service
    from argus.api.households import households_service
    from argus.api.ingestion import ingestion_hub
    from argus.domain.account_deletion.auth_admin import SupabaseAuthAdmin
    from argus.domain.household.postgres import PostgresHouseholdRepository
    from argus.observability.analytics_deletion import analytics_deletion_from_env

    households = households_service()
    repository = getattr(households, "_repository", None)
    gateway = api_state.supabase_gateway
    if not isinstance(repository, PostgresHouseholdRepository) or gateway is None:
        return None
    return AccountDeletionService(
        households=repository,
        auth_admin=SupabaseAuthAdmin(gateway.client),
        revoker=ingestion_hub(),
        analytics=analytics_deletion_from_env(),
        # #793's service when its capture surface is on; without it a stored
        # Apple token keeps the run pending (503, retry) and is never dropped.
        apple=apple_credentials_service(),
    )


def _deleting_user(request: Request) -> User:
    # The flag is checked before current_user, so a disabled route says
    # nothing about sessions.
    if not account_deletion_enabled():
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Not found.",
        )
    return current_user(request)


@router.post("/account/delete", response_model=AccountDeletionResponse)
def delete_account(
    payload: AccountDeletionRequest,
    request: Request,
    user: User = Depends(_deleting_user),  # noqa: B008
) -> AccountDeletionResponse:
    # A guest session is deleted by the same command (Lane 6 acceptance).
    service = account_deletion_service()
    if service is None:
        raise problem(
            request,
            status_code=503,
            code="account_deletion_unavailable",
            title="Account Deletion Unavailable",
            detail="Account deletion is not available right now.",
        )
    try:
        outcome = service.delete_account(user_id=user.id)
    except AccountDeletionRejected:
        raise problem(
            request,
            status_code=403,
            code="account_deletion_not_allowed",
            title="Not Allowed",
            detail="This account can't be deleted here.",
        ) from None
    except AccountDeletionIncomplete:
        raise problem(
            request,
            status_code=503,
            code="account_deletion_incomplete",
            title="Account Deletion Incomplete",
            detail="Deletion did not finish. Try again to finish it.",
            headers={"Retry-After": "5"},
        ) from None
    except Exception as exc:
        # No user id in logs: the run is keyed on a hash for that reason.
        logger.error("Account deletion failed: {}", type(exc).__name__)
        raise problem(
            request,
            status_code=503,
            code="account_deletion_incomplete",
            title="Account Deletion Incomplete",
            detail="Deletion did not finish. Try again to finish it.",
            headers={"Retry-After": "5"},
        ) from None
    return AccountDeletionResponse(
        status="done" if outcome.status == "done" else "auth_deleted",
        pending=sorted(outcome.pending),
    )
