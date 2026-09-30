"""Retained synthetic debt journey on isolated loopback allocation 59200."""

from __future__ import annotations

import argparse
import fcntl
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "ios/.build/accounts-local-59200"
PROOF = ROOT / "docs/reports/evidence/connected-debt-plans/debt-api-proof.json"
DEBTS = "/financial-plan/debts"
ZONE = "America/Santo_Domingo"

# The private journal, exact-byte retry and auth transport have one implementation.
SPEC = importlib.util.spec_from_file_location(
    "debt_local_transport", Path(__file__).with_name("goals-journey.py")
)
scene = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scene)
scene.WORK = WORK
scene.API = "http://127.0.0.1:59200/api/v1"
scene.AUTH = "http://127.0.0.1:59201"
scene.PROXY = "http://127.0.0.1:59212"
scene.GOALS = DEBTS
require, wire, get = scene.require, scene.wire, scene.get

ACCOUNT_FIXTURES = (
    ("bank", "checking", "DOP", "2000", 200000),
    ("savings", "savings", "DOP", "300", 30000),
    ("loan", "other_debt", "DOP", "1000", -100000),
    ("card", "credit_card", "DOP", "400", -40000),
    ("unknown", "other_debt", "DOP", None, None),
    ("usd_bank", "checking", "USD", "1000", 100000),
    ("usd_loan", "other_debt", "USD", "500", -50000),
)


def ids(journal):
    return {
        label: journal.state["operations"]["account_" + label]["result"]["id"]
        for label, *_ in ACCOUNT_FIXTURES
    }


def command(journal, client, name, method, path, body, statuses=(200, 201), owner=0):
    return journal.command(
        client, name, method, path, body, statuses=statuses, owner=owner
    )


def identity(journal, operation, key):
    return journal.state["operations"][operation]["result"][key]["id"]


def replay(journal, client, name):
    op = journal.state["operations"][name]
    status, result = client.api(
        op["owner"], op["method"], op["path"], op["body"].encode(), op["key"]
    )
    require(
        status in op["statuses"] and result.get("replayed") is True,
        "Exact retry did not replay the accepted command",
    )
    return result


def check_accounts(client, accounts, expected):
    for label, amount in expected.items():
        row = get(client, "/financial-accounts/" + accounts[label])
        require(
            row["balance"]["amount_minor"] == amount,
            "Account differs from independent literal expected balance: " + label,
        )
        require(
            row["balance"]["state"] == ("unknown" if amount is None else "known"),
            "Missing balance became known",
        )


def setup(journal, client):
    now = datetime.fromisoformat(journal.state["now"])
    opened = (now - timedelta(days=60)).replace(hour=9, minute=0, second=0)
    for label, kind, currency, amount, _ in ACCOUNT_FIXTURES:
        body = {
            "type": kind,
            "currency": currency,
            "nickname": "Debt demo " + label + " " + journal.state["suffix"],
        }
        if amount is not None:
            body |= {"amount": amount, "as_of": opened.isoformat(), "time_zone": ZONE}
        command(
            journal,
            client,
            "account_" + label,
            "POST",
            "/financial-accounts",
            lambda body=body: body,
        )
    accounts = ids(journal)
    command(
        journal,
        client,
        "cost_budget",
        "POST",
        "/financial-plan/budgets",
        lambda: {
            "name": "Loan costs " + journal.state["suffix"],
            "limit": "50",
            "currency": "DOP",
            "month": now.strftime("%Y-%m"),
            "account_ids": [accounts["bank"]],
            "category_ids": ["interest_fees"],
            "include_uncategorized": False,
        },
    )
    command(
        journal,
        client,
        "goal",
        "POST",
        "/financial-plan/goals",
        lambda: {
            "name": "Debt funding reserve " + journal.state["suffix"],
            "currency": "DOP",
            "target": "2000",
            "destination_account_id": accounts["bank"],
        },
    )
    gid = journal.state["operations"]["goal"]["result"]["goal"]["goal"]["id"]
    command(
        journal,
        client,
        "allocation",
        "PUT",
        "/financial-plan/goals/allocations",
        lambda: {
            "changes": [
                {
                    "goal_id": gid,
                    "expected_version": get(client, "/financial-plan/goals/" + gid)[
                        "goal"
                    ]["version"],
                    "account_id": accounts["bank"],
                    "amount": "1500",
                    "release_claim_ids": [],
                }
            ],
            "expected_account_versions": scene.versions(client, [accounts["bank"]]),
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
            "account_ids": [accounts["bank"], accounts["savings"], accounts["usd_bank"]],
            "time_zone": ZONE,
        },
    )
    if "initial" not in journal.state["checks"]:
        check_accounts(
            client,
            accounts,
            {label: expected for label, *_, expected in ACCOUNT_FIXTURES},
        )
        budget = get(
            client,
            "/financial-plan/budgets/" + identity(journal, "cost_budget", "budget"),
        )
        require(
            budget["spent_minor"] == "0" and budget["remaining_minor"] == "5000",
            "Creating a budget changed actual spending",
        )
        goal = get(client, "/financial-plan/goals/" + gid)
        require(
            goal["supported_minor"] == "150000" and goal["planned_minor"] == "0",
            "Existing savings assignment changed actual or planned money",
        )
        journal.state["checks"]["initial"] = {
            "account_balances_minor": {
                label: expected for label, *_, expected in ACCOUNT_FIXTURES
            },
            "budget_spent_minor": 0,
            "goal_supported_minor": 150000,
            "goal_planned_minor": 0,
        }
        journal.save()
    return accounts


