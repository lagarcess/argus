"""Command lifecycle and atomic reuse of the real finance owners."""

import asyncio
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

import pytest
from platform_identity_factory import identity_context
from server.platform import commands, investing, ledger, planning, services
from server.platform.common import PlatformError, active_context, now
from server.platform.identity_lifecycle import advance_household_generation
from server.platform.ledger_contracts import AccountCreate, AccountPatch
from server.store import Store, TransactionBoundaryError


@pytest.fixture
def setup(tmp_path):
    store = Store(tmp_path / "commands.sqlite")
    context = identity_context(store)
    ledger.initialize(store)
    planning.initialize(store)
    investing.initialize(store)
    services.initialize(store)
    commands.initialize(store)
    with store.connection(write=True) as connection:
        connection.execute(
            "CREATE TABLE command_test_messages(id TEXT PRIMARY KEY,proposal_id TEXT,record_id TEXT)"
        )
    return store, context, commands.CommandService(store)


def prepare(
    service,
    context,
    name="account.create",
    args=None,
    request_id="request-1",
    conversation_id="conversation-1",
):
    return service.prepare(
        context,
        name,
        args
        or {
            "name": "Reserve",
            "kind": "savings",
            "currency": "USD",
            "opening_balance": "100",
        },
        conversation_id,
        request_id,
    )


def test_confirm_replay_survives_new_pending_proposal_and_concurrent_confirmation(setup):
    store, ctx, service = setup
    proposal = prepare(service, ctx)

    def append(bound, context, receipt):
        with bound.connection(write=True) as connection:
            connection.execute(
                "INSERT INTO command_test_messages VALUES(?,?,?)",
                ("reply", receipt.proposal_id, receipt.record_id),
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(
            pool.map(
                lambda _: service.confirm(
                    ctx, proposal.proposal_id, proposal.revision, on_receipt=append
                ),
                range(2),
            )
        )
    assert receipts[0] == receipts[1]
    prepare(service, ctx, request_id="request-new")
    assert (
        service.confirm(ctx, proposal.proposal_id, proposal.revision, on_receipt=append)
        == receipts[0]
    )
    account = ledger.get_account(receipts[0].record_id, store, ctx)
    assert account["name"] == "Reserve" and account["balance"] == "100.00"
    with store.connection() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM command_test_messages").fetchone()[0]
            == 1
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM p_command_receipts").fetchone()[0]
            == 1
        )


def test_mid_append_failure_rolls_back_domain_receipt_and_consumption(setup):
    store, ctx, service = setup
    proposal = prepare(service, ctx)
    before = len(ledger.account_balances(store, ctx))

    def broken(bound, context, receipt):
        with bound.connection(write=True) as connection:
            connection.execute(
                "INSERT INTO command_test_messages VALUES(?,?,?)",
                ("reply", receipt.proposal_id, receipt.record_id),
            )
        raise RuntimeError("injected transcript failure")

    with pytest.raises(RuntimeError, match="transcript failure"):
        service.confirm(ctx, proposal.proposal_id, proposal.revision, on_receipt=broken)
    assert len(ledger.account_balances(store, ctx)) == before
    assert service.get(ctx, proposal.proposal_id).status == "pending"
    with store.connection() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM command_test_messages").fetchone()[0]
            == 0
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM p_command_receipts").fetchone()[0]
            == 0
        )
    receipt = service.confirm(ctx, proposal.proposal_id, proposal.revision)
    assert ledger.get_account(receipt.record_id, store, ctx)["balance"] == "100.00"


def test_inner_caught_database_failure_poisons_entire_outer_transaction(setup):
    store, _, _ = setup
    with pytest.raises(TransactionBoundaryError, match="poisoned"):
        with store.transaction() as bound:
            with bound.connection(write=True) as connection:
                connection.execute(
                    "INSERT INTO command_test_messages VALUES(?,?,?)", ("one", "p", "r")
                )
                try:
                    connection.execute(
                        "INSERT INTO command_test_messages VALUES(?,?,?)",
                        ("one", "p", "r"),
                    )
                except Exception:
                    pass
    with store.connection() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM command_test_messages").fetchone()[0]
            == 0
        )
    with store.transaction() as bound:
        with bound.connection(write=True) as connection:
            connection.execute(
                "INSERT INTO command_test_messages VALUES(?,?,?)", ("success", "p", "r")
            )
    with store.connection() as connection:
        assert (
            connection.execute("SELECT id FROM command_test_messages").fetchone()[0]
            == "success"
        )


