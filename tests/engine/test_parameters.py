"""
Unit tests for the SignalParameterFactory.
"""

from datetime import timedelta, timezone
from unittest.mock import MagicMock

import pandas as pd
import pytest
from crypto_signals.domain.schemas import AssetClass, StrategyConfig
from crypto_signals.engine.parameters import SignalParameterFactory
from loguru import logger


@pytest.fixture
def factory():
    return SignalParameterFactory()


@pytest.fixture
def caplog(caplog):
    """Override caplog fixture to capture loguru logs."""
    handler_id = logger.add(
        caplog.handler,
        format="{message}",
        level=0,
        filter=lambda record: record["level"].no >= 0,
        catch=False,
    )
    yield caplog
    logger.remove(handler_id)


@pytest.fixture
def strategy_config():
    return StrategyConfig(
        strategy_id="BULLISH_ENGULFING_CRYPTO",
        active=True,
        timeframe="1D",
        asset_class=AssetClass.CRYPTO,
        assets=["BTC/USD"],
    )


@pytest.fixture
def mock_analyzer():
    analyzer = MagicMock()
    analyzer.pivots = []
    return analyzer


def test_bull_flag_parameters(factory, mock_analyzer):
    """Test parameter calculation for Bull Flag."""
    latest = pd.Series(
        {
            "close": 100.0,
            "low": 90.0,
            "high": 110.0,
            "open": 95.0,
            "ATRr_14": 5.0,
            "bull_flag_duration": 10,
            "bull_flag_classification": "STANDARD",
        }
    )
    latest.name = pd.Timestamp("2023-01-01")

    params = factory.get_parameters(
        symbol="BTC/USD",
        asset_class=AssetClass.CRYPTO,
        pattern_name="BULL_FLAG",
        latest=latest,
        sig_id="test_id",
        analyzer=mock_analyzer,
    )

    # Expected calculations:
    # pole_high = 110.0, pole_low = 90.0
    # atr = 5.0
    # flagpole_height = max(5.0 * 3.0, 110-90) = max(15, 20) = 20.0
    # tp1 = 100 + 0.5 * 20 = 110
    # tp2 = 100 + 1.0 * 20 = 120
    # tp3 = 100 + 1.5 * 20 = 130
    # stop = 90 * 0.99 = 89.1

    assert params["symbol"] == "BTC/USD", 'Expected params["symbol"] == "BTC/USD"'
    assert (
        params["pattern_name"] == "BULL_FLAG"
    ), 'Expected params["pattern_name"] == "BULL_FLAG"'
    assert params["take_profit_1"] == 110.0, 'Expected params["take_profit_1"] == 110.0'
    assert params["take_profit_2"] == 120.0, 'Expected params["take_profit_2"] == 120.0'
    assert params["take_profit_3"] == 130.0, 'Expected params["take_profit_3"] == 130.0'
    assert params["suggested_stop"] == 89.1, 'Expected params["suggested_stop"] == 89.1'
    assert (
        params["pattern_duration_days"] == 10
    ), 'Expected params["pattern_duration_days"] == 10'
    assert (
        params["pattern_classification"] == "STANDARD"
    ), 'Expected params["pattern_classification"] == "STANDARD"'


def test_elliott_wave_micro_cap_safety(factory, mock_analyzer):
    """Test Elliott Wave with micro-cap safety (Issue #136)."""
    # Low price and high volatility causing potential negative stop
    latest = pd.Series(
        {
            "close": 0.00000080,
            "low": 0.00000080,
            "high": 0.00000090,
            "open": 0.00000085,
            "ATRr_14": 0.00000200,
        }
    )
    latest.name = pd.Timestamp("2023-01-01")

    params = factory.get_parameters(
        symbol="PEPE/USD",
        asset_class=AssetClass.CRYPTO,
        pattern_name="ELLIOTT_IMPULSE_WAVE",
        latest=latest,
        sig_id="test_id",
        analyzer=mock_analyzer,
    )

    # Calculation:
    # stop = low - (0.5 * atr) = 0.8e-6 - 1.0e-6 = -0.2e-6
    # Should be capped at SAFE_STOP_VAL = 1e-8

    assert (
        params["suggested_stop"] == factory.SAFE_STOP_VAL
    ), 'Expected params["suggested_stop"] == factory.SAFE_STOP_VAL'
    assert (
        params["suggested_stop"] > 0
    ), 'Assertion condition not met: params["suggested_stop"] > 0'


