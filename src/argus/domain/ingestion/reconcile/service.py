"""Reconciliation service: the connectors' sink and the person's review queue.

Recording reviewed imports (the only canonical write) lives in ``recording``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from argus.domain.ingestion.contract import ImportCandidate
from argus.domain.ingestion.reconcile import intake
from argus.domain.ingestion.reconcile.matching import (
    ACTIVITY_EVIDENCE,
    account_key,
    activity_matches,
    compare,
    event_facts,
    primary,
)
from argus.domain.ingestion.reconcile.model import (
    RESOLVABLE,
    AccountLink,
    EventNotFound,
    ImportEvent,
    ReconcileError,
    StaleEvent,
)
from argus.domain.ingestion.reconcile.recording import Recording
from argus.domain.ingestion.reconcile.render import event_view, proposed_kind, unresolved
from argus.domain.ingestion.reconcile.store import ImportStore, ImportTx
from argus.domain.ingestion.sink import SubmitResult
from argus.domain.recording.money_reads import current_activities
from argus.domain.recording.money_service import MoneyService


class ReconciliationService(Recording):
    def __init__(
        self, store: ImportStore, money: MoneyService, clock: Callable[[], datetime]
    ) -> None:
        self.store = store
        self.money = money
        self.clock = clock

    # --- CandidateSink -------------------------------------------------
    def submit(
        self, *, user_id: str, connection_id: str, candidates: Sequence[ImportCandidate]
    ) -> SubmitResult:
        return intake.submit(
            self.store,
            self.clock(),
            user_id=user_id,
            connection_id=connection_id,
            candidates=candidates,
        )

    def forget_connection(self, *, user_id: str, connection_id: str) -> int:
        return intake.forget(
            self.store, self.clock(), user_id=user_id, connection_id=connection_id
        )

    # --- Review --------------------------------------------------------
    def list(self, *, user_id: str, states: tuple[str, ...]) -> list[dict[str, Any]]:
        accounts = self.money.accounts.list_accounts(user_id=user_id)
        with self.store.transaction(user_id) as tx:
            return [self._view(tx, e, accounts) for e in tx.events(states)]

    def detail(self, *, user_id: str, event_id: str) -> dict[str, Any]:
        accounts = self.money.accounts.list_accounts(user_id=user_id)
        with self.store.transaction(user_id) as tx:
            return self._view(tx, tx.event(event_id), accounts)

    def resolve(
        self, *, user_id: str, event_id: str, version: int, changes: dict[str, Any]
    ) -> dict[str, Any]:
        unknown = set(changes) - RESOLVABLE
        if unknown:
            raise ReconcileError("field_not_resolvable", ", ".join(sorted(unknown)))
        cleaned = _clean_resolution(changes)
        owned = {s.account.id for s in self.money.accounts.list_accounts(user_id=user_id)}
        for field in ("account_id", "destination_account_id"):
            if cleaned.get(field) and cleaned[field] not in owned:
                raise ReconcileError(
                    "financial_account_not_found", "Choose your own account."
                )
        now = self.clock()
        with self.store.transaction(user_id) as tx:
            event = self._editable(tx, event_id, version)
            resolution = {**event.resolution, **cleaned}
            resolution = {k: v for k, v in resolution.items() if v is not None}
            event = replace(event, resolution=resolution)
            if cleaned.get("account_id"):
                self._remember_account(tx, event, cleaned["account_id"], now)
            event = self._recheck_duplicates(tx, event)
            tx.put_event(_bump(event, now))
        return self.detail(user_id=user_id, event_id=event_id)

    def merge(
        self, *, user_id: str, event_id: str, into_event_id: str, version: int
    ) -> dict[str, Any]:
        """The person says two events are the same purchase."""

        if event_id == into_event_id:
            raise ReconcileError("import_merge_self", "Choose a different import.")
        now = self.clock()
        with self.store.transaction(user_id) as tx:
            source = tx.event(event_id)
            if source.version != version:
                raise StaleEvent()
            target = tx.event(into_event_id)
            if "accepting" in (source.state, target.state):
                raise ReconcileError("import_accept_in_progress", "Try again shortly.")
            if source.state == target.state == "accepted":
                raise ReconcileError(
                    "import_merge_two_records",
                    "Both are already recorded; correct or remove one of the records.",
                )
            survivor, absorbed = (
                (source, target) if source.state == "accepted" else (target, source)
            )
            moving = tx.observations(absorbed.id)
            staying = tx.observations(survivor.id)
            live_sources = {o.source for o in staying if o.live}
            if any(o.live and o.source in live_sources for o in moving):
                raise ReconcileError(
                    "import_merge_same_source",
                    "One source reported both; they are separate purchases.",
                )
            for observation in moving:
                tx.put_observation(replace(observation, event_id=survivor.id))
            tx.delete_event(absorbed.id)
            anchors = [d for d in (survivor.anchor_on, absorbed.anchor_on) if d]
            survivor = replace(
                survivor,
                anchor_on=min(anchors) if anchors else None,
                resolution={**absorbed.resolution, **survivor.resolution},
                possible_duplicates=tuple(
                    d
                    for d in survivor.possible_duplicates
                    if d not in (absorbed.id, survivor.id)
                ),
            )
            if survivor.attention in ("possible_duplicate", "ambiguous_match"):
                if not survivor.possible_duplicates:
                    survivor = replace(survivor, attention=None)
            tx.put_event(_bump(survivor, now))
            survivor_id = survivor.id
        return self.detail(user_id=user_id, event_id=survivor_id)

    def dismiss(self, *, user_id: str, event_id: str, version: int) -> dict[str, Any]:
        now = self.clock()
        with self.store.transaction(user_id) as tx:
            event = self._editable(tx, event_id, version)
            tx.put_event(_bump(replace(event, state="dismissed"), now))
        return self.detail(user_id=user_id, event_id=event_id)

    def reopen(self, *, user_id: str, event_id: str, version: int) -> dict[str, Any]:
        now = self.clock()
        with self.store.transaction(user_id) as tx:
            event = tx.event(event_id)
            if event.version != version:
                raise StaleEvent()
            if event.state != "dismissed":
                raise ReconcileError(
                    "import_not_dismissed", "Only dismissed imports reopen."
                )
            if not any(o.live for o in tx.observations(event_id)):
                raise ReconcileError("import_source_removed", "The source withdrew this.")
            tx.put_event(_bump(replace(event, state="open", attention_detail=None), now))
        return self.detail(user_id=user_id, event_id=event_id)

    def acknowledge(self, *, user_id: str, event_id: str, version: int) -> dict[str, Any]:
        """Clear a source-changed warning after the person checked the record."""

        now = self.clock()
        with self.store.transaction(user_id) as tx:
            event = tx.event(event_id)
            if event.version != version:
                raise StaleEvent()
            tx.put_event(
                _bump(replace(event, attention=None, attention_detail=None), now)
            )
        return self.detail(user_id=user_id, event_id=event_id)

    # --- Internals -----------------------------------------------------
    def _view(self, tx: ImportTx, event: ImportEvent, accounts: list) -> dict[str, Any]:
        observations = tx.observations(event.id)
        facts = event_facts(event, observations, tx.links())
        matches: list[str] = []
        if event.state == "open" and event.evidence in ACTIVITY_EVIDENCE:
            linked = tx.linked_activity_ids()
            matches = [
                a
                for a in activity_matches(facts, current_activities(accounts))
                if a not in linked
            ]
        shared = tx.account_shared(facts.account_id) if facts.account_id else None
        return event_view(
            event,
            observations,
            facts,
            existing_activity_matches=matches,
            account_shared=shared,
        )

    def _editable(self, tx: ImportTx, event_id: str, version: int) -> ImportEvent:
        event = tx.event(event_id)
        if event.version != version:
            raise StaleEvent()
        if event.state != "open":
            raise ReconcileError(
                "import_not_open", "This import is not waiting for review."
            )
        return event

    def _remember_account(
        self, tx: ImportTx, event: ImportEvent, account_id: str, now: datetime
    ) -> None:
        """Each confirmed mapping is reused for that source's later imports."""

        first = primary(tx.observations(event.id))
        if first is None:
            return
        key = account_key(first.candidate)
        if key is None:
            return
        tx.put_link(
            AccountLink(
                user_id=event.user_id,
                connection_id=first.connection_id,
                account_key=key,
                account_id=account_id,
                created_at=now,
            )
        )

    def _recheck_duplicates(self, tx: ImportTx, event: ImportEvent) -> ImportEvent:
        """After a person supplies facts (an unclassified email), point at
        events that may be the same purchase; never merge on their behalf."""

        observations = tx.observations(event.id)
        facts = event_facts(event, observations, tx.links())
        sources = {o.source for o in observations if o.live}
        found = []
        for other, others, other_facts in intake.nearby_facts(tx, facts):
            if other.id == event.id or other.state == "dismissed":
                continue
            if sources & {o.source for o in others if o.live}:
                continue
            if compare(facts, other_facts) is not None:
                found.append(other.id)
        if found:
            return replace(
                event,
                possible_duplicates=tuple(sorted(found)),
                attention="possible_duplicate",
            )
        if event.attention in ("possible_duplicate", "ambiguous_match"):
            return replace(event, possible_duplicates=(), attention=None)
        return event


