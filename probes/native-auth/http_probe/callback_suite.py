"""WP-A confirmation and recovery callbacks (evidence level 3).

Argus is unchanged. The lane stack adds one synthetic allowlisted redirect,
argusnativeproof://auth-callback, which is a local stand-in for whatever app
identifier the founder approves. It is not a production identifier.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from harness import (
    Device,
    GoTrue,
    Identities,
    Mailpit,
    Recorder,
    Stack,
    device_ip,
    me_email,
    pkce_pair,
)
from session_suite import LOCAL_CAPTCHA, argus_login

NATIVE_CALLBACK = "argusnativeproof://auth-callback"
UNLISTED_CALLBACK = "argusnotlisted://auth-callback"
UNCHANGED = "unchanged-argus + lane redirect allowlist entry"


def _callback(location: str) -> dict[str, str]:
    parsed = urlparse(location)
    params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    params.update({k: v[0] for k, v in parse_qs(parsed.fragment).items()})
    return {"target": f"{parsed.scheme}://{parsed.netloc}{parsed.path}", **params}


def _request_recovery(gotrue: GoTrue, mail: Mailpit, email: str, redirect: str):
    verifier, challenge = pkce_pair()
    for _ in range(5):
        sent_at = datetime.now(timezone.utc).timestamp()
        requested = gotrue.recover(email, redirect, challenge, None)
        if requested.status_code != 429:
            break
        time.sleep(1.5)
    link = mail.latest_link(email, after=sent_at)
    return requested, link, verifier


def _error(response) -> str | None:
    return None if response.status_code == 200 else response.json().get("error_code")


def run(stack: Stack, ids: Identities, rec: Recorder, *, wait_for_expiry: bool) -> None:
    gotrue = GoTrue(stack)
    mail = Mailpit(stack)
    device = Device(stack, "callbacks", device_ip(40), "none")

    newcomer = ids.email("confirm")
    ids.allowlist(newcomer)
    sent_at = datetime.now(timezone.utc).timestamp()
    signup = device.argus(
        "POST",
        "/auth/signup",
        json_body={
            "email": newcomer,
            "password": ids.new_password(),
            "captcha_token": LOCAL_CAPTCHA,
            "language": "en",
        },
    )
    confirm = _callback(gotrue.verify_link(mail.latest_link(newcomer, after=sent_at)).headers.get("location", ""))
    rec.check(
        "D1",
        area="confirmation",
        scenario="Email confirmation after Argus /auth/signup",
        path="unchanged-argus",
        level=3,
        expected="Confirmation returns to the web site_url; Argus signup has no redirect parameter a native client could set",
        observed={
            "signup_status": signup.status_code,
            "callback_target": confirm["target"],
            "carries_session_fragment": "access_token" in confirm,
        },
        ok=signup.status_code == 200 and confirm["target"].startswith("http://localhost:3000"),
        note="Hosted: lands on the web app with an implicit-flow session in the URL fragment. A native return needs Argus to pass emailRedirectTo (proposal P4).",
    )

    user = ids.create("recover")
    requested, link, verifier = _request_recovery(gotrue, mail, user.email, NATIVE_CALLBACK)
    landed = _callback(gotrue.verify_link(link).headers.get("location", ""))
    exchanged = gotrue.exchange_pkce(landed.get("code", ""), verifier)
    session = exchanged.json() if exchanged.status_code == 200 else {}
    me = device.argus("GET", "/me", token=session.get("access_token"))
    rec.check(
        "D2",
        area="recovery",
        scenario="PKCE recovery that returns to an allowlisted app callback",
        path=UNCHANGED,
        level=3,
        expected="Link redirects to the app scheme with ?code; exchange with the verifier yields a session Argus accepts",
        observed={
            "recover_status": requested.status_code,
            "callback_target": landed["target"],
            "callback_has_code": "code" in landed,
            "callback_has_tokens": "access_token" in landed,
            "exchange_status": exchanged.status_code,
            "argus_me_matches": me_email(me) == user.email,
        },
        ok=landed["target"] == NATIVE_CALLBACK and me_email(me) == user.email,
    )

    repeat_exchange = gotrue.exchange_pkce(landed.get("code", ""), verifier)
    repeat_link = _callback(gotrue.verify_link(link).headers.get("location", ""))
    rec.check(
        "D3",
        area="recovery",
        scenario="The same callback delivered twice, and the same email link opened twice",
        path=UNCHANGED,
        level=3,
        expected="Second exchange refused; second link open returns an error to the callback, not a code",
        observed={
            "repeat_exchange_status": repeat_exchange.status_code,
            "repeat_exchange_error": _error(repeat_exchange),
            "repeat_link_target": repeat_link["target"],
            "repeat_link_error_code": repeat_link.get("error_code"),
            "repeat_link_has_code": "code" in repeat_link,
        },
        ok=repeat_exchange.status_code != 200 and "code" not in repeat_link,
    )

    _, link2, _verifier2 = _request_recovery(gotrue, mail, user.email, NATIVE_CALLBACK)
    landed2 = _callback(gotrue.verify_link(link2).headers.get("location", ""))
    other_verifier, _ = pkce_pair()
    mismatched = gotrue.exchange_pkce(landed2.get("code", ""), other_verifier)
    invalid = gotrue.exchange_pkce("00000000-0000-0000-0000-000000000000", other_verifier)
    rec.check(
        "D4",
        area="recovery",
        scenario="A code arrives on a device that did not start the flow (wrong verifier), and a forged code",
        path=UNCHANGED,
        level=3,
        expected="Both refused; no session",
        observed={
            "mismatched_status": mismatched.status_code,
            "mismatched_error": _error(mismatched),
            "invalid_status": invalid.status_code,
            "invalid_error": _error(invalid),
        },
        ok=mismatched.status_code != 200 and invalid.status_code != 200,
        note="PKCE binds the link to the device that requested it. A user who requests recovery on the phone and opens the email on a laptop cannot finish on the laptop through this flow.",
    )

    unlisted_requested, unlisted_link, _ = _request_recovery(gotrue, mail, user.email, UNLISTED_CALLBACK)
    unlisted = _callback(gotrue.verify_link(unlisted_link).headers.get("location", ""))
    rec.check(
        "D5",
        area="recovery",
        scenario="Recovery requested with a redirect that is not on the allowlist",
        path=UNCHANGED,
        level=3,
        expected="Supabase ignores the unlisted redirect and falls back to site_url",
        observed={"recover_status": unlisted_requested.status_code, "callback_target": unlisted["target"]},
        ok=unlisted["target"] != UNLISTED_CALLBACK,
    )

    before = argus_login(Device(stack, "other-device", device_ip(41), "none"), user.email, user.password)
    other_access = (before.json().get("session") or {}).get("access_token") if before.status_code == 200 else None
    _, link3, verifier3 = _request_recovery(gotrue, mail, user.email, NATIVE_CALLBACK)
    recovered = gotrue.exchange_pkce(
        _callback(gotrue.verify_link(link3).headers.get("location", "")).get("code", ""), verifier3
    ).json()
    updated = gotrue.http.put(
        f"{stack.supabase_url}/auth/v1/user",
        json={"password": ids.new_password()},
        headers={"apikey": stack.anon_key, "Authorization": f"Bearer {recovered.get('access_token', '')}"},
    )
    other_after_update = device.argus("GET", "/me", token=other_access)
    global_out = gotrue.logout(recovered.get("access_token", ""), "global")
    other_after_global = device.argus("GET", "/me", token=other_access)
    rec.check(
        "D6",
        area="recovery",
        scenario="Password reset by recovery, then sign out everywhere as the web recovery page does",
        path=UNCHANGED,
        level=3,
        expected="Other sessions end after the reset; the recovery session ends after signOut(scope: global)",
        observed={
            "update_status": updated.status_code,
            "other_session_after_update": other_after_update.status_code,
            "global_signout_status": global_out.status_code,
            "other_session_after_global": other_after_global.status_code,
        },
        ok=updated.status_code == 200
        and other_after_update.status_code == 401
        and global_out.status_code == 204
        and other_after_global.status_code == 401,
        note="Supabase revoked the other session on the password update itself. Native recovery still ends with a global sign-out, matching web/lib/auth-security.ts resetRecoveredPassword, so the recovery session does not linger.",
    )

    if wait_for_expiry:
        _, link4, _ = _request_recovery(gotrue, mail, user.email, NATIVE_CALLBACK)
        time.sleep(62)
        expired = _callback(gotrue.verify_link(link4).headers.get("location", ""))
        rec.check(
            "D7",
            area="recovery",
            scenario="Recovery link opened after otp_expiry (60 s on the lane stack)",
            path=UNCHANGED,
            level=3,
            expected="Callback receives an error, not a code",
            observed={
                "callback_target": expired["target"],
                "error_code": expired.get("error_code"),
                "has_code": "code" in expired,
            },
            ok="code" not in expired and bool(expired.get("error_code")),
        )
