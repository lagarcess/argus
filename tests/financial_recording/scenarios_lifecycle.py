"""Refunds, notes, recovery, spaces, categories and plan occurrences.

These scenarios cover the September 28 mobile baseline's recording rules. They
share the driver in scenes.py and feed the same evidence file as scenarios.py.
"""

from tests.financial_recording.derive import (
    balance,
    expectation_status,
    forecast,
    space_scope,
    standing,
)
from tests.financial_recording.scenes import Scene, local, outcome


def refund_partial_and_limits() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "5000.00")
    purchase = scene.record("expense", cash, "1000.00", 3, category="shopping")
    link = {"refund_of": purchase.id}
    first = scene.record("refund", cash, "300.00", 5, **link)
    checks = {
        "over_limit": scene.issues(scene.act("refund", cash, "800.00", 6, **link)),
        "before_purchase": scene.issues(scene.act("refund", cash, "100.00", 2, **link)),
        "other_category": scene.issues(
            scene.act("refund", cash, "100.00", 6, category="dining", **link)
        ),
    }
    scene.record("refund", cash, "700.00", 6, **link)
    totals = scene.totals(cash)["DOP"]
    return {
        **checks,
        "spending": totals["spending"],
        "purchases": totals["purchases"],
        "refunds": totals["refunds"],
        "income": totals["income"],
        "refund_shares_purchase_category": totals["spending_by_category"],
        "remove_purchase": outcome(lambda: scene.store.remove(purchase.id, 1, "oops")),
        "shrink_purchase": outcome(
            lambda: scene.store.correct(purchase.id, 1, "was 900", amount="900.00")
        ),
        "first_refund_removed": scene.store.book.records[first.id].removed,
        "balance": scene.amount(cash),
    }


def refund_unlinked_and_cross_account() -> dict:
    scene = Scene()
    card = scene.account("Tarjeta", "credit_card", "DOP", "0.00")
    checking = scene.account("Corriente", "checking", "DOP", "1000.00")
    dollars = scene.account("Dolares", "savings", "USD", "0.00")
    investment = scene.account("Inversion", "investment", "DOP", "100.00")
    loan = scene.account("Prestamo", "other_debt", "DOP", "5000.00")
    purchase = scene.record("expense", card, "2000.00", 3, category="shopping")
    scene.record("refund", checking, "500.00", 6, refund_of=purchase.id)
    scene.record("refund", checking, "250.00", 7, category="groceries")
    scene.record("refund", checking, "100.00", 7)
    foreign_linked = scene.act("refund", dollars, "10.00", 7, refund_of=purchase.id)
    foreign_link_issues = scene.issues(foreign_linked)
    scene.store.reject(foreign_linked.id)
    return {
        "cross_account_balances": [scene.amount(card), scene.amount(checking)],
        "dop_totals": scene.totals(card, checking)["DOP"],
        "foreign_currency_link": foreign_link_issues,
        "foreign_unlinked": outcome(
            lambda: scene.record("refund", dollars, "10.00", 7, note="returned in USD")
        ),
        "usd_totals_not_clamped": scene.totals(dollars)["USD"],
        "refund_on_investment": scene.issues(scene.act("refund", investment, "10.00", 7)),
        "refund_on_loan": scene.issues(scene.act("refund", loan, "10.00", 7)),
    }


def card_refund_credit_balance() -> dict:
    scene = Scene()
    card = scene.account("Tarjeta", "credit_card", "DOP", "100.00")
    before = standing(card, balance(scene.store.book, card.id))
    scene.record("refund", card, "300.00", 4)
    after = balance(scene.store.book, card.id)
    position = scene.position(card)["DOP"]
    return {
        "standing_before": before,
        "balance_after": after.amount,
        "standing_after": standing(card, after),
        "liabilities_total": position["liabilities"],
        "income": scene.spending(card)[1],
    }


def notes_across_records() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    longest = "ñ" * 200
    expense = scene.record("expense", cash, "100.00", 2, note=longest)
    too_long = scene.issues(scene.act("expense", cash, "100.00", 3, note="x" * 201))
    twin = scene.issues(scene.act("expense", cash, "100.00", 2, note="otra nota"))
    refund = scene.record("refund", cash, "20.00", 3, note="devolución parcial")
    check = scene.observe(cash, "920.00", 4, note="saldo en la app")
    before = scene.amount(cash)
    edited = scene.store.correct(expense.id, 1, "fix note", note="almuerzo")
    return {
        "longest_note_characters": len(expense.body.note),
        "note_too_long": too_long,
        "notes_saved": [refund.body.note, check.body.note],
        "note_edit_keeps_money": [before, scene.amount(cash)],
        "note_edit_revisions": len(edited.revisions),
        "notes_ignored_for_duplicates": twin,
        "note_edit_too_long": outcome(
            lambda: scene.store.correct(expense.id, 2, "long", note="y" * 201)
        ),
    }


