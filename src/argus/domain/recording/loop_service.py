"""Reviewed financial commands using one atomic repository boundary."""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4
from zoneinfo import ZoneInfo

from argus.domain.backtest_admission import canonical_hash
from argus.domain.recording.accounts import signed_to_owner
from argus.domain.recording.currency import (
    MAX_MINOR_UNITS,
    currency_exponent,
    format_minor_units,
    parse_minor_units,
)
from argus.domain.recording.errors import (
    AccountNotFound,
    RecordingInputError,
    StaleVersion,
)
from argus.domain.recording.loop import (
    CheckRecord,
    Coverage,
    ExpenseRecord,
    ExpenseRevision,
    eligible,
    expected_at,
    observations,
    position,
    validate_monotonic,
)
from argus.domain.recording.loop_schemas import (
    CATEGORY_IDS,
    ActivityRequest,
    CheckRequest,
    LoopOpeningRequest,
)
from argus.domain.recording.loop_storage import Mutation, apply
from argus.domain.recording.records import (
    OpeningRecord,
    OpeningRevision,
    _as_instant,
    _normalize_reason,
    _validate_zone,
    plan_opening_write,
)
from argus.domain.recording.schemas import _balance_response


def token(kind, account_id, record_id, request):
    body = request.model_dump(mode="json", exclude={"preview_token"})
    return canonical_hash(
        {"kind": kind, "account_id": account_id, "record_id": record_id, "request": body}
    )


def _answers(values, key):
    answers = {}
    for value in values:
        identity = getattr(value, key)
        if identity in answers:
            raise RecordingInputError(
                "coverage_duplicate", "Answer each balance question once."
            )
        answers[identity] = value.included
    return answers


def _stamp(stamp, zone, now):
    stamp = _as_instant(stamp)
    _validate_zone(zone, None)
    if stamp > now:
        raise RecordingInputError(
            "date_in_future", "The recorded date cannot be in the future."
        )
    return stamp


def _view(stored):
    b = position(stored.opening, stored.checks, stored.expenses, stored.coverage)
    if (
        b.amount_minor is not None
        and abs(b.amount_minor) > MAX_MINOR_UNITS
        or abs(b.activity_since_tracking_minor) > MAX_MINOR_UNITS
    ):
        raise RecordingInputError(
            "amount_out_of_range", "The resulting recorded amount is too large."
        )
    return _balance_response(b, stored.opening, stored.account).model_dump(mode="json")


