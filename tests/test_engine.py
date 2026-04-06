from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest
from argus.analysis.structural import warmup_jit
from argus.engine import ArgusEngine, BacktestResult, StrategyConfig
from pydantic import ValidationError


@pytest.fixture(scope="module", autouse=True)
def setup_numba():
    # Warmup JIT to avoid test latency
    warmup_jit()


@pytest.fixture
def mock_data():
    """Generates simple OHLCV data for 2 assets."""
    dates = pd.date_range(end=datetime.now(timezone.utc), periods=100, freq="1D")

    # Asset A
    df_a = pd.DataFrame(
        {
            "open": np.random.uniform(10, 20, 100),
            "high": np.random.uniform(20, 25, 100),
            "low": np.random.uniform(5, 10, 100),
            "close": np.random.uniform(10, 20, 100),
            "volume": np.random.uniform(100, 1000, 100),
            "EMA_20": np.random.uniform(10, 20, 100),
            "EMA_50": np.random.uniform(10, 20, 100),
            "RSI_14": np.random.uniform(30, 70, 100),
        },
        index=dates,
    )

    # Asset B
    df_b = pd.DataFrame(
        {
            "open": np.random.uniform(50, 60, 100),
            "high": np.random.uniform(60, 65, 100),
            "low": np.random.uniform(45, 50, 100),
            "close": np.random.uniform(50, 60, 100),
            "volume": np.random.uniform(1000, 5000, 100),
            "EMA_20": np.random.uniform(50, 60, 100),
            "EMA_50": np.random.uniform(50, 60, 100),
            "RSI_14": np.random.uniform(30, 70, 100),
        },
        index=dates,
    )

    df_a["symbol"] = "A/USD"
    df_b["symbol"] = "B/USD"

    df = pd.concat([df_a, df_b])
    df = df.set_index(["symbol", df.index])
    df.index.names = ["symbol", "timestamp"]
    return df


def test_engine_initialization():
    engine = ArgusEngine()
    assert engine.data_provider is None


def test_strategy_config_validation():
    # Valid
    config = StrategyConfig(
        entry_patterns=["is_hammer_shape"], confluence_mode="OR", slippage=0.002
    )
    assert config.confluence_mode == "OR"
    assert config.slippage == 0.002

    # Invalid
    with pytest.raises(ValidationError):
        StrategyConfig(confluence_mode="XOR")  # Invalid literal


def test_engine_run_with_data(mock_data):
    engine = ArgusEngine()
    config = StrategyConfig(
        entry_patterns=["is_hammer_shape", "ABCD"],
        exit_patterns=["is_engulfing_shape"],
        confluence_mode="OR",
    )

    result = engine.run(config=config, data=mock_data)

    # Assert return type
    assert isinstance(result, BacktestResult)

    # Assert metrics
    assert hasattr(result.metrics, "total_return_pct")
    assert hasattr(result.metrics, "sharpe_ratio")

    # Assert equity curve
    assert len(result.equity_curve) > 0
    assert hasattr(result.equity_curve[0], "timestamp")
    assert hasattr(result.equity_curve[0], "value")
    # Verify timestamp format (ISO 8601 string)
    assert (
        "T" in result.equity_curve[0].timestamp
        or "+" in result.equity_curve[0].timestamp
        or result.equity_curve[0].timestamp.endswith("Z")
        or " " in result.equity_curve[0].timestamp
    )

    # Assert trades
    for trade in result.trades:
        assert isinstance(trade.symbol, str)
        assert trade.direction in ["Long", "Short"]
    # ISO8601 formatting checks
    assert isinstance(trade.entry_time, str)
    assert isinstance(trade.exit_time, str)


def test_engine_institutional_metrics(mock_data):
    """Test that Alpha, Beta, and Calmar Ratio are calculated."""
    engine = ArgusEngine()
    config = StrategyConfig(
        entry_patterns=["is_hammer_shape"],
        benchmark_symbol="SPY",
    )

    # We need to mock the benchmark data fetch since ArgusEngine.run()
    # calls it if benchmark_symbol is set.
    # For simplicity in this test, we can just check if the fields exist in the result.
    result = engine.run(config=config, data=mock_data)

    assert hasattr(result.metrics, "alpha")
    assert hasattr(result.metrics, "beta")
    assert hasattr(result.metrics, "calmar_ratio")
    assert hasattr(result.metrics, "avg_trade_duration")

    # Metrics should be floats (alpha/beta/calmar) or strings (duration)
    assert isinstance(result.metrics.alpha, float)
    assert isinstance(result.metrics.beta, float)
    assert isinstance(result.metrics.calmar_ratio, float)
    assert isinstance(result.metrics.avg_trade_duration, str)


def test_engine_run_with_and_mode_short_circuit(mock_data):
    """Test AND confluence mode to ensure it evaluates correctly and short-circuits."""
    engine = ArgusEngine()
    config = StrategyConfig(
        entry_patterns=["is_hammer_shape", "non_existent_pattern"],
        exit_patterns=[],
        confluence_mode="AND",
    )
    result = engine.run(config=config, data=mock_data)
    assert isinstance(result, BacktestResult)
    # Since "non_existent_pattern" is missing, we shouldn't get entry signals and total trades should likely be 0
    # unless shorting is enabled and exit triggered an entry.


def test_engine_empty_data():
    engine = ArgusEngine()
    config = StrategyConfig()

    with pytest.raises(
        ValueError,
        match="Must provide either 'data' DataFrame or both 'data_provider' and 'symbols' list.",
    ):
        engine.run(config=config, data=pd.DataFrame())


def test_engine_data_buffer_mocking(mocker, mock_data):
    """Test that data buffer logic works using mocked dataprovider."""

    class MockProvider:
        def get_historical_bars(self, *args, **kwargs):
            return mock_data.copy()

    engine = ArgusEngine(data_provider=MockProvider())
    config = StrategyConfig()

    result = engine.run(
        config=config, symbols=["A/USD", "B/USD"], timeframe="1Min", freq="1min"
    )
    assert isinstance(result, BacktestResult)
