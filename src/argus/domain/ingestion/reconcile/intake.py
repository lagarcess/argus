"""The sink side: recording connector evidence into events.

Identity order for each candidate:
1. the same (connection, external id) is the same observation;
2. ``replaces_external_id`` joins the observation it supersedes;
3. otherwise activity evidence is placed among nearby events by ``matching``.

Source changes after a person accepted an event never edit canonical activity:
they raise ``source_changed`` / ``source_removed`` for the person to act on.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Any

from argus.domain.ingestion.contract import ImportCandidate
from argus.domain.ingestion.reconcile.matching import (
    ACTIVITY_EVIDENCE,
    MATCH_WINDOW_DAYS,
    Facts,
    event_facts,
    observation_facts,
    place,
)
from argus.domain.ingestion.reconcile.model import (
    ImportEvent,
    Observation,
    SubmitTally,
)
from argus.domain.ingestion.reconcile.store import ImportStore, ImportTx
from argus.domain.ingestion.sink import SubmitResult

_MONEY_FACTS = ("amount", "currency", "direction", "occurred_on")
# Kept after disconnect for accepted events: enough to explain the record.
_PROVENANCE = ("source", "evidence", "status", "occurred_on", "posted_on")


def submit(
    store: ImportStore,
    now: datetime,
    *,
    user_id: str,
    connection_id: str,
    candidates: Sequence[ImportCandidate],
) -> SubmitResult:
    for candidate in candidates:
        if candidate.source.connection_id != connection_id:
            raise ValueError("candidate belongs to another connection")
    tally = SubmitTally()
    with store.transaction(user_id) as tx:
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
                tx.delete_event(event.id)
        tx.delete_links(connection_id)
    return removed


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
    event_id, duplicates, ambiguous = None, (), False
    if candidate.evidence in ACTIVITY_EVIDENCE and candidate.evidence != "unclassified":
        placement = place(facts, ref.source, _nearby(tx, facts))
        event_id, duplicates, ambiguous = (
            placement.event_id,
            placement.duplicates,
            placement.ambiguous,
        )
    if event_id is not None:
        event = tx.event(event_id)
        tx.put_observation(replace(observation, event_id=event_id))
        tx.put_event(_touch(event, now, anchor=_anchor(candidate, facts)))
        return
    event = ImportEvent(
        id=str(uuid.uuid4()),
        user_id=user_id,
        state="open",
        evidence=candidate.evidence,
        anchor_on=_anchor(candidate, facts),
        attention=(
            "ambiguous_match"
            if ambiguous
            else "possible_duplicate"
            if duplicates
            else None
        ),
        attention_detail=None,
        possible_duplicates=duplicates,
        resolution={},
        activity_id=None,
        accept_key=None,
        created_at=now,
        updated_at=now,
        version=1,
    )
    tx.put_event(event)
    tx.put_observation(replace(observation, event_id=event.id))


def nearby_facts(
    tx: ImportTx, facts: Facts
) -> list[tuple[ImportEvent, list[Observation], Facts]]:
    return _nearby(tx, facts)


def _nearby(
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


def _facts(tx: ImportTx, event_id: str) -> Facts:
    return event_facts(tx.event(event_id), tx.observations(event_id), tx.links())


def _after_change(tx: ImportTx, event_id: str, before: Facts, now: datetime) -> None:
    event = tx.event(event_id)
    observations = tx.observations(event_id)
    after = event_facts(event, observations, tx.links())
    live = any(o.live for o in observations)
    changed = {
        name: {
            "before": _plain(getattr(before, name)),
            "after": _plain(getattr(after, name)),
        }
        for name in _MONEY_FACTS
        if getattr(before, name) != getattr(after, name)
    }
    if event.state in ("accepted", "accepting"):
        if not live:
            event = replace(event, attention="source_removed", attention_detail=None)
        elif changed:
            event = replace(event, attention="source_changed", attention_detail=changed)
    elif event.state == "open" and not live:
        event = replace(
            event, state="dismissed", attention_detail={"reason": "source_removed"}
        )
    tx.put_event(_touch(event, now, anchor=after.occurred_on))


def _touch(event: ImportEvent, now: datetime, *, anchor: date | None) -> ImportEvent:
    anchors = [d for d in (event.anchor_on, anchor) if d is not None]
    return replace(
        event,
        anchor_on=min(anchors) if anchors else None,
        updated_at=now,
        version=event.version + 1,
    )


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
    kept = {k: candidate.get(k) for k in _PROVENANCE if k != "source"}
    kept["source"] = {
        "source": source.get("source"),
        "connection_id": source.get("connection_id"),
        "external_id": source.get("external_id"),
        "observed_at": source.get("observed_at"),
    }
    kept["redacted"] = True
    return kept


def _plain(value: Any) -> Any:
    return str(value) if value is not None and not isinstance(value, str) else value