def debt_id(journal, label="loan"):
    return journal.state["operations"]["debt_" + label]["result"]["debt"]["debt"]["id"]


def debt(client, journal, label="loan"):
    return get(client, DEBTS + "/" + debt_id(journal, label))


def payment_body(journal, source, destination, amount, split=None, *, original=None):
    body = {
        "kind": "payment_reversal"
        if original
        else "debt_payment"
        if split
        else "card_payment",
        "source_account_id": source,
        "destination_account_id": destination,
        "amount": amount,
        "occurred_at": journal.state["now"],
        "time_zone": ZONE,
        "note": "Debt payment " + journal.state["suffix"],
        "coverage": [],
        "expected_versions": {},
    }
    if split:
        body |= dict(zip(("principal", "interest", "fees"), split, strict=True))
    if original:
        body["reversal_of_activity_id"] = original
    return body


def reviewed_money(client, body, path, owner=0):
    status, preview = client.api(owner, "POST", path + "/preview", wire(body))
    require(status == 200, "Money preview returned HTTP " + str(status))
    if not preview["ready"]:
        # These new fixture events happen after the retained check and were not in it.
        answers = [
            {
                "account_id": effect["account_id"],
                "observation_id": q["observation_id"],
                "included": False,
            }
            for effect in preview["affected_accounts"]
            for q in effect["observations"]
            if q["included"] is None
        ]
        status, preview = client.api(
            owner, "POST", path + "/preview", wire(body | {"coverage": answers})
        )
    require(
        status == 200 and preview["ready"],
        "Fixture coverage did not produce a ready review",
    )
    return preview["reviewed_request"] | {"preview_token": preview["preview_token"]}


def money(journal, client, name, body, activity_id=None, owner=0):
    path = "/financial-activities" + ("/" + activity_id if activity_id else "")
    return command(
        journal,
        client,
        name,
        "PATCH" if activity_id else "POST",
        path,
        lambda: reviewed_money(client, body, path, owner),
        owner=owner,
    )


def occurrence_id(client, journal, label="loan"):
    if label in journal.state.setdefault("occurrence_ids", {}):
        return journal.state["occurrence_ids"][label]
    row = debt(client, journal, label)["occurrences"][0]
    journal.state["occurrence_ids"][label] = row["id"]
    journal.save()
    return row["id"]


def record(journal, client, name, body, label="loan", occurrence=True):
    path = DEBTS + "/" + debt_id(journal, label) + "/payments"

    def review():
        request = {
            "expected_version": debt(client, journal, label)["debt"]["version"],
            "activity": body,
        }
        if occurrence:
            request["occurrence_id"] = occurrence_id(client, journal, label)
        status, preview = client.api(0, "POST", path + "/preview", wire(request))
        require(
            status == 200 and preview["money"]["ready"],
            "Debt payment preview was not ready",
        )
        request["activity"] = preview["money"]["reviewed_request"] | {
            "preview_token": preview["money"]["preview_token"]
        }
        return request

    return command(journal, client, name, "POST", path, review)


def link(journal, client, name, actual, label="loan"):
    accounts = ids(journal)
    return command(
        journal,
        client,
        name,
        "POST",
        DEBTS + "/" + debt_id(journal, label) + "/payments/link",
        lambda: {
            "expected_version": debt(client, journal, label)["debt"]["version"],
            "activity_id": actual["activity_id"],
            "activity_revision": actual["revision"],
            "occurrence_id": occurrence_id(client, journal, label),
            "expected_account_versions": scene.versions(
                client, [accounts["bank"], accounts[label]]
            ),
        },
    )


