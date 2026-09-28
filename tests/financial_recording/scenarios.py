"""Named acceptance scenarios for the PROPOSED financial-recording reference model.

Each scenario builds a fresh store and returns its externally meaningful
results as JSON-ready data. `python -m tests.financial_recording.scenarios
--write PATH` writes all of them as the committed evidence file.
"""

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Optional

from tests.financial_recording import scenarios_lifecycle
from tests.financial_recording.catalog import DEFAULT_CATEGORIES
from tests.financial_recording.derive import anchors, observation_gaps
from tests.financial_recording.scenes import Scene, jsonable, local, outcome

EVIDENCE = (
    Path(__file__).resolve().parents[2]
    / "docs/reports/evidence/financial-recording/scenarios.json"
)


def clavito_large_opening() -> dict:
    scene = Scene()
    clavito = scene.account("Clavito", "savings", "DOP", "250000.00")
    return {"balance": scene.balance(clavito), "totals": scene.totals(clavito)}


def blank_opening_unknown() -> dict:
    scene = Scene()
    wallet = scene.account(None, "cash", "DOP")
    before = scene.balance(wallet)
    scene.record("expense", wallet, "850.00", 2)
    return {
        "nickname": wallet.nickname,
        "balance_before": before,
        "balance_after": scene.balance(wallet),
        "totals": scene.totals(wallet),
        "position": scene.position(wallet),
    }


def expense_beyond_known_balance() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "100.00")
    unknown = scene.account("Billetera", "cash", "DOP")
    known_draft = scene.act("expense", cash, "150.00", 2)
    unknown_draft = scene.act("expense", unknown, "40.00", 2)
    issues = {"known": scene.issues(known_draft), "unknown": scene.issues(unknown_draft)}
    return {
        "issues": issues,
        "confirm_known": outcome(lambda: scene.confirm(known_draft)),
        "confirm_unknown": outcome(lambda: scene.confirm(unknown_draft)),
        "balances": {"known": scene.balance(cash), "unknown": scene.balance(unknown)},
    }


def income_with_category() -> dict:
    scene = Scene()
    checking = scene.account("Nomina", "checking", "DOP", "1000.00")
    savings = scene.account("Ahorro", "savings", "DOP", "0.00")
    scene.record("income", checking, "18000.00", 2, category="remittance")
    scene.record("expense", checking, "300.00", 3)
    wrong_family = scene.act("expense", checking, "50.00", 3, category="salary")
    on_transfer = scene.act(
        "transfer", checking, "60.00", 3, counter=savings, category="groceries"
    )
    return {
        "totals": scene.totals(checking),
        "category_on_wrong_kind": scene.issues(wrong_family),
        "category_on_transfer": scene.issues(on_transfer),
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
        "to_same_account": scene.issues(
            scene.act("transfer", checking, "50.00", 3, counter=checking)
        ),
    }


def credit_card_purchase_then_payment() -> dict:
    scene = Scene()
    checking = scene.account("Corriente", "checking", "DOP", "10000.00")
    card = scene.account("Tarjeta", "credit_card", "DOP", "0.00")
    scene.record("expense", card, "3000.00", 2, category="shopping")
    after_purchase = {"card": scene.amount(card), "totals": scene.totals(checking, card)}
    payment = scene.record("debt_payment", checking, "3000.00", 5, counter=card)
    statement_row = scene.act("refund", card, "3000.00", 5, method="document")
    return {
        "after_purchase": after_purchase,
        "after_payment": {
            "card": scene.amount(card),
            "checking": scene.amount(checking),
            "totals": scene.totals(checking, card),
        },
        "card_statement_payment_row": {
            "issues": scene.issues(statement_row),
            "matches": scene.refs(statement_row, "possible_duplicate"),
            "payment_record": payment.id,
        },
    }


def _gap_scene() -> tuple[Scene, object, object, str]:
    scene = Scene()
    checking = scene.account("Corriente", "checking", "DOP", "10000.00")
    expense = scene.record("expense", checking, "2000.00", 3)
    scene.now = local(5, 19)
    check = scene.observe(checking, "7500.00", 5)
    return scene, checking, check, expense.id


def _reading(scene: Scene, account) -> dict:
    spending, income = scene.spending(account)
    return {
        "balance": scene.amount(account),
        "gaps": scene.gaps(account),
        "spending": spending,
        "income": income,
    }


