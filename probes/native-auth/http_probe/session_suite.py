"""WP-A session scenarios against unchanged Argus (evidence level 3)."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from harness import (
    SECRETS,
    Device,
    GoTrue,
    Identities,
    Recorder,
    Stack,
    device_ip,
    jwt_claims,
    me_email,
    problem_code,
    refresh_token_rows,
    set_cookie_names,
)

LOCAL_CAPTCHA = "native-proof-local-captcha"
UNCHANGED = "unchanged-argus"


def _error(response) -> str | None:
    return None if response.status_code == 200 else response.json().get("error_code")


def argus_login(device: Device, email: str, password: str):
    response = device.argus(
        "POST",
        "/auth/login",
        json_body={"email": email, "password": password, "captcha_token": LOCAL_CAPTCHA},
    )
    if response.status_code == 200:
        SECRETS.add_session(response.json())
    return response


def run(stack: Stack, ids: Identities, rec: Recorder, *, wait_for_expiry: bool) -> None:
    gotrue = GoTrue(stack)
    alice = ids.create("alice")
    bob = ids.create("bob")
    phone = Device(stack, "phone-a", device_ip(10), "none")

    login = argus_login(phone, alice.email, alice.password)
    body = login.json() if login.status_code == 200 else {}
    session = body.get("session") or {}
    access, refresh = session.get("access_token", ""), session.get("refresh_token", "")
    rec.check(
        "A1",
        area="sign-in",
        scenario="Argus /auth/login with no Origin and no cookies returns the session in JSON",
        path=UNCHANGED,
        level=3,
        expected="200 with access_token, refresh_token, expires_in; user id",
        observed={
            "status": login.status_code,
            "has_access_token": bool(access),
            "has_refresh_token": bool(refresh),
            "expires_in": session.get("expires_in"),
            "set_cookie_names": set_cookie_names(login),
        },
        ok=login.status_code == 200 and bool(access) and bool(refresh),
        note="Argus also sets sb-auth-token and sb-refresh-token cookies; a bearer client must not store them.",
    )

    me = phone.argus("GET", "/me", token=access)
    rec.check(
        "A2",
        area="bearer",
        scenario="Bearer access token reaches a harmless protected endpoint (GET /me)",
        path=UNCHANGED,
        level=3,
        expected="200 and the profile email matches the signed-in user",
        observed={"status": me.status_code, "email_matches": me_email(me) == alice.email},
        ok=me_email(me) == alice.email,
    )

    anon = phone.argus("GET", "/me")
    rec.check(
        "A3",
        area="bearer",
        scenario="No bearer and no cookie is rejected",
        path=UNCHANGED,
        level=3,
        expected="401 unauthorized",
        observed={"status": anon.status_code, "code": problem_code(anon)},
        ok=anon.status_code == 401 and problem_code(anon) == "unauthorized",
    )

    refreshed = gotrue.refresh(refresh)
    new = refreshed.json() if refreshed.status_code == 200 else {}
    same_session = (
        bool(new)
        and jwt_claims(new["access_token"])["session_id"]
        == jwt_claims(access)["session_id"]
    )
    me_new = phone.argus("GET", "/me", token=new.get("access_token"))
    me_old = phone.argus("GET", "/me", token=access)
    rec.check(
        "A4",
        area="refresh",
        scenario="Refresh directly against Supabase Auth with the public anon key, as the web does",
        path=UNCHANGED,
        level=3,
        expected="200, rotated refresh token, same session_id; Argus accepts the new access token",
        observed={
            "refresh_status": refreshed.status_code,
            "refresh_token_rotated": bool(new) and new.get("refresh_token") != refresh,
            "same_session_id": same_session,
            "me_with_new_access": me_new.status_code,
            "me_with_previous_access_before_expiry": me_old.status_code,
        },
        ok=refreshed.status_code == 200 and same_session and me_new.status_code == 200,
        note="The previous access token stays usable until its exp because the session row is unchanged.",
    )
    refresh = new.get("refresh_token", refresh)
    access = new.get("access_token", access)

    with ThreadPoolExecutor(max_workers=5) as pool:
        racers = list(pool.map(lambda _: gotrue.refresh(refresh), range(5)))
    statuses = sorted(r.status_code for r in racers)
    winners = [r.json() for r in racers if r.status_code == 200]
    rec.check(
        "A5a",
        area="refresh-race",
        scenario="Five unserialized refreshes with one refresh token inside the reuse window",
        path=UNCHANGED,
        level=3,
        expected="Server tolerates reuse inside refresh_token_reuse_interval (10 s locally)",
        observed={
            "statuses": statuses,
            "distinct_refresh_tokens_returned": len(
                {w["refresh_token"] for w in winners}
            ),
        },
        ok=all(s == 200 for s in statuses),
        note="The reuse window hides races only when every racer finishes inside it.",
    )
    parent = winners[-1]["refresh_token"] if winners else ""
    child = gotrue.refresh(parent).json()
    time.sleep(11)
    parent_reuse = gotrue.refresh(parent)
    grandparent_reuse = gotrue.refresh(refresh)
    active_after = gotrue.refresh(child.get("refresh_token", ""))
    rec.check(
        "A5b",
        area="refresh-race",
        scenario="Late racers present older refresh tokens after the reuse window",
        path=UNCHANGED,
        level=3,
        expected="Record Supabase's rule: which older tokens are still accepted, and whether the family is revoked",
        observed={
            "parent_status": parent_reuse.status_code,
            "grandparent_status": grandparent_reuse.status_code,
            "grandparent_error": _error(grandparent_reuse),
            "active_token_status_after_reuse": active_after.status_code,
        },
        ok=grandparent_reuse.status_code == 400
        and _error(grandparent_reuse) == "refresh_token_already_used",
        note="A token two rotations old is refused; the immediate parent is tolerated. One lost refresh response is survivable, two are a sign-out. Clients single-flight refresh and persist the rotated token before using it.",
    )

    expiring = argus_login(phone, alice.email, alice.password).json()["session"]
    carol = ids.create("carol")
    untouched = argus_login(
        Device(stack, "phone-c", device_ip(17), "none"), carol.email, carol.password
    ).json()["session"]
    carol_session = jwt_claims(untouched["access_token"])["session_id"]
    carol_rows_at_login = refresh_token_rows(stack, carol_session)
    if wait_for_expiry:
        exp = jwt_claims(untouched["access_token"])["exp"]
        time.sleep(max(0, exp - time.time()) + 2)
        expired = phone.argus("GET", "/me", token=expiring["access_token"])
        recovered = gotrue.refresh(expiring["refresh_token"])
        me_recovered = phone.argus(
            "GET",
            "/me",
            token=recovered.json().get("access_token")
            if recovered.status_code == 200
            else None,
        )
        rec.check(
            "A6",
            area="expiry",
            scenario="Expired access token is rejected; refresh recovers without re-entering credentials",
            path=UNCHANGED,
            level=3,
            expected="401 unauthorized on the expired token, then 200 after refresh",
            observed={
                "expired_status": expired.status_code,
                "expired_code": problem_code(expired),
                "refresh_status": recovered.status_code,
                "me_after_refresh": me_recovered.status_code,
            },
            ok=expired.status_code == 401 and me_recovered.status_code == 200,
            note="Another account signed in through the same API process afterwards, which moves that process's server-side refresh timer off this session (see A14). The API does not distinguish expired from revoked; clients refresh once on 401 and treat a second 401 as signed out.",
        )
        carol_rows_later = refresh_token_rows(stack, carol_session)
        carol_refresh = gotrue.refresh(untouched["refresh_token"])
        rec.check(
            "A14",
            area="refresh-ownership",
            scenario="The client alone owns refresh for a session Argus issued (the most recent sign-in on this API process, left untouched)",
            path=UNCHANGED,
            level=3,
            expected="The client's refresh token is still valid after the access token expires",
            observed={
                "refresh_tokens_at_login_total_revoked": list(carol_rows_at_login),
                "refresh_tokens_after_expiry_total_revoked": list(carol_rows_later),
                "client_refresh_status": carol_refresh.status_code,
                "client_refresh_error": _error(carol_refresh),
            },
            ok=carol_refresh.status_code == 200,
            note="Failed assumption. Argus's shared server-side supabase-py auth client keeps the last session it signed in and refreshes it on a timer (auto_refresh_token defaults to true), rotating the token the client holds. Once it rotates twice, the client's token is refused and the user is signed out. Affects web and native alike.",
        )

    fresh = argus_login(phone, alice.email, alice.password).json()["session"]
    access, refresh = fresh["access_token"], fresh["refresh_token"]
    argus_logout = phone.argus("POST", "/auth/logout", token=access)
    after_argus_logout = phone.argus("GET", "/me", token=access)
    rec.check(
        "A7",
        area="logout",
        scenario="Argus POST /auth/logout alone (clearing local state only)",
        path=UNCHANGED,
        level=3,
        expected="200, but the same access token still works: nothing was revoked",
        observed={
            "logout_status": argus_logout.status_code,
            "me_after": after_argus_logout.status_code,
            "refresh_still_valid": gotrue.refresh(refresh).status_code == 200,
        },
        ok=argus_logout.status_code == 200 and after_argus_logout.status_code == 200,
        note="Discarding tokens locally leaves a live refresh token server-side. Native logout must revoke.",
    )

    fresh = argus_login(phone, alice.email, alice.password).json()["session"]
    access, refresh = fresh["access_token"], fresh["refresh_token"]
    revoke = gotrue.logout(access, "local")
    me_revoked = phone.argus("GET", "/me", token=access)
    refresh_revoked = gotrue.refresh(refresh)
    rec.check(
        "A8",
        area="revoke",
        scenario="Supabase signOut(scope: local) revokes this session; Argus rejects its unexpired access token",
        path=UNCHANGED,
        level=3,
        expected="204; /me 401 before the JWT exp; refresh token rejected",
        observed={
            "revoke_status": revoke.status_code,
            "me_status": me_revoked.status_code,
            "me_code": problem_code(me_revoked),
            "access_token_unexpired": jwt_claims(access)["exp"] > time.time(),
            "refresh_status": refresh_revoked.status_code,
        },
        ok=revoke.status_code == 204
        and me_revoked.status_code == 401
        and refresh_revoked.status_code != 200,
        note="Argus checks auth.sessions on every request, so revocation is immediate, not at token expiry.",
    )

    tablet = Device(stack, "tablet-a", device_ip(11), "none")
    s1 = argus_login(phone, alice.email, alice.password).json()["session"]
    s2 = argus_login(tablet, alice.email, alice.password).json()["session"]
    others = gotrue.logout(s1["access_token"], "others")
    keep_s1 = phone.argus("GET", "/me", token=s1["access_token"])
    lost_s2 = tablet.argus("GET", "/me", token=s2["access_token"])
    everywhere = gotrue.logout(s1["access_token"], "global")
    lost_s1 = phone.argus("GET", "/me", token=s1["access_token"])
    rec.check(
        "A9",
        area="revoke",
        scenario="Sign out other devices, then everywhere",
        path=UNCHANGED,
        level=3,
        expected="others: this device 200, tablet 401; global: this device 401",
        observed={
            "others_status": others.status_code,
            "this_device_after_others": keep_s1.status_code,
            "tablet_after_others": lost_s2.status_code,
            "global_status": everywhere.status_code,
            "this_device_after_global": lost_s1.status_code,
        },
        ok=keep_s1.status_code == 200
        and lost_s2.status_code == 401
        and lost_s1.status_code == 401,
    )

    a = argus_login(phone, alice.email, alice.password).json()["session"]
    b = argus_login(phone, bob.email, bob.password).json()["session"]
    me_a = me_email(phone.argus("GET", "/me", token=a["access_token"]))
    me_b = me_email(phone.argus("GET", "/me", token=b["access_token"]))
    rec.check(
        "A10",
        area="account-switch",
        scenario="The server resolves identity only from the bearer on each request",
        path=UNCHANGED,
        level=3,
        expected="Each token returns its own user; switching is a client-side cache and in-flight concern",
        observed={
            "token_a_resolves_a": me_a == alice.email,
            "token_b_resolves_b": me_b == bob.email,
        },
        ok=me_a == alice.email and me_b == bob.email,
    )

    shared = Device(stack, "phone-default-jar", device_ip(12), "platform-default")
    argus_login(shared, alice.email, alice.password)
    b2 = argus_login(
        Device(stack, "scratch", device_ip(13), "none"), bob.email, bob.password
    ).json()["session"]
    no_bearer = shared.argus("GET", "/me")
    bearer_b = shared.argus("GET", "/me", token=b2["access_token"])
    rec.check(
        "A11",
        area="cookie-hazard",
        scenario="A platform-default cookie store keeps Argus's sb-auth-token from the last /auth/login",
        path=UNCHANGED,
        level=3,
        expected="Failed assumption: a request that omits the bearer is silently authenticated as the cookie's user",
        observed={
            "stored_cookie_names": sorted(shared.cookies),
            "no_bearer_status": no_bearer.status_code,
            "no_bearer_resolves_previous_user": me_email(no_bearer) == alice.email,
            "bearer_wins_over_cookie": me_email(bearer_b) == bob.email,
        },
        ok=me_email(no_bearer) == alice.email and me_email(bearer_b) == bob.email,
        note="Bearer takes precedence, but any code path that forgets the header acts as the previous account. Native clients must not keep sb-* cookies.",
    )

    dave = ids.create("dave")
    limited = Device(stack, "phone-rate", device_ip(14), "none")
    statuses = [
        argus_login(limited, dave.email, "wrong-password-xx").status_code
        for _ in range(9)
    ]
    last = argus_login(limited, dave.email, "wrong-password-xx")
    direct = [
        gotrue.password(dave.email, "wrong-password-xx", None).status_code
        for _ in range(9)
    ]
    rec.check(
        "A12",
        area="argus-checks",
        scenario="Argus login attempt limit versus calling Supabase password sign-in directly",
        path=UNCHANGED,
        level=3,
        expected="Argus answers 401 for 8 attempts, then 429 with Retry-After; direct Supabase calls are not counted by Argus",
        observed={
            "argus_statuses": statuses,
            "argus_retry_after_present": bool(last.headers.get("retry-after")),
            "direct_supabase_statuses": direct,
        },
        ok=statuses[:8] == [401] * 8 and statuses[8] == 429 and 429 not in direct,
        note="Direct SDK sign-in skips Argus's limiter, allowlist gate, profile repair, and guest claim. Sign-in stays on Argus.",
    )

    outsider = ids.create("outsider", allowlisted=False)
    via_argus = argus_login(
        Device(stack, "outsider-a", device_ip(15), "none"),
        outsider.email,
        outsider.password,
    )
    direct_ok = gotrue.password(outsider.email, outsider.password, None)
    me_direct = Device(stack, "outsider-b", device_ip(16), "none").argus(
        "GET",
        "/me",
        token=direct_ok.json().get("access_token")
        if direct_ok.status_code == 200
        else None,
    )
    rec.check(
        "A13",
        area="argus-checks",
        scenario="A non-allowlisted account signs in directly against Supabase",
        path=UNCHANGED,
        level=3,
        expected="Argus login 401; direct Supabase issues a session; Argus still refuses it on every product call",
        observed={
            "argus_login_status": via_argus.status_code,
            "direct_supabase_status": direct_ok.status_code,
            "me_with_direct_session": me_direct.status_code,
            "me_code": problem_code(me_direct),
        },
        ok=via_argus.status_code == 401 and me_direct.status_code in (401, 403),
        note="The allowlist is enforced twice, so a direct session is not an access bypass, but it is a live Supabase session Argus never counted.",
    )
