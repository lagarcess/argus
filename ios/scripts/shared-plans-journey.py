"""Replay-safe synthetic scene and real Auth/API readback for owned allocation59750."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import secrets
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "ios/.build/accounts-local-59750"
API = "http://127.0.0.1:59750/api/v1"
AUTH = "http://127.0.0.1:59751"
STATE = WORK / "shared-plans-private.json"
ROOTS = (
    "/auth/session",
    "/households",
    "/household-invitations",
    "/financial-accounts",
    "/financial-activities",
    "/financial-plan",
    "/financial-home",
    "/financial-search",
)
SCENE = (
    (0, "checking", "checking", "DOP", "1000", 100000),
    (0, "savings", "savings", "DOP", "0", 0),
    (0, "card", "credit_card", "DOP", "200", 20000),
    (0, "unknown", "savings", "DOP", None, None),
    (0, "usd", "checking", "USD", "100", 10000),
    (1, "checking", "checking", "DOP", "500", 50000),
    (1, "savings", "savings", "DOP", "0", 0),
)


class Refused(Exception):
    """Public diagnostic excluding credentials and response bodies."""


def require(condition, message):
    if not condition:
        raise Refused(message)


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def read_private(path):
    require(
        path.is_file() and not path.is_symlink() and path.stat().st_mode & 0o077 == 0,
        "Missing or unsafe private local fixture",
    )
    return json.loads(path.read_bytes())


def save_private(path, value):
    require(not path.is_symlink(), "Refusing symlinked private state")
    temporary = path.with_name(path.name + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(wire(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def validate_path(path):
    parsed = urlsplit(path)
    require(
        not parsed.scheme
        and not parsed.netloc
        and not parsed.fragment
        and not any(value in parsed.path for value in ("..", "//", "%"))
        and any(
            parsed.path == root or parsed.path.startswith(root + "/") for root in ROOTS
        ),
        "Refusing unexpected API path",
    )


def load_client():
    config = read_private(WORK / "client.json")
    require(
        config.get("apiURL") == API and config.get("supabaseURL") == AUTH,
        "Refusing endpoints outside new local allocation59750",
    )
    require(
        len(config.get("users", [])) == 3,
        "Reuse exactly three seeded synthetic identities",
    )
    return config


class Client:
    def __init__(self, config):
        self.config = config
        self.sessions = {}

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
            return error.code, {}
        except (urllib.error.URLError, TimeoutError):
            raise Refused(
                "Local HTTP interrupted; resume the exact pending operation"
            ) from None

    def login(self, actor):
        require(actor in (0, 1, 2), "Unexpected synthetic identity")
        user = self.config["users"][actor]
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
            "Local registered authentication failed",
        )
        require(
            result.get("user", {}).get("id") == user["id"],
            "Registered identity differs from fixture",
        )
        self.sessions[actor] = result["session"]

    def api(self, actor, method, path, body=None, key=None):
        validate_path(path)
        if actor not in self.sessions:
            self.login(actor)
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.sessions[actor]["access_token"],
        }
        if key:
            headers["Idempotency-Key"] = key
        return self.raw(API + path, method, body, headers)

    def get(self, actor, path, status=200):
        actual, result = self.api(actor, "GET", path)
        require(actual == status, f"Read returned HTTP {actual}; expected {status}")
        return result


class Journal:
    def __init__(self, path, create=False):
        self.path = path
        if path.exists():
            self.state = read_private(path)
            require(self.state.get("version") == 1, "Unsupported private scene journal")
        else:
            require(create, "Prepare the local scene before readback")
            self.state = {"version": 1, "suffix": secrets.token_hex(4), "operations": {}}
            self.save()

    def save(self):
        save_private(self.path, self.state)

    def command(self, client, name, actor, path, build, method="POST"):
        rows = self.state["operations"]
        if name not in rows:
            require(
                all("result" in row for row in rows.values()),
                "Resume pending write before another command",
            )
            validate_path(path)
            rows[name] = {
                "actor": actor,
                "path": path,
                "method": method,
                "body": wire(build()).decode(),
                "key": str(uuid4()),
            }
            self.save()
        row = rows[name]
        if "result" in row:
            return row["result"]
        status, result = client.api(
            row["actor"], row["method"], row["path"], row["body"].encode(), row["key"]
        )
        require(status in (200, 201), f"Operation {name} returned HTTP {status}")
        row["result"] = result
        self.save()
        return result


def prepare(journal, client):
    suffix = journal.state["suffix"]
    for actor, label, kind, currency, amount, _ in SCENE:
        body = {
            "type": kind,
            "currency": currency,
            "amount": amount,
            "nickname": f"Private {label} {actor} {suffix}",
        }
        journal.command(
            client,
            f"account-{actor}-{label}",
            actor,
            "/financial-accounts",
            lambda body=body: body,
        )
    created = journal.command(
        client,
        "household",
        0,
        "/households",
        lambda: {
            "name": "Shared plans " + suffix,
            "display_name": "Alice",
        },
    )
    hid = created["household_id"]
    invitation = journal.command(
        client,
        "invite",
        0,
        f"/households/{hid}/invitations",
        lambda: {
            "expected_version": client.get(0, f"/households/{hid}")["version"],
        },
    )
    journal.command(
        client,
        "accept",
        1,
        "/household-invitations/accept",
        lambda: {
            "token": invitation["invitation"]["token"],
            "display_name": "Bob",
        },
    )


def readback(journal, client):
    rows = journal.state["operations"]
    hid = rows["household"]["result"]["household_id"]
    for actor in (0, 1, 2):
        session = client.get(actor, "/auth/session")
        require(
            session["user"]["id"] == client.config["users"][actor]["id"],
            "Auth readback identity changed",
        )
    for actor, label, _, _, _, expected in SCENE:
        account = rows[f"account-{actor}-{label}"]["result"]
        current = client.get(actor, "/financial-accounts/" + account["id"])
        require(
            current["balance"]["amount_minor"] == expected,
            "Scene balance changed; do not reset or overwrite human edits",
        )
        client.get(1 - actor, "/financial-accounts/" + account["id"], status=404)
        client.get(2, "/financial-accounts/" + account["id"], status=404)
    for actor in (0, 1):
        household = client.get(actor, f"/households/{hid}")
        require(len(household["members"]) == 2, "Scene membership changed")
        require(
            client.get(actor, f"/households/{hid}/snapshot")["accounts"] == [],
            "Preparation must not auto-share accounts",
        )
    client.get(2, f"/households/{hid}", status=404)
    return {
        "source_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "runtime": "real isolated Auth59751/API59750/Postgres59752",
        "checks": [
            "three distinct registered identities",
            "two named household members",
            "private account isolation for both members and third identity",
            "unknown remains unknown",
            "currency separation",
            "membership does not share accounts",
        ],
        "scope": "Preparation and inherited boundaries only; shared plans are not yet accepted.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "readback"))
    args = parser.parse_args()
    require(
        WORK.is_dir() and not WORK.is_symlink(), "Missing lane-owned local allocation"
    )
    with (WORK / "shared-plans.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        client = Client(load_client())
        journal = Journal(STATE, create=args.action == "prepare")
        if args.action == "prepare":
            prepare(journal, client)
        proof = readback(journal, client)
        output = WORK / "shared-plans-preparation-proof.json"
        output.write_bytes(wire(proof))
        print(
            "Verified synthetic three-user preparation; private journal and proof retained locally."
        )


if __name__ == "__main__":
    try:
        main()
    except (Refused, BlockingIOError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from None