def stage(
    journal,
    client,
    name,
    bank,
    loan,
    spending,
    remaining,
    *,
    card=-40000,
    goal_state="active",
    clear=False,
):
    if name in journal.state["checks"]:
        return
    accounts = ids(journal)
    check_accounts(
        client,
        accounts,
        {
            "bank": bank,
            "loan": loan,
            "card": card,
            "savings": 30000,
            "unknown": None,
            "usd_bank": 100000,
            "usd_loan": -50000,
        },
    )
    current = debt(client, journal)
    require(
        current["balance"]["amount_minor"] == loan
        and current["state"] == ("recorded_clear" if clear else "active"),
        "Debt detail disagrees with the recorded position",
    )
    row = next(
        r for r in current["occurrences"] if r["id"] == occurrence_id(client, journal)
    )
    require(
        row["remaining_minor"] == remaining,
        "Linked payment did not leave the independent unpaid amount",
    )
    if remaining == 0:
        require(row["status"] == "fulfilled", "Covered occurrence is not fulfilled")
    budget = get(
        client, "/financial-plan/budgets/" + identity(journal, "cost_budget", "budget")
    )
    require(
        int(budget["spent_minor"]) == spending
        and int(budget["remaining_minor"]) == 5000 - spending
        and int(budget["over_budget_minor"]) == max(0, spending - 5000),
        "Budget counted principal, counted a payment twice, or lost its costs",
    )
    gid = journal.state["operations"]["goal"]["result"]["goal"]["goal"]["id"]
    goal = get(client, "/financial-plan/goals/" + gid)
    require(
        goal["state"] == goal_state
        and int(goal["independently_backed_minor"]) == (150000 if bank >= 150000 else 0)
        and int(goal["supported_minor"]) == min(bank, 150000),
        "Debt cash movement lost existing savings backing",
    )
    pool = current["funding_pool"]
    require(
        pool is not None
        and int(pool["backing_minor"]) == bank
        and int(pool["assigned_minor"]) == 150000
        and int(pool["available_minor"]) == max(0, bank - 150000)
        and int(pool["shortfall_minor"]) == max(0, 150000 - bank),
        "Debt created a separate allocation owner or hid assigned savings",
    )
    snapshot = get(client, "/financial-plan")
    standalone = get(client, "/financial-home")
    for rows in (snapshot["debts"], snapshot["home"]["debts"], standalone["debts"]):
        nested = next(r for r in rows if r["debt"]["id"] == current["debt"]["id"])
        require(
            nested["balance"]["amount_minor"] == loan
            and nested["state"] == current["state"],
            "Accounts, Plan and Home show different debt",
        )
    currency = next(r for r in standalone["currencies"] if r["currency"] == "DOP")
    require(
        int(currency["net_spending_minor"]) == spending
        and currency["unknown_accounts"] == 1,
        "Home spending or unknown debt differs",
    )
    owned_ids = {r["id"] for r in current["occurrences"]}
    points = [
        p
        for c in snapshot["currencies"]
        if c["currency"] == "DOP"
        for p in c["points"]
        if p["occurrence_id"] in owned_ids
    ]
    selected = [p for p in points if p["occurrence_id"] == row["id"]]
    require(
        not selected
        if remaining == 0 or clear
        else len(selected) == 1 and int(selected[0]["change_minor"]) == -remaining,
        "Forecast did not consume the linked payment exactly once",
    )
    if clear:
        require(not points, "Recorded clear debt still consumes future cash")
    journal.state["checks"][name] = {
        "bank_minor": bank,
        "loan_position_minor": loan,
        "budget_spent_minor": spending,
        "occurrence_remaining_minor": remaining,
        "goal_state": goal_state,
        "debt_state": current["state"],
    }
    journal.save()


