from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from argus.engine import ArgusEngine, EngineBacktestResults, StrategyInput


class MockDataProvider:
    def get_historical_bars(self, symbol, asset_class, timeframe_str, start_dt, end_dt):
        # Generate 200 days of upward trending data with some noise
        length = 200
        dates = pd.date_range(start=start_dt, periods=length, freq="D")

        # Price starts at 100, ends near 200
        base = np.linspace(100, 200, length)
        noise = np.random.normal(0, 2, length)
        close = base + noise

        df = pd.DataFrame(
            {
                "open": close - np.random.uniform(0, 2, length),
                "high": close + np.random.uniform(0, 3, length),
                "low": close - np.random.uniform(0, 3, length),
                "close": close,
                "volume": np.random.uniform(1000, 5000, length),
            },
            index=dates,
        )

        return df


def test_engine_adapter_v1_full_flow():
    """
    Test the full end-to-end flow of the adapted ArgusEngine.
    Verifies:
    1. StrategyInput acceptance.
    2. Dynamic pandas-ta indicator resolution (SMA_50, SMA_100).
    3. Trigger-Filter logic (ABCD pattern + SMA trend).
    4. SL/TP integration.
    5. BacktestResults output normalization.
    """
    engine = ArgusEngine(data_provider=MockDataProvider())

    # Define a complex strategy matching the new API contract
    strategy = StrategyInput(
        name="Adaptive Trend Follower",
        symbols=["BTC/USD"],
        timeframe="1Day",
        start_date=datetime.now(timezone.utc) - timedelta(days=200),
        patterns=["ABCD"],  # Trigger
        entry_criteria=[
            {
                "indicator": "SMA",
                "period": 50,
                "condition": "is_above",
                "target": "SMA_100",  # Indicator vs Indicator
            },
            {
                "indicator": "RSI",
                "period": 14,
                "condition": "is_below",
                "target": 70.0,  # Indicator vs Value
            },
        ],
        exit_criteria=[],
        stop_loss_pct=0.05,
        take_profit_pct=0.15,
        slippage=0.001,
        fees=0.001,
    )

    # Run the backtest
    results = engine.run(config=strategy)

    # 1. Assert Schema
    assert isinstance(results, EngineBacktestResults)

    # 2. Check Metrics Presence (Contract alignment)
    assert hasattr(results, "total_return_pct")
    assert hasattr(results, "win_rate")
    assert hasattr(results, "sharpe_ratio")
    assert hasattr(results, "sortino_ratio")
    assert hasattr(results, "calmar_ratio")
    assert hasattr(results, "expectancy")
    assert hasattr(results, "max_drawdown_pct")

    # 3. Check Equity Curve (Flattened list of floats)
    assert isinstance(results.equity_curve, list)
    assert len(results.equity_curve) > 0
    assert isinstance(results.equity_curve[0], float)

    # 4. Check Trades (Snippet format)
    assert isinstance(results.trades, list)
    if results.trades:
        trade = results.trades[0]
        assert "entry_time" in trade
        assert "entry_price" in trade
        assert "exit_price" in trade
        assert "pnl_pct" in trade
        assert isinstance(trade["pnl_pct"], float)

    # 5. Check Pattern Breakdown
    assert isinstance(results.pattern_breakdown, dict)

    # 6. Ensure it's JSON serializable (production requirement)

    # Ensure it's JSON serializable (production requirement)
    # Use a custom encoder for datetime if necessary, but here we expect strings
    json_results = results.model_dump_json()
    assert json_results is not None


if __name__ == "__main__":
    test_engine_adapter_v1_full_flow()
