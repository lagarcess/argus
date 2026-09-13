from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import pytest
from argus.agent_runtime.confirmation_artifacts import (
    validate_confirmation_execution_payload,
)
from argus.agent_runtime.confirmation_revalidation import (
    revalidated_confirmation_candidate,
)
from argus.agent_runtime.retest_confirmation import (
    prepare_retest_confirmation_payload,
)
from argus.api.chat.confirmation import runtime_confirmation_card
from argus.domain.backtesting.coverage import prepare_market_data
from argus.domain.engine_launch.models import LaunchBacktestRequest
from argus.domain.retest_setup import RetestSetup

from tests.domain.test_market_data_coverage import (
    _approved_payload,
    _bars,
    _config,
    _fetcher,
    _market_session,
    _session_calendar,
)


def _confirmation_card(
    adjustment_reason: str | None,
    *,
    limited_by: dict[str, str] | None = None,
) -> dict[str, object]:
    coverage_preflight: dict[str, object] = {
        "outcome": "adjusted_coverage",
        "requested_date_range": {
            "start": "2024-01-01",
            "end": "2024-01-05",
        },
        "effective_date_range": {
            "start": "2024-01-03",
            "end": "2024-01-05",
        },
        "preflight_id": "coverage-fixture",
    }
    if adjustment_reason is not None:
        coverage_preflight["adjustment_reason"] = adjustment_reason
    if limited_by is not None:
        coverage_preflight["limited_by"] = limited_by

    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "asset_universe": ["AAPL"],
                    "asset_class": "equity",
                    "date_range": {"start": "2024-01-03", "end": "2024-01-05"},
                },
                "launch_payload": {
                    "strategy_type": "buy_and_hold",
                    "symbol": "AAPL",
                    "symbols": ["AAPL"],
                    "asset_class": "equity",
                    "timeframe": "1D",
                    "date_range": {"start": "2024-01-03", "end": "2024-01-05"},
                    "requested_date_range": {
                        "start": "2024-01-01",
                        "end": "2024-01-05",
                    },
                    "coverage_preflight": coverage_preflight,
                    "sizing_mode": "capital_amount",
                    "capital_amount": 10_000,
                    "benchmark_symbol": "SPY",
                },
            },
        },
        language="en",
    )

    assert card is not None
    return card


def test_confirmation_card_carries_only_provider_adjustment_sidecar() -> None:
    card = _confirmation_card("provider_coverage_adjustment")

    assert card["date_range"] == {
        "start": "2024-01-03",
        "end": "2024-01-05",
        "display": "January 3, 2024 - January 5, 2024",
    }
    assert card["period_adjustment"] == {
        "code": "effective_window_adjusted",
        "requested_date_range": {"start": "2024-01-01", "end": "2024-01-05"},
        "effective_date_range": {"start": "2024-01-03", "end": "2024-01-05"},
    }


def test_confirmation_card_names_the_series_that_limits_the_start() -> None:
    card = _confirmation_card(
        "provider_coverage_adjustment",
        limited_by={"symbol": "AAPL", "first_available": "2024-01-03"},
    )

    assert card["period_adjustment"] == {
        "code": "effective_window_adjusted",
        "requested_date_range": {"start": "2024-01-01", "end": "2024-01-05"},
        "effective_date_range": {"start": "2024-01-03", "end": "2024-01-05"},
        "limited_by": {"symbol": "AAPL", "first_available": "2024-01-03"},
    }


@pytest.mark.parametrize(
    "adjustment_reason",
    ["none", "calendar_alignment", None, "unknown_reason"],
)
def test_confirmation_card_omits_non_provider_adjustment_sidecar(
    adjustment_reason: str | None,
) -> None:
    assert "period_adjustment" not in _confirmation_card(adjustment_reason)


def test_full_coverage_confirmation_does_not_emit_adjustment() -> None:
    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "asset_universe": ["AAPL"],
                    "asset_class": "equity",
                    "date_range": {"start": "2024-01-01", "end": "2024-01-05"},
                },
                "launch_payload": {
                    "strategy_type": "buy_and_hold",
                    "symbol": "AAPL",
                    "symbols": ["AAPL"],
                    "asset_class": "equity",
                    "timeframe": "1D",
                    "date_range": {"start": "2024-01-01", "end": "2024-01-05"},
                    "requested_date_range": {
                        "start": "2024-01-01",
                        "end": "2024-01-05",
                    },
                    "coverage_preflight": {
                        "outcome": "full_coverage",
                        "requested_date_range": {
                            "start": "2024-01-01",
                            "end": "2024-01-05",
                        },
                        "effective_date_range": {
                            "start": "2024-01-01",
                            "end": "2024-01-05",
                        },
                        "preflight_id": "coverage-fixture",
                    },
                    "sizing_mode": "capital_amount",
                    "capital_amount": 10_000,
                    "benchmark_symbol": "SPY",
                },
            },
        }
    )

    assert card is not None
    assert "period_adjustment" not in card


