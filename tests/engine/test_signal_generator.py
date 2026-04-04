"""Unit tests for the SignalGenerator module."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from crypto_signals.domain.schemas import (
    AssetClass,
    ExitReason,
    OrderSide,
    SignalStatus,
    StrategyConfig,
)
from crypto_signals.engine.signal_generator import SignalGenerator

from tests.factories import SignalFactory


@pytest.fixture
def mock_market_provider():
    """Fixture for mocking the MarketDataProvider."""
    return MagicMock()


@pytest.fixture
def mock_indicators():
    """Fixture for mocking TechnicalIndicators."""
    mock = MagicMock()
    # Mock add_all_indicators to return the DataFrame unchanged
    mock.add_all_indicators.side_effect = lambda df: df
    return mock


@pytest.fixture
def mock_analyzer_cls():
    """Fixture for mocking the PatternAnalyzer class."""
    return MagicMock()


@pytest.fixture
def mock_repository():
    """Fixture for mocking SignalRepository."""
    mock = MagicMock()
    mock.get_most_recent_exit.return_value = None
    return mock


@pytest.fixture
def signal_generator(
    mock_market_provider, mock_indicators, mock_analyzer_cls, mock_repository
):
    """Fixture for creating a SignalGenerator instance with mocks."""
    with patch("crypto_signals.repository.firestore.PositionRepository") as mock_pos_repo:
        mock_pos_repo_instance = mock_pos_repo.return_value
        mock_pos_repo_instance.get_open_position_by_symbol.return_value = None

        return SignalGenerator(
            market_provider=mock_market_provider,
            indicators=mock_indicators,
            pattern_analyzer_cls=mock_analyzer_cls,
            signal_repo=mock_repository,
        )


@pytest.fixture
def chandelier_exit_df(mock_analyzer_cls):
    """Single-row OHLCV + indicators DataFrame + mock analyzer setup for chandelier exit tests."""
    df = pd.DataFrame(
        {
            "open": [110.0],
            "high": [115.0],
            "low": [105.0],
            "close": [108.0],
            "volume": [1000.0],
            "bearish_engulfing": [False],
            "RSI_14": [50.0],
            "ADX_14": [20.0],
            "CHANDELIER_EXIT_LONG": [112.0],
        },
        index=[pd.Timestamp("2023-01-02")],
    )

    mock_analyzer_instance = MagicMock()
    mock_analyzer_cls.return_value = mock_analyzer_instance
    mock_analyzer_instance.check_patterns.return_value = df

    return df


@pytest.mark.parametrize(
    "symbol,asset_class,pattern_flags,expected_pattern,expected_stop",
    [
        pytest.param(
            "BTC/USD",
            AssetClass.CRYPTO,
            {"bullish_engulfing": True, "bullish_hammer": False},
            "BULLISH_ENGULFING",
            100.0 * 0.99,
            id="bullish_engulfing_crypto",
        ),
        pytest.param(
            "AAPL",
            AssetClass.EQUITY,
            {"bullish_engulfing": False, "bullish_hammer": True},
            "BULLISH_HAMMER",
            90.0 * 0.99,
            id="bullish_hammer_equity",
        ),
    ],
)
def test_generate_signal_patterns(
    signal_generator,
    mock_market_provider,
    mock_analyzer_cls,
    symbol,
    asset_class,
    pattern_flags,
    expected_pattern,
    expected_stop,
):
    """Test signal generation for various patterns."""
    # Arrange
    today = date(2023, 1, 1)
    df = pd.DataFrame(
        {
            "open": [100.0],
            "high": [110.0],
            "low": [90.0],
            "close": [105.0],
            "volume": [1000.0],
        },
        index=[pd.Timestamp(today)],
    )
    mock_market_provider.get_daily_bars.return_value = df

    mock_analyzer_instance = MagicMock()
    mock_analyzer_cls.return_value = mock_analyzer_instance

    result_df = df.copy()
    for pattern, val in pattern_flags.items():
        result_df[pattern] = val
    mock_analyzer_instance.check_patterns.return_value = result_df

    # Act
    signal = signal_generator.generate_signals(symbol, asset_class)

    # Assert
    assert signal is not None
    assert signal.symbol == symbol
    assert signal.pattern_name == expected_pattern
    assert signal.suggested_stop == expected_stop
    assert signal.asset_class == asset_class
    assert signal.entry_price == 105.0


def test_generate_signal_priority(
    signal_generator, mock_market_provider, mock_analyzer_cls
):
    """Test that Bullish Engulfing is prioritized over Bullish Hammer."""
    # Arrange
    # BOTH patterns are True
    df = pd.DataFrame(
        {
            "open": [100.0],
            "high": [110.0],
            "low": [90.0],
            "close": [100.0],
            "volume": [1000.0],
        },
        index=[pd.Timestamp("2023-01-01")],
    )
    mock_market_provider.get_daily_bars.return_value = df

    mock_analyzer_instance = MagicMock()
    mock_analyzer_cls.return_value = mock_analyzer_instance

    result_df = df.copy()
    result_df["bullish_engulfing"] = True
    result_df["bullish_hammer"] = True
    mock_analyzer_instance.check_patterns.return_value = result_df

    # Act
    signal = signal_generator.generate_signals("BTC/USD", AssetClass.CRYPTO)

    # Assert
    # Engulfing should win
    assert signal is not None, "signal should not be None"
    assert (
        signal.pattern_name == "BULLISH_ENGULFING"
    ), 'Expected signal.pattern_name == "BULLISH_ENGULFING"'


def test_generate_signal_none(signal_generator, mock_market_provider, mock_analyzer_cls):
    """Test that None is returned when no patterns are detected."""
    # Arrange
    # NO patterns
    df = pd.DataFrame(
        {"close": [100.0], "low": [90.0]}, index=[pd.Timestamp("2023-01-01")]
    )
    mock_market_provider.get_daily_bars.return_value = df

    mock_analyzer_instance = MagicMock()
    mock_analyzer_cls.return_value = mock_analyzer_instance

    result_df = df.copy()
    result_df["bullish_engulfing"] = False
    result_df["bullish_hammer"] = False
    mock_analyzer_instance.check_patterns.return_value = result_df

    # Act
    signal = signal_generator.generate_signals("BTC/USD", AssetClass.CRYPTO)

    # Assert
    assert signal is None, f"signal should be None, got {signal}"


def test_generate_signal_empty_data(signal_generator, mock_market_provider):
    """Test that None is returned when the market provider returns empty data."""
    # Arrange
    # Empty DataFrame
    mock_market_provider.get_daily_bars.return_value = pd.DataFrame()

    # Act
    signal = signal_generator.generate_signals("BTC/USD", AssetClass.CRYPTO)

    # Assert
    assert signal is None, f"signal should be None, got {signal}"


def test_check_exits_profit_hit_tp1_scaling(
    signal_generator, mock_market_provider, mock_analyzer_cls
):
    """Test detecting a Take Profit 1 hit (Scaling)."""
    # Arrange
    # Arrange Active Signal
    signal = SignalFactory.build(
        signal_id="sig_1",
        ds=date(2023, 1, 1),
        strategy_id="strat_1",
        symbol="BTC/USD",
        entry_price=100.0,
        pattern_name="TEST",
        suggested_stop=90.0,
        status=SignalStatus.WAITING,
        take_profit_1=110.0,
        take_profit_2=120.0,
        invalidation_price=90.0,
    )

    # Arrange Market Data (Hit TP1)
    df = pd.DataFrame(
        {
            "open": [100.0],
            "high": [115.0],  # Hit 110
            "low": [95.0],
            "close": [105.0],
            "volume": [1000.0],
            "bearish_engulfing": [False],
            "RSI_14": [50.0],
            "ADX_14": [20.0],
        },
        index=[pd.Timestamp("2023-01-02")],
    )
    # Passed via dataframe argument, so provider shouldn't be called if logic is correct

    mock_analyzer_instance = MagicMock()
    mock_analyzer_cls.return_value = mock_analyzer_instance
    mock_analyzer_instance.check_patterns.return_value = df

    # Act
    exited = signal_generator.check_exits(
        [signal], "BTC/USD", AssetClass.CRYPTO, dataframe=df
    )

    # Assert
    assert len(exited) == 1, f"Expected len(exited) == 1, got {len(exited)}"
    assert (
        exited[0].status == SignalStatus.TP1_HIT
    ), f"Expected exited[0].status == SignalStatus.TP1_HIT, got {exited[0].status}"
    # Stop should be moved to Breakeven
    assert (
        exited[0].suggested_stop == 100.0
    ), f"Expected exited[0].suggested_stop == 100.0, got {exited[0].suggested_stop}"
    assert (
        exited[0].exit_reason == ExitReason.TP1
    ), f"Expected exited[0].exit_reason == ExitReason.TP1, got {exited[0].exit_reason}"

    # Ensure provider was NOT called because we passed dataframe
    mock_market_provider.get_daily_bars.assert_not_called()


def test_check_exits_invalidation(
    signal_generator, mock_market_provider, mock_analyzer_cls
):
    """Test detecting a Structural Invalidation."""
    # Arrange
    # Arrange Active Signal
    signal = MagicMock()
    signal.take_profit_1 = 120.0
    signal.take_profit_2 = None
    signal.invalidation_price = 95.0
    signal.status = SignalStatus.WAITING
    signal.valid_until = datetime.now(timezone.utc) + timedelta(hours=24)
    signal.created_at = None  # Skip cooldown gate in check_exits

    # Arrange Market Data (Close below invalidation)
    df = pd.DataFrame(
        {
            "open": [100.0],
            "high": [102.0],
            "low": [90.0],
            "close": [92.0],  # Below 95
            "volume": [1000.0],
            "bearish_engulfing": [False],
            "RSI_14": [50.0],
            "ADX_14": [20.0],
        },
        index=[pd.Timestamp("2023-01-02")],
    )
    mock_market_provider.get_daily_bars.return_value = df

    mock_analyzer_instance = MagicMock()
    mock_analyzer_cls.return_value = mock_analyzer_instance
    mock_analyzer_instance.check_patterns.return_value = df

    # Act
    exited = signal_generator.check_exits([signal], "BTC/USD", AssetClass.CRYPTO)

    # Assert
    assert len(exited) == 1, f"Expected len(exited) == 1, got {len(exited)}"
    assert (
        exited[0].status == SignalStatus.INVALIDATED
    ), f"Expected exited[0].status == SignalStatus.INVALIDATED, got {exited[0].status}"


def test_check_exits_none(signal_generator, mock_market_provider, mock_analyzer_cls):
    """Test no exit triggered."""
    # Arrange
    # Arrange Active Signal
    signal = MagicMock()
    signal.take_profit_1 = 120.0
    signal.take_profit_2 = None
    signal.invalidation_price = 90.0
    signal.status = SignalStatus.WAITING
    signal.valid_until = datetime.now(timezone.utc) + timedelta(hours=24)
    signal.created_at = None  # Skip cooldown gate in check_exits

    # Arrange Market Data (Normal day)
    df = pd.DataFrame(
        {
            "open": [100.0],
            "high": [105.0],
            "low": [98.0],
            "close": [102.0],
            "volume": [1000.0],
            "bearish_engulfing": [False],
            "RSI_14": [50.0],
            "ADX_14": [20.0],
        },
        index=[pd.Timestamp("2023-01-02")],
    )
    mock_market_provider.get_daily_bars.return_value = df

    mock_analyzer_instance = MagicMock()
    mock_analyzer_cls.return_value = mock_analyzer_instance
    mock_analyzer_instance.check_patterns.return_value = df

    # Act
    exited = signal_generator.check_exits([signal], "BTC/USD", AssetClass.CRYPTO)

    # Assert
    assert len(exited) == 0, f"Expected len(exited) == 0, got {len(exited)}"


def test_check_exits_runner_exit(
    signal_generator, mock_market_provider, mock_analyzer_cls
):
    """Test detecting a Runner Exit (Chandelier Exit)."""
    # Arrange
    # Arrange Active Signal (TP2 already hit, now in Runner mode)
    signal = SignalFactory.build(
        signal_id="sig_2",
        ds=date(2023, 1, 1),
        strategy_id="strat_1",
        symbol="BTC/USD",
        entry_price=100.0,
        pattern_name="TEST",
        suggested_stop=110.0,
        status=SignalStatus.TP2_HIT,
        take_profit_1=110.0,
        take_profit_2=120.0,
        invalidation_price=90.0,
    )

    # Arrange Market Data (Close BELOW Chandelier Exit)
    # Price > Entry (Win) but < Chandelier
    df = pd.DataFrame(
        {
            "open": [130.0],
            "high": [135.0],
            "low": [125.0],
            "close": [128.0],
            "volume": [1000.0],
            "bearish_engulfing": [False],
            "RSI_14": [50.0],
            "ADX_14": [20.0],
            "CHANDELIER_EXIT_LONG": [129.0],  # Exit Trigger
        },
        index=[pd.Timestamp("2023-01-02")],
    )

    mock_analyzer_instance = MagicMock()
    mock_analyzer_cls.return_value = mock_analyzer_instance
    mock_analyzer_instance.check_patterns.return_value = df

    # Act
    exited = signal_generator.check_exits(
        [signal], "BTC/USD", AssetClass.CRYPTO, dataframe=df
    )

    # Assert
    assert len(exited) == 1, f"Expected len(exited) == 1, got {len(exited)}"
    assert (
        exited[0].status == SignalStatus.TP3_HIT
    ), f"Expected exited[0].status == SignalStatus.TP3_HIT, got {exited[0].status}"
    assert (
        exited[0].exit_reason == ExitReason.TP_HIT
    ), f"Expected exited[0].exit_reason == ExitReason.TP_HIT, got {exited[0].exit_reason}"

    # Arrange
    signal.take_profit_1 = 104.0
    signal.take_profit_2 = 110.0
    signal.entry_price = 100.0
    signal.status = SignalStatus.WAITING
    signal.valid_until = datetime.now(timezone.utc) + timedelta(hours=24)

    # Arrange Market Data (Hit TP1)
    df = pd.DataFrame(
        {
            "open": [100.0],
            "high": [105.0],  # Hit TP1
            "low": [98.0],
            "close": [102.0],
            "volume": [1000.0],
            "bearish_engulfing": [False],
            "RSI_14": [50.0],
            "ADX_14": [20.0],
        },
        index=[pd.Timestamp("2023-01-02")],
    )

    mock_market_provider.get_daily_bars.return_value = df
    mock_analyzer_instance = MagicMock()
    mock_analyzer_cls.return_value = mock_analyzer_instance
    mock_analyzer_instance.check_patterns.return_value = df

    # Act
    exited = signal_generator.check_exits(
        [signal], "BTC/USD", AssetClass.CRYPTO, dataframe=df
    )

    # Assert
    assert len(exited) == 1, f"Expected len(exited) == 1, got {len(exited)}"
    assert (
        exited[0].status == SignalStatus.TP1_HIT
    ), f"Expected exited[0].status == SignalStatus.TP1_HIT, got {exited[0].status}"
    assert (
        exited[0].suggested_stop == 100.0
    ), f"Breakeven: expected 100.0, got {exited[0].suggested_stop}"
    assert (
        exited[0].exit_reason == ExitReason.TP1
    ), f"Expected exited[0].exit_reason == ExitReason.TP1, got {exited[0].exit_reason}"


def test_check_exits_no_waiting_tp3_jump(
    signal_generator, mock_market_provider, chandelier_exit_df
):
    """Verify WAITING signal is NOT marked TP3_HIT when close < chandelier (Issue 123)."""
    # Arrange
    # Arrange Active Signal in WAITING status
    signal = SignalFactory.build(
        signal_id="sig_waiting",
        ds=date(2023, 1, 1),
        strategy_id="strat_1",
        symbol="BTC/USD",
        entry_price=100.0,
        pattern_name="TEST",
        suggested_stop=90.0,
        status=SignalStatus.WAITING,
        take_profit_1=150.0,  # Far away
        take_profit_2=200.0,
        invalidation_price=80.0,
        created_at=None,
    )

    df = chandelier_exit_df

    # Act
    exited = signal_generator.check_exits(
        [signal], "BTC/USD", AssetClass.CRYPTO, dataframe=df
    )

    # Assert
    # Currently BUGGY, it will return TP3_HIT.
    # We want it to be empty (no exit triggered).
    assert len(exited) == 0, f"Expected len(exited) == 0, got {len(exited)}"


@pytest.mark.parametrize(
    "start_status",
    [
        pytest.param(SignalStatus.TP1_HIT, id="tp1_to_tp3"),
        pytest.param(SignalStatus.TP2_HIT, id="tp2_to_tp3"),
    ],
)
def test_check_exits_status_transitions_to_tp3(
    signal_generator, mock_market_provider, chandelier_exit_df, start_status
):
    """Verify TP1_HIT and TP2_HIT signals correctly transition to TP3_HIT (Issue 123)."""
    # Arrange
    # Arrange Active Signal
    signal = SignalFactory.build(
        signal_id="sig_test",
        ds=date(2023, 1, 1),
        strategy_id="strat_1",
        symbol="BTC/USD",
        entry_price=100.0,
        pattern_name="TEST",
        suggested_stop=100.0,
        status=start_status,
        take_profit_1=110.0,
        take_profit_2=120.0,
        invalidation_price=80.0,
        created_at=None,
    )

    df = chandelier_exit_df

    # Act
    exited = signal_generator.check_exits(
        [signal], "BTC/USD", AssetClass.CRYPTO, dataframe=df
    )

    # Assert
    assert len(exited) == 1, f"Expected len(exited) == 1, got {len(exited)}"
    assert (
        exited[0].status == SignalStatus.TP3_HIT
    ), f"Expected exited[0].status == SignalStatus.TP3_HIT, got {exited[0].status}"


@pytest.mark.parametrize(
    "side,chandelier_col,close_price",
    [
        pytest.param(OrderSide.BUY, "CHANDELIER_EXIT_LONG", 108.0, id="long_waiting"),
        pytest.param(OrderSide.SELL, "CHANDELIER_EXIT_SHORT", 102.0, id="short_waiting"),
    ],
)
def test_check_exits_stale_waiting_signal_regression(
    signal_generator,
    mock_market_provider,
    mock_analyzer_cls,
    side,
    chandelier_col,
    close_price,
):
    """Regression: 288h-old WAITING signal does not phantom-trigger TP3 (Issue 123)."""
    now_utc = datetime.now(timezone.utc)
    signal = SignalFactory.build(
        signal_id="sig_stale",
        ds=date(2023, 1, 1),
        strategy_id="strat_1",
        symbol="BTC/USD",
        side=side,
        entry_price=100.0,
        status=SignalStatus.WAITING,
        take_profit_1=150.0 if side == OrderSide.BUY else 50.0,
        take_profit_2=200.0 if side == OrderSide.BUY else 30.0,
        created_at=now_utc - timedelta(hours=288),
    )

    df = pd.DataFrame(
        {
            "open": [close_price],
            "high": [close_price + 2.0],
            "low": [close_price - 2.0],
            "close": [close_price],
            "volume": [1000.0],
            chandelier_col: [112.0 if side == OrderSide.BUY else 98.0],
            "bearish_engulfing": [False],
            "RSI_14": [50.0],
            "ADX_14": [20.0],
        },
        index=[pd.Timestamp("2023-01-02")],
    )

    mock_analyzer_instance = MagicMock()
    mock_analyzer_cls.return_value = mock_analyzer_instance
    mock_analyzer_instance.check_patterns.return_value = df

    # Act
    exited = signal_generator.check_exits(
        [signal], "BTC/USD", AssetClass.CRYPTO, dataframe=df
    )

    # Assert
    assert len(exited) == 0


@pytest.mark.parametrize(
    "side,initial_tp3,chandelier_col,chandelier_val,expected_tp3",
    [
        pytest.param(
            OrderSide.BUY, 115.0, "CHANDELIER_EXIT_LONG", 117.0, 117.0, id="long_trail_up"
        ),
        pytest.param(
            OrderSide.SELL,
            95.0,
            "CHANDELIER_EXIT_SHORT",
            88.0,
            88.0,
            id="short_trail_down",
        ),
    ],
)
def test_check_exits_trail_update(
    signal_generator,
    mock_market_provider,
    mock_analyzer_cls,
    side,
    initial_tp3,
    chandelier_col,
    chandelier_val,
    expected_tp3,
):
    """Test that take_profit_3 is updated when Chandelier Exit moves favorably."""
    signal = SignalFactory.build(
        signal_id="sig_trail",
        ds=date(2023, 1, 1),
        symbol="BTC/USD",
        side=side,
        entry_price=100.0,
        status=SignalStatus.TP1_HIT,
        take_profit_3=initial_tp3,
        # Set other TPs far away to avoid status change or exit
        take_profit_1=105.0 if side == OrderSide.BUY else 95.0,
        take_profit_2=150.0 if side == OrderSide.BUY else 50.0,
        suggested_stop=50.0 if side == OrderSide.BUY else 150.0,
        invalidation_price=None,
    )

    # OHLC should be between TP1 and TP2 to avoid further status changes
    # and close must be on the right side of UPDATED tp3 to avoid exit
    df = pd.DataFrame(
        {
            "open": [116.0 if side == OrderSide.BUY else 86.0],
            "high": [119.0 if side == OrderSide.BUY else 87.0],
            "low": [114.0 if side == OrderSide.BUY else 84.0],
            "close": [118.0 if side == OrderSide.BUY else 85.0],
            chandelier_col: [chandelier_val],
            "bearish_engulfing": [False],
            "RSI_14": [50.0],
            "ADX_14": [20.0],
        },
        index=[pd.Timestamp("2023-01-02")],
    )

    mock_analyzer_instance = MagicMock()
    mock_analyzer_cls.return_value = mock_analyzer_instance
    mock_analyzer_instance.check_patterns.return_value = df

    # Act
    result = signal_generator.check_exits(
        [signal], "BTC/USD", AssetClass.CRYPTO, dataframe=df
    )

    # Assert
    assert len(result) == 1, f"Expected len(result) == 1, got {len(result)}"
    assert (
        result[0].take_profit_3 == expected_tp3
    ), f"Updated to new Chandelier Exit: expected {expected_tp3}, got {result[0].take_profit_3}"
    assert result[0]._trail_updated is True
    assert result[0]._previous_tp3 == initial_tp3
    assert result[0].status == SignalStatus.TP1_HIT


@pytest.mark.parametrize(
    "side,initial_tp3,chandelier_col,chandelier_val",
    [
        pytest.param(
            OrderSide.BUY, 125.0, "CHANDELIER_EXIT_LONG", 120.0, id="long_no_trail_down"
        ),
        pytest.param(
            OrderSide.SELL, 80.0, "CHANDELIER_EXIT_SHORT", 85.0, id="short_no_trail_up"
        ),
    ],
)
def test_check_exits_trail_not_updated_unfavorable(
    signal_generator,
    mock_market_provider,
    mock_analyzer_cls,
    side,
    initial_tp3,
    chandelier_col,
    chandelier_val,
):
    """Test that take_profit_3 is NOT updated when Chandelier Exit moves unfavorably."""
    signal = SignalFactory.build(
        signal_id="sig_no_trail",
        ds=date(2023, 1, 1),
        symbol="BTC/USD",
        side=side,
        entry_price=100.0,
        status=SignalStatus.TP2_HIT,
        take_profit_3=initial_tp3,
        invalidation_price=None,
    )

    df = pd.DataFrame(
        {
            "open": [100.0],
            "high": [140.0],
            "low": [70.0],
            "close": [132.0 if side == OrderSide.BUY else 75.0],
            chandelier_col: [chandelier_val],
            "bearish_engulfing": [False],
            "RSI_14": [50.0],
            "ADX_14": [20.0],
        },
        index=[pd.Timestamp("2023-01-02")],
    )

    mock_analyzer_instance = MagicMock()
    mock_analyzer_cls.return_value = mock_analyzer_instance
    mock_analyzer_instance.check_patterns.return_value = df

    # Act
    result = signal_generator.check_exits(
        [signal], "BTC/USD", AssetClass.CRYPTO, dataframe=df
    )

    # Assert
    # No signals should be returned (no exit, no trail update)
    assert len(result) == 0, f"Expected len(result) == 0, got {len(result)}"
    # Original signal should still have original TP3
    assert (
        signal.take_profit_3 == initial_tp3
    ), f"Expected signal.take_profit_3 == {initial_tp3}, got {signal.take_profit_3}"


def test_check_exits_trail_not_updated_for_waiting_status(
    signal_generator, mock_market_provider, mock_analyzer_cls
):
    """Test that trailing updates only apply to TP1_HIT and TP2_HIT statuses."""
    # Arrange Active Signal in WAITING status (not in Runner phase yet)
    signal = SignalFactory.build(
        signal_id="sig_trail_3",
        ds=date(2023, 1, 1),
        strategy_id="strat_1",
        symbol="BTC/USD",
        entry_price=100.0,
        pattern_name="TEST",
        suggested_stop=90.0,
        status=SignalStatus.WAITING,
        take_profit_1=110.0,
        take_profit_2=120.0,
        take_profit_3=105.0,  # Initial TP3
        invalidation_price=90.0,
    )

    # Arrange Market Data: Chandelier Exit is higher but status is WAITING
    # Close is ABOVE Chandelier to avoid TP3 exit trigger
    # High is BELOW TP1 to avoid TP1 hit
    df = pd.DataFrame(
        {
            "open": [102.0],
            "high": [109.0],  # Below TP1 (110) - no TP1 trigger
            "low": [100.0],
            "close": [109.0],  # Above Chandelier Exit (108) - no TP3 exit
            "volume": [1000.0],
            "bearish_engulfing": [False],
            "RSI_14": [50.0],
            "ADX_14": [20.0],
            "CHANDELIER_EXIT_LONG": [108.0],  # Higher than TP3 (105)
        },
        index=[pd.Timestamp("2023-01-02")],
    )

    mock_analyzer_instance = MagicMock()
    mock_analyzer_cls.return_value = mock_analyzer_instance
    mock_analyzer_instance.check_patterns.return_value = df

    # Act
    result = signal_generator.check_exits(
        [signal], "BTC/USD", AssetClass.CRYPTO, dataframe=df
    )

    # Assert
    # No exit, no trail update (WAITING status doesn't get trailing)
    assert len(result) == 0, f"Expected len(result) == 0, got {len(result)}"
    assert (
        signal.take_profit_3 == 105.0
    ), f"Unchanged: expected 105.0, got {signal.take_profit_3}"


# =============================================================================
# SHORT POSITION TRAILING STOP TESTS
# =============================================================================


def test_check_exits_short_trail_update_lower(
    signal_generator, mock_market_provider, mock_analyzer_cls
):
    """Test that Short position take_profit_3 is updated when Chandelier Exit moves LOWER."""
    # Arrange Active SHORT SHORT Signal in Runner phase (TP1_HIT)
    signal = SignalFactory.build(
        signal_id="sig_short_trail_1",
        ds=date(2023, 1, 1),
        strategy_id="strat_1",
        symbol="BTC/USD",
        entry_price=100.0,  # Shorted at $100
        pattern_name="TEST",
        suggested_stop=110.0,  # Stop loss ABOVE entry for short
        status=SignalStatus.TP1_HIT,
        take_profit_1=90.0,  # TP1 for short is BELOW entry
        take_profit_2=80.0,
        take_profit_3=95.0,  # Current trailing stop (above current price)
        invalidation_price=None,  # Avoid Long-biased invalidation check triggering
        side=OrderSide.SELL,  # SHORT position
    )

    # Arrange Market Data: Chandelier Exit Short is LOWER than current TP3
    df = pd.DataFrame(
        {
            "open": [85.0],
            "high": [87.0],
            "low": [82.0],
            "close": [85.0],  # BELOW entry (Profit) and ABOVE Chandelier Short (No exit)
            "volume": [1000.0],
            "bearish_engulfing": [False],
            "RSI_14": [50.0],
            "ADX_14": [20.0],
            "CHANDELIER_EXIT_SHORT": [88.0],  # Lower than current TP3 (95)
        },
        index=[pd.Timestamp("2023-01-02")],
    )

    mock_analyzer_instance = MagicMock()
    mock_analyzer_cls.return_value = mock_analyzer_instance
    mock_analyzer_instance.check_patterns.return_value = df

    # Act
    result = signal_generator.check_exits(
        [signal], "BTC/USD", AssetClass.CRYPTO, dataframe=df
    )

    # Assert
    assert len(result) == 1, f"Expected len(result) == 1, got {len(result)}"
    assert (
        result[0].take_profit_3 == 88.0
    ), f"Updated to new (lower) Chandelier Exit Short: expected 88.0, got {result[0].take_profit_3}"
    assert (
        result[0]._trail_updated is True
    ), f"Expected result[0]._trail_updated to be True, got {result[0]._trail_updated}"
    assert (
        result[0]._previous_tp3 == 95.0
    ), f"Expected result[0]._previous_tp3 == 95.0, got {result[0]._previous_tp3}"


def test_check_exits_short_trail_not_updated_when_higher(
    signal_generator, mock_market_provider, mock_analyzer_cls
):
    """Test that Short position take_profit_3 is NOT updated when Chandelier Exit is HIGHER."""
    # Arrange Active SHORT Signal in Runner phase (TP2_HIT)
    signal = SignalFactory.build(
        signal_id="sig_short_trail_2",
        ds=date(2023, 1, 1),
        strategy_id="strat_1",
        symbol="BTC/USD",
        side=OrderSide.SELL,
        entry_price=100.0,
        status=SignalStatus.TP2_HIT,
        take_profit_1=90.0,
        take_profit_2=80.0,
        take_profit_3=80.0,
        suggested_stop=110.0,
        pattern_name="TEST",
        invalidation_price=None,
    )

    # Arrange Market Data: Chandelier Exit is HIGHER than current TP3
    df = pd.DataFrame(
        {
            "open": [75.0],
            "high": [78.0],
            "low": [72.0],
            "close": [75.0],
            "CHANDELIER_EXIT_SHORT": [85.0],  # Higher than current TP3 (80)
        },
        index=[pd.Timestamp("2023-01-02")],
    )

    mock_analyzer_instance = MagicMock()
    mock_analyzer_cls.return_value = mock_analyzer_instance
    mock_analyzer_instance.check_patterns.return_value = df

    # Act
    result = signal_generator.check_exits(
        [signal], "BTC/USD", AssetClass.CRYPTO, dataframe=df
    )

    # Assert
    assert len(result) == 0, f"Expected len(result) == 0, got {len(result)}"
    assert (
        signal.take_profit_3 == 80.0
    ), f"Unchanged: expected 80.0, got {signal.take_profit_3}"


def test_resolve_strategy_config(signal_generator):
    """Test StrategyConfig resolution enforces SCD: one active per asset."""
    active_cfg = StrategyConfig(
        strategy_id="BULLISH_ENGULFING_CRYPTO",
        active=True,
        timeframe="1D",
        asset_class=AssetClass.CRYPTO,
        assets=["BTC/USD", "ETH/USD"],
    )
    inactive_cfg = StrategyConfig(
        strategy_id="BULLISH_ENGULFING_CRYPTO",
        active=False,  # Retired SCD version
        timeframe="1D",
        asset_class=AssetClass.CRYPTO,
        assets=["BTC/USD", "ETH/USD"],
    )
    signal_generator._strategy_configs = [inactive_cfg, active_cfg]

    # 1. Active config found for matching asset
    resolved = signal_generator._resolve_strategy_config(
        "BTC/USD", AssetClass.CRYPTO, "BULLISH_ENGULFING"
    )
    assert resolved == active_cfg, f"Expected active config, got {resolved}"

    # 2. Active config found for second asset in same config
    resolved = signal_generator._resolve_strategy_config(
        "ETH/USD", AssetClass.CRYPTO, "MORNING_STAR"
    )
    assert resolved == active_cfg, f"Expected active config for ETH/USD, got {resolved}"

    # 3. No match for unregistered asset class
    resolved = signal_generator._resolve_strategy_config(
        "AAPL", AssetClass.EQUITY, "BULLISH_ENGULFING"
    )
    assert resolved is None, f"Expected None for EQUITY, got {resolved}"

    # 4. No match when only inactive configs exist
    signal_generator._strategy_configs = [inactive_cfg]
    resolved = signal_generator._resolve_strategy_config(
        "BTC/USD", AssetClass.CRYPTO, "BULLISH_ENGULFING"
    )
    assert (
        resolved is None
    ), f"Expected None when only inactive configs exist, got {resolved}"


def test_check_exits_short_tp3_hit(
    signal_generator, mock_market_provider, mock_analyzer_cls
):
    """Test detecting a Short position Take Profit 3 hit."""
    # Arrange Active SHORT Signal in Runner phase
    signal = SignalFactory.build(
        signal_id="sig_short_tp3",
        ds=date(2023, 1, 1),
        strategy_id="strat_1",
        symbol="BTC/USD",
        side=OrderSide.SELL,
        entry_price=100.0,
        status=SignalStatus.TP2_HIT,
        take_profit_1=90.0,
        take_profit_2=80.0,
        take_profit_3=80.0,
        suggested_stop=110.0,
        pattern_name="TEST",
        invalidation_price=None,
    )

    # Arrange Market Data: Price crosses ABOVE Chandelier Exit Short
    df = pd.DataFrame(
        {
            "open": [85.0],
            "high": [92.0],
            "low": [84.0],
            "close": [90.0],  # Above Chandelier (88)
            "CHANDELIER_EXIT_SHORT": [88.0],
        },
        index=[pd.Timestamp("2023-01-02")],
    )

    mock_analyzer_instance = MagicMock()
    mock_analyzer_cls.return_value = mock_analyzer_instance
    mock_analyzer_instance.check_patterns.return_value = df

    # Act
    result = signal_generator.check_exits(
        [signal], "BTC/USD", AssetClass.CRYPTO, dataframe=df
    )

    # Assert
    assert len(result) == 1, f"Expected len(result) == 1, got {len(result)}"
    assert (
        result[0].status == SignalStatus.TP3_HIT
    ), f"Expected result[0].status == SignalStatus.TP3_HIT, got {result[0].status}"
    assert (
        result[0].exit_reason == ExitReason.TP_HIT
    ), f"Expected result[0].exit_reason == ExitReason.TP_HIT, got {result[0].exit_reason}"
