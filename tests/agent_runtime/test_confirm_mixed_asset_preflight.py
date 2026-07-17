from __future__ import annotations

from types import SimpleNamespace

import pytest
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.stages.confirm import confirm_stage
from argus.agent_runtime.state.models import RunState, StrategySummary
from argus.domain.backtesting import coverage
from argus.domain.engine_launch import adapter
from argus.domain.engine_launch.models import LaunchBacktestRequest


@pytest.mark.parametrize(
    ("strategy_type", "cadence", "asset_class"),
    [
        ("buy_and_hold", None, None),
        ("dca_accumulation", "weekly", None),
        ("buy_and_hold", None, "equity"),
        ("dca_accumulation", "weekly", "equity"),
    ],
)
def test_confirm_rejects_mixed_assets_before_coverage_fetch(
    monkeypatch: pytest.MonkeyPatch,
    strategy_type: str,
    cadence: str | None,
    asset_class: str | None,
) -> None:
    coverage_calls: list[dict[str, object]] = []

    def prepare_market_data(config: dict[str, object]) -> None:
        coverage_calls.append(config)
        raise AssertionError("coverage preflight ran before same-asset validation")

    def classify_symbol(symbol: str) -> SimpleNamespace:
        return SimpleNamespace(
            symbol=symbol,
            asset_class="crypto" if symbol == "BTC" else "equity",
        )

    monkeypatch.setattr(coverage, "prepare_market_data", prepare_market_data)
    monkeypatch.setattr(adapter, "classify_symbol", classify_symbol)

    state = RunState.new(
        current_user_message="Test AAPL and BTC together.",
        recent_thread_history=[],
    )
    state.candidate_strategy_draft = StrategySummary(
        strategy_type=strategy_type,
        strategy_thesis="Test a mixed AAPL and BTC basket.",
        asset_universe=["AAPL", "BTC"],
        asset_class=asset_class,
        capital_amount=1_000,
        cadence=cadence,
        date_range={"start": "2024-01-01", "end": "2024-01-05"},
    )

    result = confirm_stage(
        state=state,
        contract=build_default_capability_contract(),
    )

    assert result.outcome == "needs_clarification"
    assert coverage_calls == []
    constraints = result.patch["optional_parameter_status"]["unsupported_constraints"]
    assert constraints[-1]["raw_value"] == "asset_class_conflict"
    assert "confirmation_payload" not in result.patch
    assert "coverage_recovery" not in result.patch["optional_parameter_status"]


def test_confirm_preserves_idea_when_asset_resolution_is_transiently_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coverage_calls: list[dict[str, object]] = []

    def prepare_market_data(config: dict[str, object]) -> None:
        coverage_calls.append(config)
        raise AssertionError("coverage preflight ran after resolution failure")

    def classify_symbol(_: str) -> SimpleNamespace:
        raise ValueError("asset_universe_unavailable")

    monkeypatch.setattr(coverage, "prepare_market_data", prepare_market_data)
    monkeypatch.setattr(adapter, "classify_symbol", classify_symbol)

    state = RunState.new(
        current_user_message="Test an AAPL buy and hold.",
        recent_thread_history=[],
    )
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL.",
        asset_universe=["AAPL"],
        asset_class="equity",
        capital_amount=1_000,
        date_range={"start": "2024-01-01", "end": "2024-01-05"},
    )

    result = confirm_stage(
        state=state,
        contract=build_default_capability_contract(),
    )

    assert result.outcome == "needs_clarification"
    assert coverage_calls == []
    recovery = result.patch["optional_parameter_status"]["coverage_recovery"]
    assert recovery["code"] == "market_data_unavailable"
    assert recovery["asset_universe"] == ["AAPL"]
    assert "unsupported_constraints" not in result.patch["optional_parameter_status"]
    assert "confirmation_payload" not in result.patch
    assert state.candidate_strategy_draft.asset_universe == ["AAPL"]


def test_symbol_validation_checks_known_assets_after_an_unresolved_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classified_symbols: list[str] = []

    def classify_symbol(symbol: str) -> SimpleNamespace:
        classified_symbols.append(symbol)
        if symbol == "UNKNOWN":
            raise ValueError("invalid_symbol")
        return SimpleNamespace(symbol=symbol, asset_class="crypto")

    monkeypatch.setattr(adapter, "classify_symbol", classify_symbol)

    result = adapter.validate_request_symbols(
        _launch_request(symbols=["UNKNOWN", "BTC"], asset_class="equity")
    )

    assert classified_symbols == ["UNKNOWN", "BTC"]
    assert result.outcome == "conflict"
    assert result.error_code == "asset_class_conflict"


def test_symbol_validation_defers_unresolved_declared_class_assets_to_coverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classified_symbols: list[str] = []

    def classify_symbol(symbol: str) -> SimpleNamespace:
        classified_symbols.append(symbol)
        raise ValueError("invalid_symbol")

    monkeypatch.setattr(adapter, "classify_symbol", classify_symbol)

    result = adapter.validate_request_symbols(
        _launch_request(symbols=["COST", "TGT"], asset_class="equity")
    )

    assert classified_symbols == ["COST", "TGT"]
    assert result.outcome == "resolved"
    assert result.symbols == ("COST", "TGT")
    assert result.asset_class == "equity"


def _launch_request(
    *, symbols: list[str], asset_class: str | None
) -> LaunchBacktestRequest:
    return LaunchBacktestRequest(
        strategy_type="buy_and_hold",
        symbol=symbols[0],
        symbols=symbols,
        asset_class=asset_class,
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-01-05"},
        entry_rule=None,
        exit_rule=None,
        sizing_mode="capital_amount",
        capital_amount=1_000,
        position_size=None,
        cadence=None,
        parameters={},
        risk_rules=[],
        benchmark_symbol="SPY",
    )