def observation_gap() -> dict:
    scene, checking, check, _ = _gap_scene()
    audit = check.revisions[-1]
    return {
        **_reading(scene, checking),
        "shown_at_confirmation": [audit.confirmed_expected, audit.confirmed_difference],
    }


def _late_expense(answer: Optional[str]) -> tuple[Scene, object, dict]:
    scene, checking, check, _ = _gap_scene()
    scene.now = local(6)
    late = scene.act("expense", checking, "500.00", 4)
    seen = {
        "asked_about_the_check": scene.refs(late, "inclusion_unanswered")[:1]
        == [check.id],
        "confirm_unanswered": outcome(lambda: scene.confirm(late)),
    }
    if answer is not None:
        scene.store.resolve(late.id, answers={check.id: answer})
        record = scene.confirm(late)
        gap = observation_gaps(scene.store.book, checking.id, scene.store.tz)[0]
        seen["explained_by_late_record"] = list(gap.explained_by) == [record.id]
    return scene, checking, seen


def late_explanation() -> dict:
    scene, checking, seen = _late_expense("included")
    other_scene, other_checking, other_seen = _late_expense("not_included")
    return {
        **seen,
        **_reading(scene, checking),
        "answered_not_included": {
            **_reading(other_scene, other_checking),
            "explained_by_late_record": other_seen["explained_by_late_record"],
        },
    }


def new_expense_after_observation() -> dict:
    scene, checking, _ = _late_expense("included")
    later = scene.act("expense", checking, "500.00", 7)
    questions = scene.refs(later, "inclusion_unanswered")
    scene.confirm(later)
    return {"questions": questions, **_reading(scene, checking)}


def _equal_amounts() -> tuple[Scene, object, str, object, dict]:
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
        "spending": scene.spending(first)[0],
    }
    scene, first, original, twin, _ = _equal_amounts()
    scene.store.resolve(twin.id, duplicate_of=original)
    replay = scene.confirm(twin)
    linked = {
        "activity_records": scene.activity_count(),
        "spending": scene.spending(first)[0],
        "confirm_returns_the_existing_record": replay.id == original,
        "linked_methods": [
            source.method for source in scene.store.book.records[original].linked
        ],
    }
    return {**seen, "resolved_distinct": distinct, "resolved_duplicate_of": linked}


def partial_reconciliation() -> dict:
    scene = Scene()
    checking = scene.account("Corriente", "checking", "DOP", "10000.00")
    check = scene.observe(checking, "9500.00", 5)
    before = scene.gaps(checking)
    part = scene.act("expense", checking, "300.00", 3)
    scene.store.resolve(part.id, answers={check.id: "included"})
    scene.confirm(part)
    return {
        "gaps_before": before,
        "gaps_after": scene.gaps(checking),
        "balance": scene.amount(checking),
    }


def backdated_correction() -> dict:
    scene, checking, _, expense_id = _gap_scene()
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
            [revision.body.amount, revision.reason, revision.recorded_by]
            for revision in corrected.revisions
        ],
        "stale_correction": stale,
    }


def two_observations() -> dict:
    scene = Scene()
    checking = scene.account("Corriente", "checking", "DOP", "10000.00")
    scene.observe(checking, "9000.00", 5)
    scene.record("expense", checking, "300.00", 7)
    second = scene.observe(checking, "8500.00", 10)
    before = scene.gaps(checking)
    between = scene.act("expense", checking, "200.00", 8)
    asked = scene.refs(between, "inclusion_unanswered")[:1] == [second.id]
    scene.store.resolve(between.id, answers={second.id: "included"})
    scene.confirm(between)
    return {
        "gaps_before": before,
        "asked_only_the_later_check": asked,
        "gaps_after": scene.gaps(checking),
        "balance": scene.amount(checking),
    }


def older_activity_inclusion() -> dict:
    return {
        "same_day_after_timed_check": _same_day_check(),
        "older_than_two_checks": _older_than_two_checks(),
        "transfer_answers_each_leg": _transfer_per_leg(),
        "statement_rows_answer_from_source": _statement_source(),
        "same_day_as_opening": _same_day_opening(),
    }


