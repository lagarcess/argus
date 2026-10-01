"""Recording reviewed imports: preview, accept, reviewed batches, linking.

Canonical writes happen in exactly one place, ``accept``, through
``MoneyService.write`` with an idempotency key derived from the event. An
event is claimed before the write, so two concurrent accepts with different
keys cannot record the same purchase twice; a retry with the same key replays.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from argus.domain.ingestion.reconcile.matching import ACTIVITY_EVIDENCE
from argus.domain.ingestion.reconcile.model import (
    EventNotFound,
    ReconcileError,
    StaleEvent,
)
from argus.domain.recording.errors import IdempotencyConflict
from argus.domain.recording.money_schemas import MoneyRequest

DEFAULT_ZONE = "America/Santo_Domingo"
_PAIRED = {"transfer", "card_payment", "debt_payment"}
MAX_CLIENT_KEY = 80
MAX_BATCH_KEY = 40
MAX_BATCH = 100


class Recording:
    """Mixed into ``ReconciliationService``; uses its ``store``, ``money``,
    ``clock``, ``detail`` and ``_remember_account``."""

    def preview(
        self, *, user_id: str, event_id: str, overrides: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        detail = self.detail(user_id=user_id, event_id=event_id)
        if detail["state"] not in ("open", "accepting"):
            raise ReconcileError(
                "import_not_open", "This import is not waiting for review."
            )
        if detail["evidence"] not in ACTIVITY_EVIDENCE:
            raise ReconcileError(
                "import_not_activity", "This is information, not money that moved."
            )
        request = MoneyRequest.model_validate(
            {**self._draft(user_id, detail), **(overrides or {})}
        )
        return {
            "event": detail,
            "preview": self.money.preview(user_id=user_id, request=request),
        }

    def accept(
        self,
        *,
        user_id: str,
        event_id: str,
        idempotency_key: str,
        version: int,
        request: MoneyRequest,
    ) -> dict[str, Any]:
        if len(idempotency_key) > MAX_CLIENT_KEY:
            raise ReconcileError("idempotency_key_too_long", "Use at most 80 characters.")
        now = self.clock()
        with self.store.transaction(user_id) as tx:
            event = tx.event(event_id)
            claimed = event.state in ("accepting", "accepted")
            if claimed and event.accept_key != idempotency_key:
                code = (
                    "import_already_accepted"
                    if event.state == "accepted"
                    else ("import_accept_in_progress")
                )
                raise ReconcileError(code, "This import is already being recorded.")
            if not claimed:
                if event.version != version:
                    raise StaleEvent()
                if event.state != "open":
                    raise ReconcileError("import_not_open", "Reopen it to record it.")
                if event.evidence not in ACTIVITY_EVIDENCE:
                    raise ReconcileError(
                        "import_not_activity",
                        "This is information, not money that moved.",
                    )
                tx.put_event(
                    _bump(
                        replace(event, state="accepting", accept_key=idempotency_key), now
                    )
                )
        try:
            result = self.money.write(
                user_id=user_id,
                request=request,
                idempotency_key=f"imp:{event_id}:{idempotency_key}",
            )
        except IdempotencyConflict:
            # The key already recorded a different request; keep the claim so
            # the original record stays linked to this event.
            raise
        except Exception:
            with self.store.transaction(user_id) as tx:
                current = tx.event(event_id)
                if current.state == "accepting" and current.accept_key == idempotency_key:
                    tx.put_event(
                        _bump(replace(current, state="open", accept_key=None), now)
                    )
            raise
        activity_id = result["activity"]["activity_id"]
        with self.store.transaction(user_id) as tx:
            current = tx.event(event_id)
            if current.state == "accepting":
                recorded = request.model_dump(
                    mode="json",
                    exclude={"preview_token", "coverage", "expected_versions"},
                )
                current = replace(
                    current,
                    state="accepted",
                    activity_id=activity_id,
                    attention=None,
                    attention_detail=None,
                    possible_duplicates=(),
                    resolution={**current.resolution, "accepted_request": recorded},
                )
                account = request.account_id or request.source_account_id
                if account:
                    self._remember_account(tx, current, account, now)
                tx.put_event(_bump(current, now))
        return {
            "event": self.detail(user_id=user_id, event_id=event_id),
            "activity": result["activity"],
            "replayed": result["replayed"],
        }

    def accept_batch(
        self,
        *,
        user_id: str,
        items: Sequence[tuple[str, int]],
        idempotency_key: str,
    ) -> list[dict[str, Any]]:
        """Record a reviewed batch; exceptions stay for individual review.

        Each item names the event version the person saw, so nothing changed
        since review is recorded. An item is recorded only when it has no open
        question: nothing unresolved, no duplicate warning, and a preview that
        is ready without balance-coverage answers. Every other item is returned
        as ``needs_review`` with its reason; nothing about it changes.
        """

        if len(idempotency_key) > MAX_BATCH_KEY:
            raise ReconcileError("idempotency_key_too_long", "Use at most 40 characters.")
        if len(items) > MAX_BATCH:
            raise ReconcileError("import_batch_too_large", "Confirm at most 100 at once.")
        results = []
        for event_id, version in items:
            try:
                results.append(
                    self._accept_one(user_id, event_id, version, idempotency_key)
                )
            except (ReconcileError, StaleEvent, EventNotFound) as error:
                code = getattr(error, "code", None) or (
                    "stale_version"
                    if isinstance(error, StaleEvent)
                    else "financial_import_not_found"
                )
                results.append(
                    {"event_id": event_id, "outcome": "needs_review", "code": code}
                )
        return results

    def _accept_one(
        self, user_id: str, event_id: str, version: int, batch_key: str
    ) -> dict[str, Any]:
        key = f"b:{batch_key}:{event_id}"
        with self.store.transaction(user_id) as tx:
            event = tx.event(event_id)
            # Named as a possible duplicate by another open import: decide
            # them together, never by batch.
            contested = any(
                event_id in other.possible_duplicates for other in tx.events(("open",))
            )
        if event.state == "accepted" and event.accept_key == key:
            # A retried batch: this item was already recorded by this batch.
            return {
                "event_id": event_id,
                "outcome": "accepted",
                "activity_id": event.activity_id,
                "replayed": True,
            }
        resuming = event.state == "accepting" and event.accept_key == key
        detail = self.detail(user_id=user_id, event_id=event_id)
        if detail["version"] != version and not resuming:
            raise StaleEvent()
        if not resuming and (
            contested or detail["attention"] or detail["existing_activity_matches"]
        ):
            raise ReconcileError(
                "import_possible_duplicate", "Review this one individually."
            )
        preview = self.preview(user_id=user_id, event_id=event_id)["preview"]
        if not preview["ready"]:
            raise ReconcileError(
                "balance_coverage_required", "Answer its balance question."
            )
        request = MoneyRequest.model_validate(preview["reviewed_request"]).model_copy(
            update={"preview_token": preview["preview_token"]}
        )
        result = self.accept(
            user_id=user_id,
            event_id=event_id,
            idempotency_key=key,
            version=version,
            request=request,
        )
        return {
            "event_id": event_id,
            "outcome": "accepted",
            "activity_id": result["activity"]["activity_id"],
            "replayed": result["replayed"],
        }

    def link_activity(
        self, *, user_id: str, event_id: str, activity_id: str, version: int
    ) -> dict[str, Any]:
        """The purchase is already recorded (by hand, by voice, earlier import)."""

        self.money.detail(user_id=user_id, activity_id=activity_id)  # owner check
        now = self.clock()
        with self.store.transaction(user_id) as tx:
            event = self._editable(tx, event_id, version)
            if activity_id in tx.linked_activity_ids():
                raise ReconcileError(
                    "activity_already_linked", "Another import already points to it."
                )
            tx.put_event(
                _bump(
                    replace(
                        event,
                        state="accepted",
                        activity_id=activity_id,
                        attention=None,
                        possible_duplicates=(),
                    ),
                    now,
                )
            )
        return self.detail(user_id=user_id, event_id=event_id)

    def _draft(self, user_id: str, detail: dict[str, Any]) -> dict[str, Any]:
        facts, resolution = detail["facts"], detail["resolution"]
        missing = [f for f in detail["unresolved"] if f != "direction"]
        if missing:
            raise ReconcileError("import_unresolved", "Complete: " + ", ".join(missing))
        account_id = facts["account_id"]
        accounts = {
            s.account.id: s.account
            for s in self.money.accounts.list_accounts(user_id=user_id)
        }
        account = accounts.get(account_id)
        if account is None:
            raise ReconcileError(
                "financial_account_not_found", "Choose your own account."
            )
        if facts["currency"] and facts["currency"] != account.currency:
            raise ReconcileError(
                "import_currency_mismatch",
                "This import is in another currency than the account; nothing is converted.",
            )
        kind = resolution.get("kind") or facts["kind"]
        zone = resolution.get("time_zone") or DEFAULT_ZONE
        draft: dict[str, Any] = {
            "kind": kind,
            "amount": facts["amount"],
            "occurred_at": _start_of_day(facts["occurred_on"], zone),
            "time_zone": zone,
            "note": resolution.get("note") or _merchant(detail),
        }
        if kind in _PAIRED:
            draft["source_account_id"] = account_id
            draft["destination_account_id"] = resolution.get("destination_account_id")
        else:
            draft["account_id"] = account_id
        for field in ("category_id", "source_id", "purchase_activity_id"):
            if resolution.get(field):
                draft[field] = resolution[field]
        return draft


def _merchant(detail: dict[str, Any]) -> str | None:
    for observation in detail["observations"]:
        if observation["live"] and observation["merchant"]:
            return observation["merchant"][:200]
    return None


def _start_of_day(day: str, zone: str) -> datetime:
    try:
        tz = ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ReconcileError("time_zone_unknown", "Choose a valid time zone.") from None
    return datetime.combine(date.fromisoformat(day), time(0, 0), tzinfo=tz)


def _bump(event: Any, now: datetime) -> Any:
    return replace(event, updated_at=now, version=event.version + 1)
