"""In-memory write side of a PROPOSED financial-recording contract (test-only).

This is an executable reference model, not a production ledger. Every
operation computes a complete new State and swaps it in, so a failure leaves
nothing half written. Issues are recomputed at every review, never stored.
The model has no permission logic: which accounts a caller may see or change
is outside it.
"""

import hashlib
import itertools
import json
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from tests.financial_recording.derive import (
    DEFAULT_TZ,
    GAP_LABEL,
    LEG_SIGNS,
    NATURE,
    Account,
    Activity,
    Body,
    Book,
    Known,
    Observation,
    Opening,
    Provenance,
    Record,
    Revision,
    accounts_of,
    activities,
    anchors,
    balance,
    legs,
    live_records,
    order,
)
from tests.financial_recording.money import InvalidInput, exponent, parse_minor

NICKNAME_MAX = 60
FULL_SHARE_BPS = 10_000
LIQUID_TYPES = frozenset({"cash", "checking", "savings"})
NOTICE_CODES = frozenset({"negative_asset_balance"})
EXPENSE_CATEGORIES = frozenset(
    {"groceries", "dining", "transport", "housing", "utilities", "health"}
    | {"education", "entertainment", "shopping", "interest", "fees", "other"}
)
INCOME_CATEGORIES = frozenset(
    {"salary", "remittance", "business", "interest", "gift", "other"}
)
KIND_CATEGORIES: Mapping[str, frozenset] = {
    "expense": EXPENSE_CATEGORIES,
    "refund": EXPENSE_CATEGORIES,
    "income": INCOME_CATEGORIES,
    "transfer": frozenset(),
    "debt_payment": frozenset(),
}
COUNTER_NATURE: Mapping[str, Optional[str]] = {
    "transfer": None,
    "debt_payment": "liability",
}
REQUIRED_FIELDS: Mapping[str, tuple[str, ...]] = {
    **{kind: ("account_id", "amount", "occurred_on") for kind in LEG_SIGNS},
    "balance_observation": ("account_id", "amount", "as_of", "basis"),
}


class StaleVersion(Exception):
    pass


class StalePreview(Exception):
    pass


class IdempotencyConflict(Exception):
    pass


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str
    refs: tuple[str, ...] = ()


class ReviewRequired(Exception):
    def __init__(self, issues: Sequence[Issue]) -> None:
        super().__init__(", ".join(item.code for item in issues))
        self.issues = tuple(issues)


@dataclass(frozen=True)
class Draft:
    id: str
    fields: Mapping[str, Optional[str]]
    provenance: Provenance
    status: Literal["proposed", "confirmed"] = "proposed"
    revision: int = 1
    distinct: bool = False
    record_id: Optional[str] = None


@dataclass(frozen=True)
class Preview:
    draft_id: str
    draft_revision: int
    basis: Mapping[str, int]
    effects: Mapping[str, int]
    issues: tuple[Issue, ...]


@dataclass(frozen=True)
class State:
    book: Book
    drafts: Mapping[str, Draft]
    replays: Mapping[tuple[str, str], tuple[str, object]]


def issue(code: str, *refs: str) -> Issue:
    return Issue(code, "notice" if code in NOTICE_CODES else "blocking", refs)


