"""Create one registered disposable LOCAL owner; retain secrets only in temp/."""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[5]
PRIVATE = ROOT / "temp/share-answer-qa"
OUTPUT = PRIVATE / "owner.json"
assert not OUTPUT.exists(), "Reuse the existing local owner rather than minting another."
local = dotenv_values(PRIVATE / "supabase-local.env")
origin = str(local["API_URL"])
assert urlparse(origin).hostname == "127.0.0.1"
assert urlparse(origin).port == 55431
key = str(local["SERVICE_ROLE_KEY"])
headers = {"apikey": key, "Authorization": f"Bearer {key}"}
email = f"share-answer-{secrets.token_hex(8)}@example.test"
password = f"Qa!{secrets.token_urlsafe(30)}"

with httpx.Client(base_url=origin, headers=headers, timeout=30) as client:
    response = client.post(
        "/auth/v1/admin/users",
        json={
            "email": email,
            "password": password,
            "email_confirm": True,
        },
    )
    response.raise_for_status()
    owner_id = response.json()["id"]
    for table, row in [
        (
            "profiles",
            {
                "id": owner_id,
                "email": email,
                "display_name": "Local QA",
                "language": "en",
            },
        ),
        ("private_alpha_allowlist", {"email": email}),
    ]:
        response = client.post(
            f"/rest/v1/{table}",
            json=row,
            headers={
                "Prefer": "resolution=merge-duplicates",
            },
        )
        response.raise_for_status()
    response = client.post(
        "/auth/v1/token?grant_type=password",
        json={
            "email": email,
            "password": password,
        },
    )
    response.raise_for_status()
    session = response.json()

OUTPUT.write_text(
    json.dumps(
        {
            "email": email,
            "password": password,
            "owner_id": owner_id,
            "session": session,
        },
        indent=2,
    )
)
OUTPUT.chmod(0o600)
print("Created one disposable registered local owner; private state is ignored.")
