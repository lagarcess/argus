"""`GET /market/session` hands the frontend backend-owned session truth."""

from __future__ import annotations

from datetime import datetime

import pytest
from argus.api.main import app
from argus.api.routers import market as market_router
from argus.domain.market_data.market_session import (
    EASTERN,
    MarketSessionSnapshot,
    reset_market_session_cache,
)
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _isolated_session_cache(monkeypatch: pytest.MonkeyPatch):
    from argus.api import state as api_state

    monkeypatch.setattr(api_state, "supabase_gateway", None)
    reset_market_session_cache()
    yield
    reset_market_session_cache()


def _client() -> TestClient:
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    return client


def test_the_endpoint_returns_the_resolved_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    at = datetime(2026, 8, 8, 11, 0, tzinfo=EASTERN)
    monkeypatch.setattr(
        market_router,
        "resolve_market_session",
        lambda: MarketSessionSnapshot(
            phase="closed_weekend", is_market_day=False, as_of=at
        ),
    )

    response = _client().get("/api/v1/market/session")

    assert response.status_code == 200
    assert response.json()["session"]["phase"] == "closed_weekend"
    assert response.json()["session"]["is_market_day"] is False


def test_an_unreachable_calendar_is_a_null_session_not_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A greeting that says nothing about the market is correct. A 500 would make
    # the empty chat look broken over a cosmetic line.
    monkeypatch.setattr(market_router, "resolve_market_session", lambda: None)

    response = _client().get("/api/v1/market/session")

    assert response.status_code == 200
    assert response.json() == {"session": None}


def test_a_raising_resolver_is_a_null_session_not_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode():
        raise RuntimeError("provider down")

    monkeypatch.setattr(market_router, "resolve_market_session", explode)

    response = _client().get("/api/v1/market/session")

    assert response.status_code == 200
    assert response.json() == {"session": None}


def test_the_endpoint_is_owner_authenticated() -> None:
    route = next(
        candidate
        for candidate in app.routes
        if getattr(candidate, "path", None) == "/api/v1/market/session"
    )
    assert [dependency.call.__name__ for dependency in route.dependant.dependencies] == [
        "current_user"
    ]


def test_the_response_carries_an_eastern_offset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The frontend never recomputes the session, so the timestamp it renders or
    # logs has to be the one the backend resolved.
    at = datetime(2026, 8, 10, 14, 0, tzinfo=EASTERN)
    assert at.utcoffset() is not None
    monkeypatch.setattr(
        market_router,
        "resolve_market_session",
        lambda: MarketSessionSnapshot(phase="open", is_market_day=True, as_of=at),
    )

    payload = _client().get("/api/v1/market/session").json()

    assert payload["session"]["as_of"].endswith("-04:00")


def test_the_session_date_asked_for_is_the_eastern_one() -> None:
    # Guards the wiring rather than the resolver: a router that passed its own
    # `now` would reintroduce the local-clock bug one layer up.
    import inspect

    source = inspect.getsource(market_router.get_market_session)
    assert "resolve_market_session()" in source
    assert "date.today" not in source
    assert "datetime.now" not in source
