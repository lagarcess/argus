"""The sink side: recording connector evidence into events.

Identity order for each candidate:
1. the same (connection, external id) is the same observation;
2. ``replaces_external_id`` joins the observation it supersedes;
3. otherwise activity evidence is placed among nearby events by ``matching``.

Source changes after a person accepted an event never edit canonical activity:
they raise ``source_changed`` / ``source_removed`` for the person to act on.
Evidence that arrives after its connection ended is ignored, so an in-flight
sync cannot resurrect drafts a disconnect removed.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from argus.domain.ingestion.contract import ImportCandidate
from argus.domain.ingestion.reconcile import duplicates
from argus.domain.ingestion.reconcile.matching import (
    ACTIVITY_EVIDENCE,
    MATCH_WINDOW_DAYS,
    Facts,
    event_facts,
    observation_facts,
    place,
    recorded_facts,
)
from argus.domain.ingestion.reconcile.model import (
    ImportEvent,
    Observation,
    SubmitTally,
)
from argus.domain.ingestion.reconcile.store import ImportStore, ImportTx
from argus.domain.ingestion.sink import SubmitResult

_MONEY_FACTS = ("amount", "currency", "occurred_on")
# Kept after disconnect for accepted events: enough to explain the record.
_PROVENANCE = ("evidence", "status", "occurred_on", "posted_on")


def submit(
    store: ImportStore,
    now: datetime,
    *,
    user_id: str,
    connection_id: str,
    candidates: Sequence[ImportCandidate],
    is_live: Callable[[], bool] = lambda: True,
) -> SubmitResult:
    for candidate in candidates:
        if candidate.source.connection_id != connection_id:
            raise ValueError("candidate belongs to another connection")
    tally = SubmitTally()
    with store.transaction(user_id) as tx:
        # Checked under the person's lock: a disconnect's cleanup takes the
        # same lock after the connection is marked ended.
        if not is_live():
            return SubmitResult(0, len(candidates), 0)
        for candidate in candidates:
            _record(tx, user_id, candidate, now, tally)
    return SubmitResult(tally.recorded, tally.unchanged, tally.withdrawn)


def forget(store: ImportStore, now: datetime, *, user_id: str, connection_id: str) -> int:
    """Disconnect retention: unreviewed evidence goes; accepted keeps provenance."""

    removed = 0
    with store.transaction(user_id) as tx:
        for observation in tx.connection_observations(connection_id):
            event = tx.event(observation.event_id)
            if event.state in ("accepted", "accepting"):
                tx.put_observation(
                    replace(
                        observation,
                        candidate=_provenance(observation.candidate),
                        live=False,
                        updated_at=now,
                    )
                )
                continue
            tx.delete_observation(observation.id)
            removed += 1
            if not tx.observations(event.id):
                duplicates.forget(tx, event, now)
                tx.delete_event(event.id)
        tx.delete_links(connection_id)
    return removed


def reanchor(tx: ImportTx, event: ImportEvent) -> ImportEvent:
    """The match window follows the event's current best date, including one
    the person supplied, so later evidence is compared against it."""

    facts = event_facts(event, tx.observations(event.id), tx.links())
    return replace(event, anchor_on=facts.occurred_on or event.anchor_on)


def nearby_facts(
    tx: ImportTx, facts: Facts
) -> list[tuple[ImportEvent, list[Observation], Facts]]:
    if facts.occurred_on is None:
        return []
    window = timedelta(days=MATCH_WINDOW_DAYS)
    links = tx.links()
    found = []
    for event in tx.nearby(facts.occurred_on - window, facts.occurred_on + window):
        observations = tx.observations(event.id)
        found.append((event, observations, event_facts(event, observations, links)))
    return found


def _record(
    tx: ImportTx,
    user_id: str,
    candidate: ImportCandidate,
    now: datetime,
    tally: SubmitTally,
) -> None:
    ref = candidate.source
    fingerprint = candidate.fingerprint()
    body = candidate.model_dump(mode="json")
    existing = tx.observation(ref.connection_id, ref.external_id)
    if existing is not None:
        if existing.fingerprint == fingerprint:
            tally.unchanged += 1
            return
        removed = candidate.status == "removed"
        before = _facts(tx, existing.event_id)
        tx.put_observation(
            replace(
                existing,
                candidate={**existing.candidate, "status": "removed"}
                if removed
                else body,
                fingerprint=fingerprint,
                live=not removed and not _superseded(tx, existing),
                revisions=existing.revisions + 1,
                updated_at=now,
            )
        )
        _after_change(tx, existing.event_id, before, now)
        if removed:
            tally.withdrawn += 1
        else:
            tally.recorded += 1
        return
    if candidate.status == "removed":
        tally.unchanged += 1  # nothing known to withdraw
        return
    observation = Observation(
        id=str(uuid.uuid4()),
        user_id=user_id,
        event_id="",
        connection_id=ref.connection_id,
        source=ref.source,
        external_id=ref.external_id,
        fingerprint=fingerprint,
        candidate=body,
        live=True,
        revisions=1,
        first_seen_at=now,
        updated_at=now,
    )
    tally.recorded += 1
    prior = (
        tx.observation(ref.connection_id, ref.replaces_external_id)
        if ref.replaces_external_id
        else None
    )
    if prior is not None:
        before = _facts(tx, prior.event_id)
        tx.put_observation(replace(prior, live=False, updated_at=now))
        tx.put_observation(replace(observation, event_id=prior.event_id))
        _after_change(tx, prior.event_id, before, now)
        return
    facts = observation_facts(observation, tx.links())
    event_id, found, ambiguous = None, (), False
    if candidate.evidence in ACTIVITY_EVIDENCE and candidate.evidence != "unclassified":
        placement = place(facts, ref.source, nearby_facts(tx, facts))
        event_id, found, ambiguous = (
            placement.event_id,
            placement.duplicates,
            placement.ambiguous,
        )
    if event_id is not None:
        tx.put_observation(replace(observation, event_id=event_id))
        tx.put_event(_bump(reanchor(tx, tx.event(event_id)), now))
        return
    event = ImportEvent(
        id=str(uuid.uuid4()),
        user_id=user_id,
        state="open",
        evidence=candidate.evidence,
        anchor_on=_anchor(candidate, facts),
        attention=None,
        attention_detail=None,
        possible_duplicates=(),
        resolution={},
        activity_id=None,
        accept_key=None,
        created_at=now,
        updated_at=now,
        version=1,
    )
    event = duplicates.flag(event, found, ambiguous=ambiguous)
    tx.put_event(event)
    tx.put_observation(replace(observation, event_id=event.id))
    duplicates.mirror(tx, event, (), now)


def _evidence(tx: ImportTx, event: ImportEvent) -> Facts:
    """What the sources say, ignoring what the person resolved or recorded:
    the baseline for noticing that a source changed its story."""

    return event_facts(
        replace(event, resolution={}), tx.observations(event.id), tx.links()
    )


def _facts(tx: ImportTx, event_id: str) -> Facts:
    return _evidence(tx, tx.event(event_id))


def _after_change(tx: ImportTx, event_id: str, before: Facts, now: datetime) -> None:
    event = tx.event(event_id)
    observations = tx.observations(event_id)
    after = _evidence(tx, event)
    live = any(o.live for o in observations)
    recorded = recorded_facts(event.resolution.get("accepted"))
    if recorded:
        # Compare with what was recorded, not with the previous evidence: a
        # replacement that restores the recorded facts is not a change.
        before = replace(
            before,
            amount=Decimal(recorded["amount"]) if "amount" in recorded else None,
            currency=recorded.get("currency"),
            occurred_on=date.fromisoformat(recorded["occurred_on"])
            if "occurred_on" in recorded
            else None,
        )
    changed = {
        name: {
            "before": _plain(getattr(before, name)),
            "after": _plain(getattr(after, name)),
        }
        for name in _MONEY_FACTS
        if _differs(name, getattr(before, name), getattr(after, name))
    }
    withdrawn = (event.attention_detail or {}).get("reason") == "source_removed"
    if event.state in ("accepted", "accepting"):
        if not live:
            event = replace(event, attention="source_removed", attention_detail=None)
        elif changed:
            event = replace(event, attention="source_changed", attention_detail=changed)
        elif event.attention == "source_removed":
            event = replace(event, attention=None, attention_detail=None)
    elif event.state == "open" and not live:
        event = replace(
            event, state="dismissed", attention_detail={"reason": "source_removed"}
        )
    elif event.state == "dismissed" and live and withdrawn:
        # Withdrawn by the source, then replaced (pending removed, posted
        # later): the purchase is real again and back in review.
        event = replace(event, state="open", attention_detail=None)
    tx.put_event(_bump(reanchor(tx, event), now))


def _differs(name: str, before: Any, after: Any) -> bool:
    """A fact changed in a way the person must look at. Dates move between
    authorization, posting and statements, so only a move beyond the match
    window counts; a fact a source stopped reporting is not a change."""

    if before is None or after is None:
        return False
    if name == "occurred_on":
        return abs((after - before).days) > MATCH_WINDOW_DAYS
    return before != after


def _bump(event: ImportEvent, now: datetime) -> ImportEvent:
    return replace(event, updated_at=now, version=event.version + 1)


def _anchor(candidate: ImportCandidate, facts: Facts) -> date | None:
    return (
        facts.occurred_on
        or candidate.due_on
        or candidate.period_end
        or candidate.posted_on
    )


def _superseded(tx: ImportTx, observation: Observation) -> bool:
    return any(
        (o.candidate.get("source") or {}).get("replaces_external_id")
        == observation.external_id
        and o.connection_id == observation.connection_id
        and o.live
        for o in tx.observations(observation.event_id)
    )


def _provenance(candidate: dict[str, Any]) -> dict[str, Any]:
    source = candidate.get("source") or {}
    kept = {k: candidate.get(k) for k in _PROVENANCE}
    kept["source"] = {
        "source": source.get("source"),
        "connection_id": source.get("connection_id"),
        "external_id": source.get("external_id"),
        "observed_at": source.get("observed_at"),
    }
    kept["redacted"] = True
    return kept


def _plain(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    return str(value) if value is not None and not isinstance(value, str) else value
