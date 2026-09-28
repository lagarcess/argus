"""Refunds, notes, recovery, spaces, categories and plan occurrences.

These scenarios cover the September 28 mobile baseline's recording rules. They
share the driver in scenes.py and feed the same evidence file as scenarios.py.
"""

from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

from tests.financial_recording.derive import (
    DEFAULT_TZ,
    Provenance,
    anchors,
    balance,
    expectation_status,
    forecast,
    observation_gaps,
    space_scope,
    standing,
)
from tests.financial_recording.derive import (
    position as position_at,
)
from tests.financial_recording.model import Store
from tests.financial_recording.scenes import Scene, jsonable, local, outcome


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


def edits_that_move_money_need_review() -> dict:
    return {
        "removing_a_check_others_depend_on": _remove_check_with_dependents(),
        "redating_activity_into_a_check": _redate_into_check(),
        "restoring_activity_the_check_never_saw": _restore_unseen_activity(),
        "redating_a_check": _redate_check(),
        "note_only_correction_keeps_evidence": _note_keeps_evidence(),
        "redating_the_opening_onto_untimed_activity": _redate_opening_onto_day(),
        "purchase_edits_recheck_refunds": _purchase_edits_recheck_refunds(),
        "custom_category_blocks_a_move": _custom_category_blocks_move(),
        "anchors_keep_their_account": _anchor_account_fixed(),
        "contradicting_answers_stop_for_review": _contradicting_answers(),
        "redated_check_restamps_its_contents": _redated_check_restamps(),
        "restore_needs_a_reason": _restore_needs_reason(),
        "stale_duplicate_resolve_is_refused": _stale_duplicate_resolve(),
        "future_anchors_are_refused": _future_anchors_are_refused(),
        "type_edits_preserve_linked_asset_rules": _type_edits_preserve_links(),
        "liability_anchors_use_owner_sign": _liability_anchor_sign(),
        "moving_activity_across_accounts_needs_reordering": _move_across_accounts(),
        "occurred_on_and_at_must_agree": _occurred_on_at_agree(),
        "value_estimate_only_on_estimated_assets": _value_estimate_restricted(),
        "anchor_zone_survives_reader_tz_change": _anchor_zone_stable(),
        "type_edit_revalidates_existing_anchors": _type_edit_revalidates_anchors(),
        "distinct_bound_to_reviewed_revision": _distinct_bound_to_revision(),
        "linked_duplicate_keeps_import_account": _linked_duplicate_account(),
        "oldest_anchor_in_coverage": _oldest_anchor_in_coverage(),
        "spanish_labels_use_supported_locale": _spanish_labels_locale(),
        "rejected_draft_cannot_confirm": _rejected_draft_cannot_confirm(),
        "inclusion_answers_bound_to_revision": _answers_bound_to_revision(),
        "correction_unknown_account_is_structured": _correction_unknown_account(),
        "first_observation_keeps_recorded_difference": _first_obs_keeps_difference(),
        "cross_space_transfer_stays_unresolved": _cross_space_transfer(),
        "refund_inherits_category_space": _refund_inherits_category_space(),
        "corrected_observation_basis_is_canonical": _corrected_basis_canonical(),
        "linked_digest_places_restored_activity": _linked_digest_placement(),
        "balance_check_preview_exposes_effect": _check_preview_effect(),
        "batch_checks_bind_to_previewed_prior": _batch_checks_bind_prior(),
        "correction_rejects_bogus_kind": _correction_rejects_bogus_kind(),
        "external_id_bound_to_confirm_account": _external_id_bound_account(),
        "restore_reviews_placement": _restore_reviews_placement(),
        "position_gaps_honor_as_of": _position_gaps_honor_as_of(),
        "future_activity_is_refused": _future_activity_is_refused(),
        "activity_zone_survives_reader_tz_change": _activity_zone_stable(),
        "activity_zone_honors_historical_as_of": _activity_zone_honors_as_of(),
        "expectation_direction_is_canonical": _expectation_direction_canonical(),
        "restamp_honors_not_included": _restamp_honors_not_included(),
        "duplicate_of_draft_is_refused": _duplicate_of_draft_refused(),
        "unsupported_weighting_is_refused": _unsupported_weighting_is_refused(),
        "check_correction_bound_to_account_state": _check_correction_bound_to_account(),
        "observation_basis_and_restamp_together": _observation_basis_and_restamp_together(),
        "distinct_bound_to_reviewed_matches": _distinct_bound_to_reviewed_matches(),
        "preview_basis_requires_touched_accounts": _preview_basis_requires_touched(),
        "remove_answers_limited_to_exposed": _remove_answers_limited_to_exposed(),
        "observation_preview_requires_check": _observation_preview_requires_check(),
        "remove_rejects_empty_answer_map": _remove_rejects_empty_answer_map(),
        "zone_change_restamps_check": _zone_change_restamps_check(),
        "correction_dry_run_keeps_seq": _correction_dry_run_keeps_seq(),
        "reordering_bound_to_account_state": _reordering_bound_to_account_state(),
    }


def _stale_duplicate_resolve() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "5000.00")
    original = scene.record("expense", cash, "500.00", 3)
    twin = scene.act("expense", cash, "500.00", 3, method="chat")
    scene.store.edit_draft(twin.id, amount="600.00")
    stale_revision = outcome(
        lambda: scene.store.resolve(
            twin.id, duplicate_of=original.id, expected_revision=1
        )
    )
    edited_away = outcome(
        lambda: scene.store.resolve(
            twin.id,
            duplicate_of=original.id,
            expected_revision=scene.store.state.drafts[twin.id].revision,
        )
    )
    removed = Scene()
    cash = removed.account("Efectivo", "cash", "DOP", "5000.00")
    original = removed.record("expense", cash, "500.00", 3)
    twin = removed.act("expense", cash, "500.00", 3, method="chat")
    removed.store.remove(original.id, 1, "gone")
    after_remove = outcome(
        lambda: removed.store.resolve(
            twin.id, duplicate_of=original.id, expected_revision=twin.revision
        )
    )
    return {
        "stale_revision": stale_revision,
        "edited_away": edited_away,
        "target_removed": after_remove,
    }


