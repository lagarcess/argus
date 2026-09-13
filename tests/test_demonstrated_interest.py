"""One owner answers what a person has shown interest in, from records they own."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from argus.api import state as api_state
from argus.api.demonstrated_interest import demonstrated_interest
from argus.api.main import app
from argus.api.routers import market as market_router
from argus.api.schemas import BacktestRun
from argus.domain.market_data.market_session import (
    EASTERN,
    MarketSessionSnapshot,
    reset_market_session_cache,
)
from argus.domain.store import utcnow
from argus.domain.supabase_gateway import SupabaseGateway
from faker import Faker
from fastapi.testclient import TestClient

fake = Faker()
SESSION_URL = "/api/v1/market/session"


@pytest.fixture(autouse=True)
def _memory_persistence(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    reset_market_session_cache()
    TestClient(app).post("/api/v1/dev/reset")
    yield
    reset_market_session_cache()


def _seed_run(user_id: str, *, status: str) -> None:
    run = BacktestRun(
        id=fake.uuid4(),
        conversation_id=fake.uuid4(),
        status=status,
        asset_class="equity",
        symbols=["AAPL"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={},
        config_snapshot={"template": "buy_and_hold", "symbols": ["AAPL"]},
        conversation_result_card={},
        created_at=utcnow(),
    )
    api_state.store.backtest_runs[run.id] = run
    api_state.store.backtest_run_owners[run.id] = user_id


def test_no_history_shows_no_interest() -> None:
    assert demonstrated_interest(fake.uuid4()).markets is False


def test_a_completed_run_shows_market_interest_to_its_owner_only() -> None:
    owner, stranger = fake.uuid4(), fake.uuid4()
    _seed_run(owner, status="completed")

    assert demonstrated_interest(owner).markets is True
    assert demonstrated_interest(stranger).markets is False


@pytest.mark.parametrize("status", ["queued", "running", "failed"])
def test_a_run_that_never_completed_shows_no_interest(status: str) -> None:
    owner = fake.uuid4()
    _seed_run(owner, status=status)

    assert demonstrated_interest(owner).markets is False


@pytest.mark.parametrize(("completed", "markets"), [(0, False), (3, True)])
def test_durable_history_is_read_for_the_caller_alone(
    monkeypatch: pytest.MonkeyPatch, completed: int, markets: bool
) -> None:
    gateway = MagicMock(spec=SupabaseGateway)
    gateway.count_completed_runs.return_value = completed
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    owner = fake.uuid4()

    assert demonstrated_interest(owner).markets is markets
    gateway.count_completed_runs.assert_called_once_with(user_id=owner)


def test_the_durable_count_filters_on_the_owner_and_completion() -> None:
    calls: list[tuple] = []

    class Query:
        def select(self, *columns, **options):
            calls.append(("select", columns, options))
            return self

        def eq(self, column, value):
            calls.append(("eq", column, value))
            return self

        def execute(self):
            return SimpleNamespace(count=1, data=[])

    def table(name):
        calls.append(("table", name))
        return Query()

    gateway = SupabaseGateway.__new__(SupabaseGateway)
    gateway.client = SimpleNamespace(table=table)
    owner = fake.uuid4()

    assert gateway.count_completed_runs(user_id=owner) == 1
    assert ("table", "backtest_runs") in calls
    assert ("eq", "user_id", owner) in calls
    assert ("eq", "status", "completed") in calls


def test_the_session_response_carries_the_callers_interest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(market_router, "resolve_market_session", lambda: None)
    client = TestClient(app)
    caller = api_state.store.get_or_create_dev_user()

    _seed_run(fake.uuid4(), status="completed")
    assert client.get(SESSION_URL).json()["interest"] == {"markets": False}

    _seed_run(caller.id, status="completed")
    assert client.get(SESSION_URL).json()["interest"] == {"markets": True}


def test_unreadable_history_is_a_null_interest_and_the_session_still_arrives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The greeting falls back to the neutral pool. A 500 would blank the session
    # line for a market fan and make the empty chat look broken.
    at = datetime(2026, 9, 12, 11, 0, tzinfo=EASTERN)
    monkeypatch.setattr(
        market_router,
        "resolve_market_session",
        lambda: MarketSessionSnapshot(
            phase="closed_weekend", is_market_day=False, as_of=at
        ),
    )

    def unreadable(user_id: str):
        raise RuntimeError("history store down")

    monkeypatch.setattr(market_router, "demonstrated_interest", unreadable)

    response = TestClient(app).get(SESSION_URL)

    assert response.status_code == 200
    assert response.json()["interest"] is None
    assert response.json()["session"]["phase"] == "closed_weekend"
