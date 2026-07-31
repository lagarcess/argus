from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest
from argus.agent_runtime.retest_confirmation import (
    retest_confirmation_payload,
    retest_runtime_result,
)
from argus.domain.retest_setup import retest_setup_from_run

_TODAY = date(2026, 7, 31)

_BUY_AND_HOLD = {
    "strategy_type": "buy_and_hold",
    "symbol": "TSLA",
    "timeframe": "1D",
    "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
    "entry_rule": None,
    "exit_rule": None,
    "sizing_mode": "capital_amount",
    "capital_amount": 10_000.0,
    "position_size": None,
    "cadence": None,
    "parameters": {},
    "risk_rules": [],
    "benchmark_symbol": "SPY",
}
_DCA = {
    **_BUY_AND_HOLD,
    "strategy_type": "dca_accumulation",
    "capital_amount": 500.0,
    "cadence": "monthly",
}
_INDICATOR_THRESHOLD = {
    **_BUY_AND_HOLD,
    "strategy_type": "indicator_threshold",
    "entry_rule": {"indicator": "rsi", "operator": "below", "threshold": 30},
    "exit_rule": {"indicator": "rsi", "operator": "above", "threshold": 55},
}
_SIGNAL_STRATEGY = {
    **_BUY_AND_HOLD,
    "strategy_type": "signal_strategy",
    "entry_rule": {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 20,
        "slow_indicator": "sma",
        "slow_period": 50,
        "direction": "bullish",
    },
    "exit_rule": {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 20,
        "slow_indicator": "sma",
        "slow_period": 50,
        "direction": "bearish",
    },
}


def _persisted_run(
    monkeypatch: pytest.MonkeyPatch,
    request_payload: dict[str, Any],
) -> dict[str, Any]:
    from argus.api.chat.persistence import build_runtime_backtest_run
    from argus.domain.engine_launch.adapter import run_launch_backtest
    from argus.domain.engine_launch.models import LaunchBacktestRequest

    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
    launch = run_launch_backtest(LaunchBacktestRequest.model_validate(request_payload))
    assert launch.envelope.execution_status == "succeeded"
    assert launch.result_card is not None
    run = build_runtime_backtest_run(
        user_id="retest-fixture-user",
        conversation_id="retest-fixture-conversation",
        result_card=launch.result_card,
        envelope=launch.envelope.model_dump(mode="python"),
        default_benchmark_func=lambda _asset_class, _symbols: "SPY",
        run_id=f"retest-fixture-{request_payload['strategy_type']}",
    )
    assert run is not None
    return run.model_dump(mode="python")


@pytest.mark.parametrize(
    "request_payload",
    [_BUY_AND_HOLD, _DCA, _INDICATOR_THRESHOLD, _SIGNAL_STRATEGY],
    ids=["buy_and_hold", "dca", "indicator_threshold", "signal_strategy"],
)
def test_supported_runs_reload_into_an_executable_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    request_payload: dict[str, Any],
) -> None:
    run = _persisted_run(monkeypatch, request_payload)

    setup = retest_setup_from_run(run, today=_TODAY)

    assert setup is not None
    assert setup.strategy_type == request_payload["strategy_type"]
    assert setup.symbols == ("TSLA",)
    assert setup.benchmark_symbol == "SPY"
    payload = retest_confirmation_payload(setup, language="en")
    assert payload is not None
    assert payload["validation"] == {
        "status": "ready_to_run",
        "executable": True,
        "date_adjusted": False,
    }
    assert payload["launch_payload"]["strategy_type"] == setup.strategy_type
    assert payload["launch_payload"]["date_range"] == {
        "start": setup.start.isoformat(),
        "end": setup.end.isoformat(),
    }


@pytest.mark.parametrize(
    "request_payload",
    [_BUY_AND_HOLD, _DCA, _INDICATOR_THRESHOLD, _SIGNAL_STRATEGY],
    ids=["buy_and_hold", "dca", "indicator_threshold", "signal_strategy"],
)
def test_confirmation_card_is_ready_to_run_without_provider_calls(
    monkeypatch: pytest.MonkeyPatch,
    request_payload: dict[str, Any],
) -> None:
    from argus.api.chat.confirmation import runtime_confirmation_card

    run = _persisted_run(monkeypatch, request_payload)
    monkeypatch.delenv("ARGUS_MARKET_DATA_PROVIDER_MODE", raising=False)
    monkeypatch.setattr(
        "argus.domain.backtesting.coverage.prepare_market_data",
        _forbidden_provider_call,
    )
    setup = retest_setup_from_run(run, today=_TODAY)
    assert setup is not None

    payload = retest_confirmation_payload(
        setup,
        language="en",
        confirmation_id="confirmation-retest-1",
    )
    assert payload is not None
    card = runtime_confirmation_card(
        retest_runtime_result(payload),
        confirmation_id="confirmation-retest-1",
        conversation_id="retest-fixture-conversation",
        language="en",
    )

    assert card is not None
    assert card["status"] == "ready_to_run"
    assert card["confirmation_id"] == "confirmation-retest-1"
    assert [action["type"] for action in card["actions"]][0] == "run_backtest"
    assert card["date_range"] == {
        "start": setup.start.isoformat(),
        "end": setup.end.isoformat(),
        "display": card["date_range"]["display"],
    }