def _future_anchors_are_refused() -> dict:
    # Fixed clock: Scene helpers advance `now` to the balance instant, so this
    # probe uses Store directly against a clock that does not move.
    now = local(1)
    store = Store(lambda: now, tz=DEFAULT_TZ)
    future = local(2)
    opening = outcome(
        lambda: store.create_account(
            "cash",
            "DOP",
            "100.00",
            nickname="Futuro",
            as_of=future,
            idempotency_key="future-opening",
        )
    )
    cash = store.create_account(
        "cash", "DOP", "1000.00", nickname="Efectivo", idempotency_key="cash"
    )
    from tests.financial_recording.derive import Provenance

    draft = store.draft(
        {
            "kind": "balance_observation",
            "account_id": cash.id,
            "amount": "1000.00",
            "as_of": future.isoformat(),
            "basis": "user_check",
        },
        Provenance("manual", now),
    )
    check = outcome(lambda: store.confirm(store.preview(draft.id), "future-check"))
    opening_id = anchors(store.book, cash.id)[0].id
    correction = outcome(lambda: store.correct(opening_id, 1, "tomorrow", as_of=future))
    return {
        "future_opening": opening,
        "future_check": check,
        "future_opening_correction": correction,
    }


def _type_edits_preserve_links() -> dict:
    scene = Scene()
    car = scene.account("Carro", "vehicle", "DOP")
    loan = scene.account("Prestamo", "other_debt", "DOP")
    linked = scene.store.edit_account(loan.id, 1, linked_asset_id=car.id)
    debt_to_asset = outcome(
        lambda: scene.store.edit_account(loan.id, linked.version, type="checking")
    )
    asset_to_debt = outcome(
        lambda: scene.store.edit_account(car.id, 1, type="credit_card")
    )
    return {
        "debt_to_asset_keeps_link": debt_to_asset,
        "asset_to_debt_while_linked": asset_to_debt,
        "link_still_set": scene.store.book.accounts[loan.id].linked_asset_id == car.id,
    }


def _liability_anchor_sign() -> dict:
    scene = Scene()
    card = scene.account("Tarjeta", "credit_card", "DOP", "2000.00")
    opening_id = anchors(scene.store.book, card.id)[0].id
    scene.store.correct(opening_id, 1, "was 2500 owed", amount="2500.00")
    after_correct = scene.amount(card)
    scene.observe(card, "2200.00", 5)
    return {
        "opening_after_correction": after_correct,
        "after_check": scene.amount(card),
        "still_owed": scene.amount(card) < 0,
    }


def _move_across_accounts() -> dict:
    scene = Scene()
    checking = scene.account("Corriente", "checking", "DOP", "10000.00")
    savings = scene.account("Ahorros", "savings", "DOP", "5000.00")
    expense = scene.record("expense", checking, "500.00", 3)
    check = scene.observe(savings, "5000.00", 5)
    scene.now = local(6)
    blocked = outcome(
        lambda: scene.store.correct(
            expense.id,
            1,
            "paid from savings",
            account_id=savings.id,
            answers={check.id: "included"},
        )
    )
    scene.store.correct(
        expense.id,
        1,
        "paid from savings",
        account_id=savings.id,
        answers={check.id: "included"},
        accept_reordering=True,
        account_basis=scene.account_basis(checking, savings),
    )
    return {
        "unaccepted_move": blocked,
        "balances": [scene.amount(checking), scene.amount(savings)],
        "savings_gaps": scene.gaps(savings),
    }


def _occurred_on_at_agree() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    draft = scene.draft(
        kind="expense",
        account_id=cash.id,
        amount="50.00",
        occurred_on=local(10).date().isoformat(),
        occurred_at=local(3, 12).isoformat(),
    )
    return {
        "issues": scene.issues(draft),
        "confirm": outcome(lambda: scene.confirm(draft)),
    }


def _value_estimate_restricted() -> dict:
    scene = Scene()
    checking = scene.account("Corriente", "checking", "DOP", "1000.00")
    car = scene.account("Carro", "vehicle", "DOP", "100000.00")
    on_checking = scene.issues(
        scene.observation(checking, "900.00", 5, basis="value_estimate")
    )
    on_car = outcome(lambda: scene.observe(car, "90000.00", 5, basis="value_estimate"))
    user_check_on_car = scene.issues(
        scene.observation(car, "90000.00", 5, basis="user_check")
    )
    return {
        "on_checking": on_checking,
        "on_vehicle": on_car,
        "user_check_on_vehicle": user_check_on_car,
    }


def _anchor_zone_stable() -> dict:
    from zoneinfo import ZoneInfo

    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00", as_of=local(5, 0, 30))
    scene.record("expense", cash, "100.00", 4)
    before = scene.amount(cash)
    opening = anchors(scene.store.book, cash.id)[0].body
    scene.store.tz = ZoneInfo("America/Los_Angeles")
    try:
        after = scene.amount(cash)
        readable = True
    except Exception:
        after = None
        readable = False
    return {
        "readable_after_tz_change": readable,
        "balance_stable": before == after,
        "opening_zone": opening.zone,
    }


def _type_edit_revalidates_anchors() -> dict:
    scene = Scene()
    car = scene.account("Carro", "vehicle", "DOP", "100000.00")
    scene.observe(car, "90000.00", 5, basis="value_estimate")
    version = scene.store.book.accounts[car.id].version
    refused = outcome(lambda: scene.store.edit_account(car.id, version, type="checking"))
    cash = scene.account("Efectivo", "cash", "DOP", "100.00")
    allowed = outcome(lambda: scene.store.edit_account(cash.id, 1, type="checking"))
    return {
        "value_estimate_blocks_type_edit": refused,
        "opening_only_same_nature": allowed,
    }


def _distinct_bound_to_revision() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "5000.00")
    scene.record("expense", cash, "500.00", 3)
    other = scene.record("expense", cash, "400.00", 4)
    twin = scene.act("expense", cash, "500.00", 3, method="chat")
    scene.store.resolve(twin.id, distinct=True, expected_revision=twin.revision)
    scene.store.edit_draft(
        twin.id, amount="400.00", occurred_on=local(4).date().isoformat()
    )
    after_edit = scene.issues(twin)
    unique = scene.act("expense", cash, "123.00", 5, method="chat")
    without_match = outcome(
        lambda: scene.store.resolve(
            unique.id, distinct=True, expected_revision=unique.revision
        )
    )
    missing_revision = outcome(lambda: scene.store.resolve(twin.id, distinct=True))
    return {
        "after_edit_possible_duplicate": after_edit,
        "matches_the_other_expense": scene.refs(twin, "possible_duplicate") == [other.id],
        "distinct_without_match": without_match,
        "distinct_requires_revision": missing_revision,
    }


