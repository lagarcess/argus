"""Trusted client-IP resolution for visitor keys and edge rate limits.

Render sits behind Cloudflare. The first ``X-Forwarded-For`` hop is
client-controlled: Cloudflare and Render append to whatever the caller sent.
The single owner of client IP for keying and rate limits is the header
Cloudflare actually overwrites on the path to origin, configurable via
``ARGUS_TRUSTED_CLIENT_IP_HEADER`` and defaulting to ``CF-Connecting-IP``.
When that header is absent (local dev and tests), the socket peer is used.
``X-Forwarded-For`` is never consulted.
"""

from __future__ import annotations

import os

from fastapi import Request

DEFAULT_TRUSTED_CLIENT_IP_HEADER = "CF-Connecting-IP"
TRUSTED_CLIENT_IP_HEADER_ENV = "ARGUS_TRUSTED_CLIENT_IP_HEADER"


def trusted_client_ip_header_name() -> str:
    raw = os.getenv(TRUSTED_CLIENT_IP_HEADER_ENV, "").strip()
    return raw or DEFAULT_TRUSTED_CLIENT_IP_HEADER


def resolve_client_ip(request: Request) -> str:
    """The one client-IP read every visitor key and IP limiter must use."""
    raw = request.headers.get(trusted_client_ip_header_name())
    if raw:
        value = raw.split(",", 1)[0].strip()
        if value:
            return value
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
