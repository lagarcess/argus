"""Prove recurring expectation to confirmed payment over real local HTTP.

Runs against a pristine three-identity allocation (default port base 59800):
real Auth, API and Postgres with synthetic market data and no provider keys.
Evidence carries check names, counts and synthetic dates only, never credentials.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
ZONE = "America/Santo_Domingo"
EVIDENCE = ROOT / "docs/reports/evidence/overnight-2026-10-05-recurring-plan"
ROOTS = ("/auth/login", "/financial-accounts", "/financial-activities", "/financial-plan")
NOT_FOUND = "financial_account_not_found"
TITLE_LIMIT = 100
ELIGIBLE = ("cash", "checking", "savings")


class Refused(Exception):
    """Public diagnostic that never carries credentials."""


def require(condition, message):
    if not condition:
        raise Refused(message)


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def add_months(anchor: date, months: int) -> date:
    index = anchor.year * 12 + anchor.month - 1 + months
    year, month = divmod(index, 12)
    return date(year, month + 1, min(anchor.day, monthrange(year, month + 1)[1]))


def next_cadence_date(movement_day: date, today: date) -> date:
    months = 1
    while add_months(movement_day, months) < today:
        months += 1
    return add_months(movement_day, months)


def expectation_from_movement(activity: dict, account: dict, today: date) -> dict:
    """The client-side derivation agreed with native; ExpectationCreate has no category."""
    body = {
        "kind": "income" if activity["kind"] == "income" else "bill",
        "title": (activity.get("note") or "Recurring").strip()[:TITLE_LIMIT],
        "currency": activity["currency"],
        "amount": activity["amount"],
        "schedule": {
            "cadence": "monthly",
            "start_date": next_cadence_date(
                datetime.fromisoformat(activity["occurred_at"].replace("Z", "+00:00"))
                .astimezone(ZoneInfo(ZONE))
                .date(),
                today,
            ).isoformat(),
        },
    }
    if account["type"] in ELIGIBLE and account["currency"] == activity["currency"]:
        body["account_id"] = account["id"]
    return body


def month_dates(today: date, until: date, days: tuple[int, ...]) -> list[str]:
    result = []
    index = today.year * 12 + today.month - 1
    while True:
        year, month = divmod(index, 12)
        month += 1
        if date(year, month, 1) > until:
            return result
        last = monthrange(year, month)[1]
        for day in sorted({min(d, last) for d in days}):
            due = date(year, month, day)
            if today <= due <= until:
                result.append(due.isoformat())
        index += 1


def fortnight_dates(today: date, until: date) -> list[str]:
    return [
        (today + timedelta(days=n)).isoformat()
        for n in range(0, (until - today).days + 1, 14)
    ]


class Checks:
    def __init__(self):
        self.rows = []
        self.name = None

    def begin(self, name):
        self.name = name
        self.rows.append({"name": name, "assertions": 0})

    def eq(self, actual, expected, label):
        self.rows[-1]["assertions"] += 1
        if actual != expected:
            raise Refused(f"{self.name}: {label}: got {actual!r}, expected {expected!r}")

    @property
    def total(self):
        return sum(row["assertions"] for row in self.rows)


def validate_path(path):
    require(
        path.startswith("/")
        and not any(value in path for value in ("..", "//", "%", "#"))
        and any(
            path == root or path.startswith(root + "/") or path.startswith(root + "?")
            for root in ROOTS
        ),
        "Refusing unexpected API path",
    )


class Client:
    def __init__(self, base):
        self.api_url = f"http://127.0.0.1:{base}/api/v1"
        path = ROOT / f"ios/.build/accounts-local-{base}/client.json"
        require(
            path.is_file() and not path.is_symlink() and path.stat().st_mode & 0o077 == 0,
            "Missing or unsafe local fixture; configure and seed the allocation first",
        )
        self.config = json.loads(path.read_bytes())
        require(
            self.config.get("apiURL") == self.api_url
            and self.config.get("supabaseURL") == f"http://127.0.0.1:{base + 1}",
            "Refusing endpoints outside the local allocation",
        )
        require(len(self.config.get("users", [])) == 3, "Seed exactly three identities")
        self.sessions = {}

    @staticmethod
    def raw(url, method, body=None, headers=None):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *_):
                return None

        request = urllib.request.Request(
            url, data=body, method=method, headers=headers or {}
        )
        try:
            with urllib.request.build_opener(NoRedirect).open(
                request, timeout=30
            ) as reply:
                return reply.status, json.load(reply)
        except urllib.error.HTTPError as error:
            try:
                return error.code, json.loads(error.read() or b"{}")
            except ValueError:
                return error.code, {}
        except (urllib.error.URLError, TimeoutError):
            raise Refused("Local HTTP interrupted") from None

    def login(self, actor):
        user = self.config["users"][actor]
        status, result = self.raw(
            self.api_url + "/auth/login",
            "POST",
            wire(
                {
                    "email": user["email"],
                    "password": user["password"],
                    "captcha_token": "XXXX.DUMMY.TOKEN.XXXX",
                }
            ),
            {"Content-Type": "application/json"},
        )
        require(
            status == 200 and result.get("user", {}).get("id") == user["id"],
            "Local registered authentication failed",
        )
        self.sessions[actor] = result["session"]["access_token"]

    def call(
        self, actor, method, path, body=None, key=None, expect=(200, 201), anonymous=False
    ):
        validate_path(path)
        headers = {"Content-Type": "application/json"}
        if not anonymous:
            if actor not in self.sessions:
                self.login(actor)
            headers["Authorization"] = "Bearer " + self.sessions[actor]
        if key:
            headers["Idempotency-Key"] = key
        status, result = self.raw(
            self.api_url + path, method, None if body is None else wire(body), headers
        )
        require(status in expect, f"{method} {path.split('?')[0]} returned HTTP {status}")
        return status, result


def stamp(moment: datetime) -> str:
    return moment.isoformat()


def expense(account, amount, when, note="Internet Claro", category="housing"):
    return {
        "kind": "expense",
        "account_id": account,
        "amount": amount,
        "occurred_at": stamp(when),
        "time_zone": ZONE,
        "note": note,
        "category_id": category,
    }


def record(c, actor, request, activity_id=None):
    root = "/financial-activities" + ("/" + activity_id if activity_id else "")
    _, preview = c.call(actor, "POST", root + "/preview", request, expect=(200,))
    require(preview.get("ready") is True, "Money preview requires review")
    reviewed = {**preview["reviewed_request"], "preview_token": preview["preview_token"]}
    _, receipt = c.call(
        actor, "PATCH" if activity_id else "POST", root, reviewed, key=str(uuid4())
    )
    return receipt["activity"]


def create_account(c, actor, kind, currency, amount, when, nickname):
    body = {"type": kind, "currency": currency, "amount": amount, "nickname": nickname}
    if when:
        body["as_of"] = stamp(when)
    return c.call(actor, "POST", "/financial-accounts", body, key=str(uuid4()))[1]


def select(c, actor, version, accounts):
    return c.call(
        actor,
        "PUT",
        "/financial-plan/selection",
        {"expected_version": version, "account_ids": accounts, "time_zone": ZONE},
        key=str(uuid4()),
    )[1]


def plan(c, actor, end=None, today=None):
    path = "/financial-plan"
    if end:
        path += f"?start_date={today.isoformat()}&end_date={end.isoformat()}"
    return c.call(actor, "GET", path, expect=(200,))[1]


def balance(c, actor, account):
    result = c.call(actor, "GET", "/financial-accounts/" + account, expect=(200,))[1]
    return result["balance"]["amount_minor"], result["version"]


def group(read, currency):
    return next(g for g in read["currencies"] if g["currency"] == currency)


def rows(read, expectation_id):
    return [r for r in read["occurrences"] if r["expectation_id"] == expectation_id]


def totals(read, currency):
    g = group(read, currency)
    return g["starting_minor"], g["expected_bills_minor"], g["ending_minor"]


def fulfillment(version, request):
    return {"expected_version": version, "activity": request}


def pristine(c):
    for actor in (0, 1, 2):
        read = plan(c, actor)
        require(
            read["accounts"] == []
            and read["expectations"] == []
            and read["selection"]["version"] == 0,
            "Identity already used; seed a fresh allocation",
        )


def journey(c, k, now):
    today = datetime.fromisoformat(plan(c, 0)["start_date"]).date()
    long_ago = now - timedelta(days=40)
    evidence = {"run_date": today.isoformat()}

    k.begin("movement becomes a prefilled expectation without touching the original")
    chk = create_account(c, 0, "checking", "DOP", "50000", long_ago, "Journey checking")
    sav = create_account(c, 0, "savings", "DOP", "2000", long_ago, "Journey savings")
    usd = create_account(c, 0, "checking", "USD", "100", long_ago, "Journey dollars")
    card = create_account(c, 0, "credit_card", "DOP", "200", long_ago, "Journey card")
    select(c, 0, 0, [chk["id"], usd["id"]])
    m0 = record(c, 0, expense(chk["id"], "1500", now - timedelta(days=12)))
    k.eq(
        (m0["revision"], m0["amount"], m0["category_id"]),
        (1, "1500.00", "housing"),
        "movement recorded",
    )
    before = balance(c, 0, chk["id"])
    k.eq(before[0], 4850000, "balance after movement")
    body = expectation_from_movement(m0, chk, today)
    k.eq(
        (
            body["kind"],
            body["title"],
            body["amount"],
            body["account_id"],
            body["schedule"]["cadence"],
        ),
        ("bill", "Internet Claro", "1500.00", chk["id"], "monthly"),
        "derived fields",
    )
    start = date.fromisoformat(body["schedule"]["start_date"])
    k.eq(
        today <= start <= today + timedelta(days=30),
        True,
        "first date inside Home window",
    )
    create_key = str(uuid4())
    _, first = c.call(0, "POST", "/financial-plan/expectations", body, key=create_key)
    exp = first["expectation"]
    k.eq(
        (exp["kind"], exp["title"], exp["amount_minor"], exp["version"], exp["archived"]),
        ("bill", "Internet Claro", 150000, 1, False),
        "expectation stored",
    )
    k.eq(
        exp["schedule"],
        {
            "cadence": "monthly",
            "start_date": start.isoformat(),
            "end_date": None,
            "month_days": [],
        },
        "schedule stored",
    )
    k.eq("category_id" in exp, False, "category is not carried (recorded limitation)")
    k.eq(first["replayed"], False, "first create is not a replay")
    _, resend = c.call(0, "POST", "/financial-plan/expectations", body, key=create_key)
    k.eq(
        (resend["replayed"], resend["expectation"]["id"]),
        (True, exp["id"]),
        "lost response resend returns same expectation",
    )
    k.eq(len(plan(c, 0)["expectations"]), 1, "interrupted create does not duplicate")
    _, original = c.call(
        0, "GET", "/financial-activities/" + m0["activity_id"], expect=(200,)
    )
    k.eq(
        (
            original["revision"],
            original["amount"],
            original["category_id"],
            original["note"],
        ),
        (1, "1500.00", "housing", "Internet Claro"),
        "original movement unchanged",
    )
    k.eq(
        balance(c, 0, chk["id"]),
        before,
        "creating an expectation never changes a balance",
    )

    k.begin("Default window is unaffected by a longer request")
    default = plan(c, 0)
    k.eq(
        (default["start_date"], default["end_date"]),
        (today.isoformat(), (today + timedelta(days=30)).isoformat()),
        "default window",
    )
    k.eq(
        [r["due_date"] for r in rows(default, exp["id"])],
        [start.isoformat()],
        "one occurrence in 30 days",
    )
    k.eq(totals(default, "DOP"), ("4850000", "150000", "4700000"), "default totals")
    long_end = today + timedelta(days=90)
    longer = plan(c, 0, long_end, today)
    expected_dates = [add_months(start, n).isoformat() for n in range(3)]
    k.eq(longer["end_date"], long_end.isoformat(), "Plan end date honoured")
    k.eq(
        [r["due_date"] for r in rows(longer, exp["id"])],
        expected_dates,
        "Plan sees three occurrences",
    )
    k.eq(totals(longer, "DOP"), ("4850000", "450000", "4400000"), "Plan totals")
    again = plan(c, 0)
    k.eq(again["end_date"], default["end_date"], "later default call keeps 30 days")
    k.eq(
        totals(again, "DOP"),
        totals(default, "DOP"),
        "default totals unchanged by Plan request",
    )
    explicit = plan(c, 0, today + timedelta(days=30), today)
    k.eq(
        (explicit["occurrences"], explicit["currencies"]),
        (default["occurrences"], default["currencies"]),
        "default equals explicit 30 days",
    )
    too_long = f"/financial-plan?start_date={today.isoformat()}&end_date={(today + timedelta(days=367)).isoformat()}"
    tomorrow = f"/financial-plan?start_date={(today + timedelta(days=1)).isoformat()}"
    for label, path in (
        ("horizon over 366 days", too_long),
        ("start after today", tomorrow),
    ):
        _, problem = c.call(0, "GET", path, expect=(422,))
        k.eq(problem["code"], "forecast_period_invalid", label + " refused")

    k.begin("currency separation")
    usd_bill = {"kind": "bill", "title": "Cloud", "currency": "USD", "amount": "25"}
    due_soon = (today + timedelta(days=5)).isoformat()
    refusals = [
        (usd_bill | {"account_id": chk["id"]}, "currency_mismatch"),
        (
            {**usd_bill, "currency": "DOP", "amount": "10", "account_id": usd["id"]},
            "currency_mismatch",
        ),
        (
            {**usd_bill, "currency": "DOP", "amount": "10", "account_id": card["id"]},
            "account_ineligible",
        ),
    ]
    for item, code in refusals:
        _, problem = c.call(
            0,
            "POST",
            "/financial-plan/expectations",
            item | {"schedule": {"cadence": "once", "start_date": due_soon}},
            key=str(uuid4()),
            expect=(422,),
        )
        k.eq(problem["code"], code, "refusal " + code)
    c.call(
        0,
        "POST",
        "/financial-plan/expectations",
        usd_bill
        | {
            "account_id": usd["id"],
            "schedule": {"cadence": "once", "start_date": due_soon},
        },
        key=str(uuid4()),
    )
    mixed = plan(c, 0)
    k.eq(
        [g["currency"] for g in mixed["currencies"]],
        ["DOP", "USD"],
        "one group per currency",
    )
    k.eq(totals(mixed, "USD"), ("10000", "2500", "7500"), "USD totals")
    k.eq(
        totals(mixed, "DOP"),
        ("4850000", "150000", "4700000"),
        "DOP totals untouched by USD bill",
    )

    k.begin("link an actual payment fulfils the occurrence once")
    first_occurrence, second_occurrence, third_occurrence = (
        r["id"] for r in rows(longer, exp["id"])
    )
    m1 = record(
        c,
        0,
        expense(chk["id"], "1500", now - timedelta(minutes=1), "Internet Claro paid"),
    )
    k.eq(
        totals(plan(c, 0), "DOP"),
        ("4700000", "150000", "4550000"),
        "payment recorded before linking is double counted until linked",
    )
    _, candidates = c.call(
        0,
        "GET",
        f"/financial-plan/occurrences/{first_occurrence}/candidates",
        expect=(200,),
    )
    k.eq(
        m1["activity_id"] in {i["activity_id"] for i in candidates["items"]},
        True,
        "payment is a candidate",
    )
    link_body = {
        "expected_version": 1,
        "activity_id": m1["activity_id"],
        "activity_revision": 1,
    }
    link_key = str(uuid4())
    _, linked = c.call(
        0,
        "POST",
        f"/financial-plan/occurrences/{first_occurrence}/link",
        link_body,
        key=link_key,
    )
    k.eq(
        (
            linked["replayed"],
            linked["occurrence"]["status"],
            linked["occurrence"]["activity_id"],
        ),
        (False, "fulfilled", m1["activity_id"]),
        "occurrence fulfilled",
    )
    k.eq(
        totals(plan(c, 0), "DOP"),
        ("4700000", "0", "4700000"),
        "bills fall by 150000 and ending rises by 150000 once",
    )
    _, replay = c.call(
        0,
        "POST",
        f"/financial-plan/occurrences/{first_occurrence}/link",
        link_body,
        key=link_key,
    )
    k.eq(
        (replay["replayed"], replay["occurrence"]),
        (True, linked["occurrence"]),
        "same key replays same result",
    )
    k.eq(
        totals(plan(c, 0), "DOP"),
        ("4700000", "0", "4700000"),
        "replay has no second effect",
    )
    _, conflict = c.call(
        0,
        "POST",
        f"/financial-plan/occurrences/{first_occurrence}/link",
        link_body | {"activity_id": m0["activity_id"]},
        key=link_key,
        expect=(409,),
    )
    k.eq(conflict["code"], "idempotency_conflict", "different body with same key refused")
    _, taken = c.call(
        0,
        "POST",
        f"/financial-plan/occurrences/{second_occurrence}/link",
        link_body,
        key=str(uuid4()),
        expect=(422,),
    )
    k.eq(
        taken["code"],
        "activity_already_linked",
        "one activity cannot fulfil a second occurrence",
    )
    k.eq(
        totals(plan(c, 0, long_end, today), "DOP"),
        ("4700000", "300000", "4400000"),
        "refused link changed nothing",
    )

    k.begin("record a new payment through fulfillment")
    request = expense(
        chk["id"], "1500", now - timedelta(minutes=1), "Internet Claro prepaid"
    )
    path = f"/financial-plan/occurrences/{second_occurrence}/fulfillment"
    _, wrong = c.call(
        0,
        "POST",
        path + "/preview",
        fulfillment(1, request | {"account_id": sav["id"]}),
        expect=(422,),
    )
    k.eq(wrong["code"], "fulfillment_mismatch", "payment must use the occurrence account")
    _, preview = c.call(
        0, "POST", path + "/preview", fulfillment(1, request), expect=(200,)
    )
    reviewed = fulfillment(
        1,
        {
            **preview["money"]["reviewed_request"],
            "preview_token": preview["money"]["preview_token"],
        },
    )
    fulfil_key = str(uuid4())
    _, paid = c.call(0, "POST", path, reviewed, key=fulfil_key)
    k.eq(
        (paid["replayed"], paid["occurrence"]["status"]),
        (False, "fulfilled"),
        "recorded payment fulfils occurrence",
    )
    after = plan(c, 0, long_end, today)
    k.eq(
        totals(after, "DOP"),
        ("4550000", "150000", "4400000"),
        "one occurrence removed from projected bills",
    )
    k.eq(
        [r["status"] for r in rows(after, exp["id"])],
        ["fulfilled", "fulfilled", "planned"],
        "occurrence statuses",
    )
    _, resent = c.call(0, "POST", path, reviewed, key=fulfil_key)
    k.eq(
        (resent["replayed"], resent["activity"]["activity_id"]),
        (True, paid["activity"]["activity_id"]),
        "lost response resend returns same payment",
    )
    k.eq(balance(c, 0, chk["id"])[0], 4550000, "resend recorded no second payment")
    _, clash = c.call(
        0,
        "POST",
        path,
        fulfillment(1, {**reviewed["activity"], "amount": "1600"}),
        key=fulfil_key,
        expect=(409,),
    )
    k.eq(clash["code"], "idempotency_conflict", "different body with same key refused")
    _, again_paid = c.call(0, "POST", path, reviewed, key=str(uuid4()), expect=(422,))
    k.eq(
        again_paid["code"],
        "occurrence_already_linked",
        "a new key cannot pay the same occurrence twice",
    )
    m2 = paid["activity"]

    k.begin("correcting the linked payment follows the stored contract")
    fix = expense(
        chk["id"],
        "1600",
        datetime.fromisoformat(m1["occurred_at"].replace("Z", "+00:00")),
        "Internet Claro paid",
    ) | {"expected_revision": 1, "reason": "Journey amount correction"}
    corrected = record(c, 0, fix, m1["activity_id"])
    read = plan(c, 0, long_end, today)
    first_row = rows(read, exp["id"])[0]
    k.eq(
        (corrected["revision"], first_row["status"], first_row["activity_revision"]),
        (2, "fulfilled", 2),
        "amount correction keeps the occurrence fulfilled",
    )
    k.eq(
        totals(read, "DOP"),
        ("4540000", "150000", "4390000"),
        "totals after amount correction",
    )
    move = expense(
        sav["id"],
        "1500",
        datetime.fromisoformat(m2["occurred_at"].replace("Z", "+00:00")),
        "Internet Claro prepaid",
    ) | {"expected_revision": 1, "reason": "Journey account correction"}
    record(c, 0, move, m2["activity_id"])
    read = plan(c, 0, long_end, today)
    second_row = rows(read, exp["id"])[1]
    k.eq(
        (second_row["status"], second_row["exclusion_reason"]),
        ("needs_review", "link_needs_review"),
        "account correction needs review",
    )
    k.eq(
        totals(read, "DOP"),
        ("4690000", "150000", "4540000"),
        "ambiguous occurrence is excluded from projection",
    )
    m3 = record(
        c,
        0,
        expense(
            chk["id"], "1500", now - timedelta(minutes=1), "Internet Claro replacement"
        ),
    )
    _, candidates = c.call(
        0,
        "GET",
        f"/financial-plan/occurrences/{second_occurrence}/candidates",
        expect=(200,),
    )
    ids = {i["activity_id"] for i in candidates["items"]}
    k.eq(
        (m3["activity_id"] in ids, m2["activity_id"] in ids),
        (True, False),
        "moved payment is no longer a candidate",
    )
    _, relinked = c.call(
        0,
        "POST",
        f"/financial-plan/occurrences/{second_occurrence}/link",
        {"expected_version": 1, "activity_id": m3["activity_id"], "activity_revision": 1},
        key=str(uuid4()),
    )
    k.eq(
        relinked["occurrence"]["status"],
        "fulfilled",
        "explicit relink restores fulfilled",
    )
    k.eq(
        totals(plan(c, 0, long_end, today), "DOP"),
        ("4540000", "150000", "4390000"),
        "totals after relink",
    )
    _, original = c.call(
        0, "GET", "/financial-activities/" + m0["activity_id"], expect=(200,)
    )
    k.eq(
        (original["revision"], original["amount"], original["category_id"]),
        (1, "1500.00", "housing"),
        "original movement still unchanged",
    )

    k.begin("authorization")
    foreign = [
        ("GET", f"/financial-plan/expectations/{exp['id']}", None),
        (
            "PATCH",
            f"/financial-plan/expectations/{exp['id']}",
            {"expected_version": 1, "title": "Taken"},
        ),
        ("GET", f"/financial-plan/occurrences/{first_occurrence}/candidates", None),
        (
            "POST",
            f"/financial-plan/occurrences/{first_occurrence}/link",
            {
                "expected_version": 1,
                "activity_id": m1["activity_id"],
                "activity_revision": 2,
            },
        ),
        (
            "POST",
            f"/financial-plan/occurrences/{third_occurrence}/fulfillment/preview",
            fulfillment(1, expense(chk["id"], "1500", now)),
        ),
        (
            "POST",
            f"/financial-plan/occurrences/{third_occurrence}/fulfillment",
            fulfillment(1, expense(chk["id"], "1500", now)),
        ),
        ("GET", f"/financial-activities/{m1['activity_id']}", None),
    ]
    snapshot = plan(c, 0, long_end, today)["occurrences"]
    for method, path, payload in foreign:
        _, problem = c.call(
            1,
            method,
            path,
            payload,
            key=str(uuid4()) if method != "GET" else None,
            expect=(404,),
        )
        k.eq(
            problem["code"],
            NOT_FOUND,
            f"user B {method} {path.split('/')[2]} is not found",
        )
    c.call(1, "GET", "/financial-plan", anonymous=True, expect=(401,))
    k.eq(
        plan(c, 0, long_end, today)["occurrences"],
        snapshot,
        "foreign attempts changed nothing",
    )

    k.begin("a due date never posts money")
    b_chk = create_account(
        c, 1, "checking", "DOP", "1000", long_ago, "Journey B checking"
    )
    select(c, 1, 0, [b_chk["id"]])
    for title, amount, days in (("Overdue bill", "200", -3), ("Due today", "100", 0)):
        c.call(
            1,
            "POST",
            "/financial-plan/expectations",
            {
                "kind": "bill",
                "title": title,
                "currency": "DOP",
                "amount": amount,
                "account_id": b_chk["id"],
                "schedule": {
                    "cadence": "once",
                    "start_date": (today + timedelta(days=days)).isoformat(),
                },
            },
            key=str(uuid4()),
        )
    b_read = plan(c, 1)
    k.eq(
        [(r["title"], r["status"], r["overdue"]) for r in b_read["occurrences"]],
        [("Overdue bill", "planned", True), ("Due today", "planned", False)],
        "overdue and due-today stay planned",
    )
    k.eq(
        totals(b_read, "DOP"),
        ("100000", "30000", "70000"),
        "bills are expected, not posted",
    )
    k.eq(
        (balance(c, 1, b_chk["id"])[0], b_read["home"]["recent_activity"]),
        (100000, []),
        "balance and activity untouched",
    )
    k.eq(
        {r["id"] for r in b_read["occurrences"]} & {r["id"] for r in snapshot},
        set(),
        "owners never see each other's occurrences",
    )

    k.begin("unknown balance is not counted as known")
    unknown = create_account(c, 0, "savings", "DOP", None, None, "Journey unknown")
    k.eq(unknown["balance"]["state"], "unknown", "account balance unknown")
    select(c, 0, 1, [chk["id"], usd["id"], unknown["id"]])
    c.call(
        0,
        "POST",
        "/financial-plan/expectations",
        {
            "kind": "bill",
            "title": "Water",
            "currency": "DOP",
            "amount": "300",
            "account_id": unknown["id"],
            "schedule": {
                "cadence": "once",
                "start_date": (today + timedelta(days=3)).isoformat(),
            },
        },
        key=str(uuid4()),
    )
    g = group(plan(c, 0), "DOP")
    k.eq(
        (
            g["unknown_account_ids"],
            g["known_starting_minor"],
            g["starting_minor"],
            g["ending_minor"],
        ),
        ([unknown["id"]], "4540000", None, None),
        "unknown account listed and excluded from known start",
    )
    k.eq(
        (
            g["expected_bills_minor"],
            g["first_shortfall_date"],
            g["points"][-1]["balance_minor"],
        ),
        ("30000", None, None),
        "no invented ending balance",
    )

    k.begin("empty plan invents no totals")
    empty = plan(c, 2)
    k.eq(
        (
            empty["has_expectations"],
            empty["expectations"],
            empty["occurrences"],
            empty["currencies"],
        ),
        (False, [], [], []),
        "unselected empty plan",
    )
    c_chk = create_account(c, 2, "checking", "DOP", "800", long_ago, "Journey C checking")
    select(c, 2, 0, [c_chk["id"]])
    empty = plan(c, 2)
    g = group(empty, "DOP")
    k.eq(
        (
            empty["has_expectations"],
            g["expected_bills_minor"],
            g["expected_income_minor"],
            g["starting_minor"],
            g["ending_minor"],
            len(g["points"]),
        ),
        (False, "0", "0", "80000", "80000", 1),
        "selected empty plan",
    )

    k.begin("cadence dates")
    until = today + timedelta(days=366)
    specs = {
        "month_end": {
            "cadence": "monthly",
            "start_date": today.isoformat(),
            "month_days": [31],
        },
        "twice_monthly": {
            "cadence": "twice_monthly",
            "start_date": today.isoformat(),
            "month_days": [15, 31],
        },
        "every_two_weeks": {
            "cadence": "every_two_weeks",
            "start_date": today.isoformat(),
        },
    }
    wanted = {
        "month_end": month_dates(today, until, (31,)),
        "twice_monthly": month_dates(today, until, (15, 31)),
        "every_two_weeks": fortnight_dates(today, until),
    }
    ids = {}
    for name, schedule in specs.items():
        _, made = c.call(
            2,
            "POST",
            "/financial-plan/expectations",
            {
                "kind": "bill",
                "title": name,
                "currency": "DOP",
                "amount": "10",
                "account_id": c_chk["id"],
                "schedule": schedule,
            },
            key=str(uuid4()),
        )
        ids[name] = made["expectation"]["id"]
    read = plan(c, 2, until, today)
    for name in specs:
        got = [r["due_date"] for r in rows(read, ids[name])]
        k.eq(got, wanted[name], name + " dates")
        evidence[name + "_dates"] = got
    month_end = wanted["month_end"]
    k.eq(
        {d[5:7] for d in month_end} >= {"02", "04", "11"},
        True,
        "window covers February, April and November",
    )
    k.eq(
        all(
            date.fromisoformat(d)
            == date(int(d[:4]), int(d[5:7]), monthrange(int(d[:4]), int(d[5:7]))[1])
            for d in month_end
        ),
        True,
        "every month-end occurrence keeps the 31st anchor clamped",
    )
    count = sum(len(v) for v in wanted.values())
    k.eq(
        (read["has_expectations"], group(read, "DOP")["expected_bills_minor"]),
        (True, str(1000 * count)),
        "per-occurrence totals add up",
    )
    evidence["identities"] = 3
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port-base", type=int, default=59800)
    parser.add_argument("--write-evidence", action="store_true")
    args = parser.parse_args()
    require(
        58400 <= args.port_base <= 59900,
        "Refusing a port base outside the owned local range",
    )
    c = Client(args.port_base)
    pristine(c)
    checks = Checks()
    evidence = journey(c, checks, datetime.now(ZoneInfo(ZONE)))
    proof = {
        "source_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "runtime": f"real isolated Auth{args.port_base + 1}/API{args.port_base}/Postgres{args.port_base + 2}, synthetic market data, no provider keys",
        "checks": checks.rows,
        "total_assertions": checks.total,
        **evidence,
    }
    if args.write_evidence:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        (EVIDENCE / "journey-proof.json").write_text(
            json.dumps(proof, indent=2, sort_keys=True) + "\n"
        )
    print(f"{len(checks.rows)} checks, {checks.total} assertions passed")


if __name__ == "__main__":
    try:
        main()
    except Refused as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from None
