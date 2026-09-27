"""Named acceptance scenarios for the PROPOSED financial-recording reference model.

Each scenario builds a fresh store and returns its externally meaningful
results as JSON-ready data. `python -m tests.financial_recording.scenarios
--write PATH` writes all of them as the committed evidence file.
"""

import argparse
import dataclasses
import json
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
    anchors,
    balance,
    live_records,
    observation_gaps,
    position,
)
from tests.financial_recording.model import (
    Draft,
    IdempotencyConflict,
    ReviewRequired,
    StalePreview,
    StaleVersion,
    Store,
)
from tests.financial_recording.money import InvalidInput
from tests.synthetic_ingestion.extract import load_input

SAMPLES = Path(__file__).resolve().parents[1] / "synthetic_ingestion" / "samples"
EVIDENCE = (
    Path(__file__).resolve().parents[2]
    / "docs/reports/evidence/financial-recording/scenarios.json"
)


def local(day: int, hour: int = 9) -> datetime:
    return datetime(2026, 9, day, hour, tzinfo=DEFAULT_TZ)


def jsonable(value: object) -> object:
    if dataclasses.is_dataclass(value):
        return {
            item.name: jsonable(getattr(value, item.name))
            for item in dataclasses.fields(value)
        }
    if isinstance(value, date):
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
        nickname: str,
        type: str = "checking",
        currency: str = "DOP",
        opening=None,
        **options,
    ) -> Account:
        return self.store.create_account(
            nickname,
            type,
            currency,
            opening,
            idempotency_key=f"create:{nickname}",
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
        occurred_on = local(day).date().isoformat()
        return self.draft(
            kind=kind,
            account_id=account.id,
            amount=amount,
            occurred_on=occurred_on,
            **fields,
        )

    def confirm(self, draft: Draft):
        return self.store.confirm(self.store.preview(draft.id), f"confirm:{draft.id}")

    def record(self, kind: str, account: Account, amount: str, day: int, **options):
        return self.confirm(self.act(kind, account, amount, day, **options))

    def observe(self, account: Account, amount: str, day: int, basis: str = "user_check"):
        as_of = local(day, 18).isoformat()
        return self.confirm(
            self.draft(
                kind="balance_observation",
                account_id=account.id,
                amount=amount,
                as_of=as_of,
                basis=basis,
            )
        )

    def issues(self, draft: Draft) -> dict[str, str]:
        return {item.code: item.severity for item in self.store.preview(draft.id).issues}

    def balance(self, account: Account) -> object:
        return jsonable(balance(self.store.book, account.id, tz=self.store.tz))

    def amount(self, account: Account) -> int:
        return balance(self.store.book, account.id, tz=self.store.tz).amount

    def gaps(self, account: Account) -> list:
        return [
            [gap.amount, gap.label]
            for gap in observation_gaps(self.store.book, account.id, self.store.tz)
        ]

    def totals(self, *accounts: Account) -> object:
        return jsonable(
            activity_totals(
                self.store.book, [item.id for item in accounts], tz=self.store.tz
            )
        )

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


def clavito_large_opening() -> dict:
    scene = Scene()
    clavito = scene.account("Clavito", "savings", "DOP", "250000.00")
    return {"balance": scene.balance(clavito), "totals": scene.totals(clavito)}


def blank_opening_unknown() -> dict:
    scene = Scene()
    wallet = scene.account("Billetera", "cash", "DOP", "")
    before = scene.balance(wallet)
    scene.record("expense", wallet, "850.00", 3)
    return {
        "balance_before": before,
        "balance_after": scene.balance(wallet),
        "totals": scene.totals(wallet),
        "position": scene.position(wallet),
    }


def expense_beyond_known_balance() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "100.00")
    unknown = scene.account("Sobre", "cash", "DOP")
    over = scene.act("expense", cash, "150.00", 2)
    on_unknown = scene.act("expense", unknown, "40.00", 2)
    issues = {"known": scene.issues(over), "unknown": scene.issues(on_unknown)}
    return {
        "issues": issues,
        "confirm_known": outcome(lambda: scene.confirm(over)),
        "confirm_unknown": outcome(lambda: scene.confirm(on_unknown)),
        "balances": {"known": scene.balance(cash), "unknown": scene.balance(unknown)},
    }