def run(journal, client):
    accounts = setup(journal, client)
    day = datetime.fromisoformat(journal.state["now"]).date().isoformat()
    for label, amount in (
        ("loan", "500"),
        ("card", "400"),
        ("unknown", "40"),
        ("usd_loan", "100"),
    ):
        source = accounts["usd_bank"] if label == "usd_loan" else accounts["bank"]
        command(
            journal,
            client,
            "debt_" + label,
            "POST",
            DEBTS,
            lambda label=label, amount=amount, source=source: {
                "debt_account_id": accounts[label],
                "name": "Debt plan " + label + " " + journal.state["suffix"],
                "source_account_id": source,
                "amount": amount,
                "schedule": {
                    "cadence": "monthly" if label in {"loan", "usd_loan"} else "once",
                    "start_date": day,
                },
            },
        )
    replay(journal, client, "debt_loan")
    if "no_invented_terms" not in journal.state["checks"]:
        for label, reason in (("loan", "terms_missing"), ("unknown", "balance_unknown")):
            require(
                debt(client, journal, label)["payoff"]["reason"] == reason,
                "Payoff invented a balance, rate or breakdown",
            )
        journal.state["checks"]["no_invented_terms"] = True
        journal.save()
    first_body = payment_body(
        journal, accounts["bank"], accounts["loan"], "350", ("300", "40", "10")
    )
    first = money(journal, client, "first_payment", first_body)["activity"]
    replay(journal, client, "first_payment")
    command(
        journal,
        client,
        "link_first",
        "POST",
        DEBTS + "/" + debt_id(journal) + "/payments/link",
        lambda: {
            "expected_version": debt(client, journal)["debt"]["version"],
            "activity_id": first["activity_id"],
            "activity_revision": first["revision"],
            "occurrence_id": occurrence_id(client, journal),
            "expected_account_versions": scene.versions(
                client, [accounts["bank"], accounts["loan"]]
            ),
        },
    )
    replay(journal, client, "link_first")
    stage(journal, client, "linked_partial", 165000, -70000, 5000, 15000)
    money(
        journal,
        client,
        "correct_first",
        first_body
        | {
            "amount": "300",
            "principal": "250",
            "expected_revision": first["revision"],
            "reason": "Correct principal from the receipt",
        },
        first["activity_id"],
    )["activity"]
    replay(journal, client, "correct_first")
    stage(journal, client, "corrected_partial", 170000, -75000, 5000, 20000)
    record(
        journal,
        client,
        "second_payment",
        payment_body(
            journal, accounts["bank"], accounts["loan"], "200", ("180", "15", "5")
        ),
    )
    replay(journal, client, "second_payment")
    stage(journal, client, "fulfilled_once", 150000, -57000, 7000, 0)
    extra = record(
        journal,
        client,
        "extra_payment",
        payment_body(
            journal, accounts["bank"], accounts["loan"], "800", ("750", "40", "10")
        ),
        occurrence=False,
    )["activity"]
    stage(
        journal,
        client,
        "overpayment_credit_and_savings_shortfall",
        70000,
        18000,
        12000,
        0,
        goal_state="needs_review",
        clear=True,
    )
    record(
        journal,
        client,
        "card_payment",
        payment_body(journal, accounts["bank"], accounts["card"], "400"),
        label="card",
    )
    stage(
        journal,
        client,
        "card_no_second_purchase",
        30000,
        18000,
        12000,
        0,
        card=0,
        goal_state="needs_review",
        clear=True,
    )
    money(
        journal,
        client,
        "partial_return",
        payment_body(
            journal,
            accounts["bank"],
            accounts["loan"],
            "100",
            ("80", "15", "5"),
            original=extra["activity_id"],
        ),
    )
    stage(
        journal,
        client,
        "explicit_partial_return",
        40000,
        10000,
        10000,
        0,
        card=0,
        goal_state="needs_review",
        clear=True,
    )
    money(
        journal,
        client,
        "remaining_return",
        payment_body(
            journal,
            accounts["bank"],
            accounts["loan"],
            "700",
            ("670", "25", "5"),
            original=extra["activity_id"],
        ),
    )
    replay(journal, client, "remaining_return")
    stage(
        journal,
        client,
        "returned_payment_reopens_debt",
        110000,
        -57000,
        7000,
        0,
        card=0,
        goal_state="needs_review",
    )
    actual = get(client, "/financial-activities/" + extra["activity_id"])
    require(
        actual["amount_minor"] == 80000 and actual["principal_minor"] == 75000,
        "Returning a payment rewrote its original activity",
    )
    income = {
        "kind": "income",
        "account_id": accounts["bank"],
        "amount": "400",
        "occurred_at": journal.state["now"],
        "time_zone": ZONE,
        "source_id": "other",
    }
    money(journal, client, "restore_funding", income)
    card = journal.state["operations"]["card_payment"]["result"]["activity"]
    money(
        journal,
        client,
        "card_return",
        payment_body(
            journal,
            accounts["bank"],
            accounts["card"],
            "100",
            original=card["activity_id"],
        ),
    )
    stage(journal, client, "card_return_cost_zero", 160000, -57000, 7000, 0, card=-10000)
    record(
        journal,
        client,
        "unknown_payment",
        payment_body(
            journal, accounts["bank"], accounts["unknown"], "40", ("25", "10", "5")
        ),
        label="unknown",
    )
    stage(journal, client, "unknown_stays_unknown", 156000, -57000, 8500, 0, card=-10000)
    record(
        journal,
        client,
        "usd_payment",
        payment_body(
            journal, accounts["usd_bank"], accounts["usd_loan"], "110", ("100", "8", "2")
        ),
        label="usd_loan",
    )
    check_accounts(
        client, accounts, {"usd_bank": 89000, "usd_loan": -40000, "unknown": None}
    )
    journal.state["checks"]["currency_isolation"] = {
        "usd_bank_minor": 89000,
        "usd_debt_minor": -40000,
        "dop_budget_spent_minor": 8500,
    }
    journal.save()
    journal.state["payments_complete"] = True
    journal.save()


def reject(journal, client, name, method, path, body, statuses):
    result = command(journal, client, name, method, path, lambda: body, statuses)
    require("detail" in result, "Rejected request has no explicit error")
    return result


