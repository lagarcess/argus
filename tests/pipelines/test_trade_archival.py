from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from crypto_signals.pipelines.trade_archival import TradeArchivalPipeline


@pytest.fixture
def mock_alpaca():
    return MagicMock()


@pytest.fixture
def mock_firestore():
    return MagicMock()


@pytest.fixture
def mock_market_provider():
    return MagicMock()


@pytest.fixture
def pipeline(mock_alpaca, mock_firestore, mock_market_provider):
    with (
        patch(
            "crypto_signals.pipelines.trade_archival.get_trading_client",
            return_value=mock_alpaca,
        ),
        patch(
            "crypto_signals.pipelines.trade_archival.firestore.Client",
            return_value=mock_firestore,
        ),
        patch("crypto_signals.pipelines.base.get_settings") as mock_get_settings,
        patch(
            "crypto_signals.pipelines.trade_archival.MarketDataProvider",
            return_value=mock_market_provider,
        ),
        # Patch BigQuery client in the base class to prevent credentials error
        patch("crypto_signals.pipelines.base.bigquery.Client") as mock_bq,
    ):
        mock_get_settings.return_value.GOOGLE_CLOUD_PROJECT = "test-project"
        mock_get_settings.return_value.ENVIRONMENT = "PROD"  # Set default environment

        # Instantiate pipeline with mocked execution engine
        mock_exec = MagicMock()
        mock_exec.get_current_fee_tier.return_value = {
            "taker_fee_pct": 0.25,
            "tier_name": "Tier 0",
        }
        pipe = TradeArchivalPipeline(execution_engine=mock_exec)
        # Inject mocks again to be sure (since __init__ creates them)
        pipe.alpaca = mock_alpaca
        pipe.firestore_client = mock_firestore
        pipe.market_provider = mock_market_provider
        pipe.bq_client = mock_bq.return_value

        return pipe


def test_transform_mfe_long(pipeline, mock_market_provider, mock_alpaca):
    """Test MFE calculation for a Long trade."""
    # Setup Input Data
    entry_time = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    exit_time = datetime(2023, 1, 3, 10, 0, 0, tzinfo=timezone.utc)

    raw_position = {
        "position_id": "trade_1",
        "symbol": "BTC/USD",
        "asset_class": "CRYPTO",
        "entry_time": entry_time.isoformat(),
        "exit_time": exit_time.isoformat(),
        "exit_fill_price": 52000.0,
        "entry_fill_price": 50000.0,  # This is the TARGET price from Signal
        "qty": 1.0,
        "side": "buy",
        "account_id": "acc_1",
        "strategy_id": "strat_1",
    }

    # Mock Alpaca Order - filled_avg_price is the ACTUAL execution price
    mock_order = MagicMock()
    mock_order.filled_avg_price = "50100.0"  # $100 slippage from target
    mock_order.filled_qty = "1.0"
    mock_order.side = "buy"
    mock_order.id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"  # Mock UUID
    mock_alpaca.get_order_by_client_id.return_value = mock_order

    # Mock Market Data (3 days)
    # Day 1: High 51000
    # Day 2: High 55000 (MFE trigger)
    # Day 3: High 52000
    dates = pd.date_range("2023-01-01", periods=3, freq="D", tz="UTC")
    df = pd.DataFrame(
        {
            "high": [51000.0, 55000.0, 52000.0],
            "low": [49000.0, 50000.0, 51000.0],
            "close": [50500.0, 54000.0, 52000.0],
            "open": [50000.0, 50500.0, 54000.0],
            "volume": [100.0, 200.0, 150.0],
        },
        index=dates,
    )
    mock_market_provider.get_daily_bars.return_value = df

    # Execute
    transformed = pipeline.transform([raw_position])

    # Verify
    assert len(transformed) == 1
    trade = transformed[0]
    assert trade["max_favorable_excursion"] == 4900.0  # 55000 - 50100 (actual entry)
    # Verify pnl_usd is correctly calculated and rounded
    # PnL = (exit_price - entry_price) * qty = (52000 - 50100) * 1.0 = 1900.0
    assert trade["pnl_usd"] == 1644.75
    # Verify pnl_pct is also present
    assert "pnl_pct" in trade

    # NEW ASSERTIONS for Schema Evolution
    # Verify target_entry_price is from Firestore (original Signal price)
    assert trade["target_entry_price"] == 50000.0
    # Verify alpaca_order_id is the broker's UUID
    assert trade["alpaca_order_id"] == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    # Verify slippage calculation: ((50100 - 50000) / 50000) * 100 = 0.2%
    assert trade["slippage_pct"] == 0.2


