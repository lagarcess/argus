"""Household membership, invitations, and explicit account grants."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from argus.api.households import (
    HouseholdsContext,
    domain_problem,
    require_households_context,
)
from argus.domain.household.schemas import (
    AcceptInvitationRequest,
    AccountGrantRecord,
    CreateAccountGrantRequest,
    CreateHouseholdRequest,
    HouseholdRecord,
    InvitationCreated,
    SharedAccountView,
    TransferAdminRequest,
    UpdateAccountGrantRequest,
)

router = APIRouter(prefix="/api/v1", tags=["households"])


class HouseholdListResponse(BaseModel):
    households: list[HouseholdRecord]


class SharedAccountListResponse(BaseModel):
    accounts: list[SharedAccountView]


@router.post("/households", response_model=HouseholdRecord, status_code=201)
def create_household(
    request: Request,
    body: CreateHouseholdRequest,
    context: HouseholdsContext = Depends(require_households_context),  # noqa: B008
) -> HouseholdRecord:
    try:
        return context.service.create(user_id=context.user_id, request=body)
    except Exception as error:
        raise domain_problem(request, error) from None


@router.get("/households", response_model=HouseholdListResponse)
def list_households(
    context: HouseholdsContext = Depends(require_households_context),  # noqa: B008
) -> HouseholdListResponse:
    return HouseholdListResponse(
        households=context.service.list(user_id=context.user_id)
    )


@router.get("/households/{household_id}", response_model=HouseholdRecord)
def get_household(
    request: Request,
    household_id: str,
    context: HouseholdsContext = Depends(require_households_context),  # noqa: B008
) -> HouseholdRecord:
    try:
        return context.service.get(user_id=context.user_id, household_id=household_id)
    except Exception as error:
        raise domain_problem(request, error) from None


@router.post(
    "/households/{household_id}/invitations",
    response_model=InvitationCreated,
    status_code=201,
)
def create_invitation(
    request: Request,
    household_id: str,
    context: HouseholdsContext = Depends(require_households_context),  # noqa: B008
) -> InvitationCreated:
    try:
        return context.service.invite(user_id=context.user_id, household_id=household_id)
    except Exception as error:
        raise domain_problem(request, error) from None


@router.post(
    "/households/{household_id}/invitations/{invitation_id}/revoke",
    status_code=204,
)
def revoke_invitation(
    request: Request,
    household_id: str,
    invitation_id: str,
    context: HouseholdsContext = Depends(require_households_context),  # noqa: B008
) -> Response:
    try:
        context.service.revoke_invitation(
            user_id=context.user_id,
            household_id=household_id,
            invitation_id=invitation_id,
        )
    except Exception as error:
        raise domain_problem(request, error) from None
    return Response(status_code=204)


@router.post("/household-invitations/accept", response_model=HouseholdRecord)
def accept_invitation(
    request: Request,
    body: AcceptInvitationRequest,
    context: HouseholdsContext = Depends(require_households_context),  # noqa: B008
) -> HouseholdRecord:
    try:
        return context.service.accept(user_id=context.user_id, token=body.token)
    except Exception as error:
        raise domain_problem(request, error) from None


@router.post("/households/{household_id}/leave", status_code=204)
def leave_household(
    request: Request,
    household_id: str,
    context: HouseholdsContext = Depends(require_households_context),  # noqa: B008
) -> Response:
    try:
        context.service.leave(user_id=context.user_id, household_id=household_id)
    except Exception as error:
        raise domain_problem(request, error) from None
    return Response(status_code=204)


@router.post("/households/{household_id}/members/{member_user_id}/remove", status_code=204)
def remove_member(
    request: Request,
    household_id: str,
    member_user_id: str,
    context: HouseholdsContext = Depends(require_households_context),  # noqa: B008
) -> Response:
    try:
        context.service.remove_member(
            user_id=context.user_id,
            household_id=household_id,
            member_user_id=member_user_id,
        )
    except Exception as error:
        raise domain_problem(request, error) from None
    return Response(status_code=204)


@router.post("/households/{household_id}/transfer-admin", response_model=HouseholdRecord)
def transfer_admin(
    request: Request,
    household_id: str,
    body: TransferAdminRequest,
    context: HouseholdsContext = Depends(require_households_context),  # noqa: B008
) -> HouseholdRecord:
    try:
        return context.service.transfer_admin(
            user_id=context.user_id,
            household_id=household_id,
            new_admin_user_id=body.user_id,
        )
    except Exception as error:
        raise domain_problem(request, error) from None


@router.post("/households/{household_id}/close", response_model=HouseholdRecord)
def close_household(
    request: Request,
    household_id: str,
    context: HouseholdsContext = Depends(require_households_context),  # noqa: B008
) -> HouseholdRecord:
    try:
        return context.service.close(user_id=context.user_id, household_id=household_id)
    except Exception as error:
        raise domain_problem(request, error) from None


@router.post(
    "/households/{household_id}/account-grants",
    response_model=AccountGrantRecord,
    status_code=201,
)
def create_account_grant(
    request: Request,
    household_id: str,
    body: CreateAccountGrantRequest,
    context: HouseholdsContext = Depends(require_households_context),  # noqa: B008
) -> AccountGrantRecord:
    try:
        return context.service.create_grant(
            user_id=context.user_id, household_id=household_id, request=body
        )
    except Exception as error:
        raise domain_problem(request, error) from None


@router.patch(
    "/households/{household_id}/account-grants/{grant_id}",
    response_model=AccountGrantRecord,
)
def update_account_grant(
    request: Request,
    household_id: str,
    grant_id: str,
    body: UpdateAccountGrantRequest,
    context: HouseholdsContext = Depends(require_households_context),  # noqa: B008
) -> AccountGrantRecord:
    try:
        return context.service.update_grant(
            user_id=context.user_id,
            household_id=household_id,
            grant_id=grant_id,
            request=body,
        )
    except Exception as error:
        raise domain_problem(request, error) from None


@router.delete(
    "/households/{household_id}/account-grants/{grant_id}",
    status_code=204,
)
def revoke_account_grant(
    request: Request,
    household_id: str,
    grant_id: str,
    context: HouseholdsContext = Depends(require_households_context),  # noqa: B008
) -> Response:
    try:
        context.service.revoke_grant(
            user_id=context.user_id, household_id=household_id, grant_id=grant_id
        )
    except Exception as error:
        raise domain_problem(request, error) from None
    return Response(status_code=204)


@router.get(
    "/households/{household_id}/accounts",
    response_model=SharedAccountListResponse,
)
def list_shared_accounts(
    request: Request,
    household_id: str,
    context: HouseholdsContext = Depends(require_households_context),  # noqa: B008
) -> SharedAccountListResponse:
    try:
        accounts = context.service.list_shared_accounts(
            user_id=context.user_id, household_id=household_id
        )
    except Exception as error:
        raise domain_problem(request, error) from None
    return SharedAccountListResponse(accounts=accounts)
