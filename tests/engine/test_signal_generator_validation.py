from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from crypto_signals.domain.schemas import AssetClass, SignalStatus
from crypto_signals.engine.parameters import SignalParameterFactory
from crypto_signals.engine.signal_generator import SignalGenerator


@pytest.fixture
def mock_market_provider():
    return MagicMock()


@pytest.fixture
def mock_indicators():
    mock = MagicMock()
    mock.add_all_indicators.return_value = None
    return mock


@pytest.fixture
def mock_repository():
    mock = MagicMock()
    mock.get_open_position_by_symbol.return_value = None
    return mock


@pytest.fixture
def signal_generator(mock_market_provider, mock_indicators, mock_repository):
    sg = SignalGenerator(
        market_provider=mock_market_provider,
        indicators=mock_indicators,
        signal_repo=mock_repository,
    )
    sg.position_repo = mock_repository
    return sg


def test_generate_signal_with_negative_stop(signal_generator):
    """
    Test that a signal with a negative stop (due to volatility or bad math)
    returns a REJECTED_BY_FILTER signal instead of None.
    """
    # Arrange
    symbol = "BTC/USD"
    asset_class = AssetClass.CRYPTO

    # Create a dummy dataframe/series simulating a signal
    # Mock pattern analyzer to return a test pattern
    # Mock check_patterns to return a dataframe with a pattern
    data = {
        "close": 100.0,
        "open": 90.0,
        "high": 110.0,
        "low": 80.0,
        "volume": 1000,
        "bullish_engulfing": True,  # Trigger pattern
        "ATRr_14": 200.0,  # Huge ATR to cause negative stop
        # Stop = Low - (0.5 * ATR) = 80 - 100 = -20 (Negative Stop)
    }
    df = pd.DataFrame([data], index=[datetime.now(timezone.utc)])

    # Mock the pattern analyzer class instantiation
    with patch.object(signal_generator, "pattern_analyzer_cls") as MockAnalyzerCls:
        mock_instance = MockAnalyzerCls.return_value
        mock_instance.check_patterns.return_value = df
        mock_instance.pivots = []  # No pivots for now

        df["elliott_impulse_wave"] = True
        df["bullish_engulfing"] = False

        # Act
        signal = signal_generator.generate_signals(symbol, asset_class, dataframe=df)

        # Assert
        assert signal is not None, "Signal should not be None"
        # Since we now proactively fix negative stops for Elliott patterns,
        # the signal should be valid (WAITING), not REJECTED.
        assert (
            signal.status == SignalStatus.WAITING
        ), f"Expected signal.status == SignalStatus.WAITING, got {signal.status}"
        assert (
            signal.suggested_stop == SignalParameterFactory.SAFE_STOP_VAL
        ), "Safe hydration check"