def test_transform_mfe_short(pipeline, mock_market_provider, mock_alpaca):
    """Test MFE calculation for a Short trade."""
    entry_time = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    exit_time = datetime(2023, 1, 3, 10, 0, 0, tzinfo=timezone.utc)

    raw_position = {
        "position_id": "trade_2",
        "symbol": "BTC/USD",
        "asset_class": "CRYPTO",
        "entry_time": entry_time.isoformat(),
        "exit_time": exit_time.isoformat(),
        "exit_fill_price": 48000.0,
        "entry_fill_price": 50000.0,  # Target price from Signal
        "qty": 1.0,
        "side": "sell",
        "account_id": "acc_1",
        "strategy_id": "strat_1",
    }

    # Mock Alpaca Order
    mock_order = MagicMock()
    mock_order.filled_avg_price = "50000.0"  # Actual fill = target (no slippage)
    mock_order.filled_qty = "1.0"
    mock_order.side = "sell"
    mock_order.id = "b2c3d4e5-f6a7-8901-bcde-f23456789012"  # Mock UUID
    mock_alpaca.get_order_by_client_id.return_value = mock_order

    # Mock Market Data
    # Day 1: Low 49000
    # Day 2: Low 45000 (MFE trigger)
    # Day 3: Low 48000
    dates = pd.date_range("2023-01-01", periods=3, freq="D", tz="UTC")
    df = pd.DataFrame(
        {
            "high": [51000.0, 55000.0, 52000.0],
            "low": [49000.0, 45000.0, 48000.0],
            "close": [50500.0, 46000.0, 48000.0],
            "open": [50000.0, 50500.0, 47000.0],
            "volume": [100.0, 200.0, 150.0],
        },
        index=dates,
    )
    mock_market_provider.get_daily_bars.return_value = df

    # Execute
    transformed = pipeline.transform([raw_position])

    # Verify
    assert len(transformed) == 1
    trade = transformed[0]
    assert trade["max_favorable_excursion"] == 5000.0  # 50000 - 45000
    # Verify pnl_usd is correctly calculated for short position
    # Short PnL = (entry_price - exit_price) * qty = (50000 - 48000) * 1.0 = 2000.0
    assert trade["pnl_usd"] == 1755.0
    # Verify pnl_pct is also present
    assert "pnl_pct" in trade

    # NEW ASSERTIONS for Schema Evolution
    assert trade["target_entry_price"] == 50000.0
    assert trade["alpaca_order_id"] == "b2c3d4e5-f6a7-8901-bcde-f23456789012"
    # No slippage: ((50000 - 50000) / 50000) * 100 = 0%
    assert trade["slippage_pct"] == 0.0


