from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest
from argus.domain.backtesting.coverage import (
    MarketDataCoverageError,
    apply_coverage_to_config,
    prepare_market_data,
)
from argus.domain.engine import build_result_chart, compute_alpha_metrics
from argus.domain.market_data.capabilities import EASTERN, EquityMarketSession

_UTC_EASTERN_DATE_BOUNDARY_NOW = datetime.fromisoformat("2026-08-13T01:00:00+00:00")


def _bars(*days: str, base: float = 100.0) -> pd.DataFrame:
    index = pd.DatetimeIndex(pd.to_datetime(list(days), utc=True))
    close = pd.Series(
        [base + float(offset) for offset in range(len(index))],
        index=index,
    )
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1_000.0,
        },
        index=index,
    )


def _config(*symbols: str) -> dict[str, object]:
    return {
        "template": "buy_and_hold",
        "asset_class": "equity",
        "symbols": list(symbols),
        "timeframe": "1D",
        "start_date": "2024-01-02",
        "end_date": "2024-01-08",
        "side": "long",
        "starting_capital": 10_000.0,
        "allocation_method": "equal_weight",
        "benchmark_symbol": "SPY",
        "parameters": {},
    }


def _fetcher(
    frames: dict[str, pd.DataFrame],
    calls: Counter[str] | None = None,
):
    def fetch(
        symbol: str,
        asset_class: str,  # noqa: ARG001
        start_date: date,  # noqa: ARG001
        end_date: date,  # noqa: ARG001
        timeframe: str,  # noqa: ARG001
    ) -> pd.DataFrame:
        if calls is not None:
            calls[symbol] += 1
        return frames[symbol].copy(deep=True)

    return fetch


def _market_session(
    day: str,
    *,
    opens_at: str = "09:30",
    closes_at: str = "16:00",
) -> EquityMarketSession:
    return EquityMarketSession(
        provider="alpaca",
        session_date=date.fromisoformat(day),
        opens_at=datetime.fromisoformat(f"{day}T{opens_at}:00-05:00"),
        closes_at=datetime.fromisoformat(f"{day}T{closes_at}:00-05:00"),
    )


def _session_calendar(
    *sessions: EquityMarketSession,
    calls: list[tuple[date, date]] | None = None,
):
    def fetch(*, start_date: date, end_date: date) -> tuple[EquityMarketSession, ...]:
        if calls is not None:
            calls.append((start_date, end_date))
        return tuple(
            session
            for session in sessions
            if start_date <= session.session_date <= end_date
        )

    return fetch


def _no_equity_calendar(**_: object) -> tuple[EquityMarketSession, ...]:
    raise AssertionError("continuous markets must not request an equity calendar")


def test_exact_equity_session_boundaries_have_no_adjustment_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    days = ("2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05")
    sessions = tuple(_market_session(day) for day in days)
    calendar_calls: list[tuple[date, date]] = []

    prepared = prepare_market_data(
        {
            **_config("AAPL"),
            "start_date": days[0],
            "end_date": days[-1],
        },
        fetch_ohlcv_func=_fetcher({"AAPL": _bars(*days), "SPY": _bars(*days)}),
        fetch_market_calendar_func=_session_calendar(
            *sessions,
            calls=calendar_calls,
        ),
    )

    assert prepared.outcome == "full_coverage"
    assert prepared.adjustment_reason == "none"
    assert prepared.coverage_payload()["adjustment_reason"] == "none"
    assert calendar_calls == [(date(2024, 1, 2), date(2024, 1, 5))]


