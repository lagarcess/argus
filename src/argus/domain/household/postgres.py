"""Postgres household store over the financial DATABASE_URL pool."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from psycopg_pool import ConnectionPool

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
from argus.domain.household.repository import (
    INVITE_TTL,
    FinancialAccountLookup,
    hash_token,
)
from argus.domain.household.schemas import (
    AccountGrantRecord,
    HouseholdRecord,
    InvitationCreated,
    MemberRecord,
    Permission,
    SharedAccountView,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PostgresHouseholdRepository:
    def __init__(
        self,
        pool: ConnectionPool,
        accounts: FinancialAccountLookup,
        *,
        clock=_utcnow,  # noqa: ANN001
    ) -> None:
        self._pool = pool
        self._accounts = accounts
        self._clock = clock

    def create_household(self, *, user_id: str, name: str | None) -> HouseholdRecord:
        now = self._clock()
        hid = str(uuid4())
        trimmed = name.strip() if name and name.strip() else None
        with self._pool.connection() as connection:
            with connection.transaction():
                connection.execute(
                    "insert into public.households"
                    " (id, name, status, created_by, admin_user_id, created_at)"
                    " values (%s, %s, 'active', %s, %s, %s)",
                    (hid, trimmed, user_id, user_id, now),
                )
                connection.execute(
                    "insert into public.household_members"
                    " (id, household_id, user_id, joined_at)"
                    " values (%s, %s, %s, %s)",
                    (str(uuid4()), hid, user_id, now),
                )
            return self._load(connection, user_id=user_id, household_id=hid)

    def list_households(self, *, user_id: str) -> list[HouseholdRecord]:
        with self._pool.connection() as connection:
            rows = connection.execute(
                "select h.id from public.households h"
                " join public.household_members m on m.household_id = h.id"
                " where h.status = 'active' and m.user_id = %s and m.left_at is null"
                " order by h.created_at asc",
                (user_id,),
            ).fetchall()
            return [
                self._load(connection, user_id=user_id, household_id=str(row[0]))
                for row in rows
            ]

    def get_household(self, *, user_id: str, household_id: str) -> HouseholdRecord:
        with self._pool.connection() as connection:
            return self._load(connection, user_id=user_id, household_id=household_id)

    def create_invitation(self, *, user_id: str, household_id: str) -> InvitationCreated:
        with self._pool.connection() as connection:
            with connection.transaction():
                self._require_admin(connection, user_id=user_id, household_id=household_id)
                now = self._clock()
                token = secrets.token_urlsafe(32)
                invite_id = str(uuid4())
                expires = now + INVITE_TTL
                connection.execute(
                    "insert into public.household_invitations"
                    " (id, household_id, token_hash, created_by, created_at, expires_at)"
                    " values (%s, %s, %s, %s, %s, %s)",
                    (invite_id, household_id, hash_token(token), user_id, now, expires),
                )
                return InvitationCreated(
                    id=invite_id,
                    household_id=household_id,
                    expires_at=expires,
                    token=token,
                )

    def revoke_invitation(
        self, *, user_id: str, household_id: str, invitation_id: str
    ) -> None:
        with self._pool.connection() as connection:
            with connection.transaction():
                self._require_admin(connection, user_id=user_id, household_id=household_id)
                row = connection.execute(
                    "select accepted_at, revoked_at from public.household_invitations"
                    " where id = %s and household_id = %s",
                    (invitation_id, household_id),
                ).fetchone()
                if row is None:
                    raise InvitationNotFound()
                if row[0] is not None:
                    raise InvitationConsumed()
                if row[1] is None:
                    connection.execute(
                        "update public.household_invitations set revoked_at = %s"
                        " where id = %s",
                        (self._clock(), invitation_id),
                    )

    def accept_invitation(self, *, user_id: str, token: str) -> HouseholdRecord:
        token_hash = hash_token(token)
        with self._pool.connection() as connection:
            with connection.transaction():
                invite = connection.execute(
                    "select id, household_id, expires_at, revoked_at, accepted_by"
                    " from public.household_invitations where token_hash = %s"
                    " for update",
                    (token_hash,),
                ).fetchone()
                if invite is None:
                    raise InvitationNotFound()
                invite_id, household_id, expires_at, revoked_at, accepted_by = invite
                household_id = str(household_id)
                now = self._clock()
                if revoked_at is not None:
                    raise InvitationRevoked()
                if expires_at <= now:
                    raise InvitationExpired()
                if accepted_by is not None and str(accepted_by) != user_id:
                    raise InvitationConsumed()
                status = connection.execute(
                    "select status from public.households where id = %s for update",
                    (household_id,),
                ).fetchone()
                if status is None or status[0] != "active":
                    raise HouseholdClosed()
                active = connection.execute(
                    "select 1 from public.household_members"
                    " where household_id = %s and user_id = %s and left_at is null",
                    (household_id, user_id),
                ).fetchone()
                if active is not None:
                    if accepted_by is None:
                        connection.execute(
                            "update public.household_invitations"
                            " set accepted_by = %s, accepted_at = %s where id = %s",
                            (user_id, now, invite_id),
                        )
                    return self._load(
                        connection, user_id=user_id, household_id=household_id
                    )
                if accepted_by is not None:
                    raise InvitationConsumed()
                connection.execute(
                    "update public.household_invitations"
                    " set accepted_by = %s, accepted_at = %s where id = %s",
                    (user_id, now, invite_id),
                )
                connection.execute(
                    "insert into public.household_members"
                    " (id, household_id, user_id, joined_at) values (%s, %s, %s, %s)",
                    (str(uuid4()), household_id, user_id, now),
                )
                return self._load(
                    connection, user_id=user_id, household_id=household_id
                )

    def leave(self, *, user_id: str, household_id: str) -> None:
        with self._pool.connection() as connection:
            with connection.transaction():
                household = self._require_member_row(
                    connection, user_id=user_id, household_id=household_id
                )
                if str(household["admin_user_id"]) == user_id:
                    others = connection.execute(
                        "select 1 from public.household_members"
                        " where household_id = %s and user_id <> %s and left_at is null"
                        " limit 1",
                        (household_id, user_id),
                    ).fetchone()
                    if others:
                        raise MustTransferOrClose()
                    self._close_locked(connection, household_id=household_id)
                    return
                self._end_membership(connection, household_id=household_id, user_id=user_id)

    def remove_member(
        self, *, admin_user_id: str, household_id: str, member_user_id: str
    ) -> None:
        with self._pool.connection() as connection:
            with connection.transaction():
                self._require_admin(
                    connection, user_id=admin_user_id, household_id=household_id
                )
                if member_user_id == admin_user_id:
                    raise MustTransferOrClose()
                row = connection.execute(
                    "select 1 from public.household_members"
                    " where household_id = %s and user_id = %s and left_at is null",
                    (household_id, member_user_id),
                ).fetchone()
                if row is None:
                    raise MemberNotFound()
                self._end_membership(
                    connection, household_id=household_id, user_id=member_user_id
                )

    def transfer_admin(
        self, *, admin_user_id: str, household_id: str, new_admin_user_id: str
    ) -> HouseholdRecord:
        with self._pool.connection() as connection:
            with connection.transaction():
                self._require_admin(
                    connection, user_id=admin_user_id, household_id=household_id
                )
                if new_admin_user_id != admin_user_id:
                    row = connection.execute(
                        "select 1 from public.household_members"
                        " where household_id = %s and user_id = %s and left_at is null",
                        (household_id, new_admin_user_id),
                    ).fetchone()
                    if row is None:
                        raise MemberNotFound()
                    connection.execute(
                        "update public.households set admin_user_id = %s where id = %s",
                        (new_admin_user_id, household_id),
                    )
                return self._load(
                    connection, user_id=admin_user_id, household_id=household_id
                )

    def close(self, *, user_id: str, household_id: str) -> HouseholdRecord:
        with self._pool.connection() as connection:
            with connection.transaction():
                self._require_admin(connection, user_id=user_id, household_id=household_id)
                self._close_locked(connection, household_id=household_id)
                # Caller is no longer an active member after close; return closed view.
                row = connection.execute(
                    "select id, name, status, admin_user_id, created_by, created_at, closed_at"
                    " from public.households where id = %s",
                    (household_id,),
                ).fetchone()
                assert row is not None
                return HouseholdRecord(
                    id=str(row[0]),
                    name=row[1],
                    status=row[2],
                    admin_user_id=str(row[3]),
                    created_by=str(row[4]),
                    created_at=row[5],
                    closed_at=row[6],
                    members=[],
                )

    def create_grant(
        self,
        *,
        user_id: str,
        household_id: str,
        account_id: str,
        permission: Permission,
    ) -> AccountGrantRecord:
        with self._pool.connection() as connection:
            with connection.transaction():
                self._require_member_row(
                    connection, user_id=user_id, household_id=household_id
                )
                account = self._accounts.owned_account(
                    user_id=user_id, account_id=account_id
                )
                if account is None:
                    raise AccountNotOwned()
                existing = connection.execute(
                    "select id, owner_user_id, created_at from public.household_account_grants"
                    " where household_id = %s and account_id = %s and revoked_at is null"
                    " for update",
                    (household_id, account_id),
                ).fetchone()
                now = self._clock()
                if existing is not None:
                    if str(existing[1]) != user_id:
                        raise AccountNotOwned()
                    connection.execute(
                        "update public.household_account_grants set permission = %s"
                        " where id = %s",
                        (permission, existing[0]),
                    )
                    return AccountGrantRecord(
                        id=str(existing[0]),
                        household_id=household_id,
                        account_id=account_id,
                        owner_user_id=user_id,
                        permission=permission,
                        created_at=existing[2],
                    )
                grant_id = str(uuid4())
                connection.execute(
                    "insert into public.household_account_grants"
                    " (id, household_id, account_id, owner_user_id, permission, created_at)"
                    " values (%s, %s, %s, %s, %s, %s)",
                    (grant_id, household_id, account_id, user_id, permission, now),
                )
                return AccountGrantRecord(
                    id=grant_id,
                    household_id=household_id,
                    account_id=account_id,
                    owner_user_id=user_id,
                    permission=permission,
                    created_at=now,
                )

    def update_grant(
        self,
        *,
        user_id: str,
        household_id: str,
        grant_id: str,
        permission: Permission,
    ) -> AccountGrantRecord:
        with self._pool.connection() as connection:
            with connection.transaction():
                self._require_member_row(
                    connection, user_id=user_id, household_id=household_id
                )
                row = connection.execute(
                    "select account_id, owner_user_id, created_at"
                    " from public.household_account_grants"
                    " where id = %s and household_id = %s and revoked_at is null"
                    " for update",
                    (grant_id, household_id),
                ).fetchone()
                if row is None:
                    raise GrantNotFound()
                if str(row[1]) != user_id:
                    raise AccountNotOwned()
                connection.execute(
                    "update public.household_account_grants set permission = %s"
                    " where id = %s",
                    (permission, grant_id),
                )
                return AccountGrantRecord(
                    id=grant_id,
                    household_id=household_id,
                    account_id=str(row[0]),
                    owner_user_id=user_id,
                    permission=permission,
                    created_at=row[2],
                )

    def revoke_grant(
        self, *, user_id: str, household_id: str, grant_id: str
    ) -> None:
        with self._pool.connection() as connection:
            with connection.transaction():
                household = self._require_member_row(
                    connection, user_id=user_id, household_id=household_id
                )
                row = connection.execute(
                    "select owner_user_id from public.household_account_grants"
                    " where id = %s and household_id = %s and revoked_at is null"
                    " for update",
                    (grant_id, household_id),
                ).fetchone()
                if row is None:
                    raise GrantNotFound()
                if str(row[0]) != user_id and str(household["admin_user_id"]) != user_id:
                    raise AdminRequired()
                connection.execute(
                    "update public.household_account_grants set revoked_at = %s"
                    " where id = %s",
                    (self._clock(), grant_id),
                )

    def list_shared_accounts(
        self, *, user_id: str, household_id: str
    ) -> list[SharedAccountView]:
        with self._pool.connection() as connection:
            self._require_member_row(
                connection, user_id=user_id, household_id=household_id
            )
            rows = connection.execute(
                "select g.id, g.account_id, g.owner_user_id, g.permission,"
                " a.type, a.currency, a.nickname, a.archived, a.ownership_share_bps"
                " from public.household_account_grants g"
                " join public.financial_accounts a"
                "   on a.id = g.account_id and a.user_id = g.owner_user_id"
                " where g.household_id = %s and g.revoked_at is null"
                " order by g.owner_user_id, g.account_id",
                (household_id,),
            ).fetchall()
            return [
                SharedAccountView(
                    grant_id=str(row[0]),
                    account_id=str(row[1]),
                    owner_user_id=str(row[2]),
                    permission=row[3],
                    type=row[4],
                    currency=row[5],
                    nickname=row[6],
                    archived=row[7],
                    ownership_share_bps=row[8],
                )
                for row in rows
            ]

    def _close_locked(self, connection, *, household_id: str) -> None:  # noqa: ANN001
        now = self._clock()
        connection.execute(
            "update public.households set status = 'closed', closed_at = %s"
            " where id = %s and status = 'active'",
            (now, household_id),
        )
        connection.execute(
            "update public.household_members set left_at = %s"
            " where household_id = %s and left_at is null",
            (now, household_id),
        )
        connection.execute(
            "update public.household_invitations set revoked_at = %s"
            " where household_id = %s and revoked_at is null and accepted_at is null",
            (now, household_id),
        )
        connection.execute(
            "update public.household_account_grants set revoked_at = %s"
            " where household_id = %s and revoked_at is null",
            (now, household_id),
        )

    def _end_membership(
        self, connection, *, household_id: str, user_id: str  # noqa: ANN001
    ) -> None:
        now = self._clock()
        connection.execute(
            "update public.household_members set left_at = %s"
            " where household_id = %s and user_id = %s and left_at is null",
            (now, household_id, user_id),
        )
        connection.execute(
            "update public.household_account_grants set revoked_at = %s"
            " where household_id = %s and owner_user_id = %s and revoked_at is null",
            (now, household_id, user_id),
        )

    def _require_admin(
        self, connection, *, user_id: str, household_id: str  # noqa: ANN001
    ) -> dict[str, Any]:
        household = self._require_member_row(
            connection, user_id=user_id, household_id=household_id
        )
        if str(household["admin_user_id"]) != user_id:
            raise AdminRequired()
        return household

    def _require_member_row(
        self, connection, *, user_id: str, household_id: str  # noqa: ANN001
    ) -> dict[str, Any]:
        row = connection.execute(
            "select h.id, h.name, h.status, h.admin_user_id, h.created_by,"
            " h.created_at, h.closed_at"
            " from public.households h"
            " join public.household_members m on m.household_id = h.id"
            " where h.id = %s and h.status = 'active'"
            "   and m.user_id = %s and m.left_at is null"
            " for update of h",
            (household_id, user_id),
        ).fetchone()
        if row is None:
            raise HouseholdNotFound()
        return {
            "id": str(row[0]),
            "name": row[1],
            "status": row[2],
            "admin_user_id": str(row[3]),
            "created_by": str(row[4]),
            "created_at": row[5],
            "closed_at": row[6],
        }

    def _load(
        self, connection, *, user_id: str, household_id: str  # noqa: ANN001
    ) -> HouseholdRecord:
        household = self._require_member_row(
            connection, user_id=user_id, household_id=household_id
        )
        members = connection.execute(
            "select user_id, joined_at from public.household_members"
            " where household_id = %s and left_at is null order by joined_at asc",
            (household_id,),
        ).fetchall()
        return HouseholdRecord(
            id=household["id"],
            name=household["name"],
            status=household["status"],
            admin_user_id=household["admin_user_id"],
            created_by=household["created_by"],
            created_at=household["created_at"],
            closed_at=household["closed_at"],
            members=[
                MemberRecord(
                    user_id=str(row[0]),
                    role=(
                        "admin"
                        if str(row[0]) == household["admin_user_id"]
                        else "member"
                    ),
                    joined_at=row[1],
                )
                for row in members
            ],
        )
