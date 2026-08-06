#!/usr/bin/env python3
"""Probe that a requested private-alpha signup is denied before promotion."""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROBE = "requested_signup_denial"
REQUIRED_ENV = (
    "CANARY_REQUESTED_SIGNUP_DENIAL_API_URL",
    "CANARY_REQUESTED_SIGNUP_DENIAL_EMAIL",
    "CANARY_REQUESTED_SIGNUP_DENIAL_OPS_TOKEN",
)


def _required_environment() -> dict[str, str]:
    values = {name: os.environ.get(name, "").strip() for name in REQUIRED_ENV}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ValueError(f"missing required configuration: {', '.join(missing)}")
    return values


def _response_payload(body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _request_denial(values: dict[str, str]) -> tuple[int, dict[str, Any]]:
    request = Request(
        f"{values['CANARY_REQUESTED_SIGNUP_DENIAL_API_URL'].rstrip('/')}/internal/canary/requested-signup-denial",
        data=json.dumps(
            {
                "email": values["CANARY_REQUESTED_SIGNUP_DENIAL_EMAIL"],
            }
        ).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": (
                "Bearer "
                f"{values['CANARY_REQUESTED_SIGNUP_DENIAL_OPS_TOKEN']}"
            ),
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:  # noqa: S310 -- supplied canary URL
            return response.status, _response_payload(response.read())
    except HTTPError as error:
        return error.code, _response_payload(error.read())


def main() -> int:
    try:
        values = _required_environment()
    except ValueError as error:
        print(f"canary_probe={PROBE} result=configuration_error detail={error}")
        return 1

    for attempt in (1, 2):
        try:
            status, payload = _request_denial(values)
        except (OSError, URLError) as error:
            print(
                f"canary_probe={PROBE} attempt={attempt} "
                f"result=transport_error error_type={type(error).__name__}"
            )
            continue

        if status == 200 and payload.get("denied") is True:
            print(f"canary_probe={PROBE} attempt={attempt} result=passed")
            return 0
        print(
            f"canary_probe={PROBE} attempt={attempt} result=unexpected_response "
            f"status={status} denied={payload.get('denied')!r}"
        )

    print(f"canary_probe={PROBE} attempts=2 result=failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
