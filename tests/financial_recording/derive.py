"""Recorded facts and the pure reads over them (proposed contract, test-only).

Balances, remaining differences, totals and positions are recomputed from the
current revisions on every read and never stored, so a fact supplied later
explains an earlier balance check without a compensating write. What a check
showed when it was confirmed is kept on its revision and never recomputed. A
scope is a caller-supplied set of account ids; this model has no permission
logic.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from fractions import Fraction
from typing import Literal, Optional, Union
from zoneinfo import ZoneInfo

from tests.financial_recording.catalog import (
    DEFAULT_CATEGORIES,
    ESTIMATED_TYPES,
    LEG_SIGNS,
    NATURE,
    TOTAL_BUCKET,
    AccountType,
    Category,
    Kind,
)
from tests.financial_recording.money import round_half_up

DEFAULT_TZ = ZoneInfo("America/Santo_Domingo")
INCLUDED, NOT_INCLUDED = "included", "not_included"

Basis = Literal["user_check", "statement", "value_estimate"]
Inclusion = Literal["included", "not_included"]
Weighting = Literal["full", "owner_share"]
Answers = tuple[tuple[str, Inclusion], ...]

GAP_LABEL: Mapping[str, str] = {
    "user_check": "unexplained",
    "statement": "unexplained",
    "value_estimate": "revaluation",
}


@dataclass(frozen=True)
class Account:
    id: str
    nickname: Optional[str]
    type: AccountType
    currency: str
    ownership_share_bps: int
    created_at: datetime
    space_id: str = "personal"
    archived: bool = False
    version: int = 1
    linked_asset_id: Optional[str] = None


@dataclass(frozen=True)
class Opening:
    account_id: str
    amount: int
    as_of: datetime
    zone: str


@dataclass(frozen=True)
class Observation:
    account_id: str
    amount: int
    as_of: datetime
    basis: Basis
    zone: str
    note: Optional[str] = None


@dataclass(frozen=True)
class Activity:
    kind: Kind
    account_id: str
    amount: int
    occurred_on: date
    occurred_at: Optional[datetime] = None
    category: Optional[str] = None
    counter_account_id: Optional[str] = None
    answers: Answers = ()
    note: Optional[str] = None
    refund_of: Optional[str] = None
    fulfills: Optional[str] = None


Anchor = Union[Opening, Observation]
Body = Union[Opening, Observation, Activity]


@dataclass(frozen=True)
class Provenance:
    method: str
    captured_at: datetime
    source_ref: Optional[dict] = None


@dataclass(frozen=True)
class Revision:
    body: Body
    recorded_at: datetime
    provenance: Provenance
    reason: Optional[str] = None
    removed: bool = False
    recorded_by: Optional[str] = None
    confirmed_expected: Optional[int] = None
    confirmed_difference: Optional[int] = None
    contained: Optional[frozenset[str]] = None


@dataclass(frozen=True)
class Record:
    id: str
    seq: int
    revisions: tuple[Revision, ...]
    linked: tuple[Provenance, ...] = ()

    @property
    def body(self) -> Body:
        return self.revisions[-1].body

    @property
    def removed(self) -> bool:
        return self.revisions[-1].removed


@dataclass(frozen=True)
class Expectation:
    id: str
    account_id: str
    direction: Literal["in", "out"]
    amount: int
    due_on: date


@dataclass(frozen=True)
class Book:
    accounts: Mapping[str, Account]
    records: Mapping[str, Record]
    categories: Mapping[str, Category] = field(
        default_factory=lambda: dict(DEFAULT_CATEGORIES)
    )
    expectations: Mapping[str, Expectation] = field(default_factory=dict)


@dataclass(frozen=True)
class Known:
    amount: int
    as_of: datetime
    basis: str
    state: str = "known"


@dataclass(frozen=True)
class Unknown:
    activity_since_tracking: int
    state: str = "unknown"


Balance = Union[Known, Unknown]


@dataclass(frozen=True)
class Gap:
    record_id: str
    account_id: str
    as_of: datetime
    recorded: Optional[int]
    remaining: Optional[int]
    label: Optional[str]
    explained_by: tuple[str, ...]


@dataclass(frozen=True)
class Totals:
    spending: int
    income: int
    purchases: int
    refunds: int
    moved_in_from_outside_scope: int
    moved_out_of_scope: int
    spending_by_category: Mapping[str, int]
    income_by_category: Mapping[str, int]


@dataclass(frozen=True)
class Coverage:
    accounts_known: tuple[str, ...]
    accounts_unknown: tuple[str, ...]
    archived_included: tuple[str, ...]
    oldest_anchor_as_of: Optional[datetime]
    unexplained_gaps: tuple[Gap, ...]


@dataclass(frozen=True)
class Position:
    assets: Optional[int]
    liabilities: Optional[int]
    net: Optional[int]
    coverage: Coverage


class Unanswered(ValueError):
    pass


def legs(activity: Activity) -> dict[str, int]:
    source, counter = LEG_SIGNS[activity.kind]
    effects = {activity.account_id: source * activity.amount}
    if counter is not None and activity.counter_account_id is not None:
        effects[activity.counter_account_id] = counter * activity.amount
    return effects


def accounts_of(body: Body) -> set[str]:
    return set(legs(body)) if isinstance(body, Activity) else {body.account_id}


def anchor_zone(anchor: Anchor) -> ZoneInfo:
    """Zone stored with the balance date; later reader-zone changes never rewrite it."""
    return ZoneInfo(anchor.zone)


def anchor_day(anchor: Anchor) -> date:
    return anchor.as_of.astimezone(anchor_zone(anchor)).date()


def placement(
    activity_record: Record, anchor_record: Record, tz: ZoneInfo
) -> Optional[Inclusion]:
    """Whether an anchor's balance already contains the activity; None means ask.

    Activity dated after the anchor never is. Otherwise an explicit answer
    wins; activity the check stored as contained when it was confirmed, or
    that came from the same source document, is included; anything else is
    asked. The stored set, not recording order, is what the person saw.
    Local days for the anchor use the zone stored on that anchor, not `tz`.
    """
    activity, anchor = activity_record.body, anchor_record.body
    day = anchor_day(anchor)
    _ = tz
    if activity.occurred_at is not None:
        if activity.occurred_at > anchor.as_of:
            return NOT_INCLUDED
        earlier_day = True
    else:
        if activity.occurred_on > day:
            return NOT_INCLUDED
        earlier_day = activity.occurred_on < day
    answer = dict(activity.answers).get(anchor_record.id)
    if answer is not None:
        return answer
    if isinstance(anchor, Opening):
        return INCLUDED if earlier_day else None
    contained = anchor_record.revisions[-1].contained or frozenset()
    if activity_record.id in contained or _same_source(activity_record, anchor_record):
        return INCLUDED
    return None


def dated_after(activity: Activity, anchor: Anchor, tz: ZoneInfo) -> bool:
    _ = tz
    if activity.occurred_at is not None:
        return activity.occurred_at > anchor.as_of
    return activity.occurred_on > anchor_day(anchor)


def contained_at_confirmation(
    book: Book, anchor: Observation, tz: ZoneInfo
) -> frozenset[str]:
    """What a check's preview showed as the prior recorded amount."""
    return frozenset(
        record.id
        for record in activities(book, anchor.account_id)
        if not dated_after(record.body, anchor, tz)
    )