def test_transform_short_slippage(pipeline, mock_market_provider, mock_alpaca):
    """Test slippage calculation for a Short trade with UNFAVORABLE slippage.

    For shorts, filling LOWER than target is unfavorable (sold at worse price).
    Formula: (target - actual) / target = (50000 - 49900) / 50000 = +0.2%
    """
    entry_time = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    exit_time = datetime(2023, 1, 3, 10, 0, 0, tzinfo=timezone.utc)

    raw_position = {
        "position_id": "trade_short_slip",
        "symbol": "BTC/USD",
        "asset_class": "CRYPTO",
        "entry_time": entry_time.isoformat(),
        "exit_time": exit_time.isoformat(),
        "exit_fill_price": 48000.0,
        "entry_fill_price": 50000.0,  # Target price from Signal
        "qty": 1.0,
        "side": "sell",
        "account_id": "acc_1",
        "strategy_id": "strat_1",
    }

    # Mock Alpaca Order - filled LOWER than target (unfavorable for short)
    mock_order = MagicMock()
    mock_order.filled_avg_price = "49900.0"  # Sold at $49,900 (below target $50,000)
    mock_order.filled_qty = "1.0"
    mock_order.side = "sell"
    mock_order.id = "short-slip-uuid-123"
    mock_alpaca.get_order_by_client_id.return_value = mock_order

    # Mock Market Data
    dates = pd.date_range("2023-01-01", periods=3, freq="D", tz="UTC")
    df = pd.DataFrame(
        {
            "high": [51000.0, 55000.0, 52000.0],
            "low": [49000.0, 45000.0, 48000.0],
            "close": [50500.0, 46000.0, 48000.0],
            "open": [50000.0, 50500.0, 47000.0],
            "volume": [100.0, 200.0, 150.0],
        },
        index=dates,
    )
    mock_market_provider.get_daily_bars.return_value = df

    # Execute
    transformed = pipeline.transform([raw_position])

    # Verify
    assert len(transformed) == 1
    trade = transformed[0]

    # Verify target and actual entry
    assert trade["target_entry_price"] == 50000.0
    assert trade["entry_price"] == 49900.0  # Actual fill from Alpaca

    # Verify slippage calculation: (50000 - 49900) / 50000 * 100 = +0.2%
    # POSITIVE slippage = UNFAVORABLE for SHORT (sold at worse price)
    assert trade["slippage_pct"] == 0.2

    # Verify PnL is based on ACTUAL fill, not target
    # Short PnL = (entry - exit) * qty = (49900 - 48000) * 1.0 = 1900.0
    assert trade["pnl_usd"] == 1655.25

    # Verify MFE based on actual entry
    # MFE = actual_entry - lowest = 49900 - 45000 = 4900
    assert trade["max_favorable_excursion"] == 4900.0


def test_transform_short_unfavorable_slippage(
    pipeline, mock_market_provider, mock_alpaca
):
    """Test slippage calculation for a Short trade with FAVORABLE slippage.

    For shorts, filling HIGHER than target is favorable (sold at better price).
    Formula: (target - actual) / target = (50000 - 50100) / 50000 = -0.2%
    """
    entry_time = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    exit_time = datetime(2023, 1, 3, 10, 0, 0, tzinfo=timezone.utc)

    raw_position = {
        "position_id": "trade_short_unfav_slip",
        "symbol": "BTC/USD",
        "asset_class": "CRYPTO",
        "entry_time": entry_time.isoformat(),
        "exit_time": exit_time.isoformat(),
        "exit_fill_price": 48000.0,
        "entry_fill_price": 50000.0,  # Target price from Signal
        "qty": 1.0,
        "side": "sell",
        "account_id": "acc_1",
        "strategy_id": "strat_1",
    }

    # Mock Alpaca Order - filled HIGHER than target (favorable for short)
    mock_order = MagicMock()
    mock_order.filled_avg_price = "50100.0"  # Sold at $50,100 (above target $50,000)
    mock_order.filled_qty = "1.0"
    mock_order.side = "sell"
    mock_order.id = "short-unfav-slip-uuid-456"
    mock_alpaca.get_order_by_client_id.return_value = mock_order

    # Mock Market Data
    dates = pd.date_range("2023-01-01", periods=3, freq="D", tz="UTC")
    df = pd.DataFrame(
        {
            "high": [51000.0, 55000.0, 52000.0],
            "low": [49000.0, 45000.0, 48000.0],
            "close": [50500.0, 46000.0, 48000.0],
            "open": [50000.0, 50500.0, 47000.0],
            "volume": [100.0, 200.0, 150.0],
        },
        index=dates,
    )
    mock_market_provider.get_daily_bars.return_value = df

    # Execute
    transformed = pipeline.transform([raw_position])

    # Verify
    assert len(transformed) == 1
    trade = transformed[0]

    # Verify target and actual entry
    assert trade["target_entry_price"] == 50000.0
    assert trade["entry_price"] == 50100.0  # Actual fill from Alpaca

    # Verify slippage calculation: (50000 - 50100) / 50000 * 100 = -0.2%
    # NEGATIVE slippage = FAVORABLE for SHORT (sold at better price)
    assert trade["slippage_pct"] == -0.2

    # Verify PnL is based on ACTUAL fill, not target
    # Short PnL = (entry - exit) * qty = (50100 - 48000) * 1.0 = 2100.0
    assert trade["pnl_usd"] == 1854.75