@pytest.mark.parametrize(
    "operation",
    [
        lambda db: db.commit(),
        lambda db: db.rollback(),
        lambda db: db.executescript("SELECT 1"),
        lambda db: db.execute("COMMIT"),
        lambda db: db.execute("CREATE TABLE escaped(id TEXT)"),
        lambda db: db.execute("ATTACH DATABASE ':memory:' AS escape"),
        lambda db: db.execute("SELECT 1").connection,
    ],
)
def test_connection_escape_is_rejected_and_rolled_back(setup, operation):
    store, _, _ = setup
    with pytest.raises((TransactionBoundaryError, sqlite3.DatabaseError)):
        with store.transaction() as bound:
            with bound.connection(write=True) as connection:
                connection.execute(
                    "INSERT INTO command_test_messages VALUES(?,?,?)",
                    ("escape", "p", "r"),
                )
                operation(connection)
    with store.connection() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM command_test_messages").fetchone()[0]
            == 0
        )


def test_bound_store_rejects_cross_thread_closed_snapshot_and_async_yield(setup):
    store, _, _ = setup
    with pytest.raises(TransactionBoundaryError):
        with store.transaction() as bound:
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(lambda: bound._execute("SELECT 1", (), many=False)).result()
    with store.transaction() as closed:
        with closed.connection() as connection:
            assert connection.execute("SELECT 1").fetchone()[0] == 1
    with pytest.raises(TransactionBoundaryError, match="closed"):
        with closed.connection():
            pass
    with pytest.raises(TransactionBoundaryError, match="snapshot"):
        with store.transaction() as bound:
            bound.read_snapshot()

    async def illegal_yield():
        with store.transaction() as bound:
            with bound.connection(write=True) as connection:
                connection.execute(
                    "INSERT INTO command_test_messages VALUES(?,?,?)", ("await", "p", "r")
                )
            await asyncio.sleep(0)

    with pytest.raises(TransactionBoundaryError, match="poisoned"):
        asyncio.run(illegal_yield())
    with store.connection() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM command_test_messages").fetchone()[0]
            == 0
        )


@pytest.mark.parametrize(
    "currency,valid,invalid", [("JPY", "100", "100.5"), ("KWD", "10.125", "10.1251")]
)
def test_owned_currency_and_minor_precision_are_preserved(
    setup, currency, valid, invalid
):
    store, ctx, service = setup
    account = ledger.create_account(
        AccountCreate(
            name="Currency reserve",
            kind="cash",
            currency=currency,
            opening_balance=valid,
            idempotency_key=currency,
        ),
        store,
        ctx,
    )
    args = {
        "account_id": account["id"],
        "date": "2026-09-20",
        "merchant": "Local purchase",
        "amount": "-" + valid,
        "category": "groceries",
        "kind": "expense",
    }
    proposal = prepare(service, ctx, "transaction.create", args)
    assert (
        proposal.currency[0].kind == "account" and proposal.currency[0].code == currency
    )
    receipt = service.confirm(ctx, proposal.proposal_id, proposal.revision)
    assert receipt.record_id
    assert Decimal(ledger.get_account(account["id"], store, ctx)["balance"]) == 0
    with pytest.raises(PlatformError, match="invalid_money_precision"):
        prepare(
            service,
            ctx,
            "transaction.create",
            {**args, "amount": "-" + invalid},
            request_id="bad",
        )
    with pytest.raises(PlatformError, match="command_currency_mismatch"):
        service.prepare(
            ctx,
            "transaction.create",
            args,
            "conv",
            "currency-conflict",
            {"kind": "explicit", "code": "USD"},
        )