def lifecycle(journal, client):
    accounts, did = ids(journal), debt_id(journal)
    path = DEBTS + "/" + did
    first = journal.state["operations"]["first_payment"]["result"]["activity"]
    if "constraints" not in journal.state["checks"]:
        before = scene.versions(client, list(accounts.values()))
        invalid = payment_body(journal, accounts["bank"], accounts["loan"], "10")
        invalid["kind"] = "debt_payment"
        reject(
            journal,
            client,
            "reject_missing_breakdown",
            "POST",
            "/financial-activities/preview",
            invalid,
            (400, 422),
        )
        invalid = payment_body(
            journal, accounts["bank"], accounts["usd_loan"], "10", ("8", "1", "1")
        )
        reject(
            journal,
            client,
            "reject_mixed_currency",
            "POST",
            "/financial-activities/preview",
            invalid,
            (400, 422),
        )
        extra = journal.state["operations"]["extra_payment"]["result"]["activity"]
        invalid = payment_body(
            journal,
            accounts["bank"],
            accounts["loan"],
            "1",
            ("1", "0", "0"),
            original=extra["activity_id"],
        )
        reject(
            journal,
            client,
            "reject_excess_return",
            "POST",
            "/financial-activities/preview",
            invalid,
            (400, 422),
        )
        invalid = payment_body(
            journal, accounts["bank"], accounts["loan"], "790", ("740", "40", "10")
        ) | {
            "expected_revision": extra["revision"],
            "reason": "Below already returned principal",
        }
        reject(
            journal,
            client,
            "reject_under_returned_correction",
            "POST",
            "/financial-activities/" + extra["activity_id"] + "/preview",
            invalid,
            (400, 422),
        )
        reject(
            journal,
            client,
            "reject_stale_link",
            "POST",
            path + "/payments/link",
            {
                "expected_version": debt(client, journal)["debt"]["version"],
                "activity_id": first["activity_id"],
                "activity_revision": first["revision"],
                "expected_account_versions": scene.versions(
                    client, [accounts["bank"], accounts["loan"]]
                ),
            },
            (409,),
        )
        require(
            scene.versions(client, list(accounts.values())) == before,
            "Rejected write changed accounts",
        )
        journal.state["checks"]["constraints"] = {
            "missing_split": "rejected",
            "mixed_currency": "rejected",
            "component_return_cap": "rejected",
            "correction_below_returned": "rejected",
            "stale_link": "rejected",
        }
        journal.save()
    if "owner_isolation" not in journal.state["checks"]:
        for target in (path, path + "/payments/candidates"):
            status, _ = client.api(1, "GET", target)
            require(status == 404, "Foreign owner could inspect debt")
        status, _ = client.api(
            1,
            "PATCH",
            path,
            wire(
                {
                    "expected_version": debt(client, journal)["debt"]["version"],
                    "name": "foreign",
                }
            ),
            scene.secrets.token_hex(16),
        )
        require(status == 404, "Foreign owner could edit debt")
        query = "/financial-search?kind=debt&q=" + journal.state["suffix"]
        require(not get(client, query, owner=1)["items"], "Search exposed foreign debt")
        require(
            len(get(client, query)["items"]) == 4, "Owned Search did not find all plans"
        )
        journal.state["checks"]["owner_isolation"] = True
        journal.save()
    command(
        journal,
        client,
        "rename",
        "PATCH",
        path,
        lambda: {
            "expected_version": debt(client, journal)["debt"]["version"],
            "name": "Loan repayment " + journal.state["suffix"],
        },
    )
    replay(journal, client, "rename")
    reject(
        journal,
        client,
        "reject_stale_edit",
        "PATCH",
        path,
        {"expected_version": 1, "name": "stale overwrite"},
        (409,),
    )
    command(
        journal,
        client,
        "archive",
        "PATCH",
        path,
        lambda: {
            "expected_version": debt(client, journal)["debt"]["version"],
            "archived": True,
        },
    )
    if "archived" not in journal.state["checks"]:
        current = debt(client, journal)
        require(
            current["debt"]["archived"] and current["payments"],
            "Archive lost debt history",
        )
        require(
            not any(
                r["debt"]["id"] == did for r in get(client, "/financial-home")["debts"]
            ),
            "Archived debt still in active Home",
        )
        check_accounts(client, accounts, {"bank": 156000, "loan": -57000, "card": -10000})
        journal.state["checks"]["archived"] = True
        journal.save()
    command(
        journal,
        client,
        "restore",
        "PATCH",
        path,
        lambda: {
            "expected_version": debt(client, journal)["debt"]["version"],
            "archived": False,
        },
    )
    if "restored" not in journal.state["checks"]:
        current = debt(client, journal)
        require(
            not current["debt"]["archived"] and len(current["payments"]) == 3,
            "Restore duplicated or lost payment claims",
        )
        require(
            next(
                r
                for r in current["occurrences"]
                if r["id"] == occurrence_id(client, journal)
            )["remaining_minor"]
            == 0,
            "Restore lost fulfilled occurrence",
        )
        journal.state["checks"]["restored"] = True
        journal.save()
    check_path = "/financial-accounts/" + accounts["loan"] + "/balance-checks"

    def balance_check():
        journal.state.setdefault("checked_at", datetime.now(ZoneInfo(ZONE)).isoformat())
        journal.save()
        body = {
            "expected_version": get(client, "/financial-accounts/" + accounts["loan"])[
                "version"
            ],
            "amount": "500",
            "as_of": journal.state["checked_at"],
            "time_zone": ZONE,
            "note": "Statement remaining principal; difference is not spending",
        }
        preview = get_preview(client, check_path + "/preview", body)
        require(
            preview["expected_amount_minor"] == -57000
            and preview["observed_amount_minor"] == -50000
            and preview["difference_minor"] == 7000,
            "Reconciliation difference was invented or double counted",
        )
        return body | {"preview_token": preview["preview_token"]}

    command(journal, client, "principal_check", "POST", check_path, balance_check)
    replay(journal, client, "principal_check")
    checked_day = datetime.fromisoformat(journal.state["checked_at"]).date()
    import calendar

    month = checked_day.month % 12 + 1
    year = checked_day.year + (checked_day.month == 12)
    next_due = checked_day.replace(
        year=year,
        month=month,
        day=min(checked_day.day, calendar.monthrange(year, month)[1]),
    )
    command(
        journal,
        client,
        "explicit_projection",
        "PATCH",
        path,
        lambda: {
            "expected_version": debt(client, journal)["debt"]["version"],
            "amount": "500",
            "schedule": {"cadence": "monthly", "start_date": next_due.isoformat()},
            "effective_date": debt(client, journal)["debt"]["earliest_effective_date"],
            "assumptions": {
                "annual_rate_percent": "12",
                "recurring_fees": "0",
                "first_period_start": checked_day.isoformat(),
                "no_new_borrowing": True,
            },
        },
    )
    if "conditional_projection" not in journal.state["checks"]:
        current = debt(client, journal)
        require(
            current["balance"]["amount_minor"] == -50000,
            "Projection changed recorded principal",
        )
        require(
            current["payoff"]["state"] == "conditional"
            and current["payoff"]["payments"] == 2
            and current["payoff"]["total_interest_minor"] == "505"
            and current["payoff"]["total_fees_minor"] == "0",
            "Explicit monthly scenario differs from independent two-payment calculation",
        )
        budget = get(
            client,
            "/financial-plan/budgets/" + identity(journal, "cost_budget", "budget"),
        )
        require(
            budget["spent_minor"] == "8500", "Balance check or projection became spending"
        )
        journal.state["checks"]["conditional_projection"] = {
            "recorded_principal_minor": 50000,
            "payments": 2,
            "projected_interest_minor": 505,
            "recorded_costs_minor": 8500,
            "apr_percent": 12,
            "monthly_fees_minor": 0,
            "no_new_borrowing": True,
        }
        journal.save()
    command(
        journal,
        client,
        "edit_amount",
        "PATCH",
        path,
        lambda: {
            "expected_version": debt(client, journal)["debt"]["version"],
            "amount": "600",
        },
    )
    if "edited_projection" not in journal.state["checks"]:
        current = debt(client, journal)
        require(
            current["debt"]["amount_minor"] == 60000
            and current["payoff"]["payments"] == 1
            and current["payoff"]["total_interest_minor"] == "500",
            "Editing payment did not refresh scenario",
        )
        check_accounts(
            client,
            accounts,
            {"bank": 156000, "loan": -50000, "usd_bank": 89000, "usd_loan": -40000},
        )
        journal.state["checks"]["edited_projection"] = True
        journal.save()
    command(
        journal,
        client,
        "restore_amount",
        "PATCH",
        path,
        lambda: {
            "expected_version": debt(client, journal)["debt"]["version"],
            "amount": "500",
        },
    )
    journal.state["lifecycle_complete"] = True
    journal.save()