def removal_and_restore() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    purchase = scene.record("expense", cash, "400.00", 2, category="dining")
    refund = scene.record("refund", cash, "100.00", 3, refund_of=purchase.id)
    steps = {"start": scene.amount(cash)}
    scene.store.remove(refund.id, 1, "entered twice")
    steps["refund_removed"] = scene.amount(cash)
    scene.store.remove(purchase.id, 1, "wrong account")
    steps["purchase_removed"] = scene.amount(cash)
    steps["restore_refund_first"] = outcome(
        lambda: scene.store.restore(refund.id, 2, "back")
    )
    steps["stale_restore"] = outcome(lambda: scene.store.restore(purchase.id, 1, "x"))
    restored = scene.store.restore(purchase.id, 2, "right account after all")
    scene.store.restore(refund.id, 2, "back")
    steps["both_restored"] = scene.amount(cash)
    steps["same_record"] = restored.id == purchase.id
    steps["purchase_history"] = [
        [revision.reason, revision.removed] for revision in restored.revisions
    ]
    steps["spending"] = scene.spending(cash)[0]
    return steps


def spaces_and_account_moves() -> dict:
    scene = Scene()
    cash = scene.account("Caja chica", "cash", "DOP", "2000.00")
    checking = scene.account("Corriente", "checking", "DOP", "10000.00")
    savings = scene.account("Ahorro", "savings", "DOP", "0.00")
    scene.record("expense", cash, "300.00", 2)
    record_ids_before = set(scene.store.book.records)
    moved = scene.store.move_account(cash.id, cash.version + 1, "business")
    transfer = scene.record("transfer", checking, "500.00", 3, counter=savings)
    scene.store.remove(transfer.id, 1, "never happened")
    book = scene.store.book
    return {
        "moved_to": moved.space_id,
        "records_untouched": set(book.records) == record_ids_before | {transfer.id},
        "personal_scope": space_scope(book, "personal"),
        "business_scope": space_scope(book, "business"),
        "business_spending": scene.spending(cash)[0],
        "business_balance": scene.amount(cash),
        "linked_account_move": outcome(
            lambda: scene.store.move_account(
                checking.id, book.accounts[checking.id].version, "business"
            )
        ),
    }


def custom_categories() -> dict:
    scene = Scene()
    shop = scene.account("Negocio", "checking", "DOP", "5000.00", space_id="business")
    home = scene.account("Casa", "checking", "DOP", "5000.00")
    materials = scene.store.create_category("business", "Materiales", "spending")
    scene.record("expense", shop, "700.00", 2, category=materials.id)
    before = scene.totals(shop)["DOP"]["spending_by_category"]
    renamed = scene.store.rename_category(materials.id, "Materia prima")
    return {
        "custom_in_personal": outcome(
            lambda: scene.store.create_category("personal", "Mio", "spending")
        ),
        "rename_keeps_identity": renamed.id == materials.id,
        "renamed_label": renamed.labels["custom"],
        "totals_by_id_before_and_after_rename": [
            before,
            scene.totals(shop)["DOP"]["spending_by_category"],
        ],
        "business_category_on_personal_account": scene.issues(
            scene.act("expense", home, "10.00", 2, category=materials.id)
        ),
        "rename_default": outcome(
            lambda: scene.store.rename_category("groceries", "Colmado")
        ),
    }


def plan_occurrence_counted_once() -> dict:
    scene = Scene()
    checking = scene.account("Corriente", "checking", "DOP", "10000.00")
    savings = scene.account("Ahorro", "savings", "DOP", "0.00")
    rent = scene.store.expect(checking.id, "out", "3000.00", local(10).date())
    steps = {
        "planned": [
            expectation_status(scene.store.book, rent),
            forecast(scene.store.book, [checking.id]),
        ]
    }
    paid = scene.record("expense", checking, "3000.00", 9, fulfills=rent)
    steps["completed"] = [
        expectation_status(scene.store.book, rent),
        forecast(scene.store.book, [checking.id]),
        scene.spending(checking)[0],
    ]
    steps["second_payment_for_same_occurrence"] = scene.issues(
        scene.act("expense", checking, "3000.00", 10, fulfills=rent)
    )
    scene.record("refund", checking, "500.00", 11, refund_of=paid.id)
    steps["after_refund"] = expectation_status(scene.store.book, rent)
    scene.store.correct(paid.id, 1, "fee waived", amount="2900.00")
    steps["after_amount_correction"] = expectation_status(scene.store.book, rent)
    steps["account_change_needs_review"] = outcome(
        lambda: scene.store.correct(paid.id, 2, "wrong account", account_id=savings.id)
    )
    scene.store.correct(paid.id, 2, "not rent", fulfills=None)
    steps["after_unlinking"] = [
        expectation_status(scene.store.book, rent),
        forecast(scene.store.book, [checking.id]),
    ]
    return steps


LIFECYCLE = (
    refund_partial_and_limits,
    refund_unlinked_and_cross_account,
    card_refund_credit_balance,
    notes_across_records,
    removal_and_restore,
    spaces_and_account_moves,
    custom_categories,
    plan_occurrence_counted_once,
)