def income_with_category() -> dict:
    scene = Scene()
    checking = scene.account("Nomina", "checking", "DOP", "1000.00")
    scene.record("income", checking, "18000.00", 2, category="remittance")
    scene.record("income", checking, "200.00", 3, category="other")
    scene.record("expense", checking, "300.00", 3, category="other")
    mismatch = scene.act("expense", checking, "50.00", 4, category="remittance")
    return {
        "mismatch_issues": scene.issues(mismatch),
        "mismatch_confirm": outcome(lambda: scene.confirm(mismatch)),
        "activity_records": scene.activity_count(),
        "totals": scene.totals(checking),
    }


def same_currency_transfer() -> dict:
    scene = Scene()
    checking = scene.account("Corriente", "checking", "DOP", "20000.00")
    savings = scene.account("Ahorro", "savings", "DOP", "1000.00")
    net_before = scene.position(checking, savings)["DOP"]["net"]
    scene.record("transfer", checking, "5000.00", 2, counter=savings)
    return {
        "balances": {
            "checking": scene.amount(checking),
            "savings": scene.amount(savings),
        },
        "net_before": net_before,
        "net_after": scene.position(checking, savings)["DOP"]["net"],
        "totals_both": scene.totals(checking, savings),
        "totals_savings_only": scene.totals(savings),
        "totals_checking_only": scene.totals(checking),
    }


def credit_card_purchase_then_payment() -> dict:
    scene = Scene()
    checking = scene.account("Corriente", "checking", "DOP", "10000.00")
    card = scene.account("Tarjeta", "credit_card", "DOP", "0.00")
    scene.record("expense", card, "3000.00", 2, category="shopping")
    after_purchase = {"card": scene.amount(card), "totals": scene.totals(checking, card)}
    scene.record("debt_payment", checking, "3000.00", 5, counter=card)
    return {
        "after_purchase": after_purchase,
        "after_payment": {
            "card": scene.amount(card),
            "checking": scene.amount(checking),
            "totals": scene.totals(checking, card),
        },
    }


def _gap_scene() -> tuple[Scene, Account, str]:
    scene = Scene()
    checking = scene.account("Corriente", "checking", "DOP", "10000.00")
    expense = scene.record("expense", checking, "2000.00", 3)
    scene.now = local(5, 19)
    scene.observe(checking, "7500.00", 5)
    return scene, checking, expense.id


def _reading(scene: Scene, account: Account) -> dict:
    totals = scene.totals(account)["DOP"]
    return {
        "balance": scene.balance(account),
        "gaps": scene.gaps(account),
        "spending": totals["spending"],
        "income": totals["income"],
    }


def observation_gap() -> dict:
    scene, checking, _ = _gap_scene()
    return _reading(scene, checking)


def _late_explanation_scene() -> tuple[Scene, Account, str]:
    scene, checking, first = _gap_scene()
    scene.now = local(6)
    scene.record("expense", checking, "500.00", 4)
    return scene, checking, first


def late_explanation() -> dict:
    scene, checking, _ = _late_explanation_scene()
    return _reading(scene, checking)


def new_expense_after_observation() -> dict:
    scene, checking, _ = _late_explanation_scene()
    scene.record("expense", checking, "500.00", 7)
    return _reading(scene, checking)


def _equal_amounts() -> tuple[Scene, Account, str, Draft, dict]:
    scene = Scene()
    first = scene.account("Efectivo", "cash", "DOP", "5000.00")
    other = scene.account("Monedero", "cash", "DOP", "5000.00")
    original = scene.record("expense", first, "500.00", 3)
    other_account = scene.act("expense", other, "500.00", 3)
    other_day = scene.act("expense", first, "500.00", 4)
    seen = {
        "different_account": scene.issues(other_account),
        "different_day": scene.issues(other_day),
    }
    scene.confirm(other_account)
    scene.confirm(other_day)
    twin = scene.act("expense", first, "500.00", 3, method="chat")
    seen["same_signature"] = scene.issues(twin)
    seen["confirm_unresolved"] = outcome(lambda: scene.confirm(twin))
    return scene, first, original.id, twin, seen