@pytest.mark.parametrize(
    ("requested_start", "requested_end", "session_days"),
    [
        (
            "2024-01-01",
            "2024-01-05",
            ("2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"),
        ),
        (
            "2024-01-06",
            "2024-01-10",
            ("2024-01-08", "2024-01-09", "2024-01-10"),
        ),
        (
            "2024-12-20",
            "2024-12-25",
            ("2024-12-20", "2024-12-23", "2024-12-24"),
        ),
    ],
    ids=("holiday-start", "weekend-start", "weekend-holiday-end"),
)
def test_equity_calendar_only_boundaries_are_calendar_alignment(
    monkeypatch: pytest.MonkeyPatch,
    requested_start: str,
    requested_end: str,
    session_days: tuple[str, ...],
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    sessions = tuple(_market_session(day) for day in session_days)
    bars = _bars(*session_days)
    calendar_calls: list[tuple[date, date]] = []

    prepared = prepare_market_data(
        {
            **_config("AAPL"),
            "start_date": requested_start,
            "end_date": requested_end,
        },
        fetch_ohlcv_func=_fetcher({"AAPL": bars, "SPY": bars}),
        fetch_market_calendar_func=_session_calendar(
            *sessions,
            calls=calendar_calls,
        ),
    )

    assert prepared.outcome == "adjusted_coverage"
    assert prepared.adjustment_reason == "calendar_alignment"
    assert prepared.effective_date_range.model_dump() == {
        "start": session_days[0],
        "end": session_days[-1],
    }
    assert calendar_calls == [
        (date.fromisoformat(requested_start), date.fromisoformat(requested_end))
    ]


@pytest.mark.parametrize(
    ("observed_days", "expected_start", "expected_end"),
    [
        (
            ("2024-01-03", "2024-01-04", "2024-01-05"),
            "2024-01-03",
            "2024-01-05",
        ),
        (
            ("2024-01-02", "2024-01-03", "2024-01-04"),
            "2024-01-02",
            "2024-01-04",
        ),
    ],
    ids=("provider-head", "provider-tail"),
)
def test_equity_provider_edge_loss_is_material(
    monkeypatch: pytest.MonkeyPatch,
    observed_days: tuple[str, ...],
    expected_start: str,
    expected_end: str,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    candidate_days = ("2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05")
    sessions = tuple(_market_session(day) for day in candidate_days)
    calendar_calls: list[tuple[date, date]] = []

    prepared = prepare_market_data(
        {
            **_config("AAPL"),
            "start_date": candidate_days[0],
            "end_date": candidate_days[-1],
        },
        fetch_ohlcv_func=_fetcher(
            {"AAPL": _bars(*observed_days), "SPY": _bars(*candidate_days)}
        ),
        fetch_market_calendar_func=_session_calendar(
            *sessions,
            calls=calendar_calls,
        ),
    )

    assert prepared.outcome == "adjusted_coverage"
    assert prepared.adjustment_reason == "provider_coverage_adjustment"
    assert prepared.effective_date_range.model_dump() == {
        "start": expected_start,
        "end": expected_end,
    }
    assert calendar_calls == [(date(2024, 1, 2), date(2024, 1, 5))]


def test_multi_symbol_and_benchmark_common_window_loss_is_material(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    candidate_days = ("2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05")
    sessions = tuple(_market_session(day) for day in candidate_days)

    prepared = prepare_market_data(
        {
            **_config("AAPL", "MSFT"),
            "start_date": candidate_days[0],
            "end_date": candidate_days[-1],
        },
        fetch_ohlcv_func=_fetcher(
            {
                "AAPL": _bars(*candidate_days),
                "MSFT": _bars("2024-01-03", "2024-01-04", "2024-01-05"),
                "SPY": _bars("2024-01-02", "2024-01-03", "2024-01-04"),
            }
        ),
        fetch_market_calendar_func=_session_calendar(*sessions),
    )

    assert prepared.effective_date_range.model_dump() == {
        "start": "2024-01-03",
        "end": "2024-01-04",
    }
    assert prepared.adjustment_reason == "provider_coverage_adjustment"


def test_continuous_market_classifications_never_use_the_equity_calendar() -> None:
    today = _UTC_EASTERN_DATE_BOUNDARY_NOW.astimezone(timezone.utc).date()
    requested_start = today - timedelta(days=4)
    latest_complete = today - timedelta(days=1)
    complete_days = tuple(
        (requested_start + timedelta(days=offset)).isoformat() for offset in range(4)
    )

    exact = prepare_market_data(
        {
            **_config("ETH"),
            "asset_class": "crypto",
            "benchmark_symbol": "BTC",
            "start_date": requested_start.isoformat(),
            "end_date": latest_complete.isoformat(),
        },
        fetch_ohlcv_func=_fetcher(
            {"ETH": _bars(*complete_days), "BTC": _bars(*complete_days)}
        ),
        fetch_market_calendar_func=_no_equity_calendar,
        now=_UTC_EASTERN_DATE_BOUNDARY_NOW,
    )
    latest_complete_alignment = prepare_market_data(
        {
            **_config("ETH"),
            "asset_class": "crypto",
            "benchmark_symbol": "BTC",
            "start_date": requested_start.isoformat(),
            "end_date": latest_complete.isoformat(),
            "requested_date_range": {
                "start": requested_start.isoformat(),
                "end": today.isoformat(),
            },
        },
        fetch_ohlcv_func=_fetcher(
            {"ETH": _bars(*complete_days), "BTC": _bars(*complete_days)}
        ),
        fetch_market_calendar_func=_no_equity_calendar,
        now=_UTC_EASTERN_DATE_BOUNDARY_NOW,
    )
    provider_truncated = prepare_market_data(
        {
            **_config("ETH"),
            "asset_class": "crypto",
            "benchmark_symbol": "BTC",
            "start_date": requested_start.isoformat(),
            "end_date": latest_complete.isoformat(),
        },
        fetch_ohlcv_func=_fetcher(
            {
                "ETH": _bars(*complete_days[1:]),
                "BTC": _bars(*complete_days),
            }
        ),
        fetch_market_calendar_func=_no_equity_calendar,
        now=_UTC_EASTERN_DATE_BOUNDARY_NOW,
    )

    assert exact.adjustment_reason == "none"
    assert latest_complete_alignment.adjustment_reason == "calendar_alignment"
    assert provider_truncated.adjustment_reason == "provider_coverage_adjustment"


def test_relative_equity_period_ending_today_aligns_to_latest_completed_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    today = _UTC_EASTERN_DATE_BOUNDARY_NOW.astimezone(EASTERN).date()
    latest_complete = today - timedelta(days=1)
    while latest_complete.weekday() >= 5:
        latest_complete -= timedelta(days=1)
    candidate_start = latest_complete - timedelta(days=6)
    session_days = tuple(
        (candidate_start + timedelta(days=offset)).isoformat()
        for offset in range((latest_complete - candidate_start).days + 1)
        if (candidate_start + timedelta(days=offset)).weekday() < 5
    )
    sessions = tuple(_market_session(day) for day in session_days)
    bars = _bars(*session_days)

    prepared = prepare_market_data(
        {
            **_config("AAPL"),
            "start_date": candidate_start.isoformat(),
            "end_date": latest_complete.isoformat(),
            "requested_date_range": {
                "start": candidate_start.isoformat(),
                "end": today.isoformat(),
            },
        },
        fetch_ohlcv_func=_fetcher({"AAPL": bars, "SPY": bars}),
        fetch_market_calendar_func=_session_calendar(*sessions),
        now=_UTC_EASTERN_DATE_BOUNDARY_NOW,
    )

    assert prepared.outcome == "adjusted_coverage"
    assert prepared.effective_date_range.model_dump() == {
        "start": session_days[0],
        "end": latest_complete.isoformat(),
    }
    assert prepared.adjustment_reason == "calendar_alignment"


def test_full_coverage_preserves_requested_window_and_fetches_each_series_once() -> None:
    full = _bars(
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
        "2024-01-08",
    )
    calls: Counter[str] = Counter()

    prepared = prepare_market_data(
        _config("AAPL", "MSFT"),
        fetch_ohlcv_func=_fetcher({"AAPL": full, "MSFT": full, "SPY": full}, calls),
    )

    assert prepared.outcome == "full_coverage"
    assert prepared.requested_date_range.model_dump() == {
        "start": "2024-01-02",
        "end": "2024-01-08",
    }
    assert prepared.effective_date_range == prepared.requested_date_range
    assert calls == Counter({"AAPL": 1, "MSFT": 1, "SPY": 1})


@pytest.mark.parametrize(
    ("symbol_days", "expected_start", "expected_end"),
    [
        (
            ["2024-01-04", "2024-01-05", "2024-01-08"],
            "2024-01-04",
            "2024-01-08",
        ),
        (
            ["2024-01-02", "2024-01-03", "2024-01-04"],
            "2024-01-02",
            "2024-01-04",
        ),
    ],
)
def test_leading_and_trailing_gaps_produce_one_effective_window(
    symbol_days: list[str],
    expected_start: str,
    expected_end: str,
) -> None:
    full = _bars(
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
        "2024-01-08",
    )

    prepared = prepare_market_data(
        _config("AAPL"),
        fetch_ohlcv_func=_fetcher({"AAPL": _bars(*symbol_days), "SPY": full}),
    )
    effective_config = apply_coverage_to_config(_config("AAPL"), prepared)

    assert prepared.outcome == "adjusted_coverage"
    assert prepared.effective_date_range.model_dump() == {
        "start": expected_start,
        "end": expected_end,
    }
    assert effective_config["start_date"] == expected_start
    assert effective_config["end_date"] == expected_end
    assert effective_config["requested_date_range"] == {
        "start": "2024-01-02",
        "end": "2024-01-08",
    }
    assert effective_config["effective_date_range"] == {
        "start": expected_start,
        "end": expected_end,
    }


def test_multi_symbol_window_is_intersection_including_benchmark() -> None:
    prepared = prepare_market_data(
        _config("AAPL", "MSFT"),
        fetch_ohlcv_func=_fetcher(
            {
                "AAPL": _bars("2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"),
                "MSFT": _bars("2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"),
                "SPY": _bars("2024-01-02", "2024-01-03", "2024-01-04"),
            }
        ),
    )

    assert prepared.effective_date_range.model_dump() == {
        "start": "2024-01-03",
        "end": "2024-01-04",
    }
    assert all(
        list(frame.index.strftime("%Y-%m-%d")) == ["2024-01-03", "2024-01-04"]
        for frame in prepared.bars_by_symbol.values()
    )


def test_effective_window_uses_observed_boundaries_for_every_series() -> None:
    all_days = [
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
        "2024-01-08",
        "2024-01-09",
        "2024-01-10",
        "2024-01-11",
        "2024-01-12",
        "2024-01-16",
        "2024-01-17",
        "2024-01-18",
        "2024-01-19",
    ]
    strategy_days = [day for day in all_days if day not in {"2024-01-03", "2024-01-18"}]
    benchmark_days = [
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
        "2024-01-08",
        "2024-01-09",
        "2024-01-10",
        "2024-01-11",
        "2024-01-12",
        "2024-01-16",
        "2024-01-17",
        "2024-01-18",
    ]

    prepared = prepare_market_data(
        {
            **_config("AAPL", "MSFT"),
            "end_date": "2024-01-20",
        },
        fetch_ohlcv_func=_fetcher(
            {
                "AAPL": _bars(*strategy_days),
                "MSFT": _bars(*benchmark_days, base=200.0),
                "SPY": _bars(*all_days, base=300.0),
            }
        ),
    )

    assert prepared.effective_date_range.model_dump() == {
        "start": "2024-01-04",
        "end": "2024-01-17",
    }
    assert all(
        frame.index[0].date().isoformat() == "2024-01-04"
        and frame.index[-1].date().isoformat() == "2024-01-17"
        for frame in prepared.bars_by_symbol.values()
    )


def test_sparse_history_is_rejected_with_typed_recovery_code() -> None:
    full = _bars(
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
        "2024-01-08",
    )

    with pytest.raises(MarketDataCoverageError) as exc_info:
        prepare_market_data(
            _config("AAPL", "MSFT"),
            fetch_ohlcv_func=_fetcher(
                {
                    "AAPL": full,
                    "MSFT": _bars("2024-01-02", "2024-01-08"),
                    "SPY": full,
                }
            ),
        )

    assert exc_info.value.code == "insufficient_common_data"


def test_uniformly_sparse_history_is_rejected_against_the_effective_window() -> None:
    endpoints = _bars("2024-01-02", "2024-01-31")

    with pytest.raises(MarketDataCoverageError) as exc_info:
        prepare_market_data(
            {
                **_config("AAPL"),
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
            },
            fetch_ohlcv_func=_fetcher({"AAPL": endpoints, "SPY": endpoints}),
        )

    assert exc_info.value.code == "insufficient_common_data"


def test_complete_equity_history_across_market_holidays_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    market_sessions = _bars(
        "2024-12-24",
        "2024-12-26",
        "2024-12-27",
        "2024-12-30",
        "2024-12-31",
        "2025-01-02",
    )

    prepared = prepare_market_data(
        {
            **_config("AAPL"),
            "start_date": "2024-12-24",
            "end_date": "2025-01-02",
        },
        fetch_ohlcv_func=_fetcher({"AAPL": market_sessions, "SPY": market_sessions}),
        fetch_market_calendar_func=lambda **_: (
            _market_session("2024-12-24", closes_at="13:00"),
            _market_session("2024-12-26"),
            _market_session("2024-12-27"),
            _market_session("2024-12-30"),
            _market_session("2024-12-31"),
            _market_session("2025-01-02"),
        ),
    )

    assert prepared.outcome == "full_coverage"
    assert prepared.observations_by_symbol == {"AAPL": 6, "SPY": 6}


def test_genuinely_sparse_equity_history_across_holidays_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    sparse = _bars("2024-12-24", "2024-12-27", "2025-01-02")
    sessions = (
        _market_session("2024-12-24", closes_at="13:00"),
        _market_session("2024-12-26"),
        _market_session("2024-12-27"),
        _market_session("2024-12-30"),
        _market_session("2024-12-31"),
        _market_session("2025-01-02"),
    )

    with pytest.raises(MarketDataCoverageError) as exc_info:
        prepare_market_data(
            {
                **_config("AAPL"),
                "start_date": "2024-12-24",
                "end_date": "2025-01-02",
            },
            fetch_ohlcv_func=_fetcher({"AAPL": sparse, "SPY": sparse}),
            fetch_market_calendar_func=lambda **_: sessions,
        )

    assert exc_info.value.code == "insufficient_common_data"


def test_early_close_reduces_expected_intraday_equity_observations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    intraday = _bars(
        "2024-11-27T09:30:00-05:00",
        "2024-11-27T10:30:00-05:00",
        "2024-11-27T11:30:00-05:00",
        "2024-11-27T12:30:00-05:00",
        "2024-11-27T13:30:00-05:00",
        "2024-11-27T14:30:00-05:00",
        "2024-11-27T15:30:00-05:00",
        "2024-11-29T09:30:00-05:00",
        "2024-11-29T10:30:00-05:00",
        "2024-11-29T11:30:00-05:00",
        "2024-11-29T12:30:00-05:00",
    )

    prepared = prepare_market_data(
        {
            **_config("AAPL"),
            "timeframe": "1h",
            "start_date": "2024-11-27",
            "end_date": "2024-11-29",
        },
        fetch_ohlcv_func=_fetcher({"AAPL": intraday, "SPY": intraday}),
        fetch_market_calendar_func=lambda **_: (
            _market_session("2024-11-27"),
            _market_session("2024-11-29", closes_at="13:00"),
        ),
    )

    assert prepared.outcome == "full_coverage"
    assert prepared.observations_by_symbol == {"AAPL": 11, "SPY": 11}


@pytest.mark.parametrize("calendar_failure", ["unavailable", "empty", "malformed"])
def test_live_calendar_failure_is_provider_neutral_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    calendar_failure: str,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    full = _bars(
        "2024-12-24",
        "2024-12-26",
        "2024-12-27",
        "2024-12-30",
        "2024-12-31",
        "2025-01-02",
    )
    calls = 0

    def failed_calendar(**_: object) -> tuple[EquityMarketSession, ...]:
        nonlocal calls
        calls += 1
        if calendar_failure == "unavailable":
            raise ValueError("provider-specific calendar failure")
        if calendar_failure == "empty":
            return ()
        return (
            _market_session(
                "2024-12-24",
                opens_at="16:00",
                closes_at="09:30",
            ),
        )

    with pytest.raises(MarketDataCoverageError) as exc_info:
        prepare_market_data(
            {
                **_config("AAPL"),
                "start_date": "2024-12-24",
                "end_date": "2025-01-02",
            },
            fetch_ohlcv_func=_fetcher({"AAPL": full, "SPY": full}),
            fetch_market_calendar_func=failed_calendar,
        )

    assert exc_info.value.code == "market_data_unavailable"
    assert calls == 1


@pytest.mark.parametrize(
    ("asset_class", "symbol", "benchmark_symbol"),
    [
        ("crypto", "ETH", "BTC"),
        ("currency_pair", "EURUSD", "GBPUSD"),
    ],
)
def test_continuous_markets_never_request_the_equity_calendar(
    asset_class: str,
    symbol: str,
    benchmark_symbol: str,
) -> None:
    full = _bars("2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05")

    prepared = prepare_market_data(
        {
            **_config(symbol),
            "asset_class": asset_class,
            "benchmark_symbol": benchmark_symbol,
            "start_date": "2024-01-02",
            "end_date": "2024-01-05",
        },
        fetch_ohlcv_func=_fetcher({symbol: full, benchmark_symbol: full}),
        fetch_market_calendar_func=lambda **_: (_ for _ in ()).throw(
            AssertionError("continuous markets must not request an equity calendar")
        ),
    )

    assert prepared.outcome == "full_coverage"


def test_no_common_window_is_rejected_before_a_runnable_artifact_exists() -> None:
    with pytest.raises(MarketDataCoverageError) as exc_info:
        prepare_market_data(
            _config("AAPL", "MSFT"),
            fetch_ohlcv_func=_fetcher(
                {
                    "AAPL": _bars("2024-01-02", "2024-01-03"),
                    "MSFT": _bars("2024-01-05", "2024-01-08"),
                    "SPY": _bars(
                        "2024-01-02",
                        "2024-01-03",
                        "2024-01-04",
                        "2024-01-05",
                        "2024-01-08",
                    ),
                }
            ),
        )

    assert exc_info.value.code == "no_common_data_window"


def test_approved_effective_window_cannot_silently_change_during_execution() -> None:
    full = _bars(
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
        "2024-01-08",
    )
    approved = {
        "requested_date_range": {"start": "2024-01-02", "end": "2024-01-08"},
        "effective_date_range": {"start": "2024-01-03", "end": "2024-01-08"},
    }

    with pytest.raises(MarketDataCoverageError) as exc_info:
        prepare_market_data(
            _config("AAPL"),
            fetch_ohlcv_func=_fetcher({"AAPL": full, "SPY": full}),
            approved_coverage=approved,
        )

    assert exc_info.value.code == "approved_data_window_unavailable"


def test_approved_dataset_identity_cannot_silently_change_during_execution() -> None:
    confirmed = _bars(
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
        "2024-01-08",
    )
    config = _config("AAPL")
    preflight = prepare_market_data(
        config,
        fetch_ohlcv_func=_fetcher({"AAPL": confirmed, "SPY": confirmed}),
    ).coverage_payload()
    preflight["preflight_id"] = preflight.pop("dataset_id")
    revised = confirmed.copy(deep=True)
    revised.loc[revised.index[-1], "close"] += 1.0

    with pytest.raises(MarketDataCoverageError) as exc_info:
        prepare_market_data(
            config,
            fetch_ohlcv_func=_fetcher({"AAPL": revised, "SPY": confirmed}),
            approved_coverage=preflight,
        )

    assert exc_info.value.code == "approved_data_window_unavailable"


def test_approved_dataset_identity_accepts_the_identical_execution_dataset() -> None:
    confirmed = _bars(
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
        "2024-01-08",
    )
    config = _config("AAPL")
    preflight = prepare_market_data(
        config,
        fetch_ohlcv_func=_fetcher({"AAPL": confirmed, "SPY": confirmed}),
    ).coverage_payload()
    preflight["preflight_id"] = preflight.pop("dataset_id")

    prepared = prepare_market_data(
        config,
        fetch_ohlcv_func=_fetcher({"AAPL": confirmed, "SPY": confirmed}),
        approved_coverage=preflight,
    )

    assert prepared.dataset_id == preflight["preflight_id"]


def test_metrics_and_chart_share_prepared_bars_without_refetch_or_edge_backfill() -> None:
    full = _bars(
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
        "2024-01-08",
    )
    calls: Counter[str] = Counter()
    config = _config("AAPL", "MSFT")
    prepared = prepare_market_data(
        config,
        fetch_ohlcv_func=_fetcher(
            {
                "AAPL": full,
                "MSFT": _bars("2024-01-04", "2024-01-05", "2024-01-08", base=200),
                "SPY": full,
            },
            calls,
        ),
    )
    effective_config = apply_coverage_to_config(config, prepared)
    calls_after_preflight = calls.copy()

    metrics = compute_alpha_metrics(
        effective_config,
        prepared_market_data=prepared,
    )
    chart = build_result_chart(
        effective_config,
        prepared_market_data=prepared,
    )

    assert calls == calls_after_preflight
    assert chart["series"][0]["time"] == "2024-01-04"
    assert chart["series"][-1]["time"] == "2024-01-08"
    assert chart["series"][0]["value"] == 10_000.0
    assert (
        metrics["aggregate"]["performance"]["portfolio_value_range"]["lowest_value"]
        >= 10_000.0
    )
    assert effective_config["data_coverage"]["dataset_id"] == prepared.dataset_id


# Completion clamp property (#475): bars enter coverage only once their trading
# day can no longer change, so the preflight and the worker must resolve the
# same effective window for the same request at any time of day.

_INCIDENT_NOW = datetime.fromisoformat("2026-08-12T15:56:00+00:00")

_US_EQUITY_HOLIDAYS_2026_Q3 = frozenset(
    {
        date.fromisoformat("2026-07-03"),
        date.fromisoformat("2026-09-07"),
    }
)


def _realistic_us_equity_sessions(
    start: date,
    end: date,
) -> tuple[EquityMarketSession, ...]:
    sessions = []
    day = start
    while day <= end:
        if day.weekday() < 5 and day not in _US_EQUITY_HOLIDAYS_2026_Q3:
            sessions.append(
                EquityMarketSession(
                    provider="alpaca",
                    session_date=day,
                    opens_at=datetime.fromisoformat(f"{day.isoformat()}T09:30:00-04:00"),
                    closes_at=datetime.fromisoformat(f"{day.isoformat()}T16:00:00-04:00"),
                )
            )
        day += timedelta(days=1)
    return tuple(sessions)


def _realistic_calendar(calls: list[tuple[date, date]] | None = None):
    def fetch(*, start_date: date, end_date: date) -> tuple[EquityMarketSession, ...]:
        if calls is not None:
            calls.append((start_date, end_date))
        return _realistic_us_equity_sessions(start_date, end_date)

    return fetch


_AUGUST_SESSION_DAYS = (
    "2026-08-05",
    "2026-08-06",
    "2026-08-07",
    "2026-08-10",
    "2026-08-11",
)


def _august_config(**overrides: object) -> dict[str, object]:
    config = {
        **_config("KO"),
        "start_date": "2026-08-05",
        "end_date": "2026-08-12",
    }
    config.update(overrides)
    config.setdefault(
        "requested_date_range",
        {"start": str(config["start_date"]), "end": str(config["end_date"])},
    )
    return config


def _crypto_config(**overrides: object) -> dict[str, object]:
    config = {
        **_config("ETH"),
        "asset_class": "crypto",
        "benchmark_symbol": "BTC",
        "start_date": "2026-08-05",
        "end_date": "2026-08-10",
    }
    config.update(overrides)
    config.setdefault(
        "requested_date_range",
        {"start": str(config["start_date"]), "end": str(config["end_date"])},
    )
    return config


def _bars_with_forming_day(close: float, volume: float) -> pd.DataFrame:
    complete = _bars(*_AUGUST_SESSION_DAYS)
    forming = pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 0.5,
            "low": close - 1.0,
            "close": close,
            "volume": volume,
        },
        index=pd.DatetimeIndex([pd.Timestamp("2026-08-12", tz="UTC")]),
    )
    return pd.concat([complete, forming])


def _approved_payload(prepared) -> dict[str, object]:
    payload = prepared.coverage_payload()
    payload["preflight_id"] = payload.pop("dataset_id")
    return payload


def test_equity_window_ending_today_mid_session_clamps_to_last_completed_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    bars = _bars_with_forming_day(close=87.025, volume=417_972.0)

    prepared = prepare_market_data(
        _august_config(),
        fetch_ohlcv_func=_fetcher({"KO": bars, "SPY": bars}),
        fetch_market_calendar_func=_realistic_calendar(),
        now=_INCIDENT_NOW,
    )

    assert prepared.effective_date_range.model_dump() == {
        "start": "2026-08-05",
        "end": "2026-08-11",
    }
    assert prepared.outcome == "adjusted_coverage"
    assert prepared.adjustment_reason == "calendar_alignment"


@pytest.mark.parametrize(
    ("now_utc", "expected_end"),
    [
        # 17:34 ET: after the close, corrections can still change the bar.
        ("2026-08-12T21:34:00+00:00", "2026-08-11"),
        # 20:01 ET: after-hours over, but the session's Eastern date remains.
        ("2026-08-13T00:01:00+00:00", "2026-08-11"),
        # 00:01 ET the next day: the session's date has passed, its bar is final.
        ("2026-08-13T04:01:00+00:00", "2026-08-12"),
    ],
)
def test_equity_completion_boundary_is_eastern_midnight(
    monkeypatch: pytest.MonkeyPatch,
    now_utc: str,
    expected_end: str,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    bars = _bars(*_AUGUST_SESSION_DAYS, "2026-08-12")

    prepared = prepare_market_data(
        _august_config(),
        fetch_ohlcv_func=_fetcher({"KO": bars, "SPY": bars}),
        fetch_market_calendar_func=_realistic_calendar(),
        now=datetime.fromisoformat(now_utc),
    )

    assert prepared.effective_date_range.model_dump()["end"] == expected_end


@pytest.mark.parametrize(
    ("session_days", "window_start", "window_end", "now_utc", "expected_end"),
    [
        # Weekend: Saturday resolves to Friday's session.
        (
            (*_AUGUST_SESSION_DAYS, "2026-08-12", "2026-08-13", "2026-08-14"),
            "2026-08-05",
            "2026-08-15",
            "2026-08-15T18:00:00+00:00",
            "2026-08-14",
        ),
        # Labor Day: the holiday Monday resolves past the weekend to Friday.
        (
            ("2026-08-31", "2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04"),
            "2026-08-31",
            "2026-09-07",
            "2026-09-07T15:00:00+00:00",
            "2026-09-04",
        ),
    ],
)
def test_equity_window_ending_on_closed_days_resolves_to_prior_session(
    monkeypatch: pytest.MonkeyPatch,
    session_days: tuple[str, ...],
    window_start: str,
    window_end: str,
    now_utc: str,
    expected_end: str,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    bars = _bars(*session_days)

    prepared = prepare_market_data(
        _august_config(start_date=window_start, end_date=window_end),
        fetch_ohlcv_func=_fetcher({"KO": bars, "SPY": bars}),
        fetch_market_calendar_func=_realistic_calendar(),
        now=datetime.fromisoformat(now_utc),
    )

    assert prepared.effective_date_range.model_dump()["end"] == expected_end


def test_historical_window_is_untouched_by_the_completion_clamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    session_days = ("2026-07-13", "2026-07-14", "2026-07-15", "2026-07-16", "2026-07-17")
    bars = _bars(*session_days)
    calendar_calls: list[tuple[date, date]] = []

    prepared = prepare_market_data(
        _august_config(start_date="2026-07-13", end_date="2026-07-17"),
        fetch_ohlcv_func=_fetcher({"KO": bars, "SPY": bars}),
        fetch_market_calendar_func=_realistic_calendar(calendar_calls),
        now=_INCIDENT_NOW,
    )

    assert prepared.outcome == "full_coverage"
    assert prepared.effective_date_range.model_dump() == {
        "start": "2026-07-13",
        "end": "2026-07-17",
    }
    assert calendar_calls == [
        (date.fromisoformat("2026-07-13"), date.fromisoformat("2026-07-17"))
    ]


def test_preflight_and_worker_resolve_identical_windows_while_todays_bar_moves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    config = _august_config()
    preflight_bars = _bars_with_forming_day(close=87.025, volume=417_972.0)
    worker_bars = _bars_with_forming_day(close=86.995, volume=419_452.0)

    preflight = prepare_market_data(
        config,
        fetch_ohlcv_func=_fetcher({"KO": preflight_bars, "SPY": preflight_bars}),
        fetch_market_calendar_func=_realistic_calendar(),
        now=datetime.fromisoformat("2026-08-12T15:55:48+00:00"),
    )
    worker = prepare_market_data(
        apply_coverage_to_config(config, preflight),
        fetch_ohlcv_func=_fetcher({"KO": worker_bars, "SPY": worker_bars}),
        fetch_market_calendar_func=_realistic_calendar(),
        approved_coverage=_approved_payload(preflight),
        now=datetime.fromisoformat("2026-08-12T15:56:15+00:00"),
    )

    assert worker.effective_date_range == preflight.effective_date_range
    assert worker.dataset_id == preflight.dataset_id


def test_worker_reclamp_is_a_noop_across_the_completion_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    config = _august_config()
    bars = _bars(*_AUGUST_SESSION_DAYS, "2026-08-12")

    preflight = prepare_market_data(
        config,
        fetch_ohlcv_func=_fetcher({"KO": bars, "SPY": bars}),
        fetch_market_calendar_func=_realistic_calendar(),
        now=datetime.fromisoformat("2026-08-13T03:59:00+00:00"),
    )
    worker = prepare_market_data(
        apply_coverage_to_config(config, preflight),
        fetch_ohlcv_func=_fetcher({"KO": bars, "SPY": bars}),
        fetch_market_calendar_func=_realistic_calendar(),
        approved_coverage=_approved_payload(preflight),
        now=datetime.fromisoformat("2026-08-13T04:01:00+00:00"),
    )

    assert preflight.effective_date_range.model_dump()["end"] == "2026-08-11"
    assert worker.effective_date_range == preflight.effective_date_range
    assert worker.dataset_id == preflight.dataset_id


def test_crypto_window_ending_today_clamps_to_previous_utc_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    days = tuple(f"2026-08-{day:02d}" for day in range(5, 11))
    bars = _bars(*days)

    prepared = prepare_market_data(
        _crypto_config(),
        fetch_ohlcv_func=_fetcher({"ETH": bars, "BTC": bars}),
        fetch_market_calendar_func=_no_equity_calendar,
        now=datetime.fromisoformat("2026-08-10T12:00:00+00:00"),
    )

    # Monday: crypto keeps Sunday, where the equity rule resolves to Friday.
    assert prepared.effective_date_range.model_dump()["end"] == "2026-08-09"
    assert prepared.adjustment_reason == "calendar_alignment"


def test_crypto_window_ending_yesterday_is_untouched_after_utc_midnight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    days = tuple(f"2026-08-{day:02d}" for day in range(5, 13))
    bars = _bars(*days)

    prepared = prepare_market_data(
        _crypto_config(end_date="2026-08-12"),
        fetch_ohlcv_func=_fetcher({"ETH": bars, "BTC": bars}),
        fetch_market_calendar_func=_no_equity_calendar,
        now=datetime.fromisoformat("2026-08-13T00:30:00+00:00"),
    )

    assert prepared.outcome == "full_coverage"
    assert prepared.effective_date_range.model_dump()["end"] == "2026-08-12"


def test_currency_pair_weekend_end_resolves_to_friday_bar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    weekday_days = (
        "2026-08-10",
        "2026-08-11",
        "2026-08-12",
        "2026-08-13",
        "2026-08-14",
    )
    bars = _bars(*weekday_days)

    prepared = prepare_market_data(
        _crypto_config(
            asset_class="currency_pair",
            symbols=["EURUSD"],
            benchmark_symbol="EURUSD",
            start_date="2026-08-10",
            end_date="2026-08-16",
        ),
        fetch_ohlcv_func=_fetcher({"EURUSD": bars}),
        fetch_market_calendar_func=_no_equity_calendar,
        now=datetime.fromisoformat("2026-08-16T12:00:00+00:00"),
    )

    assert prepared.effective_date_range.model_dump()["end"] == "2026-08-14"


def test_window_entirely_inside_the_forming_day_is_rejected_with_typed_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    bars = _bars("2026-08-12")

    with pytest.raises(MarketDataCoverageError) as excinfo:
        prepare_market_data(
            _crypto_config(start_date="2026-08-12", end_date="2026-08-12"),
            fetch_ohlcv_func=_fetcher({"ETH": bars, "BTC": bars}),
            fetch_market_calendar_func=_no_equity_calendar,
            now=datetime.fromisoformat("2026-08-12T15:56:00+00:00"),
        )

    assert excinfo.value.code == "no_common_data_window"


def test_synthetic_fixture_mode_bypasses_the_completion_clamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
    bars = _bars(*_AUGUST_SESSION_DAYS, "2026-08-12")

    prepared = prepare_market_data(
        _august_config(),
        fetch_ohlcv_func=_fetcher({"KO": bars, "SPY": bars}),
        fetch_market_calendar_func=_no_equity_calendar,
        now=_INCIDENT_NOW,
    )

    assert prepared.outcome == "full_coverage"
    assert prepared.effective_date_range.model_dump()["end"] == "2026-08-12"


def test_calendar_failure_fails_closed_for_live_current_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    bars = _bars(*_AUGUST_SESSION_DAYS, "2026-08-12")

    def broken_calendar(**_: object) -> tuple[EquityMarketSession, ...]:
        raise RuntimeError("calendar down")

    with pytest.raises(MarketDataCoverageError) as excinfo:
        prepare_market_data(
            _august_config(),
            fetch_ohlcv_func=_fetcher({"KO": bars, "SPY": bars}),
            fetch_market_calendar_func=broken_calendar,
            now=_INCIDENT_NOW,
        )

    assert excinfo.value.code == "market_data_unavailable"


def test_approved_window_hash_guard_still_rejects_changed_final_bars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    config = _august_config()
    now = datetime.fromisoformat("2026-08-13T05:00:00+00:00")
    original = _bars(*_AUGUST_SESSION_DAYS, "2026-08-12")
    revised = original.copy(deep=True)
    revised.iloc[-1, revised.columns.get_loc("close")] += 0.5

    preflight = prepare_market_data(
        config,
        fetch_ohlcv_func=_fetcher({"KO": original, "SPY": original}),
        fetch_market_calendar_func=_realistic_calendar(),
        now=now,
    )

    with pytest.raises(MarketDataCoverageError) as excinfo:
        prepare_market_data(
            apply_coverage_to_config(config, preflight),
            fetch_ohlcv_func=_fetcher({"KO": revised, "SPY": revised}),
            fetch_market_calendar_func=_realistic_calendar(),
            approved_coverage=_approved_payload(preflight),
            now=now,
        )

    assert excinfo.value.code == "approved_data_window_unavailable"


@pytest.mark.parametrize("clause", ["requested_range", "effective_range", "dataset_id"])
def test_approved_window_rejection_names_the_mismatched_clause(
    monkeypatch: pytest.MonkeyPatch,
    clause: str,
) -> None:
    from loguru import logger as loguru_logger

    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    config = _august_config()
    now = datetime.fromisoformat("2026-08-13T05:00:00+00:00")
    bars = _bars(*_AUGUST_SESSION_DAYS, "2026-08-12")

    preflight = prepare_market_data(
        config,
        fetch_ohlcv_func=_fetcher({"KO": bars, "SPY": bars}),
        fetch_market_calendar_func=_realistic_calendar(),
        now=now,
    )
    tampered = _approved_payload(preflight)
    if clause == "dataset_id":
        tampered["preflight_id"] = "sha256:" + "0" * 64
    else:
        key = "requested_date_range" if clause == "requested_range" else "effective_date_range"
        tampered[key] = {**tampered[key], "start": "2026-08-04"}

    captured: list[str] = []
    handler_id = loguru_logger.add(
        lambda message: captured.append(str(message)), level="WARNING"
    )
    try:
        with pytest.raises(MarketDataCoverageError):
            prepare_market_data(
                apply_coverage_to_config(config, preflight),
                fetch_ohlcv_func=_fetcher({"KO": bars, "SPY": bars}),
                fetch_market_calendar_func=_realistic_calendar(),
                approved_coverage=tampered,
                now=now,
            )
    finally:
        loguru_logger.remove(handler_id)

    mismatch_lines = [line for line in captured if "Approved data window" in line]
    assert mismatch_lines, captured
    line = mismatch_lines[-1]
    assert f"rejected: {clause} approved=" in line
    if clause == "dataset_id":
        assert "sha256:000000" in line
        assert preflight.dataset_id in line
    else:
        assert "approved=2026-08-04" in line
    # A hash-only failure must show whether both windows stayed the same.
    assert f"requested_range approved={tampered['requested_date_range']['start']}" in line
    assert f"current={preflight.requested_date_range.start}..{preflight.requested_date_range.end}" in line
    assert f"effective_range approved={tampered['effective_date_range']['start']}" in line
    assert f"current={preflight.effective_date_range.start}..{preflight.effective_date_range.end}" in line


def test_intraday_timeframes_keep_the_current_days_completed_candles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    hours = pd.date_range(
        start="2026-08-11T13:00:00Z", end="2026-08-12T15:00:00Z", freq="1h"
    )
    frame = pd.DataFrame(
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1_000.0,
        },
        index=hours,
    )

    prepared = prepare_market_data(
        _august_config(timeframe="1h", start_date="2026-08-11"),
        fetch_ohlcv_func=_fetcher({"KO": frame, "SPY": frame}),
        fetch_market_calendar_func=_realistic_calendar(),
        now=_INCIDENT_NOW,
    )

    assert prepared.effective_date_range.model_dump()["end"] == "2026-08-12"


def test_same_day_intraday_crypto_window_keeps_density_owned_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    hours = pd.date_range(
        start="2026-08-12T00:00:00Z", end="2026-08-12T14:00:00Z", freq="1h"
    )
    frame = pd.DataFrame(
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1_000.0,
        },
        index=hours,
    )

    with pytest.raises(MarketDataCoverageError) as excinfo:
        prepare_market_data(
            _crypto_config(
                timeframe="1h", start_date="2026-08-12", end_date="2026-08-12"
            ),
            fetch_ohlcv_func=_fetcher({"ETH": frame, "BTC": frame}),
            fetch_market_calendar_func=_no_equity_calendar,
            now=datetime.fromisoformat("2026-08-12T15:56:00+00:00"),
        )

    # Density owns this rejection exactly as before the completion clamp; the
    # clamp must not pre-empt it with no_common_data_window.
    assert excinfo.value.code == "insufficient_common_data"