def test_elliott_wave_normal(factory, mock_analyzer):
    """Test Elliott Wave normal calculation."""
    latest = pd.Series(
        {
            "close": 100.0,
            "low": 90.0,
            "high": 110.0,
            "open": 95.0,
            "ATRr_14": 5.0,
        }
    )
    latest.name = pd.Timestamp("2023-01-01")

    params = factory.get_parameters(
        symbol="BTC/USD",
        asset_class=AssetClass.CRYPTO,
        pattern_name="ELLIOTT_IMPULSE_WAVE",
        latest=latest,
        sig_id="test_id",
        analyzer=mock_analyzer,
    )

    # stop = 90 - 2.5 = 87.5
    assert params["suggested_stop"] == 87.5, 'Expected params["suggested_stop"] == 87.5'


@pytest.mark.parametrize(
    "pattern_name,ohlc,expected",
    [
        pytest.param(
            "BULLISH_HAMMER",
            {"close": 100.0, "low": 90.0, "high": 110.0, "open": 95.0, "ATRr_14": 5.0},
            {"invalidation": 90.0, "stop": 89.1, "tp1": 110.0},
            id="bullish_hammer",
        ),
        pytest.param(
            "MORNING_STAR",
            {"close": 100.0, "low": 90.0, "high": 110.0, "open": 95.0, "ATRr_14": 5.0},
            {"invalidation": 90.0, "stop": 89.1, "tp1": 110.0},
            id="morning_star",
        ),
        pytest.param(
            "BULLISH_ENGULFING",
            {"close": 105.0, "low": 90.0, "high": 110.0, "open": 95.0, "ATRr_14": 5.0},
            {"invalidation": 95.0, "stop": 94.05, "tp1": 115.0},
            id="bullish_engulfing",
        ),
        pytest.param(
            "BULLISH_MARUBOZU",
            {"close": 110.0, "low": 90.0, "high": 110.0, "open": 90.0, "ATRr_14": 5.0},
            {"invalidation": 100.0, "stop": 99.0, "tp1": 120.0},
            id="bullish_marubozu",
        ),
        pytest.param(
            "INVERSE_HEAD_SHOULDERS",
            {"close": 100.0, "low": 90.0, "high": 110.0, "open": 95.0, "ATRr_14": 5.0},
            {"invalidation": None, "stop": 89.1, "tp1": 110.0},
            id="fallthrough_pattern",
        ),
    ],
)
def test_pattern_parameters(factory, mock_analyzer, pattern_name, ohlc, expected):
    """Test parameter calculation for various patterns."""
    latest = pd.Series(ohlc)
    latest.name = pd.Timestamp("2023-01-01")

    params = factory.get_parameters(
        symbol="BTC/USD",
        asset_class=AssetClass.CRYPTO,
        pattern_name=pattern_name,
        latest=latest,
        sig_id="test_id",
        analyzer=mock_analyzer,
    )

    assert params["invalidation_price"] == expected["invalidation"]
    assert params["suggested_stop"] == pytest.approx(expected["stop"])
    assert params["take_profit_1"] == pytest.approx(expected["tp1"])


def test_hydrate_safe_values(factory):
    """Test safe hydration logic."""
    bad_params = {
        "suggested_stop": -1.0,
        "take_profit_1": 0.0,
        "take_profit_2": -5.0,
        "take_profit_3": None,
    }

    safe = factory.hydrate_safe_values(bad_params)

    assert (
        safe["suggested_stop"] == factory.SAFE_STOP_VAL
    ), 'Expected safe["suggested_stop"] == factory.SAFE_STOP_VAL'
    assert (
        safe["take_profit_1"] == factory.SAFE_TP1_VAL
    ), 'Expected safe["take_profit_1"] == factory.SAFE_TP1_VAL'
    assert (
        safe["take_profit_2"] == factory.SAFE_TP2_VAL
    ), 'Expected safe["take_profit_2"] == factory.SAFE_TP2_VAL'
    assert (
        safe["take_profit_3"] == factory.SAFE_TP3_VAL
    ), 'Expected safe["take_profit_3"] == factory.SAFE_TP3_VAL'