def _linked_duplicate_account() -> dict:
    scene = Scene()
    checking = scene.account("Corriente", "checking", "DOP", "5000.00")
    savings = scene.account("Ahorros", "savings", "DOP", "0.00")
    move = scene.record("transfer", checking, "500.00", 3, counter=savings)
    twin = scene.draft(
        "document",
        {"external_id": "savings-stmt-99"},
        kind="transfer",
        account_id=savings.id,
        amount="500.00",
        occurred_on=local(3).date().isoformat(),
        counter_account_id=checking.id,
    )
    scene.store.resolve(twin.id, duplicate_of=move.id, expected_revision=twin.revision)
    again = scene.draft(
        "document",
        {"external_id": "savings-stmt-99"},
        kind="transfer",
        account_id=savings.id,
        amount="500.00",
        occurred_on=local(3).date().isoformat(),
        counter_account_id=checking.id,
    )
    linked = scene.store.book.records[move.id].linked[-1]
    return {
        "reimport": scene.issues(again),
        "linked_import_account": linked.account_id == savings.id,
    }


def _oldest_anchor_in_coverage() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00", as_of=local(1))
    scene.observe(cash, "900.00", 5)
    return {
        "oldest_anchor_as_of": scene.position(cash)["DOP"]["coverage"][
            "oldest_anchor_as_of"
        ]
    }


def _spanish_labels_locale() -> dict:
    from tests.financial_recording.catalog import DEFAULT_CATEGORIES

    locales = sorted(
        {locale for category in DEFAULT_CATEGORIES.values() for locale in category.labels}
    )
    return {
        "locale_keys": locales,
        "groceries": DEFAULT_CATEGORIES["groceries"].labels.get("es-419"),
    }


def _rejected_draft_cannot_confirm() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    draft = scene.act("expense", cash, "10.00", 3)
    preview = scene.store.preview(draft.id)
    scene.store.reject(draft.id)
    return {
        "confirm_rejected": outcome(
            lambda: scene.store.confirm(preview, f"confirm:{draft.id}")
        )
    }


def _answers_bound_to_revision() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    check = scene.observe(cash, "1000.00", 5)
    draft = scene.act("expense", cash, "10.00", 3)
    scene.store.resolve(
        draft.id,
        answers={check.id: "included"},
        expected_revision=draft.revision,
    )
    scene.store.edit_draft(draft.id, amount="500.00")
    after_edit = scene.issues(draft)
    missing_revision = outcome(
        lambda: scene.store.resolve(draft.id, answers={check.id: "included"})
    )
    return {
        "after_edit_asks_again": after_edit,
        "answers_require_revision": missing_revision,
    }


def _correction_unknown_account() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    other = scene.account("Monedero", "cash", "DOP", "100.00")
    expense = scene.record("expense", cash, "10.00", 3)
    opening = anchors(scene.store.book, cash.id)[0]
    return {
        "unknown_activity_account": outcome(
            lambda: scene.store.correct(expense.id, 1, "typo", account_id="acct-missing")
        ),
        "unknown_anchor_account": outcome(
            lambda: scene.store.correct(opening.id, 1, "typo", account_id="acct-missing")
        ),
        "anchor_keeps_account": outcome(
            lambda: scene.store.correct(opening.id, 1, "wrong", account_id=other.id)
        ),
    }


def _first_obs_keeps_difference() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    scene.record("expense", cash, "100.00", 3)
    scene.observe(cash, "850.00", 5)
    before = scene.gaps(cash)
    opening = anchors(scene.store.book, cash.id)[0]
    scene.store.remove(opening.id, 1, "wrong start")
    gap = observation_gaps(scene.store.book, cash.id, scene.store.tz)[0]
    return {
        "before": before,
        "after_opening_removed": [gap.recorded, gap.remaining, gap.label],
        "stored_difference": scene.store.book.records[gap.record_id]
        .revisions[-1]
        .confirmed_difference,
    }


def _cross_space_transfer() -> dict:
    scene = Scene()
    personal = scene.account("Casa", "checking", "DOP", "5000.00")
    business = scene.account("Negocio", "checking", "DOP", "5000.00", space_id="business")
    draft = scene.act("transfer", personal, "100.00", 3, counter=business)
    return {
        "issues": scene.issues(draft),
        "confirm": outcome(lambda: scene.confirm(draft)),
    }


def _refund_inherits_category_space() -> dict:
    scene = Scene()
    shop = scene.account("Negocio", "checking", "DOP", "5000.00", space_id="business")
    home = scene.account("Casa", "checking", "DOP", "5000.00")
    materials = scene.store.create_category("business", "Materiales", "spending")
    purchase = scene.record("expense", shop, "700.00", 2, category=materials.id)
    draft = scene.act("refund", home, "100.00", 5, refund_of=purchase.id)
    return {
        "issues": scene.issues(draft),
        "confirm": outcome(lambda: scene.confirm(draft)),
    }


def _corrected_basis_canonical() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    obs = scene.observe(cash, "1000.00", 5)
    refused = outcome(lambda: scene.store.correct(obs.id, 1, "typo", basis="bogus"))
    return {"bogus_basis": refused, "gaps_still_readable": scene.gaps(cash)}