def _same_day_check() -> dict:
    results = {}
    for answer in ("included", "not_included"):
        scene = Scene()
        checking = scene.account("Corriente", "checking", "DOP", "10000.00")
        check = scene.observe(checking, "9000.00", 5)
        purchase = scene.act("expense", checking, "1000.00", 5)
        asked = scene.refs(purchase, "inclusion_unanswered")[:1] == [check.id]
        scene.store.resolve(purchase.id, answers={check.id: answer})
        scene.confirm(purchase)
        results[answer] = {
            "asked": asked,
            "gaps": scene.gaps(checking),
            "balance": scene.amount(checking),
        }
    return results


def _older_than_two_checks() -> dict:
    scene = Scene()
    checking = scene.account("Corriente", "checking", "DOP", "10000.00")
    first = scene.observe(checking, "10000.00", 5)
    second = scene.observe(checking, "9000.00", 10)
    old = scene.act("expense", checking, "1000.00", 3)
    first_question = scene.refs(old, "inclusion_unanswered")[:1]
    scene.store.resolve(old.id, answers={first.id: "not_included"})
    second_question = scene.refs(old, "inclusion_unanswered")[:1]
    scene.store.resolve(old.id, answers={second.id: "included"})
    confirm = outcome(lambda: scene.confirm(old))
    return {
        "questions_in_date_order": [first_question, second_question]
        == [[first.id], [second.id]],
        "confirm": confirm,
        "gaps": scene.gaps(checking),
        "balance": scene.amount(checking),
    }


def _transfer_per_leg() -> dict:
    scene = Scene()
    checking = scene.account("Corriente", "checking", "DOP", "10000.00")
    savings = scene.account("Ahorro", "savings", "DOP", "5000.00")
    checking_check = scene.observe(checking, "9000.00", 5)
    savings_check = scene.observe(savings, "5000.00", 5)
    move = scene.act("transfer", checking, "1000.00", 3, counter=savings)
    first = scene.refs(move, "inclusion_unanswered")[:1]
    scene.store.resolve(move.id, answers={checking_check.id: "included"})
    second = scene.refs(move, "inclusion_unanswered")[:1]
    scene.store.resolve(move.id, answers={savings_check.id: "not_included"})
    scene.confirm(move)
    return {
        "one_question_per_leg": [first, second]
        == [[checking_check.id], [savings_check.id]],
        "balances": [scene.amount(checking), scene.amount(savings)],
        "gaps": [scene.gaps(checking), scene.gaps(savings)],
    }


def _statement_source() -> dict:
    scene = Scene()
    checking = scene.account("Corriente", "checking", "DOP", "10000.00")
    statement = {"digest": "synthetic-statement-1"}
    close = scene.draft(
        "document",
        {**statement, "row": 0},
        kind="balance_observation",
        account_id=checking.id,
        amount="9500.00",
        as_of=local(5, 23, 59).isoformat(),
        basis="statement",
    )
    scene.confirm(close)
    row = scene.draft(
        "document",
        {**statement, "row": 1},
        kind="expense",
        account_id=checking.id,
        amount="500.00",
        occurred_on=local(4).date().isoformat(),
    )
    return {
        "row_issues": scene.issues(row),
        "confirm": outcome(lambda: scene.confirm(row)),
        "gaps": scene.gaps(checking),
        "balance": scene.amount(checking),
    }


def _same_day_opening() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    opening_id = anchors(scene.store.book, cash.id)[0].id
    lunch = scene.act("expense", cash, "200.00", 1)
    asked = scene.refs(lunch, "inclusion_unanswered")[:1] == [opening_id]
    scene.store.resolve(lunch.id, answers={opening_id: "included"})
    scene.confirm(lunch)
    spending, _ = scene.spending(cash)
    return {"asked": asked, "balance": scene.amount(cash), "spending": spending}


