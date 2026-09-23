"""Ordered statement identity plans, independent of which rows are retained."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

IDENTITY_VERSION = "ordered-v1"
Fingerprint = tuple[str, str, str, int, str]
Status = Literal["new", "possible", "exact"]


@dataclass(frozen=True)
class Identity:
    key: str
    fingerprint: Fingerprint
    source_id: str | None = None
    source_fingerprint: Fingerprint | None = None


@dataclass(frozen=True)
class Resolution:
    duplicate_status: Status
    duplicate_of: str | None
    match_snapshot: str
    action: Literal["import", "skip"] | None = None
    error: str | None = None


def resolve_sequence(
    candidates: list[Identity],
    existing: list[Identity],
    *,
    legacy: bool = False,
    frozen: list[Resolution] | None = None,
    decisions: dict[str, str] | None = None,
) -> list[Resolution]:
    """Reserve ancestry in file order; apply review choices without changing it.

    Persisted-match snapshots are separate from candidate ancestry. Only a real
    ledger change can invalidate a confirmation, never an earlier skip choice.
    """
    sources: dict[str, Identity] = {}
    first: dict[Fingerprint, Identity] = {}
    unknown: dict[Fingerprint, Identity] = {}
    persisted: dict[tuple[Fingerprint, bool], list[str]] = defaultdict(list)
    for identity in existing:
        first.setdefault(identity.fingerprint, identity)
        persisted[identity.fingerprint, False].append(identity.key)
        if identity.source_id:
            sources.setdefault(identity.source_id, identity)
        else:
            unknown.setdefault(identity.fingerprint, identity)
            persisted[identity.fingerprint, True].append(identity.key)
    snapshots = {
        key: hashlib.sha256(
            json.dumps(sorted(keys), separators=(",", ":")).encode()
        ).hexdigest()
        for key, keys in persisted.items()
    }
    empty_snapshot = hashlib.sha256(b"[]").hexdigest()
    results = []
    for index, candidate in enumerate(candidates):
        fingerprint, source_id = candidate.fingerprint, candidate.source_id
        exact = sources.get(source_id) if source_id else None
        error = None
        if exact and (exact.source_fingerprint or exact.fingerprint) != fingerprint:
            error = "source_transaction_changed"
        if legacy and exact is None:
            exact = first.get(fingerprint)
        possible = (unknown if source_id else first).get(fingerprint)
        ancestor = exact or possible
        status: Status = "exact" if exact else "possible" if possible else "new"
        snapshot = snapshots.get((fingerprint, bool(source_id)), empty_snapshot)
        action = None
        if frozen is not None:
            reviewed = frozen[index]
            # Exact descendants are permanently omitted, even if their first
            # occurrence was a possible duplicate that the user later skipped.
            if (
                reviewed.duplicate_status == "exact"
                or (decisions or {}).get(candidate.key) == "skip"
            ):
                action, error = "skip", None
            elif error is None and exact:
                action = "skip"
            elif error is None and not legacy and snapshot != reviewed.match_snapshot:
                error = "import_preview_changed"
            elif error is None:
                action = "import"
        results.append(
            Resolution(
                status, ancestor.key if ancestor else None, snapshot, action, error
            )
        )
        first.setdefault(fingerprint, candidate)
        if source_id:
            sources.setdefault(source_id, candidate)
        else:
            unknown.setdefault(fingerprint, candidate)
    return results