def equal_amount_not_a_match() -> dict:
    scene, first, _, twin, seen = _equal_amounts()
    scene.store.resolve(twin.id, distinct=True)
    scene.confirm(twin)
    distinct = {
        "activity_records": scene.activity_count(),
        "totals": scene.totals(first)["DOP"]["spending"],
    }
    scene, first, original, twin, _ = _equal_amounts()
    scene.store.resolve(twin.id, duplicate_of=original)
    replay = scene.confirm(twin)
    linked = {
        "activity_records": scene.activity_count(),
        "totals": scene.totals(first)["DOP"]["spending"],
        "confirm_returns": replay.id,
        "linked_methods": [
            source.method for source in scene.store.book.records[original].linked
        ],
    }
    return {**seen, "resolved_distinct": distinct, "resolved_duplicate_of": linked}


def partial_reconciliation() -> dict:
    scene = Scene()
    checking = scene.account("Corriente", "checking", "DOP", "10000.00")
    scene.observe(checking, "9500.00", 5)
    before = scene.gaps(checking)
    scene.record("expense", checking, "300.00", 3)
    return {
        "gaps_before": before,
        "gaps_after": scene.gaps(checking),
        "balance": scene.amount(checking),
    }


def backdated_correction() -> dict:
    scene, checking, expense_id = _gap_scene()
    before = scene.gaps(checking)
    scene.now = local(8)
    corrected = scene.store.correct(
        expense_id, 1, "receipt shows 2,100", amount="2100.00"
    )
    stale = outcome(lambda: scene.store.correct(expense_id, 1, "again", amount="2200.00"))
    return {
        "gaps_before": before,
        **_reading(scene, checking),
        "revisions": [
            [revision.body.amount, revision.reason] for revision in corrected.revisions
        ],
        "stale_correction": stale,
    }


def two_observations() -> dict:
    scene = Scene()
    checking = scene.account("Corriente", "checking", "DOP", "10000.00")
    scene.observe(checking, "9000.00", 5)
    scene.record("expense", checking, "300.00", 7)
    scene.observe(checking, "8500.00", 10)
    before = scene.gaps(checking)
    scene.record("expense", checking, "200.00", 8)
    return {
        "gaps_before": before,
        "gaps_after": scene.gaps(checking),
        "balance": scene.amount(checking),
    }


def _same_day(order: Optional[str]) -> dict:
    scene = Scene()
    checking = scene.account("Corriente", "checking", "DOP", "10000.00")
    scene.observe(checking, "9000.00", 5)
    draft = scene.act("expense", checking, "1000.00", 5)
    seen = {
        "issues": scene.issues(draft),
        "confirm": outcome(lambda: scene.confirm(draft)),
    }
    if order is not None:
        scene.store.resolve(draft.id, same_day_order=order)
        seen = {
            "issues": scene.issues(draft),
            "confirm": outcome(lambda: scene.confirm(draft)),
        }
    return {**seen, "gaps": scene.gaps(checking), "balance": scene.amount(checking)}


def same_day_order() -> dict:
    return {
        "unresolved": _same_day(None),
        "before": _same_day("before"),
        "after": _same_day("after"),
    }


