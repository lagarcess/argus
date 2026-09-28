"""A small driver the scenarios share, so each reads as the person's steps.

A production adapter can implement the same methods against the real API; the
scenarios and their expected outcomes then run unchanged.
"""

import dataclasses
from collections.abc import Callable, Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from tests.financial_recording.derive import (
    DEFAULT_TZ,
    Account,
    Activity,
    Provenance,
    activity_totals,
    balance,
    live_records,
    observation_gaps,
    position,
)
from tests.financial_recording.model import (
    Draft,
    IdempotencyConflict,
    StalePreview,
    StaleVersion,
    Store,
)
from tests.financial_recording.money import InvalidInput
from tests.financial_recording.review import ReviewRequired
from tests.synthetic_ingestion.extract import load_input

SAMPLES = Path(__file__).resolve().parents[1] / "synthetic_ingestion" / "samples"


def local(day: int, hour: int = 9, minute: int = 0) -> datetime:
    return datetime(2026, 9, day, hour, minute, tzinfo=DEFAULT_TZ)


def jsonable(value: object) -> object:
    if dataclasses.is_dataclass(value):
        return {
            item.name: jsonable(getattr(value, item.name))
            for item in dataclasses.fields(value)
        }
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def outcome(action: Callable[[], object]) -> str:
    try:
        action()
    except ReviewRequired as error:
        return "ReviewRequired:" + ",".join(sorted({item.code for item in error.issues}))
    except InvalidInput as error:
        return f"InvalidInput:{error.code}"
    except (StaleVersion, StalePreview, IdempotencyConflict) as error:
        return type(error).__name__
    return "ok"


class Scene:
    def __init__(self) -> None:
        self.now = local(1)
        self.store = Store(lambda: self.now)

    def account(
        self,
        name: Optional[str],
        type: str = "checking",
        currency: str = "DOP",
        entered: Optional[str] = None,
        **options,
    ) -> Account:
        as_of = options.get("as_of")
        if isinstance(as_of, datetime) and as_of > self.now:
            # Recording happens at or after the balance instant the person chose.
            self.now = as_of
        return self.store.create_account(
            type,
            currency,
            entered,
            nickname=name,
            idempotency_key=f"create:{name}:{type}:{currency}",
            **options,
        )

    def draft(
        self, method: str = "manual", source_ref: Optional[dict] = None, **fields
    ) -> Draft:
        return self.store.draft(fields, Provenance(method, self.now, source_ref))

    def act(
        self, kind: str, account: Account, amount: str, day: int, counter=None, **fields
    ) -> Draft:
        if counter is not None:
            fields["counter_account_id"] = counter.id
        return self.draft(
            kind=kind,
            account_id=account.id,
            amount=amount,
            occurred_on=local(day).date().isoformat(),
            **fields,
        )

    def confirm(self, draft: Draft):
        return self.store.confirm(self.store.preview(draft.id), f"confirm:{draft.id}")

    def record(self, kind: str, account: Account, amount: str, day: int, **options):
        return self.confirm(self.act(kind, account, amount, day, **options))

    def observation(
        self,
        account: Account,
        amount: str,
        day: int,
        basis: str = "user_check",
        hour: int = 18,
        **fields,
    ) -> Draft:
        as_of = local(day, hour)
        if as_of > self.now:
            self.now = as_of
        return self.draft(
            kind="balance_observation",
            account_id=account.id,
            amount=amount,
            as_of=as_of.isoformat(),
            basis=basis,
            **fields,
        )

    def observe(self, account: Account, amount: str, day: int, **options):
        return self.confirm(self.observation(account, amount, day, **options))

    def issues(self, draft: Draft) -> dict[str, str]:
        return {item.code: item.severity for item in self.store.preview(draft.id).issues}

    def refs(self, draft: Draft, code: str) -> list[str]:
        return [
            ref
            for item in self.store.preview(draft.id).issues
            if item.code == code
            for ref in item.refs
        ]

    def balance(self, account: Account) -> object:
        return jsonable(balance(self.store.book, account.id, tz=self.store.tz))

    def amount(self, account: Account) -> Optional[int]:
        current = balance(self.store.book, account.id, tz=self.store.tz)
        return getattr(current, "amount", None)

    def gaps(self, account: Account) -> list:
        return [
            [gap.recorded, gap.remaining, gap.label]
            for gap in observation_gaps(self.store.book, account.id, self.store.tz)
        ]

    def totals(self, *accounts: Account) -> object:
        return jsonable(
            activity_totals(
                self.store.book, [item.id for item in accounts], tz=self.store.tz
            )
        )

    def spending(self, *accounts: Account, currency: str = "DOP") -> list[int]:
        totals = self.totals(*accounts)[currency]
        return [totals["spending"], totals["income"]]

    def position(self, *accounts: Account, weighting: str = "full") -> object:
        scope = [item.id for item in accounts]
        return jsonable(
            position(self.store.book, scope, weighting=weighting, tz=self.store.tz)
        )

    def activity_count(self) -> int:
        return sum(
            isinstance(record.body, Activity) for record in live_records(self.store.book)
        )

    def import_file(self, name: str, accounts: Mapping[str, str]) -> dict[str, Draft]:
        loaded = load_input(SAMPLES / name)
        drafts = {}
        for proposal in loaded["proposals"]:
            row = proposal["fields"]
            drafts[row["source_id"]] = self.draft(
                "document",
                {**proposal["source_ref"], "external_id": row["source_id"]},
                kind=row["kind"],
                account_id=(
                    accounts.get(row["account"], row["account"])
                    if row["destination"] == "personal"
                    else ""
                ),
                amount=row["amount"],
                currency=row["currency"],
                occurred_on=row["date"],
            )
        return drafts
