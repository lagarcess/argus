from datetime import datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest
from alpaca.trading.client import TradingClient
from crypto_signals.domain.schemas import (
    SignalStatus,
    TradeStatus,
)
from crypto_signals.engine.risk import RiskEngine
from crypto_signals.market.data_provider import MarketDataProvider
from crypto_signals.repository.firestore import PositionRepository

from tests.factories import PositionFactory, SignalFactory


class TestRiskCorrelation:
    @pytest.fixture
    def mock_market_provider(self):
        return MagicMock(spec=MarketDataProvider)

    @pytest.fixture
    def mock_repo(self):
        return MagicMock(spec=PositionRepository)

    @pytest.fixture
    def mock_client(self):
        return MagicMock(spec=TradingClient)

    @pytest.fixture
    def risk_engine(self, mock_client, mock_repo, mock_market_provider):
        # We need to mock get_settings as well
        with pytest.MonkeyPatch.context() as m:
            settings = MagicMock()
            settings.MAX_CRYPTO_POSITIONS = 5
            settings.MAX_EQUITY_POSITIONS = 5
            settings.MAX_DAILY_DRAWDOWN_PCT = 0.05
            settings.MIN_ASSET_BP_USD = 100.0
            m.setattr("crypto_signals.engine.risk.get_settings", lambda: settings)
            return RiskEngine(
                trading_client=mock_client,
                repository=mock_repo,
                market_provider=mock_market_provider,
            )

    def create_signal(self, symbol="BTC/USD"):
        return SignalFactory.build(
            signal_id="sig_1",
            strategy_id="test_strat",
            symbol=symbol,
            pattern_name="TestPattern",
            status=SignalStatus.WAITING,
            entry_price=50000.0,
            take_profit_1=55000.0,
            suggested_stop=45000.0,
        )

    def create_position(self, symbol="ETH/USD"):
        return PositionFactory.build(
            position_id="pos_1",
            signal_id="sig_old",
            symbol=symbol,
            status=TradeStatus.OPEN,
            entry_fill_price=3000.0,
            qty=1.0,
            current_stop_loss=2500.0,
            alpaca_order_id="order_1",
        )

    def test_check_correlation_no_positions(self, risk_engine, mock_repo):
        """Verify correlation check passes with no open positions."""
        mock_repo.get_open_positions.return_value = []
        signal = self.create_signal()

        # Should pass if no positions
        if not hasattr(risk_engine, "check_correlation"):
            pytest.fail("RiskEngine.check_correlation not implemented")

        result = risk_engine.check_correlation(signal)
        assert (
            result.passed is True
        ), f"Expected result.passed to be True, got {result.passed}"

    def test_check_correlation_high(self, risk_engine, mock_repo, mock_market_provider):
        """Verify signal rejection for high correlation with an open position."""
        # Arrange: Open position in ETH
        mock_repo.get_open_positions.return_value = [
            self.create_position(symbol="ETH/USD")
        ]

        signal = self.create_signal(symbol="BTC/USD")

        # Mock Market Data: Perfectly correlated data
        dates = pd.date_range(end=datetime.now(), periods=90)
        # BTC and ETH moving exactly together
        btc_prices = [100 + i for i in range(90)]
        eth_prices = [10 + i for i in range(90)]

        # MarketDataProvider.get_daily_bars returns DataFrame with 'close' column (or similar)
        # Based on MarketDataProvider code: "df.index = pd.to_datetime(df.index)"
        # And it returns whatever Alpaca returns. Alpaca bars usually have 'close'.

        btc_df = pd.DataFrame({"close": btc_prices}, index=dates)
        eth_df = pd.DataFrame({"close": eth_prices}, index=dates)

        def get_bars_side_effect(symbol, asset_class, lookback_days=90):
            # Handle list input (new batching behavior)
            if isinstance(symbol, list):
                dfs = []
                keys = []
                for s in symbol:
                    if s == "BTC/USD":
                        dfs.append(btc_df)
                        keys.append(s)
                    elif s == "ETH/USD":
                        dfs.append(eth_df)
                        keys.append(s)

                if not dfs:
                    return pd.DataFrame()

                # Create MultiIndex DF
                return pd.concat(dfs, keys=keys, names=["symbol", "timestamp"])

            # Handle single input (fallback or old behavior if any)
            if symbol == "BTC/USD":
                return btc_df
            elif symbol == "ETH/USD":
                return eth_df
            return pd.DataFrame()

        mock_market_provider.get_daily_bars.side_effect = get_bars_side_effect

        if not hasattr(risk_engine, "check_correlation"):
            pytest.fail("RiskEngine.check_correlation not implemented")

        result = risk_engine.check_correlation(signal)
        assert (
            result.passed is False
        ), f"Expected result.passed to be False, got {result.passed}"
        assert (
            "highly correlated" in result.reason.lower()
            or "correlation" in result.reason.lower()
        ), f"Expected risk gate reason to contain relevant keyword, got {result.reason}"

    def test_check_correlation_low(self, risk_engine, mock_repo, mock_market_provider):
        """Verify signal acceptance for low or inverse correlation."""
        # Arrange: Open position in ETH
        mock_repo.get_open_positions.return_value = [
            self.create_position(symbol="ETH/USD")
        ]

        signal = self.create_signal(symbol="BTC/USD")

        # Mock Market Data: Uncorrelated/Inverse
        dates = pd.date_range(end=datetime.now(), periods=90)
        btc_prices = [100 + i for i in range(90)]
        eth_prices = [100 - i for i in range(90)]  # Inverse

        btc_df = pd.DataFrame({"close": btc_prices}, index=dates)
        eth_df = pd.DataFrame({"close": eth_prices}, index=dates)

        def get_bars_side_effect(symbol, asset_class, lookback_days=90):
            if isinstance(symbol, list):
                dfs = []
                keys = []
                for s in symbol:
                    if s == "BTC/USD":
                        dfs.append(btc_df)
                        keys.append(s)
                    elif s == "ETH/USD":
                        dfs.append(eth_df)
                        keys.append(s)
                if not dfs:
                    return pd.DataFrame()
                return pd.concat(dfs, keys=keys, names=["symbol", "timestamp"])

            if symbol == "BTC/USD":
                return btc_df
            elif symbol == "ETH/USD":
                return eth_df
            return pd.DataFrame()

        mock_market_provider.get_daily_bars.side_effect = get_bars_side_effect

        if not hasattr(risk_engine, "check_correlation"):
            pytest.fail("RiskEngine.check_correlation not implemented")

        result = risk_engine.check_correlation(signal)
        assert (
            result.passed is True
        ), f"Expected result.passed to be True, got {result.passed}"

    def test_check_correlation_market_data_failure(
        self, risk_engine, mock_repo, mock_market_provider
    ):
        """Ensure safe failure (rejection) if correlation data is missing."""
        mock_repo.get_open_positions.return_value = [
            self.create_position(symbol="ETH/USD")
        ]
        signal = self.create_signal(symbol="BTC/USD")

        # Raise exception when fetching data
        mock_market_provider.get_daily_bars.side_effect = Exception("API Error")

        if not hasattr(risk_engine, "check_correlation"):
            pytest.fail("RiskEngine.check_correlation not implemented")

        result = risk_engine.check_correlation(signal)
        # Should fail safe (block)
        assert (
            result.passed is False
        ), f"Expected result.passed to be False, got {result.passed}"
        assert (
            "error checking correlation" in result.reason.lower()
            or "market data missing" in result.reason.lower()
        ), f"Expected risk gate reason to contain relevant keyword, got {result.reason}"
