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
    ESTIMATED_TYPES,
    NATURE,
    NICKNAME_MAX,
    PERSONAL_SPACE,
    Category,
    signed_to_owner,
)
from tests.financial_recording.derive import (
    DEFAULT_TZ,
    FULFILLING_KINDS,
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
)
from tests.financial_recording.money import InvalidInput, exponent, parse_minor
from tests.financial_recording.review import (
    TRIAL_ID,
    Issue,
    ReviewRequired,
    blocking,
    duplicates,
    ensure_anchor_not_future,
    inclusion_issues,
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
    distinct_of: tuple[str, ...] = ()
    record_id: Optional[str] = None
    answers: Answers = ()


@dataclass(frozen=True)
class Preview:
    draft_id: str
    draft_revision: int
    basis: Mapping[str, int]
    effects: Mapping[str, int]
    issues: tuple[Issue, ...]
    check: Optional[Mapping[str, Optional[int]]] = None


@dataclass(frozen=True)
class State:
    book: Book
    drafts: Mapping[str, Draft]
    replays: Mapping[tuple[str, str], tuple[str, object]]


def fingerprint(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def review(
    state: State, draft: Draft, tz: ZoneInfo, now: Optional[datetime] = None
) -> tuple[Optional[Body], tuple[Issue, ...]]:
    book = state.book
    body, parsed = parse_fields(draft.fields, book, draft.answers, tz=tz)
    found = list(parsed)
    if body is not None:
        found.extend(validate(book, body, tz, provenance=draft.provenance, now=now))
    order = list(state.drafts)
    earlier = [
        (other.id, other.fields, other.provenance)
        for other in list(state.drafts.values())[: order.index(draft.id)]
        if other.status == "proposed"
    ]
    account_id = (draft.fields.get("account_id") or "").strip()
    found.extend(
        duplicates(
            book,
            earlier,
            draft.provenance,
            account_id,
            body,
            draft.distinct,
            _materialized_distinct_of(state, draft.distinct_of),
        )
    )
    if body is not None and not blocking(found):
        found.extend(notices(book, body, tz, draft.provenance))
    return body, tuple(found)


def _materialized_distinct_of(state: State, distinct_of: Sequence[str]) -> tuple[str, ...]:
    """Map reviewed draft ids to the records they became after confirm."""
    resolved = []
    for ref in distinct_of:
        other = state.drafts.get(ref)
        if other is not None and other.record_id is not None:
            resolved.append(other.record_id)
        else:
            resolved.append(ref)
    return tuple(resolved)


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
            # Replay returns the create-time account, not a later edit.
            return replayed
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
            stamp = as_of or now
            ensure_anchor_not_future(stamp, now)
            amount = signed_to_owner(parse_minor(entered, currency), type)
            opening = Opening(account.id, amount, stamp, zone=str(self.tz))
            record = self._new_record(opening, Provenance("manual", now), records)
            records[record.id] = record
        self._swap(
            accounts={**self.book.accounts, account.id: account},
            records=records,
            replay=(("create_account", idempotency_key), request, account),
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
            # Expectations store minor units only; forecast reads the account's
            # currency, so a plan locks currency the same way a record does.
            has_plan = any(
                expectation.account_id == account_id
                for expectation in self.book.expectations.values()
            )
            if records or has_plan:
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
        self._assert_link_natures(edited)
        self._assert_anchors_fit_type(edited)
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
        if direction not in FULFILLING_KINDS:
            raise InvalidInput("direction_unsupported", direction)
        account = self.book.accounts[account_id]
        # Direction owns the forecast sign; the typed amount must be positive.
        minor = parse_minor(amount, account.currency)
        if minor <= 0:
            raise InvalidInput("amount_not_positive", amount)
        expectation = Expectation(
            self._id("exp"),
            account_id,
            direction,
            minor,
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
            draft,
            fields={**draft.fields, **fields},
            revision=draft.revision + 1,
            distinct=False,
            distinct_of=(),
            answers=(),
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
        expected_revision: Optional[int] = None,
    ) -> Draft:
        draft = self._proposed(draft_id)
        if distinct or duplicate_of is not None or answers is not None:
            if expected_revision is None:
                raise InvalidInput("revision_required", draft_id)
            if draft.revision != expected_revision:
                raise StaleVersion(draft_id)
        elif expected_revision is not None and draft.revision != expected_revision:
            raise StaleVersion(draft_id)
        changes: dict = {"revision": draft.revision + 1}
        records = self.book.records
        if distinct:
            matches = self._live_duplicate_matches(draft)
            if not matches:
                raise InvalidInput("distinct_not_applicable", draft_id)
            changes["distinct"] = True
            changes["distinct_of"] = matches
        else:
            changes["distinct"] = draft.distinct
            changes["distinct_of"] = draft.distinct_of
        if duplicate_of is not None:
            matches = self._live_duplicate_matches(draft)
            if duplicate_of not in matches:
                raise ReviewRequired(
                    [issue("possible_duplicate", *matches)]
                    if matches
                    else [issue("duplicate_target_invalid", duplicate_of)]
                )
            # Targets are confirmed records only; draft ids appear in match
            # lists during batch review but cannot receive a source link.
            target = records.get(duplicate_of)
            if target is None:
                raise ReviewRequired(
                    [issue("duplicate_target_invalid", duplicate_of)]
                )
            linked = replace(
                draft.provenance,
                account_id=(draft.fields.get("account_id") or "").strip() or None,
            )
            records = {
                **records,
                duplicate_of: replace(target, linked=(*target.linked, linked)),
            }
            changes.update(status="confirmed", record_id=duplicate_of)
        if answers:
            changes["answers"] = _merged_answers(draft.answers, answers)
        resolved = replace(draft, **changes)
        self._swap(records=records, drafts={**self.state.drafts, draft_id: resolved})
        return resolved

    def preview(self, draft_id: str) -> Preview:
        draft = self.state.drafts[draft_id]
        body, found = review(self.state, draft, self.tz, now=self.clock())
        touched = sorted(accounts_of(body)) if body is not None else []
        effects: Mapping[str, int] = {}
        check = None
        if isinstance(body, Activity):
            effects = legs(body)
        elif isinstance(body, Observation):
            trial = with_trial(self.book, body, None, self.tz, draft.provenance)
            gap = next(
                item
                for item in observation_gaps(trial, body.account_id, self.tz)
                if item.record_id == TRIAL_ID
            )
            prior = None if gap.remaining is None else body.amount - gap.remaining
            check = {
                "prior": prior,
                "observed": body.amount,
                "difference": gap.remaining,
            }
            if gap.remaining is not None:
                effects = {body.account_id: gap.remaining}
        return Preview(
            draft_id=draft.id,
            draft_revision=draft.revision,
            basis={
                account_id: self.book.accounts[account_id].version
                for account_id in touched
                if account_id in self.book.accounts
            },
            effects=effects,
            issues=found,
            check=check,
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
            # Replay returns the confirmation-time records, not later revisions.
            return list(replayed)
        working = start
        confirmed: list[Record] = []
        for preview in previews:
            draft = working.drafts[preview.draft_id]
            if draft.status == "confirmed":
                confirmed.append(working.book.records[draft.record_id])
                continue
            if draft.status != "proposed":
                raise InvalidInput("draft_not_proposed", draft.id)
            if draft.revision != preview.draft_revision:
                raise StalePreview(self.preview(preview.draft_id))
            body, found = review(working, draft, self.tz, now=self.clock())
            # Require every touched account version from the batch's starting
            # state; an empty or partial basis must not bypass staleness.
            required = (
                accounts_of(body) & set(start.book.accounts) if body is not None else set()
            )
            if any(
                account_id not in preview.basis
                or start.book.accounts[account_id].version != preview.basis[account_id]
                for account_id in required
            ):
                raise StalePreview(self.preview(preview.draft_id))
            if blocking(found):
                raise ReviewRequired(blocking(found))
            records = dict(working.book.records)
            record = self._new_record(body, draft.provenance, records)
            stamped = self._stamped(working.book, record)
            if isinstance(body, Observation):
                # Observation confirms must carry the previewed check evidence;
                # omitting it bypasses the batch prior/difference bind.
                if preview.check is None:
                    raise StalePreview(self.preview(preview.draft_id))
                last = stamped.revisions[-1]
                shown = preview.check
                if (
                    last.confirmed_expected != shown.get("prior")
                    or last.confirmed_difference != shown.get("difference")
                    or body.amount != shown.get("observed")
                ):
                    # An earlier batch row changed the prior; re-preview.
                    saved = self.state
                    self.state = working
                    try:
                        raise StalePreview(self.preview(preview.draft_id))
                    finally:
                        self.state = saved
            records[record.id] = stamped
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
            confirmed.append(stamped)
        self.state = working
        self._swap(replay=(("confirm", idempotency_key), request, tuple(confirmed)))
        return list(confirmed)

    def correct(
        self,
        record_id: str,
        expected_revision: int,
        reason: str,
        *,
        accept_reordering: bool = False,
        answers: Optional[Mapping[str, str]] = None,
        account_basis: Optional[Mapping[str, int]] = None,
        check: Optional[Mapping[str, Optional[int]]] = None,
        **changes,
    ) -> Record:
        """A correction that moves any activity between a balance and a difference
        stops for review; `accept_reordering` records that the person saw it.

        Amount/date corrections on a check restamp confirmation evidence. Pass
        `account_basis` (touched account versions) and reviewed `check` evidence
        from the correction screen so concurrent included activity cannot rewrite
        what the person accepted. `accept_reordering` also requires `account_basis`
        for every touched account. The observation field `basis` stays in `changes`.
        """
        record = self._current(record_id, expected_revision, reason)
        currency = self.book.accounts[record.body.account_id].currency
        if "amount" in changes:
            typed = parse_minor(changes["amount"], currency)
            if isinstance(record.body, (Opening, Observation)):
                account = self.book.accounts[record.body.account_id]
                typed = signed_to_owner(typed, account.type)
            changes["amount"] = typed
        for name, parser in TEXT_FIELDS.items():
            if isinstance(changes.get(name), str):
                changes[name] = parser(changes[name])
        if "as_of" in changes and isinstance(record.body, (Opening, Observation)):
            changes["zone"] = str(self.tz)
        if isinstance(record.body, Activity) and (
            "occurred_on" in changes or "occurred_at" in changes
        ):
            changes["zone"] = str(self.tz)
        if answers and not isinstance(record.body, Activity):
            raise InvalidInput("answers_not_applicable", record_id)
        if answers:
            changes["answers"] = _merged_answers(record.body.answers, answers)
        body = replace(record.body, **changes)
        found = blocking(validate(self.book, body, self.tz, record_id, now=self.clock()))
        if (
            not isinstance(body, Activity)
            and body.account_id != record.body.account_id
            and body.account_id in self.book.accounts
        ):
            raise InvalidInput("anchor_account_immutable", body.account_id)
        target = self.book.accounts.get(body.account_id)
        if target is not None and target.currency != currency:
            raise InvalidInput("currency_mismatch", body.account_id)
        left = accounts_of(record.body) - accounts_of(body)
        trial = with_trial(self.book, body, record_id, self.tz)
        found.extend(inclusion_issues(trial, left, self.tz))
        found.extend(self._linked_refund_issues(record_id, body))
        only_answers = set(changes) == {"answers"}
        touched = accounts_of(record.body) | accounts_of(body)
        if accept_reordering:
            self._assert_reordering_basis(touched, account_basis, record_id)
        elif not found and not only_answers:
            found.extend(self._placement_changes(record, body))
        if found:
            raise ReviewRequired(found)
        will_reconfirm = isinstance(body, Observation) and _observation_needs_restamp(
            record.body, body
        )
        if will_reconfirm:
            if account_basis is None or check is None:
                raise InvalidInput("check_correction_basis_required", record_id)
            self._assert_check_correction_basis(record_id, body, account_basis, check)
        return self._revise(record, body, reason, removed=False)

    def remove(
        self,
        record_id: str,
        expected_revision: int,
        reason: str,
        *,
        accept_reordering: bool = False,
        account_basis: Optional[Mapping[str, int]] = None,
        answers: Optional[Mapping[str, Mapping[str, str]]] = None,
    ) -> Record:
        """Remove a record. When removing a check, `answers` carries
        activity_id → {check_id: included|not_included} only for questions the
        trial removal exposes against later checks."""
        record = self._current(record_id, expected_revision, reason)
        refunds = [
            other.id
            for other in live_records(self.book)
            if isinstance(other.body, Activity) and other.body.refund_of == record_id
        ]
        if refunds:
            raise ReviewRequired([issue("linked_refunds_present", *refunds)])
        if answers and isinstance(record.body, Activity):
            raise InvalidInput("answers_not_applicable", record_id)
        now = self.clock()
        scope = set(accounts_of(record.body))
        trial_tombstone = replace(record.revisions[-1], removed=True)
        trial = replace(
            self.book,
            records={
                **self.book.records,
                record_id: replace(
                    record, revisions=(*record.revisions, trial_tombstone)
                ),
            },
        )
        exposed = {
            (item.refs[1], item.refs[0])
            for item in inclusion_issues(trial, scope, self.tz)
            if item.code == "inclusion_unanswered" and len(item.refs) >= 2
        }
        records = dict(self.book.records)
        touched = set(scope)
        if answers:
            for activity_id, activity_answers in answers.items():
                target = records.get(activity_id)
                if (
                    target is None
                    or target.removed
                    or not isinstance(target.body, Activity)
                    or not activity_answers
                ):
                    raise InvalidInput("answer_target_invalid", activity_id)
                for check_id in activity_answers:
                    if (activity_id, check_id) not in exposed:
                        raise InvalidInput("answer_target_invalid", activity_id)
                new_body = replace(
                    target.body,
                    answers=_merged_answers(target.body.answers, activity_answers),
                )
                previous = target.revisions[-1]
                revised = replace(
                    target,
                    revisions=(
                        *target.revisions,
                        replace(
                            previous,
                            body=new_body,
                            recorded_at=now,
                            provenance=Provenance("manual", now),
                            reason=reason,
                            recorded_by=self.actor,
                        ),
                    ),
                )
                records[activity_id] = revised
                touched |= accounts_of(new_body)
        tombstone = replace(
            record.revisions[-1],
            removed=True,
            recorded_at=now,
            provenance=Provenance("manual", now),
            reason=reason,
            recorded_by=self.actor,
        )
        removed = replace(record, revisions=(*record.revisions, tombstone))
        records[record_id] = removed
        after = replace(self.book, records=records)
        # Validate every account the write touches, not only the removed check's.
        questions = inclusion_issues(after, touched, self.tz)
        if questions:
            raise ReviewRequired(questions)
        if accept_reordering:
            self._assert_reordering_basis(touched, account_basis, record_id)
        else:
            moved = self._placement_changes_against(after, touched)
            if moved:
                raise ReviewRequired(moved)
        self._swap(
            accounts={**self.book.accounts, **_bumped(self.book.accounts, touched)},
            records=records,
        )
        return removed

    def restore(
        self,
        record_id: str,
        expected_revision: int,
        reason: str,
        *,
        answers: Optional[Mapping[str, str]] = None,
        accept_reordering: bool = False,
        account_basis: Optional[Mapping[str, int]] = None,
    ) -> Record:
        """Restores the original record, never a copy; both legs return together."""
        record = self.book.records[record_id]
        if len(record.revisions) != expected_revision:
            raise StaleVersion(record_id)
        if not record.removed:
            raise InvalidInput("record_not_removed", record_id)
        if not reason.strip():
            raise InvalidInput("reason_required", record_id)
        body = record.body
        if answers and not isinstance(body, Activity):
            raise InvalidInput("answers_not_applicable", record_id)
        if answers:
            body = replace(body, answers=_merged_answers(body.answers, answers))
        found = blocking(validate(self.book, body, self.tz, record_id, now=self.clock()))
        if found:
            raise ReviewRequired(found)
        touched = accounts_of(record.body) | accounts_of(body)
        after = with_trial(self.book, body, record_id, self.tz)
        if accept_reordering:
            self._assert_reordering_basis(touched, account_basis, record_id)
        else:
            moved = self._placement_changes_against(after, touched)
            if moved:
                raise ReviewRequired(moved)
        return self._revise(record, body, reason, removed=False)

    def _live_duplicate_matches(self, draft: Draft) -> tuple[str, ...]:
        """Current possible_duplicate targets for this draft revision."""
        _, found = review(self.state, draft, self.tz, now=self.clock())
        for item in found:
            if item.code == "possible_duplicate":
                return item.refs
        return ()

    def _assert_link_natures(self, account: Account) -> None:
        """Debt→asset links must hold after type edits in both directions."""
        if account.linked_asset_id is not None:
            self._linked_asset(account, account.linked_asset_id)
        for other in self.book.accounts.values():
            if other.id == account.id or other.linked_asset_id != account.id:
                continue
            if NATURE[account.type] != "asset":
                raise InvalidInput("linked_asset_invalid", account.id)

    def _assert_anchors_fit_type(self, account: Account) -> None:
        """Existing openings/checks must stay valid under the account's new type."""
        for record in live_records(self.book):
            body = record.body
            if not isinstance(body, (Opening, Observation)):
                continue
            if body.account_id != account.id:
                continue
            if isinstance(body, Observation):
                estimated = account.type in ESTIMATED_TYPES
                if body.basis == "value_estimate" and not estimated:
                    raise InvalidInput("basis_not_applicable", account.type)
                if estimated and body.basis != "value_estimate":
                    raise InvalidInput("basis_not_applicable", body.basis)

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
        """Any activity whose landing relative to an account's anchors changes.

        Includes activity that leaves one account or enters another, so a
        same-currency move cannot silently rewrite a destination check.
        """
        after = with_trial(self.book, body, record.id, self.tz)
        return self._placement_changes_against(
            after, accounts_of(record.body) | accounts_of(body)
        )

    def _placement_changes_against(
        self, after: Book, account_ids: set[str]
    ) -> list[Issue]:
        """Compare landings in `self.book` vs `after` for the given accounts."""
        moved = set()
        for account_id in sorted(account_ids):
            before_anchors = anchors(self.book, account_id)
            after_anchors = anchors(after, account_id)
            before = {item.id: item for item in activities(self.book, account_id)}
            later = {item.id: item for item in activities(after, account_id)}
            for move_id in set(before) | set(later):
                before_land = (
                    landed_at(before[move_id], before_anchors, self.tz)
                    if move_id in before
                    else None
                )
                after_land = (
                    landed_at(later[move_id], after_anchors, self.tz)
                    if move_id in later
                    else None
                )
                if before_land != after_land:
                    moved.add(move_id)
        return [issue("inclusion_changed", *sorted(moved))] if moved else []

    def _stamped(self, book: Book, record: Record) -> Record:
        """Stores what a balance check showed when confirmed: its contents,
        expected amount and difference. Later reads never rewrite them."""
        if not isinstance(record.body, Observation):
            return record
        last = record.revisions[-1]
        contained = (
            last.contained
            if last.contained is not None
            else contained_at_confirmation(
                book, record.body, self.tz, check_id=record.id
            )
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

    def _assert_reordering_basis(
        self,
        account_ids: set[str],
        basis: Optional[Mapping[str, int]],
        ref: str,
    ) -> None:
        """Refuse unbound reordering after concurrent writes on touched accounts."""
        if basis is None:
            raise InvalidInput("reordering_basis_required", ref)
        required = {account_id for account_id in account_ids if account_id in self.book.accounts}
        for account_id in sorted(required):
            if account_id not in basis:
                raise StaleVersion(account_id)
        for account_id, version in basis.items():
            account = self.book.accounts.get(account_id)
            if account is None or account.version != version:
                raise StaleVersion(account_id)

    def _assert_check_correction_basis(
        self,
        record_id: str,
        body: Observation,
        basis: Mapping[str, int],
        check: Mapping[str, Optional[int]],
    ) -> None:
        """Refuse a restamp when the reviewed account state or evidence moved."""
        # The observation's own account version must be present; `{}` is not enough.
        if body.account_id not in basis:
            raise StaleVersion(body.account_id)
        for account_id, version in basis.items():
            account = self.book.accounts.get(account_id)
            if account is None or account.version != version:
                raise StaleVersion(account_id)
        # Dry-run with the real check id and sequence so same-instant anchors
        # keep the order `_revise` will stamp.
        current = self.book.records[record_id]
        placeholder = Record(
            record_id,
            current.seq,
            (
                Revision(
                    body,
                    self.clock(),
                    Provenance("manual", self.clock()),
                    contained=None,
                ),
            ),
        )
        stamped = self._stamped(self.book, placeholder)
        last = stamped.revisions[-1]
        if (
            last.confirmed_expected != check.get("prior")
            or last.confirmed_difference != check.get("difference")
            or body.amount != check.get("observed")
        ):
            raise StaleVersion(body.account_id)

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
        # Amount, instant, or stored zone changes re-confirm a check; a note or
        # restore keeps the evidence the person accepted. Zone belongs here
        # because correct() rewrites it with as_of and a TZ day-boundary shift
        # can move date-only activity into or out of the check.
        if isinstance(body, Observation) and _observation_needs_restamp(
            previous.body, body
        ):
            reconfirmed = replace(revised.revisions[-1], contained=None)
            revised = self._stamped(
                self.book, replace(revised, revisions=(*record.revisions, reconfirmed))
            )
        touched = accounts_of(record.body) | accounts_of(body)
        self._swap(
            accounts={**self.book.accounts, **_bumped(self.book.accounts, touched)},
            records={**self.book.records, record.id: revised},
        )
        return revised

    def _new_record(
        self, body: Body, provenance: Provenance, records: Mapping[str, Record]
    ) -> Record:
        # Bind external_id identity to the account at confirmation so later
        # corrections cannot retarget the source row to another account.
        bound = (
            provenance
            if provenance.account_id is not None
            else replace(provenance, account_id=body.account_id)
        )
        revision = Revision(body, self.clock(), bound, recorded_by=self.actor)
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


def _observation_needs_restamp(before: Observation, after: Observation) -> bool:
    """True when confirmation evidence must be recomputed for the new body."""
    return (after.amount, after.as_of, after.zone) != (
        before.amount,
        before.as_of,
        before.zone,
    )


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
