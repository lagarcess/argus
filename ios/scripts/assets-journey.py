"""Retained manual-asset acceptance using the existing private HTTP journal."""

from __future__ import annotations

import argparse
import fcntl
import importlib.util
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "ios/.build/accounts-local-59200"
SPEC = importlib.util.spec_from_file_location(
    "asset_local_transport", Path(__file__).with_name("goals-journey.py")
)
scene = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scene)
scene.WORK = WORK
scene.API = "http://127.0.0.1:59300/api/v1"
scene.AUTH = "http://127.0.0.1:59201"
scene.PROXY = "http://127.0.0.1:59312"
scene.GOALS = "/financial-accounts"
require, wire, get = scene.require, scene.wire, scene.get
ZONE = "America/Santo_Domingo"


def command(journal, client, name, method, path, body, owner=0):
    return journal.command(client, name, method, path, body, owner=owner)


def setup(journal, client):
    now = datetime.fromisoformat(journal.state["now"])
    rows = [
        ("house", "property", "DOP", "8000000", 5000),
        ("car", "vehicle", "DOP", "100000", 10000),
        ("unknown", "other_asset", "DOP", None, 10000),
        ("zero", "other_asset", "DOP", "0", 10000),
        ("loan", "other_debt", "DOP", "1000000", 10000),
        ("usd", "property", "USD", "1000", 5000),
        ("cash", "checking", "DOP", "1000", 10000),
        ("unknown_loan", "other_debt", "USD", None, 10000),
    ]
    ids = {}
    for name, kind, currency, amount, share in rows:
        body = {
            "type": kind,
            "currency": currency,
            "amount": amount,
            "ownership_share_bps": share,
            "nickname": "Asset demo " + name + " " + journal.state["suffix"],
            "as_of": (now - timedelta(days=10)).isoformat(),
            "time_zone": ZONE,
        }
        ids[name] = command(
            journal,
            client,
            "create_" + name,
            "POST",
            "/financial-accounts",
            lambda body=body: body,
        )["id"]
    journal.state["ids"] = ids
    journal.save()
    command(
        journal,
        client,
        "budget",
        "POST",
        "/financial-plan/budgets",
        lambda: {
            "name": "Asset unaffected budget " + journal.state["suffix"],
            "limit": "200",
            "currency": "DOP",
            "month": now.strftime("%Y-%m"),
            "account_ids": [ids["cash"]],
            "category_ids": [],
            "include_uncategorized": True,
        },
    )
    goal = command(
        journal,
        client,
        "goal",
        "POST",
        "/financial-plan/goals",
        lambda: {
            "name": "Asset unaffected savings " + journal.state["suffix"],
            "currency": "DOP",
            "target": "1000",
            "destination_account_id": ids["cash"],
        },
    )
    goal_id = goal["goal"]["goal"]["id"]
    command(
        journal,
        client,
        "allocation",
        "PUT",
        "/financial-plan/goals/allocations",
        lambda: {
            "changes": [
                {
                    "goal_id": goal_id,
                    "expected_version": 1,
                    "account_id": ids["cash"],
                    "amount": "500",
                }
            ],
            "expected_account_versions": {
                ids["cash"]: get(client, "/financial-accounts/" + ids["cash"])["version"]
            },
        },
    )
    command(
        journal,
        client,
        "cash_selection",
        "PUT",
        "/financial-plan/selection",
        lambda: {
            "expected_version": get(client, "/financial-plan")["selection"]["version"],
            "account_ids": [ids["cash"]],
            "time_zone": ZONE,
        },
    )
    if "baseline_plan" not in journal.state:
        plan = get(client, "/financial-plan")
        journal.state["baseline_plan"] = {
            key: plan[key] for key in ["currencies", "budgets", "goals", "goal_pools"]
        }
        journal.save()
    house = "/financial-accounts/" + ids["house"]
    for label, amount, days in [("first", "9000000", 5), ("latest", "10000000", 1)]:

        def body(amount=amount, days=days, label=label):
            current = get(client, house)
            request = {
                "expected_version": current["version"],
                "amount": amount,
                "as_of": (now - timedelta(days=days)).isoformat(),
                "time_zone": ZONE,
                "estimate_basis": "Manual estimate " + label,
            }
            status, preview = client.api(
                0, "POST", house + "/asset-estimates/preview", wire(request)
            )
            require(status == 200, "Estimate preview failed")
            return request | {"preview_token": preview["preview_token"]}

        command(
            journal, client, "estimate_" + label, "POST", house + "/asset-estimates", body
        )

    def correction():
        current = get(client, house)
        old = current["asset"]["estimates"][1]
        request = {
            "expected_version": current["version"],
            "record_id": old["record_id"],
            "expected_revision": old["revision"],
            "amount": "9100000",
            "as_of": old["as_of"],
            "time_zone": ZONE,
            "estimate_basis": "Corrected manual basis",
            "reason": "Corrected an older estimate",
        }
        status, preview = client.api(
            0, "POST", house + "/asset-estimates/preview", wire(request)
        )
        require(status == 200, "Correction preview failed")
        require(
            preview["account"]["asset"]["personal_position_minor"] == 500000000,
            "Old correction changed current value",
        )
        return request | {"preview_token": preview["preview_token"]}

    command(
        journal, client, "correct_old", "POST", house + "/asset-estimates", correction
    )
    for label in ["house", "car", "unknown"]:
        path = "/financial-accounts/" + ids[label]
        command(
            journal,
            client,
            "link_" + label,
            "PUT",
            path + "/asset-details",
            lambda path=path, label=label: {
                "expected_version": get(client, path)["version"],
                "ownership_share_bps": 5000 if label == "house" else 10000,
                "related_debt_account_id": ids["unknown_loan"]
                if label == "unknown"
                else ids["loan"],
            },
        )
    loan_path = "/financial-accounts/" + ids["loan"]

    def check_debt():
        request = {
            "expected_version": get(client, loan_path)["version"],
            "amount": "900000",
            "as_of": now.isoformat(),
            "time_zone": ZONE,
            "note": "Updated recorded principal",
        }
        status, preview = client.api(
            0, "POST", loan_path + "/balance-checks/preview", wire(request)
        )
        require(
            status == 200 and preview["observed_amount_minor"] == -90000000,
            "Debt check preview differs",
        )
        return request | {"preview_token": preview["preview_token"]}

    command(
        journal, client, "check_debt", "POST", loan_path + "/balance-checks", check_debt
    )
    command(
        journal,
        client,
        "archive",
        "PATCH",
        house,
        lambda: {"expected_version": get(client, house)["version"], "archived": True},
    )
    command(
        journal,
        client,
        "restore",
        "PATCH",
        house,
        lambda: {"expected_version": get(client, house)["version"], "archived": False},
    )
    original = journal.state["operations"]["correct_old"]
    status, replay = client.api(
        0,
        original["method"],
        original["path"],
        original["body"].encode(),
        original["key"],
    )
    require(
        status == 200 and replay["replayed"] and replay["revision"] == 2,
        "Estimate exact replay failed",
    )
    original = journal.state["operations"]["link_house"]
    status, replay = client.api(
        0,
        original["method"],
        original["path"],
        original["body"].encode(),
        original["key"],
    )
    require(status == 200 and replay["replayed"], "Details exact replay failed")
    status, _ = client.api(1, "GET", house)
    require(status == 404, "Other owner could read asset")
    other = command(
        journal,
        client,
        "other_owner_debt",
        "POST",
        "/financial-accounts",
        lambda: {"type": "other_debt", "currency": "DOP", "amount": None},
        owner=1,
    )
    status, _ = client.api(
        0,
        "PUT",
        house + "/asset-details",
        wire(
            {
                "expected_version": get(client, house)["version"],
                "ownership_share_bps": 5000,
                "related_debt_account_id": other["id"],
            }
        ),
        "cross-owner-link",
    )
    require(status == 404, "Other owner debt could be linked")
    return readback(journal, client)