def test_pending_revision_expiry_dependency_reset_and_role_fences(setup):
    store, ctx, service = setup
    pending = prepare(service, ctx)
    with pytest.raises(PlatformError, match="proposal_revision_changed"):
        service.confirm(ctx, pending.proposal_id, pending.revision + 1)
    newer = prepare(service, ctx, request_id="second")
    with pytest.raises(PlatformError, match="proposal_not_pending"):
        service.confirm(ctx, pending.proposal_id, pending.revision)
    with store.connection(write=True) as connection:
        document = json.loads(
            connection.execute(
                "SELECT document FROM p_command_proposals WHERE id=?",
                (newer.proposal_id,),
            ).fetchone()[0]
        )
        document["expires_at"] = (now() - timedelta(seconds=1)).isoformat()
        connection.execute(
            "UPDATE p_command_proposals SET document=? WHERE id=?",
            (json.dumps(document), newer.proposal_id),
        )
    with pytest.raises(PlatformError, match="proposal_expired"):
        service.confirm(ctx, newer.proposal_id, newer.revision)
    edit = prepare(
        service,
        ctx,
        "account.edit",
        {"record_id": "acct-demo-01", "changes": {"name": "Renamed"}},
        request_id="edit",
    )
    ledger.patch_account(
        "acct-demo-01", AccountPatch(name="Changed elsewhere"), store, ctx
    )
    with pytest.raises(PlatformError, match="proposal_dependency_changed"):
        service.confirm(ctx, edit.proposal_id, edit.revision)
    fresh = prepare(service, ctx, request_id="reset")
    with store.connection(write=True) as connection:
        advance_household_generation(connection, ctx.household_id)
    with pytest.raises(PlatformError, match="household_data_changed"):
        service.confirm(ctx, fresh.proposal_id, fresh.revision)
    with store.connection() as connection:
        current = active_context(
            connection,
            user_id=ctx.user_id,
            household_id=ctx.household_id,
            session_id=ctx.session_id,
        )
    with pytest.raises(PlatformError, match="household_data_changed"):
        service.confirm(current, fresh.proposal_id, fresh.revision)
    role_proposal = prepare(service, current, request_id="role")
    with store.connection(write=True) as connection:
        connection.execute(
            "UPDATE p_memberships SET role='editor' WHERE user_id=? AND household_id=?",
            (ctx.user_id, ctx.household_id),
        )
    with pytest.raises(PlatformError, match="household_access_changed"):
        service.confirm(current, role_proposal.proposal_id, role_proposal.revision)


def test_followup_preserves_unmentioned_typed_inputs_and_cancel_is_idempotent(setup):
    store, ctx, service = setup
    initial = prepare(
        service,
        ctx,
        "goal.create",
        {
            "name": "Reserve",
            "currency": "USD",
            "target_amount": "1000",
            "target_date": "2028-09-20",
            "monthly_contribution": "125",
        },
    )
    revised = service.revise(
        ctx,
        initial.proposal_id,
        initial.revision,
        {"target_amount": "2000"},
        request_id="revise",
    )
    assert (
        revised.arguments["monthly_contribution"] == "125"
        and revised.arguments["target_date"] == "2028-09-20"
    )
    receipt = service.confirm(ctx, revised.proposal_id, revised.revision)
    goal = next(
        row
        for row in planning.list_goals(store, ctx)["items"]
        if row["id"] == receipt.record_id
    )
    assert goal["target_amount"] == "2000" and goal["monthly_contribution"] == "125"
    pending = prepare(service, ctx, request_id="cancel")
    assert (
        service.cancel(ctx, pending.proposal_id, pending.revision).status == "cancelled"
    )
    assert (
        service.cancel(ctx, pending.proposal_id, pending.revision).status == "cancelled"
    )