def test_confluence_factors(factory, mock_analyzer):
    """Test extraction of confluence factors."""
    latest = pd.Series(
        {
            "close": 100.0,
            "low": 90.0,
            "open": 95.0,
            "rsi_bullish_divergence": True,
            "volume_expansion": True,
            "trend_bullish": False,
        }
    )
    latest.name = pd.Timestamp("2023-01-01")

    params = factory.get_parameters(
        symbol="BTC/USD",
        asset_class=AssetClass.CRYPTO,
        pattern_name="TEST_PATTERN",
        latest=latest,
        sig_id="test_id",
        analyzer=mock_analyzer,
        geometric_pattern_name="BULL_FLAG",
    )

    assert (
        "rsi_bullish_divergence" in params["confluence_factors"]
    ), 'Assertion condition not met: "rsi_bullish_divergence" in params["confluence_factors"]'
    assert (
        "volume_expansion" in params["confluence_factors"]
    ), 'Assertion condition not met: "volume_expansion" in params["confluence_factors"]'
    assert (
        "trend_bullish" not in params["confluence_factors"]
    ), 'Assertion condition not met: "trend_bullish" not in params["confluence_factors"]'
    # If harmonic_pattern is provided, geometric_pattern_name is appended,
    # but here harmonic_pattern is None, so check logic again.
    assert (
        "BULL_FLAG" not in params["confluence_factors"]
    ), 'Assertion condition not met: "BULL_FLAG" not in params["confluence_factors"]'


def test_harmonic_metadata(factory, mock_analyzer):
    """Test harmonic metadata extraction."""
    latest = pd.Series({"close": 100.0, "low": 90.0, "open": 95.0})
    latest.name = pd.Timestamp("2023-01-01")

    mock_harmonic = MagicMock()
    mock_harmonic.ratios = {"XA": 0.618}
    mock_harmonic.is_macro = True
    mock_harmonic.pattern_type = "GARTLEY"

    params = factory.get_parameters(
        symbol="BTC/USD",
        asset_class=AssetClass.CRYPTO,
        pattern_name="GARTLEY",
        latest=latest,
        sig_id="test_id",
        analyzer=mock_analyzer,
        harmonic_pattern=mock_harmonic,
    )

    assert (
        params["strategy_id"] == "GARTLEY_CRYPTO"
    ), "Multi-Layer: fallback uses structured pattern_name format"
    assert (
        params["pattern_classification"] == "MACRO_PATTERN"
    ), 'Expected params["pattern_classification"] == "MACRO_PATTERN"'
    assert (
        params["harmonic_metadata"] == {"XA": 0.618}
    ), f'Expected params["harmonic_metadata"] to match expected value, got {params["harmonic_metadata"]}'
    assert (
        params["structural_context"] == "GARTLEY"
    ), 'Expected params["structural_context"] == "GARTLEY"'
    assert (
        params["conviction_tier"] == "HIGH"
    ), 'Expected params["conviction_tier"] == "HIGH"'

    expected_ts = pd.Timestamp("2023-01-01").to_pydatetime().replace(
        tzinfo=timezone.utc
    ) + timedelta(hours=120)
    assert (
        params["valid_until"] == expected_ts
    ), 'Expected params["valid_until"] == expected_ts'


@pytest.mark.parametrize(
    "inject_config,expected_id_type",
    [
        pytest.param(True, "UUID", id="uuid_when_config_injected"),
        pytest.param(False, "PATTERN", id="pattern_name_fallback"),
    ],
)
def test_strategy_id_injection(
    factory, mock_analyzer, strategy_config, caplog, inject_config, expected_id_type
):
    """Test injection of real strategy_id UUID vs pattern_name fallback."""
    latest = pd.Series({"close": 100.0, "low": 90.0, "open": 95.0})
    latest.name = pd.Timestamp("2023-01-01")
    pattern_name = "BULLISH_ENGULFING"

    params = factory.get_parameters(
        symbol="BTC/USD",
        asset_class=AssetClass.CRYPTO,
        pattern_name=pattern_name,
        latest=latest,
        sig_id="test_id",
        analyzer=mock_analyzer,
        strategy_config=strategy_config if inject_config else None,
    )

    if expected_id_type == "UUID":
        expected_id = strategy_config.strategy_id
        assert (
            params["strategy_id"] == expected_id
        ), f"Expected strategy_id={expected_id!r}, got {params['strategy_id']!r}"
        assert (
            "Falling back to pattern_name" not in caplog.text
        ), "Did not expect a fallback warning when config is injected"
    else:
        expected_id = f"{pattern_name}_CRYPTO"
        assert (
            params["strategy_id"] == expected_id
        ), f"Expected strategy_id={expected_id!r}, got {params['strategy_id']!r}"
        assert (
            "Falling back to structured pattern_name as strategy_id" in caplog.text
        ), "Expected a fallback warning when config is missing"