def get_preview(client, path, body):
    status, result = client.api(0, "POST", path, wire(body))
    require(status == 200, "Check preview failed")
    return result


def interest_only(journal, client):
    accounts = ids(journal)
    paid = money(
        journal,
        client,
        "interest_only_real",
        payment_body(
            journal, accounts["bank"], accounts["loan"], "100", ("0", "90", "10")
        ),
    )["activity"]
    if "interest_only_real" not in journal.state["checks"]:
        check_accounts(client, accounts, {"bank": 146000, "loan": -50000})
        budget = get(
            client,
            "/financial-plan/budgets/" + identity(journal, "cost_budget", "budget"),
        )
        require(
            budget["spent_minor"] == "18500",
            "Interest-only costs were lost or principal invented",
        )
        journal.state["checks"]["interest_only_real"] = {
            "principal_minor": 0,
            "cost_minor": 10000,
            "bank_minor": 146000,
            "loan_position_minor": -50000,
        }
        journal.save()
    money(
        journal,
        client,
        "interest_only_return",
        payment_body(
            journal,
            accounts["bank"],
            accounts["loan"],
            "100",
            ("0", "90", "10"),
            original=paid["activity_id"],
        ),
    )
    if "interest_only_return" not in journal.state["checks"]:
        check_accounts(client, accounts, {"bank": 156000, "loan": -50000})
        budget = get(
            client,
            "/financial-plan/budgets/" + identity(journal, "cost_budget", "budget"),
        )
        require(
            budget["spent_minor"] == "8500",
            "Interest-only return did not reverse exact costs",
        )
        journal.state["checks"]["interest_only_return"] = {
            "net_cost_minor": 0,
            "bank_minor": 156000,
            "loan_position_minor": -50000,
        }
        journal.save()


