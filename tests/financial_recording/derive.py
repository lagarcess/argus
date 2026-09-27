"""Recorded facts and the pure reads over them (proposed contract, test-only).

Balances, gaps, totals and positions are recomputed from current revisions on
every read and never stored, so a fact supplied later explains an earlier
observation without a compensating write. A scope is a caller-supplied set of
account ids; this model has no permission logic.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from fractions import Fraction
from typing import Literal, Optional, Union
from zoneinfo import ZoneInfo

from tests.financial_recording.money import round_half_up

DEFAULT_TZ = ZoneInfo("America/Santo_Domingo")

AccountType = Literal[
    "cash",
    "checking",
    "savings",
    "investment",
    "property",
    "credit_card",
    "loan",
    "other_debt",
]
Nature = Literal["asset", "liability"]
Kind = Literal["expense", "income", "refund", "transfer", "debt_payment"]
Basis = Literal["user_check", "statement", "value_estimate"]
SameDayOrder = Literal["before", "after"]
Weighting = Literal["full", "owner_share"]

NATURE: Mapping[str, Nature] = {
    "cash": "asset",
    "checking": "asset",
    "savings": "asset",
    "investment": "asset",
    "property": "asset",
    "credit_card": "liability",
    "loan": "liability",
    "other_debt": "liability",
}
LEG_SIGNS: Mapping[str, tuple[int, Optional[int]]] = {
    "expense": (-1, None),
    "income": (1, None),
    "refund": (1, None),
    "transfer": (-1, 1),
    "debt_payment": (-1, 1),
}
TOTAL_BUCKET: Mapping[str, Optional[tuple[str, int]]] = {
    "expense": ("spending", 1),
    "refund": ("spending", -1),
    "income": ("income", 1),
    "transfer": None,
    "debt_payment": None,
}
GAP_LABEL: Mapping[str, str] = {
    "user_check": "unexplained",
    "statement": "unexplained",
    "value_estimate": "revaluation",
}


@dataclass(frozen=True)
class Account:
    id: str
    nickname: str
    type: AccountType
    currency: str
    ownership_share_bps: int
    created_at: datetime
    archived: bool = False
    version: int = 1


@dataclass(frozen=True)
class Opening:
    account_id: str
    amount: int
    as_of: datetime


@dataclass(frozen=True)
class Observation:
    account_id: str
    amount: int
    as_of: datetime
    basis: Basis


@dataclass(frozen=True)
class Activity:
    kind: Kind
    account_id: str
    amount: int
    occurred_on: date
    occurred_at: Optional[datetime] = None
    category: Optional[str] = None
    counter_account_id: Optional[str] = None
    same_day_order: Optional[SameDayOrder] = None


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


@dataclass(frozen=True)
class Record:
    id: str
    revisions: tuple[Revision, ...]
    linked: tuple[Provenance, ...] = ()

    @property
    def body(self) -> Body:
        return self.revisions[-1].body

    @property
    def removed(self) -> bool:
        return self.revisions[-1].removed


@dataclass(frozen=True)
class Book:
    accounts: Mapping[str, Account]
    records: Mapping[str, Record]


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
    amount: Optional[int]
    label: Optional[str]


@dataclass(frozen=True)
class Totals:
    spending: int
    income: int
    moved_in_from_outside_scope: int
    moved_out_of_scope: int
    spending_by_category: Mapping[str, int]
    income_by_category: Mapping[str, int]


@dataclass(frozen=True)
class Coverage:
    accounts_known: tuple[str, ...]
    accounts_unknown: tuple[str, ...]
    archived_excluded: tuple[str, ...]
    oldest_anchor_as_of: Optional[datetime]
    unexplained_gaps: tuple[Gap, ...]


@dataclass(frozen=True)
class Position:
    assets: int
    liabilities: int
    net: int
    coverage: Coverage


def legs(activity: Activity) -> dict[str, int]:
    source, counter = LEG_SIGNS[activity.kind]
    effects = {activity.account_id: source * activity.amount}
    if counter is not None and activity.counter_account_id is not None:
        effects[activity.counter_account_id] = counter * activity.amount
    return effects


def accounts_of(body: Body) -> set[str]:
    return set(legs(body)) if isinstance(body, Activity) else {body.account_id}


def order(activity: Activity, anchor: Anchor, tz: ZoneInfo) -> Optional[SameDayOrder]:
    if activity.occurred_at is not None:
        return "before" if activity.occurred_at <= anchor.as_of else "after"
    anchor_day = anchor.as_of.astimezone(tz).date()
    if activity.occurred_on != anchor_day:
        return "before" if activity.occurred_on < anchor_day else "after"
    if activity.same_day_order is not None:
        return activity.same_day_order
    # An opening starts tracking, so untimed activity on its day follows it.
    return "after" if isinstance(anchor, Opening) else None


def live_records(book: Book) -> list[Record]:
    return [record for record in book.records.values() if not record.removed]


def anchors(book: Book, account_id: str) -> list[tuple[str, Anchor]]:
    found = [
        (index, record.id, record.body)
        for index, record in enumerate(live_records(book))
        if not isinstance(record.body, Activity) and record.body.account_id == account_id
    ]
    found.sort(key=lambda item: (item[2].as_of, item[0]))
    return [(record_id, anchor) for _, record_id, anchor in found]


def activities(book: Book, account_id: str) -> list[tuple[str, Activity]]:
    return [
        (record.id, record.body)
        for record in live_records(book)
        if isinstance(record.body, Activity) and account_id in legs(record.body)
    ]


def balance(
    book: Book, account_id: str, at: Optional[datetime] = None, tz: ZoneInfo = DEFAULT_TZ
) -> Balance:
    known = [
        item for item in anchors(book, account_id) if at is None or item[1].as_of <= at
    ]
    included = [
        activity
        for _, activity in activities(book, account_id)
        if at is None or _on_or_before(activity, at, tz)
    ]
    if not known:
        return Unknown(sum(legs(activity)[account_id] for activity in included))
    anchor = known[-1][1]
    later = sum(
        legs(activity)[account_id]
        for activity in included
        if _placed(activity, anchor, tz) == "after"
    )
    return Known(anchor.amount + later, anchor.as_of, _basis(anchor))


def observation_gaps(book: Book, account_id: str, tz: ZoneInfo = DEFAULT_TZ) -> list[Gap]:
    ordered = anchors(book, account_id)
    moves = [activity for _, activity in activities(book, account_id)]
    gaps = []
    for position, (record_id, anchor) in enumerate(ordered):
        if not isinstance(anchor, Observation):
            continue
        if position == 0:
            gaps.append(Gap(record_id, account_id, anchor.as_of, None, None))
            continue
        previous = ordered[position - 1][1]
        between = sum(
            legs(activity)[account_id]
            for activity in moves
            if _placed(activity, previous, tz) == "after"
            and _placed(activity, anchor, tz) == "before"
        )
        expected = previous.amount + between
        gaps.append(
            Gap(
                record_id,
                account_id,
                anchor.as_of,
                anchor.amount - expected,
                GAP_LABEL[anchor.basis],
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
            category = activity.category or "uncategorized"
            by_category = target[f"{name}_by_category"]
            target[name] += sign * activity.amount
            by_category[category] = by_category.get(category, 0) + sign * activity.amount
        elif bucket is None and source_in != counter_in:
            direction = (
                "moved_out_of_scope" if source_in else "moved_in_from_outside_scope"
            )
            target[direction] += activity.amount
    return {currency: Totals(**values) for currency, values in sorted(sums.items())}


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
            continue
        current = balance(book, account_id, at, tz)
        if isinstance(current, Unknown):
            group["unknown"].append(account_id)
            continue
        share = (
            Fraction(account.ownership_share_bps, 10_000)
            if weighting == "owner_share"
            else Fraction(1)
        )
        side = "assets" if NATURE[account.type] == "asset" else "liabilities"
        group[side] += current.amount * share
        group["known"].append(account_id)
        group["as_of"].append(current.as_of)
        group["gaps"].extend(
            gap
            for gap in observation_gaps(book, account_id, tz)
            if gap.label == "unexplained" and gap.amount
        )
    return {
        currency: Position(
            assets=round_half_up(group["assets"]),
            liabilities=round_half_up(group["liabilities"]),
            net=round_half_up(group["assets"] + group["liabilities"]),
            coverage=Coverage(
                accounts_known=tuple(group["known"]),
                accounts_unknown=tuple(group["unknown"]),
                archived_excluded=tuple(group["archived"]),
                oldest_anchor_as_of=min(group["as_of"], default=None),
                unexplained_gaps=tuple(group["gaps"]),
            ),
        )
        for currency, group in sorted(groups.items())
    }


def _placed(activity: Activity, anchor: Anchor, tz: ZoneInfo) -> SameDayOrder:
    placed = order(activity, anchor, tz)
    if placed is None:
        raise ValueError("observation_order_unknown must be resolved at review")
    return placed


def _on_or_before(activity: Activity, at: datetime, tz: ZoneInfo) -> bool:
    if activity.occurred_at is not None:
        return activity.occurred_at <= at
    return activity.occurred_on <= at.astimezone(tz).date()


def _basis(anchor: Anchor) -> str:
    return anchor.basis if isinstance(anchor, Observation) else "opening"


def _blank_sums() -> dict:
    return {
        "spending": 0,
        "income": 0,
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
        "as_of": [],
        "gaps": [],
    }
