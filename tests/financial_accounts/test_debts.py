"""Independent debt arithmetic over the same memory and Postgres fixture."""

from datetime import timedelta
from uuid import uuid4

import pytest
from argus.domain.planning.debt_schemas import DebtCreate, DebtEdit, DebtLink, DebtRecord
from argus.domain.planning.debts import DebtService
from argus.domain.planning.service import PlanService
from argus.domain.recording.errors import RecordingInputError
from argus.domain.recording.money_reads import current_activities
from argus.domain.recording.money_schemas import MoneyRequest
from argus.domain.recording.money_service import MoneyService
from argus.domain.recording.spending import spending

from tests.financial_accounts import test_loop_commands as shared
from tests.financial_accounts.test_loop_commands import NOW
from tests.financial_accounts.test_personal_money import account

scene = shared.scene


def save(scene, **values):
    money = MoneyService(scene[0])
    preview = money.preview(user_id=scene[1], request=MoneyRequest(**values))
    assert preview["ready"]
    request = MoneyRequest.model_validate(preview["reviewed_request"]).model_copy(
        update={"preview_token": preview["preview_token"]}
    )
    return money.write(user_id=scene[1], request=request, idempotency_key=str(uuid4()))


def setup(scene):
    cash = account(scene, amount="2000")
    loan = account(scene, "other_debt", amount="1000")
    debts = DebtService(PlanService(scene[0]))
    created = debts.create(
        scene[1],
        DebtCreate(
            debt_account_id=loan,
            name="Loan",
            source_account_id=cash,
            amount="500",
            schedule={"cadence": "monthly", "start_date": NOW.date()},
        ),
        str(uuid4()),
    )["debt"]
    return debts, cash, loan, created


def record(
    scene, debts, progress, cash, loan, total, principal, interest, fees, oid=None
):
    body = DebtRecord(
        expected_version=progress["debt"]["version"],
        occurrence_id=oid,
        activity=MoneyRequest(
            kind="debt_payment",
            source_account_id=cash,
            destination_account_id=loan,
            amount=total,
            principal=principal,
            interest=interest,
            fees=fees,
            occurred_at=NOW,
        ),
    )
    preview = debts.preview(scene[1], progress["debt"]["id"], body)
    assert preview["money"]["ready"]
    reviewed = MoneyRequest.model_validate(
        preview["money"]["reviewed_request"]
    ).model_copy(update={"preview_token": preview["money"]["preview_token"]})
    return debts.record(
        scene[1],
        progress["debt"]["id"],
        body.model_copy(update={"activity": reviewed}),
        str(uuid4()),
    )


def test_partial_payments_costs_and_real_returns_reopen_current_debt(scene):
    debts, cash, loan, progress = setup(scene)
    oid = progress["occurrences"][0]["id"]
    first = record(scene, debts, progress, cash, loan, "350", "300", "40", "10", oid)
    assert first["debt"]["balance"]["amount_minor"] == -70000
    assert first["debt"]["occurrences"][0]["remaining_minor"] == 15000
    assert first["activity"]["category_id"] == "interest_fees"
    second = record(scene, debts, first["debt"], cash, loan, "150", "130", "15", "5", oid)
    assert second["debt"]["occurrences"][0]["status"] == "fulfilled"
    extra = record(scene, debts, second["debt"], cash, loan, "800", "750", "40", "10")
    assert extra["debt"]["state"] == "recorded_clear"
    assert extra["debt"]["balance"]["amount_minor"] == 18000
    assert extra["debt"]["occurrences"][1]["remaining_minor"] == 50000
    returned = save(
        scene,
        kind="payment_reversal",
        source_account_id=cash,
        destination_account_id=loan,
        amount="800",
        principal="750",
        interest="40",
        fees="10",
        reversal_of_activity_id=extra["activity"]["activity_id"],
        occurred_at=NOW,
    )
    assert returned["activity"]["reversal_of_revision"] == 1
    current = debts.get(scene[1], progress["debt"]["id"])
    assert current["state"] == "active" and current["balance"]["amount_minor"] == -57000
    original = MoneyService(scene[0]).detail(
        user_id=scene[1], activity_id=extra["activity"]["activity_id"]
    )
    assert original["amount_minor"] == 80000 and original["revision"] == 1
    actual = spending(
        current_activities(scene[0].list_accounts(user_id=scene[1])),
        currency="DOP",
        start=NOW - timedelta(days=1),
        end=NOW + timedelta(days=1),
    )
    assert actual.purchases == 12000 and actual.refunds == 5000 and actual.net == 7000


def test_return_components_capped_and_original_corrections_guard_returns(scene):
    debts, cash, loan, progress = setup(scene)
    receipt = record(scene, debts, progress, cash, loan, "350", "300", "40", "10")
    original = receipt["activity"]
    save(
        scene,
        kind="payment_reversal",
        source_account_id=cash,
        destination_account_id=loan,
        amount="100",
        principal="80",
        interest="15",
        fees="5",
        reversal_of_activity_id=original["activity_id"],
        occurred_at=NOW,
    )
    with pytest.raises(RecordingInputError, match="payment_return_limit"):
        save(
            scene,
            kind="payment_reversal",
            source_account_id=cash,
            destination_account_id=loan,
            amount="20",
            principal="0",
            interest="14",
            fees="6",
            reversal_of_activity_id=original["activity_id"],
            occurred_at=NOW,
        )
    with pytest.raises(RecordingInputError, match="payment_return_limit"):
        MoneyService(scene[0]).preview(
            user_id=scene[1],
            activity_id=original["activity_id"],
            request=MoneyRequest(
                kind="debt_payment",
                source_account_id=cash,
                destination_account_id=loan,
                amount="100",
                principal="70",
                interest="25",
                fees="5",
                occurred_at=NOW,
                expected_revision=1,
                reason="Correct original",
            ),
        )