def dated_return(journal, client):
    now = datetime.fromisoformat(journal.state["now"])
    start = now.replace(day=1, hour=0, minute=30, second=0, microsecond=0)
    previous = start - timedelta(hours=1)
    names = {}
    for label, kind, amount in (
        ("cash", "checking", "1000"),
        ("loan", "other_debt", "500"),
    ):
        row = command(
            journal,
            client,
            "history_" + label,
            "POST",
            "/financial-accounts",
            lambda label=label, kind=kind, amount=amount: {
                "type": kind,
                "currency": "DOP",
                "amount": amount,
                "as_of": (now - timedelta(days=60)).isoformat(),
                "time_zone": ZONE,
                "nickname": "Dated return " + label + " " + journal.state["suffix"],
            },
            owner=1,
        )
        names[label] = row["id"]
    created = command(
        journal,
        client,
        "history_plan",
        "POST",
        DEBTS,
        lambda: {
            "debt_account_id": names["loan"],
            "name": "Dated return plan " + journal.state["suffix"],
            "source_account_id": names["cash"],
            "amount": "120",
            "schedule": {"cadence": "once", "start_date": previous.date().isoformat()},
        },
        owner=1,
    )
    did = created["debt"]["debt"]["id"]
    payment = money(
        journal,
        client,
        "history_payment",
        payment_body(journal, names["cash"], names["loan"], "120", ("100", "15", "5"))
        | {"occurred_at": previous.isoformat()},
        owner=1,
    )["activity"]
    command(
        journal,
        client,
        "history_link",
        "POST",
        DEBTS + "/" + did + "/payments/link",
        lambda: {
            "expected_version": get(client, DEBTS + "/" + did, owner=1)["debt"][
                "version"
            ],
            "activity_id": payment["activity_id"],
            "activity_revision": payment["revision"],
            "occurrence_id": get(client, DEBTS + "/" + did, owner=1)["occurrences"][0][
                "id"
            ],
            "expected_account_versions": {
                aid: get(client, "/financial-accounts/" + aid, owner=1)["version"]
                for aid in names.values()
            },
        },
        owner=1,
    )
    money(
        journal,
        client,
        "history_return",
        payment_body(
            journal,
            names["cash"],
            names["loan"],
            "60",
            ("50", "7.50", "2.50"),
            original=payment["activity_id"],
        )
        | {"occurred_at": start.isoformat()},
        owner=1,
    )
    command(
        journal,
        client,
        "history_selection",
        "PUT",
        "/financial-plan/selection",
        lambda: {
            "expected_version": get(client, "/financial-plan", owner=1)["selection"][
                "version"
            ],
            "account_ids": [names["cash"]],
            "time_zone": ZONE,
        },
        owner=1,
    )
    if "return_month_and_missed_occurrence" not in journal.state["checks"]:
        for month, expected in (
            (previous.strftime("%Y-%m"), 2000),
            (start.strftime("%Y-%m"), -1000),
        ):
            home = get(
                client, "/financial-home?month=" + month + "&time_zone=" + ZONE, owner=1
            )
            row = next(r for r in home["currencies"] if r["currency"] == "DOP")
            require(
                int(row["net_spending_minor"]) == expected,
                "Return changed original month or lost current-period costs",
            )
        cash = get(client, "/financial-accounts/" + names["cash"], owner=1)
        loan = get(client, "/financial-accounts/" + names["loan"], owner=1)
        current = get(client, DEBTS + "/" + did, owner=1)
        occurrence = current["occurrences"][0]
        require(
            cash["balance"]["amount_minor"] == 94000
            and loan["balance"]["amount_minor"] == -45000,
            "Dated partial return did not restore its explicit component amounts",
        )
        require(
            occurrence["overdue"] and occurrence["remaining_minor"] == 6000,
            "Missed partial obligation disappeared",
        )
        snapshot = get(client, "/financial-plan", owner=1)
        points = [
            p
            for currency in snapshot["currencies"]
            for p in currency["points"]
            if p["occurrence_id"] == occurrence["id"]
        ]
        require(
            len(points) == 1 and int(points[0]["change_minor"]) == -6000,
            "Overdue remainder is absent or duplicated in forecast",
        )
        journal.state["checks"]["return_month_and_missed_occurrence"] = {
            "payment_month": previous.strftime("%Y-%m"),
            "original_costs_minor": 2000,
            "return_month": start.strftime("%Y-%m"),
            "returned_costs_minor": 1000,
            "net_principal_paid_minor": 5000,
            "overdue_remaining_minor": 6000,
        }
        journal.save()
    require(
        not client.response_loss or journal.state.get("response_loss_verified"),
        "Response-loss run did not prove a committed retry",
    )
    journal.state["history_complete"] = True
    journal.save()