def duplicate_submission() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    again = scene.account("Efectivo", "cash", "DOP", "1000.00")
    changed = outcome(lambda: scene.account("Efectivo", "cash", "DOP", "2000.00"))
    preview = scene.store.preview(scene.act("expense", cash, "100.00", 2).id)
    first = scene.store.confirm(preview, "k1")
    second = scene.store.confirm(preview, "k1")
    other_key = scene.store.confirm(preview, "k2")
    different = scene.store.preview(scene.act("expense", cash, "200.00", 2).id)
    return {
        "accounts": len(scene.store.book.accounts),
        "same_account_returned": again.id == cash.id,
        "create_changed_body": changed,
        "record_ids": [first.id, second.id, other_key.id],
        "same_key_different_body": outcome(lambda: scene.store.confirm(different, "k1")),
        "activity_records": scene.activity_count(),
        "balance": scene.amount(cash),
    }


def duplicate_import_vs_twins() -> dict:
    scene = Scene()
    dop = scene.account("cash-dop", "cash", "DOP", "5000.00")
    usd = scene.account("cash-usd", "cash", "USD", "300.00")
    accounts = {"cash-dop": dop.id, "cash-usd": usd.id}
    first = scene.import_file("transactions.csv", accounts)
    first_issues = {row: scene.issues(draft) for row, draft in first.items()}
    scene.store.resolve(first["tx-dop-03"].id, distinct=True)
    previews = [scene.store.preview(draft.id) for draft in first.values()]
    clean = [
        item
        for item in previews
        if not any(i.severity == "blocking" for i in item.issues)
    ]
    scene.store.confirm_batch(clean, "import:transactions.csv")
    after_first = {
        "activity_records": scene.activity_count(),
        "totals": scene.totals(dop, usd),
    }
    again = scene.import_file("transactions.csv", accounts)
    reimport = {
        "rows_already_recorded": sorted(
            row
            for row, draft in again.items()
            if "already_recorded" in scene.issues(draft)
        ),
        "confirm": outcome(
            lambda: scene.store.confirm(scene.store.preview(again["tx-dop-01"].id), "re")
        ),
        "activity_records": scene.activity_count(),
    }
    overlap = scene.import_file("overlapping.csv", accounts)
    overlap_issues = {row: scene.issues(draft) for row, draft in overlap.items()}
    scene.confirm(overlap["overlap-new"])
    return {
        "first_import_issues": first_issues,
        "confirmed_in_batch": len(clean),
        "after_first_import": after_first,
        "reimport": reimport,
        "overlap_issues": overlap_issues,
        "after_overlap": {
            "activity_records": scene.activity_count(),
            "dop_balance": scene.amount(dop),
        },
        "totals": scene.totals(dop, usd),
    }


def stale_preview_two_confirms() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    pending = scene.act("expense", cash, "100.00", 2)
    stale = scene.store.preview(pending.id)
    scene.record("expense", cash, "200.00", 2)
    attempts = [
        outcome(lambda key=key: scene.store.confirm(stale, key)) for key in ("k1", "k2")
    ]
    count_after_attempts = scene.activity_count()
    fresh = scene.store.preview(pending.id)
    confirmed = scene.store.confirm(fresh, "k1")
    return {
        "stale_attempts": attempts,
        "activity_records_after_stale": count_after_attempts,
        "fresh_confirm_record": confirmed.id,
        "activity_records": scene.activity_count(),
        "balance": scene.amount(cash),
    }


def linked_correction_and_removal() -> dict:
    scene = Scene()
    a = scene.account("Corriente", "checking", "DOP", "10000.00")
    b = scene.account("Ahorro", "savings", "DOP", "0.00")
    c = scene.account("Meta", "savings", "DOP", "0.00")

    def balances() -> list[int]:
        return [scene.amount(a), scene.amount(b), scene.amount(c)]

    transfer = scene.record("transfer", a, "1000.00", 2, counter=b)
    steps = {"recorded": balances()}
    scene.store.correct(transfer.id, 1, "amount was 1,500", amount="1500.00")
    steps["amount_corrected"] = balances()
    scene.store.correct(transfer.id, 2, "went to Meta", counter_account_id=c.id)
    steps["counter_corrected"] = balances()
    steps["stale_correction"] = outcome(
        lambda: scene.store.correct(transfer.id, 2, "late", amount="9.00")
    )
    steps["after_stale"] = balances()
    dollars = scene.account("Dolares", "savings", "USD", "0.00")
    steps["moved_to_other_currency"] = outcome(
        lambda: scene.store.correct(transfer.id, 3, "wrong", account_id=dollars.id)
    )
    removed = scene.store.remove(transfer.id, 3, "never happened")
    steps["removed"] = balances()
    steps["history"] = [
        [rev.body.amount, rev.body.counter_account_id, rev.reason, rev.removed]
        for rev in removed.revisions
    ]
    steps["versions"] = [scene.store.book.accounts[item.id].version for item in (a, b, c)]
    return steps