def test_transform_caches_market_data_per_symbol(
    pipeline, mock_market_provider, mock_alpaca
):
    """Test that multiple trades on the same symbol only fetch data once."""
    entry_time = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    exit_time = datetime(2023, 1, 3, 10, 0, 0, tzinfo=timezone.utc)

    # Create 3 trades for BTC/USD (same symbol)
    btc_trades = [
        {
            "position_id": f"btc_trade_{i}",
            "symbol": "BTC/USD",
            "asset_class": "CRYPTO",
            "entry_time": entry_time.isoformat(),
            "exit_time": exit_time.isoformat(),
            "exit_fill_price": 52000.0,
            "qty": 1.0,
            "side": "buy",
            "account_id": "acc_1",
            "strategy_id": "strat_1",
        }
        for i in range(3)
    ]

    # Create 2 trades for ETH/USD (different symbol)
    eth_trades = [
        {
            "position_id": f"eth_trade_{i}",
            "symbol": "ETH/USD",
            "asset_class": "CRYPTO",
            "entry_time": entry_time.isoformat(),
            "exit_time": exit_time.isoformat(),
            "exit_fill_price": 2000.0,
            "qty": 1.0,
            "side": "buy",
            "account_id": "acc_1",
            "strategy_id": "strat_1",
        }
        for i in range(2)
    ]

    # Combine all trades (5 total: 3 BTC + 2 ETH)
    all_trades = btc_trades + eth_trades

    # Mock Alpaca Order
    mock_order = MagicMock()
    mock_order.filled_avg_price = "50000.0"
    mock_order.filled_qty = "1.0"
    mock_order.side = "buy"
    mock_order.id = "cache-test-order-uuid"
    mock_alpaca.get_order_by_client_id.return_value = mock_order

    # Mock Market Data
    dates = pd.date_range("2023-01-01", periods=3, freq="D", tz="UTC")
    df = pd.DataFrame(
        {
            "high": [51000.0, 55000.0, 52000.0],
            "low": [49000.0, 50000.0, 51000.0],
            "close": [50500.0, 54000.0, 52000.0],
            "open": [50000.0, 50500.0, 54000.0],
            "volume": [100.0, 200.0, 150.0],
        },
        index=dates,
    )
    mock_market_provider.get_daily_bars.return_value = df

    # Execute - process 5 trades
    transformed = pipeline.transform(all_trades)

    # Verify all 5 trades were processed
    assert len(transformed) == 5

    # CRITICAL ASSERTION: Verify get_daily_bars was called only 2 times
    # (once for BTC/USD, once for ETH/USD) - NOT 5 times!
    assert mock_market_provider.get_daily_bars.call_count == 2

    # Verify the calls were for the expected symbols
    calls = mock_market_provider.get_daily_bars.call_args_list
    called_symbols = [call.kwargs.get("symbol") for call in calls]
    assert "BTC/USD" in called_symbols
    assert "ETH/USD" in called_symbols


