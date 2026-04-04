"""Unit tests for SignalGenerator micro-cap edge cases (Issue #136)."""

from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest
from crypto_signals.domain.schemas import AssetClass
from crypto_signals.engine.signal_generator import SignalGenerator


@pytest.fixture
def mock_market_provider():
    return MagicMock()


@pytest.fixture
def mock_indicators():
    mock = MagicMock()
    mock.add_all_indicators.return_value = None  # modified from side_effect lambda
    return mock


@pytest.fixture
def mock_analyzer_cls():
    return MagicMock()


@pytest.fixture
def mock_repository():
    mock = MagicMock()
    mock.get_most_recent_exit.return_value = None
    mock.get_open_position_by_symbol.return_value = None
    return mock


@pytest.fixture
def signal_generator(
    mock_market_provider, mock_indicators, mock_analyzer_cls, mock_repository
):
    sg = SignalGenerator(
        market_provider=mock_market_provider,
        indicators=mock_indicators,
        pattern_analyzer_cls=mock_analyzer_cls,
        signal_repo=mock_repository,
    )
    sg.position_repo = mock_repository
    return sg


def test_elliott_pattern_negative_stop_prevention(
    signal_generator, mock_market_provider, mock_analyzer_cls
):
    """
    Issue #136: Verify that ELLIOTT pattern stop calculation prevents negative values.

    Scenario:
    - Low Price: 0.00000080
    - ATR: 0.000002
    - Standard calc: 0.00000080 - (0.5 * 0.000002) = -0.00000020
    - Expected: max(SAFE_STOP_VAL, ...) = 1e-8
    """
    # Arrange Data
    today = date(2026, 1, 24)
    low_price = 0.00000080
    atr = 0.000002

    df = pd.DataFrame(
        {
            "open": [0.00000100],
            "high": [0.00000120],
            "low": [low_price],
            "close": [0.00000110],
            "volume": [1_000_000_000],
            "ATRr_14": [atr],
            # Minimal required columns for confluence check to pass
            "VOL_SMA_20": [1_000_000],
            "RSI_14": [50],
            "ADX_14": [25],
            "SMA_200": [0.00000090],
        },
        index=[pd.Timestamp(today)],
    )
    mock_market_provider.get_daily_bars.return_value = df

    # Arrange Pattern Analysis Result
    mock_analyzer_instance = MagicMock()
    mock_analyzer_cls.return_value = mock_analyzer_instance

    result_df = df.copy()
    # Enable ELLIOTT pattern
    result_df["elliott_impulse_wave"] = True

    mock_analyzer_instance.check_patterns.return_value = result_df

    # Act
    signal = signal_generator.generate_signals("PEPE/USD", AssetClass.CRYPTO)

    # Assert
    assert signal is not None, "signal should not be None"
    assert (
        signal.pattern_name == "ELLIOTT_IMPULSE_WAVE"
    ), 'Expected signal.pattern_name == "ELLIOTT_IMPULSE_WAVE"'

    # Check stop loss floor
    SAFE_STOP_VAL = 1e-8
    expected_stop = SAFE_STOP_VAL

    assert (
        signal.suggested_stop == expected_stop
    ), f"Expected signal.suggested_stop == expected_stop, got {signal.suggested_stop}"
    assert (
        signal.suggested_stop > 0
    ), f"Expected signal.suggested_stop > 0, got {signal.suggested_stop}"


def test_elliott_pattern_normal_stop(
    signal_generator, mock_market_provider, mock_analyzer_cls
):
    """Verify normal ATR calculation still works for non-micro-cap prices."""
    # Arrange Data
    today = date(2026, 1, 24)
    low_price = 50000.0
    atr = 1000.0

    df = pd.DataFrame(
        {
            "open": [51000.0],
            "high": [52000.0],
            "low": [low_price],
            "close": [51500.0],
            "volume": [1000],
            "ATRr_14": [atr],
            "VOL_SMA_20": [1000],
            "RSI_14": [50],
            "ADX_14": [25],
            "SMA_200": [48000.0],
        },
        index=[pd.Timestamp(today)],
    )
    mock_market_provider.get_daily_bars.return_value = df

    mock_analyzer_instance = MagicMock()
    mock_analyzer_cls.return_value = mock_analyzer_instance

    result_df = df.copy()
    result_df["elliott_impulse_wave"] = True

    mock_analyzer_instance.check_patterns.return_value = result_df

    # Act
    signal = signal_generator.generate_signals("BTC/USD", AssetClass.CRYPTO)

    # Assert
    assert signal is not None, "signal should not be None"
    # Standard calc: low - 0.5 * ATR
    expected_stop = low_price - (0.5 * atr)  # 50000 - 500 = 49500
    assert (
        signal.suggested_stop == expected_stop
    ), f"Expected signal.suggested_stop == expected_stop, got {signal.suggested_stop}"
