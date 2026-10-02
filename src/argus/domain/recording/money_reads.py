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
    canonical = getattr(accounts, "canonical", None)
    if canonical is not None:
        return canonical.history
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
    canonical = getattr(accounts, "canonical", None)
    if canonical is None:
        return render_activity(activity_id, groups(accounts).get(activity_id), revision)
    visible = {s.account.id for s in accounts}
    if revision is None:
        revision = canonical.current_visible(visible).get(activity_id)
        if revision is None:
            raise AccountNotFound()
    full = render_activity(activity_id, canonical.history.get(activity_id), revision)
    return visible_activity(full, visible, canonical.history)


def visible_activity(full: dict, account_ids: set[str], history: dict) -> dict:
    body = full.copy()
    legs = [leg for leg in body["legs"] if leg["account_id"] in account_ids]
    if not legs:
        raise AccountNotFound()
    primary_hidden = body["legs"][0]["account_id"] not in account_ids
    body["legs"] = legs
    if primary_hidden:
        for key in (
            "amount",
            "amount_minor",
            "note",
            "reason",
            "source_id",
            "category_id",
            "principal_minor",
            "interest_minor",
            "fees_minor",
            "recorded_by",
        ):
            body[key] = None
    for key, rev in (
        ("purchase_activity_id", "purchase_revision"),
        ("reversal_of_activity_id", "reversal_of_revision"),
    ):
        linked = history.get(body[key], {}).get(body[rev], []) if body[key] else []
        if body[key] and any(s.account.id not in account_ids for s, _, __ in linked):
            body[key] = body[rev] = None
    return body


def render_activity(
    activity_id: str,
    history: dict[int, list[tuple[StoredAccount, ExpenseRecord, ExpenseRevision]]] | None,
    revision: int | None = None,
) -> dict[str, Any]:
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
    result = {
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
        "reversal_of_activity_id": r.reversal_of_activity_id,
        "reversal_of_revision": r.reversal_of_revision,
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
    from argus.domain.recording.payments import breakdown

    return result | breakdown(legs)


def current_activities(accounts: list[StoredAccount]) -> list[dict[str, Any]]:
    canonical = getattr(accounts, "canonical", None)
    if canonical is not None:
        return [
            activity(accounts, aid, revision)
            for aid, revision in canonical.current_visible(
                {s.account.id for s in accounts}
            ).items()
        ]
    return [render_activity(aid, history) for aid, history in groups(accounts).items()]
