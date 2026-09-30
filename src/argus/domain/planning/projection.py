"""One snapshot supplies dated Plan and Home cash projections."""

from datetime import date, datetime
from typing import Any

from argus.domain.planning import claims, goal_model, goal_projection
from argus.domain.planning.budgets import all_progress
from argus.domain.planning.model import expectation_response, occurrences
from argus.domain.planning.schemas import CASH_TYPES
from argus.domain.recording.currency import currency_exponent
from argus.domain.recording.loop_reads import home_response, personal_share
from argus.domain.recording.money_reads import current_activities
from argus.domain.recording.repository import StoredAccount
from argus.domain.recording.schemas import account_response


def matches(occurrence: dict[str, Any], activity: dict[str, Any]) -> bool:
    if occurrence["kind"] == "goal_transfer":
        return goal_model.transfer_matches(
            activity,
            occurrence["source_account_id"],
            occurrence["destination_account_id"],
            occurrence["currency"],
        )
    return (
        activity["kind"] == ("income" if occurrence["kind"] == "income" else "expense")
        and activity["currency"] == occurrence["currency"]
        and len(activity["legs"]) == 1
        and activity["legs"][0]["account_id"] == occurrence["account_id"]
    )


def occurrence_response(
    item: dict[str, Any], state: dict[str, Any], actual: dict[str, Any], start: date
) -> dict[str, Any]:
    link = claims.for_occurrence(state, item["id"])
    activity = actual.get(link["activity_id"]) if link else None
    status = (
        "planned"
        if not link
        else "fulfilled"
        if activity and matches(item, activity)
        else "needs_review"
    )
    reason = None
    if status == "needs_review":
        reason = "link_needs_review"
    elif status == "planned":
        if not item["account_id"]:
            reason = "account_unassigned"
        elif not any(
            aid in state["selection"]["account_ids"] for aid, _ in movement_legs(item)
        ):
            reason = "account_not_selected"
    due = date.fromisoformat(item["due_date"])
    return item | {
        "projection_date": max(start, due).isoformat(),
        "status": status,
        "activity_id": link["activity_id"] if link else None,
        "activity_revision": activity["revision"] if activity else None,
        "exclusion_reason": reason,
        "overdue": due < start and status != "fulfilled",
    }


