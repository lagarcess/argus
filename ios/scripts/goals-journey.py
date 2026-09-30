"""Run/resume a retained savings-goal HTTP journey on owned local allocation 59100.

Every write is journaled before HTTP. Readback checks the initial retained scene;
--observe labels later human edits. Credentials and receipts stay in ignored .build.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import secrets
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "ios/.build/accounts-local-59100"
API = "http://127.0.0.1:59100/api/v1"
PROXY = "http://127.0.0.1:59112"
AUTH = "http://127.0.0.1:59101"
ZONE = "America/Santo_Domingo"
PROOF = ROOT / "docs/reports/evidence/connected-savings-goals/goal-api-proof.json"
GOALS = "/financial-plan/goals"
ROOTS = (
    "/financial-accounts",
    "/financial-activities",
    "/financial-plan",
    "/financial-home",
    "/financial-search",
)


class Refused(Exception):
    """Safe public diagnostic without credentials or server text."""


def require(condition, message):
    if not condition:
        raise Refused(message)


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def save_private(path, value):
    require(
        not path.is_symlink() and not path.parent.is_symlink(),
        "Refusing symlinked private state",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(wire(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def read_private(path):
    require(
        path.is_file() and not path.is_symlink() and path.stat().st_mode & 0o077 == 0,
        "Missing or unsafe private local file",
    )
    return json.loads(path.read_bytes())


def validate_config(config):
    require(
        config.get("apiURL") == API and config.get("supabaseURL") == AUTH,
        "Refusing endpoints outside local allocation 59100",
    )
    require(
        len(config.get("users", [])) == 2 and config.get("publicAnonKey"),
        "Reuse two seeded local users",
    )
    for user in config["users"]:
        require(
            user.get("email") and user.get("password"), "Local credentials are incomplete"
        )


def validate_path(path):
    parsed = urlsplit(path)
    require(
        not parsed.scheme
        and not parsed.netloc
        and not parsed.fragment
        and ".." not in parsed.path
        and "//" not in parsed.path
        and "%" not in parsed.path
        and any(
            parsed.path == root or parsed.path.startswith(root + "/") for root in ROOTS
        ),
        "Refusing unrelated or unexpected API route",
    )


class Journal:
    def __init__(self, path, create=False):
        self.path = path
        if path.exists():
            self.state = read_private(path)
            require(self.state.get("version") == 1, "Unsupported private journal version")
        else:
            require(create, "Run the journey before readback")
            now = datetime.now(ZoneInfo(ZONE)) - timedelta(minutes=1)
            self.state = {
                "version": 1,
                "suffix": secrets.token_hex(4),
                "now": now.isoformat(),
                "operations": {},
                "checks": {},
                "sessions": {},
            }
            self.save()

    def save(self):
        save_private(self.path, self.state)

    def command(
        self, client, name, method, path, build, statuses=(200, 201), owner=0, key=None
    ):
        validate_path(path)
        operations = self.state["operations"]
        if name not in operations:
            require(
                all("result" in row for row in operations.values()),
                "Recover pending command before another write",
            )
            operation = {
                "method": method,
                "path": path,
                "body": wire(build()).decode(),
                "key": key or str(uuid4()),
                "owner": owner,
                "statuses": list(statuses),
            }
            operations[name] = operation
            self.save()
        operation = operations[name]
        if "result" in operation:
            return operation["result"]
        self.save()
        status, result = client.api(
            operation["owner"],
            operation["method"],
            operation["path"],
            operation["body"].encode(),
            operation["key"],
        )
        require(status in operation["statuses"], f"Command {name} returned HTTP {status}")
        operation["status"] = status
        operation["result"] = result
        self.save()
        return result


class Client:
    def __init__(self, config, journal, response_loss=False):
        validate_config(config)
        self.config, self.journal = config, journal
        self.sessions = journal.state["sessions"]
        self.origin = PROXY + "/api/v1" if response_loss else API
        self.response_loss = response_loss

    @staticmethod
    def raw(url, method, body=None, headers=None):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, request, fp, code, message, headers, newurl):
                return None

        request = urllib.request.Request(
            url, data=body, method=method, headers=headers or {}
        )
        try:
            with urllib.request.build_opener(NoRedirect).open(
                request, timeout=30
            ) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            raise Refused("Local HTTP failed; rerun to replay pending command") from None

    def authenticate(self, owner, refresh=False):
        session = self.sessions.get(str(owner))
        if refresh and session and session.get("refresh_token"):
            status, result = self.raw(
                AUTH + "/auth/v1/token?grant_type=refresh_token",
                "POST",
                wire({"refresh_token": session["refresh_token"]}),
                {
                    "Content-Type": "application/json",
                    "apikey": self.config["publicAnonKey"],
                },
            )
            if status == 200 and result.get("access_token"):
                self.sessions[str(owner)] = result
                self.journal.save()
                return
        user = self.config["users"][owner]
        status, result = self.raw(
            API + "/auth/login",
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
            status == 200 and result.get("session", {}).get("access_token"),
            "Local authentication failed",
        )
        self.sessions[str(owner)] = result["session"]
        self.journal.save()

    def api(self, owner, method, path, body=None, key=None):
        validate_path(path)
        require(owner in (0, 1), "Unexpected local owner")
        if str(owner) not in self.sessions:
            self.authenticate(owner)

        def send():
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self.sessions[str(owner)]["access_token"],
            }
            if key:
                headers["Idempotency-Key"] = key
            return self.raw(self.origin + path, method, body, headers)

        fault = self.journal.state.get("fault")
        drop = (
            self.response_loss
            and method == "POST"
            and path == GOALS
            and not self.journal.state.get("response_loss_verified")
        )
        if drop and not fault:
            status, before = self.raw(PROXY + "/__fault", "POST")
            require(
                status == 200 and before.get("armed") is True,
                "Response-loss proxy did not arm",
            )
            fault = {"before_dropped": before["dropped"], "key": key}
            self.journal.state["fault"] = fault
            self.journal.save()
        try:
            status, result = send()
        except Refused:
            if not drop:
                raise
            status, result = send()
        if status == 401:
            self.authenticate(owner, refresh=True)
            status, result = send()
        if drop:
            _, after = self.raw(PROXY + "/__fault", "GET")
            require(
                fault["key"] == key
                and after["dropped"] == fault["before_dropped"] + 1
                and result.get("replayed") is True,
                "Committed response-loss retry was not proved",
            )
            self.journal.state["response_loss_verified"] = True
            self.journal.save()
        return status, result


def get(client, path, owner=0):
    status, result = client.api(owner, "GET", path)
    require(status == 200, f"Read returned HTTP {status}")
    return result


def goal_id(journal, label="a"):
    return journal.state["operations"]["goal_" + label]["result"]["goal"]["goal"]["id"]


def account_ids(journal):
    return {
        label: journal.state["operations"]["account_" + label]["result"]["id"]
        for label in ("savings", "bank", "usd", "unknown")
    }


def goal(client, identity):
    return get(client, GOALS + "/" + identity)


def versions(client, ids):
    return {
        identity: get(client, "/financial-accounts/" + identity)["version"]
        for identity in ids
    }


def plan(client, journal):
    day = datetime.now(ZoneInfo(ZONE)).date()
    return get(
        client,
        "/financial-plan?"
        + urlencode(
            {
                "start_date": day.isoformat(),
                "end_date": (day + timedelta(days=30)).isoformat(),
            }
        ),
    )


def money(journal, client, name, build, identity=None):
    root = "/financial-activities" + ("/" + identity if identity else "")

    def reviewed():
        status, preview = client.api(0, "POST", root + "/preview", wire(build()))
        require(
            status == 200 and preview.get("ready") is True,
            "Money preview requires review",
        )
        return {**preview["reviewed_request"], "preview_token": preview["preview_token"]}

    return journal.command(client, name, "PATCH" if identity else "POST", root, reviewed)


def transfer(journal, source, destination, amount, occurred_at=None):
    return {
        "kind": "transfer",
        "source_account_id": source,
        "destination_account_id": destination,
        "amount": amount,
        "occurred_at": occurred_at or journal.state["now"],
        "time_zone": ZONE,
        "note": "Goal fixture " + journal.state["suffix"],
        "coverage": [],
        "expected_versions": {},
    }


def allocate(journal, client, name, assignments, statuses=(200, 201)):
    def body():
        changes = [
            {
                "goal_id": identity,
                "expected_version": goal(client, identity)["goal"]["version"],
                "account_id": account,
                "amount": amount,
                "release_claim_ids": [],
            }
            for identity, account, amount in assignments
        ]
        return {
            "changes": changes,
            "expected_account_versions": versions(
                client, list(dict.fromkeys(row[1] for row in assignments))
            ),
        }

    return journal.command(
        client, name, "PUT", GOALS + "/allocations", body, statuses=statuses
    )


def replay(journal, client, name, field):
    operation = journal.state["operations"][name]
    status, result = client.api(
        operation["owner"],
        operation["method"],
        operation["path"],
        operation["body"].encode(),
        operation["key"],
    )
    require(
        status in (200, 201)
        and result.get("replayed") is True
        and result[field] == operation["result"][field],
        "Exact retry changed accepted record",
    )


def assert_progress(result, assigned, supported, remaining, state="active"):
    require(
        (
            result["assigned_minor"],
            result["supported_minor"],
            result["remaining_minor"],
            result["state"],
        )
        == (
            str(assigned),
            None if supported is None else str(supported),
            None if remaining is None else str(remaining),
            state,
        ),
        "Goal differs from independent literal expected progress",
    )


def check(
    journal,
    client,
    name,
    a,
    b,
    savings,
    bank,
    available,
    shortfall=0,
    *,
    verify_owner_totals=True,
):
    if name in journal.state["checks"]:
        return
    identities = (goal_id(journal), goal_id(journal, "b"))
    details = [goal(client, identity) for identity in identities]
    ids = account_ids(journal)
    for detail, expected in zip(details, (a, b), strict=True):
        assert_progress(detail, *expected)
        pool = next(row for row in detail["pools"] if row["account_id"] == ids["savings"])
        require(
            pool["backing_minor"] == str(savings)
            and pool["available_minor"] == str(available)
            and pool["shortfall_minor"] == str(shortfall),
            "Shared pool differs from literal backing",
        )
    for label, amount in (("savings", savings), ("bank", bank), ("usd", 10000)):
        account = get(client, "/financial-accounts/" + ids[label])
        require(
            account["balance"]["amount_minor"] == amount,
            "Allocation or transfer changed money incorrectly",
        )
    unknown = get(client, "/financial-accounts/" + ids["unknown"])
    require(
        unknown["balance"]["state"] == "unknown"
        and unknown["balance"]["amount_minor"] is None,
        "Unknown position became funded",
    )
    snapshot = plan(client, journal)
    home = get(client, "/financial-home")
    for collection in (snapshot["goals"], snapshot["home"]["goals"], home["goals"]):
        for detail in details:
            nested = next(
                row for row in collection if row["goal"]["id"] == detail["goal"]["id"]
            )
            require(
                all(
                    nested[key] == detail[key]
                    for key in (
                        "goal",
                        "assigned_minor",
                        "supported_minor",
                        "independently_backed_minor",
                        "remaining_minor",
                        "state",
                        "contributions",
                    )
                ),
                "Plan/Home/detail goal projections disagree",
            )
    if verify_owner_totals:
        dop = next(
            row for row in snapshot["home"]["currencies"] if row["currency"] == "DOP"
        )
        require(
            int(dop["net_worth_minor"]) == 200000 and int(dop["net_spending_minor"]) == 0,
            "Internal transfers changed combined recorded position or spending",
        )
    forecast = next(row for row in snapshot["currencies"] if row["currency"] == "DOP")
    require(
        forecast["known_starting_minor"] == "200000"
        and forecast["ending_minor"] == "200000"
        and forecast["transfer_effect_minor"] == "0",
        "Selected two-leg cash forecast is incorrect",
    )
    journal.state["checks"][name] = {
        "a_assigned_minor": a[0],
        "a_supported_minor": a[1],
        "b_assigned_minor": b[0],
        "b_supported_minor": b[1],
        "savings_minor": savings,
        "bank_minor": bank,
        "available_minor": available,
        "shortfall_minor": shortfall,
    }
    journal.save()


def run(journal, client):
    now = datetime.fromisoformat(journal.state["now"])
    today = now.date()
    for label, kind, currency, amount in (
        ("savings", "savings", "DOP", "800"),
        ("bank", "checking", "DOP", "1200"),
        ("usd", "checking", "USD", "100"),
        ("unknown", "cash", "DOP", None),
    ):
        body = {
            "type": kind,
            "currency": currency,
            "nickname": "Goal " + label + " " + journal.state["suffix"],
            "as_of": (now - timedelta(days=4)).isoformat(),
            "time_zone": ZONE,
        }
        if amount is not None:
            body["amount"] = amount
        journal.command(
            client,
            "account_" + label,
            "POST",
            "/financial-accounts",
            lambda body=body: body,
        )
    ids = account_ids(journal)
    historical = money(
        journal,
        client,
        "historical",
        lambda: transfer(
            journal,
            ids["bank"],
            ids["savings"],
            "200",
            (now - timedelta(days=3)).isoformat(),
        ),
    )
    historical_id = historical["activity"]["activity_id"]
    journal.command(
        client,
        "selection",
        "PUT",
        "/financial-plan/selection",
        lambda: {
            "expected_version": get(client, "/financial-plan")["selection"]["version"],
            "account_ids": [ids["bank"], ids["savings"]],
            "time_zone": ZONE,
        },
    )
    for label, target in (("a", "1000"), ("b", "500")):
        journal.command(
            client,
            "goal_" + label,
            "POST",
            GOALS,
            lambda label=label, target=target: {
                "name": "Savings goal " + label + " " + journal.state["suffix"],
                "currency": "DOP",
                "target": target,
                "destination_account_id": ids["savings"],
                **(
                    {
                        "contribution_plan": {
                            "source_account_id": ids["bank"],
                            "amount": "100",
                            "schedule": {
                                "cadence": "once",
                                "start_date": today.isoformat(),
                            },
                        }
                    }
                    if label == "a"
                    else {}
                ),
            },
        )
    a, b = goal_id(journal), goal_id(journal, "b")
    replay(journal, client, "goal_a", "goal")
    allocate(
        journal,
        client,
        "assign",
        [(a, ids["savings"], "600"), (b, ids["savings"], "300")],
    )
    check(
        journal,
        client,
        "allocated",
        (60000, 60000, 40000),
        (30000, 30000, 20000),
        100000,
        100000,
        10000,
    )
    if "included" not in journal.state["operations"]:
        candidates = get(client, GOALS + "/" + a + "/contributions/candidates")
        require(
            any(row["activity_id"] == historical_id for row in candidates["items"]),
            "Original missing from candidates",
        )
    journal.command(
        client,
        "included",
        "POST",
        GOALS + "/" + a + "/contributions/link",
        lambda: {
            "expected_version": goal(client, a)["goal"]["version"],
            "activity_id": historical_id,
            "activity_revision": get(client, "/financial-activities/" + historical_id)[
                "revision"
            ],
            "treatment": "included",
            "expected_account_versions": versions(client, [ids["bank"], ids["savings"]]),
        },
    )
    check(
        journal,
        client,
        "included",
        (60000, 60000, 40000),
        (30000, 30000, 20000),
        100000,
        100000,
        10000,
    )
    if "original150" not in journal.state["operations"]:
        detail = goal(client, a)
        require(
            detail["goal"]["allocations"]
            == [{"account_id": ids["savings"], "unlinked_minor": 40000}]
            and detail["contributions"][0]["current_personal_minor"] == "20000",
            "Included link hid old credit",
        )
    for name, amount, expected, savings, bank in (
        ("original150", "150", (55000, 55000, 45000), 95000, 105000),
        ("original250", "250", (65000, 65000, 35000), 105000, 95000),
    ):

        def correction(amount=amount):
            current = get(client, "/financial-activities/" + historical_id)
            return {
                **transfer(
                    journal,
                    ids["bank"],
                    ids["savings"],
                    amount,
                    (now - timedelta(days=3)).isoformat(),
                ),
                "expected_revision": current["revision"],
                "reason": "Correct original contribution",
            }

        money(journal, client, name, correction, historical_id)
        check(
            journal, client, name, expected, (30000, 30000, 20000), savings, bank, 10000
        )
    allocate(journal, client, "overclaim", [(a, ids["savings"], "800")], statuses=(422,))
    allocate(journal, client, "wrong_currency", [(a, ids["usd"], "1")], statuses=(422,))
    allocate(
        journal, client, "unknown_funding", [(a, ids["unknown"], "1")], statuses=(422,)
    )
    check(
        journal,
        client,
        "rejected_claims",
        (65000, 65000, 35000),
        (30000, 30000, 20000),
        105000,
        95000,
        10000,
    )

    def contribution():
        current = goal(client, a)
        occurrence = next(
            row
            for row in plan(client, journal)["occurrences"]
            if row.get("goal_id") == a and row["due_date"] == today.isoformat()
        )
        require(
            occurrence["status"] == "planned" and current["planned_minor"] == "10000",
            "Plan became actual",
        )
        body = {
            "expected_version": current["goal"]["version"],
            "occurrence_id": occurrence["id"],
            "activity": transfer(journal, ids["bank"], ids["savings"], "100"),
        }
        status, preview = client.api(
            0, "POST", GOALS + "/" + a + "/contributions/preview", wire(body)
        )
        require(
            status == 200 and preview["money"]["ready"],
            "Goal money preview requires review",
        )
        return {
            **body,
            "activity": {
                **preview["money"]["reviewed_request"],
                "preview_token": preview["money"]["preview_token"],
            },
        }

    actual = journal.command(
        client, "contribution", "POST", GOALS + "/" + a + "/contributions", contribution
    )
    replay(journal, client, "contribution", "activity")
    activity_id = actual["activity"]["activity_id"]
    check(
        journal,
        client,
        "new_contribution",
        (75000, 75000, 25000),
        (30000, 30000, 20000),
        115000,
        85000,
        10000,
    )
    money(
        journal,
        client,
        "contribution80",
        lambda: {
            **transfer(journal, ids["bank"], ids["savings"], "80"),
            "expected_revision": get(client, "/financial-activities/" + activity_id)[
                "revision"
            ],
            "reason": "Correct contributed amount",
        },
        activity_id,
    )
    check(
        journal,
        client,
        "contribution_corrected",
        (73000, 73000, 27000),
        (30000, 30000, 20000),
        113000,
        87000,
        10000,
    )
    if "withdraw700" not in journal.state["operations"]:
        require(
            goal(client, a)["planned_minor"] == "0",
            "Fulfilled occurrence still forecasts payment",
        )
        occurrence_id = json.loads(journal.state["operations"]["contribution"]["body"])[
            "occurrence_id"
        ]
        occurrence = next(
            row
            for row in plan(client, journal)["occurrences"]
            if row["id"] == occurrence_id
        )
        require(
            occurrence["status"] == "fulfilled"
            and occurrence["activity_id"] == activity_id,
            "Correction reopened or duplicated fulfilled occurrence",
        )
    money(
        journal,
        client,
        "withdraw700",
        lambda: transfer(journal, ids["savings"], ids["bank"], "700"),
    )
    check(
        journal,
        client,
        "shared_shortfall",
        (73000, None, None, "needs_review"),
        (30000, None, None, "needs_review"),
        43000,
        157000,
        0,
        60000,
    )
    allocate(
        journal,
        client,
        "resolve",
        [(a, ids["savings"], "400"), (b, ids["savings"], "30")],
    )
    check(
        journal,
        client,
        "resolved",
        (40000, 40000, 60000),
        (3000, 3000, 47000),
        43000,
        157000,
        0,
    )
    journal.command(
        client,
        "archive",
        "PATCH",
        GOALS + "/" + a,
        lambda: {
            "expected_version": goal(client, a)["goal"]["version"],
            "archived": True,
        },
    )
    if "archive_withdraw20" not in journal.state["operations"]:
        archived = goal(client, a)
        require(
            archived["goal"]["archived"] is True
            and archived["assigned_minor"] == "40000"
            and len(archived["contributions"]) == 2
            and archived["planned_minor"] == "0",
            "Archive discarded claims or kept pending schedule",
        )
    money(
        journal,
        client,
        "archive_withdraw20",
        lambda: transfer(journal, ids["savings"], ids["bank"], "20"),
    )
    if "restore" not in journal.state["operations"]:
        archived = goal(client, a)
        other = goal(client, b)
        assert_progress(archived, 40000, None, None, "needs_review")
        assert_progress(other, 3000, None, None, "needs_review")
        require(archived["goal"]["archived"] is True, "Withdrawal changed goal lifecycle")
    journal.command(
        client,
        "restore",
        "PATCH",
        GOALS + "/" + a,
        lambda: {
            "expected_version": goal(client, a)["goal"]["version"],
            "archived": False,
        },
    )
    replay(journal, client, "restore", "goal")
    check(
        journal,
        client,
        "restored_needs_review",
        (40000, None, None, "needs_review"),
        (3000, None, None, "needs_review"),
        41000,
        159000,
        0,
        2000,
    )
    allocate(journal, client, "resolve_restored", [(b, ids["savings"], "10")])
    journal.command(
        client,
        "future_plan",
        "PATCH",
        GOALS + "/" + a,
        lambda: {
            "expected_version": goal(client, a)["goal"]["version"],
            "contribution_plan": {
                "source_account_id": ids["bank"],
                "amount": "100",
                "schedule": {
                    "cadence": "once",
                    "start_date": (today + timedelta(days=1)).isoformat(),
                },
            },
        },
    )
    journal.command(
        client,
        "stale_goal",
        "PATCH",
        GOALS + "/" + a,
        lambda: {"expected_version": 1, "target": "1001"},
        statuses=(409,),
    )
    journal.command(
        client,
        "other_owner",
        "PATCH",
        GOALS + "/" + a,
        lambda: {"expected_version": 1, "target": "1002"},
        statuses=(404,),
        owner=1,
    )
    original = journal.state["operations"]["goal_a"]
    journal.command(
        client,
        "changed_idempotency",
        "POST",
        GOALS,
        lambda: {**json.loads(original["body"]), "target": "1003"},
        statuses=(409,),
        key=original["key"],
    )
    check(
        journal,
        client,
        "retained",
        (40000, 40000, 60000),
        (1000, 1000, 49000),
        41000,
        159000,
        0,
    )
    journal.state["complete"] = True
    journal.save()


def readback(journal, client, observe=False):
    require(
        journal.state.get("complete"), "Complete the resumable journey before readback"
    )
    a, b = goal_id(journal), goal_id(journal, "b")
    main, second = goal(client, a), goal(client, b)
    status, _ = client.api(1, "GET", GOALS + "/" + a)
    require(status == 404, "Other owner read retained goal")
    search_path = "/financial-search?" + urlencode(
        {"q": journal.state["suffix"], "kind": "goal"}
    )
    hits = get(client, search_path)["items"]
    require(
        {row["goal"]["goal"]["id"] for row in hits} == {a, b},
        "Search lost canonical goal detail",
    )
    require(
        get(client, search_path, owner=1)["items"] == [],
        "Goal Search leaked another owner's records",
    )
    activity_hits = get(
        client,
        "/financial-search?"
        + urlencode({"q": journal.state["suffix"], "kind": "activity", "limit": 50}),
    )["items"]
    activity_ids = {
        journal.state["operations"][name]["result"]["activity"]["activity_id"]
        for name in ("historical", "contribution", "withdraw700", "archive_withdraw20")
    }
    require(
        {row["activity"]["activity_id"] for row in activity_hits} == activity_ids,
        "Second activity ledger found",
    )
    if not observe:
        assert_progress(main, 40000, 40000, 60000)
        assert_progress(second, 1000, 1000, 49000)
        require(
            main["goal"]["target_minor"] == 100000
            and main["goal"]["archived"] is False
            and main["planned_minor"] == "10000",
            "Retained definition or planned amount changed",
        )
        expected_links = {
            journal.state["operations"][name]["result"]["activity"]["activity_id"]
            for name in ("historical", "contribution")
        }
        require(
            {row["activity_id"] for row in main["contributions"]} == expected_links,
            "Original detail identities changed",
        )
        for row in main["contributions"]:
            original = get(client, "/financial-activities/" + row["activity_id"])
            require(
                row["activity"] == original
                and row["activity_revision"] == original["revision"],
                "Stale original detail",
            )
        journal.state["checks"].pop("readback", None)
        check(
            journal,
            client,
            "readback",
            (40000, 40000, 60000),
            (1000, 1000, 49000),
            41000,
            159000,
            0,
            verify_owner_totals=False,
        )
    return {
        "journey": "connected_savings_goals_real_http",
        "mode": "interactive_observation" if observe else "initial_retained_scene",
        "local_allocation": 59100,
        "scenario_checks": journal.state["checks"],
        "canonical_activity_count": 4,
        "owner_isolation": True,
        "search_goal_identity": True,
        "main_supported_minor": main["supported_minor"],
        "main_target_minor": main["goal"]["target_minor"],
        "planned_minor": main["planned_minor"],
        "original_contribution_detail": not observe,
        "committed_response_loss": journal.state.get("response_loss_verified", False),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "readback"))
    parser.add_argument(
        "--response-loss",
        action="store_true",
        help="Use captain's 59112 proxy to drop one accepted goal response",
    )
    parser.add_argument(
        "--observe",
        action="store_true",
        help="Label human edits without asserting original retained amounts",
    )
    args = parser.parse_args()
    require(not args.observe or args.action == "readback", "Observe requires readback")
    config = read_private(WORK / "client.json")
    validate_config(config)
    require(not WORK.is_symlink(), "Refusing symlinked fixture directory")
    fd = os.open(
        WORK / "goals-journey.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(fd, "w") as lock:
        os.fchmod(lock.fileno(), 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Refused("Another journey owns the private journal") from None
        journal = Journal(
            WORK / "goals-journey-private.json", create=args.action == "run"
        )
        client = Client(config, journal, response_loss=args.response_loss)
        if args.action == "run" and not journal.state.get("complete"):
            run(journal, client)
        proof = readback(journal, client, args.observe)
        if not args.observe:
            PROOF.parent.mkdir(parents=True, exist_ok=True)
            PROOF.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
        print(json.dumps(proof, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (Refused, ValueError, KeyError, TypeError, OSError, StopIteration) as error:
        print(
            str(error)
            if isinstance(error, Refused)
            else "Private journal or API response is invalid",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