def test_every_declared_handler_uses_atomic_canonical_writes(setup):
    store, ctx, service = setup
    ids, seen = {}, set()
    tables = (
        "p_accounts",
        "p_transactions",
        "p_transaction_splits",
        "p_ledger_commands",
        "p_plans",
        "p_goal_allocations",
        "p_scenarios",
        "p_investment_holdings",
        "p_credit_accounts",
        "p_tax_organizers",
        "p_tax_scenarios",
        "p_tax_items",
        "p_estate_documents",
        "p_estate_checklist",
        "p_investment_books",
        "p_investment_positions",
        "p_investment_recurring_plans",
        "p_investment_recurring_runs",
        "p_bill_occurrences",
        "p_estate_assets",
        "p_estate_contacts",
        "p_estate_beneficiaries",
        "p_memories",
    )

    def snapshot():
        with store.connection() as connection:
            return {
                table: [
                    tuple(row)
                    for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")
                ]
                for table in tables
            }

    def execute(name, args):
        before = snapshot()
        proposal = prepare(service, ctx, name, args, request_id=name)
        assert snapshot() == before, name + " prepare must not write finance records"

        def broken(bound, context, receipt):
            raise RuntimeError("after canonical write")

        with pytest.raises(RuntimeError, match="after canonical write"):
            service.confirm(
                ctx, proposal.proposal_id, proposal.revision, on_receipt=broken
            )
        assert snapshot() == before, name + " must fully roll back"
        assert service.get(ctx, proposal.proposal_id).status == "pending"
        receipt = service.confirm(ctx, proposal.proposal_id, proposal.revision)
        assert receipt.fields and receipt.evidence and receipt.target.record_id
        assert service.confirm(ctx, proposal.proposal_id, proposal.revision) == receipt
        ids[name] = receipt.record_id
        seen.add(name)
        return receipt

    execute(
        "account.create",
        {
            "name": "Command cash",
            "kind": "cash",
            "currency": "USD",
            "opening_balance": "5000",
        },
    )
    execute(
        "account.edit",
        {"record_id": ids["account.create"], "changes": {"name": "Revised cash"}},
    )
    execute(
        "transaction.create",
        {
            "account_id": ids["account.create"],
            "date": "2026-09-20",
            "merchant": "Corner store",
            "amount": "-10",
            "category": "groceries",
            "kind": "expense",
        },
    )
    execute(
        "transaction.edit",
        {
            "record_id": ids["transaction.create"],
            "changes": {"notes": "Receipt retained"},
        },
    )
    execute(
        "budget.create",
        {"currency": "USD", "category": "groceries", "month": "2027-01", "limit": "350"},
    )
    execute(
        "budget.edit", {"record_id": ids["budget.create"], "changes": {"limit": "400"}}
    )
    execute(
        "bill.create",
        {
            "currency": "USD",
            "name": "Phone",
            "account_id": ids["account.create"],
            "category": "utilities",
            "amount": "50",
            "anchor_date": "2026-09-30",
        },
    )
    execute("bill.edit", {"record_id": ids["bill.create"], "changes": {"amount": "55"}})
    execute(
        "bill.payment.record",
        {"record_id": ids["bill.create"], "values": {"due_date": "2026-09-30"}},
    )
    execute(
        "goal.create",
        {
            "currency": "USD",
            "name": "Course",
            "target_amount": "1000",
            "target_date": "2028-01-01",
            "monthly_contribution": "50",
        },
    )
    execute(
        "goal.edit",
        {"record_id": ids["goal.create"], "changes": {"target_amount": "1200"}},
    )
    execute(
        "goal.allocate",
        {
            "record_id": ids["goal.create"],
            "values": {
                "allocations": [{"account_id": ids["account.create"], "amount": "100"}]
            },
        },
    )
    execute(
        "scenario.create",
        {
            "name": "Time away",
            "template": "sabbatical",
            "inputs": {
                "currency": "USD",
                "initial_balance": "10000",
                "monthly_withdrawal": "100",
                "horizon_years": 1,
            },
        },
    )
    execute(
        "holding.create",
        {
            "symbol": "XYZ",
            "name": "Manual holding",
            "currency": "USD",
            "quantity": "2",
            "total_cost": "100",
            "as_of": "2026-09-20",
        },
    )
    execute(
        "holding.edit", {"record_id": ids["holding.create"], "changes": {"quantity": "3"}}
    )
    execute(
        "credit.create",
        {
            "name": "Local credit",
            "currency": "USD",
            "balance": "100",
            "credit_limit": "1000",
            "apr_pct": "0",
            "minimum_payment": "10",
            "as_of": "2026-09-20",
        },
    )
    execute(
        "credit.edit",
        {"record_id": ids["credit.create"], "changes": {"minimum_payment": "15"}},
    )
    execute("tax.organizer.create", {"currency": "USD", "country": "US", "year": 2029})
    execute(
        "tax.item.create",
        {
            "organizer_id": ids["tax.organizer.create"],
            "kind": "income",
            "title": "Recorded consulting",
            "amount": "1000",
            "effective_on": "2029-09-20",
        },
    )
    execute(
        "tax.scenario",
        {"organizer_id": ids["tax.organizer.create"], "user_rate_pct": "10"},
    )
    execute(
        "estate.asset.create",
        {
            "name": "Archive asset",
            "currency": "USD",
            "value": "100",
            "as_of": "2026-09-20",
        },
    )
    execute("estate.contact.create", {"name": "Alex", "relationship": "Sibling"})
    execute(
        "estate.beneficiaries.set",
        {
            "record_id": ids["estate.asset.create"],
            "values": {
                "shares": [
                    {"contact_id": ids["estate.contact.create"], "share_pct": "100"}
                ]
            },
        },
    )
    execute(
        "estate.document.create",
        {
            "title": "Inventory reference",
            "location": "Home document folder",
            "effective_on": "2026-09-20",
        },
    )
    execute("estate.checklist.create", {"title": "Review inventory with household"})
    execute(
        "investing.recurring.create",
        {
            "book_id": "book-demo-usd",
            "cadence": "monthly",
            "next_run_on": "2026-10-31",
            "symbol": "VTI",
            "amount": "100",
        },
    )
    execute(
        "memory.create", {"content": "I prefer monthly summaries.", "confirmed": True}
    )
    execute(
        "memory.edit",
        {
            "record_id": ids["memory.create"],
            "changes": {"content": "I prefer quarterly summaries.", "confirmed": True},
        },
    )
    assert seen == {item.name for item in commands.catalog()} == set(commands.REGISTRY)
    assert ledger.get_account(ids["account.create"], store, ctx)["balance"] == "4935.00"
    with store.connection() as connection:
        assert commands.usage_data(connection, ctx)["receipts"] == len(seen)


