"""CLI-driven same-browser local recovery proof. Never prints credential material."""

from __future__ import annotations

import argparse
import html
import json
import re
import secrets
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from local_stack import WORK, status

FOLDER = WORK / "recovery-browser"
FIXTURE = FOLDER / "private-fixture.json"
CLI = Path.home() / ".codex/skills/playwright/scripts/playwright_cli.sh"
SESSION = "ios-auth-recovery"


def request(url, data=None, headers=None, method=None):
    body = None if data is None else json.dumps(data).encode()
    headers = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        return error.code, {}


def cli(*args):
    result = subprocess.run(
        [str(CLI), "--session", SESSION, "--raw", *args],
        cwd=FOLDER,
        capture_output=True,
        text=True,
        check=False,
    )
    # Output can include browser URLs, generated code, or fields. Never print it.
    if result.returncode:
        raise RuntimeError(
            "Browser CLI operation failed; inspect only a fresh sanitized snapshot."
        )
    return result.stdout


def save(data):
    FIXTURE.write_text(json.dumps(data))
    FIXTURE.chmod(0o600)


def load():
    return json.loads(FIXTURE.read_text())


def seed():
    if FIXTURE.exists():
        raise RuntimeError("Recovery fixture exists; do not create duplicates.")
    cfg = status()
    f = {
        "email": "recovery-only-" + secrets.token_hex(5) + "@example.test",
        "oldPassword": secrets.token_urlsafe(24),
        "newPassword": secrets.token_urlsafe(24),
    }
    code, user = request(
        cfg["API_URL"] + "/auth/v1/admin/users",
        {"email": f["email"], "password": f["oldPassword"], "email_confirm": True},
        {
            "apikey": cfg["SERVICE_ROLE_KEY"],
            "Authorization": "Bearer " + cfg["SERVICE_ROLE_KEY"],
        },
    )
    assert code in (200, 201), "Local admin create failed"
    f["id"] = user["id"]
    save(f)
    code, result = request(
        "http://127.0.0.1:58400/api/v1/auth/login",
        {
            "email": f["email"],
            "password": f["oldPassword"],
            "captcha_token": "argus-local-browser-qa",
        },
    )
    f["oldLoginStatus"] = code
    if code == 200:
        f["oldSession"] = result["session"]
    save(f)
    print(
        json.dumps(
            {
                "createdRecoveryOnlyUser": True,
                "oldArgusLoginStatus": code,
                "argusLoginCalls": 1,
            }
        )
    )


def submit(email_ref, button_ref):
    f = load()
    cli("fill", email_ref, f["email"])
    cli("click", button_ref)
    print("Submitted recovery-only email through the unchanged form.")


def mail():
    f = load()
    query = urllib.parse.urlencode({"query": "to:" + f["email"]})
    code, results = request("http://127.0.0.1:58403/api/v1/search?" + query)
    assert code == 200, "Local mail query failed"
    messages = results.get("messages", [])
    if not messages:
        print(json.dumps({"recoveryMailFound": False}))
        return
    message_id = messages[0]["ID"]
    code, body = request("http://127.0.0.1:58403/api/v1/message/" + message_id)
    assert code == 200
    text = body.get("HTML", "") + body.get("Text", "")
    urls = [html.unescape(x) for x in re.findall(r'https?://[^\s<>"\']+', text)]
    link = next(
        (x for x in urls if "/auth/v1/verify" in x and "type=recovery" in x), None
    )
    assert link, "Recovery mail has no expected provider verification link"
    parsed = urllib.parse.urlparse(link)
    assert (
        parsed.hostname in ("127.0.0.1", "localhost") and parsed.port == 58401
    ), "Non-lane link refused"
    f["recoveryLink"] = link
    save(f)
    # No tokenized URL is emitted or stored in an automation snapshot: run-code
    # is captured and discarded, and the page strips the code before snapshot.
    cli("run-code", "async (page) => { await page.goto(" + json.dumps(link) + "); }")
    print(json.dumps({"recoveryMailFound": True, "openedInSameBrowser": True}))


def reset():
    f = load()
    password = json.dumps(f["newPassword"])
    code = (
        "async (page) => { await page.getByRole('textbox', {name:'New password', exact:true}).fill("
        + password
        + "); await page.getByRole('textbox', {name:'Confirm new password', exact:true}).fill("
        + password
        + "); await page.getByRole('button', {name:'Update password',exact:true}).click(); }"
    )
    cli("run-code", code)
    print(
        "Submitted the new synthetic password without printing it or capturing filled fields."
    )


def verify():
    cfg = status()
    f = load()
    old = f.get("oldSession", {})
    access_status, _ = request(
        "http://127.0.0.1:58400/api/v1/me",
        headers={"Authorization": "Bearer " + old.get("access_token", "")},
    )
    refresh_status, _ = request(
        cfg["API_URL"] + "/auth/v1/token?grant_type=refresh_token",
        {"refresh_token": old.get("refresh_token", "")},
        {"apikey": cfg["ANON_KEY"]},
    )
    new_status, new = request(
        "http://127.0.0.1:58400/api/v1/auth/login",
        {
            "email": f["email"],
            "password": f["newPassword"],
            "captcha_token": "argus-local-browser-qa",
        },
    )
    profile_status = None
    if new_status == 200:
        session = new["session"]
        profile_status, profile = request(
            "http://127.0.0.1:58400/api/v1/me",
            headers={"Authorization": "Bearer " + session["access_token"]},
        )
        assert profile_status != 200 or profile["user"]["id"] == f["id"]
        request(
            cfg["API_URL"] + "/auth/v1/logout?scope=local",
            {},
            {
                "apikey": cfg["ANON_KEY"],
                "Authorization": "Bearer " + session["access_token"],
            },
        )
    result = {
        "oldArgusLoginStatus": f.get("oldLoginStatus"),
        "oldAccessAfterReset": access_status,
        "oldRefreshAfterReset": refresh_status,
        "newPasswordLogin": new_status,
        "newIdentityMe": profile_status,
        "argusLoginCalls": 2,
        "boundary": "Unchanged web development CAPTCHA fixture; Supabase public Cloudflare always-pass test secret, no hosted changes.",
    }
    (FOLDER / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["seed", "submit", "mail", "reset", "verify"])
    parser.add_argument("--email-ref")
    parser.add_argument("--button-ref")
    args = parser.parse_args()
    FOLDER.mkdir(parents=True, exist_ok=True)
    if args.action == "submit":
        submit(args.email_ref, args.button_ref)
    else:
        globals()[args.action]()
