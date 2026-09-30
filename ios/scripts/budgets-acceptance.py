"""Prepare and verify the initial replay-safe synthetic personal-money scene.

Usage: python ios/scripts/budgets-acceptance.py setup|readback
The private journal lives beside the allocation-59000 client fixture.
Readback checks the initial scene before interactive budget demo edits.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "ios/.build/accounts-local-59000"
CLIENT = WORK / "client.json"
STATE = WORK / "budgets-acceptance-private.json"
API = "http://127.0.0.1:59000/api/v1"
AUTH = "http://127.0.0.1:59001"
ZONE = "America/Santo_Domingo"
OPENED = "2026-09-01T09:00:00-04:00"
OCCURRED = "2026-09-10T12:00:00-04:00"

# Expected values are independent of the server's money or future budget reducer.
ACCOUNTS = (
    ("checking", "checking", "DOP", "1000.00", 82300),
    ("cash", "cash", "DOP", "100.00", 14000),
    ("card", "credit_card", "DOP", "0.00", 0),
    ("unknown", "checking", "DOP", None, None),
    ("usd", "checking", "USD", "100.00", 5000),
)
ACTIVITIES = (
    ("groceries_checking", "expense", "100.00", "DOP", "groceries", ("checking",), (-10000,)),
    ("groceries_card", "expense", "20.00", "DOP", "groceries", ("card",), (-2000,)),
    ("transport", "expense", "10.00", "DOP", "transport", ("checking",), (-1000,)),
    ("uncategorized", "expense", "7.00", "DOP", None, ("checking",), (-700,)),
    ("usd_groceries", "expense", "50.00", "USD", "groceries", ("usd",), (-5000,)),
    ("transfer", "transfer", "40.00", "DOP", None, ("checking", "cash"), (-4000, 4000)),
    ("card_payment", "card_payment", "20.00", "DOP", None, ("checking", "card"), (-2000, 2000)),
    ("unknown_groceries", "expense", "3.00", "DOP", "groceries", ("unknown",), (-300,)),
)


class Refused(Exception):
    """Safe public diagnostic, with no response body or identity."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Refused(message)


def load_client() -> dict:
    require(CLIENT.is_file() and not CLIENT.is_symlink(), "Missing local client fixture")
    config = json.loads(CLIENT.read_text())
    require(config.get("apiURL") == API and config.get("supabaseURL") == AUTH,
            "Refusing non-allocation-59000 endpoints")
    require(len(config.get("users", [])) >= 2 and config.get("publicAnonKey"),
            "Local client fixture is incomplete")
    return config