def fingerprint(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def parse_fields(
    fields: Mapping[str, Optional[str]], accounts: Mapping[str, Account]
) -> tuple[Optional[Body], tuple[Issue, ...]]:
    kind = fields.get("kind") or ""
    if kind not in REQUIRED_FIELDS:
        return None, (issue("kind_unsupported", kind),)
    text = {name: (value or "").strip() for name, value in fields.items()}
    missing = tuple(name for name in REQUIRED_FIELDS[kind] if not text.get(name))
    if missing:
        return None, (issue("field_missing", *missing),)
    account = accounts.get(text["account_id"])
    if account is None:
        return None, (issue("account_unknown", text["account_id"]),)
    found: list[Issue] = []
    currency = text.get("currency") or account.currency
    if _parsed(found, exponent, currency) is not None and currency != account.currency:
        found.append(issue("currency_mismatch", currency))
    values = {
        "account_id": account.id,
        "amount": _parsed(found, parse_minor, text["amount"], account.currency),
    }
    if kind == "balance_observation":
        values["as_of"] = _parsed(found, _instant, text["as_of"])
        values["basis"] = _parsed(found, _choice, text["basis"], GAP_LABEL)
        return (None if found else Observation(**values)), tuple(found)
    values.update(
        kind=kind,
        occurred_on=_parsed(found, _date, text["occurred_on"]),
        occurred_at=_parsed(found, _instant, text.get("occurred_at")),
        same_day_order=_parsed(
            found, _choice, text.get("same_day_order"), ("before", "after")
        ),
        category=text.get("category") or None,
        counter_account_id=text.get("counter_account_id") or None,
    )
    return (None if found else Activity(**values)), tuple(found)


def validate(book: Book, body: Body, tz: ZoneInfo) -> list[Issue]:
    unusable = [
        issue(
            "account_archived" if account_id in book.accounts else "account_unknown",
            account_id,
        )
        for account_id in sorted(accounts_of(body))
        if account_id not in book.accounts or book.accounts[account_id].archived
    ]
    if unusable:
        return unusable
    if isinstance(body, Activity):
        return _activity_issues(book, body, tz)
    if isinstance(body, Observation):
        return [
            issue("observation_order_unknown", record_id)
            for record_id, activity in activities(book, body.account_id)
            if order(activity, body, tz) is None
        ]
    return []


def review(
    state: State, draft: Draft, tz: ZoneInfo
) -> tuple[Optional[Body], tuple[Issue, ...]]:
    body, parsed = parse_fields(draft.fields, state.book.accounts)
    found = [*parsed, *(validate(state.book, body, tz) if body is not None else ())]
    found.extend(_duplicates(state, draft, body))
    if body is not None and not any(item.severity == "blocking" for item in found):
        found.extend(_notices(state.book, body, tz))
    return body, tuple(found)


def _activity_issues(book: Book, body: Activity, tz: ZoneInfo) -> list[Issue]:
    found = [issue("amount_not_positive")] if body.amount <= 0 else []
    if body.category and body.category not in EXPENSE_CATEGORIES | INCOME_CATEGORIES:
        found.append(issue("category_unknown", body.category))
    elif body.category and body.category not in KIND_CATEGORIES[body.kind]:
        found.append(issue("category_kind_mismatch", body.category))
    needs_counter = body.kind in COUNTER_NATURE
    counter = book.accounts.get(body.counter_account_id or "")
    if needs_counter and counter is None:
        found.append(issue("counter_account_missing"))
    elif not needs_counter and body.counter_account_id:
        found.append(issue("counter_account_unexpected", body.counter_account_id))
    elif needs_counter:
        if counter.currency != book.accounts[body.account_id].currency:
            found.append(issue("cross_currency_unresolved", counter.id))
        wanted = COUNTER_NATURE[body.kind]
        if wanted is not None and NATURE[counter.type] != wanted:
            found.append(issue("counter_not_liability", counter.id))
    found.extend(
        issue("observation_order_unknown", record_id)
        for account_id in sorted(accounts_of(body))
        for record_id, anchor in anchors(book, account_id)
        if isinstance(anchor, Observation) and order(body, anchor, tz) is None
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


def _signature(body: Optional[Body]) -> Optional[tuple]:
    if not isinstance(body, Activity):
        return None
    return (body.account_id, body.amount, body.occurred_on, body.kind)


def _duplicates(state: State, draft: Draft, body: Optional[Body]) -> list[Issue]:
    # Only drafts created earlier count as existing, so a later import never
    # re-flags the rows it duplicates.
    earlier = list(state.drafts.values())[: list(state.drafts).index(draft.id)]
    existing = [
        (
            record.id,
            record.body,
            record.body.account_id,
            (record.revisions[0].provenance, *record.linked),
        )
        for record in live_records(state.book)
    ] + [
        (
            other.id,
            parse_fields(other.fields, state.book.accounts)[0],
            (other.fields.get("account_id") or "").strip(),
            (other.provenance,),
        )
        for other in earlier
        if other.status == "proposed"
    ]
    mine = _identities(draft.provenance, (draft.fields.get("account_id") or "").strip())
    same_source = [
        item_id
        for item_id, _, account_id, sources in existing
        if any(mine & _identities(source, account_id) for source in sources)
    ]
    if same_source:
        return [issue("already_recorded", *same_source)]
    signature = _signature(body)
    if signature is None or draft.distinct:
        return []
    matches = [
        item_id
        for item_id, item_body, _, _ in existing
        if _signature(item_body) == signature
    ]
    return [issue("possible_duplicate", *matches)] if matches else []


def _notices(book: Book, body: Body, tz: ZoneInfo) -> list[Issue]:
    trial_revision = Revision(body, _EPOCH, Provenance("manual", _EPOCH))
    trial = Book(
        book.accounts, {**book.records, "trial": Record("trial", (trial_revision,))}
    )
    after = {
        account_id: balance(trial, account_id, tz=tz) for account_id in accounts_of(body)
    }
    return [
        issue("negative_asset_balance", account_id)
        for account_id, current in sorted(after.items())
        if book.accounts[account_id].type in LIQUID_TYPES
        and isinstance(current, Known)
        and current.amount < 0
    ]


def _parsed(found: list[Issue], parser: Callable, text: Optional[str], *args):
    if not text:
        return None
    try:
        return parser(text, *args)
    except InvalidInput as error:
        found.append(issue(error.code, text))
        return None


def _date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as error:
        raise InvalidInput("date_invalid", text) from error


def _instant(text: str) -> datetime:
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


def _nickname(text: str) -> str:
    trimmed = text.strip()
    if not 1 <= len(trimmed) <= NICKNAME_MAX:
        raise InvalidInput("nickname_invalid", repr(text))
    return trimmed


_EPOCH = datetime.fromisoformat("1970-01-01T00:00:00+00:00")


class Store:
    def __init__(
        self,
        clock: Callable[[], datetime],
        ids: Optional[Iterator[int]] = None,
        tz: ZoneInfo = DEFAULT_TZ,
    ) -> None:
        self.clock = clock
        self.tz = tz
        self._ids = itertools.count(1) if ids is None else ids
        self.state = State(Book({}, {}), {}, {})

    @property
    def book(self) -> Book:
        return self.state.book

    def create_account(
        self,
        nickname: str,
        type: str,
        currency: str,
        opening: Optional[str] = None,
        *,
        idempotency_key: str,
        as_of: Optional[datetime] = None,
        ownership_share_bps: int = FULL_SHARE_BPS,
    ) -> Account:
        request = [nickname, type, currency, opening, as_of, ownership_share_bps]
        replayed = self._replayed(("create_account", idempotency_key), request)
        if replayed is not None:
            return self.book.accounts[replayed]
        if type not in NATURE:
            raise InvalidInput("account_type_unsupported", type)
        if not 1 <= ownership_share_bps <= FULL_SHARE_BPS:
            raise InvalidInput("ownership_share_invalid", str(ownership_share_bps))
        exponent(currency)
        now = self.clock()
        account = Account(
            self._id("acct"),
            _nickname(nickname),
            type,
            currency,
            ownership_share_bps,
            now,
        )
        records = dict(self.book.records)
        if opening is not None and opening.strip():
            anchor = Opening(account.id, parse_minor(opening, currency), as_of or now)
            record = self._new_record(anchor, Provenance("manual", now))
            records[record.id] = record
        self._swap(
            accounts={**self.book.accounts, account.id: account},
            records=records,
            replay=(("create_account", idempotency_key), request, account.id),
        )
        return account

    def edit_account(
        self,
        account_id: str,
        expected_version: int,
        *,
        nickname: Optional[str] = None,
        type: Optional[str] = None,
        currency: Optional[str] = None,
        archived: Optional[bool] = None,
    ) -> Account:
        account = self.book.accounts[account_id]
        if account.version != expected_version:
            raise StaleVersion(account_id)
        in_use = any(
            account_id in accounts_of(revision.body)
            for record in self.book.records.values()
            for revision in record.revisions
        )
        changes: dict = {"version": account.version + 1}
        if nickname is not None:
            changes["nickname"] = _nickname(nickname)
        if type is not None:
            if type not in NATURE:
                raise InvalidInput("account_type_unsupported", type)
            if in_use and NATURE[type] != NATURE[account.type]:
                raise InvalidInput("nature_change_requires_empty_account", type)
            changes["type"] = type
        if currency is not None and currency != account.currency:
            exponent(currency)
            if in_use:
                raise InvalidInput("currency_locked", currency)
            changes["currency"] = currency
        if archived is not None:
            changes["archived"] = archived
        edited = replace(account, **changes)
        self._swap(accounts={**self.book.accounts, account_id: edited})
        return edited

    def draft(self, fields: Mapping[str, Optional[str]], provenance: Provenance) -> Draft:
        created = Draft(self._id("draft"), dict(fields), provenance)
        self._swap(drafts={**self.state.drafts, created.id: created})
        return created

    def resolve(
        self,
        draft_id: str,
        *,
        distinct: bool = False,
        duplicate_of: Optional[str] = None,
        same_day_order: Optional[str] = None,
    ) -> Draft:
        draft = self.state.drafts[draft_id]
        if draft.status != "proposed":
            raise InvalidInput("draft_not_proposed", draft_id)
        changes: dict = {
            "revision": draft.revision + 1,
            "distinct": draft.distinct or distinct,
        }
        records = self.book.records
        if duplicate_of is not None:
            target = records[duplicate_of]
            records = {
                **records,
                duplicate_of: replace(target, linked=(*target.linked, draft.provenance)),
            }
            changes.update(status="confirmed", record_id=duplicate_of)
        if same_day_order is not None:
            changes["fields"] = {**draft.fields, "same_day_order": same_day_order}
        resolved = replace(draft, **changes)
        self._swap(records=records, drafts={**self.state.drafts, draft_id: resolved})
        return resolved

    def preview(self, draft_id: str) -> Preview:
        draft = self.state.drafts[draft_id]
        body, found = review(self.state, draft, self.tz)
        touched = sorted(accounts_of(body)) if body is not None else []
        return Preview(
            draft_id=draft.id,
            draft_revision=draft.revision,
            basis={
                account_id: self.book.accounts[account_id].version
                for account_id in touched
                if account_id in self.book.accounts
            },
            effects=legs(body) if isinstance(body, Activity) else {},
            issues=found,
        )

    def confirm(self, preview: Preview, idempotency_key: str) -> Record:
        return self.confirm_batch([preview], idempotency_key)[0]

    def confirm_batch(
        self, previews: Sequence[Preview], idempotency_key: str
    ) -> list[Record]:
        start = self.state
        request = [
            [item.draft_id, start.drafts[item.draft_id].fields] for item in previews
        ]
        replayed = self._replayed(("confirm", idempotency_key), request)
        if replayed is not None:
            return [self.book.records[record_id] for record_id in replayed]
        accounts, records = dict(start.book.accounts), dict(start.book.records)
        drafts = dict(start.drafts)
        confirmed = []
        for preview in previews:
            draft = drafts[preview.draft_id]
            if draft.status == "confirmed":
                confirmed.append(draft.record_id)
                continue
            # Staleness is judged against the batch's starting state, so one
            # batch may carry several previews of the same account.
            if draft.revision != preview.draft_revision or any(
                start.book.accounts[account_id].version != version
                for account_id, version in preview.basis.items()
            ):
                raise StalePreview(preview.draft_id)
            working = State(Book(accounts, records), drafts, start.replays)
            body, found = review(working, draft, self.tz)
            blocking = [item for item in found if item.severity == "blocking"]
            if blocking:
                raise ReviewRequired(blocking)
            record = self._new_record(body, draft.provenance)
            records[record.id] = record
            accounts.update(_bumped(accounts, accounts_of(body)))
            drafts[draft.id] = replace(draft, status="confirmed", record_id=record.id)
            confirmed.append(record.id)
        self._swap(
            accounts=accounts,
            records=records,
            drafts=drafts,
            replay=(("confirm", idempotency_key), request, tuple(confirmed)),
        )
        return [records[record_id] for record_id in confirmed]

    def correct(
        self, record_id: str, expected_revision: int, reason: str, **changes
    ) -> Record:
        record = self._current(record_id, expected_revision, reason)
        if "amount" in changes:
            account = self.book.accounts[
                changes.get("account_id", record.body.account_id)
            ]
            changes["amount"] = parse_minor(changes["amount"], account.currency)
        body = replace(record.body, **changes)
        currency = self.book.accounts[record.body.account_id].currency
        if self.book.accounts[body.account_id].currency != currency:
            raise InvalidInput("currency_mismatch", body.account_id)
        others = {
            key: value for key, value in self.book.records.items() if key != record_id
        }
        found = validate(Book(self.book.accounts, others), body, self.tz)
        if found:
            raise ReviewRequired(found)
        return self._revise(record, body, reason, removed=False)

    def remove(self, record_id: str, expected_revision: int, reason: str) -> Record:
        record = self._current(record_id, expected_revision, reason)
        return self._revise(record, record.body, reason, removed=True)

    def _current(self, record_id: str, expected_revision: int, reason: str) -> Record:
        record = self.book.records[record_id]
        if len(record.revisions) != expected_revision:
            raise StaleVersion(record_id)
        if record.removed:
            raise InvalidInput("record_removed", record_id)
        if not reason.strip():
            raise InvalidInput("reason_required", record_id)
        return record

    def _revise(
        self, record: Record, body: Body, reason: str, *, removed: bool
    ) -> Record:
        now = self.clock()
        revision = Revision(body, now, Provenance("manual", now), reason, removed)
        revised = replace(record, revisions=(*record.revisions, revision))
        touched = accounts_of(record.body) | accounts_of(body)
        self._swap(
            accounts={**self.book.accounts, **_bumped(self.book.accounts, touched)},
            records={**self.book.records, record.id: revised},
        )
        return revised

    def _new_record(self, body: Body, provenance: Provenance) -> Record:
        return Record(self._id("rec"), (Revision(body, self.clock(), provenance),))

    def _id(self, prefix: str) -> str:
        return f"{prefix}-{next(self._ids)}"

    def _replayed(self, key: tuple[str, str], request: object) -> Optional[object]:
        seen = self.state.replays.get(key)
        if seen is None:
            return None
        if seen[0] != fingerprint(request):
            raise IdempotencyConflict(key[1])
        return seen[1]

    def _swap(self, *, accounts=None, records=None, drafts=None, replay=None) -> None:
        state = self.state
        replays = dict(state.replays)
        if replay is not None:
            key, request, result = replay
            replays[key] = (fingerprint(request), result)
        book = Book(
            state.book.accounts if accounts is None else accounts,
            state.book.records if records is None else records,
        )
        self.state = State(book, state.drafts if drafts is None else drafts, replays)


def _bumped(accounts: Mapping[str, Account], touched: set[str]) -> dict[str, Account]:
    return {
        account_id: replace(
            accounts[account_id], version=accounts[account_id].version + 1
        )
        for account_id in touched
    }
