"""In-memory write side of a PROPOSED financial-recording contract (test-only).

This is an executable reference model, not a production ledger. Every
operation computes a complete new state and swaps it in, so a failure leaves
nothing half written. The model has no permission logic: which accounts a
caller may see or change is outside it.
"""

import hashlib
import itertools
import json
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from tests.financial_recording.catalog import (
    CUSTOM_CATEGORY_MAX,
    NATURE,
    NICKNAME_MAX,
    PERSONAL_SPACE,
    Category,
)
from tests.financial_recording.derive import (
    DEFAULT_TZ,
    Account,
    Activity,
    Answers,
    Body,
    Book,
    Expectation,
    Observation,
    Opening,
    Provenance,
    Record,
    Revision,
    accounts_of,
    activities,
    anchors,
    contained_at_confirmation,
    landed_at,
    legs,
    live_records,
    observation_gaps,
    unanswered,
)
from tests.financial_recording.money import InvalidInput, exponent, parse_minor
from tests.financial_recording.review import (
    Issue,
    ReviewRequired,
    blocking,
    duplicates,
    issue,
    notices,
    parse_date,
    parse_fields,
    parse_instant,
    refund_issues,
    validate,
    with_trial,
)

FULL_SHARE_BPS = 10_000
TEXT_FIELDS = {
    "occurred_on": parse_date,
    "occurred_at": parse_instant,
    "as_of": parse_instant,
}
UNSET = object()


class StaleVersion(Exception):
    pass


class StalePreview(Exception):
    def __init__(self, fresh: "Preview") -> None:
        super().__init__(fresh.draft_id)
        self.fresh = fresh


class IdempotencyConflict(Exception):
    pass


@dataclass(frozen=True)
class Draft:
    id: str
    fields: Mapping[str, Optional[str]]
    provenance: Provenance
    status: Literal["proposed", "confirmed", "rejected"] = "proposed"
    revision: int = 1
    distinct: bool = False
    record_id: Optional[str] = None
    answers: Answers = ()


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