def _clean_resolution(changes: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(changes)
    if cleaned.get("amount") is not None:
        try:
            number = Decimal(str(cleaned["amount"]))
        except InvalidOperation:
            raise ReconcileError("amount_invalid", "Enter a plain amount.") from None
        if not number.is_finite() or number <= 0:
            raise ReconcileError("amount_positive_required", "Enter a positive amount.")
        cleaned["amount"] = format(number.normalize(), "f")
    if cleaned.get("currency") is not None:
        code = str(cleaned["currency"]).strip().upper()
        if len(code) != 3 or not code.isalpha():
            raise ReconcileError("currency_invalid", "Use a three-letter currency code.")
        cleaned["currency"] = code
    if cleaned.get("occurred_on") is not None:
        try:
            cleaned["occurred_on"] = date.fromisoformat(
                str(cleaned["occurred_on"])
            ).isoformat()
        except ValueError:
            raise ReconcileError("date_invalid", "Use YYYY-MM-DD.") from None
    if cleaned.get("direction") not in (None, "outflow", "inflow"):
        raise ReconcileError("direction_invalid", "Use outflow or inflow.")
    if cleaned.get("note") is not None:
        cleaned["note"] = str(cleaned["note"])[:200]
    return cleaned


def _bump(event: ImportEvent, now: datetime) -> ImportEvent:
    return replace(event, updated_at=now, version=event.version + 1)


__all__ = ["EventNotFound", "ReconciliationService", "proposed_kind", "unresolved"]
