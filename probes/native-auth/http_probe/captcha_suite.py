"""WP-A bot protection with Cloudflare's published Turnstile test secrets.

Local Supabase Auth is configured with a test secret, so it really calls
Cloudflare siteverify, but the answer is fixed by the key. This proves how
Argus and Supabase pass and enforce the token. It proves nothing about how a
production sitekey behaves inside a native web view.
"""

from __future__ import annotations

from harness import (
    SECRETS,
    Device,
    GoTrue,
    Identities,
    Recorder,
    Stack,
    device_ip,
    problem_code,
)

DUMMY_TOKEN = "XXXX.DUMMY.TOKEN.XXXX"
PATH = "unchanged-argus + local Supabase Auth with a Cloudflare test secret"


def _login(device: Device, email: str, password: str, token: str | None):
    body = {"email": email, "password": password}
    if token is not None:
        body["captcha_token"] = token
    response = device.argus("POST", "/auth/login", json_body=body)
    if response.status_code == 200:
        SECRETS.add_session(response.json())
    return response


def _guest(device: Device, token: str):
    return device.argus("POST", "/auth/guest", json_body={"captcha_token": token})


def _err(response) -> str | None:
    return None if response.status_code == 200 else response.json().get("error_code")


def run(stack: Stack, ids: Identities, rec: Recorder, *, captcha_mode: str) -> None:
    gotrue = GoTrue(stack)
    user = ids.create(f"captcha-{captcha_mode}")
    device = Device(stack, f"captcha-{captcha_mode}", device_ip(50), "none")

    if captcha_mode == "turnstile-pass":
        guest = _guest(device, DUMMY_TOKEN)
        login = _login(device, user.email, user.password, DUMMY_TOKEN)
        missing = _login(device, user.email, user.password, None)
        direct = gotrue.password(user.email, user.password, None)
        session = (login.json().get("session") or {}) if login.status_code == 200 else {}
        refreshed = gotrue.refresh(session.get("refresh_token", ""))
        rec.check(
            "B1",
            area="captcha",
            scenario="Test secret that always passes: token forwarded by Argus and verified by Supabase Auth",
            path=PATH,
            level=3,
            expected="Guest start and sign-in succeed with the dummy token; Argus rejects a missing token before Supabase; direct Supabase sign-in without a token fails; refresh needs no token",
            observed={
                "guest_with_dummy": guest.status_code,
                "login_with_dummy": login.status_code,
                "login_without_token": missing.status_code,
                "direct_supabase_without_token": direct.status_code,
                "direct_supabase_error": _err(direct),
                "refresh_without_token": refreshed.status_code,
            },
            ok=guest.status_code == 200
            and login.status_code == 200
            and missing.status_code == 422
            and direct.status_code != 200
            and refreshed.status_code == 200,
            note="Calling Supabase directly from the SDK does not skip captcha, so E2's direct-refresh path does not weaken bot protection. Sign-in still belongs on Argus for its own checks (A12, A13).",
        )
        other = _login(device, user.email, user.password, "not-the-dummy-token")
        rec.check(
            "B2",
            area="captcha",
            scenario="Always-pass test secret given a token the test widget would never issue",
            path=PATH,
            level=3,
            expected="Record Cloudflare's test-secret behavior for a non-dummy token",
            observed={"login_status": other.status_code, "code": problem_code(other)},
            ok=other.status_code in (200, 401),
            note="Documented: test secrets accept only the dummy token. Observed status tells whether that holds for this key.",
        )
    elif captcha_mode == "turnstile-fail":
        guest = _guest(device, DUMMY_TOKEN)
        login = _login(device, user.email, user.password, DUMMY_TOKEN)
        rec.check(
            "B3",
            area="captcha",
            scenario="Test secret that always fails",
            path=PATH,
            level=3,
            expected="Guest start and sign-in refused",
            observed={
                "guest_status": guest.status_code,
                "guest_code": problem_code(guest),
                "login_status": login.status_code,
                "login_code": problem_code(login),
                "login_detail_says_password": "password" in str(login.json()).lower(),
            },
            ok=guest.status_code >= 400 and login.status_code >= 400,
            note="Argus maps a rejected captcha to 401 'Invalid email or password' on sign-in and 503 guest_bootstrap_failed on guest start. A native client cannot tell a failed check from a wrong password (proposal P5).",
        )
    elif captcha_mode == "turnstile-spent":
        login = _login(device, user.email, user.password, DUMMY_TOKEN)
        rec.check(
            "B4",
            area="captcha",
            scenario="Test secret that reports an already-spent token (stand-in for reuse or expiry)",
            path=PATH,
            level=3,
            expected="Sign-in refused; the client must fetch a fresh token for every attempt",
            observed={"login_status": login.status_code, "code": problem_code(login)},
            ok=login.status_code >= 400,
        )