def _weekdays(start: str, end: str) -> list[str]:
    return [day.date().isoformat() for day in pd.bdate_range(start=start, end=end)]


@pytest.mark.parametrize(
    ("symbol", "benchmark_symbol", "late_symbol", "window", "late_start"),
    [
        ("SPY", "SPY", "SPY", ("2020-07-20", "2020-07-31"), "2020-07-27"),
        ("DOCN", "SPY", "DOCN", ("2021-03-15", "2021-03-31"), "2021-03-24"),
        ("SPY", "DOCN", "DOCN", ("2021-03-15", "2021-03-31"), "2021-03-24"),
    ],
    ids=("spy-vs-spy", "asset-history", "benchmark-history"),
)
def test_coverage_names_the_series_whose_history_starts_the_window(
    monkeypatch: pytest.MonkeyPatch,
    symbol: str,
    benchmark_symbol: str,
    late_symbol: str,
    window: tuple[str, str],
    late_start: str,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    days = _weekdays(*window)
    frames = {symbol: _bars(*days), benchmark_symbol: _bars(*days, base=300.0)}
    frames[late_symbol] = _bars(*(day for day in days if day >= late_start))

    prepared = prepare_market_data(
        {
            **_config(symbol),
            "benchmark_symbol": benchmark_symbol,
            "start_date": window[0],
            "end_date": window[1],
        },
        fetch_ohlcv_func=_fetcher(frames),
        fetch_market_calendar_func=_session_calendar(
            *(_market_session(day) for day in days)
        ),
    )

    assert prepared.effective_date_range.model_dump() == {
        "start": late_start,
        "end": window[1],
    }
    assert prepared.adjustment_reason == "provider_coverage_adjustment"
    assert prepared.coverage_payload()["limited_by"] == {
        "symbol": late_symbol,
        "first_available": late_start,
    }


def test_approved_execution_keeps_the_preflight_limiting_series(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    days = _weekdays("2021-03-15", "2021-03-31")
    frames = {
        "DOCN": _bars(*(day for day in days if day >= "2021-03-24")),
        "SPY": _bars(*days, base=300.0),
    }
    calendar = _session_calendar(*(_market_session(day) for day in days))
    config = {**_config("DOCN"), "start_date": days[0], "end_date": days[-1]}
    preflight = prepare_market_data(
        config,
        fetch_ohlcv_func=_fetcher(frames),
        fetch_market_calendar_func=calendar,
    )
    # Execution fetches from the effective start, where every series begins
    # together, so only the approval can name the limiting series.
    execution_config = {
        **config,
        "start_date": "2021-03-24",
        "requested_date_range": {"start": days[0], "end": days[-1]},
    }

    def executed_coverage(**approval: Any) -> dict[str, Any]:
        return prepare_market_data(
            execution_config,
            fetch_ohlcv_func=_fetcher(frames),
            fetch_market_calendar_func=calendar,
            approved_coverage=_approved_payload(preflight),
            approved_adjustment_reason=preflight.adjustment_reason,
            **approval,
        ).coverage_payload()

    assert executed_coverage(approved_limited_by=preflight.limited_by)["limited_by"] == {
        "symbol": "DOCN",
        "first_available": "2021-03-24",
    }
    assert "limited_by" not in executed_coverage()


def _serve_recorded_bars(
    monkeypatch: pytest.MonkeyPatch,
    first_bars: dict[str, str],
    *,
    end: str,
) -> None:
    from argus.domain.backtesting import coverage
    from argus.domain.engine_launch import adapter

    frames = {
        symbol: _bars(*_weekdays(first_bar, end))
        for symbol, first_bar in first_bars.items()
    }

    def prepare_with_recorded_bars(config: dict[str, Any], **kwargs: Any) -> Any:
        return prepare_market_data(
            config,
            fetch_ohlcv_func=lambda *, symbol, **_: frames[symbol].copy(deep=True),
            **kwargs,
        )

    monkeypatch.setattr(coverage, "prepare_market_data", prepare_with_recorded_bars)
    monkeypatch.setattr(
        adapter,
        "validate_request_symbols",
        lambda request: adapter.RequestSymbolValidationResult(
            outcome="resolved",
            symbols=tuple(request.symbols),
            asset_class="equity",
        ),
    )
    monkeypatch.setattr(
        adapter,
        "validate_request_benchmark",
        lambda request, *, asset_class: adapter.BenchmarkSymbolValidationResult(
            outcome="resolved",
            benchmark_symbol=request.benchmark_symbol,
            asset_class=asset_class,
        ),
    )


def _retest_setup(
    symbols: tuple[str, ...],
    benchmark_symbol: str,
    *,
    start: str,
    end: str,
) -> RetestSetup:
    return RetestSetup(
        source_run_id="run-limited-history",
        strategy_type="buy_and_hold",
        symbols=symbols,
        asset_class="equity",
        timeframe="1D",
        original_start=date.fromisoformat(start),
        original_end=date.fromisoformat(end),
        start=date.fromisoformat(start),
        end=date.fromisoformat(end),
        sizing_mode="capital_amount",
        benchmark_symbol=benchmark_symbol,
        capital_amount=10_000.0,
    )


@pytest.mark.parametrize(
    ("symbols", "benchmark_symbol", "first_bars", "window", "limited_by"),
    [
        (
            ("SPY",),
            "SPY",
            {"SPY": "2020-07-27"},
            ("2020-07-20", "2020-07-31"),
            {"symbol": "SPY", "first_available": "2020-07-27"},
        ),
        (
            ("DOCN",),
            "SPY",
            {"DOCN": "2021-03-24", "SPY": "2021-03-15"},
            ("2021-03-15", "2021-03-31"),
            {"symbol": "DOCN", "first_available": "2021-03-24"},
        ),
    ],
    ids=("spy-vs-spy", "docn-vs-spy"),
)
def test_limiting_series_survives_validation_and_the_retest_path(
    monkeypatch: pytest.MonkeyPatch,
    symbols: tuple[str, ...],
    benchmark_symbol: str,
    first_bars: dict[str, str],
    window: tuple[str, str],
    limited_by: dict[str, str],
) -> None:
    start, end = window
    _serve_recorded_bars(monkeypatch, first_bars, end=end)

    preparation = prepare_retest_confirmation_payload(
        _retest_setup(symbols, benchmark_symbol, start=start, end=end)
    )

    assert preparation.coverage_error_code is None
    payload = preparation.confirmation_payload
    assert payload is not None
    launch_payload = payload["launch_payload"]
    assert launch_payload["date_range"] == {
        "start": limited_by["first_available"],
        "end": end,
    }
    assert launch_payload["coverage_preflight"]["limited_by"] == limited_by

    validation = validate_confirmation_execution_payload(payload)
    assert validation.executable is True
    assert validation.launch_payload is not None
    # Provenance is not launch identity, so the validated dump leaves it out.
    assert "limited_by" not in validation.launch_payload["coverage_preflight"]
    request = LaunchBacktestRequest.model_validate(launch_payload)
    assert request.coverage_preflight is not None
    assert request.coverage_preflight.limited_by is not None
    assert request.coverage_preflight.limited_by.model_dump() == limited_by


def test_basket_revalidation_keeps_the_added_series_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _serve_recorded_bars(
        monkeypatch,
        {"AAPL": "2021-03-15", "SPY": "2021-03-15", "DOCN": "2021-03-24"},
        end="2021-03-31",
    )
    source = prepare_retest_confirmation_payload(
        _retest_setup(("AAPL",), "SPY", start="2021-03-15", end="2021-03-31")
    ).confirmation_payload
    assert source is not None
    assert "limited_by" not in source["launch_payload"]["coverage_preflight"]
    patched_launch = {
        key: value
        for key, value in source["launch_payload"].items()
        if key != "coverage_preflight"
    }
    patched_launch["symbols"] = ["AAPL", "DOCN"]

    candidate, error_code = revalidated_confirmation_candidate(
        patched_strategy={**source["strategy"], "asset_universe": ["AAPL", "DOCN"]},
        patched_launch=patched_launch,
        source_payload=source,
    )

    assert error_code is None
    assert candidate is not None
    assert candidate["launch_payload"]["coverage_preflight"]["limited_by"] == {
        "symbol": "DOCN",
        "first_available": "2021-03-24",
    }