def landed_at(record: Record, ordered: list[Record], tz: ZoneInfo) -> Optional[str]:
    index = landing(record, ordered, tz)
    return ordered[index].id if index < len(ordered) else None


def landing(record: Record, ordered: list[Record], tz: ZoneInfo) -> int:
    """Index of the first anchor that already contains the activity.

    Once a balance contains an activity, every later balance does too, so an
    activity lands in exactly one interval and is counted once.
    """
    for index, anchor in enumerate(ordered):
        answer = placement(record, anchor, tz)
        if answer is None:
            raise Unanswered(anchor.id)
        if answer == INCLUDED:
            return index
    return len(ordered)


def unanswered(record: Record, ordered: list[Record], tz: ZoneInfo) -> Optional[str]:
    try:
        landing(record, ordered, tz)
    except Unanswered as error:
        return str(error)
    return None


def contradicted(record: Record, ordered: list[Record], tz: ZoneInfo) -> list[str]:
    """Later anchors the person said did not include an activity an earlier
    anchor already contains. Both facts cannot hold, so neither may win silently."""
    answers = dict(record.body.answers)
    first = landing(record, ordered, tz)
    return [
        anchor.id
        for anchor in ordered[first + 1 :]
        if answers.get(anchor.id) == NOT_INCLUDED
    ]


def live_records(book: Book) -> list[Record]:
    return [record for record in book.records.values() if not record.removed]


def anchors(book: Book, account_id: str) -> list[Record]:
    found = [
        record
        for record in live_records(book)
        if not isinstance(record.body, Activity) and record.body.account_id == account_id
    ]
    return sorted(found, key=lambda record: (record.body.as_of, record.seq))