def test_prepare_revision_replays_and_rejected_inputs_preserve_current(setup):
    store, ctx, service = setup
    initial = prepare(service, ctx)
    assert prepare(service, ctx) == initial
    with pytest.raises(PlatformError, match="command_request_conflict"):
        prepare(
            service, ctx, args={"name": "Different", "kind": "cash", "currency": "USD"}
        )
    with pytest.raises(PlatformError, match="command_currency_required"):
        prepare(
            service,
            ctx,
            args={"name": "Missing currency", "kind": "cash"},
            request_id="bad",
        )
    assert service.current(ctx, initial.conversation_id) == initial
    revised = service.revise(
        ctx,
        initial.proposal_id,
        initial.revision,
        {"name": "Changed"},
        request_id="revision",
    )
    assert (
        service.revise(
            ctx,
            initial.proposal_id,
            initial.revision,
            {"name": "Changed"},
            request_id="revision",
        )
        == revised
    )
    with pytest.raises(PlatformError, match="command_request_conflict"):
        service.revise(
            ctx,
            initial.proposal_id,
            initial.revision,
            {"name": "Conflicting"},
            request_id="revision",
        )

    def fail_prepare(bound, context, proposal):
        raise RuntimeError("proposal transcript failure")

    with pytest.raises(RuntimeError, match="proposal transcript failure"):
        service.prepare(
            ctx,
            "account.create",
            initial.arguments,
            "conversation-1",
            "failed-append",
            on_proposal=fail_prepare,
        )
    assert service.current(ctx, "conversation-1") == revised


def test_private_choices_and_reset_cleanup(setup):
    store, ctx, service = setup
    proposal = prepare(service, ctx)
    service.confirm(ctx, proposal.proposal_id, proposal.revision)
    choices = service.record_choices(ctx, limit=10)
    assert len(choices["items"]) == 10 and choices["has_more"]
    assert "account" in {item["kind"] for item in choices["items"]}
    other = identity_context(store, user_id="command-other", household_id="command-other")
    assert not service.record_choices(other)["items"]
    with pytest.raises(PlatformError, match="proposal_not_found"):
        service.get(other, proposal.proposal_id)
    with pytest.raises(PlatformError):
        service.resolve_record(other, "account", "acct-demo-01")
    with store.connection(write=True) as connection:
        assert commands.export_data(connection, ctx)["p_command_receipts"]
        commands.clear_data(connection, ctx)
    commands.initialize(store)
    with store.connection() as connection:
        assert commands.usage_data(connection, ctx) == {"proposals": 0, "receipts": 0}


