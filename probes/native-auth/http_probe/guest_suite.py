"""WP-A guest continuity against unchanged Argus (evidence level 3).

Compares a bearer-only client (no cookie store) with a cookie store scoped to
the two handoff cookies. No chat turn is sent: the conversation a guest carries
over is created empty through POST /conversations.
"""

from __future__ import annotations

import copy
import re
from datetime import datetime, timezone

from harness import (
    HANDOFF_COOKIES,
    SECRETS,
    Device,
    GoTrue,
    Identities,
    Mailpit,
    Recorder,
    Stack,
    device_ip,
    me_email,
    problem_code,
    set_cookie_attrs,
    set_cookie_names,
)
from session_suite import LOCAL_CAPTCHA, argus_login

UNCHANGED = "unchanged-argus"


class Guest:
    def __init__(self, device: Device) -> None:
        self.device = device
        response = device.argus(
            "POST",
            "/auth/guest",
            json_body={"captcha_token": LOCAL_CAPTCHA, "language": "en"},
        )
        self.start = response
        body = response.json() if response.status_code == 200 else {}
        SECRETS.add_session(body)
        self.access = (body.get("session") or {}).get("access_token", "")
        created = device.argus(
            "POST", "/conversations", token=self.access, json_body={"title": None}
        )
        self.conversation_id = (
            created.json()["conversation"]["id"] if created.status_code == 200 else ""
        )

    def handoff(self, email: str, kind: str = "existing_account"):
        return self.device.argus(
            "POST",
            "/auth/guest/handoffs",
            token=self.access,
            json_body={
                "handoff_kind": kind,
                "destination_email": email,
                "source_conversation_id": self.conversation_id,
            },
        )


def conversation_ids(device: Device, access: str) -> set[str]:
    response = device.argus("GET", "/conversations", token=access)
    return (
        {c["id"] for c in response.json().get("items", [])}
        if response.status_code == 200
        else set()
    )


def session_of(response) -> dict:
    return (
        (response.json() or {}).get("session") or {}
        if response.status_code == 200
        else {}
    )