def _linked_digest_placement() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "10000.00")
    record = scene.record("expense", cash, "500.00", 4)
    twin = scene.store.draft(
        {
            "kind": "expense",
            "account_id": cash.id,
            "amount": "500.00",
            "occurred_on": local(4).date().isoformat(),
        },
        Provenance("document", local(5), {"digest": "stmt-digest", "row": "1"}),
    )
    scene.store.resolve(twin.id, duplicate_of=record.id, expected_revision=twin.revision)
    scene.store.remove(record.id, 1, "wrong")
    scene.now = local(5, 18)
    check = scene.store.draft(
        {
            "kind": "balance_observation",
            "account_id": cash.id,
            "amount": "10000.00",
            "as_of": local(5, 18).isoformat(),
            "basis": "statement",
        },
        Provenance("document", local(5), {"digest": "stmt-digest", "row": "bal"}),
    )
    scene.store.confirm(scene.store.preview(check.id), "stmt-check")
    shifted = outcome(lambda: scene.store.restore(record.id, 2, "back"))
    restored = outcome(
        lambda: scene.store.restore(
            record.id,
            2,
            "back",
            accept_reordering=True,
            account_basis=scene.account_basis(cash),
        )
    )
    return {
        "restore_needs_reordering": shifted,
        "restore": restored,
        "balance": scene.amount(cash),
    }


def _check_preview_effect() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    scene.record("expense", cash, "100.00", 3)
    draft = scene.observation(cash, "850.00", 5)
    preview = scene.store.preview(draft.id)
    confirmed = scene.confirm(draft)
    stamped = confirmed.revisions[-1]
    return {
        "preview_check": dict(preview.check or {}),
        "preview_effects": dict(preview.effects),
        "stamped": [stamped.confirmed_expected, stamped.confirmed_difference],
    }


def _batch_checks_bind_prior() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    first = scene.observation(cash, "900.00", 5)
    second = scene.observation(cash, "800.00", 10)
    previews = [scene.store.preview(first.id), scene.store.preview(second.id)]
    stale = outcome(lambda: scene.store.confirm_batch(previews, "two-checks"))
    scene.confirm(first)
    scene.confirm(second)
    stored = [
        [
            scene.store.book.records[gap.record_id].revisions[-1].confirmed_expected,
            scene.store.book.records[gap.record_id].revisions[-1].confirmed_difference,
        ]
        for gap in observation_gaps(scene.store.book, cash.id, scene.store.tz)
    ]
    return {"batch": stale, "stored": stored}


def _correction_rejects_bogus_kind() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    expense = scene.record("expense", cash, "100.00", 3)
    return {
        "bogus_kind": outcome(
            lambda: scene.store.correct(expense.id, 1, "typo", kind="bogus")
        ),
    }


def _external_id_bound_account() -> dict:
    scene = Scene()
    checking = scene.account("Corriente", "checking", "DOP", "5000.00")
    savings = scene.account("Ahorros", "savings", "DOP", "5000.00")
    draft = scene.draft(
        "document",
        {"external_id": "row-42"},
        kind="expense",
        account_id=checking.id,
        amount="100.00",
        occurred_on=local(3).date().isoformat(),
    )
    record = scene.confirm(draft)
    scene.store.correct(record.id, 1, "was savings", account_id=savings.id)
    again = scene.draft(
        "document",
        {"external_id": "row-42"},
        kind="expense",
        account_id=checking.id,
        amount="100.00",
        occurred_on=local(3).date().isoformat(),
    )
    return {
        "bound_account": scene.store.book.records[record.id].revisions[0].provenance.account_id,
        "reimport": scene.issues(again),
        "confirm": outcome(lambda: scene.confirm(again)),
    }


def _restore_reviews_placement() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    expense = scene.record("expense", cash, "100.00", 3)
    scene.observe(cash, "900.00", 5)
    # Removing contained activity also shifts placement.
    scene.store.remove(
        expense.id,
        1,
        "wrong",
        accept_reordering=True,
        account_basis=scene.account_basis(cash),
    )
    # Contained at confirmation, so restore needs no inclusion answer — but
    # landing still shifts the remaining difference.
    shifted = outcome(lambda: scene.store.restore(expense.id, 2, "keep"))
    restored = outcome(
        lambda: scene.store.restore(
            expense.id,
            2,
            "keep",
            accept_reordering=True,
            account_basis=scene.account_basis(cash),
        )
    )
    return {
        "unaccepted": shifted,
        "accepted": restored,
        "gaps": scene.gaps(cash),
        "balance": scene.amount(cash),
    }


def _position_gaps_honor_as_of() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    scene.record("expense", cash, "50.00", 3)
    scene.observe(cash, "900.00", 5)
    scene.observe(cash, "800.00", 10)
    early = local(6, 12)
    full = scene.position(cash)
    historic = jsonable(
        position_at(scene.store.book, [cash.id], at=early, tz=scene.store.tz)
    )
    return {
        "full_gap_count": len(full["DOP"]["coverage"]["unexplained_gaps"]),
        "historic_gap_count": len(historic["DOP"]["coverage"]["unexplained_gaps"]),
        "historic_as_of_days": [
            gap["as_of"][:10] for gap in historic["DOP"]["coverage"]["unexplained_gaps"]
        ],
    }


def _future_activity_is_refused() -> dict:
    """Actual activity after the store clock stays out of the ledger."""
    now = local(1)
    store = Store(lambda: now, tz=DEFAULT_TZ)
    cash = store.create_account(
        "cash", "DOP", "1000.00", nickname="Efectivo", idempotency_key="cash"
    )
    draft = store.draft(
        {
            "kind": "expense",
            "account_id": cash.id,
            "amount": "50.00",
            "occurred_on": local(2).date().isoformat(),
        },
        Provenance("manual", now),
    )
    preview = store.preview(draft.id)
    return {
        "issues": {
            item.code: item.severity
            for item in preview.issues
            if item.code == "date_in_future"
        },
        "confirm": outcome(lambda: store.confirm(preview, "future-exp")),
    }


def _activity_zone_stable() -> dict:
    """Note-only edits keep occurred_on/at agreement after the reader zone changes."""
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    # 2026-09-04 01:00 UTC == 2026-09-03 21:00 in America/Santo_Domingo.
    instant = datetime(2026, 9, 4, 1, 0, tzinfo=ZoneInfo("UTC"))
    scene.now = local(4)
    local_day = instant.astimezone(DEFAULT_TZ).date()
    expense = scene.confirm(
        scene.draft(
            kind="expense",
            account_id=cash.id,
            amount="50.00",
            occurred_on=local_day.isoformat(),
            occurred_at=instant.isoformat(),
        )
    )
    scene.store.tz = ZoneInfo("UTC")
    note_only = outcome(
        lambda: scene.store.correct(expense.id, 1, "add note", note="almuerzo")
    )
    return {
        "note_edit_after_tz_change": note_only,
        "activity_zone": scene.store.book.records[expense.id].body.zone,
    }


