"""Canonical consented credits reduce original intentions without private DTOs."""

from argus.domain.recording.payments import net_total

from . import goal_projection


def credit(entry, accepted, purpose, actual, accounts):
    if (
        not entry
        or entry["currency"] != accepted["currency"]
        or entry["kind"] != accepted["kind"]
    ):
        return None
    if {(leg["role"], leg["account_id"]) for leg in entry["legs"]} != {
        tuple(leg) for leg in accepted["legs"]
    }:
        return None
    if purpose == "goal_saving":
        return goal_projection.contribution_minor(entry, accepted, accounts)
    if purpose == "debt_payment":
        return net_total(entry, list(actual.values()))
    return entry["amount_minor"] if purpose == "bill_payment" else 0


def for_occurrence(state, identifier, accounts=None):
    canonical = getattr(accounts, "canonical", None)
    actual = state.get("_canonical_activities", {})
    records = state.get("_canonical_records", accounts or [])
    if canonical is not None:
        from argus.domain.recording.money_reads import render_activity

        actual = {
            aid: render_activity(aid, canonical.history[aid], revision)
            for aid, revision in canonical.current.items()
        }
        records = canonical.records
    links = [
        link
        for link in state.get("_shared_links", [])
        if link["occurrence_id"] == identifier
    ]
    if not links:
        return None
    values = [
        0
        if link["released"]
        else credit(
            actual.get(link["activity_id"]),
            link["attribution"],
            link["purpose"],
            actual,
            records,
        )
        for link in links
    ]
    return dict(amount=sum(values) if all(v is not None for v in values) else None)