def observe(journal, client, observational=False):
    accounts = ids(journal)
    result = {
        "stage": "api_complete"
        if journal.state.get("api_complete")
        else "payments_complete"
        if journal.state.get("payments_complete")
        else "synthetic_baseline",
        "allocation": 59200,
        "suffix": journal.state["suffix"],
        "checks": journal.state["checks"],
        "committed_response_loss": journal.state.get("response_loss_verified", False),
        "readback_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "readback_at": datetime.now(ZoneInfo("UTC")).isoformat(),
        "observational": observational,
        "current_accounts": {},
    }
    for label, account in accounts.items():
        row = get(client, "/financial-accounts/" + account)
        result["current_accounts"][label] = {
            "state": row["balance"]["state"],
            "amount_minor": row["balance"]["amount_minor"],
            "currency": row["currency"],
        }
    if journal.state.get("api_complete") and not observational:
        check_accounts(
            client,
            accounts,
            {
                "bank": 156000,
                "loan": -50000,
                "card": -10000,
                "savings": 30000,
                "unknown": None,
                "usd_bank": 89000,
                "usd_loan": -40000,
            },
        )
        current = debt(client, journal)
        require(
            current["debt"]["name"] == "Loan repayment " + journal.state["suffix"]
            and current["debt"]["amount_minor"] == 50000
            and not current["debt"]["archived"]
            and len(current["payments"]) == 3,
            "Retained plan or claims differ",
        )
        require(
            next(
                r
                for r in current["occurrences"]
                if r["id"] == occurrence_id(client, journal)
            )["remaining_minor"]
            == 0,
            "Reopening lost the fulfilled occurrence",
        )
        pool = current["funding_pool"]
        require(
            pool["backing_minor"] == "156000"
            and pool["assigned_minor"] == "150000"
            and pool["available_minor"] == "6000",
            "Retained allocation pool differs",
        )
        budget = get(
            client,
            "/financial-plan/budgets/" + identity(journal, "cost_budget", "budget"),
        )
        require(budget["spent_minor"] == "8500", "Retained costs differ")
        result["retained_state_verified"] = True
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("setup", "run", "readback"))
    parser.add_argument(
        "--response-loss",
        action="store_true",
        help="Use only owned59212 proxy to prove a lost accepted response",
    )
    parser.add_argument(
        "--observe",
        action="store_true",
        help="Read later human edits without claiming the original fixture totals",
    )
    args = parser.parse_args()
    config = scene.read_private(WORK / "client.json")
    scene.validate_config(config)
    require(not WORK.is_symlink(), "Refusing symlinked fixture directory")
    fd = os.open(
        WORK / "debt-journey.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(fd, "w") as lock:
        os.fchmod(lock.fileno(), 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise scene.Refused("Another journey owns this private journal") from None
        journal = scene.Journal(
            WORK / "debt-journey-private.json", create=args.action in {"setup", "run"}
        )
        client = scene.Client(config, journal, response_loss=args.response_loss)
        if args.action == "setup":
            setup(journal, client)
        if args.action == "run" and not journal.state.get("payments_complete"):
            run(journal, client)
        if args.action == "run" and not journal.state.get("lifecycle_complete"):
            lifecycle(journal, client)
        if args.action == "run" and not journal.state.get("history_complete"):
            dated_return(journal, client)
        if args.action == "run" and not journal.state["checks"].get(
            "interest_only_return"
        ):
            interest_only(journal, client)
        if args.action == "run":
            journal.state["api_complete"] = True
            journal.save()
        result = observe(journal, client, observational=args.observe)
        PROOF.parent.mkdir(parents=True, exist_ok=True)
        target = PROOF.with_name("debt-api-observation.json") if args.observe else PROOF
        target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (
        scene.Refused,
        ValueError,
        KeyError,
        TypeError,
        OSError,
        StopIteration,
    ) as error:
        print(
            str(error)
            if isinstance(error, scene.Refused)
            else "Private state or response is invalid",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
