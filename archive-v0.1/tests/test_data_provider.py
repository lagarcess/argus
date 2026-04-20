from datetime import datetime, timezone

import pandas as pd
import pytest
from alpaca.data.timeframe import TimeFrameUnit
from argus.domain.schemas import AssetClass
from argus.market.data_provider import MarketDataProvider
from argus.market.exceptions import MarketDataError


def test_timeframe_parsing_valid(mocker):
    # Mocking clients
    mock_stock_client = mocker.Mock()
    mock_crypto_client = mocker.Mock()

    # Mocking the response df
    mock_df = pd.DataFrame(
        data={
            "Open": [150.0],
            "High": [155.0],
            "Low": [149.0],
            "Close": [152.0],
            "Volume": [1000],
        },
        index=[datetime.now(timezone.utc)],
    )

    mock_response = mocker.Mock()
    mock_response.df = mock_df

    mock_stock_client.get_stock_bars.return_value = mock_response

    provider = MarketDataProvider(
        stock_client=mock_stock_client, crypto_client=mock_crypto_client
    )

    start = datetime.now(timezone.utc)
    end = datetime.now(timezone.utc)

    provider.get_historical_bars(
        symbol="AAPL",
        asset_class=AssetClass.EQUITY,
        timeframe_str="15Min",
        start_dt=start,
        end_dt=end,
    )

    # Verify the timeframe was passed correctly to Alpaca client
    called_args = mock_stock_client.get_stock_bars.call_args[0][0]
    assert called_args.timeframe.amount == 15
    assert called_args.timeframe.unit == TimeFrameUnit.Minute


def test_timeframe_parsing_invalid(mocker):
    provider = MarketDataProvider(stock_client=mocker.Mock(), crypto_client=mocker.Mock())

    start = datetime.now(timezone.utc)
    end = datetime.now(timezone.utc)

    # Retry logic bubbles up "failed after 3 attempts" string, checking that directly
    with pytest.raises(MarketDataError, match="failed after 3 attempts"):
        provider.get_historical_bars(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            timeframe_str="Invalid15Min",
            start_dt=start,
            end_dt=end,
        )