def run(stack: Stack, ids: Identities, rec: Recorder) -> None:
    gotrue = GoTrue(stack)
    alice = ids.create("alice")
    bob = ids.create("bob")

    phone = Device(stack, "guest-bearer-only", device_ip(20), "none")
    guest = Guest(phone)
    start_body = guest.start.json() if guest.start.status_code == 200 else {}
    reuse = phone.argus(
        "POST",
        "/auth/guest",
        token=guest.access,
        json_body={"captcha_token": LOCAL_CAPTCHA},
    )
    rec.check(
        "C1",
        area="guest-start",
        scenario="Bearer-only guest start, then a second start that presents the guest bearer",
        path=UNCHANGED,
        level=3,
        expected="200 anonymous session in JSON; the repeat reuses the guest instead of minting one",
        observed={
            "status": guest.start.status_code,
            "account_kind": start_body.get("account_kind"),
            "has_session": bool(guest.access),
            "conversation_created": bool(guest.conversation_id),
            "repeat_status": reuse.status_code,
            "repeat_reused": reuse.json().get("reused")
            if reuse.status_code == 200
            else None,
        },
        ok=guest.start.status_code == 200
        and bool(guest.conversation_id)
        and reuse.status_code == 200
        and reuse.json().get("reused") is True,
        note="A native client must persist and resend its guest bearer; starting without it creates a new anonymous user and loses the temporary conversation.",
    )

    created = guest.handoff(alice.email)
    body = created.json() if created.status_code == 201 else {}
    rec.check(
        "C2",
        area="handoff-transport",
        scenario="Handoff creation returns its secret only as HttpOnly cookies scoped to /api/v1/auth",
        path=UNCHANGED,
        level=3,
        expected="201 {handoff_id, expires_at}; secret absent from the body",
        observed={
            "status": created.status_code,
            "body_keys": sorted(body),
            "set_cookie_names": set_cookie_names(created),
            "secret_cookie_attrs": set_cookie_attrs(created, "argus-guest-handoff"),
        },
        ok=created.status_code == 201 and sorted(body) == ["expires_at", "handoff_id"],
    )

    login = argus_login(phone, alice.email, alice.password)
    alice_access = session_of(login).get("access_token", "")
    explicit_claim = phone.argus(
        "POST", f"/auth/guest/handoffs/{body.get('handoff_id')}/claim", token=alice_access
    )
    rec.check(
        "C3",
        area="bearer-only-conversion",
        scenario="A bearer-only client signs in after creating a handoff",
        path=UNCHANGED,
        level=3,
        expected="Failed assumption: sign-in succeeds but nothing is claimed; the claim route refuses without the cookie",
        observed={
            "login_status": login.status_code,
            "guest_claim_present": "guest_claim"
            in (login.json() if login.status_code == 200 else {}),
            "conversation_moved": guest.conversation_id
            in conversation_ids(phone, alice_access),
            "explicit_claim_status": explicit_claim.status_code,
            "explicit_claim_code": problem_code(explicit_claim),
        },
        ok=login.status_code == 200
        and guest.conversation_id not in conversation_ids(phone, alice_access)
        and problem_code(explicit_claim) == "guest_handoff_invalid",
        note="Without a cookie store or a new transport, guest-to-account conversion on native loses the conversation.",
    )

    scoped = Device(stack, "guest-auth-scoped-jar", device_ip(21), "auth-scoped")
    g2 = Guest(scoped)
    g2.handoff(alice.email)
    stored_before = sorted(scoped.cookies)
    snapshot = copy.deepcopy(scoped.cookies)
    first = argus_login(scoped, alice.email, alice.password)
    first_claim = (first.json() if first.status_code == 200 else {}).get(
        "guest_claim"
    ) or {}
    a_access = session_of(first).get("access_token", "")
    rec.check(
        "C4",
        area="scoped-jar-conversion",
        scenario="A cookie store that keeps only argus-guest-handoff* converts the guest on sign-in",
        path=UNCHANGED,
        level=3,
        expected="200 with guest_claim for the guest conversation; no sb-* cookie retained; handoff cookies cleared",
        observed={
            "stored_before_login": stored_before,
            "login_status": first.status_code,
            "claimed_conversation_matches": first_claim.get("conversation_id")
            == g2.conversation_id,
            "conversation_visible_to_account": g2.conversation_id
            in conversation_ids(scoped, a_access),
            "stored_after_login": sorted(scoped.cookies),
            "response_set_cookie_names": set_cookie_names(first),
        },
        ok=first_claim.get("conversation_id") == g2.conversation_id
        and scoped.cookies == {}
        and g2.conversation_id in conversation_ids(scoped, a_access),
    )

    scoped.cookies = snapshot
    retry = argus_login(scoped, alice.email, alice.password)
    retry_claim = (retry.json() if retry.status_code == 200 else {}).get(
        "guest_claim"
    ) or {}
    rec.check(
        "C5",
        area="interruption",
        scenario="The sign-in response is lost after the claim committed; the app retries with the handoff it still holds",
        path=UNCHANGED,
        level=3,
        expected="Replay-safe: 200 with the same guest_claim, no duplicate and no error",
        observed={
            "retry_status": retry.status_code,
            "same_conversation": retry_claim.get("conversation_id") == g2.conversation_id,
        },
        ok=retry.status_code == 200
        and retry_claim.get("conversation_id") == g2.conversation_id,
        note="Clients must delete the stored handoff only after a response is received and processed.",
    )

    cancel = Device(stack, "guest-cancel", device_ip(22), "auth-scoped")
    g3 = Guest(cancel)
    h1 = g3.handoff(alice.email)
    still_guest = cancel.argus("GET", "/me", token=g3.access)
    h2 = g3.handoff(alice.email)
    later = argus_login(cancel, alice.email, alice.password)
    later_claim = (later.json() if later.status_code == 200 else {}).get(
        "guest_claim"
    ) or {}
    rec.check(
        "C6",
        area="cancellation",
        scenario="The user cancels sign-in, keeps chatting as a guest, then retries",
        path=UNCHANGED,
        level=3,
        expected="Guest session unaffected; a second handoff replaces the first; the later sign-in claims",
        observed={
            "guest_me_after_cancel": still_guest.status_code,
            "first_handoff": h1.status_code,
            "second_handoff": h2.status_code,
            "handoff_id_changed": h1.json().get("handoff_id")
            != h2.json().get("handoff_id")
            if h1.status_code == 201 and h2.status_code == 201
            else None,
            "later_claim_matches": later_claim.get("conversation_id")
            == g3.conversation_id,
        },
        ok=still_guest.status_code == 200
        and later_claim.get("conversation_id") == g3.conversation_id,
    )

    wrong = Device(stack, "guest-wrong-account", device_ip(23), "auth-scoped")
    g4 = Guest(wrong)
    g4.handoff(alice.email)
    as_bob = argus_login(wrong, bob.email, bob.password)
    bob_body = as_bob.json() if as_bob.content else {}
    rec.check(
        "C7",
        area="account-mismatch",
        scenario="The guest named one email, then signs in to a different account",
        path=UNCHANGED,
        level=3,
        expected="Claim refused as wrong destination; handoff cleared; the conversation stays with the guest",
        observed={
            "status": as_bob.status_code,
            "code": problem_code(as_bob),
            "session_in_body": isinstance(bob_body.get("session"), dict),
            "response_set_cookie_names": set_cookie_names(as_bob),
            "handoff_cookies_left": sorted(set(wrong.cookies) & set(HANDOFF_COOKIES)),
        },
        ok=problem_code(as_bob) == "guest_handoff_wrong_destination",
        note="Bob's password was accepted and Argus set sb-* session cookies, but the body carries no session. A bearer client ends up with a live Supabase session it cannot see or revoke.",
    )

    newcomer_email = ids.email("newcomer")
    ids.allowlist(newcomer_email)
    newcomer_password = ids.new_password()
    fresh = Device(stack, "guest-new-account", device_ip(24), "auth-scoped")
    g5 = Guest(fresh)
    created_new = g5.handoff(newcomer_email, kind="new_account_signup")
    expires_at = datetime.fromisoformat(
        re.sub(r"\.\d+", "", created_new.json()["expires_at"].replace("Z", "+00:00"))
    )
    ttl_minutes = round((expires_at - datetime.now(timezone.utc)).total_seconds() / 60)
    sent_at = datetime.now(timezone.utc).timestamp()
    signup = fresh.argus(
        "POST",
        "/auth/guest/signup",
        token=g5.access,
        json_body={
            "email": newcomer_email,
            "password": newcomer_password,
            "captcha_token": LOCAL_CAPTCHA,
            "language": "en",
        },
    )
    signup_body = signup.json() if signup.status_code == 200 else {}
    link = Mailpit(stack).latest_link(newcomer_email, after=sent_at)
    confirmed = gotrue.verify_link(link)
    location = confirmed.headers.get("location", "")
    restarted = Device(
        stack, "guest-new-account-after-restart", device_ip(24), "auth-scoped"
    )
    restarted.cookies = copy.deepcopy(fresh.cookies)
    after_confirm = argus_login(restarted, newcomer_email, newcomer_password)
    confirm_claim = (
        after_confirm.json() if after_confirm.status_code == 200 else {}
    ).get("guest_claim") or {}
    rec.check(
        "C8",
        area="new-account-conversion",
        scenario="Guest creates an account, leaves to confirm email, the app restarts, then signs in",
        path=UNCHANGED,
        level=3,
        expected="Signup returns no session while confirmation is pending; the persisted handoff claims on first sign-in",
        observed={
            "handoff_ttl_minutes": ttl_minutes,
            "signup_status": signup.status_code,
            "signup_session_present": isinstance(signup_body.get("session"), dict),
            "handoff_cookies_kept_for_confirmation": sorted(
                set(fresh.cookies) & set(HANDOFF_COOKIES)
            ),
            "confirmation_redirect_origin": location.split("#")[0].split("?")[0],
            "login_after_confirm": after_confirm.status_code,
            "claim_matches": confirm_claim.get("conversation_id") == g5.conversation_id,
        },
        ok=signup.status_code == 200
        and not isinstance(signup_body.get("session"), dict)
        and confirm_claim.get("conversation_id") == g5.conversation_id,
        note="The confirmation link returns to the web site_url, not the app. The handoff secret must survive an app restart in secure storage for its full lifetime.",
    )

    old_guest = fresh.argus("GET", "/me", token=g5.access)
    rec.check(
        "C9",
        area="post-conversion",
        scenario="The converted guest's old bearer after a successful claim",
        path=UNCHANGED,
        level=3,
        expected="Guest bearer no longer works; the app must discard it",
        observed={"status": old_guest.status_code, "code": problem_code(old_guest)},
        ok=old_guest.status_code in (401, 403),
    )

    switch = Device(stack, "switch", device_ip(25), "none")
    alice_session = session_of(argus_login(switch, alice.email, alice.password))
    gotrue.logout(alice_session["access_token"], "local")
    bob_session = session_of(argus_login(switch, bob.email, bob.password))
    bob_sees = conversation_ids(switch, bob_session["access_token"])
    stale = switch.argus("GET", "/me", token=alice_session["access_token"])
    rec.check(
        "C10",
        area="account-switch",
        scenario="After converting into Alice, sign out and sign in as Bob on the same device",
        path=UNCHANGED,
        level=3,
        expected="Bob sees none of Alice's claimed conversations; Alice's revoked token is refused",
        observed={
            "bob_sees_alice_claims": bool(
                bob_sees & {g2.conversation_id, g3.conversation_id}
            ),
            "alice_token_after_switch": stale.status_code,
            "bob_is_bob": me_email(
                switch.argus("GET", "/me", token=bob_session["access_token"])
            )
            == bob.email,
        },
        ok=not (bob_sees & {g2.conversation_id, g3.conversation_id})
        and stale.status_code == 401,
    )
