from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx


@dataclass(frozen=True)
class LoadIdentity:
    label: str
    email: str


class IdentityHarnessConfig(Protocol):
    api_url: str
    timeout_seconds: float
    identities: tuple[LoadIdentity, ...]


def create_temporary_identities(
    *,
    config: IdentityHarnessConfig,
    client: httpx.Client,
    user_ids: list[str],
    source: str,
) -> None:
    for identity in config.identities:
        existing = client.get(
            "/rest/v1/private_alpha_allowlist",
            params={"select": "email", "email": f"eq.{identity.email}", "limit": "1"},
        )
        existing.raise_for_status()
        if existing.json():
            raise RuntimeError("dedicated load identity is not temporary and unused")
    for identity in config.identities:
        response = client.post(
            "/auth/v1/admin/users",
            json={
                "email": identity.email,
                "email_confirm": True,
                "user_metadata": {"source": source},
            },
        )
        response.raise_for_status()
        body = response.json()
        user_id = str(body.get("id") or "").strip()
        if not user_id:
            raise RuntimeError("temporary identity creation returned no user")
        user_ids.append(user_id)
        allowlist = client.post(
            "/rest/v1/private_alpha_allowlist",
            headers={"Prefer": "return=minimal"},
            json={"email": identity.email, "role": "user"},
        )
        allowlist.raise_for_status()


def create_service_role_session_client(
    config: IdentityHarnessConfig,
    service_client: httpx.Client,
    identity: LoadIdentity,
) -> httpx.Client:
    link_response = service_client.post(
        "/auth/v1/admin/generate_link",
        json={"type": "magiclink", "email": identity.email},
    )
    link_response.raise_for_status()
    link_body = link_response.json()
    properties = link_body.get("properties")
    if not isinstance(properties, dict):
        raise RuntimeError("temporary identity link response lacked properties")
    hashed_token = str(properties.get("hashed_token") or "").strip()
    verification_type = str(properties.get("verification_type") or "").strip()
    if not hashed_token or not verification_type:
        raise RuntimeError("temporary identity link response lacked verification data")

    verify_response = service_client.post(
        "/auth/v1/verify",
        json={"token_hash": hashed_token, "type": verification_type},
    )
    verify_response.raise_for_status()
    verify_body = verify_response.json()
    access_token = str(verify_body.get("access_token") or "").strip()
    if not access_token:
        raise RuntimeError("temporary identity verification returned no session")

    return httpx.Client(
        base_url=config.api_url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=config.timeout_seconds,
        follow_redirects=True,
    )


def cleanup_temporary_identities(
    *,
    config: IdentityHarnessConfig,
    client: httpx.Client,
    user_ids: list[str],
) -> dict[str, Any]:
    auth_deleted = 0
    auth_already_absent = 0
    auth_failed = 0
    for user_id in user_ids:
        try:
            response = client.delete(f"/auth/v1/admin/users/{user_id}")
            if response.status_code == 404:
                auth_already_absent += 1
            elif 200 <= response.status_code < 300:
                auth_deleted += 1
            else:
                auth_failed += 1
        except Exception:
            auth_failed += 1

    allowlist_completed = 0
    allowlist_failed = 0
    for identity in config.identities:
        try:
            response = client.delete(
                "/rest/v1/private_alpha_allowlist",
                params={"email": f"eq.{identity.email}"},
            )
            if 200 <= response.status_code < 300 or response.status_code == 404:
                allowlist_completed += 1
            else:
                allowlist_failed += 1
        except Exception:
            allowlist_failed += 1

    status = (
        "completed"
        if auth_failed == 0 and allowlist_failed == 0
        else "incomplete"
    )
    return {
        "status": status,
        "auth": {
            "targets": len(user_ids),
            "deleted": auth_deleted,
            "already_absent": auth_already_absent,
            "failed": auth_failed,
        },
        "allowlist": {
            "targets": len(config.identities),
            "completed": allowlist_completed,
            "failed": allowlist_failed,
        },
    }
