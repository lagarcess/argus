"""Owner-side service for public evidence receipts.

Creation is the only place private records are read. It loads the owner's
artifact and the immutable run behind it, freezes a sanitized payload, and stores
it. Everything after that reads the snapshot and nothing else.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Protocol

from starlette.exceptions import HTTPException as StarletteHTTPException

from argus.api import state as api_state
from argus.api.public_excerpt_schemas import (
    PublicExcerptSnapshot,
    PublicExcerptView,
)
from argus.api.schemas import EvidenceArtifact, User
from argus.domain.public_excerpts import (
    PublicExcerptSourceError,
    build_public_excerpt_payload,
    new_public_excerpt_id,
    payload_digest,
    revoked_public_view,
    snapshot_public_view,
)

_TRUE_VALUES = {"1", "true", "yes", "on"}

RECEIPT_CREATE_LIMIT = 10
RECEIPT_CREATE_WINDOW_SECONDS = 3600
RECEIPT_CREATE_DAILY_LIMIT = 30
RECEIPT_CREATE_DAILY_WINDOW_SECONDS = 86_400


class EvidenceReceiptDisabledError(RuntimeError):
    """Sharing is behind a default-off flag and this deployment has it off."""


class EvidenceReceiptSourceMissingError(LookupError):
    """The artifact is absent, not owned, or not a shareable result."""


def evidence_receipt_sharing_enabled() -> bool:
    """Default off. Landing this lane does not turn sharing on."""
    raw_value = os.getenv("ARGUS_EVIDENCE_RECEIPT_SHARING_ENABLED", "")
    return raw_value.strip().lower() in _TRUE_VALUES


def require_evidence_receipt_sharing_enabled() -> None:
    """While sharing is off, these paths answer exactly as if they did not exist.

    Raising Starlette's base ``HTTPException`` rather than Argus's problem helper
    is deliberate: it is the same exception an unmatched route raises, so the
    response body is produced by the same handler and is byte-identical to a
    deployment without this lane. A distinctive problem body would advertise that
    receipt code is deployed.
    """
    if evidence_receipt_sharing_enabled():
        return
    raise StarletteHTTPException(status_code=404, detail="Not Found")


class PublicExcerptReader(Protocol):
    """The entire surface the unauthenticated public route may call."""

    def read_public_excerpt_view(self, *, public_id: str) -> PublicExcerptView: ...


class MemoryPublicExcerptRepository:
    """In-process parity for dev and test runs, same contract as the gateway."""

    def __init__(self, store: Any) -> None:
        self._store = store

    def create_public_excerpt_snapshot(
        self, *, snapshot: PublicExcerptSnapshot
    ) -> PublicExcerptSnapshot:
        existing = self.get_live_public_excerpt_for_artifact(
            owner_id=snapshot.owner_id,
            evidence_artifact_id=snapshot.evidence_artifact_id,
        )
        if existing is not None:
            return existing
        self._store.public_excerpt_snapshots[snapshot.id] = snapshot
        return snapshot

    def get_live_public_excerpt_for_artifact(
        self, *, owner_id: str, evidence_artifact_id: str | None
    ) -> PublicExcerptSnapshot | None:
        if evidence_artifact_id is None:
            return None
        for snapshot in self._store.public_excerpt_snapshots.values():
            if (
                snapshot.owner_id == owner_id
                and snapshot.evidence_artifact_id == evidence_artifact_id
                and snapshot.revoked_at is None
            ):
                return snapshot
        return None

    def list_public_excerpt_snapshots(
        self, *, owner_id: str
    ) -> list[PublicExcerptSnapshot]:
        owned = [
            snapshot
            for snapshot in self._store.public_excerpt_snapshots.values()
            if snapshot.owner_id == owner_id
        ]
        return sorted(owned, key=lambda snapshot: snapshot.created_at, reverse=True)

    def get_owned_public_excerpt_snapshot(
        self, *, owner_id: str, snapshot_id: str
    ) -> PublicExcerptSnapshot | None:
        snapshot = self._store.public_excerpt_snapshots.get(snapshot_id)
        if snapshot is None or snapshot.owner_id != owner_id:
            return None
        return snapshot

    def revoke_public_excerpt_snapshot(
        self,
        *,
        owner_id: str,
        snapshot_id: str,
        reason: str = "owner_revoked",
    ) -> PublicExcerptSnapshot | None:
        snapshot = self.get_owned_public_excerpt_snapshot(
            owner_id=owner_id,
            snapshot_id=snapshot_id,
        )
        if snapshot is None or snapshot.revoked_at is not None:
            return snapshot
        return self._revoke(snapshot, reason=reason)

    def revoke_public_excerpts_for_conversation(
        self, *, owner_id: str, conversation_id: str
    ) -> int:
        revoked = 0
        for snapshot in list(self._store.public_excerpt_snapshots.values()):
            if (
                snapshot.owner_id == owner_id
                and snapshot.source_conversation_id == conversation_id
                and snapshot.revoked_at is None
            ):
                self._revoke(snapshot, reason="source_deleted")
                revoked += 1
        return revoked

    def revoke_all_public_excerpts(self, *, owner_id: str) -> int:
        revoked = 0
        for snapshot in list(self._store.public_excerpt_snapshots.values()):
            if snapshot.owner_id == owner_id and snapshot.revoked_at is None:
                self._revoke(snapshot, reason="source_deleted")
                revoked += 1
        return revoked

    def read_public_excerpt_view(self, *, public_id: str) -> PublicExcerptView:
        for snapshot in self._store.public_excerpt_snapshots.values():
            if snapshot.public_id == public_id:
                return snapshot_public_view(snapshot)
        return revoked_public_view(public_id)

    def _revoke(
        self, snapshot: PublicExcerptSnapshot, *, reason: str
    ) -> PublicExcerptSnapshot:
        revoked = snapshot.model_copy(
            update={
                "revoked_at": datetime.now(timezone.utc),
                "revocation_reason": reason,
            }
        )
        self._store.public_excerpt_snapshots[snapshot.id] = revoked
        return revoked


def public_excerpt_repository() -> Any:
    if api_state.supabase_gateway is not None:
        return api_state.supabase_gateway
    return MemoryPublicExcerptRepository(api_state.store)


def public_excerpt_reader() -> PublicExcerptReader:
    """Resolve the narrow reader the public route is allowed to hold."""
    return public_excerpt_repository()


def create_receipt_for_artifact(
    *,
    user: User,
    artifact_id: str,
    owner_note: str | None,
) -> PublicExcerptSnapshot:
    """Freeze a receipt from an owned result. Reads private records exactly once."""
    artifact = _owned_artifact(user_id=user.id, artifact_id=artifact_id)
    repository = public_excerpt_repository()
    existing = repository.get_live_public_excerpt_for_artifact(
        owner_id=user.id,
        evidence_artifact_id=artifact.id,
    )
    if existing is not None:
        return existing
    payload = build_public_excerpt_payload(
        artifact=artifact,
        run_chart=_run_chart(user_id=user.id, run_id=artifact.source_run_id),
        owner_note=owner_note,
        content_language=user.language,
    )
    snapshot = PublicExcerptSnapshot(
        id=api_state.store.new_id(),
        public_id=new_public_excerpt_id(),
        owner_id=user.id,
        evidence_artifact_id=artifact.id,
        source_conversation_id=artifact.source_conversation_id,
        source_run_id=artifact.source_run_id,
        title=payload.idea_title,
        payload=payload,
        payload_digest=payload_digest(payload),
        created_at=datetime.now(timezone.utc),
    )
    return repository.create_public_excerpt_snapshot(snapshot=snapshot)


def revoke_receipts_for_conversation(*, user_id: str, conversation_id: str) -> int:
    """Deleting a conversation revokes the receipts it produced."""
    return public_excerpt_repository().revoke_public_excerpts_for_conversation(
        owner_id=user_id,
        conversation_id=conversation_id,
    )


def revoke_all_receipts(*, user_id: str) -> int:
    return public_excerpt_repository().revoke_all_public_excerpts(owner_id=user_id)


def _owned_artifact(*, user_id: str, artifact_id: str) -> EvidenceArtifact:
    if api_state.supabase_gateway is not None:
        artifact = api_state.supabase_gateway.get_evidence_artifact(
            user_id=user_id,
            artifact_id=artifact_id,
        )
    else:
        artifact = api_state.store.evidence_artifacts.get(artifact_id)
        if artifact is not None and (
            api_state.store.evidence_artifact_owners.get(artifact_id) != user_id
        ):
            artifact = None
    if artifact is None:
        raise EvidenceReceiptSourceMissingError("That result is not available.")
    if artifact.artifact_type != "backtest":
        raise PublicExcerptSourceError(
            "Only completed backtest results are shareable."
        )
    return artifact


def _run_chart(*, user_id: str, run_id: str | None) -> dict[str, Any] | None:
    """Read the run's frozen chart. The public view never repeats this read."""
    if run_id is None:
        return None
    if api_state.supabase_gateway is not None:
        run = api_state.supabase_gateway.get_backtest_run(
            user_id=user_id,
            run_id=run_id,
        )
        return run.chart if run is not None else None
    run = api_state.store.backtest_runs.get(run_id)
    if run is None:
        return None
    if api_state.store.backtest_run_owners.get(run_id) != user_id:
        return None
    chart = getattr(run, "chart", None)
    return chart if isinstance(chart, dict) else None
