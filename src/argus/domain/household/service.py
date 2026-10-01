"""Household application service: thin facade over the store."""

from __future__ import annotations

from argus.domain.household.schemas import (
    AccountGrantRecord,
    CreateAccountGrantRequest,
    CreateHouseholdRequest,
    HouseholdRecord,
    InvitationCreated,
    Permission,
    SharedAccountView,
    UpdateAccountGrantRequest,
)


class HouseholdService:
    def __init__(self, repository) -> None:  # noqa: ANN001
        self._repository = repository

    def create(self, *, user_id: str, request: CreateHouseholdRequest) -> HouseholdRecord:
        return self._repository.create_household(user_id=user_id, name=request.name)

    def list(self, *, user_id: str) -> list[HouseholdRecord]:
        return self._repository.list_households(user_id=user_id)

    def get(self, *, user_id: str, household_id: str) -> HouseholdRecord:
        return self._repository.get_household(user_id=user_id, household_id=household_id)

    def invite(self, *, user_id: str, household_id: str) -> InvitationCreated:
        return self._repository.create_invitation(
            user_id=user_id, household_id=household_id
        )

    def revoke_invitation(
        self, *, user_id: str, household_id: str, invitation_id: str
    ) -> None:
        self._repository.revoke_invitation(
            user_id=user_id, household_id=household_id, invitation_id=invitation_id
        )

    def accept(self, *, user_id: str, token: str) -> HouseholdRecord:
        return self._repository.accept_invitation(user_id=user_id, token=token)

    def leave(self, *, user_id: str, household_id: str) -> None:
        self._repository.leave(user_id=user_id, household_id=household_id)

    def remove_member(
        self, *, user_id: str, household_id: str, member_user_id: str
    ) -> None:
        self._repository.remove_member(
            admin_user_id=user_id,
            household_id=household_id,
            member_user_id=member_user_id,
        )

    def transfer_admin(
        self, *, user_id: str, household_id: str, new_admin_user_id: str
    ) -> HouseholdRecord:
        return self._repository.transfer_admin(
            admin_user_id=user_id,
            household_id=household_id,
            new_admin_user_id=new_admin_user_id,
        )

    def close(self, *, user_id: str, household_id: str) -> HouseholdRecord:
        return self._repository.close(user_id=user_id, household_id=household_id)

    def create_grant(
        self,
        *,
        user_id: str,
        household_id: str,
        request: CreateAccountGrantRequest,
    ) -> AccountGrantRecord:
        return self._repository.create_grant(
            user_id=user_id,
            household_id=household_id,
            account_id=request.account_id,
            permission=request.permission,
        )

    def update_grant(
        self,
        *,
        user_id: str,
        household_id: str,
        grant_id: str,
        request: UpdateAccountGrantRequest,
    ) -> AccountGrantRecord:
        return self._repository.update_grant(
            user_id=user_id,
            household_id=household_id,
            grant_id=grant_id,
            permission=request.permission,
        )

    def revoke_grant(
        self, *, user_id: str, household_id: str, grant_id: str
    ) -> None:
        self._repository.revoke_grant(
            user_id=user_id, household_id=household_id, grant_id=grant_id
        )

    def list_shared_accounts(
        self, *, user_id: str, household_id: str
    ) -> list[SharedAccountView]:
        return self._repository.list_shared_accounts(
            user_id=user_id, household_id=household_id
        )

    def permission_for(
        self, *, user_id: str, household_id: str, account_id: str
    ) -> Permission | None:
        for item in self.list_shared_accounts(user_id=user_id, household_id=household_id):
            if item.account_id == account_id:
                return item.permission
        return None