def _activity_zone_honors_as_of() -> dict:
    """Date-only historical reads keep the stored activity zone, not the reader zone."""
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    scene.record("expense", cash, "100.00", 3)
    # 01:00Z on the 3rd is still the 2nd in America/Santo_Domingo, so the
    # Sept 3 expense stays out of the as-of balance under the stored zone.
    at = datetime(2026, 9, 3, 1, 0, tzinfo=ZoneInfo("UTC"))
    in_stored = balance(scene.store.book, cash.id, at=at, tz=DEFAULT_TZ).amount
    in_utc = balance(scene.store.book, cash.id, at=at, tz=ZoneInfo("UTC")).amount
    return {
        "balance_stable_across_reader_tz": in_stored == in_utc,
        "historic_balance": in_stored,
    }


def _expectation_direction_canonical() -> dict:
    """Plan expectations only accept the closed in/out direction table."""
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    refused = outcome(
        lambda: scene.store.expect(cash.id, "sideways", "100.00", local(10).date())
    )
    negative = outcome(
        lambda: scene.store.expect(cash.id, "out", "-100.00", local(10).date())
    )
    zero = outcome(
        lambda: scene.store.expect(cash.id, "in", "0.00", local(10).date())
    )
    ok = scene.store.expect(cash.id, "out", "100.00", local(10).date())
    return {
        "bogus_direction": refused,
        "negative_amount": negative,
        "zero_amount": zero,
        "accepted": ok in scene.store.book.expectations,
    }


def _duplicate_of_draft_refused() -> dict:
    """Same-signature proposed drafts cannot be linked until one is a record."""
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "5000.00")
    first = scene.act("expense", cash, "100.00", 3)
    twin = scene.act("expense", cash, "100.00", 3, method="chat")
    refused = outcome(
        lambda: scene.store.resolve(
            twin.id,
            duplicate_of=first.id,
            expected_revision=scene.store.state.drafts[twin.id].revision,
        )
    )
    return {
        "lists_the_other_draft": scene.refs(twin, "possible_duplicate") == [first.id],
        "link_to_draft": refused,
    }


def _restamp_honors_not_included() -> dict:
    """A check re-confirmation must not stamp excluded late activity as contained."""
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    check = scene.observe(cash, "1000.00", 5)
    scene.now = local(8)
    late = scene.act("expense", cash, "100.00", 3)
    scene.store.resolve(
        late.id,
        answers={check.id: "not_included"},
        expected_revision=scene.store.state.drafts[late.id].revision,
    )
    expense = scene.confirm(late)
    # Amount must change so `_revise` clears contained and restamps.
    scene.store.correct(
        check.id,
        1,
        "typo",
        amount="950.00",
        account_basis={cash.id: scene.store.book.accounts[cash.id].version},
        check={"prior": 100_000, "observed": 95_000, "difference": -5_000},
    )
    revised = scene.store.book.records[check.id]
    stamped = revised.revisions[-1]
    return {
        "reconfirmed": len(revised.revisions) == 2,
        "observed": stamped.body.amount,
        "excluded_from_contents": expense.id not in (stamped.contained or ()),
        "confirmed_expected": stamped.confirmed_expected,
    }


def _redated_check_restamps() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    check = scene.observe(cash, "1000.00", 5)
    scene.now = local(9, 18)
    expense = scene.record("expense", cash, "100.00", 8)
    redate = {"as_of": local(9, 18), "amount": "900.00"}
    unanswered = outcome(lambda: scene.store.correct(check.id, 1, "9th", **redate))
    scene.store.correct(expense.id, 1, "seen on the 9th", answers={check.id: "included"})
    unaccepted = outcome(lambda: scene.store.correct(check.id, 1, "9th", **redate))
    scene.store.correct(
        check.id,
        1,
        "9th",
        accept_reordering=True,
        account_basis={cash.id: scene.store.book.accounts[cash.id].version},
        check={"prior": 90_000, "observed": 90_000, "difference": 0},
        **redate,
    )
    gap = observation_gaps(scene.store.book, cash.id, scene.store.tz)[0]
    return {
        "unanswered": unanswered,
        "unaccepted": unaccepted,
        "recorded_and_remaining": [gap.recorded, gap.remaining],
        "explained_by": list(gap.explained_by),
        "balance": scene.amount(cash),
    }


def _restore_needs_reason() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    expense = scene.record("expense", cash, "100.00", 2)
    scene.store.remove(expense.id, 1, "typo")
    return {"blank": outcome(lambda: scene.store.restore(expense.id, 2, "  "))}


def _contradicting_answers() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    later = scene.observe(cash, "1000.00", 15)
    scene.now = local(20)
    pending = scene.act("expense", cash, "200.00", 5)
    scene.store.resolve(
        pending.id,
        answers={later.id: "not_included"},
        expected_revision=scene.store.state.drafts[pending.id].revision,
    )
    expense = scene.confirm(pending)
    before = scene.amount(cash)
    earlier = scene.observation(cash, "800.00", 10)
    blocked = outcome(lambda: scene.confirm(earlier))
    scene.store.correct(expense.id, 1, "the bank had it", answers={later.id: "included"})
    confirmed = outcome(lambda: scene.confirm(earlier))
    flip_back = outcome(
        lambda: scene.store.correct(
            expense.id, 2, "not by the 15th", answers={later.id: "not_included"}
        )
    )
    return {
        "balance_before": before,
        "earlier_check_contradicts_answer": blocked,
        "after_correcting_the_answer": confirmed,
        "answer_contradicts_earlier_check": flip_back,
        "anchor_answers": outcome(
            lambda: scene.store.correct(
                later.id, 1, "x", answers={expense.id: "included"}
            )
        ),
        "balance_after": scene.amount(cash),
        "gaps": scene.gaps(cash),
    }


