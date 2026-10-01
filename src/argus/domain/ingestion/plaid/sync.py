"""``/transactions/sync`` for one connection, safe under retries and races.

Order that keeps evidence and the cursor truthful:

1. Refuse before touching the provider when there is no candidate sink.
2. Take the connection lease; a second webhook or a retried delivery for the
   same Item finds it held and returns ``busy``.
3. Page with ``has_more`` from the cursor the sync started with. On
   ``TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION`` restart the whole loop from
   that same starting cursor, as Plaid requires (bounded attempts).
4. Hand every page's candidates to the sink in one batch.
5. Only then advance the cursor with ``record_success`` (compare-and-set on the
   starting cursor). A sink failure or a lost race leaves the cursor alone, so
   the same changes are fetched again and the idempotent sink absorbs them.

Provider failures are recorded with an actionable code; ``last_success_at``
and the cursor are never cleared by a failure.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Literal

from loguru import logger

from argus.domain.ingestion.connections import ConnectionNotFound, SourceConnection
from argus.domain.ingestion.contract import AccountHint, ImportCandidate
from argus.domain.ingestion.hub import IngestionHub
from argus.domain.ingestion.plaid import mapping
from argus.domain.ingestion.plaid.client import PlaidClient, PlaidError
from argus.domain.ingestion.plaid.failures import MUTATION_DURING_PAGINATION, meaning

SyncStatus = Literal[
    "synced", "not_ready", "busy", "no_sink", "failed", "sink_failed", "superseded"
]
PAGE_SIZE = 500
MAX_PAGES = 40
MAX_RESTARTS = 3
LEASE_TTL = timedelta(minutes=10)
CREDENTIAL_UNAVAILABLE = "plaid_credential_unavailable"


@dataclass(frozen=True)
class SyncOutcome:
    status: SyncStatus
    added: int = 0
    modified: int = 0
    removed: int = 0
    pending: int = 0
    posted: int = 0
    replacing: int = 0
    skipped: int = 0
    pages: int = 0
    restarts: int = 0
    # Page cap reached: the cursor advanced to a valid mid-update position and
    # the next sync continues from there.
    more_pending: bool = False
    error_code: str | None = None


@dataclass
class _Pages:
    payloads: list[dict[str, Any]] = field(default_factory=list)
    cursor: str | None = None
    complete: bool = True
    restarts: int = 0


class PlaidSync:
    def __init__(
        self,
        hub: IngestionHub,
        client: PlaidClient,
        *,
        page_size: int = PAGE_SIZE,
        max_pages: int = MAX_PAGES,
        max_restarts: int = MAX_RESTARTS,
        holder: Callable[[], str] = lambda: uuid.uuid4().hex,
    ) -> None:
        self.hub = hub
        self.client = client
        self.page_size = max(1, min(page_size, PAGE_SIZE))
        self.max_pages = max_pages
        self.max_restarts = max_restarts
        self._holder = holder

    def sync(self, connection: SourceConnection) -> SyncOutcome:
        sink = self.hub.sink
        if sink is None:
            return SyncOutcome("no_sink")
        repo = self.hub.connections
        holder = self._holder()
        if not repo.lease(
            connection_id=connection.id,
            holder=holder,
            now=self.hub.clock(),
            ttl=LEASE_TTL,
        ):
            return SyncOutcome("busy")
        try:
            try:
                current = repo.get(
                    user_id=connection.user_id, connection_id=connection.id
                )
            except ConnectionNotFound:
                return SyncOutcome("busy")
            return self._run(current, holder, sink)
        finally:
            repo.release(connection_id=connection.id, holder=holder)

    def _run(self, current: SourceConnection, holder: str, sink) -> SyncOutcome:  # noqa: ANN001
        try:
            token = self.hub.credential(current)
        except Exception:
            token = None
        if not token:
            self._fail(current, CREDENTIAL_UNAVAILABLE, "error")
            return SyncOutcome("failed", error_code=CREDENTIAL_UNAVAILABLE)
        start = current.cursor
        try:
            pages = self._fetch(token, start)
        except PlaidError as exc:
            failure = meaning(exc.error_code)
            self._fail(current, failure.code, failure.status or current.status)
            return SyncOutcome("failed", error_code=failure.code)
        changes = sum(len(p.get(k) or ()) for p in pages.payloads for k in _LISTS)
        if not pages.cursor and changes == 0:
            # Plaid has not prepared transactions yet (empty next_cursor):
            # nothing was observed, so freshness is not claimed either.
            return SyncOutcome("not_ready", pages=len(pages.payloads))
        try:
            candidates, counts = self._candidates(current, token, pages)
        except PlaidError as exc:
            failure = meaning(exc.error_code)
            self._fail(current, failure.code, failure.status or current.status)
            return SyncOutcome("failed", error_code=failure.code)
        try:
            sink.submit(
                user_id=current.user_id,
                connection_id=current.id,
                candidates=candidates,
            )
        except Exception as exc:
            logger.warning(
                "Plaid sync could not hand candidates to the sink; cursor kept",
                failure_mode=type(exc).__name__,
            )
            return SyncOutcome("sink_failed", **counts)
        advanced = self.hub.connections.record_success(
            connection_id=current.id,
            holder=holder,
            expected_cursor=start,
            cursor=pages.cursor or start,
            now=self.hub.clock(),
        )
        return SyncOutcome(
            "synced" if advanced else "superseded",
            pages=len(pages.payloads),
            restarts=pages.restarts,
            more_pending=not pages.complete,
            **counts,
        )

    def _fetch(self, token: str, start: str | None) -> _Pages:
        restarts = 0
        while True:
            pages = _Pages(cursor=start, restarts=restarts)
            try:
                for _ in range(self.max_pages):
                    payload = self.client.transactions_sync(
                        access_token=token, cursor=pages.cursor, count=self.page_size
                    )
                    pages.payloads.append(payload)
                    next_cursor = payload.get("next_cursor")
                    pages.cursor = next_cursor if isinstance(next_cursor, str) else None
                    if not payload.get("has_more"):
                        return pages
                pages.complete = False
                return pages
            except PlaidError as exc:
                if (
                    exc.error_code != MUTATION_DURING_PAGINATION
                    or restarts >= self.max_restarts
                ):
                    raise
                restarts += 1

    def _candidates(
        self, current: SourceConnection, token: str, pages: _Pages
    ) -> tuple[list[ImportCandidate], dict[str, int]]:
        now = self.hub.clock()
        raw_accounts = [a for p in pages.payloads for a in p.get("accounts") or ()]
        hints = mapping.account_hints(raw_accounts, institution=current.label)
        rows = [r for p in pages.payloads for r in p.get("added") or ()]
        modified = [r for p in pages.payloads for r in p.get("modified") or ()]
        removed = [r for p in pages.payloads for r in p.get("removed") or ()]
        if any(r.get("account_id") not in hints for r in rows + modified):
            hints = _merge(
                hints,
                mapping.account_hints(
                    self.client.accounts_get(token), institution=current.label
                ),
            )
        counts = {"added": 0, "modified": 0, "removed": 0, "skipped": 0}
        counts.update(pending=0, posted=0, replacing=0)
        candidates: list[ImportCandidate] = []
        for label, group in (("added", rows), ("modified", modified)):
            for row in group:
                try:
                    candidate = mapping.transaction_candidate(
                        row, connection_id=current.id, accounts=hints, observed_at=now
                    )
                except ValueError as exc:
                    counts["skipped"] += 1
                    logger.warning(
                        "Skipped a Plaid row the contract refuses",
                        failure_mode=type(exc).__name__,
                    )
                    continue
                candidates.append(candidate)
                counts[label] += 1
                counts[candidate.status] += 1
                counts["replacing"] += candidate.source.replaces_external_id is not None
        for row in removed:
            try:
                candidates.append(
                    mapping.removed_candidate(
                        row, connection_id=current.id, observed_at=now
                    )
                )
                counts["removed"] += 1
            except ValueError:
                counts["skipped"] += 1
        return candidates, counts

    def _fail(self, current: SourceConnection, code: str, status) -> None:  # noqa: ANN001
        logger.warning("Plaid sync failed", failure_code=code, connection_status=status)
        try:
            self.hub.connections.record_failure(
                connection_id=current.id, code=code, status=status, now=self.hub.clock()
            )
        except ConnectionNotFound:
            pass


_LISTS = ("added", "modified", "removed")


def _merge(
    first: dict[str, AccountHint], second: dict[str, AccountHint]
) -> dict[str, AccountHint]:
    return {**second, **first}