def multiple_precisions() -> dict:
    scene = Scene()
    yen = scene.account("Yenes", "cash", "JPY", "1500")
    dinar = scene.account("Dinares", "cash", "KWD", "1.234")
    peso = scene.account("Pesos", "cash", "DOP", "10.00")
    return {
        "yen_balance": scene.amount(yen),
        "dinar_balance": scene.amount(dinar),
        "yen_fraction_issues": scene.issues(scene.act("expense", yen, "1500.5", 2)),
        "yen_fraction_opening": outcome(
            lambda: scene.account("Yenes2", "cash", "JPY", "1500.5")
        ),
        "unknown_currency": outcome(lambda: scene.account("Raro", "cash", "ZZZ", "10")),
        "positions": {
            code: item["net"] for code, item in scene.position(yen, dinar, peso).items()
        },
    }


def overdraft_and_debt() -> dict:
    scene = Scene()
    checking = scene.account("Corriente", "checking", "DOP", "1000.00")
    loan = scene.account("Prestamo", "loan", "DOP", "-21500.00")
    card = scene.account("Tarjeta", "credit_card", "DOP", "-1000.00")
    savings = scene.account("Ahorro", "savings", "DOP", "0.00")
    overdraft = scene.act("expense", checking, "1500.00", 2)
    overdraft_issues = scene.issues(overdraft)
    scene.confirm(overdraft)
    scene.record("debt_payment", checking, "500.00", 3, counter=loan)
    scene.record("expense", card, "45.00", 4, category="interest")
    wrong_counter = scene.act("debt_payment", checking, "10.00", 5, counter=savings)
    return {
        "overdraft_issues": overdraft_issues,
        "balances": {
            "checking": scene.amount(checking),
            "loan": scene.amount(loan),
            "card": scene.amount(card),
        },
        "payment_to_asset_issues": scene.issues(wrong_counter),
        "totals": scene.totals(checking, loan, card)["DOP"]["spending_by_category"],
        "position": {
            key: value
            for key, value in scene.position(checking, loan, card)["DOP"].items()
            if key != "coverage"
        },
    }


def cross_currency_transfer_unresolved() -> dict:
    scene = Scene()
    pesos = scene.account("Pesos", "checking", "DOP", "10000.00")
    dollars = scene.account("Dolares", "savings", "USD", "100.00")
    card = scene.account("Tarjeta USD", "credit_card", "USD", "-50.00")
    transfer = scene.act("transfer", pesos, "1000.00", 2, counter=dollars)
    payment = scene.act("debt_payment", pesos, "1000.00", 2, counter=card)
    return {
        "transfer_issues": scene.issues(transfer),
        "payment_issues": scene.issues(payment),
        "confirm": outcome(lambda: scene.confirm(transfer)),
        "balances": [scene.amount(pesos), scene.amount(dollars), scene.amount(card)],
    }


def unknown_coverage_disclosure() -> dict:
    scene = Scene()
    checking = scene.account("Corriente", "checking", "DOP", "8000.00")
    wallet = scene.account("Billetera", "cash", "DOP")
    old = scene.account("Vieja", "savings", "DOP", "3000.00")
    scene.record("expense", old, "100.00", 2)
    scene.store.edit_account(old.id, 2, archived=True)
    scene.observe(checking, "7900.00", 5)
    return {
        "position": scene.position(checking, wallet, old),
        "totals": scene.totals(checking, wallet, old)["DOP"]["spending"],
    }


