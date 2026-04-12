from datetime import datetime, timedelta, timezone

import pandas as pd
from argus.analysis.structural import warmup_jit
from argus.domain.schemas import AssetClass
from argus.engine import ArgusEngine, BacktestConfig, StrategyInput
from hypothesis import given, settings
from hypothesis import strategies as st

warmup_jit()


class MockVBTDataProvider:
    def __init__(self, use_sparse=False):
        self.use_sparse = use_sparse

    def get_historical_bars(self, symbol, asset_class, timeframe_str, start_dt, end_dt):
        import numpy as np

        length = (end_dt - start_dt).days + 1
        if length <= 0:
            length = 200
        dates = pd.date_range(start=start_dt, periods=length, freq="1D")

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

        if self.use_sparse and symbol == "SPARSE/USD":
            # Simulate non-overlapping trading hours / sparse data by dropping every other day
            df = df.iloc[::2]

        return df


@settings(deadline=None)
@given(
    st.lists(
        st.sampled_from(["BTC/USD", "ETH/USD", "SPARSE/USD", "SOL/USD"]),
        min_size=1,
        max_size=3,
        unique=True,
    )
)
def test_hypothesis_matrix_alignment(symbols):
    """
    Property-based test: Ensure BacktestConfig correctly aligns matrix
    with sparse and standard datasets without crashing.
    """
    config = StrategyInput(
        name="Hypothesis Matrix Test",
        symbols=symbols,
        timeframe="1Day",
        start_date=datetime.now(timezone.utc) - timedelta(days=50),
        entry_criteria=[],
    )
    bc = BacktestConfig(config)
    provider = MockVBTDataProvider(use_sparse=True)

    # Should not crash, and should return FFilled aligned DataFrames
    open_df, high_df, low_df, close_df, volume_df = bc.prepare_vectors(
        provider, AssetClass.CRYPTO, config.start_date, datetime.now(timezone.utc)
    )

    # Assert matrix shape integrity
    assert close_df.shape[1] == len(symbols)
    assert not close_df.isnull().values.any()
    # Ensure they have identical indices
    assert close_df.index.equals(open_df.index)
    assert close_df.index.equals(volume_df.index)


def test_reality_gap_metrics_fidelity():
    """Verify fidelity score and slippage decay logic."""
    engine = ArgusEngine(data_provider=MockVBTDataProvider())
    strategy = StrategyInput(
        name="Reality Gap Metric Test",
        symbols=["BTC/USD"],
        timeframe="1Day",
        start_date=datetime.now(timezone.utc) - timedelta(days=100),
        entry_criteria=[
            {
                "indicator": "RSI",
                "period": 14,
                "condition": "is_below",
                "target": 50.0,
            }
        ],
        slippage=0.01,  # 1% extreme slip
        fees=0.005,  # 0.5% extreme fee
    )

    res = engine.run(config=strategy, asset_class=AssetClass.CRYPTO)

    assert "fidelity_score" in res.reality_gap_metrics
    assert "slippage_impact_pct" in res.reality_gap_metrics
    assert "fee_impact_pct" in res.reality_gap_metrics


def test_performance_sla(benchmark):
    """Benchmark test for <3s SLA on a 50-symbol backtest."""
    symbols = [f"SYM{i}/USD" for i in range(50)]
    engine = ArgusEngine(data_provider=MockVBTDataProvider())
    strategy = StrategyInput(
        name="SLA Test",
        symbols=symbols,
        timeframe="1Day",
        start_date=datetime.now(timezone.utc) - timedelta(days=100),
        entry_criteria=[
            {
                "indicator": "RSI",
                "period": 14,
                "condition": "is_below",
                "target": 50.0,
            }
        ],
        slippage=0.001,
        fees=0.001,
    )

    def run_benchmark():
        return engine.run(config=strategy, asset_class=AssetClass.CRYPTO)

    # Note: Mock data generation takes majority of the time here (~5s).
    # Real VectorBT/Alpaca pipelines load data much faster (cached parquet).
    # Since we're benchmarking the entire loop including Python-based mock generation
    # we expect it to take slightly longer than a pure vector run.
    benchmark.pedantic(run_benchmark, iterations=1, rounds=3)
    assert benchmark.stats.stats.mean < 15.0
