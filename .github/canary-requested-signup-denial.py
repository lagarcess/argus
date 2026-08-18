#!/usr/bin/env python3
"""Probe that the deployed API denies an explicitly disabled signup email."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from argus.api.ops_contract import REQUESTED_SIGNUP_DENIAL_PATH  # noqa: E402

PROBE = "disabled_signup_denial"
ATTEMPTS = 2
TIMEOUT_SECONDS = 20
EXPECTED_STATUS = 200
REQUIRED_ENV = (
    "CANARY_REQUESTED_SIGNUP_DENIAL_API_URL",
    "CANARY_REQUESTED_SIGNUP_DENIAL_EMAIL",
    "CANARY_REQUESTED_SIGNUP_DENIAL_OPS_TOKEN",
)


def _required_environment() -> dict[str, str]:
    values = {name: os.environ.get(name, "").strip() for name in REQUIRED_ENV}
    missing = sorted(name for name, value in values.items() if not value)
    if missing:
        raise ValueError(f"missing required configuration: {', '.join(missing)}")
    return values


def _response_payload(body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _policy_body(values: dict[str, str]) -> bytes:
    return json.dumps({"email": values["CANARY_REQUESTED_SIGNUP_DENIAL_EMAIL"]}).encode(
        "utf-8"
    )


def _request_denial(values: dict[str, str]) -> tuple[int, dict[str, Any]]:
    api_url = values["CANARY_REQUESTED_SIGNUP_DENIAL_API_URL"].rstrip("/")
    request = Request(
        f"{api_url}{REQUESTED_SIGNUP_DENIAL_PATH}",
        data=_policy_body(values),
        headers={
            "Authorization": (
                f"Bearer {values['CANARY_REQUESTED_SIGNUP_DENIAL_OPS_TOKEN']}"
            ),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            return response.status, _response_payload(response.read())
    except HTTPError as error:
        return error.code, _response_payload(error.read())


def main() -> int:
    try:
        values = _required_environment()
    except ValueError as error:
        print(f"canary_probe={PROBE} result=configuration_error detail={error}")
        return 1

    for attempt in range(1, ATTEMPTS + 1):
        try:
            status, payload = _request_denial(values)
        except OSError as error:
            print(
                f"canary_probe={PROBE} attempt={attempt} result=transport_error "
                f"error_type={type(error).__name__}"
            )
            continue

        denied = payload.get("denied")
        if status == EXPECTED_STATUS and denied is True:
            print(
                f"canary_probe={PROBE} attempt={attempt} result=passed "
                f"status={status} denied=true"
            )
            return 0
        # A reachable API that answers anything else is a real signal, so it is
        # reported once instead of being retried into ambiguity.
        print(
            f"canary_probe={PROBE} attempt={attempt} result=unexpected_response "
            f"status={status} denied={denied!r}"
        )
        return 1

    print(f"canary_probe={PROBE} attempts={ATTEMPTS} result=transport_failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