def test_deleted_user_and_fresh_viewer_cannot_confirm_pending_command(setup):
    store, ctx, service = setup
    proposal = prepare(service, ctx)
    with store.connection(write=True) as connection:
        connection.execute(
            "UPDATE p_memberships SET role='viewer' WHERE household_id=? AND user_id=?",
            (ctx.household_id, ctx.user_id),
        )
        viewer = active_context(
            connection,
            user_id=ctx.user_id,
            household_id=ctx.household_id,
            session_id=ctx.session_id,
        )
    with pytest.raises(PlatformError) as rejected:
        service.confirm(viewer, proposal.proposal_id, proposal.revision)
    assert rejected.value.status == 403
    with store.connection(write=True) as connection:
        connection.execute(
            "UPDATE p_memberships SET role='owner' WHERE household_id=? AND user_id=?",
            (ctx.household_id, ctx.user_id),
        )
        connection.execute(
            "UPDATE p_users SET deleted_at=? WHERE id=?", (now().isoformat(), ctx.user_id)
        )
    with pytest.raises(PlatformError, match="authentication_required"):
        service.confirm(ctx, proposal.proposal_id, proposal.revision)
    with store.connection() as connection:
        assert commands.usage_data(connection, ctx)["receipts"] == 0


def test_async_callbacks_and_store_escape_cannot_leave_partial_command(setup):
    store, ctx, service = setup
    proposal = prepare(service, ctx)

    async def invalid_callback(bound, context, receipt):
        return None

    with pytest.raises(PlatformError, match="async_command_callback_forbidden"):
        service.confirm(
            ctx, proposal.proposal_id, proposal.revision, on_receipt=invalid_callback
        )
    assert service.get(ctx, proposal.proposal_id).status == "pending"

    def escape(bound, context, receipt):
        bound._open_connection()

    with pytest.raises(TransactionBoundaryError, match="capability"):
        service.confirm(ctx, proposal.proposal_id, proposal.revision, on_receipt=escape)
    assert service.get(ctx, proposal.proposal_id).status == "pending"
    with store.connection() as connection:
        assert commands.usage_data(connection, ctx)["receipts"] == 0


def test_account_selected_currency_is_disclosed_and_cannot_be_changed_by_language(setup):
    store, ctx, service = setup
    selected = ledger.create_account(
        AccountCreate(
            name="Selected yen",
            kind="cash",
            currency="JPY",
            opening_balance="100",
            idempotency_key="yen-context",
        ),
        store,
        ctx,
    )
    args = {"name": "Yen goal", "target_amount": "1000", "target_date": "2029-01-01"}
    proposal = service.prepare(
        ctx,
        "goal.create",
        args,
        "choice",
        "request",
        {"kind": "account", "account_id": selected["id"]},
    )
    assert proposal.arguments["currency"] == "JPY"
    assert proposal.currency[0].record_id == selected["id"]
    revised = service.revise(
        ctx,
        proposal.proposal_id,
        proposal.revision,
        {"target_amount": "2000"},
        request_id="currency-revision",
    )
    assert revised.currency == proposal.currency
    proposal = revised
    with pytest.raises(PlatformError, match="command_currency_mismatch"):
        service.prepare(
            ctx,
            "goal.create",
            {**args, "currency": "USD"},
            "choice",
            "conflict",
            {"kind": "account", "account_id": selected["id"]},
        )
    assert service.current(ctx, "choice") == proposal
    receipt = service.confirm(ctx, proposal.proposal_id, proposal.revision)
    assert receipt.target.query["record_id"] == receipt.record_id
    with store.connection(write=True) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="immutable_command_receipt"):
            connection.execute(
                "UPDATE p_command_receipts SET document='{}' WHERE id=?",
                (receipt.receipt_id,),
            )


