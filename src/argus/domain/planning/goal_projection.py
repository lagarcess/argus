"""Account pools bound goal intentions by current Recording truth."""

from datetime import date
from typing import Any

from argus.domain.planning import claims, goal_model
from argus.domain.planning.schemas import CASH_TYPES
from argus.domain.recording.loop_reads import personal_share
from argus.domain.recording.money_reads import current_activities
from argus.domain.recording.repository import StoredAccount
from argus.domain.recording.schemas import account_response


def contributions(
    state: dict[str, Any], accounts: list[StoredAccount]
) -> dict[str, list[dict[str, Any]]]:
    actual = {a["activity_id"]: a for a in current_activities(accounts)}
    by_id = {a.account.id: a.account for a in accounts}
    result: dict[str, list[dict[str, Any]]] = {gid: [] for gid in state["goals"]}
    for cid, link in state["links"].items():
        if not link.get("goal_id"):
            continue
        accepted = link["attribution"]
        entry = actual.get(link["activity_id"])
        destination = by_id.get(accepted["destination_account_id"])
        source = by_id.get(accepted["source_account_id"])
        valid = bool(
            entry
            and destination
            and source
            and destination.type in CASH_TYPES
            and source.type in CASH_TYPES
            and destination.currency == accepted["currency"]
            and source.currency == accepted["currency"]
            and goal_model.transfer_matches(
                entry,
                accepted["source_account_id"],
                accepted["destination_account_id"],
                accepted["currency"],
            )
        )
        amount = (
            personal_share(entry["amount_minor"], destination.ownership_share_bps)
            if valid
            else None
        )
        counting = accepted["counting"]
        result[link["goal_id"]].append(
            {
                "id": cid,
                "activity_id": link["activity_id"],
                "activity_revision": entry["revision"] if entry else None,
                "occurrence_id": claims.occurrence_id(cid, link),
                "source_account_id": accepted["source_account_id"],
                "destination_account_id": accepted["destination_account_id"],
                "treatment": accepted["treatment"],
                "reviewed_personal_minor": str(accepted["reviewed_personal_minor"]),
                "current_personal_minor": str(amount) if amount is not None else None,
                "counting": counting,
                "status": "released"
                if not counting
                else "current"
                if valid
                else "needs_review",
                "reason": None
                if valid
                else "contribution_changed"
                if entry
                else "contribution_unavailable",
                "activity": entry,
            }
        )
    return result


def project(
    state: dict[str, Any], accounts: list[StoredAccount], today: date, end: date
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    linked = contributions(state, accounts)
    amounts: dict[str, dict[str, int]] = {}
    unresolved: dict[str, list[str]] = {}
    for gid, item in state["goals"].items():
        amounts[gid] = {a["account_id"]: a["unlinked_minor"] for a in item["allocations"]}
        unresolved[gid] = []
        for link in linked[gid]:
            if not link["counting"]:
                continue
            aid = link["destination_account_id"]
            if link["current_personal_minor"] is None:
                unresolved[gid].append(link["reason"])
                amounts[gid].setdefault(aid, 0)
            else:
                amounts[gid][aid] = amounts[gid].get(aid, 0) + int(
                    link["current_personal_minor"]
                )
    pools = {}
    for stored in accounts:
        account = stored.account
        claimants = sorted(
            gid for gid, values in amounts.items() if values.get(account.id, 0) > 0
        )
        total = sum(amounts[gid][account.id] for gid in claimants)
        balance = account_response(stored).balance
        eligible = account.type in CASH_TYPES
        backing = (
            max(0, personal_share(balance.amount_minor, account.ownership_share_bps))
            if eligible and balance.amount_minor is not None
            else None
        )
        pools[account.id] = {
            "account_id": account.id,
            "account_name": account.nickname,
            "currency": account.currency,
            "account_version": account.version,
            "ownership_share_bps": account.ownership_share_bps,
            "as_of": balance.as_of,
            "backing_minor": str(backing) if backing is not None else None,
            "assigned_minor": str(total),
            "available_minor": str(max(0, backing - total))
            if backing is not None
            else None,
            "shortfall_minor": str(max(0, total - backing))
            if backing is not None
            else None,
            "state": "ineligible"
            if not eligible
            else "unknown"
            if backing is None
            else "shortfall"
            if total > backing
            else "backed",
            "affected_goal_ids": claimants,
            "affected_goal_names": [state["goals"][gid]["name"] for gid in claimants],
        }
    upcoming = goal_model.occurrences(state, end)
    results = []
    by_id = {a.account.id: a.account for a in accounts}
    for gid, item in state["goals"].items():
        reasons = list(unresolved[gid])
        support, independent = 0, 0
        resolved = not reasons
        components = []
        for aid, assigned in amounts[gid].items():
            pool = pools.get(aid)
            if pool is None or pool["currency"] != item["currency"]:
                reasons.append("account_changed")
                resolved = False
                continue
            components.append(pool)
            if assigned == 0:
                continue
            if pool["state"] == "backed":
                support += assigned
                independent += assigned
            elif pool["state"] == "shortfall":
                reasons.append("pool_shortfall")
                if len(pool["affected_goal_ids"]) == 1:
                    support += min(assigned, int(pool["backing_minor"]))
                else:
                    resolved = False
            else:
                reasons.append("pool_" + pool["state"])
                resolved = False
        planned = 0
        planned_valid = True
        for oid, row in upcoming.items():
            if row["goal_id"] != gid or claims.for_occurrence(state, oid):
                continue
            destination = by_id.get(row["destination_account_id"])
            source = by_id.get(row["source_account_id"])
            if (
                not destination
                or not source
                or any(
                    a.type not in CASH_TYPES or a.currency != item["currency"]
                    for a in (source, destination)
                )
            ):
                planned_valid = False
                continue
            planned += personal_share(
                row["amount_minor"], destination.ownership_share_bps
            )
        actual = support if resolved else None
        results.append(
            {
                "goal": goal_model.definition(item, state, today),
                "assigned_minor": str(sum(amounts[gid].values())),
                "supported_minor": str(actual) if actual is not None else None,
                "independently_backed_minor": str(independent),
                "remaining_minor": str(max(0, item["target_minor"] - actual))
                if actual is not None
                else None,
                "state": "needs_review"
                if reasons
                else "reached"
                if support >= item["target_minor"]
                else "unconfigured"
                if not item["destination_account_id"] and not amounts[gid]
                else "active",
                "reasons": sorted(set(reasons)),
                "pools": components,
                "contributions": linked[gid],
                "planned_minor": str(planned),
                "projected_minor": str(actual + planned)
                if actual is not None and planned_valid
                else None,
                "projection_end_date": end.isoformat(),
            }
        )
    results.sort(key=lambda result: (result["goal"]["name"], result["goal"]["id"]))
    return results, list(pools.values())
