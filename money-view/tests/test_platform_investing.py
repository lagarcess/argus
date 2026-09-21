from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from faker import Faker
from fastapi.testclient import TestClient
from server.app import create_app
from server.interpreter import FixtureInterpreter
from server.platform import identity, investing, ledger
from server.platform.common import Context, PlatformError
from server.platform.identity import DEMO_PASSWORD
from server.platform.market_data import (
    FixtureMarketDataAdapter,
    latest_prices,
    load_market_prices,
)
from server.store import Store

fake = Faker()


@pytest.fixture
def context() -> Context:
    return Context(
        user_id="user-demo",
        household_id="household-demo",
        role="owner",
        session_id=fake.uuid4(),
    )


@pytest.fixture
def other_context() -> Context:
    return Context(
        user_id="user-other",
        household_id="household-other",
        role="owner",
        session_id=fake.uuid4(),
    )


@pytest.fixture
def store(tmp_path) -> Store:
    value = Store(tmp_path / "clara.sqlite3")
    investing.initialize(value)
    return value


def test_portfolio_keeps_currencies_separate_and_marks_unpriced_partial(
    store: Store, context: Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(investing, "_linked_investment_accounts", lambda *_: [])
    unpriced = investing.create_holding(
        store,
        context,
        investing.HoldingCreate(
            symbol="ALT-CARD",
            name="Card collection",
            quantity=Decimal("1"),
            total_cost=Decimal("1200.00"),
            currency="USD",
            as_of=date(2026, 9, 20),
        ),
    )
    eur = investing.create_holding(
        store,
        context,
        investing.HoldingCreate(
            symbol="VWCE",
            name="Separate euro certificate",
            quantity=Decimal("2"),
            total_cost=Decimal("240.00"),
            currency="EUR",
            as_of=date(2026, 9, 20),
        ),
    )

    portfolio = investing.portfolio_summary(store, context)
    totals = {item["currency"]: item for item in portfolio["totals"]}

    assert totals["USD"]["priced_alternatives"] == "3900.00"
    assert totals["USD"]["is_partial"] is True
    assert totals["USD"]["unpriced_holding_ids"] == [unpriced["id"]]
    assert totals["EUR"]["priced_alternatives"] == "270.00"
    assert totals["EUR"]["alternative_cost_basis"] == "240.00"
    assert totals["EUR"]["alternative_gain_loss"] == "30.00"
    assert totals["EUR"]["alternative_gain_loss_pct"] == "12.5000"
    additions = {item["currency"]: item for item in portfolio["net_worth_additions"]}
    assert additions["USD"]["amount"] == "3900.00"
    assert additions["EUR"]["amount"] == "270.00"
    assert eur["currency"] == "EUR"


def test_households_cannot_read_or_trade_each_others_records(
    store: Store, context: Context, other_context: Context
) -> None:
    demo_ids = {item["id"] for item in investing.list_holdings(store, context)["items"]}
    other_ids = {
        item["id"] for item in investing.list_holdings(store, other_context)["items"]
    }
    assert demo_ids.isdisjoint(other_ids)
    with pytest.raises(PlatformError, match="holding_not_found"):
        investing.get_holding(store, other_context, next(iter(demo_ids)))
    with pytest.raises(PlatformError, match="simulation_book_not_found"):
        investing.preview_order(
            store,
            other_context,
            investing.OrderPreviewRequest(
                book_id="book-demo-usd",
                side="buy",
                symbol="AAPL",
                quantity=Decimal("1"),
            ),
        )


def test_order_confirmation_is_atomic_and_idempotent_under_double_click(
    store: Store, context: Context
) -> None:
    preview = investing.preview_order(
        store,
        context,
        investing.OrderPreviewRequest(
            book_id="book-demo-usd",
            side="buy",
            symbol="AAPL",
            quantity=Decimal("2"),
        ),
    )

    def confirm() -> dict[str, object]:
        return investing.confirm_order(store, context, str(preview["id"]), "double-click")

    with ThreadPoolExecutor(max_workers=2) as executor:
        receipts = list(executor.map(lambda _: confirm(), range(2)))

    assert receipts[0]["id"] == receipts[1]["id"]
    assert receipts[0]["cash_before"] == "10000.00"
    assert receipts[0]["cash_after"] == "9540.00"
    assert len(investing.list_orders(store, context)["items"]) == 1
    assert investing.list_positions(store, context)[0]["quantity"] == "2"


def test_fractional_round_trip_cannot_manufacture_simulated_cash(
    store: Store, context: Context
) -> None:
    before = next(
        book
        for book in investing.list_books(store, context)["items"]
        if book["id"] == "book-demo-usd"
    )
    buy_preview = investing.preview_order(
        store,
        context,
        investing.OrderPreviewRequest(
            book_id="book-demo-usd",
            side="buy",
            symbol="AAPL",
            quantity=Decimal("0.00012"),
        ),
    )
    buy = investing.confirm_order(
        store, context, str(buy_preview["id"]), "fractional-buy"
    )
    sells = []
    for index in range(2):
        preview = investing.preview_order(
            store,
            context,
            investing.OrderPreviewRequest(
                book_id="book-demo-usd",
                side="sell",
                symbol="AAPL",
                quantity=Decimal("0.00006"),
            ),
        )
        sells.append(
            investing.confirm_order(
                store, context, str(preview["id"]), f"fractional-sell-{index}"
            )
        )

    after = next(
        book
        for book in investing.list_books(store, context)["items"]
        if book["id"] == "book-demo-usd"
    )

    assert buy["gross"] == "0.03"
    assert buy["rounding_rule"] == "buy_ceiling_sell_floor"
    assert buy["rounding_cost"] == "0.0024"
    assert [receipt["gross"] for receipt in sells] == ["0.01", "0.01"]
    assert [receipt["rounding_cost"] for receipt in sells] == [
        "0.0038",
        "0.0038",
    ]
    assert Decimal(str(after["cash"])) <= Decimal(str(before["cash"]))
    assert after["cash"] == "9999.99"
    assert all(
        position["symbol"] != "AAPL"
        for position in investing.list_positions(store, context)
    )


@pytest.mark.parametrize("side", ["buy", "sell"])
def test_sub_minor_unit_symbol_order_is_rejected(
    store: Store, context: Context, side: str
) -> None:
    with pytest.raises(PlatformError, match="order_amount_too_small"):
        investing.preview_order(
            store,
            context,
            investing.OrderPreviewRequest(
                book_id="book-demo-usd",
                side=side,
                symbol="AAPL",
                quantity=Decimal("0.00001"),
            ),
        )


def test_bundle_uses_the_shared_settlement_rounding_rule(
    store: Store, context: Context
) -> None:
    preview = investing.preview_order(
        store,
        context,
        investing.OrderPreviewRequest(
            book_id="book-demo-usd",
            side="buy",
            bundle_id="bundle-steady-three",
            amount=Decimal("300.00"),
        ),
    )
    receipt = investing.confirm_order(
        store, context, str(preview["id"]), "rounded-bundle"
    )

    assert preview["rounding_rule"] == "buy_ceiling_sell_floor"
    assert Decimal(str(preview["rounding_cost"])) >= 0
    assert receipt["rounding_rule"] == preview["rounding_rule"]
    assert receipt["rounding_cost"] == preview["rounding_cost"]


def test_orders_reject_insufficient_cash_and_quantity(
    store: Store, context: Context
) -> None:
    expensive = investing.preview_order(
        store,
        context,
        investing.OrderPreviewRequest(
            book_id="book-demo-usd",
            side="buy",
            symbol="AAPL",
            quantity=Decimal("100"),
        ),
    )
    with pytest.raises(PlatformError, match="insufficient_simulated_cash"):
        investing.confirm_order(store, context, str(expensive["id"]), "too-large")

    sell = investing.preview_order(
        store,
        context,
        investing.OrderPreviewRequest(
            book_id="book-demo-usd",
            side="sell",
            symbol="AAPL",
            quantity=Decimal("1"),
        ),
    )
    with pytest.raises(PlatformError, match="insufficient_simulated_quantity"):
        investing.confirm_order(store, context, str(sell["id"]), "oversell")


def test_new_price_snapshot_makes_unconfirmed_order_stale(
    store: Store, context: Context
) -> None:
    preview = investing.preview_order(
        store,
        context,
        investing.OrderPreviewRequest(
            book_id="book-demo-usd",
            side="buy",
            symbol="AAPL",
            quantity=Decimal("1"),
        ),
    )
    result = load_market_prices(
        store,
        FixtureMarketDataAdapter(
            as_of=date(2026, 9, 21),
            overrides={("AAPL", "USD"): Decimal("231.00")},
        ),
    )
    assert result["status"] == "succeeded"

    with pytest.raises(PlatformError, match="stale_quote"):
        investing.confirm_order(store, context, str(preview["id"]), "stale")


def test_failed_price_load_retains_last_good_prices(store: Store) -> None:
    before = latest_prices(store)
    failed = load_market_prices(store, FixtureMarketDataAdapter(outcome="failure"))
    after = latest_prices(store)

    assert failed["status"] == "failed"
    assert failed["error_code"] == "fixture_market_load_failed"
    assert after[("AAPL", "USD")]["set_id"] == before[("AAPL", "USD")]["set_id"]
    assert after[("AAPL", "USD")]["price_minor"] == before[("AAPL", "USD")]["price_minor"]


def test_recurring_plan_runs_once_per_period(store: Store, context: Context) -> None:
    plan = investing.create_recurring_plan(
        store,
        context,
        investing.RecurringPlanCreate(
            book_id="book-demo-usd",
            cadence="monthly",
            next_run_on=date(2026, 9, 20),
            symbol="BND",
            amount=Decimal("100.00"),
        ),
    )

    first = investing.run_recurring_plan(
        store, context, str(plan["id"]), date(2026, 9, 20)
    )
    replay = investing.run_recurring_plan(
        store, context, str(plan["id"]), date(2026, 9, 20)
    )

    assert first["status"] == "succeeded"
    assert replay["id"] == first["id"]
    assert replay["order_receipt"]["id"] == first["order_receipt"]["id"]
    assert first["order_receipt"]["rounding_rule"] == "buy_ceiling_sell_floor"
    assert Decimal(first["order_receipt"]["rounding_cost"]) >= 0
    assert len(investing.list_orders(store, context)["items"]) == 1


@pytest.mark.parametrize("authority_change", ["removed", "demoted", "deleted"])
def test_scheduled_recurring_plan_requires_current_creator_authority(
    store: Store, context: Context, authority_change: str
) -> None:
    identity.initialize(store)
    plan = investing.create_recurring_plan(
        store,
        context,
        investing.RecurringPlanCreate(
            book_id="book-demo-usd",
            cadence="monthly",
            next_run_on=date(2026, 9, 20),
            symbol="BND",
            amount=Decimal("100.00"),
        ),
    )
    with store.connection(write=True) as connection:
        if authority_change == "removed":
            connection.execute(
                "DELETE FROM p_memberships WHERE household_id=? AND user_id=?",
                (context.household_id, context.user_id),
            )
        elif authority_change == "demoted":
            connection.execute(
                """
                UPDATE p_memberships SET role='viewer'
                WHERE household_id=? AND user_id=?
                """,
                (context.household_id, context.user_id),
            )
        else:
            connection.execute(
                "UPDATE p_users SET deleted_at=? WHERE id=?",
                (datetime.now(timezone.utc).isoformat(), context.user_id),
            )

    result = investing.run_due_recurring_plans(store, date(2026, 9, 20))

    assert len(result["items"]) == 1
    assert result["items"][0]["status"] == "failed"
    assert result["items"][0]["error_code"] == "recurring_creator_unauthorized"
    assert investing.get_recurring_plan(store, context, str(plan["id"]))["active"] is False
    assert investing.list_orders(store, context) == {"items": []}


def test_household_editor_can_manually_run_another_members_plan(
    store: Store, context: Context
) -> None:
    identity.initialize(store)
    plan = investing.create_recurring_plan(
        store,
        context,
        investing.RecurringPlanCreate(
            book_id="book-demo-usd",
            cadence="monthly",
            next_run_on=date(2026, 9, 20),
            symbol="BND",
            amount=Decimal("100.00"),
        ),
    )
    with store.connection(write=True) as connection:
        connection.execute(
            """
            UPDATE p_memberships SET role='viewer'
            WHERE household_id=? AND user_id=?
            """,
            (context.household_id, context.user_id),
        )
    editor = Context(
        user_id="user-partner",
        household_id=context.household_id,
        role="editor",
        session_id=fake.uuid4(),
    )

    result = investing.run_recurring_plan(
        store, editor, str(plan["id"]), date(2026, 9, 20)
    )

    assert result["status"] == "succeeded"
    assert result["order_receipt"] is not None


def test_due_recurring_plans_are_bounded_cursor_paged_and_deduplicated(
    store: Store, context: Context
) -> None:
    identity.initialize(store)
    for cadence, due_on in (
        ("weekly", date(2026, 9, 18)),
        ("monthly", date(2026, 9, 19)),
        ("weekly", date(2026, 9, 20)),
    ):
        investing.create_recurring_plan(
            store,
            context,
            investing.RecurringPlanCreate(
                book_id="book-demo-usd",
                cadence=cadence,
                next_run_on=due_on,
                symbol="BND",
                amount=Decimal("100.00"),
            ),
        )

    first = investing.run_due_recurring_plans(
        store, date(2026, 9, 20), limit=2
    )
    second = investing.run_due_recurring_plans(
        store,
        date(2026, 9, 20),
        cursor=str(first["next_cursor"]),
        limit=2,
    )
    replay = investing.run_due_recurring_plans(store, date(2026, 9, 20), limit=2)

    assert len(first["items"]) == 2
    assert first["next_cursor"] is not None
    assert first["next_poll_on"] == "2026-09-20"
    assert len(second["items"]) == 1
    assert second["next_cursor"] is None
    assert second["next_poll_on"] == "2026-09-27"
    assert replay["items"] == []
    assert len(investing.list_orders(store, context)["items"]) == 3
    with store.connection() as connection:
        indexes = {
            row["name"]
            for row in connection.execute(
                "PRAGMA index_list('p_investment_recurring_plans')"
            )
        }
    assert "p_investment_recurring_due" in indexes


def test_due_recurring_plan_rejects_invalid_page_inputs(store: Store) -> None:
    with pytest.raises(PlatformError, match="invalid_recurring_cursor"):
        investing.run_due_recurring_plans(
            store, date(2026, 9, 20), cursor="not-a-cursor"
        )
    with pytest.raises(PlatformError, match="invalid_recurring_limit"):
        investing.run_due_recurring_plans(store, date(2026, 9, 20), limit=101)


def _insert_interrupted_recurring_run(
    store: Store,
    plan_id: str,
    *,
    created_at: datetime,
    period_key: str = "2026-09",
    run_on: date = date(2026, 9, 20),
) -> str:
    run_id = f"recurring-run-{fake.uuid4()}"
    with store.connection(write=True) as connection:
        connection.execute(
            """
            INSERT INTO p_investment_recurring_runs(
                id,plan_id,household_id,period_key,run_on,status,source_json,created_at
            )
            SELECT ?,id,household_id,?,?,'running',source_json,?
            FROM p_investment_recurring_plans WHERE id=?
            """,
            (
                run_id,
                period_key,
                run_on.isoformat(),
                created_at.isoformat(),
                plan_id,
            ),
        )
    return run_id


def test_interrupted_recurring_run_without_receipt_fails_and_advances(
    store: Store, context: Context
) -> None:
    plan = investing.create_recurring_plan(
        store,
        context,
        investing.RecurringPlanCreate(
            book_id="book-demo-usd",
            cadence="monthly",
            next_run_on=date(2026, 8, 20),
            symbol="BND",
            amount=Decimal("100.00"),
        ),
    )
    run_id = _insert_interrupted_recurring_run(
        store,
        str(plan["id"]),
        created_at=datetime.now(timezone.utc)
        - investing.RECURRING_RUN_LEASE
        - timedelta(seconds=1),
        period_key="2026-08",
        run_on=date(2026, 8, 20),
    )

    recovered = investing.run_recurring_plan(
        store, context, str(plan["id"]), date(2026, 9, 20)
    )
    replay = investing.run_recurring_plan(
        store, context, str(plan["id"]), date(2026, 8, 20)
    )

    assert recovered["id"] == run_id
    assert recovered["status"] == "failed"
    assert recovered["error_code"] == "recurring_run_interrupted"
    assert replay == recovered
    assert investing.get_recurring_plan(store, context, str(plan["id"]))[
        "next_run_on"
    ] == "2026-09-20"
    assert investing.list_orders(store, context) == {"items": []}


def test_interrupted_recurring_run_reconciles_confirmed_receipt(
    store: Store, context: Context
) -> None:
    plan = investing.create_recurring_plan(
        store,
        context,
        investing.RecurringPlanCreate(
            book_id="book-demo-usd",
            cadence="monthly",
            next_run_on=date(2026, 8, 20),
            symbol="BND",
            amount=Decimal("100.00"),
        ),
    )
    run_id = _insert_interrupted_recurring_run(
        store,
        str(plan["id"]),
        created_at=datetime.now(timezone.utc),
        period_key="2026-08",
        run_on=date(2026, 8, 20),
    )
    preview = investing.preview_order(
        store,
        context,
        investing.OrderPreviewRequest(
            book_id="book-demo-usd",
            side="buy",
            symbol="BND",
            quantity=Decimal("1"),
        ),
    )
    receipt = investing.confirm_order(
        store,
        context,
        str(preview["id"]),
        f"recurring:{plan['id']}:2026-08",
    )

    recovered = investing.run_recurring_plan(
        store, context, str(plan["id"]), date(2026, 9, 20)
    )

    assert recovered["id"] == run_id
    assert recovered["status"] == "succeeded"
    assert recovered["error_code"] is None
    assert recovered["order_receipt"]["id"] == receipt["id"]
    assert investing.get_recurring_plan(store, context, str(plan["id"]))[
        "next_run_on"
    ] == "2026-09-20"
    assert len(investing.list_orders(store, context)["items"]) == 1


def test_recovered_recurring_run_cannot_settle_after_interruption(
    store: Store, context: Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = investing.create_recurring_plan(
        store,
        context,
        investing.RecurringPlanCreate(
            book_id="book-demo-usd",
            cadence="monthly",
            next_run_on=date(2026, 9, 20),
            symbol="BND",
            amount=Decimal("100.00"),
        ),
    )
    before = next(
        book
        for book in investing.list_books(store, context)["items"]
        if book["id"] == "book-demo-usd"
    )
    original_confirm = investing.confirm_order
    recovered: dict[str, object] = {}

    def recover_then_confirm(
        target_store: Store,
        target_context: Context,
        preview_id: str,
        idempotency_key: str,
        *,
        recurring_run_id: str | None = None,
    ) -> dict[str, object]:
        assert recurring_run_id is not None
        with target_store.connection(write=True) as connection:
            connection.execute(
                "UPDATE p_investment_recurring_runs SET created_at=? WHERE id=?",
                (
                    (
                        datetime.now(timezone.utc)
                        - investing.RECURRING_RUN_LEASE
                        - timedelta(seconds=1)
                    ).isoformat(),
                    recurring_run_id,
                ),
            )
        recovered["run"] = investing.run_recurring_plan(
            target_store,
            target_context,
            str(plan["id"]),
            date(2026, 9, 20),
        )
        return original_confirm(
            target_store,
            target_context,
            preview_id,
            idempotency_key,
            recurring_run_id=recurring_run_id,
        )

    monkeypatch.setattr(investing, "confirm_order", recover_then_confirm)

    result = investing.run_recurring_plan(
        store, context, str(plan["id"]), date(2026, 9, 20)
    )
    after = next(
        book
        for book in investing.list_books(store, context)["items"]
        if book["id"] == "book-demo-usd"
    )
    recovered_run = recovered["run"]
    assert isinstance(recovered_run, dict)
    assert recovered_run["status"] == "failed"
    assert result["id"] == recovered_run["id"]
    assert result["status"] == "failed"
    assert result["error_code"] == "recurring_run_interrupted"
    assert investing.list_orders(store, context) == {"items": []}
    assert after["cash"] == before["cash"]
    assert all(
        position["symbol"] != "BND"
        for position in investing.list_positions(store, context)
    )


def test_csv_preview_is_inert_and_commit_is_idempotent(
    store: Store, context: Context
) -> None:
    content = (
        "symbol,name,quantity,total_cost,currency,as_of\n"
        "ALT-CARD,Card collection,1,1200.00,USD,2026-09-20\n"
    )
    preview = investing.preview_holding_csv(store, context, content)
    assert preview["can_commit"] is True
    assert len(investing.list_holdings(store, context)["items"]) == 1

    key = fake.uuid4()
    receipt = investing.commit_holding_import(store, context, str(preview["id"]), key)
    replay = investing.commit_holding_import(store, context, str(preview["id"]), key)
    assert receipt == replay
    assert receipt["imported"] == 1
    assert len(investing.list_holdings(store, context)["items"]) == 2


def test_manual_holding_changes_net_worth_once_and_paper_order_never_does(
    tmp_path, context: Context
) -> None:
    store = Store(tmp_path / "integrated.sqlite3")
    ledger.initialize(store)
    investing.initialize(store)
    before = ledger.overview_summary(store, context)
    before_usd = next(item for item in before["net_worth"] if item["currency"] == "USD")
    additions = investing.portfolio_summary(store, context)["net_worth_additions"]
    assert additions == [
        {
            "currency": "USD",
            "amount": "3900.00",
            "source": additions[0]["source"],
        }
    ]
    assert "3900.00" in str(before_usd["source"]["inputs"])

    preview = investing.preview_order(
        store,
        context,
        investing.OrderPreviewRequest(
            book_id="book-demo-usd",
            side="buy",
            symbol="AAPL",
            quantity=Decimal("1"),
        ),
    )
    investing.confirm_order(store, context, str(preview["id"]), "net-worth-proof")
    after = ledger.overview_summary(store, context)
    after_usd = next(item for item in after["net_worth"] if item["currency"] == "USD")
    assert after_usd["net_worth"] == before_usd["net_worth"]


def test_cleared_household_is_not_reseeded(store: Store, context: Context) -> None:
    with store.connection(write=True) as connection:
        investing.clear_data(connection, context)
    investing.initialize(store)

    assert investing.list_holdings(store, context) == {"items": []}
    assert investing.list_books(store, context) == {"items": []}


def test_http_portfolio_preview_and_confirm_use_composed_app(tmp_path) -> None:
    with TestClient(
        create_app(tmp_path / "http.sqlite3", FixtureInterpreter())
    ) as client:
        login = client.post(
            "/api/platform/session/login",
            json={"user_id": "user-demo", "password": DEMO_PASSWORD},
        )
        assert login.status_code == 200
        portfolio = client.get("/api/platform/investing/portfolio")
        assert portfolio.status_code == 200
        assert portfolio.json()["net_worth_additions"][0]["amount"] == "3900.00"

        preview = client.post(
            "/api/platform/investing/orders/preview",
            json={
                "book_id": "book-demo-usd",
                "side": "buy",
                "symbol": "AAPL",
                "quantity": "1",
            },
        )
        assert preview.status_code == 200
        receipt = client.post(
            f"/api/platform/investing/orders/{preview.json()['id']}/confirm",
            json={"idempotency_key": "http-order"},
        )
        assert receipt.status_code == 200
        assert receipt.json()["cash_after"] == "9770.00"