def test_missing_split_never_guessed_and_zero_principal_retained(scene):
    debts, cash, loan, progress = setup(scene)
    with pytest.raises(RecordingInputError, match="payment_split_required"):
        save(
            scene,
            kind="debt_payment",
            source_account_id=cash,
            destination_account_id=loan,
            amount="20",
            principal="0",
            interest="20",
            occurred_at=NOW,
        )
    result = record(scene, debts, progress, cash, loan, "20", "0", "20", "0")
    assert result["activity"]["principal_minor"] == 0
    assert result["debt"]["balance"]["amount_minor"] == -100000
    assert len(result["activity"]["legs"]) == 2


def test_lifecycle_replay_active_unique_and_link_changes_no_balance(scene):
    debts, cash, loan, progress = setup(scene)
    did = progress["debt"]["id"]
    with pytest.raises(RecordingInputError, match="debt_plan_exists"):
        debts.create(
            scene[1],
            DebtCreate(
                debt_account_id=loan,
                name="Duplicate",
                source_account_id=cash,
                amount="10",
                schedule={"cadence": "once", "start_date": NOW.date()},
            ),
            str(uuid4()),
        )
    existing = save(
        scene,
        kind="debt_payment",
        source_account_id=cash,
        destination_account_id=loan,
        amount="30",
        principal="25",
        interest="5",
        fees="0",
        occurred_at=NOW,
    )["activity"]
    versions = {
        s.account.id: s.account.version for s in scene[0].list_accounts(user_id=scene[1])
    }
    body = DebtLink(
        expected_version=1,
        activity_id=existing["activity_id"],
        activity_revision=1,
        occurrence_id=progress["occurrences"][0]["id"],
        expected_account_versions=versions,
    )
    linked = debts.link(scene[1], did, body, "link")
    replay = debts.link(scene[1], did, body, "link")
    assert replay["replayed"] and linked["debt"] == replay["debt"]
    assert linked["debt"]["occurrences"][0]["remaining_minor"] == 47000
    archived = debts.edit(
        scene[1], did, DebtEdit(expected_version=2, archived=True), "archive"
    )
    assert archived["debt"]["debt"]["archived"]
    restored = debts.edit(
        scene[1], did, DebtEdit(expected_version=3, archived=False), "restore"
    )
    assert (
        not restored["debt"]["debt"]["archived"]
        and restored["debt"]["balance"]["amount_minor"] == -97500
    )


def test_omitted_default_category_correction_survives_existing_returns(scene):
    debts, cash, loan, progress = setup(scene)
    original = record(scene, debts, progress, cash, loan, "350", "300", "40", "10")[
        "activity"
    ]
    save(
        scene,
        kind="payment_reversal",
        source_account_id=cash,
        destination_account_id=loan,
        amount="100",
        principal="80",
        interest="15",
        fees="5",
        reversal_of_activity_id=original["activity_id"],
        occurred_at=NOW,
    )
    preview = MoneyService(scene[0]).preview(
        user_id=scene[1],
        activity_id=original["activity_id"],
        request=MoneyRequest(
            kind="debt_payment",
            source_account_id=cash,
            destination_account_id=loan,
            amount="350",
            principal="300",
            interest="40",
            fees="10",
            occurred_at=NOW,
            expected_revision=1,
            reason="Fix note",
        ),
    )
    assert (
        preview["ready"] and preview["reviewed_request"]["category_id"] == "interest_fees"
    )


@pytest.mark.parametrize("account_type", ["other_debt", "credit_card"])
def test_explicit_monthly_model_uses_recorded_debt_without_clearing_it(
    scene, account_type
):
    from argus.domain.planning.debt_projection import payoff
    from argus.domain.recording.schemas import account_response

    debts, cash, loan, progress = setup(scene)
    balance = account_response(
        scene[0].get(user_id=scene[1], account_id=loan)
    ).balance.model_copy(update={"as_of": NOW})
    item = {
        "currency": "DOP",
        "archived": False,
        "assumptions": {
            "annual_rate_percent": "12",
            "recurring_fees": "0",
            "first_period_start": NOW.date().isoformat(),
            "no_new_borrowing": True,
        },
        "segments": [
            {
                "amount_minor": 50000,
                "schedule": {
                    "cadence": "monthly",
                    "start_date": "2026-10-20",
                    "month_days": [],
                },
            }
        ],
    }
    result = payoff(item, balance, [], NOW.date(), account_type)
    assert result["state"] == "conditional" and result["payments"] == 3
    assert (
        result["payoff_date"] == "2026-12-20" and result["total_interest_minor"] == "1525"
    )
    assert balance.amount_minor == -100000
    from datetime import timedelta

    assert (
        payoff(item, balance, [], NOW.date() + timedelta(days=1), account_type) == result
    )
    assert (
        payoff(item, balance, [], NOW.date() + timedelta(days=31), account_type)["state"]
        == "unavailable"
    )
    item["assumptions"] = None
    assert (
        payoff(item, balance, [], NOW.date(), account_type)["reason"] == "terms_missing"
    )