def fingerprint(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def review(
    state: State, draft: Draft, tz: ZoneInfo
) -> tuple[Optional[Body], tuple[Issue, ...]]:
    book = state.book
    body, parsed = parse_fields(draft.fields, book, draft.answers)
    found = list(parsed)
    if body is not None:
        found.extend(validate(book, body, tz, provenance=draft.provenance))
    order = list(state.drafts)
    earlier = [
        (other.id, other.fields, other.provenance)
        for other in list(state.drafts.values())[: order.index(draft.id)]
        if other.status == "proposed"
    ]
    account_id = (draft.fields.get("account_id") or "").strip()
    found.extend(
        duplicates(book, earlier, draft.provenance, account_id, body, draft.distinct)
    )
    if body is not None and not blocking(found):
        found.extend(notices(book, body, tz, draft.provenance))
    return body, tuple(found)


class Store:
    def __init__(
        self,
        clock: Callable[[], datetime],
        ids: Optional[Iterator[int]] = None,
        tz: ZoneInfo = DEFAULT_TZ,
        actor: str = "person-1",
    ) -> None:
        self.clock = clock
        self.tz = tz
        self.actor = actor
        self._ids = itertools.count(1) if ids is None else ids
        self.state = State(Book({}, {}), {}, {})

    @property
    def book(self) -> Book:
        return self.state.book

    def create_account(
        self,
        type: str,
        currency: str,
        entered: Optional[str] = None,
        *,
        idempotency_key: str,
        nickname: Optional[str] = None,
        as_of: Optional[datetime] = None,
        ownership_share_bps: int = FULL_SHARE_BPS,
        space_id: str = PERSONAL_SPACE,
    ) -> Account:
        """`entered` is what the person typed; a debt's amount owed is positive.

        This is the only place a typed amount owed becomes a negative balance.
        """
        request = [
            type,
            currency,
            entered,
            nickname,
            as_of,
            ownership_share_bps,
            space_id,
        ]
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
            space_id,
        )
        records = dict(self.book.records)
        if entered is not None and entered.strip():
            amount = parse_minor(entered, currency)
            signed = -amount if NATURE[type] == "liability" else amount
            opening = Opening(account.id, signed, as_of or now)
            record = self._new_record(opening, Provenance("manual", now), records)
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
        nickname=UNSET,
        type: Optional[str] = None,
        currency: Optional[str] = None,
        archived: Optional[bool] = None,
        ownership_share_bps: Optional[int] = None,
        linked_asset_id=UNSET,
    ) -> Account:
        account = self._fresh_account(account_id, expected_version)
        records = [
            record.body
            for record in self.book.records.values()
            if account_id in accounts_of(record.body)
        ]
        has_activity = any(isinstance(body, Activity) for body in records)
        changes: dict = {"version": account.version + 1}
        if nickname is not UNSET:
            changes["nickname"] = _nickname(nickname)
        if type is not None and type != account.type:
            if type not in NATURE:
                raise InvalidInput("account_type_unsupported", type)
            if has_activity:
                raise InvalidInput("type_locked", type)
            if records and NATURE[type] != NATURE[account.type]:
                raise InvalidInput("nature_change_requires_empty_account", type)
            changes["type"] = type
        if currency is not None and currency != account.currency:
            exponent(currency)
            if records:
                raise InvalidInput("currency_locked", currency)
            changes["currency"] = currency
        if archived is not None:
            changes["archived"] = archived
        if ownership_share_bps is not None:
            if not 1 <= ownership_share_bps <= FULL_SHARE_BPS:
                raise InvalidInput("ownership_share_invalid", str(ownership_share_bps))
            changes["ownership_share_bps"] = ownership_share_bps
        if linked_asset_id is not UNSET:
            changes["linked_asset_id"] = self._linked_asset(account, linked_asset_id)
        edited = replace(account, **changes)
        self._swap(accounts={**self.book.accounts, account_id: edited})
        return edited

    def move_account(
        self, account_id: str, expected_version: int, destination: str
    ) -> Account:
        """Organizational only: no record is created, changed or re-dated."""
        account = self._fresh_account(account_id, expected_version)
        links = self._links(account_id)
        if links:
            raise ReviewRequired([issue("account_has_links", *links)])
        moved = replace(account, space_id=destination, version=account.version + 1)
        self._swap(accounts={**self.book.accounts, account_id: moved})
        return moved

    def create_category(self, space_id: str, label: str, family: str) -> Category:
        if space_id == PERSONAL_SPACE:
            raise InvalidInput("custom_category_space", space_id)
        category = Category(self._id("cat"), family, {"custom": _label(label)}, space_id)
        self._swap(categories={**self.book.categories, category.id: category})
        return category

    def rename_category(self, category_id: str, label: str) -> Category:
        category = self.book.categories[category_id]
        if category.space_id is None:
            raise InvalidInput("default_category_fixed", category_id)
        renamed = replace(category, labels={"custom": _label(label)})
        self._swap(categories={**self.book.categories, category_id: renamed})
        return renamed

    def expect(self, account_id: str, direction: str, amount: str, due_on: date) -> str:
        account = self.book.accounts[account_id]
        expectation = Expectation(
            self._id("exp"),
            account_id,
            direction,
            parse_minor(amount, account.currency),
            due_on,
        )
        self._swap(expectations={**self.book.expectations, expectation.id: expectation})
        return expectation.id

    def draft(self, fields: Mapping[str, Optional[str]], provenance: Provenance) -> Draft:
        created = Draft(self._id("draft"), dict(fields), provenance)
        self._swap(drafts={**self.state.drafts, created.id: created})
        return created

    def edit_draft(self, draft_id: str, **fields: Optional[str]) -> Draft:
        draft = self._proposed(draft_id)
        edited = replace(
            draft, fields={**draft.fields, **fields}, revision=draft.revision + 1
        )
        self._swap(drafts={**self.state.drafts, draft_id: edited})
        return edited

    def reject(self, draft_id: str) -> Draft:
        rejected = replace(self._proposed(draft_id), status="rejected")
        self._swap(drafts={**self.state.drafts, draft_id: rejected})
        return rejected

    def resolve(
        self,
        draft_id: str,
        *,
        distinct: bool = False,
        duplicate_of: Optional[str] = None,
        answers: Optional[Mapping[str, str]] = None,
    ) -> Draft:
        draft = self._proposed(draft_id)
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
        if answers:
            changes["answers"] = _merged_answers(draft.answers, answers)
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
        working = start
        confirmed = []
        for preview in previews:
            draft = working.drafts[preview.draft_id]
            if draft.status == "confirmed":
                confirmed.append(draft.record_id)
                continue
            # Staleness is judged against the batch's starting state, so one
            # batch may carry several previews of the same account.
            if draft.revision != preview.draft_revision or any(
                start.book.accounts[account_id].version != version
                for account_id, version in preview.basis.items()
            ):
                raise StalePreview(self.preview(preview.draft_id))
            body, found = review(working, draft, self.tz)
            if blocking(found):
                raise ReviewRequired(blocking(found))
            records = dict(working.book.records)
            record = self._new_record(body, draft.provenance, records)
            records[record.id] = self._stamped(working.book, record)
            book = replace(
                working.book,
                accounts={
                    **working.book.accounts,
                    **_bumped(working.book.accounts, accounts_of(body)),
                },
                records=records,
            )
            drafts = {
                **working.drafts,
                draft.id: replace(draft, status="confirmed", record_id=record.id),
            }
            working = State(book, drafts, working.replays)
            confirmed.append(record.id)
        self.state = working
        self._swap(replay=(("confirm", idempotency_key), request, tuple(confirmed)))
        return [self.book.records[record_id] for record_id in confirmed]

    def correct(
        self,
        record_id: str,
        expected_revision: int,
        reason: str,
        *,
        accept_reordering: bool = False,
        answers: Optional[Mapping[str, str]] = None,
        **changes,
    ) -> Record:
        """A correction that moves any activity between a balance and a difference
        stops for review; `accept_reordering` records that the person saw it."""
        record = self._current(record_id, expected_revision, reason)
        currency = self.book.accounts[record.body.account_id].currency
        if "amount" in changes:
            changes["amount"] = parse_minor(changes["amount"], currency)
        for name, parser in TEXT_FIELDS.items():
            if isinstance(changes.get(name), str):
                changes[name] = parser(changes[name])
        if answers:
            changes["answers"] = _merged_answers(record.body.answers, answers)
        body = replace(record.body, **changes)
        if self.book.accounts[body.account_id].currency != currency:
            raise InvalidInput("currency_mismatch", body.account_id)
        if not isinstance(body, Activity) and body.account_id != record.body.account_id:
            raise InvalidInput("anchor_account_immutable", body.account_id)
        found = blocking(validate(self.book, body, self.tz, record_id))
        left = accounts_of(record.body) - accounts_of(body)
        trial = with_trial(self.book, body, record_id, self.tz)
        found.extend(_open_questions(trial, left, self.tz))
        found.extend(self._linked_refund_issues(record_id, body))
        only_answers = set(changes) == {"answers"}
        if not found and not accept_reordering and not only_answers:
            found.extend(self._placement_changes(record, body))
        if found:
            raise ReviewRequired(found)
        return self._revise(record, body, reason, removed=False)

    def remove(self, record_id: str, expected_revision: int, reason: str) -> Record:
        record = self._current(record_id, expected_revision, reason)
        refunds = [
            other.id
            for other in live_records(self.book)
            if isinstance(other.body, Activity) and other.body.refund_of == record_id
        ]
        if refunds:
            raise ReviewRequired([issue("linked_refunds_present", *refunds)])
        tombstone = replace(record.revisions[-1], removed=True)
        after = replace(
            self.book,
            records={
                **self.book.records,
                record_id: replace(record, revisions=(*record.revisions, tombstone)),
            },
        )
        questions = _open_questions(after, accounts_of(record.body), self.tz)
        if questions:
            raise ReviewRequired(questions)
        return self._revise(record, record.body, reason, removed=True)

    def restore(
        self,
        record_id: str,
        expected_revision: int,
        reason: str,
        *,
        answers: Optional[Mapping[str, str]] = None,
    ) -> Record:
        """Restores the original record, never a copy; both legs return together."""
        record = self.book.records[record_id]
        if len(record.revisions) != expected_revision:
            raise StaleVersion(record_id)
        if not record.removed:
            raise InvalidInput("record_not_removed", record_id)
        body = record.body
        if answers and not isinstance(body, Activity):
            raise InvalidInput("answers_not_applicable", record_id)
        if answers:
            body = replace(body, answers=_merged_answers(body.answers, answers))
        found = blocking(validate(self.book, body, self.tz, record_id))
        if found:
            raise ReviewRequired(found)
        return self._revise(record, body, reason, removed=False)

    def _linked_refund_issues(self, record_id: str, body: Body) -> list[Issue]:
        """A corrected purchase is re-checked through the same refund rule."""
        trial = with_trial(self.book, body, record_id, self.tz)
        found = []
        for other in live_records(self.book):
            refund = other.body
            if isinstance(refund, Activity) and refund.refund_of == record_id:
                account = trial.accounts[refund.account_id]
                found.extend(blocking(refund_issues(trial, refund, account, other.id)))
        return found

    def _placement_changes(self, record: Record, body: Body) -> list[Issue]:
        after = with_trial(self.book, body, record.id, self.tz)
        moved = []
        for account_id in sorted(accounts_of(record.body) | accounts_of(body)):
            before_anchors = anchors(self.book, account_id)
            after_anchors = anchors(after, account_id)
            before = {move.id: move for move in activities(self.book, account_id)}
            for move in activities(after, account_id):
                if move.id in before and landed_at(
                    before[move.id], before_anchors, self.tz
                ) != landed_at(move, after_anchors, self.tz):
                    moved.append(move.id)
        return [issue("inclusion_changed", *sorted(set(moved)))] if moved else []

    def _stamped(self, book: Book, record: Record) -> Record:
        """Stores what a balance check showed when confirmed: its contents,
        expected amount and difference. Later reads never rewrite them."""
        if not isinstance(record.body, Observation):
            return record
        last = record.revisions[-1]
        contained = (
            last.contained
            if last.contained is not None
            else contained_at_confirmation(book, record.body, self.tz)
        )
        record = replace(
            record, revisions=(*record.revisions[:-1], replace(last, contained=contained))
        )
        trial = replace(book, records={**book.records, record.id: record})
        gap = next(
            item
            for item in observation_gaps(trial, record.body.account_id, self.tz)
            if item.record_id == record.id
        )
        expected = None if gap.remaining is None else record.body.amount - gap.remaining
        revision = replace(
            record.revisions[-1],
            confirmed_expected=expected,
            confirmed_difference=gap.remaining,
        )
        return replace(record, revisions=(*record.revisions[:-1], revision))

    def _links(self, account_id: str) -> list[str]:
        found = []
        for record in self.book.records.values():
            body = record.body
            if not isinstance(body, Activity):
                continue
            touched = accounts_of(body)
            refund = self.book.records.get(body.refund_of or "")
            if refund is not None:
                touched = touched | accounts_of(refund.body)
            if account_id in touched and len(touched) > 1:
                found.append(record.id)
            if body.fulfills and account_id in touched:
                found.append(record.id)
            category = self.book.categories.get(body.category or "")
            if category is not None and category.space_id and account_id in touched:
                found.append(record.id)
        for other in self.book.accounts.values():
            if other.linked_asset_id == account_id or (
                other.id == account_id and other.linked_asset_id
            ):
                found.append(other.id)
        found.extend(
            expectation.id
            for expectation in self.book.expectations.values()
            if expectation.account_id == account_id
        )
        found.extend(
            draft.id
            for draft in self.state.drafts.values()
            if draft.status == "proposed"
            and account_id
            in {draft.fields.get("account_id"), draft.fields.get("counter_account_id")}
        )
        return sorted(set(found))

    def _linked_asset(self, account: Account, asset_id: Optional[str]) -> Optional[str]:
        if asset_id is None:
            return None
        asset = self.book.accounts.get(asset_id)
        if NATURE[account.type] != "liability" or asset is None:
            raise InvalidInput("linked_asset_invalid", str(asset_id))
        if NATURE[asset.type] != "asset":
            raise InvalidInput("linked_asset_invalid", asset_id)
        return asset_id

    def _fresh_account(self, account_id: str, expected_version: int) -> Account:
        account = self.book.accounts[account_id]
        if account.version != expected_version:
            raise StaleVersion(account_id)
        return account

    def _proposed(self, draft_id: str) -> Draft:
        draft = self.state.drafts[draft_id]
        if draft.status != "proposed":
            raise InvalidInput("draft_not_proposed", draft_id)
        return draft

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
        previous = record.revisions[-1]
        revision = replace(
            previous,
            body=body,
            recorded_at=now,
            provenance=Provenance("manual", now),
            reason=reason,
            removed=removed,
            recorded_by=self.actor,
        )
        revised = replace(record, revisions=(*record.revisions, revision))
        # Only a new amount or date re-confirms a check; a note or a restore
        # keeps the evidence the person accepted.
        if isinstance(body, Observation) and (body.amount, body.as_of) != (
            previous.body.amount,
            previous.body.as_of,
        ):
            revised = self._stamped(self.book, revised)
        touched = accounts_of(record.body) | accounts_of(body)
        self._swap(
            accounts={**self.book.accounts, **_bumped(self.book.accounts, touched)},
            records={**self.book.records, record.id: revised},
        )
        return revised

    def _new_record(
        self, body: Body, provenance: Provenance, records: Mapping[str, Record]
    ) -> Record:
        revision = Revision(body, self.clock(), provenance, recorded_by=self.actor)
        return Record(self._id("rec"), len(records) + 1, (revision,))

    def _id(self, prefix: str) -> str:
        return f"{prefix}-{next(self._ids)}"

    def _replayed(self, key: tuple[str, str], request: object) -> Optional[object]:
        seen = self.state.replays.get(key)
        if seen is None:
            return None
        if seen[0] != fingerprint(request):
            raise IdempotencyConflict(key[1])
        return seen[1]

    def _swap(
        self,
        *,
        accounts=None,
        records=None,
        drafts=None,
        categories=None,
        expectations=None,
        replay=None,
    ) -> None:
        state = self.state
        replays = dict(state.replays)
        if replay is not None:
            key, request, result = replay
            replays[key] = (fingerprint(request), result)
        changes = {
            name: value
            for name, value in (
                ("accounts", accounts),
                ("records", records),
                ("categories", categories),
                ("expectations", expectations),
            )
            if value is not None
        }
        book = replace(state.book, **changes)
        self.state = State(book, state.drafts if drafts is None else drafts, replays)