def activities(book: Book, account_id: str) -> list[Record]:
    return [
        record
        for record in live_records(book)
        if isinstance(record.body, Activity) and account_id in legs(record.body)
    ]


def balance(
    book: Book, account_id: str, at: Optional[datetime] = None, tz: ZoneInfo = DEFAULT_TZ
) -> Balance:
    ordered = [
        record
        for record in anchors(book, account_id)
        if at is None or record.body.as_of <= at
    ]
    moves = [
        record
        for record in activities(book, account_id)
        if at is None or _on_or_before(record.body, at, tz)
    ]
    if not ordered:
        return Unknown(sum(legs(record.body)[account_id] for record in moves))
    later = sum(
        legs(record.body)[account_id]
        for record in moves
        if landing(record, ordered, tz) == len(ordered)
    )
    last = ordered[-1]
    return Known(
        last.body.amount + later,
        last.body.as_of,
        _basis(last.body, book.accounts[account_id]),
    )


def observation_gaps(book: Book, account_id: str, tz: ZoneInfo = DEFAULT_TZ) -> list[Gap]:
    ordered = anchors(book, account_id)
    moves = activities(book, account_id)
    landed = {record.id: landing(record, ordered, tz) for record in moves}
    gaps = []
    for index, record in enumerate(ordered):
        anchor = record.body
        if not isinstance(anchor, Observation):
            continue
        if index == 0:
            gaps.append(Gap(record.id, account_id, anchor.as_of, None, None, None, ()))
            continue
        between = [move for move in moves if landed[move.id] == index]
        expected = ordered[index - 1].body.amount + sum(
            legs(move.body)[account_id] for move in between
        )
        gaps.append(
            Gap(
                record.id,
                account_id,
                anchor.as_of,
                record.revisions[-1].confirmed_difference,
                anchor.amount - expected,
                GAP_LABEL[anchor.basis],
                tuple(
                    move.id
                    for move in between
                    if move.id not in (record.revisions[-1].contained or ())
                ),
            )
        )
    return gaps


def activity_totals(
    book: Book,
    scope: Iterable[str],
    period: Optional[tuple[date, date]] = None,
    tz: ZoneInfo = DEFAULT_TZ,
) -> dict[str, Totals]:
    members = set(scope)
    sums: dict[str, dict] = {
        book.accounts[account_id].currency: _blank_sums()
        for account_id in sorted(members)
    }
    for record in live_records(book):
        activity = record.body
        if not isinstance(activity, Activity):
            continue
        if period is not None and not period[0] <= activity.occurred_on <= period[1]:
            continue
        source_in = activity.account_id in members
        counter_in = activity.counter_account_id in members
        bucket = TOTAL_BUCKET[activity.kind]
        target = sums.get(book.accounts[activity.account_id].currency)
        if target is None:
            continue
        if bucket is not None and source_in:
            name, sign = bucket
            category = category_of(book, activity) or "uncategorized"
            by_category = target[f"{name}_by_category"]
            target[name] += sign * activity.amount
            by_category[category] = by_category.get(category, 0) + sign * activity.amount
            gross = {"expense": "purchases", "refund": "refunds"}.get(activity.kind)
            if gross:
                target[gross] += activity.amount
        elif bucket is None and source_in != counter_in:
            direction = (
                "moved_out_of_scope" if source_in else "moved_in_from_outside_scope"
            )
            target[direction] += activity.amount
    return {currency: Totals(**values) for currency, values in sorted(sums.items())}


def category_of(book: Book, activity: Activity) -> Optional[str]:
    if activity.category or activity.refund_of is None:
        return activity.category
    purchase = book.records.get(activity.refund_of)
    return purchase.body.category if purchase is not None else None


