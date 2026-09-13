"""Load the previously committed public v1 snapshot into the LOCAL test DB.

It represents an already-existing historical row, not a new v1 creation path.
The payload is preserved byte-for-byte as canonical JSON.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[5]
PRIVATE = ROOT / "temp/share-answer-qa"
owner = json.loads((PRIVATE / "owner.json").read_text())
view = json.loads(
    (
        ROOT
        / "docs/reports/evidence/receipt-sharing/2026-09-03-end-to-end/public-receipt.json"
    ).read_text()
)
assert view["payload"]["schema_version"] == 1
canonical = json.dumps(
    view["payload"], sort_keys=True, separators=(",", ":"), ensure_ascii=False
)
dsn = str(
    dotenv_values(PRIVATE / "disposable-database.env")["ARGUS_DISPOSABLE_DATABASE_URL"]
)
assert urlparse(dsn).hostname == "127.0.0.1" and urlparse(dsn).port == 55432
with psycopg.connect(dsn) as connection:
    connection.execute(
        """insert into public.public_excerpt_snapshots
           (id, public_id, owner_id, title, payload, payload_digest, created_at)
           values (%s,%s,%s,%s,%s::jsonb,%s,%s)
           on conflict (public_id) do nothing""",
        (
            str(uuid.uuid4()),
            view["public_id"],
            owner["owner_id"],
            view["payload"]["idea_title"],
            canonical,
            hashlib.sha256(canonical.encode()).hexdigest(),
            view["created_at"],
        ),
    )
(PRIVATE / "v1.json").write_text(
    json.dumps(
        {
            "public_id": view["public_id"],
            "path": "/r/" + view["public_id"],
            "payload_digest": hashlib.sha256(canonical.encode()).hexdigest(),
        },
        indent=2,
    )
)
print("Historical version 1 snapshot loaded into local receipt table unchanged.")
