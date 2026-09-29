"""Owner-serialized Plan writes compose with canonical activity persistence."""

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime
from typing import Any

from fastapi.encoders import jsonable_encoder
from psycopg.types.json import Jsonb

from argus.domain.recording.errors import IdempotencyConflict, RegisteredAccountRequired
from argus.domain.recording.loop_storage import apply
from argus.domain.recording.money_plan import MoneyPlan
from argus.domain.recording.money_postgres import load_owner, owner_lock, persist
from argus.domain.recording.repository import (
    InMemoryFinancialAccountRepository,
    StoredAccount,
)

Action = Callable[
    [dict[str, Any], list[StoredAccount]], tuple[dict[str, Any], MoneyPlan | None]
]


def empty() -> dict[str, Any]:
    return {
        "expectations": {},
        "links": {},
        "selection": {
            "version": 0,
            "account_ids": [],
            "time_zone": "America/Santo_Domingo",
        },
        "receipts": {},
    }


def load(connection: Any, user_id: str) -> dict[str, Any]:
    state = empty()
    for eid, body in connection.execute(
        "select id,body from public.financial_expectations where user_id=%s order by id",
        (user_id,),
    ).fetchall():
        state["expectations"][str(eid)] = body
    for oid, eid, aid, revision, snapshot in connection.execute(
        "select occurrence_id,expectation_id,activity_id,activity_revision,snapshot from public.financial_plan_links where user_id=%s",
        (user_id,),
    ).fetchall():
        state["links"][str(oid)] = {
            "expectation_id": str(eid),
            "activity_id": str(aid),
            "activity_revision": revision,
            "snapshot": snapshot,
        }
    row = connection.execute(
        "select body from public.financial_plan_selections where user_id=%s", (user_id,)
    ).fetchone()
    if row:
        state["selection"] = row[0]
    return state


def read(repository: Any, user_id: str) -> tuple[dict[str, Any], list[StoredAccount]]:
    if isinstance(repository, InMemoryFinancialAccountRepository):
        with repository._lock:
            state = deepcopy(
                getattr(repository, "_plan_states", {}).get(user_id, empty())
            )
            return state, [
                s for s in repository._accounts.values() if s.account.user_id == user_id
            ]
    with repository._pool.connection() as connection, connection.transaction():
        connection.execute("set transaction isolation level repeatable read read only")
        return load(connection, user_id), load_owner(repository, connection, user_id)


def projected(
    accounts: list[StoredAccount], money: MoneyPlan, now: datetime
) -> list[StoredAccount]:
    from dataclasses import replace

    result = []
    for stored in accounts:
        aid = stored.account.id
        if aid in money.mutations:
            stored = apply(stored, money.mutations[aid], now)
        elif aid in money.affected:
            stored = replace(
                stored,
                account=replace(
                    stored.account, version=stored.account.version + 1, updated_at=now
                ),
            )
        result.append(stored)
    return result


def write(
    repository: Any,
    user_id: str,
    scope: str,
    key: str,
    identity: str,
    action: Action,
    now: datetime,
) -> dict[str, Any]:
    if isinstance(repository, InMemoryFinancialAccountRepository):
        with repository._lock:
            states = getattr(repository, "_plan_states", None)
            if states is None:
                repository._plan_states = states = {}
            state = deepcopy(states.get(user_id, empty()))
            receipt = state["receipts"].get((scope, key))
            if receipt:
                if receipt[0] != identity:
                    raise IdempotencyConflict()
                return deepcopy(receipt[1]) | {"replayed": True}
            accounts = [
                s for s in repository._accounts.values() if s.account.user_id == user_id
            ]
            result, money = action(state, accounts)
            if money:
                for stored in projected(accounts, money, now):
                    repository._accounts[stored.account.id] = stored
            result = jsonable_encoder(result) | {"replayed": False}
            state["receipts"][(scope, key)] = (identity, result)
            states[user_id] = state
            return deepcopy(result)
    with repository._pool.connection() as connection, connection.transaction():
        owner_lock(connection, user_id)
        if not connection.execute(
            "select 1 from auth.users where id=%s and coalesce(is_anonymous,false)=false",
            (user_id,),
        ).fetchone():
            raise RegisteredAccountRequired()
        receipt = connection.execute(
            "select identity_hash,result from public.financial_plan_receipts where user_id=%s and scope=%s and idempotency_key=%s",
            (user_id, scope, key),
        ).fetchone()
        if receipt:
            if receipt[0] != identity:
                raise IdempotencyConflict()
            return receipt[1] | {"replayed": True}
        connection.execute(
            "select id from public.financial_accounts where user_id=%s order by id for update",
            (user_id,),
        ).fetchall()
        state = load(connection, user_id)
        result, money = action(state, load_owner(repository, connection, user_id))
        if money:
            persist(connection, user_id, money)
        for eid, body in state["expectations"].items():
            connection.execute(
                "insert into public.financial_expectations(id,user_id,body) values(%s,%s,%s) on conflict(id) do update set body=excluded.body",
                (eid, user_id, Jsonb(body)),
            )
        connection.execute(
            "insert into public.financial_plan_selections(user_id,body) values(%s,%s) on conflict(user_id) do update set body=excluded.body",
            (user_id, Jsonb(state["selection"])),
        )
        for oid, link in state["links"].items():
            connection.execute(
                "insert into public.financial_plan_links(user_id,occurrence_id,expectation_id,activity_id,activity_revision,snapshot) values(%s,%s,%s,%s,%s,%s) on conflict(user_id,occurrence_id) do update set activity_id=excluded.activity_id,activity_revision=excluded.activity_revision",
                (
                    user_id,
                    oid,
                    link["expectation_id"],
                    link["activity_id"],
                    link["activity_revision"],
                    Jsonb(link["snapshot"]),
                ),
            )
        result = jsonable_encoder(result) | {"replayed": False}
        connection.execute(
            "insert into public.financial_plan_receipts(user_id,scope,idempotency_key,identity_hash,result) values(%s,%s,%s,%s,%s)",
            (user_id, scope, key, identity, Jsonb(result)),
        )
        return result
