"""Proposal E3 through the SYNTHETIC header adapter (evidence level 2).

The client here keeps no cookies at all. Everything it needs for guest
conversion travels in headers and JSON, as a native app would store it in
Keychain or Keystore. Argus behind the adapter is unchanged.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from guest_suite import Guest, conversation_ids, session_of
from harness import (
    SECRETS,
    Device,
    GoTrue,
    Identities,
    Mailpit,
    Recorder,
    Stack,
    device_ip,
    problem_code,
    set_cookie_names,
)
from session_suite import LOCAL_CAPTCHA

SYNTHETIC = "synthetic-header-adapter"
TRANSPORT = {"Argus-Guest-Handoff-Transport": "header"}


class HeaderClient:
    """A bearer-only app that stores the handoff in secure storage, not a jar."""

    def __init__(self, device: Device, adapter: str) -> None:
        self.device = device
        self.adapter = adapter
        self.handoff: dict[str, str] = {}

    def call(self, method: str, path: str, **kwargs):
        headers = dict(TRANSPORT)
        if self.handoff:
            headers["Argus-Guest-Handoff-Id"] = self.handoff["id"]
            headers["Argus-Guest-Handoff-Secret"] = self.handoff["secret"]
        response = self.device.argus(
            method, path, headers=headers, base=self.adapter, **kwargs
        )
        if response.headers.get("argus-guest-handoff-state") == "cleared":
            self.handoff = {}
        return response

    def create_handoff(self, guest: Guest, email: str, kind: str = "existing_account"):
        response = self.call(
            "POST",
            "/auth/guest/handoffs",
            token=guest.access,
            json_body={
                "handoff_kind": kind,
                "destination_email": email,
                "source_conversation_id": guest.conversation_id,
            },
        )
        body = response.json() if response.status_code == 201 else {}
        if body.get("handoff_secret"):
            SECRETS.add(body["handoff_secret"])
            self.handoff = {"id": body["handoff_id"], "secret": body["handoff_secret"]}
        return response

    def login(self, email: str, password: str):
        response = self.call(
            "POST",
            "/auth/login",
            json_body={
                "email": email,
                "password": password,
                "captcha_token": LOCAL_CAPTCHA,
            },
        )
        body = response.json() if response.content else {}
        SECRETS.add_session(body if isinstance(body.get("session"), dict) else None)
        return response


def run(stack: Stack, ids: Identities, rec: Recorder) -> None:
    adapter = os.environ.get("NATIVE_AUTH_ADAPTER", "http://127.0.0.1:57461")
    gotrue = GoTrue(stack)
    alice = ids.create("alice")
    bob = ids.create("bob")

    app = HeaderClient(Device(stack, "native-header", device_ip(30), "none"), adapter)
    guest = Guest(app.device)
    created = app.create_handoff(guest, alice.email)
    rec.check(
        "S1",
        area="handoff-transport",
        scenario="Handoff creation over the proposed header transport",
        path=SYNTHETIC,
        level=2,
        expected="201 with handoff_id, expires_at, handoff_secret in JSON; no Set-Cookie reaches the client",
        observed={
            "status": created.status_code,
            "body_keys": sorted(created.json()) if created.status_code == 201 else [],
            "set_cookie_names": set_cookie_names(created),
        },
        ok=created.status_code == 201
        and bool(app.handoff)
        and not set_cookie_names(created),
    )

    stored = dict(app.handoff)
    login = app.login(alice.email, alice.password)
    claim = (login.json() if login.status_code == 200 else {}).get("guest_claim") or {}
    access = session_of(login).get("access_token", "")
    rec.check(
        "S2",
        area="bearer-only-conversion",
        scenario="Bearer-only sign-in presents the stored handoff in headers",
        path=SYNTHETIC,
        level=2,
        expected="200 with guest_claim; conversation owned by the account; client told to delete its handoff",
        observed={
            "status": login.status_code,
            "claim_matches": claim.get("conversation_id") == guest.conversation_id,
            "conversation_visible": guest.conversation_id
            in conversation_ids(app.device, access),
            "handoff_state_cleared": app.handoff == {},
            "set_cookie_names": set_cookie_names(login),
        },
        ok=claim.get("conversation_id") == guest.conversation_id and app.handoff == {},
    )

    app.handoff = stored
    retry = app.login(alice.email, alice.password)
    retry_claim = (retry.json() if retry.status_code == 200 else {}).get(
        "guest_claim"
    ) or {}
    rec.check(
        "S3",
        area="interruption",
        scenario="Response lost after the claim committed; retry with the same stored handoff",
        path=SYNTHETIC,
        level=2,
        expected="200 with the same guest_claim (Argus replay rule applies unchanged)",
        observed={
            "status": retry.status_code,
            "same_conversation": retry_claim.get("conversation_id")
            == guest.conversation_id,
        },
        ok=retry_claim.get("conversation_id") == guest.conversation_id,
    )

    wrong = HeaderClient(
        Device(stack, "native-header-wrong", device_ip(31), "none"), adapter
    )
    g2 = Guest(wrong.device)
    wrong.create_handoff(g2, alice.email)
    as_bob = wrong.login(bob.email, bob.password)
    body = as_bob.json() if as_bob.content else {}
    lifted = body.get("session") or {}
    revoked = gotrue.logout(lifted.get("access_token", ""), "local") if lifted else None
    rec.check(
        "S4",
        area="account-mismatch",
        scenario="Wrong account signs in; the session Argus created is returned beside the problem",
        path=SYNTHETIC,
        level=2,
        expected="403 guest_handoff_wrong_destination with a session the app can keep or revoke",
        observed={
            "status": as_bob.status_code,
            "code": problem_code(as_bob),
            "session_in_body": bool(lifted),
            "revoke_status": revoked.status_code if revoked is not None else None,
            "handoff_state_cleared": wrong.handoff == {},
        },
        ok=problem_code(as_bob) == "guest_handoff_wrong_destination"
        and revoked is not None
        and revoked.status_code == 204,
        note="Closes the C7 gap, where a bearer client gets no tokens for a session that exists.",
    )

    newcomer = ids.email("newcomer")
    ids.allowlist(newcomer)
    password = ids.new_password()
    fresh = HeaderClient(
        Device(stack, "native-header-new", device_ip(32), "none"), adapter
    )
    g3 = Guest(fresh.device)
    fresh.create_handoff(g3, newcomer, kind="new_account_signup")
    persisted = dict(fresh.handoff)
    sent_at = datetime.now(timezone.utc).timestamp()
    signup = fresh.call(
        "POST",
        "/auth/guest/signup",
        token=g3.access,
        json_body={
            "email": newcomer,
            "password": password,
            "captcha_token": LOCAL_CAPTCHA,
            "language": "en",
        },
    )
    gotrue.verify_link(Mailpit(stack).latest_link(newcomer, after=sent_at))
    relaunched = HeaderClient(
        Device(stack, "native-header-relaunch", device_ip(32), "none"), adapter
    )
    relaunched.handoff = persisted
    first = relaunched.login(newcomer, password)
    claim = (first.json() if first.status_code == 200 else {}).get("guest_claim") or {}
    rec.check(
        "S5",
        area="new-account-conversion",
        scenario="Guest signs up, confirms by email, relaunches with the handoff from secure storage",
        path=SYNTHETIC,
        level=2,
        expected="Signup 200 without session; first sign-in after confirmation claims",
        observed={
            "signup_status": signup.status_code,
            "handoff_kept_through_signup": fresh.handoff == persisted,
            "claim_matches": claim.get("conversation_id") == g3.conversation_id,
        },
        ok=signup.status_code == 200
        and claim.get("conversation_id") == g3.conversation_id,
    )

    scoped = HeaderClient(
        Device(stack, "native-header-scope", device_ip(33), "none"), adapter
    )
    g4 = Guest(scoped.device)
    scoped.create_handoff(g4, alice.email)
    tampered = {
        "id": scoped.handoff["id"],
        "secret": scoped.handoff["secret"][:-2] + "xx",
    }
    real = dict(scoped.handoff)
    scoped.handoff = tampered
    bad = scoped.login(alice.email, alice.password)
    scoped.handoff = real
    outside = scoped.call("GET", "/me", token=g4.access)
    rec.check(
        "S6",
        area="secrecy",
        scenario="A tampered secret, and handoff headers sent outside /api/v1/auth",
        path=SYNTHETIC,
        level=2,
        expected="Tampered secret refused as guest_handoff_invalid; headers outside the auth path are not forwarded",
        observed={
            "tampered_status": bad.status_code,
            "tampered_code": problem_code(bad),
            "outside_auth_status": outside.status_code,
        },
        ok=problem_code(bad) == "guest_handoff_invalid" and outside.status_code == 200,
        note="The tampered attempt signs the user in (Argus answers the handoff problem after password success), which S4's session-in-body rule covers.",
    )