def opening_date_correction() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00", as_of=local(5))
    opening_id = anchors(scene.store.book, cash.id)[0].id
    scene.record("expense", cash, "100.00", 6)
    before = scene.amount(cash)
    unreviewed = outcome(
        lambda: scene.store.correct(
            opening_id, 1, "balance was on the 7th", as_of=local(7)
        )
    )
    scene.store.correct(
        opening_id, 1, "balance was on the 7th", as_of=local(7), accept_reordering=True
    )
    history = scene.store.book.records[opening_id].revisions
    return {
        "balance_before": before,
        "unreviewed_date_change": unreviewed,
        "balance_after": scene.amount(cash),
        "spending": scene.spending(cash)[0],
        "revisions": [
            [revision.body.as_of.isoformat(), revision.reason] for revision in history
        ],
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
        "one_record_for_three_confirms": len({first.id, second.id, other_key.id}) == 1,
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
    household = scene.store.edit_draft(first["tx-household"].id, account_id=dop.id)
    picked = outcome(lambda: scene.confirm(household))
    refund = scene.store.state.drafts[first["tx-dop-04"].id].record_id
    scene.store.remove(refund, 1, "bank reversed it")
    third = scene.import_file("transactions.csv", accounts)
    return {
        "first_import_issues": first_issues,
        "confirmed_in_batch": len(clean),
        "after_first_import": after_first,
        "reimport": reimport,
        "overlap_issues": overlap_issues,
        "household_row_after_picking_account": picked,
        "removed_row_reimport": scene.issues(third["tx-dop-04"]),
        "final": {
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
    scene.store.confirm(fresh, "k1")
    return {
        "stale_attempts": attempts,
        "activity_records_after_stale": count_after_attempts,
        "draft_kept_for_the_refreshed_review": scene.store.state.drafts[
            pending.id
        ].fields["amount"],
        "fresh_preview_effects": dict(fresh.effects),
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
    scene.store.actor = "person-2"
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
    scene.store.remove(transfer.id, 3, "never happened")
    steps["removed"] = balances()
    restored = scene.store.restore(transfer.id, 4, "it did happen")
    steps["restored_same_record"] = restored.id == transfer.id
    steps["restored"] = balances()
    steps["history"] = [
        [rev.body.amount, rev.reason, rev.removed, rev.recorded_by]
        for rev in restored.revisions
    ]
    return steps


def multiple_precisions() -> dict:
    scene = Scene()
    yen = scene.account("Yen", "cash", "JPY", "1500")
    dinar = scene.account("Dinar", "cash", "KWD", "1.234")
    pesos = scene.account("Pesos", "cash", "DOP", "10.50")
    return {
        "minor_units": [scene.amount(yen), scene.amount(dinar), scene.amount(pesos)],
        "jpy_fraction": outcome(lambda: scene.account("Yen2", "cash", "JPY", "1500.5")),
        "dop_three_decimals": outcome(
            lambda: scene.account("Pesos2", "cash", "DOP", "1.005")
        ),
        "unknown_currency": outcome(lambda: scene.account("Zeta", "cash", "ZZZ", "1")),
        "positions": {
            currency: value["net"]
            for currency, value in scene.position(yen, dinar, pesos).items()
        },
    }


def overdraft_and_debt() -> dict:
    scene = Scene()
    checking = scene.account("Corriente", "checking", "DOP", "1000.00")
    loan = scene.account("Prestamo", "other_debt", "DOP", "21500.00")
    card = scene.account("Tarjeta", "credit_card", "DOP", "2000.00")
    scene.record("expense", checking, "1500.00", 2)
    scene.record("debt_payment", checking, "500.00", 3, counter=loan)
    scene.record("expense", card, "45.00", 4, category="interest_charge")
    return {
        "balances": [scene.amount(checking), scene.amount(loan), scene.amount(card)],
        "spending_by_category": scene.totals(checking, loan, card)["DOP"][
            "spending_by_category"
        ],
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
    card = scene.account("Tarjeta USD", "credit_card", "USD", "50.00")
    transfer = scene.act("transfer", pesos, "1000.00", 2, counter=dollars)
    payment = scene.act("debt_payment", pesos, "500.00", 2, counter=card)
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
    card = scene.account("Tarjeta", "credit_card", "DOP", "3000.00")
    sides = scene.position(wallet, card)["DOP"]
    return {
        "position": scene.position(checking, wallet, old),
        "spending": scene.spending(checking, wallet, old)[0],
        "unknown_asset_side": [sides["assets"], sides["liabilities"], sides["net"]],
    }


def asset_revaluation_and_share() -> dict:
    scene = Scene()
    car = scene.account("Carro", "vehicle", "DOP", "1000000.00", ownership_share_bps=5000)
    loan = scene.account(
        "Prestamo carro", "other_debt", "DOP", "400000.00", ownership_share_bps=5000
    )
    scene.store.edit_account(loan.id, 1, linked_asset_id=car.id)
    basis = scene.balance(car)["basis"]
    scene.observe(car, "900000.00", 20, basis="value_estimate")

    def totals_only(weighting: str) -> dict:
        found = scene.position(car, loan, weighting=weighting)["DOP"]
        return {key: value for key, value in found.items() if key != "coverage"}

    return {
        "estimate_basis": basis,
        "gaps": scene.gaps(car),
        "totals": scene.totals(car, loan),
        "full": totals_only("full"),
        "owner_share": totals_only("owner_share"),
        "loan_linked_to": scene.store.book.accounts[loan.id].linked_asset_id == car.id,
    }


def account_edit_rules() -> dict:
    scene = Scene()
    store = scene.store
    empty = scene.account("  Clavito  ", "savings", "DOP")
    opened = scene.account("Solo apertura", "checking", "DOP", "100.00")
    used = scene.account("Corriente", "checking", "DOP", "100.00")
    scene.record("expense", used, "10.00", 2)
    cleared = store.edit_account(empty.id, 1, nickname="   ")
    results = {
        "trimmed": empty.nickname,
        "blank_clears_nickname": cleared.nickname,
        "long_nickname": outcome(
            lambda: store.edit_account(empty.id, 2, nickname="x" * 61)
        ),
        "currency_on_empty": store.edit_account(empty.id, 2, currency="USD").currency,
        "currency_on_opened": outcome(
            lambda: store.edit_account(opened.id, 1, currency="USD")
        ),
        "nature_flip_on_opened": outcome(
            lambda: store.edit_account(opened.id, 1, type="credit_card")
        ),
        "same_nature_on_opened": store.edit_account(opened.id, 1, type="savings").type,
        "type_after_activity": outcome(
            lambda: store.edit_account(used.id, 2, type="savings")
        ),
        "stale_version": outcome(lambda: store.edit_account(used.id, 1, nickname="Otra")),
    }
    archived = store.edit_account(used.id, 2, archived=True)
    late = scene.act("expense", used, "5.00", 3)
    results.update(
        archived_version=archived.version,
        archived_draft_issues=scene.issues(late),
        archived_draft_confirm=outcome(lambda: scene.confirm(late)),
        correct_on_archived=outcome(
            lambda: store.correct(
                anchors(store.book, used.id)[0].id, 1, "typo", amount="150.00"
            )
        ),
        archived_still_in_totals=scene.position(used)["DOP"]["net"],
    )
    return results


def first_slice_create_reopen_edit() -> dict:
    scene = Scene()
    created = scene.account("Cuenta nomina", "checking", "DOP", "12500.00")
    unnamed = scene.account(None, "cash", "USD")
    reopened = scene.store.book.accounts[created.id]
    opening_id = anchors(scene.store.book, created.id)[0].id
    first = {
        "nickname": reopened.nickname,
        "type": reopened.type,
        "currency": reopened.currency,
        "balance": scene.balance(reopened),
        "version": reopened.version,
    }
    edited = scene.store.edit_account(
        created.id, reopened.version, nickname="Nomina", type="savings"
    )
    stale = outcome(lambda: scene.store.edit_account(created.id, 1, nickname="Otra"))
    scene.now = local(3)
    scene.store.correct(opening_id, 1, "typo in starting balance", amount="12000.00")
    redated = outcome(
        lambda: scene.store.correct(
            opening_id, 2, "balance was from the 1st", as_of=local(1, 8)
        )
    )
    return {
        "opening_date_edit_without_activity": redated,
        "reopened": first,
        "unnamed_account": [unnamed.nickname, scene.balance(unnamed)],
        "catalog_untouched": dict(scene.store.book.categories)
        == dict(DEFAULT_CATEGORIES),
        "edited": [edited.nickname, edited.type, edited.version],
        "stale_edit": stale,
        "balance_after_opening_correction": scene.amount(created),
        "totals_after_opening_correction": scene.spending(created),
        "opening_revisions": len(scene.store.book.records[opening_id].revisions),
    }


CORE = (
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
    older_activity_inclusion,
    opening_date_correction,
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
SCENARIOS: dict[str, Callable[[], dict]] = {
    scenario.__name__: scenario for scenario in (*CORE, *scenarios_lifecycle.LIFECYCLE)
}


def render() -> str:
    results = {name: jsonable(scenario()) for name, scenario in SCENARIOS.items()}
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
