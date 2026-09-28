"""SYNTHETIC ADAPTER. Not Argus. Demonstrates proposal E3 without changing Argus.

A reverse proxy in front of the unchanged Argus API that gives bearer clients a
header transport for the guest handoff secret:

* A request carrying ``Argus-Guest-Handoff-Transport: header`` never receives
  a Set-Cookie. On handoff creation the secret moves into the JSON body as
  ``handoff_secret``.
* ``Argus-Guest-Handoff-Id`` and ``Argus-Guest-Handoff-Secret`` on a request
  under ``/api/v1/auth/`` are forwarded to Argus as the two handoff cookies,
  mirroring the cookies' ``Path=/api/v1/auth`` scope. Elsewhere they are dropped.
* When Argus deletes the handoff cookies, the response says
  ``Argus-Guest-Handoff-State: cleared`` so the client deletes its copy.
* When Argus signed a user in but answered with a handoff problem (the session
  then exists only in Set-Cookie), the tokens move into the problem body as
  ``session`` so the client can keep or revoke them.

Evidence produced through this adapter is level 2 (synthetic) and is kept apart
from evidence against unchanged Argus.
"""

from __future__ import annotations

import http.cookiejar
import json
import os
from http.cookies import SimpleCookie

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

UPSTREAM = os.environ.get("NATIVE_AUTH_ADAPTER_UPSTREAM", "http://127.0.0.1:57460")
TRANSPORT_HEADER = "argus-guest-handoff-transport"
ID_HEADER = "argus-guest-handoff-id"
SECRET_HEADER = "argus-guest-handoff-secret"
HANDOFF_COOKIES = {
    "argus-guest-handoff": SECRET_HEADER,
    "argus-guest-handoff-id": ID_HEADER,
}
HOP_HEADERS = {"host", "content-length", "connection", "cookie", "transfer-encoding"}

# A jar that refuses every cookie: the proxy must never replay one caller's
# Argus session cookie on another caller's request.
client = httpx.AsyncClient(
    base_url=UPSTREAM,
    timeout=60.0,
    cookies=http.cookiejar.CookieJar(
        policy=http.cookiejar.DefaultCookiePolicy(allowed_domains=[])
    ),
)


def _set_cookies(response: httpx.Response) -> dict[str, tuple[str, bool]]:
    """name -> (value, deleted)"""
    cookies: dict[str, tuple[str, bool]] = {}
    for header in response.headers.get_list("set-cookie"):
        jar: SimpleCookie = SimpleCookie()
        jar.load(header)
        for name, morsel in jar.items():
            deleted = morsel["max-age"] == "0" or morsel.value in ("", '""')
            cookies[name] = (morsel.value, deleted)
    return cookies


async def proxy(request: Request) -> Response:
    header_transport = request.headers.get(TRANSPORT_HEADER, "").lower() == "header"
    forward = {k: v for k, v in request.headers.items() if k.lower() not in HOP_HEADERS}
    for name in (TRANSPORT_HEADER, ID_HEADER, SECRET_HEADER):
        forward.pop(name, None)
    if header_transport and request.url.path.startswith("/api/v1/auth/"):
        pairs = [
            f"{cookie}={request.headers[header]}"
            for cookie, header in HANDOFF_COOKIES.items()
            if request.headers.get(header)
        ]
        if pairs:
            forward["cookie"] = "; ".join(pairs)
    upstream = await client.request(
        request.method,
        request.url.path,
        params=request.query_params,
        content=await request.body(),
        headers=forward,
    )
    headers = {
        k: v
        for k, v in upstream.headers.items()
        if k.lower()
        not in {"set-cookie", "content-length", "content-encoding", "transfer-encoding"}
    }
    body = upstream.content
    if not header_transport:
        response = Response(body, status_code=upstream.status_code, headers=headers)
        for header in upstream.headers.get_list("set-cookie"):
            response.raw_headers.append((b"set-cookie", header.encode()))
        return response

    cookies = _set_cookies(upstream)
    payload = None
    if upstream.headers.get("content-type", "").startswith("application/json") and body:
        payload = json.loads(body)
    secret = cookies.get("argus-guest-handoff")
    if isinstance(payload, dict) and secret and not secret[1]:
        payload["handoff_secret"] = secret[0]
    if any(cookies.get(name, ("", False))[1] for name in HANDOFF_COOKIES):
        headers["Argus-Guest-Handoff-State"] = "cleared"
    access = cookies.get("sb-auth-token")
    refresh = cookies.get("sb-refresh-token")
    if (
        isinstance(payload, dict)
        and upstream.status_code >= 400
        and access
        and refresh
        and not access[1]
    ):
        payload["session"] = {"access_token": access[0], "refresh_token": refresh[0]}
    if payload is not None:
        body = json.dumps(payload).encode()
    return Response(body, status_code=upstream.status_code, headers=headers)


app = Starlette(
    routes=[
        Route("/{path:path}", proxy, methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
    ]
)
