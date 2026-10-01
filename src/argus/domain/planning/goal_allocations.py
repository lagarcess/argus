"""Persist residuals once and reconstruct the existing Personal goal state."""

from typing import Any

from psycopg import Connection
from psycopg.types.json import Jsonb


def load(connection: Connection, user_id: str, goals: dict[str, dict[str, Any]]) -> None:
    for body in goals.values():
        body["allocations"] = []
    for gid, aid, amount in connection.execute(
        "select goal_id,account_id,unlinked_minor from public.financial_goal_allocations "
        "where goal_owner_id=%s and account_owner_id=%s order by goal_id,ordinal",
        (user_id, user_id),
    ).fetchall():
        goals[str(gid)]["allocations"].append(
            {"account_id": str(aid), "unlinked_minor": amount}
        )


def persist(
    connection: Connection, user_id: str, goals: dict[str, dict[str, Any]]
) -> None:
    for gid, body in goals.items():
        connection.execute(
            "insert into public.financial_goals(id,user_id,body) values(%s,%s,%s) "
            "on conflict(id,user_id) do update set body=excluded.body",
            (
                gid,
                user_id,
                Jsonb(
                    {key: value for key, value in body.items() if key != "allocations"}
                ),
            ),
        )
    connection.execute(
        "delete from public.financial_goal_allocations "
        "where goal_owner_id=%s and account_owner_id=%s",
        (user_id, user_id),
    )
    for gid, body in goals.items():
        for ordinal, allocation in enumerate(body["allocations"]):
            connection.execute(
                "insert into public.financial_goal_allocations "
                "(goal_id,goal_owner_id,account_id,account_owner_id,unlinked_minor,ordinal) "
                "values(%s,%s,%s,%s,%s,%s)",
                (
                    gid,
                    user_id,
                    allocation["account_id"],
                    user_id,
                    allocation["unlinked_minor"],
                    ordinal,
                ),
            )