def test_household_conversation_projection_does_not_grant_write_authority(setup):
    store, ctx, service = setup
    proposal = prepare(service, ctx)
    partner = identity_context(
        store, user_id="command-partner", household_id=ctx.household_id, role="editor"
    )
    assert (
        service.read_for_conversation(
            partner, proposal.proposal_id, proposal.conversation_id
        )
        == proposal
    )
    with pytest.raises(PlatformError, match="proposal_not_found"):
        service.read_for_conversation(partner, proposal.proposal_id, "wrong-conversation")
    for operation in (
        lambda: service.get(partner, proposal.proposal_id),
        lambda: service.confirm(partner, proposal.proposal_id, proposal.revision),
        lambda: service.cancel(partner, proposal.proposal_id, proposal.revision),
        lambda: service.revise(
            partner,
            proposal.proposal_id,
            proposal.revision,
            {"name": "Partner change"},
            request_id="partner-revise",
        ),
    ):
        with pytest.raises(PlatformError, match="proposal_not_found"):
            operation()
    assert service.current(partner, proposal.conversation_id) is None
    other = identity_context(
        store, user_id="command-foreign", household_id="command-foreign"
    )
    with pytest.raises(PlatformError, match="proposal_not_found"):
        service.read_for_conversation(
            other, proposal.proposal_id, proposal.conversation_id
        )


def test_inspection_and_confirmation_share_currency_and_preserved_revision_inputs(setup):
    store, ctx, service = setup
    account = ledger.create_account(
        AccountCreate(
            name="Yen account",
            kind="cash",
            currency="JPY",
            opening_balance="100",
            idempotency_key="inspect-yen",
        ),
        store,
        ctx,
    )
    args = {
        "account_id": account["id"],
        "date": "2026-09-20",
        "merchant": "Purchase",
        "amount": "-1",
        "category": "groceries",
        "kind": "expense",
    }
    inspected = service.inspect_currency(ctx, "transaction.create", args)
    assert inspected[0].code == "JPY" and inspected[0].record_id == account["id"]
    with store.connection() as db:
        assert commands.usage_data(db, ctx) == {"proposals": 0, "receipts": 0}
    proposal = prepare(service, ctx, "transaction.create", args)
    assert proposal.currency == inspected
    revision_currency = service.inspect_revision(
        ctx, proposal.proposal_id, proposal.revision, {"amount": "-2"}
    )
    revised = service.revise(
        ctx,
        proposal.proposal_id,
        proposal.revision,
        {"amount": "-2"},
        request_id="inspect-revise",
    )
    assert (
        revised.currency == revision_currency
        and revised.arguments["date"] == args["date"]
    )
    with pytest.raises(PlatformError, match="command_currency_mismatch"):
        service.inspect_currency(
            ctx,
            "transaction.create",
            args,
            currency_context={"kind": "explicit", "code": "USD"},
        )
    goal = prepare(
        service,
        ctx,
        "goal.create",
        {
            "name": "Currency choice",
            "currency": "JPY",
            "target_amount": "1000",
            "target_date": "2027-12-31",
        },
        request_id="goal-choice",
    )
    explicit = service.inspect_revision(
        ctx,
        goal.proposal_id,
        goal.revision,
        {"currency": "KWD", "target_amount": "1000.125"},
    )
    assert explicit[0].code == "KWD" and explicit[0].kind == "explicit"
    with pytest.raises(PlatformError, match="proposal_not_found"):
        partner = identity_context(
            store, user_id="inspection-other", household_id="inspection-other"
        )
        service.inspect_revision(
            partner, goal.proposal_id, goal.revision, {"target_amount": "2000"}
        )


@pytest.mark.parametrize(
    "kind,amount",
    [("income", "10"), ("expense", "5"), ("document", None), ("checklist", None)],
)
def test_tax_item_command_uses_owned_organizer_currency_and_canonical_item_kinds(
    setup, kind, amount
):
    store, ctx, service = setup
    args = {
        "organizer_id": "tax-demo",
        "kind": kind,
        "title": "Command item",
        "amount": amount,
        "effective_on": "2026-09-20",
    }
    proposal = prepare(service, ctx, "tax.item.create", args)
    assert (
        proposal.currency[0].code
        == service.resolve_record(ctx, "organizer", "tax-demo")["currency"]
        and proposal.currency[0].record_id == "tax-demo"
    )
    receipt = service.confirm(ctx, proposal.proposal_id, proposal.revision)
    with store.connection() as db:
        value = json.loads(
            db.execute(
                "SELECT document FROM p_tax_items WHERE id=?", (receipt.record_id,)
            ).fetchone()[0]
        )
    assert value["kind"] == kind and value["amount"] == amount
    other = identity_context(
        store, user_id="tax-item-other", household_id="tax-item-other"
    )
    with pytest.raises(PlatformError, match="record_not_found"):
        service.inspect_currency(other, "tax.item.create", args)


