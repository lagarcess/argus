"""In-memory household store for hermetic tests and memory persistence mode."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import uuid4

from argus.domain.household.errors import (
    AccountNotOwned,
    AdminRequired,
    GrantNotFound,
    HouseholdClosed,
    HouseholdNotFound,
    InvitationConsumed,
    InvitationExpired,
    InvitationNotFound,
    InvitationRevoked,
    MemberNotFound,
    MustTransferOrClose,
)
from argus.domain.household.schemas import (
    AccountGrantRecord,
    HouseholdRecord,
    InvitationCreated,
    MemberRecord,
    OwnedAccountRef,
    Permission,
    SharedAccountView,
)

INVITE_TTL = timedelta(days=7)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass
class _Member:
    user_id: str
    joined_at: datetime
    left_at: datetime | None = None


@dataclass
class _Invitation:
    id: str
    household_id: str
    token_hash: str
    created_by: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    accepted_by: str | None = None
    accepted_at: datetime | None = None


@dataclass
class _Grant:
    id: str
    household_id: str
    account_id: str
    owner_user_id: str
    permission: Permission
    created_at: datetime
    revoked_at: datetime | None = None


@dataclass
class _Household:
    id: str
    name: str | None
    status: str
    created_by: str
    admin_user_id: str
    created_at: datetime
    closed_at: datetime | None = None
    members: list[_Member] = field(default_factory=list)
    invitations: list[_Invitation] = field(default_factory=list)
    grants: list[_Grant] = field(default_factory=list)


class AccountLookup(Protocol):
    def owned_account(self, *, user_id: str, account_id: str) -> OwnedAccountRef | None: ...

    def account_by_id(self, *, account_id: str) -> OwnedAccountRef | None: ...


class InMemoryHouseholdRepository:
    def __init__(
        self,
        accounts: AccountLookup,
        *,
        clock=_utcnow,  # noqa: ANN001
    ) -> None:
        self._accounts = accounts
        self._clock = clock
        self._households: dict[str, _Household] = {}
        self._invites_by_hash: dict[str, str] = {}

    def create_household(self, *, user_id: str, name: str | None) -> HouseholdRecord:
        now = self._clock()
        hid = str(uuid4())
        household = _Household(
            id=hid,
            name=_trim_name(name),
            status="active",
            created_by=user_id,
            admin_user_id=user_id,
            created_at=now,
            members=[_Member(user_id=user_id, joined_at=now)],
        )
        self._households[hid] = household
        return self._view(household)

    def list_households(self, *, user_id: str) -> list[HouseholdRecord]:
        return [
            self._view(household)
            for household in self._households.values()
            if household.status == "active"
            and any(m.user_id == user_id and m.left_at is None for m in household.members)
        ]

    def get_household(self, *, user_id: str, household_id: str) -> HouseholdRecord:
        household = self._require_member(user_id=user_id, household_id=household_id)
        return self._view(household)

    def create_invitation(self, *, user_id: str, household_id: str) -> InvitationCreated:
        household = self._require_admin(user_id=user_id, household_id=household_id)
        now = self._clock()
        token = secrets.token_urlsafe(32)
        invite = _Invitation(
            id=str(uuid4()),
            household_id=household.id,
            token_hash=hash_token(token),
            created_by=user_id,
            created_at=now,
            expires_at=now + INVITE_TTL,
        )
        household.invitations.append(invite)
        self._invites_by_hash[invite.token_hash] = household.id
        return InvitationCreated(
            id=invite.id,
            household_id=household.id,
            expires_at=invite.expires_at,
            token=token,
        )

    def revoke_invitation(
        self, *, user_id: str, household_id: str, invitation_id: str
    ) -> None:
        household = self._require_admin(user_id=user_id, household_id=household_id)
        invite = next((i for i in household.invitations if i.id == invitation_id), None)
        if invite is None:
            raise InvitationNotFound()
        if invite.accepted_at is not None:
            raise InvitationConsumed()
        if invite.revoked_at is None:
            invite.revoked_at = self._clock()

    def accept_invitation(self, *, user_id: str, token: str) -> HouseholdRecord:
        token_hash = hash_token(token)
        household_id = self._invites_by_hash.get(token_hash)
        if household_id is None:
            raise InvitationNotFound()
        household = self._households[household_id]
        invite = next(i for i in household.invitations if i.token_hash == token_hash)
        now = self._clock()
        if invite.revoked_at is not None:
            raise InvitationRevoked()
        if invite.expires_at <= now:
            raise InvitationExpired()
        if invite.accepted_by is not None and invite.accepted_by != user_id:
            raise InvitationConsumed()
        if household.status != "active":
            raise HouseholdClosed()

        active = next(
            (m for m in household.members if m.user_id == user_id and m.left_at is None),
            None,
        )
        if active is not None:
            # Safe same-recipient retry: already a member.
            if invite.accepted_by is None:
                invite.accepted_by = user_id
                invite.accepted_at = now
            return self._view(household)

        if invite.accepted_by is not None:
            # Token already consumed by this user who later left; require a fresh invite.
            raise InvitationConsumed()

        invite.accepted_by = user_id
        invite.accepted_at = now
        household.members.append(_Member(user_id=user_id, joined_at=now))
        return self._view(household)

    def leave(self, *, user_id: str, household_id: str) -> None:
        household = self._require_member(user_id=user_id, household_id=household_id)
        if household.admin_user_id == user_id:
            others = [
                m
                for m in household.members
                if m.user_id != user_id and m.left_at is None
            ]
            if others:
                raise MustTransferOrClose()
            self.close(user_id=user_id, household_id=household_id)
            return
        self._end_membership(household, user_id)

    def remove_member(
        self, *, admin_user_id: str, household_id: str, member_user_id: str
    ) -> None:
        household = self._require_admin(user_id=admin_user_id, household_id=household_id)
        if member_user_id == admin_user_id:
            raise MustTransferOrClose()
        member = next(
            (
                m
                for m in household.members
                if m.user_id == member_user_id and m.left_at is None
            ),
            None,
        )
        if member is None:
            raise MemberNotFound()
        self._end_membership(household, member_user_id)

    def transfer_admin(
        self, *, admin_user_id: str, household_id: str, new_admin_user_id: str
    ) -> HouseholdRecord:
        household = self._require_admin(user_id=admin_user_id, household_id=household_id)
        if new_admin_user_id == admin_user_id:
            return self._view(household)
        member = next(
            (
                m
                for m in household.members
                if m.user_id == new_admin_user_id and m.left_at is None
            ),
            None,
        )
        if member is None:
            raise MemberNotFound()
        household.admin_user_id = new_admin_user_id
        return self._view(household)

    def close(self, *, user_id: str, household_id: str) -> HouseholdRecord:
        household = self._require_admin(user_id=user_id, household_id=household_id)
        now = self._clock()
        household.status = "closed"
        household.closed_at = now
        for member in household.members:
            if member.left_at is None:
                member.left_at = now
        for invite in household.invitations:
            if invite.revoked_at is None and invite.accepted_at is None:
                invite.revoked_at = now
        for grant in household.grants:
            if grant.revoked_at is None:
                grant.revoked_at = now
        return self._view(household)

    def create_grant(
        self,
        *,
        user_id: str,
        household_id: str,
        account_id: str,
        permission: Permission,
    ) -> AccountGrantRecord:
        household = self._require_member(user_id=user_id, household_id=household_id)
        account = self._accounts.owned_account(user_id=user_id, account_id=account_id)
        if account is None:
            raise AccountNotOwned()
        existing = next(
            (
                g
                for g in household.grants
                if g.account_id == account_id and g.revoked_at is None
            ),
            None,
        )
        now = self._clock()
        if existing is not None:
            if existing.owner_user_id != user_id:
                raise AccountNotOwned()
            existing.permission = permission
            return self._grant_view(existing)
        grant = _Grant(
            id=str(uuid4()),
            household_id=household.id,
            account_id=account_id,
            owner_user_id=user_id,
            permission=permission,
            created_at=now,
        )
        household.grants.append(grant)
        return self._grant_view(grant)

    def update_grant(
        self,
        *,
        user_id: str,
        household_id: str,
        grant_id: str,
        permission: Permission,
    ) -> AccountGrantRecord:
        household = self._require_member(user_id=user_id, household_id=household_id)
        grant = next(
            (g for g in household.grants if g.id == grant_id and g.revoked_at is None),
            None,
        )
        if grant is None:
            raise GrantNotFound()
        if grant.owner_user_id != user_id:
            raise AccountNotOwned()
        grant.permission = permission
        return self._grant_view(grant)

    def revoke_grant(
        self, *, user_id: str, household_id: str, grant_id: str
    ) -> None:
        household = self._require_member(user_id=user_id, household_id=household_id)
        grant = next(
            (g for g in household.grants if g.id == grant_id and g.revoked_at is None),
            None,
        )
        if grant is None:
            raise GrantNotFound()
        if grant.owner_user_id != user_id and household.admin_user_id != user_id:
            raise AdminRequired()
        grant.revoked_at = self._clock()

    def list_shared_accounts(
        self, *, user_id: str, household_id: str
    ) -> list[SharedAccountView]:
        household = self._require_member(user_id=user_id, household_id=household_id)
        views: list[SharedAccountView] = []
        for grant in household.grants:
            if grant.revoked_at is not None:
                continue
            account = self._accounts.account_by_id(account_id=grant.account_id)
            if account is None or account.user_id != grant.owner_user_id:
                continue
            views.append(
                SharedAccountView(
                    grant_id=grant.id,
                    account_id=account.id,
                    owner_user_id=account.user_id,
                    permission=grant.permission,
                    type=account.type,
                    currency=account.currency,
                    nickname=account.nickname,
                    archived=account.archived,
                    ownership_share_bps=account.ownership_share_bps,
                )
            )
        views.sort(key=lambda item: (item.owner_user_id, item.account_id))
        return views

    def _end_membership(self, household: _Household, user_id: str) -> None:
        now = self._clock()
        for member in household.members:
            if member.user_id == user_id and member.left_at is None:
                member.left_at = now
        for grant in household.grants:
            if grant.owner_user_id == user_id and grant.revoked_at is None:
                grant.revoked_at = now

    def _require_member(self, *, user_id: str, household_id: str) -> _Household:
        household = self._households.get(household_id)
        if household is None:
            raise HouseholdNotFound()
        if household.status != "active":
            raise HouseholdNotFound()
        if not any(m.user_id == user_id and m.left_at is None for m in household.members):
            raise HouseholdNotFound()
        return household

    def _require_admin(self, *, user_id: str, household_id: str) -> _Household:
        household = self._require_member(user_id=user_id, household_id=household_id)
        if household.admin_user_id != user_id:
            raise AdminRequired()
        return household

    def _view(self, household: _Household) -> HouseholdRecord:
        members = [
            MemberRecord(
                user_id=m.user_id,
                role="admin" if m.user_id == household.admin_user_id else "member",
                joined_at=m.joined_at,
            )
            for m in household.members
            if m.left_at is None
        ]
        members.sort(key=lambda item: item.joined_at)
        return HouseholdRecord(
            id=household.id,
            name=household.name,
            status=household.status,  # type: ignore[arg-type]
            admin_user_id=household.admin_user_id,
            created_by=household.created_by,
            created_at=household.created_at,
            closed_at=household.closed_at,
            members=members,
        )

    @staticmethod
    def _grant_view(grant: _Grant) -> AccountGrantRecord:
        return AccountGrantRecord(
            id=grant.id,
            household_id=grant.household_id,
            account_id=grant.account_id,
            owner_user_id=grant.owner_user_id,
            permission=grant.permission,
            created_at=grant.created_at,
            revoked_at=grant.revoked_at,
        )


def _trim_name(name: str | None) -> str | None:
    if name is None:
        return None
    trimmed = name.strip()
    return trimmed or None


def _ref_from_stored(stored) -> OwnedAccountRef:  # noqa: ANN001
    facts = stored.account
    return OwnedAccountRef(
        id=facts.id,
        user_id=facts.user_id,
        type=facts.type,
        currency=facts.currency,
        nickname=facts.nickname,
        archived=facts.archived,
        ownership_share_bps=facts.ownership_share_bps,
    )


class FinancialAccountLookup:
    """Adapts a financial-account repository into OwnedAccountRef lookups."""

    def __init__(self, repository) -> None:  # noqa: ANN001
        self._repository = repository

    def owned_account(self, *, user_id: str, account_id: str) -> OwnedAccountRef | None:
        stored = self._repository.get_account(user_id=user_id, account_id=account_id)
        if stored is None:
            return None
        return _ref_from_stored(stored)

    def account_by_id(self, *, account_id: str) -> OwnedAccountRef | None:
        getter = getattr(self._repository, "get_any_account", None)
        if getter is None:
            return None
        stored = getter(account_id=account_id)
        if stored is None:
            return None
        return _ref_from_stored(stored)
