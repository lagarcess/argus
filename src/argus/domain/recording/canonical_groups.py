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
    record_owner_id: str | None = None


@dataclass(frozen=True)
class ResolvedGroups:
    records: list[StoredAccount]
    current: dict[str, int]
    history: History
    owners: dict[str, str]

    def current_visible(self, account_ids: Collection[str]) -> dict[str, int]:
        return {
            aid: revision
            for aid, revision in self.current.items()
            if any(
                stored.account.id in account_ids
                for stored, _, __ in self.history[aid][revision]
            )
        }


class VisibleAccounts(list):
    """Owned account positions with privileged group facts kept service-internal."""

    def __init__(self, records: list[StoredAccount], canonical: ResolvedGroups):
        super().__init__(records)
        self.canonical = canonical


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
        leg = revisions.get(
            (
                member.record_owner_id or member.owner_id,
                member.record_id,
                member.record_revision,
            )
        )
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
        records,
        {aid: group.current_revision for aid, group in headers.items()},
        history,
        {aid: group.owner_id for aid, group in headers.items()},
    )


def projected(canonical: ResolvedGroups, money: Any, now: Any) -> ResolvedGroups:
    """Advance one reviewed group, preserving exact memberships of other groups."""
    from dataclasses import replace

    from .loop_storage import apply

    records = []
    for stored in canonical.records:
        aid = stored.account.id
        if aid in money.mutations:
            stored = apply(stored, money.mutations[aid], now)
        elif aid in money.affected:
            stored = replace(
                stored,
                account=replace(stored.account, version=stored.account.version + 1),
            )
        records.append(stored)
    headers = {
        aid: Group(aid, canonical.owners[aid], revision)
        for aid, revision in canonical.current.items()
    }
    primary = next(
        stored.account.user_id
        for stored in records
        if stored.account.id in money.mutations
        and money.mutations[stored.account.id].record.current.active
        and money.mutations[stored.account.id].record.current.role != "destination"
    )
    owner = canonical.owners.get(money.activity_id, primary)
    headers[money.activity_id] = Group(money.activity_id, owner, money.revision)
    memberships = [
        Membership(
            aid,
            canonical.owners[aid],
            number,
            record.id,
            rev.revision,
            rev.role,
            stored.account.user_id,
        )
        for aid, history in canonical.history.items()
        for number, legs in history.items()
        for stored, record, rev in legs
    ]
    memberships.extend(
        Membership(
            money.activity_id,
            owner,
            money.revision,
            mutation.record.id,
            mutation.record.current.revision,
            mutation.record.current.role,
            next(s.account.user_id for s in records if s.account.id == aid),
        )
        for aid, mutation in money.mutations.items()
        if mutation.record.current.active
    )
    return resolve(records, headers.values(), memberships)


def owner_closure(connection: Connection, owner_ids: Collection[str]) -> list[str]:
    owners = set(owner_ids)
    while owners:
        found = {
            str(value)
            for row in connection.execute(
                "select distinct g.user_id,m.record_owner_id from public.financial_activity_groups g "
                "join public.financial_activity_memberships m on m.activity_id=g.id and m.user_id=g.user_id "
                "where g.user_id=any(%s::uuid[]) or m.record_owner_id=any(%s::uuid[])",
                (sorted(owners), sorted(owners)),
            ).fetchall()
            for value in row
        }
        if found <= owners:
            break
        owners.update(found)
    return sorted(owners)


def load(
    repository: Any, connection: Connection, owner_ids: Collection[str]
) -> ResolvedGroups:
    owners = owner_closure(connection, owner_ids)
    records = [
        stored for owner in owners for stored in load_owner(repository, connection, owner)
    ]
    rows = connection.execute(
        """select g.id,g.user_id,g.current_revision,m.activity_revision,
        m.record_id,m.record_revision,m.role,m.record_owner_id
        from public.financial_activity_groups g
        left join public.financial_activity_memberships m
        on m.activity_id=g.id and m.user_id=g.user_id
        where g.user_id=any(%s::uuid[])
        order by g.id,m.activity_revision,m.role""",
        (owners,),
    ).fetchall()
    headers = {}
    memberships = []
    for aid, owner, current, revision, rid, record_revision, role, record_owner in rows:
        identifier, owner_id = str(aid), str(owner)
        headers[identifier] = Group(identifier, owner_id, current)
        if revision is not None:
            memberships.append(
                Membership(
                    identifier,
                    owner_id,
                    revision,
                    str(rid),
                    record_revision,
                    role,
                    str(record_owner),
                )
            )
    return resolve(records, headers.values(), memberships)
