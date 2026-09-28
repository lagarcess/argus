"""Review issues for a PROPOSED recording contract (test-only).

Issues are recomputed from the current book on every review and never stored.
A blocking issue stops confirmation; a notice informs and never blocks. A short
or unknown balance is never an issue: Argus records history, it does not
authorize payments.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from tests.financial_recording.catalog import (
    COUNTER_NATURE,
    KIND_FAMILY,
    LEG_SIGNS,
    LIQUID_TYPES,
    NATURE,
    NOTE_MAX,
    REFUNDABLE_TYPES,
)
from tests.financial_recording.derive import (
    GAP_LABEL,
    Account,
    Activity,
    Answers,
    Body,
    Book,
    Known,
    Observation,
    Provenance,
    Record,
    Revision,
    accounts_of,
    activities,
    anchors,
    balance,
    contained_at_confirmation,
    contradicted,
    fulfills,
    legs,
    live_records,
    unanswered,
)
from tests.financial_recording.money import InvalidInput, exponent, parse_minor

NOTICE_CODES = frozenset({"negative_asset_balance", "account_archived"})
ACTIVITY_FIELDS = ("account_id", "amount", "occurred_on")
REQUIRED_FIELDS: Mapping[str, tuple[str, ...]] = {
    **{kind: ACTIVITY_FIELDS for kind in LEG_SIGNS},
    "balance_observation": ("account_id", "amount", "as_of", "basis"),
}
TRIAL_ID = "this"
_EPOCH = datetime.fromisoformat("1970-01-01T00:00:00+00:00")


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str
    refs: tuple[str, ...] = ()


class ReviewRequired(Exception):
    def __init__(self, issues: Sequence[Issue]) -> None:
        super().__init__(", ".join(item.code for item in issues))
        self.issues = tuple(issues)


def issue(code: str, *refs: str) -> Issue:
    return Issue(code, "notice" if code in NOTICE_CODES else "blocking", refs)


def blocking(found: Sequence[Issue]) -> list[Issue]:
    return [item for item in found if item.severity == "blocking"]


def parse_fields(
    fields: Mapping[str, Optional[str]], book: Book, answers: Answers = ()
) -> tuple[Optional[Body], tuple[Issue, ...]]:
    kind = fields.get("kind") or ""
    if kind not in REQUIRED_FIELDS:
        return None, (issue("kind_unsupported", kind),)
    text = {name: (value or "").strip() for name, value in fields.items()}
    missing = tuple(name for name in REQUIRED_FIELDS[kind] if not text.get(name))
    if missing:
        return None, (issue("field_missing", *missing),)
    account = book.accounts.get(text["account_id"])
    if account is None:
        return None, (issue("account_unknown", text["account_id"]),)
    found: list[Issue] = []
    currency = text.get("currency") or account.currency
    if _parsed(found, exponent, currency) is not None and currency != account.currency:
        found.append(issue("currency_mismatch", currency))
    note = text.get("note") or None
    values = {
        "account_id": account.id,
        "amount": _parsed(found, parse_minor, text["amount"], account.currency),
        "note": note,
    }
    if kind == "balance_observation":
        values["as_of"] = _parsed(found, parse_instant, text["as_of"])
        values["basis"] = _parsed(found, _choice, text["basis"], GAP_LABEL)
        return (None if found else Observation(**values)), tuple(found)
    values.update(
        kind=kind,
        occurred_on=_parsed(found, parse_date, text["occurred_on"]),
        occurred_at=_parsed(found, parse_instant, text.get("occurred_at")),
        category=text.get("category") or None,
        counter_account_id=text.get("counter_account_id") or None,
        refund_of=text.get("refund_of") or None,
        fulfills=text.get("fulfills") or None,
        answers=answers,
    )
    return (None if found else Activity(**values)), tuple(found)


def validate(
    book: Book,
    body: Body,
    tz: ZoneInfo,
    record_id: Optional[str] = None,
    provenance: Optional[Provenance] = None,
) -> list[Issue]:
    """Issues for `body` as a new record, or as the next revision of `record_id`."""
    missing = sorted(item for item in accounts_of(body) if item not in book.accounts)
    if missing:
        return [issue("account_unknown", *missing)]
    found = [
        issue("account_archived", account_id)
        for account_id in sorted(accounts_of(body))
        if book.accounts[account_id].archived
    ]
    note = getattr(body, "note", None)
    if note is not None and len(note) > NOTE_MAX:
        found.append(issue("note_too_long", str(len(note))))
    if isinstance(body, Activity):
        found.extend(_activity_issues(book, body, record_id))
    trial = with_trial(book, body, record_id, tz, provenance)
    found.extend(inclusion_issues(trial, accounts_of(body), tz))
    return found


def with_trial(
    book: Book,
    body: Body,
    record_id: Optional[str],
    tz: ZoneInfo,
    provenance: Optional[Provenance] = None,
) -> Book:
    if record_id is not None:
        record = book.records[record_id]
        revision = replace(record.revisions[-1], body=body, removed=False)
        trial = replace(record, revisions=(*record.revisions, revision))
    else:
        contained = (
            contained_at_confirmation(book, body, tz)
            if isinstance(body, Observation)
            else None
        )
        revision = Revision(
            body,
            _EPOCH,
            provenance or Provenance("manual", _EPOCH),
            contained=contained,
        )
        trial = Record(TRIAL_ID, len(book.records) + 1, (revision,))
    return replace(book, records={**book.records, trial.id: trial})


def notices(book: Book, body: Body, tz: ZoneInfo, provenance: Provenance) -> list[Issue]:
    trial = with_trial(book, body, None, tz, provenance)
    found = [
        issue("negative_asset_balance", account_id)
        for account_id in sorted(accounts_of(body))
        if book.accounts[account_id].type in LIQUID_TYPES
        and isinstance(current := balance(trial, account_id, tz=tz), Known)
        and current.amount < 0
    ]
    return found


def duplicates(
    book: Book,
    earlier_drafts: Sequence[tuple[str, Mapping, Provenance]],
    provenance: Provenance,
    account_id: str,
    body: Optional[Body],
    distinct: bool,
) -> list[Issue]:
    existing = [
        (
            record.id,
            None if record.removed else record.body,
            record.body.account_id,
            (record.revisions[0].provenance, *record.linked),
        )
        for record in book.records.values()
    ] + [
        (
            draft_id,
            parse_fields(fields, book)[0],
            (fields.get("account_id") or "").strip(),
            (source,),
        )
        for draft_id, fields, source in earlier_drafts
    ]
    mine = _identities(provenance, account_id)
    same_source = [
        item_id
        for item_id, _, item_account, sources in existing
        if any(mine & _identities(source, item_account) for source in sources)
    ]
    if same_source:
        return [issue("already_recorded", *same_source)]
    signature = _signature(body)
    if not signature or distinct:
        return []
    matches = [
        item_id
        for item_id, item_body, _, _ in existing
        if signature & _signature(item_body)
    ]
    return [issue("possible_duplicate", *matches)] if matches else []


def _activity_issues(book: Book, body: Activity, record_id: Optional[str]) -> list[Issue]:
    account = book.accounts[body.account_id]
    found = [issue("amount_not_positive")] if body.amount <= 0 else []
    found.extend(_category_issues(book, body, account))
    found.extend(_counter_issues(book, body, account))
    found.extend(refund_issues(book, body, account, record_id))
    found.extend(_expectation_issues(book, body, record_id))
    return found


def _category_issues(book: Book, body: Activity, account: Account) -> list[Issue]:
    if body.category is None:
        return []
    family = KIND_FAMILY[body.kind]
    category = book.categories.get(body.category)
    if family is None:
        return [issue("category_not_applicable", body.category)]
    if category is None:
        return [issue("category_unknown", body.category)]
    if category.space_id not in (None, account.space_id):
        return [issue("category_other_space", body.category)]
    if category.family != family:
        return [issue("category_kind_mismatch", body.category)]
    return []


def _counter_issues(book: Book, body: Activity, account: Account) -> list[Issue]:
    needs_counter = body.kind in COUNTER_NATURE
    counter = book.accounts.get(body.counter_account_id or "")
    if not needs_counter:
        return (
            [issue("counter_account_unexpected", body.counter_account_id)]
            if body.counter_account_id
            else []
        )
    if counter is None:
        return [issue("counter_account_missing")]
    if counter.id == account.id:
        return [issue("counter_account_same", counter.id)]
    found = []
    if counter.currency != account.currency:
        found.append(issue("cross_currency_unresolved", counter.id))
    wanted = COUNTER_NATURE[body.kind]
    if wanted is not None and NATURE[counter.type] != wanted:
        found.append(issue("counter_not_liability", counter.id))
    return found


def refund_issues(
    book: Book, body: Activity, account: Account, record_id: Optional[str]
) -> list[Issue]:
    if body.kind != "refund":
        return [issue("refund_link_unexpected")] if body.refund_of else []
    if account.type not in REFUNDABLE_TYPES:
        return [issue("refund_account_unsupported", account.type)]
    if body.refund_of is None:
        return []
    purchase = book.records.get(body.refund_of)
    if purchase is None or not (
        isinstance(purchase.body, Activity) and purchase.body.kind == "expense"
    ):
        return [issue("refund_target_invalid", body.refund_of)]
    if purchase.removed:
        return [issue("refund_purchase_removed", purchase.id)]
    original = purchase.body
    if book.accounts[original.account_id].currency != account.currency:
        return [issue("refund_link_currency", purchase.id)]
    found = []
    if body.occurred_on < original.occurred_on:
        found.append(issue("refund_before_purchase", purchase.id))
    if body.category is not None and body.category != original.category:
        found.append(issue("refund_category_mismatch", purchase.id))
    refunded = sum(
        record.body.amount
        for record in live_records(book)
        if record.id != record_id
        and isinstance(record.body, Activity)
        and record.body.refund_of == purchase.id
    )
    if refunded + body.amount > original.amount:
        found.append(issue("refund_exceeds_purchase", purchase.id))
    return found


def _expectation_issues(
    book: Book, body: Activity, record_id: Optional[str]
) -> list[Issue]:
    if body.fulfills is None:
        return []
    expectation = book.expectations.get(body.fulfills)
    if expectation is None:
        return [issue("expectation_unknown", body.fulfills)]
    if not fulfills(body, expectation):
        return [issue("expectation_mismatch", expectation.id)]
    taken = [
        record.id
        for record in live_records(book)
        if record.id != record_id
        and isinstance(record.body, Activity)
        and fulfills(record.body, expectation)
    ]
    return [issue("expectation_already_fulfilled", *taken)] if taken else []


def inclusion_issues(book: Book, account_ids: set[str], tz: ZoneInfo) -> list[Issue]:
    """Every open or contradictory inclusion answer on the given accounts."""
    found = []
    for account_id in sorted(account_ids):
        ordered = anchors(book, account_id)
        for record in activities(book, account_id):
            anchor_id = unanswered(record, ordered, tz)
            if anchor_id is not None:
                found.append(issue("inclusion_unanswered", anchor_id, record.id))
                continue
            found.extend(
                issue("inclusion_conflict", conflict, record.id)
                for conflict in contradicted(record, ordered, tz)
            )
    return found


def _identities(provenance: Provenance, account_id: str) -> set[tuple]:
    ref = provenance.source_ref or {}
    keys = set()
    if "digest" in ref and "row" in ref:
        keys.add(("file", ref["digest"], ref["row"]))
    if ref.get("external_id") and account_id:
        keys.add(("external", account_id, ref["external_id"]))
    return keys


def _signature(body: Optional[Body]) -> frozenset:
    # Every leg counts, so a card statement's payment row meets the payment
    # already recorded from the checking side.
    if not isinstance(body, Activity):
        return frozenset()
    return frozenset(
        (account_id, abs(effect), body.occurred_on)
        for account_id, effect in legs(body).items()
    )


def _parsed(found: list[Issue], parser: Callable, text: Optional[str], *args):
    if not text:
        return None
    try:
        return parser(text, *args)
    except InvalidInput as error:
        found.append(issue(error.code, text))
        return None


def parse_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as error:
        raise InvalidInput("date_invalid", text) from error


def parse_instant(text: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise InvalidInput("date_invalid", text) from error
    if parsed.tzinfo is None:
        raise InvalidInput("date_invalid", f"{text} has no UTC offset")
    return parsed


def _choice(text: str, allowed: Sequence[str]) -> str:
    if text not in allowed:
        raise InvalidInput("choice_invalid", text)
    return text