def test_paper_plan_terms_owned_book_currency_and_no_execution_at_confirmation(setup):
    store, ctx, service = setup
    args = {
        "book_id": "book-demo-usd",
        "cadence": "monthly",
        "next_run_on": "2026-10-31",
        "bundle_id": "bundle-steady-three",
        "amount": "100",
    }
    proposal = prepare(service, ctx, "investing.recurring.create", args)
    assert proposal.execution.scope == "scheduled_paper"
    assert (
        proposal.execution.scheduled_after_confirmation
        and not proposal.execution.real_money
    )
    visible = {field.key: field.value for field in proposal.fields}
    assert (
        visible["execution.scope"] == "scheduled_paper"
        and visible["reference.name"] == "USD learning book"
    )
    assert proposal.currency[0].record_id == "book-demo-usd"
    choices = service.record_choices(ctx, kind="simulation_book")["items"]
    assert choices[0]["id"] == "book-demo-usd"
    before = investing.list_books(store, ctx)
    receipt = service.confirm(ctx, proposal.proposal_id, proposal.revision)
    assert receipt.execution == proposal.execution
    assert all(
        not field.editable
        for field in proposal.fields
        if field.key.startswith(("reference.", "execution."))
    )
    assert any(
        field.key == "execution.scope" and field.value == "scheduled_paper"
        for field in receipt.fields
    )
    assert investing.list_books(store, ctx) == before
    with store.connection() as db:
        assert (
            db.execute("SELECT COUNT(*) FROM p_investment_recurring_runs").fetchone()[0]
            == 0
        )
        assert (
            db.execute("SELECT COUNT(*) FROM p_investment_order_receipts").fetchone()[0]
            == 0
        )
    other = identity_context(store, user_id="paper-other", household_id="paper-other")
    with pytest.raises(PlatformError, match="simulation_book_not_found"):
        service.inspect_currency(other, "investing.recurring.create", args)
    with pytest.raises(PlatformError, match="command_currency_mismatch"):
        service.inspect_currency(
            ctx,
            "investing.recurring.create",
            args,
            currency_context={"kind": "explicit", "code": "JPY"},
        )
    with pytest.raises(PlatformError, match="invalid_money_precision"):
        service.inspect_currency(
            ctx, "investing.recurring.create", {**args, "amount": "100.001"}
        )


def test_bill_payment_confirmation_records_one_occurrence_and_one_real_ledger_artifact(
    setup,
):
    store, ctx, service = setup
    account = ledger.create_account(
        AccountCreate(
            name="Bill funds",
            kind="cash",
            currency="USD",
            opening_balance="100",
            idempotency_key="bill-funds",
        ),
        store,
        ctx,
    )
    bill = planning.save_bill(
        store,
        ctx,
        planning.BillInput(
            name="Internet",
            account_id=account["id"],
            currency="USD",
            category="utilities",
            amount="25",
            anchor_date="2026-09-30",
        ),
    )
    args = {"record_id": bill["id"], "values": {"due_date": "2026-09-30"}}
    proposal = prepare(service, ctx, "bill.payment.record", args)
    visible = {field.key: field.value for field in proposal.fields}
    assert (
        visible["reference.amount"] == "25"
        and visible["reference.account_id"] == account["id"]
    )
    assert (
        proposal.execution.scope == "recorded_bill_payment"
        and not proposal.execution.real_money
    )
    receipt = service.confirm(ctx, proposal.proposal_id, proposal.revision)
    assert receipt.target.page == "transactions"
    assert ledger.get_account(account["id"], store, ctx)["balance"] == "75.00"
    second = prepare(
        service, ctx, "bill.payment.record", args, request_id="duplicate-payment"
    )
    repeat = service.confirm(ctx, second.proposal_id, second.revision)
    assert repeat.record_id == receipt.record_id
    assert ledger.get_account(account["id"], store, ctx)["balance"] == "75.00"
    with store.connection() as db:
        assert (
            db.execute(
                "SELECT COUNT(*) FROM p_bill_occurrences WHERE bill_id=?", (bill["id"],)
            ).fetchone()[0]
            == 1
        )
    refreshed = next(
        item
        for item in planning.list_bills(store, ctx)["items"]
        if item["id"] == bill["id"]
    )
    assert refreshed["next_due"] == "2026-10-30"