def test_window_preserves_the_original_calendar_day_span(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _persisted_run(monkeypatch, _BUY_AND_HOLD)

    setup = retest_setup_from_run(run, today=_TODAY)

    assert setup is not None
    assert setup.original_start == date(2024, 1, 1)
    assert setup.original_end == date(2024, 12, 31)
    assert setup.duration_days == 365
    assert setup.end == _TODAY
    assert setup.start == _TODAY - timedelta(days=365)


def test_injected_clock_moves_the_window_without_changing_the_span(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _persisted_run(monkeypatch, _BUY_AND_HOLD)

    earlier = retest_setup_from_run(run, today=date(2026, 1, 15))
    later = retest_setup_from_run(run, today=date(2027, 3, 2))

    assert earlier is not None and later is not None
    assert earlier.duration_days == later.duration_days == 365
    assert earlier.end == date(2026, 1, 15)
    assert later.end == date(2027, 3, 2)
    assert (earlier.end - earlier.start) == (later.end - later.start)


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ({"config_snapshot": {}}, "missing canonical setup"),
        (
            {"symbols": [], "conversation_result_card": {}},
            "missing symbols",
        ),
        ({"asset_class": "commodity"}, "unsupported asset class"),
        ({"id": None}, "missing run identity"),
    ],
)
def test_unfaithful_runs_have_no_retest_setup(
    monkeypatch: pytest.MonkeyPatch,
    mutation: dict[str, Any],
    reason: str,
) -> None:
    run = {**_persisted_run(monkeypatch, _BUY_AND_HOLD), **mutation}

    assert retest_setup_from_run(run, today=_TODAY) is None, reason


def test_unsupported_strategy_template_has_no_retest_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _persisted_run(monkeypatch, _BUY_AND_HOLD)
    run["config_snapshot"]["template"] = "pairs_trading"
    run["config_snapshot"]["resolved_strategy"]["strategy_type"] = "pairs_trading"

    assert retest_setup_from_run(run, today=_TODAY) is None


def test_reversed_original_window_has_no_retest_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _persisted_run(monkeypatch, _BUY_AND_HOLD)
    run["config_snapshot"]["date_range"] = {
        "start": "2024-12-31",
        "end": "2024-01-01",
    }

    assert retest_setup_from_run(run, today=_TODAY) is None


def test_inconsistent_dca_snapshot_has_no_retest_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _persisted_run(monkeypatch, _DCA)
    run["config_snapshot"]["engine_config"] = {"recurring_contribution": 999.0}

    assert retest_setup_from_run(run, today=_TODAY) is None


def test_window_shorter_than_the_indicator_warmup_is_not_confirmable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _persisted_run(monkeypatch, _SIGNAL_STRATEGY)
    run["config_snapshot"]["date_range"] = {
        "start": "2024-01-01",
        "end": "2024-01-08",
    }

    setup = retest_setup_from_run(run, today=_TODAY)

    assert setup is not None
    assert retest_confirmation_payload(setup, language="en") is None


def _forbidden_provider_call(*args: Any, **kwargs: Any) -> Any:
    raise AssertionError("retest confirmation must not touch market data")


def test_multi_symbol_runs_carry_every_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    symbols = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]
    run = _persisted_run(
        monkeypatch,
        {**_BUY_AND_HOLD, "symbol": symbols[0], "symbols": symbols},
    )

    setup = retest_setup_from_run(run, today=_TODAY)

    assert setup is not None
    assert list(setup.symbols) == symbols
    payload = retest_confirmation_payload(setup, language="en")
    assert payload is not None
    assert payload["launch_payload"]["symbols"] == symbols
    assert payload["strategy"]["asset_universe"] == symbols


def test_runs_above_the_symbol_ceiling_have_no_retest_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _persisted_run(monkeypatch, _BUY_AND_HOLD)
    run["symbols"] = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META"]

    assert retest_setup_from_run(run, today=_TODAY) is None


def test_costed_runs_are_not_offered_while_the_kill_switch_is_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    run = _persisted_run(
        monkeypatch,
        {
            **_BUY_AND_HOLD,
            "_execution_realism": {
                "enabled": True,
                "fee_bps": 10.0,
                "slippage_bps": 5.0,
            },
        },
    )
    setup = retest_setup_from_run(run, today=_TODAY)
    assert setup is not None
    assert retest_confirmation_payload(setup, language="en") is not None

    # The engine drops stored costs while the kill switch is off, so confirming
    # this replay would promise costs the run would never apply.
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "false")

    assert retest_confirmation_payload(setup, language="en") is None


def test_idealized_runs_stay_offered_while_the_kill_switch_is_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _persisted_run(monkeypatch, _BUY_AND_HOLD)
    setup = retest_setup_from_run(run, today=_TODAY)
    assert setup is not None

    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "false")

    assert retest_confirmation_payload(setup, language="en") is not None