def _anchor_account_fixed() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "10000.00")
    other = scene.account("Monedero", "cash", "DOP", "0.00")
    check = scene.observe(cash, "8000.00", 5)
    scene.now = local(6)
    late = scene.act("expense", cash, "2000.00", 3)
    scene.store.resolve(
        late.id,
        answers={check.id: "included"},
        expected_revision=scene.store.state.drafts[late.id].revision,
    )
    expense = scene.confirm(late)
    moved = outcome(
        lambda: scene.store.correct(check.id, 1, "wrong", account_id=other.id)
    )
    flip = outcome(
        lambda: scene.store.correct(
            expense.id, 1, "it was after", answers={check.id: "not_included"}
        )
    )
    balance_after_flip = scene.amount(cash)
    scene.store.remove(check.id, 1, "typo")
    return {
        "check_to_other_account": moved,
        "own_answer_flip": flip,
        "balance_after_flip": balance_after_flip,
        "answers_on_a_check_restore": outcome(
            lambda: scene.store.restore(check.id, 2, "x", answers={expense.id: "x"})
        ),
    }


def _remove_check_with_dependents() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "10000.00")
    first = scene.observe(cash, "8000.00", 5)
    second = scene.observe(cash, "8000.00", 10)
    scene.now = local(11)
    late = scene.act("expense", cash, "2000.00", 3)
    scene.store.resolve(
        late.id,
        answers={first.id: "included"},
        expected_revision=scene.store.state.drafts[late.id].revision,
    )
    record = scene.confirm(late)
    blocked = outcome(lambda: scene.store.remove(first.id, 1, "typo"))
    # Same call can carry the activity answer the removal would expose.
    still_shifted = outcome(
        lambda: scene.store.remove(
            first.id,
            1,
            "typo",
            answers={record.id: {second.id: "included"}},
        )
    )
    removed = outcome(
        lambda: scene.store.remove(
            first.id,
            1,
            "typo",
            accept_reordering=True,
            account_basis=scene.account_basis(cash),
            answers={record.id: {second.id: "included"}},
        )
    )
    return {
        "blocked": blocked,
        "answered_still_needs_reordering": still_shifted,
        "accepted_reordering": removed,
        "balance": scene.amount(cash),
        "gaps": scene.gaps(cash),
    }


def _redate_into_check() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "10000.00")
    scene.now = local(8)
    expense = scene.record("expense", cash, "500.00", 7)
    check = scene.observe(cash, "10000.00", 5)
    before = [scene.amount(cash), scene.gaps(cash)]
    silent = outcome(
        lambda: scene.store.correct(
            expense.id, 1, "was the 4th", occurred_on=local(4).date().isoformat()
        )
    )
    scene.store.correct(
        expense.id,
        1,
        "was the 4th",
        occurred_on=local(4).date().isoformat(),
        answers={check.id: "not_included"},
    )
    return {
        "before": before,
        "unanswered": silent,
        "answered_not_included": [scene.amount(cash), scene.gaps(cash)],
    }


def _restore_unseen_activity() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "10000.00")
    expense = scene.record("expense", cash, "500.00", 3)
    scene.store.remove(expense.id, 1, "not mine")
    check = scene.observe(cash, "10000.00", 5)
    unanswered = outcome(lambda: scene.store.restore(expense.id, 2, "it was mine"))
    scene.store.restore(expense.id, 2, "it was mine", answers={check.id: "not_included"})
    return {
        "unanswered": unanswered,
        "balance": scene.amount(cash),
        "gaps": scene.gaps(cash),
    }


def _redate_check() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "10000.00")
    scene.record("expense", cash, "1000.00", 3)
    check = scene.observe(cash, "9000.00", 5)
    unreviewed = outcome(
        lambda: scene.store.correct(check.id, 1, "was the 2nd", as_of=local(2, 18))
    )
    return {
        "unreviewed": unreviewed,
        "balance": scene.amount(cash),
        "gaps": scene.gaps(cash),
    }


def _note_keeps_evidence() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "10000.00")
    scene.record("expense", cash, "2000.00", 3)
    check = scene.observe(cash, "7500.00", 5)
    scene.now = local(6)
    late = scene.act("expense", cash, "500.00", 4)
    scene.store.resolve(
        late.id,
        answers={check.id: "included"},
        expected_revision=scene.store.state.drafts[late.id].revision,
    )
    scene.confirm(late)
    before = scene.gaps(cash)
    scene.store.correct(check.id, 1, "add note", note="bank app")
    return {"before": before, "after": scene.gaps(cash)}


def _redate_opening_onto_day() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00", as_of=local(5, 18))
    opening = anchors(scene.store.book, cash.id)[0].id
    scene.record("expense", cash, "100.00", 3)
    return {
        "result": outcome(
            lambda: scene.store.correct(opening, 1, "was the 3rd", as_of=local(3, 18))
        )
    }


def _purchase_edits_recheck_refunds() -> dict:
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    purchase = scene.record("expense", cash, "100.00", 3, category="shopping")
    scene.record("refund", cash, "40.00", 5, refund_of=purchase.id, category="shopping")
    # Correction is reviewed on day 9, so the new purchase date is not future.
    scene.now = local(9)
    return {
        "later_date": outcome(
            lambda: scene.store.correct(
                purchase.id, 1, "date", occurred_on=local(9).date().isoformat()
            )
        ),
        "other_category": outcome(
            lambda: scene.store.correct(purchase.id, 1, "category", category="dining")
        ),
    }


def _custom_category_blocks_move() -> dict:
    scene = Scene()
    shop = scene.account("Negocio", "checking", "DOP", "5000.00", space_id="business")
    materials = scene.store.create_category("business", "Materiales", "spending")
    scene.record("expense", shop, "10.00", 2, category=materials.id)
    version = scene.store.book.accounts[shop.id].version
    return {
        "move": outcome(lambda: scene.store.move_account(shop.id, version, "personal"))
    }


def _unsupported_weighting_is_refused() -> dict:
    scene = Scene()
    car = scene.account("Carro", "vehicle", "DOP", "1000000.00", ownership_share_bps=5000)
    return {
        "unsupported": outcome(lambda: scene.position(car, weighting="half")),
        "full_still_works": scene.position(car, weighting="full")["DOP"]["assets"],
    }


