"""Shared plumbing for the native auth HTTP probe.

A Device models one installed app: its own client IP (sent as the header the
API trusts in place of Cloudflare), its own cookie policy, and nothing else.
Every credential the probe handles is registered as a secret, and the evidence
writer refuses to write a file that contains one.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import time
import uuid
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any, Literal

import httpx
import psycopg

CookiePolicy = Literal["none", "platform-default", "auth-scoped"]
HANDOFF_COOKIES = ("argus-guest-handoff", "argus-guest-handoff-id")
# Argus limits auth attempts per client IP in process memory, so each run gets
# its own private /16 and each device one address inside it.
_RUN_NET = (secrets.randbelow(250) + 1, secrets.randbelow(250) + 1)


def device_ip(n: int) -> str:
    return f"10.{_RUN_NET[0]}.{_RUN_NET[1]}.{n}"


@dataclass(frozen=True)
class Stack:
    argus_api: str
    supabase_url: str
    anon_key: str
    service_role_key: str
    db_url: str
    mailpit_url: str

    @classmethod
    def from_env(cls) -> Stack:
        return cls(
            argus_api=os.environ["NATIVE_AUTH_ARGUS_API"].rstrip("/"),
            supabase_url=os.environ["API_URL"].rstrip("/"),
            anon_key=os.environ["ANON_KEY"],
            service_role_key=os.environ["SERVICE_ROLE_KEY"],
            db_url=os.environ["DB_URL"],
            mailpit_url=os.environ["MAILPIT_URL"].rstrip("/"),
        )


class Secrets:
    def __init__(self) -> None:
        self._values: set[str] = set()

    def add(self, value: object) -> None:
        if isinstance(value, str) and len(value) >= 8:
            self._values.add(value)

    def add_session(self, payload: dict[str, Any] | None) -> None:
        session = (payload or {}).get("session") or payload or {}
        for key in ("access_token", "refresh_token"):
            self.add(session.get(key))

    def leaked_into(self, text: str) -> list[str]:
        return [f"secret#{i}" for i, value in enumerate(self._values) if value in text]


SECRETS = Secrets()


@dataclass
class Result:
    id: str
    area: str
    scenario: str
    path: str
    evidence_level: int
    expected: str
    observed: dict[str, Any]
    verdict: Literal["pass", "fail", "unverified"]
    note: str = ""


@dataclass
class Recorder:
    client: str
    results: list[Result] = field(default_factory=list)

    def check(
        self,
        id: str,
        *,
        area: str,
        scenario: str,
        path: str,
        level: int,
        expected: str,
        observed: dict[str, Any],
        ok: bool,
        note: str = "",
    ) -> bool:
        verdict: Literal["pass", "fail"] = "pass" if ok else "fail"
        self.results.append(
            Result(id, area, scenario, path, level, expected, observed, verdict, note)
        )
        print(f"[{verdict.upper():4}] {id} {scenario}")
        if not ok:
            print(f"       observed={observed}")
        return ok

    def write(self, target: Path, meta: dict[str, Any]) -> None:
        body = json.dumps(
            {
                "client": self.client,
                **meta,
                "results": [r.__dict__ for r in self.results],
            },
            indent=2,
            sort_keys=False,
        )
        leaked = SECRETS.leaked_into(body)
        if leaked:
            raise SystemExit(
                f"refusing to write evidence: {len(leaked)} secret(s) present"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body + "\n")


class Device:
    """One app install: an IP, a cookie policy, and a cookie store."""

    def __init__(self, stack: Stack, name: str, ip: str, policy: CookiePolicy) -> None:
        self.stack = stack
        self.name = name
        self.ip = ip
        self.policy = policy
        self.cookies: dict[str, tuple[str, str]] = {}
        self.http = httpx.Client(timeout=30.0)

    def _keep(self, name: str) -> bool:
        if self.policy == "platform-default":
            return True
        if self.policy == "auth-scoped":
            return name in HANDOFF_COOKIES
        return False

    def _absorb(self, response: httpx.Response) -> None:
        for header in response.headers.get_list("set-cookie"):
            jar: SimpleCookie = SimpleCookie()
            jar.load(header)
            for name, morsel in jar.items():
                if not self._keep(name):
                    continue
                if morsel["max-age"] == "0" or morsel.value in ("", '""'):
                    self.cookies.pop(name, None)
                else:
                    SECRETS.add(morsel.value)
                    self.cookies[name] = (morsel.value, morsel["path"] or "/")

    def _cookie_header(self, path: str) -> str | None:
        pairs = [
            f"{name}={value}"
            for name, (value, cookie_path) in self.cookies.items()
            if path.startswith(cookie_path)
        ]
        return "; ".join(pairs) or None

    def argus(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json_body: Any = None,
        headers: dict[str, str] | None = None,
        base: str | None = None,
    ) -> httpx.Response:
        full_path = f"/api/v1{path}"
        request_headers = {"CF-Connecting-IP": self.ip, **(headers or {})}
        if token:
            request_headers["Authorization"] = f"Bearer {token}"
        cookie = self._cookie_header(full_path)
        if cookie:
            request_headers["Cookie"] = cookie
        response = self.http.request(
            method,
            f"{base or self.stack.argus_api}{full_path}",
            json=json_body,
            headers=request_headers,
        )
        # httpx keeps its own jar; clearing it leaves the policy jar as the only store.
        self.http.cookies.clear()
        self._absorb(response)
        return response

    def forget_cookies(self) -> None:
        self.cookies.clear()


def problem_code(response: httpx.Response) -> str | None:
    try:
        body = response.json()
    except ValueError:
        return None
    if isinstance(body, dict):
        detail = body.get("detail")
        if isinstance(detail, dict) and detail.get("code"):
            return str(detail["code"])
        if body.get("code"):
            return str(body["code"])
    return None


def set_cookie_names(response: httpx.Response) -> list[str]:
    names: list[str] = []
    for header in response.headers.get_list("set-cookie"):
        names.append(header.split("=", 1)[0])
    return sorted(set(names))


def set_cookie_attrs(response: httpx.Response, name: str) -> list[str]:
    for header in response.headers.get_list("set-cookie"):
        if header.startswith(f"{name}="):
            return sorted(
                part.strip().split("=", 1)[0].lower()
                + (
                    "=" + part.strip().split("=", 1)[1]
                    if part.strip().lower().startswith(("path", "samesite"))
                    else ""
                )
                for part in header.split(";")[1:]
            )
    return []


def me_email(response: httpx.Response) -> str | None:
    if response.status_code != 200:
        return None
    return (response.json().get("user") or {}).get("email")


def jwt_claims(token: str) -> dict[str, Any]:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


class GoTrue:
    """Direct Supabase Auth calls, the same ones the official SDKs make."""

    def __init__(self, stack: Stack) -> None:
        self.stack = stack
        self.http = httpx.Client(timeout=30.0)

    def _headers(self, bearer: str | None = None) -> dict[str, str]:
        return {
            "apikey": self.stack.anon_key,
            "Authorization": f"Bearer {bearer or self.stack.anon_key}",
        }

    def refresh(self, refresh_token: str) -> httpx.Response:
        response = self.http.post(
            f"{self.stack.supabase_url}/auth/v1/token?grant_type=refresh_token",
            json={"refresh_token": refresh_token},
            headers=self._headers(),
        )
        if response.status_code == 200:
            SECRETS.add_session(response.json())
        return response

    def password(self, email: str, password: str, captcha: str | None) -> httpx.Response:
        body: dict[str, Any] = {"email": email, "password": password}
        if captcha is not None:
            body["gotrue_meta_security"] = {"captcha_token": captcha}
        response = self.http.post(
            f"{self.stack.supabase_url}/auth/v1/token?grant_type=password",
            json=body,
            headers=self._headers(),
        )
        if response.status_code == 200:
            SECRETS.add_session(response.json())
        return response

    def logout(self, access_token: str, scope: str) -> httpx.Response:
        return self.http.post(
            f"{self.stack.supabase_url}/auth/v1/logout?scope={scope}",
            headers=self._headers(access_token),
        )

    def recover(
        self, email: str, redirect_to: str, challenge: str | None, captcha: str | None
    ) -> httpx.Response:
        body: dict[str, Any] = {"email": email}
        if challenge:
            body.update(code_challenge=challenge, code_challenge_method="s256")
        if captcha is not None:
            body["gotrue_meta_security"] = {"captcha_token": captcha}
        return self.http.post(
            f"{self.stack.supabase_url}/auth/v1/recover",
            params={"redirect_to": redirect_to},
            json=body,
            headers=self._headers(),
        )

    def exchange_pkce(self, code: str, verifier: str) -> httpx.Response:
        response = self.http.post(
            f"{self.stack.supabase_url}/auth/v1/token?grant_type=pkce",
            json={"auth_code": code, "code_verifier": verifier},
            headers=self._headers(),
        )
        if response.status_code == 200:
            SECRETS.add_session(response.json())
        return response

    def verify_link(self, url: str) -> httpx.Response:
        return self.http.get(url, follow_redirects=False)


def refresh_token_rows(stack: Stack, session_id: str) -> tuple[int, int]:
    """(total, revoked) refresh tokens Supabase holds for one session."""
    with psycopg.connect(stack.db_url) as conn:
        row = conn.execute(
            "select count(*), count(*) filter (where revoked) "
            "from auth.refresh_tokens where session_id = %s",
            (session_id,),
        ).fetchone()
    return (int(row[0]), int(row[1])) if row else (0, 0)


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    SECRETS.add(verifier)
    return verifier, challenge


@dataclass(frozen=True)
class Identity:
    email: str
    password: str


class Identities:
    """Synthetic users on the lane stack. Passwords live only in memory."""

    def __init__(self, stack: Stack, run_id: str) -> None:
        self.stack = stack
        self.run_id = run_id

    def email(self, label: str) -> str:
        return f"native-{label}-{self.run_id}@proof.argus.local"

    def allowlist(self, email: str) -> None:
        with psycopg.connect(self.stack.db_url, autocommit=True) as conn:
            conn.execute(
                "insert into public.private_alpha_allowlist (email) values (%s) "
                "on conflict (email) do nothing",
                (email,),
            )

    def create(self, label: str, *, allowlisted: bool = True) -> Identity:
        email = self.email(label)
        password = secrets.token_urlsafe(18)
        SECRETS.add(password)
        response = httpx.post(
            f"{self.stack.supabase_url}/auth/v1/admin/users",
            json={"email": email, "password": password, "email_confirm": True},
            headers={
                "apikey": self.stack.service_role_key,
                "Authorization": f"Bearer {self.stack.service_role_key}",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        if allowlisted:
            self.allowlist(email)
        return Identity(email, password)

    def new_password(self) -> str:
        password = secrets.token_urlsafe(18)
        SECRETS.add(password)
        return password


class Mailpit:
    def __init__(self, stack: Stack) -> None:
        self.base = stack.mailpit_url

    def latest_link(self, email: str, *, after: float, timeout: float = 20.0) -> str:
        deadline = time.time() + timeout
        while time.time() < deadline:
            listing = httpx.get(
                f"{self.base}/api/v1/search", params={"query": f"to:{email}"}
            ).json()
            for message in listing.get("messages", []):
                created = message.get("Created", "")
                if _iso_to_epoch(created) + 1 < after:
                    continue
                full = httpx.get(f"{self.base}/api/v1/message/{message['ID']}").json()
                match = re.search(
                    r"https?://[^\s\"'<>]+/auth/v1/verify[^\s\"'<>]+", full["Text"]
                )
                if match:
                    link = match.group(0).replace("&amp;", "&")
                    SECRETS.add(link)
                    return link
            time.sleep(0.5)
        raise TimeoutError(f"no auth email for {email}")


def _iso_to_epoch(value: str) -> float:
    from datetime import datetime

    # Python 3.10 rejects fractional seconds that are not 3 or 6 digits.
    whole = re.sub(r"\.\d+", "", value.replace("Z", "+00:00"))
    return datetime.fromisoformat(whole).timestamp()


def run_id() -> str:
    return uuid.uuid4().hex[:8]