class FinancialLoopService:
    def __init__(self, accounts, repository, clock):
        self.accounts = accounts
        self.repository = repository
        self.clock = clock

    def _current(self, user_id, account_id, expected_version):
        stored = self.accounts.get(user_id=user_id, account_id=account_id)
        if stored.account.version != expected_version:
            raise StaleVersion()
        return stored

    def preview_activity(self, *, user_id, account_id, request, record_id=None):
        stored = self._current(user_id, account_id, request.expected_version)
        _, preview = self._activity(stored, request, record_id)
        return preview

    def write_activity(
        self, *, user_id, account_id, request, idempotency_key, record_id=None
    ):
        identity = token("activity", account_id, record_id, request)

        def plan(stored):
            mutation, preview = self._activity(stored, request, record_id)
            self._confirmed(request, preview)
            return mutation

        return self.repository.mutate(
            user_id=user_id,
            account_id=account_id,
            idempotency_key=idempotency_key,
            identity_hash=identity,
            expected_version=request.expected_version,
            planner=plan,
        )

    def _activity(self, stored, request: ActivityRequest, record_id):
        now = self.clock()
        current = next((e for e in stored.expenses if e.id == record_id), None)
        if record_id and not current:
            raise AccountNotFound()
        if request.expected_revision != (current.current.revision if current else None):
            raise StaleVersion()
        amount = parse_minor_units(request.amount, stored.account.currency)
        if amount <= 0:
            raise RecordingInputError(
                "amount_positive_required", "An expense needs a positive amount."
            )
        if request.category_id is not None and request.category_id not in CATEGORY_IDS:
            raise RecordingInputError(
                "category_unknown", "Choose an available expense category."
            )
        stamp = _stamp(request.occurred_at, request.time_zone, now)
        reason = _normalize_reason(request.reason, required=current is not None)
        revision = ExpenseRevision(
            (current.current.revision if current else 0) + 1,
            amount,
            stamp,
            request.time_zone,
            (request.note or "").strip() or None,
            request.category_id,
            reason,
            stored.account.user_id,
            now,
        )
        expense = ExpenseRecord(
            current.id if current else str(uuid4()),
            stored.account.id,
            (*current.revisions, revision) if current else (revision,),
        )
        answers = _answers(request.coverage, "observation_id")
        anchors = observations(stored.opening, stored.checks)
        eligible_ids = {a.id for a in anchors if eligible(revision, a)}
        if set(answers) - eligible_ids:
            raise RecordingInputError(
                "coverage_invalid",
                "The selected balance does not cover this activity date.",
            )
        questions, links = [], []
        for anchor in anchors:
            if anchor.id not in eligible_ids:
                continue
            choice = answers.get(anchor.id)
            questions.append(
                {
                    "observation_id": anchor.id,
                    "kind": anchor.kind,
                    "as_of": anchor.as_of,
                    "amount_minor": anchor.amount_minor,
                    "amount": format_minor_units(
                        anchor.amount_minor, stored.account.currency
                    ),
                    "included": choice,
                }
            )
            if choice is not None:
                links.append(
                    Coverage(
                        anchor.id, anchor.revision, expense.id, revision.revision, choice
                    )
                )
        ready = set(answers) == eligible_ids
        mutation = Mutation(expense, tuple(links), "expense")
        after = None
        if ready:
            candidate = apply(stored, mutation, now)
            validate_monotonic(expense, anchors, candidate.coverage)
            after = _view(candidate)
        preview = {
            "account_version": stored.account.version,
            "ready": ready,
            "observations": questions,
            "before": _view(stored),
            "after": after,
            "preview_token": token("activity", stored.account.id, record_id, request)
            if ready
            else None,
        }
        return mutation, preview

    def preview_check(self, *, user_id, account_id, request):
        stored = self._current(user_id, account_id, request.expected_version)
        _, preview = self._check(stored, request)
        return preview

    def write_check(self, *, user_id, account_id, request, idempotency_key):
        def plan(stored):
            mutation, preview = self._check(stored, request)
            self._confirmed(request, preview)
            return mutation

        return self.repository.mutate(
            user_id=user_id,
            account_id=account_id,
            idempotency_key=idempotency_key,
            identity_hash=token("check", account_id, None, request),
            expected_version=request.expected_version,
            planner=plan,
        )

    def _check(self, stored, request: CheckRequest):
        now = self.clock()
        stamp = _stamp(request.as_of, request.time_zone, now)
        anchors = observations(stored.opening, stored.checks)
        zone = ZoneInfo(request.time_zone)
        if (
            anchors
            and stamp.astimezone(zone).date() < anchors[-1].as_of.astimezone(zone).date()
        ):
            raise RecordingInputError(
                "check_before_latest_observation",
                "This build records checks on or after the latest balance date.",
            )
        amount = signed_to_owner(
            parse_minor_units(request.amount, stored.account.currency),
            stored.account.type,
        )
        kind = (
            "value_update"
            if stored.account.type in {"investment", "property", "vehicle", "other_asset"}
            else "balance_check"
        )
        check = CheckRecord(
            str(uuid4()),
            stored.account.id,
            amount,
            stamp,
            request.time_zone,
            None,
            None,
            stored.account.version,
            stored.account.user_id,
            now,
            note=(request.note or "").strip() or None,
            kind=kind,
        )
        anchor = observations(None, (check,))[0]
        links = tuple(
            Coverage(check.id, 1, e.id, e.current.revision, True)
            for e in stored.expenses
            if eligible(e.current, anchor)
        )
        expected = expected_at(
            anchor,
            anchors[-1] if anchors else None,
            stored.expenses,
            (*stored.coverage, *links),
        )
        difference = None if expected is None else amount - expected
        for value in (expected, difference):
            if value is not None and abs(value) > MAX_MINOR_UNITS:
                raise RecordingInputError(
                    "amount_out_of_range", "The resulting recorded amount is too large."
                )
        check = replace(check, expected_minor=expected, difference_minor=difference)
        mutation = Mutation(check, links, "balance_check")
        _view(apply(stored, mutation, now))
        preview = {
            "account_version": stored.account.version,
            "currency": stored.account.currency,
            "currency_fraction_digits": currency_exponent(stored.account.currency),
            "expected_amount_minor": expected,
            "observed_amount_minor": amount,
            "difference_minor": difference,
            "as_of": stamp,
            "time_zone": request.time_zone,
            "preview_token": token("check", stored.account.id, None, request),
        }
        return mutation, preview

    def preview_opening(self, *, user_id, account_id, request):
        stored = self._current(user_id, account_id, request.expected_version)
        _, preview = self._opening(stored, request)
        return preview

    def write_opening(self, *, user_id, account_id, request, idempotency_key):
        def plan(stored):
            mutation, preview = self._opening(stored, request)
            self._confirmed(request, preview)
            return mutation

        return self.repository.mutate(
            user_id=user_id,
            account_id=account_id,
            idempotency_key=idempotency_key,
            identity_hash=token("opening", account_id, None, request),
            expected_version=request.expected_version,
            planner=plan,
        )

    def _opening(self, stored, request: LoopOpeningRequest):
        now = self.clock()
        current = stored.opening.current if stored.opening else None
        if request.expected_revision != (current.revision if current else None):
            raise StaleVersion()
        write = plan_opening_write(
            account_type=stored.account.type,
            currency=stored.account.currency,
            amount=request.amount,
            as_of=request.as_of,
            time_zone=request.time_zone,
            reason=request.reason,
            current=current,
            now=now,
        )
        zone = ZoneInfo(write.time_zone)
        if any(
            write.as_of.astimezone(zone).date() > c.as_of.astimezone(zone).date()
            for c in stored.checks
        ):
            raise RecordingInputError(
                "opening_after_check",
                "A starting balance cannot follow a recorded balance check.",
            )
        revision = OpeningRevision(
            (current.revision if current else 0) + 1,
            write.amount_minor,
            write.as_of,
            write.time_zone,
            write.reason,
            stored.account.user_id,
            now,
        )
        opening = OpeningRecord(
            stored.opening.id if stored.opening else str(uuid4()),
            stored.account.id,
            (*stored.opening.revisions, revision) if stored.opening else (revision,),
        )
        anchor = observations(opening, ())[0]
        answers = _answers(request.coverage, "activity_id")
        applicable = {e.id for e in stored.expenses if eligible(e.current, anchor)}
        if set(answers) - applicable:
            raise RecordingInputError(
                "coverage_invalid", "The selected activity falls after the opening date."
            )
        questions, links = [], []
        for e in stored.expenses:
            if e.id not in applicable:
                continue
            choice = answers.get(e.id)
            questions.append(
                {
                    "activity_id": e.id,
                    "amount_minor": e.current.amount_minor,
                    "amount": format_minor_units(
                        e.current.amount_minor, stored.account.currency
                    ),
                    "occurred_at": e.current.occurred_at,
                    "note": e.current.note,
                    "included": choice,
                }
            )
            if choice is not None:
                links.append(
                    Coverage(anchor.id, anchor.revision, e.id, e.current.revision, choice)
                )
        ready = set(answers) == applicable
        mutation = Mutation(opening, tuple(links), "opening_balance")
        after = None
        if ready:
            candidate = apply(stored, mutation, now)
            for e in candidate.expenses:
                validate_monotonic(
                    e, observations(opening, candidate.checks), candidate.coverage
                )
            after = _view(candidate)
        return mutation, {
            "account_version": stored.account.version,
            "ready": ready,
            "activities": questions,
            "before": _view(stored),
            "after": after,
            "preview_token": token("opening", stored.account.id, None, request)
            if ready
            else None,
        }

    @staticmethod
    def _confirmed(request, preview):
        if preview.get("ready") is False:
            raise RecordingInputError(
                "balance_coverage_required",
                "Review whether earlier activity was included in each balance.",
            )
        if request.preview_token != preview["preview_token"]:
            raise RecordingInputError(
                "preview_required", "Review the proposed change before saving it."
            )