def _check_correction_bound_to_account() -> dict:
    """A restamp refuses when concurrent activity moves the reviewed evidence."""
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    check = scene.observe(cash, "1000.00", 5)
    prepared_basis = {cash.id: scene.store.book.accounts[cash.id].version}
    prepared_check = {"prior": 100_000, "observed": 95_000, "difference": -5_000}
    missing = outcome(
        lambda: scene.store.correct(check.id, 1, "typo", amount="950.00")
    )
    empty_basis = outcome(
        lambda: scene.store.correct(
            check.id,
            1,
            "typo",
            amount="950.00",
            account_basis={},
            check=prepared_check,
        )
    )
    scene.now = local(8)
    late = scene.act("expense", cash, "100.00", 3)
    scene.store.resolve(
        late.id,
        answers={check.id: "included"},
        expected_revision=scene.store.state.drafts[late.id].revision,
    )
    scene.confirm(late)
    stale_basis = outcome(
        lambda: scene.store.correct(
            check.id,
            1,
            "typo",
            amount="950.00",
            account_basis=prepared_basis,
            check=prepared_check,
        )
    )
    fresh_basis = {cash.id: scene.store.book.accounts[cash.id].version}
    stale_evidence = outcome(
        lambda: scene.store.correct(
            check.id,
            1,
            "typo",
            amount="950.00",
            account_basis=fresh_basis,
            check=prepared_check,
        )
    )
    accepted = outcome(
        lambda: scene.store.correct(
            check.id,
            1,
            "typo",
            amount="950.00",
            account_basis=fresh_basis,
            check={"prior": 90_000, "observed": 95_000, "difference": 5_000},
        )
    )
    return {
        "missing_basis": missing,
        "empty_account_basis": empty_basis,
        "stale_account_basis": stale_basis,
        "stale_check_evidence": stale_evidence,
        "accepted": accepted,
    }


def _observation_basis_and_restamp_together() -> dict:
    """Observation field `basis` and account-version basis are separate params."""
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    check = scene.observe(cash, "1000.00", 5)
    both = scene.store.correct(
        check.id,
        1,
        "statement and typo",
        amount="950.00",
        basis="statement",
        account_basis={cash.id: scene.store.book.accounts[cash.id].version},
        check={"prior": 100_000, "observed": 95_000, "difference": -5_000},
    )
    return {
        "observation_basis": both.body.basis,
        "observed": both.body.amount,
        "revisions": len(both.revisions),
    }


def _distinct_bound_to_reviewed_matches() -> dict:
    """Distinct only covers the match set reviewed at resolve; a new match reopens."""
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "5000.00")
    first = scene.record("expense", cash, "500.00", 3)
    twin = scene.act("expense", cash, "500.00", 3, method="chat")
    scene.store.resolve(twin.id, distinct=True, expected_revision=twin.revision)
    after_distinct = scene.issues(twin)
    bound = scene.store.state.drafts[twin.id].distinct_of == (first.id,)
    other = scene.record("expense", cash, "400.00", 4)
    scene.store.correct(other.id, 1, "was 500 on the 3rd", amount="500.00", occurred_on=local(3).date().isoformat())
    after_new_match = scene.issues(twin)
    return {
        "suppressed_while_bound": after_distinct,
        "bound_to_reviewed_match": bound,
        "reopens_for_new_match": after_new_match,
        "lists_both": sorted(scene.refs(twin, "possible_duplicate"))
        == sorted([first.id, other.id]),
    }


def _preview_basis_requires_touched() -> dict:
    """An empty or partial Preview.basis cannot bypass account-version staleness."""
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    draft = scene.observation(cash, "1000.00", 5)
    preview = scene.store.preview(draft.id)
    empty = replace(preview, basis={})
    return {
        "empty_basis": outcome(lambda: scene.store.confirm(empty, "empty-basis")),
        "full_basis_still_works": outcome(
            lambda: scene.store.confirm(preview, "full-basis")
        ),
    }


def _remove_answers_limited_to_exposed() -> dict:
    """Removal answers may only name questions the trial removal exposes."""
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "10000.00")
    other = scene.account("Ahorros", "savings", "DOP", "5000.00")
    first = scene.observe(cash, "8000.00", 5)
    second = scene.observe(cash, "8000.00", 10)
    scene.now = local(11)
    late = scene.act("expense", cash, "2000.00", 3)
    scene.store.resolve(
        late.id,
        answers={first.id: "included"},
        expected_revision=scene.store.state.drafts[late.id].revision,
    )
    record = scene.confirm(late)
    # Foreign activity on another account: not exposed by removing `first`.
    foreign = scene.record("expense", other, "100.00", 11)
    off_account = outcome(
        lambda: scene.store.remove(
            first.id,
            1,
            "typo",
            answers={foreign.id: {second.id: "included"}},
        )
    )
    accepted = outcome(
        lambda: scene.store.remove(
            first.id,
            1,
            "typo",
            accept_reordering=True,
            account_basis=scene.account_basis(cash),
            answers={record.id: {second.id: "included"}},
        )
    )
    return {
        "off_account_answer": off_account,
        "exposed_answer_ok": accepted,
        "foreign_unchanged": scene.amount(other),
    }


def _observation_preview_requires_check() -> dict:
    """An observation confirm without Preview.check is stale, not a silent write."""
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    draft = scene.observation(cash, "1000.00", 5)
    preview = scene.store.preview(draft.id)
    stripped = replace(preview, check=None)
    return {
        "missing_check": outcome(lambda: scene.store.confirm(stripped, "no-check")),
        "with_check": outcome(lambda: scene.store.confirm(preview, "with-check")),
    }


def _remove_rejects_empty_answer_map() -> dict:
    """Empty nested answer maps must not revise unrelated activities."""
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "10000.00")
    other = scene.account("Ahorros", "savings", "DOP", "5000.00")
    first = scene.observe(cash, "8000.00", 5)
    second = scene.observe(cash, "8000.00", 10)
    scene.now = local(11)
    late = scene.act("expense", cash, "2000.00", 3)
    scene.store.resolve(
        late.id,
        answers={first.id: "included"},
        expected_revision=scene.store.state.drafts[late.id].revision,
    )
    record = scene.confirm(late)
    foreign = scene.record("expense", other, "100.00", 11)
    foreign_rev = len(scene.store.book.records[foreign.id].revisions)
    empty_map = outcome(
        lambda: scene.store.remove(
            first.id,
            1,
            "typo",
            answers={foreign.id: {}},
        )
    )
    return {
        "empty_nested_map": empty_map,
        "foreign_revisions_unchanged": len(scene.store.book.records[foreign.id].revisions)
        == foreign_rev,
        "still_needs_real_answer": outcome(lambda: scene.store.remove(first.id, 1, "typo")),
        "check_still_present": first.id in scene.store.book.records
        and not scene.store.book.records[first.id].removed,
        "exposed_still_works": outcome(
            lambda: scene.store.remove(
                first.id,
                1,
                "typo",
                accept_reordering=True,
                account_basis=scene.account_basis(cash),
                answers={record.id: {second.id: "included"}},
            )
        ),
    }


