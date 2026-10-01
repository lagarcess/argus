"""Resolve exact logical activity revisions before applying caller visibility."""

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from typing import Any

from psycopg import Connection

from .errors import AccountNotFound
from .loop import ExpenseRecord, ExpenseRevision
from .money_postgres import load_owner
from .repository import StoredAccount

Leg = tuple[StoredAccount, ExpenseRecord, ExpenseRevision]
History = dict[str, dict[int, list[Leg]]]


@dataclass(frozen=True)
class Group:
    activity_id: str
    owner_id: str
    current_revision: int


@dataclass(frozen=True)
class Membership:
    activity_id: str
    owner_id: str
    activity_revision: int
    record_id: str
    record_revision: int
    role: str


@dataclass(frozen=True)
class ResolvedGroups:
    records: list[StoredAccount]
    current: dict[str, int]
    history: History

    def current_visible(self, account_ids: Collection[str]) -> dict[str, int]:
        return {
            aid: revision
            for aid, revision in self.current.items()
            if any(
                stored.account.id in account_ids
                for stored, _, __ in self.history[aid][revision]
            )
        }


def resolve(
    records: list[StoredAccount],
    groups: Iterable[Group],
    memberships: Iterable[Membership],
) -> ResolvedGroups:
    headers = {group.activity_id: group for group in groups}
    revisions = {
        (stored.account.user_id, record.id, revision.revision): (stored, record, revision)
        for stored in records
        for record in stored.expenses
        for revision in record.revisions
    }
    history: History = {}
    for member in memberships:
        group = headers.get(member.activity_id)
        if group is None or member.activity_revision > group.current_revision:
            continue
        leg = revisions.get((member.owner_id, member.record_id, member.record_revision))
        if leg is None or member.owner_id != group.owner_id:
            raise AccountNotFound()
        _, record, revision = leg
        if (
            not revision.active
            or (revision.activity_id or record.id) != member.activity_id
            or (revision.activity_revision or revision.revision)
            != member.activity_revision
            or revision.role != member.role
        ):
            raise AccountNotFound()
        history.setdefault(member.activity_id, {}).setdefault(
            member.activity_revision, []
        ).append(leg)
    for aid, group in headers.items():
        if group.current_revision not in history.get(aid, {}):
            raise AccountNotFound()
        for legs in history[aid].values():
            roles = [revision.role for _, __, revision in legs]
            if sorted(roles) not in [["single"], ["destination", "source"]]:
                raise AccountNotFound()
    return ResolvedGroups(
        records, {aid: group.current_revision for aid, group in headers.items()}, history
    )


def load(
    repository: Any, connection: Connection, owner_ids: Collection[str]
) -> ResolvedGroups:
    owners = sorted(set(owner_ids))
    records = [
        stored for owner in owners for stored in load_owner(repository, connection, owner)
    ]
    rows = connection.execute(
        """select g.id,g.user_id,g.current_revision,m.activity_revision,
        m.record_id,m.record_revision,m.role
        from public.financial_activity_groups g
        left join public.financial_activity_memberships m
        on m.activity_id=g.id and m.user_id=g.user_id
        where g.user_id=any(%s::uuid[])
        order by g.id,m.activity_revision,m.role""",
        (owners,),
    ).fetchall()
    headers = {}
    memberships = []
    for aid, owner, current, revision, rid, record_revision, role in rows:
        identifier, owner_id = str(aid), str(owner)
        headers[identifier] = Group(identifier, owner_id, current)
        if revision is not None:
            memberships.append(
                Membership(
                    identifier, owner_id, revision, str(rid), record_revision, role
                )
            )
    return resolve(records, headers.values(), memberships)
