"""Run the connected budget API journey on the preserved allocation-59000 scene."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

SPEC = importlib.util.spec_from_file_location(
    "budget_scene", Path(__file__).with_name("budgets-acceptance.py")
)
scene = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scene)


class Client(scene.Client):
    def api(self, owner, method, path, body=None, key=None):
        parsed = urlsplit(path)
        scene.require(not parsed.scheme and not parsed.netloc and not parsed.fragment
                      and ".." not in parsed.path and "//" not in parsed.path,
                      "Refusing unexpected API path")
        scene.require(any(parsed.path == root or parsed.path.startswith(root + "/")
                          for root in ("/financial-accounts", "/financial-activities",
                                       "/financial-plan", "/financial-home",
                                       "/financial-search")), "Refusing unrelated API route")
        if owner not in self.sessions:
            self.login(owner)

        def send():
            headers = {"Content-Type": "application/json",
                       "Authorization": "Bearer " + self.sessions[owner]["access_token"]}
            if key:
                headers["Idempotency-Key"] = key
            return self.raw(scene.API + path, method, body, headers)

        status, result = send()
        if status == 401:
            self.refresh(owner)
            status, result = send()
        return status, result


def write(client, state, name, method, path, body):
    operations = state.setdefault("operations", {})
    if name not in operations:
        operations[name] = {"method": method, "path": path,
                            "body": scene.wire(body).decode(), "key": str(uuid4())}
        scene.save_state(state)
    operation = operations[name]
    if "result" not in operation:
        operation["result"] = scene.expect(
            client, operation["method"], operation["path"],
            operation["body"].encode(), operation["key"], statuses=(200, 201))
        scene.save_state(state)
    return operation["result"]


def money(client, state, name, body, activity_id=None):
    root = "/financial-activities" + ("/" + activity_id if activity_id else "")
    operation = state.setdefault("operations", {}).get(name)
    if operation is None:
        preview = scene.expect(client, "POST", root + "/preview", scene.wire(body))
        scene.require(preview.get("ready") is True, "Money preview is not ready")
        body = preview["reviewed_request"]
        body["preview_token"] = preview["preview_token"]
    return write(client, state, name, "PATCH" if activity_id else "POST", root, body)


def replay(client, state, name):
    operation = state["operations"][name]
    result = scene.expect(client, operation["method"], operation["path"],
                          operation["body"].encode(), operation["key"], statuses=(200, 201))
    key = "budget" if "budget" in operation["result"] else "activity"
    identity = "id" if key == "budget" else "activity_id"
    scene.require(result.get("replayed") is True
                  and result[key][identity] == operation["result"][key][identity],
                  "Retry did not preserve canonical identity")


def progress(client, budget_id, expected):
    result = scene.expect(client, "GET", "/financial-plan/budgets/" + budget_id)
    actual = tuple(int(result[key]) for key in
                   ("spent_minor", "remaining_minor", "over_budget_minor"))
    scene.require(actual == expected, "Budget progress differs from independent expected totals")
    return result


def check_stage(client, state, name, budget_id, totals, checking, cash, home_position,
                home_spending):
    if name in state.setdefault("checks", {}):
        return
    result = progress(client, budget_id, totals)
    plan = scene.expect(client, "GET", "/financial-plan")
    nested = next(row for row in plan["budgets"] if row["budget"]["id"] == budget_id)
    standalone = scene.expect(client, "GET", "/financial-home")
    home_budget = next(row for row in standalone["budgets"] if row["budget"]["id"] == budget_id)
    for row in (nested, home_budget):
        scene.require(all(row[key] == result[key] for key in
                          ("spent_minor", "remaining_minor", "over_budget_minor")),
                      "Plan, detail and Home budget totals differ")
    home = next(row for row in plan["home"]["currencies"] if row["currency"] == "DOP")
    scene.require(int(home["net_worth_minor"]) == home_position
                  and int(home["net_spending_minor"]) == home_spending
                  and home["unknown_accounts"] == 1, "Recorded Home totals differ")
    for label, amount in (("checking", checking), ("cash", cash), ("card", 0), ("usd", 5000)):
        account = scene.expect(client, "GET", "/financial-accounts/" + state["fixture"]["accounts"][label])
        scene.require(account["balance"]["amount_minor"] == amount, "Account total differs")
    unknown = scene.expect(client, "GET", "/financial-accounts/" + state["fixture"]["accounts"]["unknown"])
    scene.require(unknown["balance"]["state"] == "unknown", "Unknown balance became known")
    state["checks"][name] = {"spent_minor": totals[0], "remaining_minor": totals[1],
                             "over_budget_minor": totals[2], "dop_position_minor": home_position,
                             "dop_net_spending_minor": home_spending}
    scene.save_state(state)


def definition(fixture, name, accounts, categories, limit="150", currency="DOP",
               month="2026-09", uncategorized=False):
    return {"name": name + " " + fixture["suffix"], "limit": limit,
            "currency": currency, "month": month,
            "account_ids": [fixture["accounts"][label] for label in accounts],
            "category_ids": categories, "include_uncategorized": uncategorized}


def run(client, state, fixture):
    state.setdefault("fixture", {"accounts": fixture["accounts"], "activities": fixture["activities"]})
    accounts = fixture["accounts"]
    body = definition(fixture, "Groceries budget demo", ["checking", "card"], ["groceries"])
    created = write(client, state, "budget", "POST", "/financial-plan/budgets", body)
    budget_id = created["budget"]["id"]
    replay(client, state, "budget")
    check_stage(client, state, "existing_activity", budget_id, (12000, 3000, 0),
                82300, 14000, 96300, 14000)
    expense = {"kind": "expense", "account_id": accounts["checking"], "amount": "80",
               "occurred_at": "2026-09-20T12:00:00-04:00", "time_zone": scene.ZONE,
               "category_id": "groceries", "note": "Budget journey purchase " + fixture["suffix"],
               "coverage": [], "expected_versions": {}}
    actual = money(client, state, "expense", expense)
    replay(client, state, "expense")
    activity_id = actual["activity"]["activity_id"]
    check_stage(client, state, "recorded_expense", budget_id, (20000, -5000, 5000),
                74300, 14000, 88300, 22000)
    corrected = money(client, state, "correction", {
        **expense, "amount": "60", "expected_revision": actual["activity"]["revision"],
        "reason": "Correct the receipt amount"}, activity_id)
    replay(client, state, "correction")
    check_stage(client, state, "corrected_expense", budget_id, (18000, -3000, 3000),
                76300, 14000, 90300, 20000)
    refunded = money(client, state, "refund", {
        "kind": "refund", "account_id": accounts["cash"], "amount": "25",
        "purchase_activity_id": corrected["activity"]["activity_id"],
        "occurred_at": "2026-09-21T12:00:00-04:00", "time_zone": scene.ZONE,
        "note": "Budget journey refund " + fixture["suffix"],
        "coverage": [], "expected_versions": {}})
    replay(client, state, "refund")
    check_stage(client, state, "cross_account_refund", budget_id, (15500, -500, 500),
                76300, 16500, 92800, 17500)
    result = progress(client, budget_id, (15500, -500, 500)) if "edit" not in state["operations"] else None
    if result:
        expected_ids = {fixture["activities"]["groceries_checking"], fixture["activities"]["groceries_card"],
                        activity_id, refunded["activity"]["activity_id"]}
        scene.require({row["activity_id"] for row in result["contributors"]} == expected_ids,
                      "Contributing rows differ from included canonical activity")
        scene.require(datetime.fromisoformat(result["period"]["start_at"]).astimezone(timezone.utc)
                      == datetime(2026, 9, 1, 4, tzinfo=timezone.utc)
                      and datetime.fromisoformat(result["period"]["end_at_exclusive"]).astimezone(timezone.utc)
                      == datetime(2026, 10, 1, 4, tzinfo=timezone.utc),
                      "Half-open reporting interval differs")
    if "edit" not in state["operations"]:
        version = created["budget"]["version"]
        status, _ = client.api(1, "GET", "/financial-plan/budgets/" + budget_id)
        scene.require(status == 404, "Other owner read a budget")
        status, _ = client.api(1, "PATCH", "/financial-plan/budgets/" + budget_id,
                               scene.wire({"expected_version": version, "limit": "151"}), str(uuid4()))
        scene.require(status == 404, "Other owner changed a budget")
    edited = write(client, state, "edit", "PATCH", "/financial-plan/budgets/" + budget_id,
                   {"expected_version": created["budget"]["version"], "limit": "160"})
    replay(client, state, "edit")
    progress(client, budget_id, (15500, 500, 0))
    for name, labels, categories, limit, currency, month, uncategorized, expected in (
        ("uncategorized", ["checking"], [], "10", "DOP", "2026-09", True, (700, 300, 0)),
        ("currency", ["usd"], ["groceries"], "100", "USD", "2026-09", False, (5000, 5000, 0)),
        ("refund_destination", ["cash"], ["groceries"], "10", "DOP", "2026-09", False, (0, 1000, 0)),
        ("previous_month", ["checking", "card"], ["groceries"], "150", "DOP", "2026-08", False, (0, 15000, 0)),
        ("unknown", ["unknown"], ["groceries"], "10", "DOP", "2026-09", False, (300, 700, 0)),
    ):
        extra = write(client, state, name, "POST", "/financial-plan/budgets",
                      definition(fixture, "Budget scope " + name, labels, categories, limit,
                                 currency, month, uncategorized))
        progress(client, extra["budget"]["id"], expected)
    search = scene.expect(client, "GET", "/financial-search?" + urlencode({
        "q": edited["budget"]["name"], "kind": "budget", "currency": "DOP"}))
    scene.require(any(row["budget"]["id"] == budget_id for row in search["items"]),
                  "Search did not return the canonical budget")
    state["complete"] = True
    scene.save_state(state)


def readback(client, state):
    scene.require(state.get("complete"), "Run the connected journey first")
    budget_id = state["operations"]["budget"]["result"]["budget"]["id"]
    result = progress(client, budget_id, (15500, 500, 0))
    scene.require(result["budget"]["limit_minor"] == 16000 and len(result["contributors"]) == 4,
                  "Saved budget definition or contributors differ")
    return {"journey": "connected_budget_api", "phases": state["checks"],
            "final_spent_minor": 15500, "final_limit_minor": 16000,
            "contributors": 4, "scope_checks": 5, "canonical_retries": 5,
            "owner_read_and_write_isolation": True,
            "limitations": "Native UI, transport-loss recovery and boundary matrix recorded separately"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "readback"))
    action = parser.parse_args().action
    config = scene.load_client()
    fixture = scene.load_state(create=False)
    scene.STATE = scene.WORK / "budgets-journey-private.json"
    state = scene.load_state(create=action == "run")
    client = Client(config)
    if action == "run":
        run(client, state, fixture)
    print(json.dumps(readback(client, state), sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (scene.Refused, ValueError, KeyError, TypeError, OSError) as error:
        print(str(error) if isinstance(error, scene.Refused) else "Local journey state or response is invalid", file=sys.stderr)
        raise SystemExit(1) from None