def projection(
    state: dict[str, Any],
    accounts: list[StoredAccount],
    start: date,
    end: date,
    now: datetime,
) -> dict[str, Any]:
    actual = {a["activity_id"]: a for a in current_activities(accounts)}
    rows = [
        occurrence_response(item, state, actual, start)
        for item in (
            occurrences(state, end) | goal_model.occurrences(state, end)
        ).values()
        if date.fromisoformat(item["due_date"]) <= end
    ]
    by_id = {s.account.id: s.account for s in accounts}
    for row in rows:
        if row["status"] == "planned" and any(
            aid
            and (
                aid not in by_id
                or by_id[aid].type not in CASH_TYPES
                or by_id[aid].currency != row["currency"]
            )
            for aid, _ in movement_legs(row)
        ):
            row["exclusion_reason"] = "account_changed"
    rows = [
        r
        for r in rows
        if r["status"] != "fulfilled" or date.fromisoformat(r["due_date"]) >= start
    ]
    rows.sort(
        key=lambda r: (
            r["projection_date"],
            r["kind"] == "income",
            r["due_date"],
            r["id"],
        )
    )
    selected = set(state["selection"]["account_ids"])
    currencies = {}
    projected_balances: dict[str, int | None] = {}
    for stored in accounts:
        if stored.account.id not in selected or stored.account.type not in CASH_TYPES:
            continue
        code = stored.account.currency
        group = currencies.setdefault(
            code,
            {
                "currency": code,
                "currency_fraction_digits": currency_exponent(code),
                "account_ids": [],
                "unknown_account_ids": [],
                "known_starting_minor": 0,
                "expected_income_minor": 0,
                "expected_bills_minor": 0,
                "transfer_effect_minor": 0,
                "as_of": None,
            },
        )
        group["account_ids"].append(stored.account.id)
        balance = account_response(stored).balance
        projected_balances[stored.account.id] = balance.amount_minor
        if balance.state == "unknown":
            group["unknown_account_ids"].append(stored.account.id)
        else:
            group["known_starting_minor"] += personal_share(
                balance.amount_minor, stored.account.ownership_share_bps
            )
            if balance.as_of and (
                group["as_of"] is None or balance.as_of < group["as_of"]
            ):
                group["as_of"] = balance.as_of
    for group in currencies.values():
        known = group["known_starting_minor"]
        complete = not group["unknown_account_ids"]
        group["starting_minor"] = str(known) if complete else None
        group["first_shortfall_date"] = (
            start.isoformat() if complete and known < 0 else None
        )
        points = [
            {
                "date": start.isoformat(),
                "occurrence_id": None,
                "change_minor": "0",
                "known_balance_minor": str(known),
                "balance_minor": str(known) if complete else None,
            }
        ]
        for row in rows:
            if (
                row["currency"] != group["currency"]
                or row["status"] != "planned"
                or row["exclusion_reason"]
            ):
                continue
            change = 0
            for account_id, whole_change in movement_legs(row):
                if account_id not in selected:
                    continue
                share = by_id[account_id].ownership_share_bps
                before = projected_balances[account_id]
                if before is None:
                    leg_change = personal_share(whole_change, share)
                else:
                    after = before + whole_change
                    leg_change = personal_share(after, share) - personal_share(
                        before, share
                    )
                    projected_balances[account_id] = after
                    known += leg_change
                change += leg_change
            if row["kind"] == "goal_transfer":
                group["transfer_effect_minor"] += change
            else:
                group[
                    "expected_income_minor"
                    if row["kind"] == "income"
                    else "expected_bills_minor"
                ] += abs(change)
            points.append(
                {
                    "date": row["projection_date"],
                    "occurrence_id": row["id"],
                    "change_minor": str(change),
                    "known_balance_minor": str(known),
                    "balance_minor": str(known) if complete else None,
                }
            )
            if complete and known < 0 and group["first_shortfall_date"] is None:
                group["first_shortfall_date"] = row["projection_date"]
        group.update(
            points=points,
            ending_minor=str(known) if complete else None,
            net_cash_change_minor=str(
                group["expected_income_minor"]
                - group["expected_bills_minor"]
                + group["transfer_effect_minor"]
            ),
            order="bills_before_income",
        )
        for key in (
            "known_starting_minor",
            "expected_income_minor",
            "expected_bills_minor",
            "transfer_effect_minor",
        ):
            group[key] = str(group[key])
    budgets = all_progress(state, accounts)
    goals, pools = goal_projection.project(state, accounts, start, end)
    return {
        "budgets": budgets,
        "goals": goals,
        "goal_pools": pools,
        "home": home_response(
            accounts, time_zone=state["selection"]["time_zone"], now=now
        )
        | {
            "budgets": [p for p in budgets if not p["budget"]["archived"]],
            "goals": [p for p in goals if not p["goal"]["archived"]],
        },
        "selection": state["selection"],
        "accounts": [account_response(s).model_dump(mode="json") for s in accounts],
        "expectations": [
            expectation_response(e, state["links"], start)
            for e in state["expectations"].values()
        ],
        "occurrences": rows,
        "currencies": [currencies[c] for c in sorted(currencies)],
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "coverage": "recorded_and_expected",
        "has_expectations": any(
            not e["archived"] for e in state["expectations"].values()
        ),
    }


def movement_legs(row: dict[str, Any]) -> list[tuple[str | None, int]]:
    amount = row["amount_minor"]
    if row["kind"] == "goal_transfer":
        return [
            (row["source_account_id"], -amount),
            (row["destination_account_id"], amount),
        ]
    return [(row["account_id"], amount if row["kind"] == "income" else -amount)]
