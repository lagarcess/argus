"""Supabase persistence for public evidence receipts.

The public read is deliberately the narrowest query in the gateway: it selects a
fixed column list from one table, filtered by ``public_id`` alone. There is no
join, no owner lookup, and no path from here to a conversation, a message, a run
or a memory record. ``PUBLIC_VIEW_COLUMNS`` is asserted by test, so widening it
is a visible change.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from argus.api.public_excerpt_schemas import (
    PublicExcerptPayload,
    PublicExcerptSnapshot,
    PublicExcerptView,
)
from argus.domain.public_excerpts import revoked_public_view

TABLE = "public_excerpt_snapshots"

# What an unauthenticated viewer's request is allowed to read. Owner id and every
# source id are absent by construction, not by filtering after the fact.
PUBLIC_VIEW_COLUMNS = ("public_id", "payload", "created_at", "revoked_at")

OWNER_COLUMNS = (
    "id",
    "public_id",
    "owner_id",
    "evidence_artifact_id",
    "source_conversation_id",
    "source_run_id",
    "title",
    "payload",
    "payload_digest",
    "created_at",
    "revoked_at",
    "revocation_reason",
)

DEFAULT_OWNER_PAGE_SIZE = 50
MAX_OWNER_PAGE_SIZE = 200


class PublicExcerptConflictError(RuntimeError):
    """A live receipt already exists for this result."""


def _rows(result: Any) -> list[dict[str, Any]]:
    data = getattr(result, "data", None)
    if not data:
        return []
    if isinstance(data, list):
        return [dict(row) for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        return [dict(data)]
    return []


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SupabasePublicExcerptMixin:
    """Service-role reads and writes for receipts, split by audience."""

    client: Any

    def create_public_excerpt_snapshot(
        self, *, snapshot: PublicExcerptSnapshot
    ) -> tuple[PublicExcerptSnapshot, bool]:
        """Insert a receipt, or return the live one that already covers the result.

        Returns ``(snapshot, created)``. Callers need the flag because sharing the
        same result twice is deliberately idempotent, and counting the second call
        as a creation would inflate the acquisition funnel.
        """
        existing = self.get_live_public_excerpt_for_artifact(
            owner_id=snapshot.owner_id,
            evidence_artifact_id=snapshot.evidence_artifact_id,
        )
        if existing is not None:
            return existing, False
        payload = snapshot.model_dump(mode="json")
        try:
            created = self.client.table(TABLE).insert(payload).execute()
        except Exception:
            # Two concurrent creates can both pass the lookup above; the partial
            # unique index lets one in and rejects the other. The loser reads the
            # winner's row rather than surfacing a 500, because the contract says
            # re-sharing a result returns its existing link.
            raced = self.get_live_public_excerpt_for_artifact(
                owner_id=snapshot.owner_id,
                evidence_artifact_id=snapshot.evidence_artifact_id,
            )
            if raced is not None:
                return raced, False
            raise
        rows = _rows(created)
        if not rows:
            raise PublicExcerptConflictError("The receipt was not recorded.")
        return _snapshot_from_row(rows[0]), True

    def get_live_public_excerpt_for_artifact(
        self, *, owner_id: str, evidence_artifact_id: str | None
    ) -> PublicExcerptSnapshot | None:
        if evidence_artifact_id is None:
            return None
        result = (
            self.client.table(TABLE)
            .select(",".join(OWNER_COLUMNS))
            .eq("owner_id", owner_id)
            .eq("evidence_artifact_id", evidence_artifact_id)
            .is_("revoked_at", "null")
            .limit(1)
            .execute()
        )
        rows = _rows(result)
        return _snapshot_from_row(rows[0]) if rows else None

    def list_public_excerpt_snapshots(
        self,
        *,
        owner_id: str,
        limit: int = DEFAULT_OWNER_PAGE_SIZE,
        before: tuple[str, str] | None = None,
    ) -> list[PublicExcerptSnapshot]:
        """One page of the owner's receipts, newest first.

        Paginated rather than capped. A silent cap would hide older live links from
        Data Controls, and Data Controls is the only place an owner can find a
        snapshot id to revoke, so a hidden row is an unrevocable public page.
        """
        query = (
            self.client.table(TABLE)
            .select(",".join(OWNER_COLUMNS))
            .eq("owner_id", owner_id)
        )
        if before is not None:
            created_at, snapshot_id = before
            # Keyset on (created_at, id) so identical timestamps cannot drop or
            # repeat a row across pages.
            query = query.or_(
                f"created_at.lt.{created_at},"
                f"and(created_at.eq.{created_at},id.lt.{snapshot_id})"
            )
        result = (
            query.order("created_at", desc=True)
            .order("id", desc=True)
            .limit(limit)
            .execute()
        )
        return [_snapshot_from_row(row) for row in _rows(result)]

    def get_owned_public_excerpt_snapshot(
        self, *, owner_id: str, snapshot_id: str
    ) -> PublicExcerptSnapshot | None:
        result = (
            self.client.table(TABLE)
            .select(",".join(OWNER_COLUMNS))
            .eq("owner_id", owner_id)
            .eq("id", snapshot_id)
            .limit(1)
            .execute()
        )
        rows = _rows(result)
        return _snapshot_from_row(rows[0]) if rows else None

    def revoke_public_excerpt_snapshot(
        self,
        *,
        owner_id: str,
        snapshot_id: str,
        reason: str = "owner_revoked",
    ) -> PublicExcerptSnapshot | None:
        result = (
            self.client.table(TABLE)
            .update({"revoked_at": _now_iso(), "revocation_reason": reason})
            .eq("owner_id", owner_id)
            .eq("id", snapshot_id)
            .is_("revoked_at", "null")
            .execute()
        )
        rows = _rows(result)
        if rows:
            return _snapshot_from_row(rows[0])
        # Already revoked is the same outcome the caller asked for.
        return self.get_owned_public_excerpt_snapshot(
            owner_id=owner_id,
            snapshot_id=snapshot_id,
        )

    def revoke_public_excerpts_for_conversation(
        self, *, owner_id: str, conversation_id: str
    ) -> int:
        result = (
            self.client.table(TABLE)
            .update(
                {"revoked_at": _now_iso(), "revocation_reason": "source_deleted"}
            )
            .eq("owner_id", owner_id)
            .eq("source_conversation_id", conversation_id)
            .is_("revoked_at", "null")
            .execute()
        )
        return len(_rows(result))

    def revoke_all_public_excerpts(self, *, owner_id: str) -> int:
        result = (
            self.client.table(TABLE)
            .update(
                {"revoked_at": _now_iso(), "revocation_reason": "source_deleted"}
            )
            .eq("owner_id", owner_id)
            .is_("revoked_at", "null")
            .execute()
        )
        return len(_rows(result))

    def read_public_excerpt_view(self, *, public_id: str) -> PublicExcerptView:
        """The only read an unauthenticated viewer can cause. One table, one row."""
        result = (
            self.client.table(TABLE)
            .select(",".join(PUBLIC_VIEW_COLUMNS))
            .eq("public_id", public_id)
            .limit(1)
            .execute()
        )
        rows = _rows(result)
        if not rows:
            return revoked_public_view(public_id)
        return _public_view_from_row(public_id, rows[0])


def _snapshot_from_row(row: dict[str, Any]) -> PublicExcerptSnapshot:
    return PublicExcerptSnapshot.model_validate(row)


def _public_view_from_row(public_id: str, row: dict[str, Any]) -> PublicExcerptView:
    if row.get("revoked_at") is not None:
        return revoked_public_view(public_id)
    return PublicExcerptView(
        public_id=public_id,
        status="available",
        created_at=row.get("created_at"),
        payload=PublicExcerptPayload.model_validate(row.get("payload") or {}),
    )
