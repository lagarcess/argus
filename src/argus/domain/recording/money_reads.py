"""Logical activity views derive from exact account-leg revisions."""

from typing import Any

from argus.domain.recording.currency import currency_exponent, format_minor_units
from argus.domain.recording.errors import AccountNotFound
from argus.domain.recording.loop import ExpenseRecord, ExpenseRevision
from argus.domain.recording.loop_reads import activity_response
from argus.domain.recording.repository import StoredAccount


def groups(
    accounts: list[StoredAccount],
) -> dict[str, dict[int, list[tuple[StoredAccount, ExpenseRecord, ExpenseRevision]]]]:
    result: dict[
        str, dict[int, list[tuple[StoredAccount, ExpenseRecord, ExpenseRevision]]]
    ] = {}
    for stored in accounts:
        for record in stored.expenses:
            for revision in record.revisions:
                if not revision.active:
                    continue
                aid = revision.activity_id or record.id
                number = revision.activity_revision or revision.revision
                result.setdefault(aid, {}).setdefault(number, []).append(
                    (stored, record, revision)
                )
    return result


def activity(
    accounts: list[StoredAccount], activity_id: str, revision: int | None = None
) -> dict[str, Any]:
    history = groups(accounts).get(activity_id)
    if not history:
        raise AccountNotFound()
    number = max(history) if revision is None else revision
    if number not in history:
        raise AccountNotFound()
    legs = sorted(
        history[number], key=lambda leg: (leg[2].role == "destination", leg[0].account.id)
    )
    stored, _, r = legs[0]
    currency = stored.account.currency
    return {
        "activity_id": activity_id,
        "revision": number,
        "kind": r.kind,
        "amount_minor": r.amount_minor,
        "amount": format_minor_units(r.amount_minor, currency),
        "currency": currency,
        "currency_fraction_digits": currency_exponent(currency),
        "occurred_at": r.occurred_at,
        "time_zone": r.time_zone,
        "note": r.note,
        "category_id": r.category_id,
        "source_id": r.source_id,
        "purchase_activity_id": r.purchase_activity_id,
        "purchase_revision": r.purchase_revision,
        "reason": r.reason,
        "recorded_at": r.recorded_at,
        "recorded_by": r.recorded_by,
        "legs": [
            {
                "record_id": record.id,
                "record_revision": rev.revision,
                "account_id": s.account.id,
                "role": rev.role,
                "balance_movement_minor": rev.movement_minor,
                "coverage": activity_response(s, record, rev.revision)["coverage"],
            }
            for s, record, rev in legs
        ],
    }


def current_activities(accounts: list[StoredAccount]) -> list[dict[str, Any]]:
    return [activity(accounts, aid) for aid in groups(accounts)]