def readback(journal, client):
    ids = journal.state["ids"]
    house = get(client, "/financial-accounts/" + ids["house"])
    require(
        house["asset"]["personal_position_minor"] == 500000000,
        "Personal contribution differs",
    )
    require(
        house["asset"]["estimates"][1]["revisions"][0]["amount_minor"] == 900000000,
        "Prior estimate missing",
    )
    require(
        house["asset"]["estimates"][1]["amount_minor"] == 910000000,
        "Old correction missing",
    )
    require(
        house["asset"]["current_estimate"]["amount_minor"] == 1000000000,
        "Old correction replaced latest estimate",
    )
    require(
        house["asset"]["related_debt_account_id"] == ids["loan"], "Debt identity changed"
    )
    require(not house["archived"], "Restoration failed")
    car = get(client, "/financial-accounts/" + ids["car"])
    require(
        car["asset"]["related_debt_account_id"] == ids["loan"],
        "Second asset lost original debt identity",
    )
    groups = {g["currency"]: g for g in get(client, "/financial-home")["currencies"]}
    require(groups["DOP"]["cash_minor"] == "100000", "Asset estimate became cash")
    require(
        groups["DOP"]["debts_minor"] == "90000000", "Linked debt counted more than once"
    )
    require(groups["DOP"]["net_worth_minor"] == "420100000", "DOP net worth differs")
    require(groups["DOP"]["unknown_accounts"] == 1, "Unknown asset became zero")
    require(
        groups["USD"]["net_worth_minor"] == "50000", "USD mixed into another currency"
    )
    plan = get(client, "/financial-plan")
    baseline = journal.state["baseline_plan"]
    for key in ("budgets", "goals"):
        require(plan[key] == baseline[key], "Asset writes changed Plan " + key)
    pools = {row["account_id"]: row for row in plan["goal_pools"]}
    previous_pools = {row["account_id"]: row for row in baseline["goal_pools"]}
    require(
        pools.keys() == previous_pools.keys(),
        "Asset writes changed savings pool identities",
    )
    require(
        pools[ids["cash"]] == previous_pools[ids["cash"]],
        "Asset writes changed cash savings pool",
    )
    for account_id, pool in pools.items():
        if account_id == ids["cash"]:
            continue
        require(
            pool["state"] == "ineligible"
            and pool["backing_minor"] is None
            and pool["assigned_minor"] == "0"
            and pool["available_minor"] is None
            and pool["shortfall_minor"] is None
            and pool["affected_goal_ids"] == []
            and pool["affected_goal_names"] == [],
            "Ineligible asset or debt became savings backing",
        )
        stable = {
            key: value
            for key, value in pool.items()
            if key not in ("account_version", "as_of")
        }
        previous = {
            key: value
            for key, value in previous_pools[account_id].items()
            if key not in ("account_version", "as_of")
        }
        require(
            stable == previous, "Asset writes changed ineligible pool financial facts"
        )
    require(plan["budgets"][0]["spent_minor"] == "0", "Valuation became budget spending")
    require(
        plan["goals"][0]["supported_minor"] == "50000", "Valuation became savings backing"
    )
    require(
        plan["selection"]["account_ids"] == [ids["cash"]],
        "Forecast selected an asset or debt",
    )
    require(
        len(plan["currencies"]) == 1,
        "Forecast did not preserve the selected DOP cash group",
    )
    forecast = plan["currencies"][0]
    require(
        forecast["currency"] == "DOP"
        and forecast["account_ids"] == [ids["cash"]]
        and forecast["unknown_account_ids"] == []
        and forecast["known_starting_minor"] == "100000"
        and forecast["starting_minor"] == "100000"
        and forecast["expected_income_minor"] == "0"
        and forecast["expected_bills_minor"] == "0"
        and forecast["transfer_effect_minor"] == "0"
        and forecast["net_cash_change_minor"] == "0"
        and forecast["ending_minor"] == "100000"
        and pools[ids["cash"]]["backing_minor"] == "100000",
        "Valuation changed forecast or eligible cash backing",
    )
    require(
        all(
            g["gross_income_minor"] == "0" and g["recorded_spending_minor"] == "0"
            for g in groups.values()
        ),
        "Valuation created money activity",
    )
    search_path = "/financial-search?" + urlencode(
        {"q": house["nickname"], "kind": "account"}
    )
    results = get(client, search_path)
    require(
        len(results["items"]) == 1 and results["items"][0]["account"] == house,
        "Asset Search did not return its canonical account detail",
    )
    require(
        get(client, search_path, owner=1)["items"] == [],
        "Asset Search exposed another owner's record",
    )
    destination = get(
        client, "/financial-accounts/" + results["items"][0]["account"]["id"]
    )
    linked = get(
        client, "/financial-accounts/" + destination["asset"]["related_debt_account_id"]
    )
    require(
        linked["id"] == ids["loan"] and linked["balance"]["amount_minor"] == -90000000,
        "Search asset link opened a different debt or stale principal",
    )
    require(
        get(client, search_path) == results,
        "Linked debt read changed the originating Search results",
    )
    return {
        "source_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "checks": [
            "unknown-zero",
            "whole-and-personal-share",
            "revision-basis",
            "selected-old-correction",
            "existing-debt-counted-once",
            "linked-debt-principal-update",
            "cash-budget-savings-forecast-unchanged",
            "cross-currency",
            "archive-restore",
            "owner-isolation",
            "search-canonical-detail-and-linked-debt",
            "search-owner-isolation-and-return",
            "exact-replay",
        ],
        "currencies": groups,
        "asset_query": house["nickname"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["run", "readback", "observe"])
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    with (WORK / "asset-journey.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        journal = scene.Journal(WORK / "asset-journey.json", create=args.action == "run")
        client = scene.Client(scene.read_private(WORK / "client.json"), journal)
        if args.action == "observe":
            proof = {
                "source_head": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
                ).strip(),
                "currencies": get(client, "/financial-home")["currencies"],
                "asset": get(
                    client, "/financial-accounts/" + journal.state["ids"]["house"]
                ),
            }
        else:
            proof = (
                setup(journal, client)
                if args.action == "run"
                else readback(journal, client)
            )
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        proof["action"] = args.action
        proof["observed_at"] = stamp
        target = (
            ROOT
            / "docs/reports/evidence/connected-personal-assets"
            / f"asset-api-{args.action}-{stamp}.json"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x") as output:
            output.write(json.dumps(proof, indent=2) + "\n")
        print(f"Asset journey {args.action} complete; separate public proof saved.")


if __name__ == "__main__":
    try:
        main()
    except scene.Refused as error:
        raise SystemExit(str(error)) from None