def _merged_answers(current: Answers, answers: Mapping[str, str]) -> Answers:
    for answer in answers.values():
        if answer not in ("included", "not_included"):
            raise InvalidInput("choice_invalid", answer)
    return tuple(sorted({**dict(current), **answers}.items()))


def _nickname(text: Optional[str]) -> Optional[str]:
    trimmed = (text or "").strip()
    if len(trimmed) > NICKNAME_MAX:
        raise InvalidInput("nickname_invalid", repr(text))
    return trimmed or None


def _label(text: str) -> str:
    trimmed = text.strip()
    if not 1 <= len(trimmed) <= CUSTOM_CATEGORY_MAX:
        raise InvalidInput("category_label_invalid", repr(text))
    return trimmed


def _bumped(accounts: Mapping[str, Account], touched: set[str]) -> dict[str, Account]:
    return {
        account_id: replace(
            accounts[account_id], version=accounts[account_id].version + 1
        )
        for account_id in touched
    }


def _open_questions(book: Book, account_ids: set[str], tz: ZoneInfo) -> list[Issue]:
    found = []
    for account_id in sorted(account_ids):
        ordered = anchors(book, account_id)
        for move in activities(book, account_id):
            anchor_id = unanswered(move, ordered, tz)
            if anchor_id is not None:
                found.append(issue("inclusion_unanswered", anchor_id, move.id))
    return found