def test_transform_propagates_exit_order_id(pipeline, mock_market_provider, mock_alpaca):
    """Test that exit_order_id is propagated from Firestore position to BigQuery trade."""
    entry_time = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    exit_time = datetime(2023, 1, 3, 10, 0, 0, tzinfo=timezone.utc)

    # Position with exit_order_id (Issue #139 field)
    raw_position = {
        "position_id": "trade_exit_order_test",
        "symbol": "BTC/USD",
        "asset_class": "CRYPTO",
        "entry_time": entry_time.isoformat(),
        "exit_time": exit_time.isoformat(),
        "exit_fill_price": 52000.0,
        "entry_fill_price": 50000.0,
        "qty": 1.0,
        "side": "buy",
        "account_id": "acc_1",
        "strategy_id": "strat_1",
        "exit_order_id": "exit-order-uuid-abc123",  # NEW FIELD
    }

    # Mock Alpaca Order
    mock_order = MagicMock()
    mock_order.filled_avg_price = "50000.0"
    mock_order.filled_qty = "1.0"
    mock_order.side = "buy"
    mock_order.id = "entry-order-uuid-xyz789"
    mock_alpaca.get_order_by_client_id.return_value = mock_order

    # Mock Market Data
    dates = pd.date_range("2023-01-01", periods=3, freq="D", tz="UTC")
    df = pd.DataFrame(
        {
            "high": [51000.0, 55000.0, 52000.0],
            "low": [49000.0, 50000.0, 51000.0],
            "close": [50500.0, 54000.0, 52000.0],
            "open": [50000.0, 50500.0, 54000.0],
            "volume": [100.0, 200.0, 150.0],
        },
        index=dates,
    )
    mock_market_provider.get_daily_bars.return_value = df

    # Execute
    transformed = pipeline.transform([raw_position])

    # Verify
    assert len(transformed) == 1
    trade = transformed[0]

    # CRITICAL: Verify exit_order_id is propagated
    assert "exit_order_id" in trade
    assert trade["exit_order_id"] == "exit-order-uuid-abc123"

    # Also verify alpaca_order_id (entry order) is still present
    assert trade["alpaca_order_id"] == "entry-order-uuid-xyz789"


def test_transform_exit_order_id_defaults_to_none(
    pipeline, mock_market_provider, mock_alpaca
):
    """Test that exit_order_id defaults to None when not present in position."""
    entry_time = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    exit_time = datetime(2023, 1, 3, 10, 0, 0, tzinfo=timezone.utc)

    # Position WITHOUT exit_order_id (legacy position)
    raw_position = {
        "position_id": "trade_no_exit_order",
        "symbol": "BTC/USD",
        "asset_class": "CRYPTO",
        "entry_time": entry_time.isoformat(),
        "exit_time": exit_time.isoformat(),
        "exit_fill_price": 52000.0,
        "entry_fill_price": 50000.0,
        "qty": 1.0,
        "side": "buy",
        "account_id": "acc_1",
        "strategy_id": "strat_1",
        # exit_order_id NOT present (legacy)
    }

    # Mock Alpaca Order
    mock_order = MagicMock()
    mock_order.filled_avg_price = "50000.0"
    mock_order.filled_qty = "1.0"
    mock_order.side = "buy"
    mock_order.id = "entry-order-uuid-legacy"
    mock_alpaca.get_order_by_client_id.return_value = mock_order

    # Mock Market Data
    dates = pd.date_range("2023-01-01", periods=3, freq="D", tz="UTC")
    df = pd.DataFrame(
        {
            "high": [51000.0, 55000.0, 52000.0],
            "low": [49000.0, 50000.0, 51000.0],
            "close": [50500.0, 54000.0, 52000.0],
            "open": [50000.0, 50500.0, 54000.0],
            "volume": [100.0, 200.0, 150.0],
        },
        index=dates,
    )
    mock_market_provider.get_daily_bars.return_value = df

    # Execute
    transformed = pipeline.transform([raw_position])

    # Verify
    assert len(transformed) == 1
    trade = transformed[0]

    # CRITICAL: Verify exit_order_id defaults to None for legacy positions
    assert "exit_order_id" in trade
    assert trade["exit_order_id"] is None