def asset_revaluation_and_share() -> dict:
    scene = Scene()
    car = scene.account("Carro", "property", "DOP", ownership_share_bps=5000)
    loan = scene.account(
        "Prestamo carro", "loan", "DOP", "-400000.00", ownership_share_bps=5000
    )
    scene.observe(car, "1000000.00", 1, basis="value_estimate")
    scene.observe(car, "900000.00", 20, basis="value_estimate")
    strip = ("coverage",)
    return {
        "gaps": scene.gaps(car),
        "totals": scene.totals(car, loan),
        "full": {
            k: v for k, v in scene.position(car, loan)["DOP"].items() if k not in strip
        },
        "owner_share": {
            k: v
            for k, v in scene.position(car, loan, weighting="owner_share")["DOP"].items()
            if k not in strip
        },
    }


def account_edit_rules() -> dict:
    scene = Scene()
    empty = scene.account("  Clavito  ", "savings", "DOP")
    used = scene.account("Corriente", "checking", "DOP", "100.00")
    store = scene.store
    return {
        "trimmed": empty.nickname,
        "blank_name": outcome(lambda: store.edit_account(empty.id, 1, nickname="   ")),
        "currency_on_empty": store.edit_account(empty.id, 1, currency="USD").currency,
        "currency_on_used": outcome(
            lambda: store.edit_account(used.id, 1, currency="USD")
        ),
        "nature_flip_on_used": outcome(
            lambda: store.edit_account(used.id, 1, type="credit_card")
        ),
        "same_nature_on_used": store.edit_account(used.id, 1, type="savings").type,
        "stale_version": outcome(lambda: store.edit_account(used.id, 1, nickname="Otra")),
        "archived_version": store.edit_account(used.id, 2, archived=True).version,
        "archived_draft_issues": scene.issues(scene.act("expense", used, "10.00", 2)),
    }


def first_slice_create_reopen_edit() -> dict:
    scene = Scene()
    created = scene.account("Cuenta nomina", "checking", "DOP", "12500.00")
    reopened = scene.store.book.accounts[created.id]
    opening_id = anchors(scene.store.book, created.id)[0][0]
    first = {
        "nickname": reopened.nickname,
        "version": reopened.version,
        "balance": scene.amount(reopened),
    }
    edited = scene.store.edit_account(created.id, 1, nickname=" Nomina ", type="savings")
    after_edit = {
        "nickname": edited.nickname,
        "type": edited.type,
        "version": edited.version,
        "balance": scene.amount(edited),
    }
    scene.store.correct(opening_id, 1, "bank app showed 13,000", amount="13000.00")
    return {
        "reopened": first,
        "edited": after_edit,
        "after_opening_correction": {
            "balance": scene.balance(created),
            "version": scene.store.book.accounts[created.id].version,
            "totals": scene.totals(created),
        },
    }


SCENARIOS: dict[str, Callable[[], dict]] = {
    scenario.__name__: scenario
    for scenario in (
        clavito_large_opening,
        blank_opening_unknown,
        expense_beyond_known_balance,
        income_with_category,
        same_currency_transfer,
        credit_card_purchase_then_payment,
        observation_gap,
        late_explanation,
        new_expense_after_observation,
        equal_amount_not_a_match,
        partial_reconciliation,
        backdated_correction,
        two_observations,
        same_day_order,
        duplicate_submission,
        duplicate_import_vs_twins,
        stale_preview_two_confirms,
        linked_correction_and_removal,
        multiple_precisions,
        overdraft_and_debt,
        cross_currency_transfer_unresolved,
        unknown_coverage_disclosure,
        asset_revaluation_and_share,
        account_edit_rules,
        first_slice_create_reopen_edit,
    )
}


def render() -> str:
    results = {name: scenario() for name, scenario in SCENARIOS.items()}
    return json.dumps(results, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", type=Path, required=True, help="evidence file to write"
    )
    target = parser.parse_args(argv).write
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(), encoding="utf-8")


if __name__ == "__main__":
    main()