def _correction_dry_run_keeps_seq() -> dict:
    """Same-instant check dry-runs must keep the record's sequence.

    With seq forced to 0, a later same-time check sorts before its peer and
    accepts evidence that `_revise` then stamps differently.
    """
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    stamp = local(5, 18)
    scene.now = stamp
    first = scene.confirm(
        scene.draft(
            kind="balance_observation",
            account_id=cash.id,
            amount="1000.00",
            as_of=stamp.isoformat(),
            basis="user_check",
        )
    )
    second = scene.confirm(
        scene.draft(
            kind="balance_observation",
            account_id=cash.id,
            amount="900.00",
            as_of=stamp.isoformat(),
            basis="user_check",
        )
    )
    scene.now = local(6)
    late = scene.act("expense", cash, "100.00", 4)
    scene.store.resolve(
        late.id,
        answers={first.id: "included", second.id: "included"},
        expected_revision=late.revision,
    )
    scene.confirm(late)
    # Evidence matching a seq=0 dry-run (prior 90k) must be refused.
    wrong_order = outcome(
        lambda: scene.store.correct(
            second.id,
            1,
            "typo",
            amount="850.00",
            account_basis=scene.account_basis(cash),
            check={"prior": 90_000, "observed": 85_000, "difference": -5_000},
        )
    )
    scene.store.correct(
        second.id,
        1,
        "typo",
        amount="850.00",
        account_basis=scene.account_basis(cash),
        check={"prior": 100_000, "observed": 85_000, "difference": -15_000},
    )
    stamped = scene.store.book.records[second.id].revisions[-1]
    return {
        "wrong_order_evidence": wrong_order,
        "confirmed_expected": stamped.confirmed_expected,
        "confirmed_difference": stamped.confirmed_difference,
    }


def _reordering_bound_to_account_state() -> dict:
    """accept_reordering must bind to the account versions that produced review."""
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00", as_of=local(5))
    opening = anchors(scene.store.book, cash.id)[0].id
    first = scene.record("expense", cash, "100.00", 6)
    scene.now = local(7)
    unreviewed = outcome(
        lambda: scene.store.correct(opening, 1, "was the 7th", as_of=local(7))
    )
    prepared = scene.account_basis(cash)
    missing = outcome(
        lambda: scene.store.correct(
            opening, 1, "was the 7th", as_of=local(7), accept_reordering=True
        )
    )
    # Concurrent activity after the review bumps the account version.
    scene.record("expense", cash, "50.00", 6)
    stale = outcome(
        lambda: scene.store.correct(
            opening,
            1,
            "was the 7th",
            as_of=local(7),
            accept_reordering=True,
            account_basis=prepared,
        )
    )
    scene.store.correct(
        opening,
        1,
        "was the 7th",
        as_of=local(7),
        accept_reordering=True,
        account_basis=scene.account_basis(cash),
    )
    return {
        "unreviewed": unreviewed,
        "missing_basis": missing,
        "stale_basis": stale,
        "accepted": scene.store.book.records[opening].body.as_of.date().isoformat(),
        "first_still_present": first.id in scene.store.book.records,
    }


def _zone_change_restamps_check() -> dict:
    """Resubmitting the same as_of after a store TZ change must restamp.

    01:00Z is Sept 4 in America/Santo_Domingo and Sept 5 in UTC. A date-only
    expense on the 5th stays outside the check under the entry zone. Answering
    it included and then rewriting the zone without restamping would keep the
    old empty contained set and zero difference after that expense becomes
    same-day.
    """
    scene = Scene()
    cash = scene.account("Efectivo", "cash", "DOP", "1000.00")
    as_of = datetime(2026, 9, 5, 1, 0, tzinfo=ZoneInfo("UTC"))
    scene.now = as_of
    check = scene.confirm(
        scene.draft(
            kind="balance_observation",
            account_id=cash.id,
            amount="1000.00",
            as_of=as_of.isoformat(),
            basis="user_check",
        )
    )
    scene.now = local(6)
    expense = scene.record("expense", cash, "100.00", 5)
    before_zone = scene.store.book.records[check.id].body.zone
    before_contained = scene.store.book.records[check.id].revisions[-1].contained or ()
    scene.store.correct(
        expense.id, 1, "seen on check day", answers={check.id: "included"}
    )
    scene.store.tz = ZoneInfo("UTC")
    moved = outcome(lambda: scene.store.correct(check.id, 1, "reread", as_of=as_of))
    missing = outcome(
        lambda: scene.store.correct(
            check.id, 1, "reread", as_of=as_of, accept_reordering=True
        )
    )
    scene.store.correct(
        check.id,
        1,
        "reread",
        as_of=as_of,
        accept_reordering=True,
        account_basis=scene.account_basis(cash),
        check={"prior": 90_000, "observed": 100_000, "difference": 10_000},
    )
    revised = scene.store.book.records[check.id]
    stamped = revised.revisions[-1]
    return {
        "entry_zone": before_zone,
        "expense_outside_before": expense.id not in before_contained,
        "zone_change_moves_inclusion": moved,
        "zone_change_requires_basis": missing,
        "restamped_zone": stamped.body.zone,
        "expense_in_contents": expense.id in (stamped.contained or ()),
        "confirmed_difference": stamped.confirmed_difference,
    }


LIFECYCLE = (
    refund_partial_and_limits,
    refund_unlinked_and_cross_account,
    card_refund_credit_balance,
    notes_across_records,
    removal_and_restore,
    spaces_and_account_moves,
    custom_categories,
    plan_occurrence_counted_once,
    edits_that_move_money_need_review,
)