def position(
    book: Book,
    scope: Iterable[str],
    at: Optional[datetime] = None,
    weighting: Weighting = "full",
    tz: ZoneInfo = DEFAULT_TZ,
) -> dict[str, Position]:
    groups: dict[str, dict] = {}
    for account_id in sorted(set(scope)):
        account = book.accounts[account_id]
        group = groups.setdefault(account.currency, _blank_group())
        if account.archived:
            group["archived"].append(account_id)
        side = "assets" if NATURE[account.type] == "asset" else "liabilities"
        current = balance(book, account_id, at, tz)
        if isinstance(current, Unknown):
            group["unknown"].append(account_id)
            group["unknown_sides"].add(side)
            continue
        share = (
            Fraction(account.ownership_share_bps, 10_000)
            if weighting == "owner_share"
            else Fraction(1)
        )
        group[side] += current.amount * share
        group["known"].append(account_id)
        group["known_sides"].add(side)
        group["as_of"].append(current.as_of)
        group["gaps"].extend(
            gap
            for gap in observation_gaps(book, account_id, tz)
            if gap.label == "unexplained" and gap.remaining
        )
    return {
        currency: Position(
            assets=_side_total(group, "assets"),
            liabilities=_side_total(group, "liabilities"),
            net=_net_total(group),
            coverage=Coverage(
                accounts_known=tuple(group["known"]),
                accounts_unknown=tuple(group["unknown"]),
                archived_included=tuple(group["archived"]),
                oldest_anchor_as_of=min(group["as_of"], default=None),
                unexplained_gaps=tuple(group["gaps"]),
            ),
        )
        for currency, group in sorted(groups.items())
    }


def standing(account: Account, current: Balance) -> str:
    if isinstance(current, Unknown):
        return "unknown"
    if NATURE[account.type] == "asset":
        return "overdrawn" if current.amount < 0 else "held"
    if current.amount == 0:
        return "settled"
    return "owed" if current.amount < 0 else "credit_in_your_favor"


def space_scope(book: Book, space_id: str) -> list[str]:
    return sorted(
        account.id for account in book.accounts.values() if account.space_id == space_id
    )


FULFILLING_KINDS: Mapping[str, frozenset] = {
    "out": frozenset({"expense", "debt_payment", "transfer"}),
    "in": frozenset({"income"}),
}


def fulfills(activity: Activity, expectation: Expectation) -> bool:
    """Derived on every read, so a changed account or kind reopens the occurrence."""
    return (
        activity.fulfills == expectation.id
        and activity.account_id == expectation.account_id
        and activity.kind in FULFILLING_KINDS[expectation.direction]
    )


def expectation_status(book: Book, expectation_id: str) -> str:
    expectation = book.expectations[expectation_id]
    fulfilled = any(
        isinstance(record.body, Activity) and fulfills(record.body, expectation)
        for record in live_records(book)
    )
    return "completed" if fulfilled else "planned"


def forecast(book: Book, scope: Iterable[str]) -> dict[str, int]:
    members = set(scope)
    totals: dict[str, int] = {}
    for expectation in book.expectations.values():
        if expectation.account_id not in members:
            continue
        if expectation_status(book, expectation.id) == "completed":
            continue
        currency = book.accounts[expectation.account_id].currency
        sign = 1 if expectation.direction == "in" else -1
        totals[currency] = totals.get(currency, 0) + sign * expectation.amount
    return dict(sorted(totals.items()))


def _same_source(first: Record, second: Record) -> bool:
    digest = (first.revisions[0].provenance.source_ref or {}).get("digest")
    other = (second.revisions[0].provenance.source_ref or {}).get("digest")
    return digest is not None and digest == other


def _on_or_before(activity: Activity, at: datetime, tz: ZoneInfo) -> bool:
    if activity.occurred_at is not None:
        return activity.occurred_at <= at
    return activity.occurred_on <= at.astimezone(tz).date()


def _basis(anchor: Anchor, account: Account) -> str:
    if isinstance(anchor, Observation):
        return anchor.basis
    return "value_estimate" if account.type in ESTIMATED_TYPES else "opening"


def _side_total(group: dict, side: str) -> Optional[int]:
    # A side whose only accounts have unknown balances is unknown, never zero.
    if side in group["unknown_sides"] and side not in group["known_sides"]:
        return None
    return round_half_up(group[side]) if group["known"] else None


def _net_total(group: dict) -> Optional[int]:
    if None in (_side_total(group, "assets"), _side_total(group, "liabilities")):
        return None
    return round_half_up(group["assets"] + group["liabilities"])


def _blank_sums() -> dict:
    return {
        "spending": 0,
        "income": 0,
        "purchases": 0,
        "refunds": 0,
        "moved_in_from_outside_scope": 0,
        "moved_out_of_scope": 0,
        "spending_by_category": {},
        "income_by_category": {},
    }


def _blank_group() -> dict:
    return {
        "assets": Fraction(0),
        "liabilities": Fraction(0),
        "known": [],
        "unknown": [],
        "archived": [],
        "known_sides": set(),
        "unknown_sides": set(),
        "as_of": [],
        "gaps": [],
    }