def save_state(state: dict) -> None:
    require(not STATE.is_symlink(), "Refusing symlinked private state")
    WORK.mkdir(parents=True, exist_ok=True)
    path = STATE.with_name(STATE.name + ".tmp")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as out:
            json.dump(state, out, sort_keys=True, separators=(",", ":"))
            out.flush()
            os.fsync(out.fileno())
        os.replace(path, STATE)
        os.chmod(STATE, 0o600)
        directory = os.open(WORK, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        path.unlink(missing_ok=True)


def load_state(*, create: bool) -> dict:
    if not STATE.exists():
        require(create, "Run setup before readback")
        state = {"version": 1, "suffix": secrets.token_hex(4), "accounts": {},
                 "activities": {}, "pending": None, "replay_proof": {}}
        save_state(state)
        return state
    require(not STATE.is_symlink() and STATE.stat().st_mode & 0o077 == 0,
            "Private state permissions are unsafe")
    state = json.loads(STATE.read_text())
    require(state.get("version") == 1 and isinstance(state.get("suffix"), str),
            "Private state format is unsupported")
    return state


def wire(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


class Client:
    def __init__(self, config: dict):
        self.config = config
        self.sessions: dict[int, dict] = {}

    @staticmethod
    def raw(url: str, method: str, body: bytes | None, headers: dict) -> tuple[int, dict]:
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, request, fp, code, msg, headers, newurl):
                return None

        request = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            try:
                result = json.load(error)
                code = result.get("code") if isinstance(result, dict) else None
            except (ValueError, UnicodeError):
                code = None
            return error.code, {"code": code}
        except urllib.error.URLError:
            raise Refused("Local HTTP request failed; rerun setup to replay pending write") from None

    def login(self, owner: int) -> dict:
        user = self.config["users"][owner]
        status, result = self.raw(API + "/auth/login", "POST", wire({
            "email": user["email"], "password": user["password"],
            "captcha_token": "XXXX.DUMMY.TOKEN.XXXX",
        }), {"Content-Type": "application/json"})
        require(status == 200 and isinstance(result.get("session"), dict)
                and result["session"].get("access_token"), "Local auth login failed")
        self.sessions[owner] = result["session"]
        return result["session"]

    def refresh(self, owner: int) -> None:
        session = self.sessions[owner]
        status, result = self.raw(AUTH + "/auth/v1/token?grant_type=refresh_token", "POST",
                                  wire({"refresh_token": session["refresh_token"]}),
                                  {"Content-Type": "application/json",
                                   "apikey": self.config["publicAnonKey"]})
        require(status == 200 and result.get("access_token"), "Local auth refresh failed")
        self.sessions[owner] = result

    def api(self, owner: int, method: str, path: str, body: bytes | None = None,
            key: str | None = None) -> tuple[int, dict]:
        require(path.startswith("/financial-accounts") or path.startswith("/financial-activities"),
                "Refusing unrelated API route")
        require("?" not in path and ".." not in path and "//" not in path,
                "Refusing unexpected API path")
        if owner not in self.sessions:
            self.login(owner)
        def send() -> tuple[int, dict]:
            headers = {"Content-Type": "application/json",
                       "Authorization": "Bearer " + self.sessions[owner]["access_token"]}
            if key:
                headers["Idempotency-Key"] = key
            return self.raw(API + path, method, body, headers)
        status, result = send()
        if status == 401:
            self.refresh(owner)
            status, result = send()
        return status, result


def expect(client: Client, method: str, path: str, body: bytes | None = None,
           key: str | None = None, owner: int = 0, statuses: tuple[int, ...] = (200,)) -> dict:
    status, result = client.api(owner, method, path, body, key)
    route = path.split("/")[1]
    require(status in statuses, f"{method} {route} returned HTTP {status}"
            + (f" ({result['code']})" if result.get("code") else ""))
    return result


def account_request(label: str, state: dict) -> dict:
    _, kind, currency, amount, _ = next(row for row in ACCOUNTS if row[0] == label)
    body = {"type": kind, "currency": currency,
            "nickname": f"Budget demo {label} {state['suffix']}",
            "as_of": OPENED, "time_zone": ZONE}
    if amount is not None:
        body["amount"] = amount
    return body


def activity_request(row: tuple, state: dict) -> dict:
    label, kind, amount, _, category, accounts, _ = row
    body = {"kind": kind, "amount": amount, "occurred_at": OCCURRED,
            "time_zone": ZONE, "note": f"Budget demo {label} {state['suffix']}",
            "category_id": category, "coverage": [], "expected_versions": {}}
    if len(accounts) == 1:
        body["account_id"] = state["accounts"][accounts[0]]
    else:
        body["source_account_id"] = state["accounts"][accounts[0]]
        body["destination_account_id"] = state["accounts"][accounts[1]]
    return body


def pending_write(client: Client, state: dict, kind: str, label: str,
                  path: str, body: bytes) -> dict:
    pending = state["pending"]
    if pending is None:
        pending = {"kind": kind, "label": label, "path": path,
                   "body": body.decode(), "key": str(uuid4())}
        state["pending"] = pending
        save_state(state)
    else:
        require((pending["kind"], pending["label"], pending["path"]) ==
                (kind, label, path), "Pending write must be recovered in order")
    result = expect(client, "POST", pending["path"], pending["body"].encode(),
                    pending["key"], statuses=(200, 201))
    if kind == "account":
        account_id = result.get("id")
    else:
        account_id = result.get("activity", {}).get("activity_id")
    require(isinstance(account_id, str) and str(UUID(account_id)) == account_id,
            "Write receipt has no valid fixture ID")
    state["accounts" if kind == "account" else "activities"][label] = account_id
    state["last_write"] = pending
    if (kind, label) in (("account", "checking"), ("activity", "groceries_checking")):
        state["replay_proof"][kind] = result
    state["pending"] = None
    save_state(state)
    return result


def prove_replay(client: Client, state: dict, kind: str) -> None:
    label = "checking" if kind == "account" else "groceries_checking"
    operation = state["requests"][kind]
    first = state["replay_proof"][kind]
    replay = expect(client, "POST", operation["path"], operation["body"].encode(),
                    operation["key"], statuses=(200, 201))
    if kind == "account":
        require(replay == first and replay["id"] == state["accounts"][label],
                "Account replay identity changed")
    else:
        require(replay.get("activity") == first.get("activity")
                and replay.get("accounts") == first.get("accounts")
                and replay.get("replayed") is True
                and replay["activity"]["activity_id"] == state["activities"][label],
                "Money replay identity or activity changed")
    state["replay_proof"][kind + "_checked"] = True
    save_state(state)


def setup(client: Client, state: dict) -> None:
    state.setdefault("requests", {})
    for label, *_ in ACCOUNTS:
        if label not in state["accounts"]:
            body = wire(account_request(label, state))
            result = pending_write(client, state, "account", label,
                                   "/financial-accounts", body)
            require(result["nickname"] == f"Budget demo {label} {state['suffix']}",
                    "Account identity mismatch")
        if label == "checking" and "account" not in state["requests"]:
            operation = state.get("last_write")
            require(operation is not None, "First account write journal missing")
            state["requests"]["account"] = operation
            save_state(state)
        if label == "checking" and not state["replay_proof"].get("account_checked"):
            prove_replay(client, state, "account")
    for row in ACTIVITIES:
        label = row[0]
        if label not in state["activities"]:
            if state["pending"] is None:
                preview = expect(client, "POST", "/financial-activities/preview",
                                 wire(activity_request(row, state)))
                require(preview.get("ready") is True and preview.get("preview_token")
                        and isinstance(preview.get("reviewed_request"), dict),
                        "Activity preview needs review")
                reviewed = preview["reviewed_request"]
                reviewed["preview_token"] = preview["preview_token"]
                body = wire(reviewed)
            else:
                body = state["pending"]["body"].encode()
            result = pending_write(client, state, "activity", label,
                                   "/financial-activities", body)
            check_activity(result["activity"], row, state)
        if label == "groceries_checking" and "activity" not in state["requests"]:
            operation = state.get("last_write")
            require(operation is not None, "First activity write journal missing")
            state["requests"]["activity"] = operation
            save_state(state)
        if label == "groceries_checking" and not state["replay_proof"].get("activity_checked"):
            prove_replay(client, state, "activity")


def check_activity(activity: dict, row: tuple, state: dict) -> None:
    label, kind, _, currency, category, account_labels, movements = row
    require(activity.get("activity_id") == state["activities"][label]
            and activity.get("kind") == kind and activity.get("currency") == currency
            and activity.get("amount_minor") == int(row[2].replace(".", ""))
            and activity.get("category_id") == category
            and activity.get("note") == f"Budget demo {label} {state['suffix']}"
            and activity.get("time_zone") == ZONE,
            "Activity identity or amount differs")
    expected = {state["accounts"][name]: movement
                for name, movement in zip(account_labels, movements, strict=True)}
    actual = {leg["account_id"]: leg["balance_movement_minor"]
              for leg in activity.get("legs", [])}
    require(actual == expected, "Activity leg movements differ")


def readback(client: Client, state: dict) -> dict:
    require(state["pending"] is None and len(state["accounts"]) == len(ACCOUNTS)
            and len(state["activities"]) == len(ACTIVITIES)
            and state["replay_proof"].get("account_checked")
            and state["replay_proof"].get("activity_checked"),
            "Fixture is incomplete; run setup")
    snapshot = {"accounts": {}, "activities": len(ACTIVITIES)}
    for label, _, currency, opening, expected_minor in ACCOUNTS:
        account_id = state["accounts"][label]
        account = expect(client, "GET", "/financial-accounts/" + account_id)
        require(account.get("id") == account_id and account.get("currency") == currency
                and account.get("nickname") == f"Budget demo {label} {state['suffix']}",
                "Account readback identity differs")
        balance = account["balance"]
        if expected_minor is None:
            require(balance.get("state") == "unknown"
                    and balance.get("activity_since_tracking_minor") == -300,
                    "Unknown account was treated as known")
            snapshot["accounts"][label] = "unknown"
        else:
            require(balance.get("state") == "known"
                    and balance.get("amount_minor") == expected_minor
                    and account.get("opening", {}).get("amount_minor") ==
                    (int(opening.replace(".", "")) * (-1 if label == "card" else 1)),
                    "Initial fixture balance differs; later demo edits need separate acceptance")
            snapshot["accounts"][label] = expected_minor
    for row in ACTIVITIES:
        activity = expect(client, "GET", "/financial-activities/" +
                          state["activities"][row[0]])
        check_activity(activity, row, state)
    account_id = state["accounts"]["checking"]
    activity_id = state["activities"]["groceries_checking"]
    status_a, result_a = client.api(1, "GET", "/financial-accounts/" + account_id)
    status_b, result_b = client.api(1, "GET", "/financial-activities/" + activity_id)
    require(status_a == status_b == 404
            and result_a.get("code") == "financial_account_not_found"
            and result_b.get("code") == "financial_account_not_found",
            "Owner isolation readback failed")
    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("setup", "readback"))
    action = parser.parse_args().action
    config = load_client()
    state = load_state(create=action == "setup")
    client = Client(config)
    if action == "setup":
        setup(client, state)
        print("initial fixture journal ready: 5 accounts, 8 activities; records preserved")
    else:
        snapshot = readback(client, state)
        print(json.dumps({"phase": "initial_fixture_baseline", "checks": 15,
                          "snapshot": snapshot},
                         sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (Refused, ValueError, KeyError, TypeError, OSError) as error:
        if isinstance(error, Refused):
            print(str(error), file=sys.stderr)
        else:
            print("Fixture state or local response is invalid", file=sys.stderr)
        raise SystemExit(1) from None
