from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from crypto_signals.domain.schemas import (
    AssetClass,
    AssetClassFee,
    FactRejectedSignal,
    OrderSide,
)
from crypto_signals.pipelines.rejected_signal_archival import (
    RejectedSignalArchival,
)


@pytest.fixture
def mock_firestore():
    return MagicMock()


@pytest.fixture
def mock_market_provider():
    return MagicMock()


@pytest.fixture
def sample_fact_rejected_signal():
    """Provides a sample FactRejectedSignal instance for testing."""
    now = datetime.now(timezone.utc)
    return FactRejectedSignal(
        doc_id="sig_1",
        signal_id="sig_1",
        created_at=now,
        ds=now.date(),
        symbol="BTC/USD",
        asset_class="CRYPTO",
        pattern_name="BULL_FLAG",
        rejection_reason="TEST",
        trade_type="FILTERED",
        side=OrderSide.BUY.value,
        entry_price=1.0,
        suggested_stop=0.9,
        take_profit_1=1.1,
        theoretical_exit_price=None,
        theoretical_exit_reason=None,
        theoretical_exit_time=None,
        theoretical_pnl_usd=0.0,
        theoretical_pnl_pct=0.0,
        theoretical_fees_usd=0.0,
    )


@pytest.fixture
def pipeline(mock_firestore, mock_market_provider):
    with (
        patch(
            "crypto_signals.pipelines.rejected_signal_archival.firestore.Client",
            return_value=mock_firestore,
        ),
        patch("crypto_signals.pipelines.base.get_settings") as mock_get_settings,
        patch(
            "crypto_signals.pipelines.rejected_signal_archival.MarketDataProvider",
            return_value=mock_market_provider,
        ),
        patch(
            "crypto_signals.pipelines.rejected_signal_archival.get_stock_data_client",
            return_value=MagicMock(),
        ),
        patch(
            "crypto_signals.pipelines.rejected_signal_archival.get_crypto_data_client",
            return_value=MagicMock(),
        ),
        # Patch BigQuery client in the base class to prevent credentials error
        patch("crypto_signals.pipelines.base.bigquery.Client") as mock_bq,
        patch("crypto_signals.pipelines.base.SchemaGuardian") as mock_guardian,
    ):
        mock_get_settings.return_value.GOOGLE_CLOUD_PROJECT = "test-project"
        mock_get_settings.return_value.ENVIRONMENT = "PROD"
        mock_get_settings.return_value.SCHEMA_GUARDIAN_STRICT_MODE = True

        # Instantiate pipeline
        pipe = RejectedSignalArchival()
        # Inject mocks
        pipe.firestore_client = mock_firestore
        pipe.market_provider = mock_market_provider
        pipe.bq_client = mock_bq.return_value
        pipe.guardian = mock_guardian.return_value

        return pipe


def test_extract(pipeline, mock_firestore):
    """Test extracting rejected signals from Firestore."""
    mock_doc = MagicMock()
    mock_doc.id = "sig_1"
    mock_doc.to_dict.return_value = {
        "signal_id": "sig_1",
        "symbol": "BTC/USD",
        "created_at": datetime.now(timezone.utc) - timedelta(days=8),
    }

    mock_query = (
        mock_firestore.collection.return_value.where.return_value.limit.return_value
    )
    mock_query.stream.return_value = [mock_doc]

    raw_data = pipeline.extract()

    assert len(raw_data) == 1
    assert raw_data[0]["signal_id"] == "sig_1"
    assert raw_data[0]["_doc_id"] == "sig_1"


def test_transform_long_tp_hit(pipeline, mock_market_provider):
    """Test transforming a Long signal that would have hit TP1."""
    created_at = datetime.now(timezone.utc) - timedelta(days=8)
    raw_data = [
        {
            "signal_id": "sig_1",
            "symbol": "BTC/USD",
            "asset_class": "CRYPTO",
            "entry_price": 50000.0,
            "suggested_stop": 48000.0,
            "take_profit_1": 55000.0,
            "side": OrderSide.BUY.value,
            "created_at": created_at,
            "pattern_name": "BULL_FLAG",
            "rejection_reason": "TEST_REASON",
        }
    ]

    # Mock Market Data: High hits TP1
    dates = pd.date_range(created_at.date(), periods=3, freq="D", tz="UTC")
    df = pd.DataFrame(
        {
            "high": [51000.0, 56000.0, 52000.0],
            "low": [49000.0, 50000.0, 51000.0],
            "close": [50500.0, 54000.0, 52000.0],
        },
        index=dates,
    )
    mock_market_provider.get_daily_bars.return_value = df

    transformed = pipeline.transform(raw_data)

    assert len(transformed) == 1
    record = transformed[0]
    assert record["theoretical_exit_reason"] == "THEORETICAL_TP1"
    assert record["theoretical_exit_price"] == 55000.0
    assert record["theoretical_pnl_usd"] > 0


def test_transform_open_position(pipeline, mock_market_provider):
    """Test transforming a signal that hits neither TP nor SL, exiting at the latest close."""
    created_at = datetime.now(timezone.utc) - timedelta(days=8)
    raw_data = [
        {
            "signal_id": "sig_open",
            "symbol": "ETH/USD",
            "asset_class": "CRYPTO",
            "entry_price": 2000.0,
            "suggested_stop": 1900.0,
            "take_profit_1": 2200.0,
            "side": OrderSide.BUY.value,
            "created_at": created_at,
            "pattern_name": "CONSOLIDATION",
            "rejection_reason": "TEST_REASON",
        }
    ]

    # Mock Market Data: Price stays between SL and TP
    dates = pd.date_range(created_at.date(), periods=3, freq="D", tz="UTC")
    df = pd.DataFrame(
        {
            "high": [2050.0, 2100.0, 2080.0],
            "low": [1950.0, 1980.0, 1990.0],
            "close": [2020.0, 2090.0, 2050.0],
        },
        index=dates,
    )
    mock_market_provider.get_daily_bars.return_value = df

    transformed = pipeline.transform(raw_data)

    assert len(transformed) == 1
    record = transformed[0]
    assert record["theoretical_exit_reason"] == "THEORETICAL_OPEN"
    assert record["theoretical_exit_price"] == 2050.0  # Final close
    assert record["theoretical_pnl_usd"] > 0


def test_transform_missing_fields(pipeline, mock_market_provider):
    """Test transforming a signal that is missing required fields."""
    raw_data = [
        {
            "signal_id": "sig_missing",
            "symbol": "BTC/USD",
            # Missing entry_price, suggested_stop, etc.
        }
    ]

    transformed = pipeline.transform(raw_data)

    assert len(transformed) == 0


def test_transform_exception_catch(pipeline, mock_market_provider):
    """Test transforming a signal where Pydantic model validation fails."""
    created_at = datetime.now(timezone.utc) - timedelta(days=8)
    raw_data = [
        {
            "signal_id": "sig_exception",
            "symbol": "BTC/USD",
            "asset_class": "CRYPTO",
            "entry_price": "NOT_A_FLOAT",  # This will cause a Pydantic validation error or ValueError
            "suggested_stop": 48000.0,
            "take_profit_1": 55000.0,
            "side": OrderSide.BUY.value,
            "created_at": created_at,
            "pattern_name": "BULL_FLAG",
        }
    ]

    dates = pd.date_range(created_at.date(), periods=3, freq="D", tz="UTC")
    df = pd.DataFrame(
        {
            "high": [51000.0, 56000.0, 52000.0],
            "low": [49000.0, 50000.0, 51000.0],
            "close": [50500.0, 54000.0, 52000.0],
        },
        index=dates,
    )
    mock_market_provider.get_daily_bars.return_value = df

    transformed = pipeline.transform(raw_data)

    assert len(transformed) == 0


def test_transform_validation_failure(pipeline, mock_market_provider):
    """Test transforming a signal rejected due to validation failure."""
    created_at = datetime.now(timezone.utc) - timedelta(days=8)
    raw_data = [
        {
            "signal_id": "sig_val_fail",
            "symbol": "BTC/USD",
            "entry_price": 100.0,
            "suggested_stop": 90.0,
            "take_profit_1": 110.0,
            "asset_class": "CRYPTO",
            "side": OrderSide.BUY.value,
            "created_at": created_at,
            "rejection_reason": "VALIDATION_FAILED: Invalid Stop",
            "pattern_name": "TEST_PATTERN",
        }
    ]

    transformed = pipeline.transform(raw_data)

    assert len(transformed) == 1
    record = transformed[0]
    assert record["theoretical_exit_reason"] == "VALIDATION_FAILED_NO_EXECUTION"
    assert record["theoretical_pnl_usd"] == 0.0


def test_transform_validation_failure_empty_data(pipeline, mock_market_provider):
    """Test transforming a signal rejected due to validation failure that also has no market data."""
    created_at = datetime.now(timezone.utc) - timedelta(days=8)
    raw_data = [
        {
            "signal_id": "sig_val_fail_empty",
            "symbol": "BTC/USD",
            "entry_price": 100.0,
            "suggested_stop": 90.0,
            "take_profit_1": 110.0,
            "asset_class": "CRYPTO",
            "side": OrderSide.BUY.value,
            "created_at": created_at,
            "rejection_reason": "VALIDATION_FAILED: Invalid Stop",
            "pattern_name": "TEST_PATTERN",
        }
    ]

    mock_market_provider.get_daily_bars.return_value = pd.DataFrame()

    transformed = pipeline.transform(raw_data)

    assert len(transformed) == 1
    record = transformed[0]
    assert record["theoretical_exit_reason"] == "VALIDATION_FAILED_NO_EXECUTION"
    assert record["theoretical_pnl_usd"] == 0.0


def test_transform_no_market_data(pipeline, mock_market_provider):
    """Test transforming a signal where fetching market data returns an empty dataframe."""
    created_at = datetime.now(timezone.utc) - timedelta(days=8)
    raw_data = [
        {
            "signal_id": "sig_no_data",
            "symbol": "AFAKECOIN/USD",
            "entry_price": 1.0,
            "suggested_stop": 0.9,
            "take_profit_1": 1.1,
            "asset_class": "CRYPTO",
            "side": OrderSide.BUY.value,
            "created_at": created_at,
            "pattern_name": "TEST_PATTERN",
        }
    ]

    # Mock market provider to return empty dataframe
    mock_market_provider.get_daily_bars.return_value = pd.DataFrame()

    transformed = pipeline.transform(raw_data)

    assert len(transformed) == 1
    record = transformed[0]
    assert record["theoretical_exit_reason"] == "NO_MARKET_DATA"
    assert record["theoretical_pnl_usd"] == 0.0


def test_transform_market_data_filtered_out(pipeline, mock_market_provider):
    """Test transforming a signal where market data is found but filtered out due to dates."""
    created_at = datetime.now(timezone.utc) - timedelta(days=8)
    raw_data = [
        {
            "signal_id": "sig_filtered_out",
            "symbol": "BTC/USD",
            "entry_price": 50000.0,
            "suggested_stop": 48000.0,
            "take_profit_1": 52000.0,
            "asset_class": "CRYPTO",
            "side": OrderSide.BUY.value,
            "created_at": created_at,
            "pattern_name": "TEST_PATTERN",
        }
    ]

    # Mock market dates BEFORE the signal creation date
    dates = pd.date_range(
        created_at.date() - timedelta(days=10), periods=3, freq="D", tz="UTC"
    )
    df = pd.DataFrame(
        {
            "high": [51000.0, 56000.0, 52000.0],
            "low": [49000.0, 50000.0, 51000.0],
            "close": [50500.0, 54000.0, 52000.0],
        },
        index=dates,
    )
    mock_market_provider.get_daily_bars.return_value = df

    transformed = pipeline.transform(raw_data)

    assert len(transformed) == 1
    record = transformed[0]
    assert record["theoretical_exit_reason"] == "NO_MARKET_DATA"
    assert record["theoretical_pnl_usd"] == 0.0


def test_cleanup(pipeline, mock_firestore, sample_fact_rejected_signal):
    """Test cleaning up processed signals from Firestore."""
    mock_batch = mock_firestore.batch.return_value
    pipeline.cleanup([sample_fact_rejected_signal])

    assert mock_firestore.collection.called
    assert mock_batch.delete.called
    assert mock_batch.commit.called


def test_run_calls_schema_guardian(pipeline, mock_firestore, sample_fact_rejected_signal):
    """Test that the pipeline's run method calls SchemaGuardian."""
    # Mock the extract method to return some data
    pipeline.extract = MagicMock(return_value=[{"signal_id": "sig_1"}])
    transformed_data = [sample_fact_rejected_signal.model_dump(mode="json")]
    pipeline.transform = MagicMock(return_value=transformed_data)
    pipeline.cleanup = MagicMock()

    # Run the pipeline
    pipeline.run()

    # Assert that SchemaGuardian.validate_schema was called
    # Now called once for the fact table (temp table does not need validation)
    assert pipeline.guardian.validate_schema.call_count == 1


def test_extract_cutoff_date(pipeline, mock_firestore):
    """Test that the extract method uses a cutoff date of T-7 days."""
    # Setup mock to avoid crash
    mock_query = (
        mock_firestore.collection.return_value.where.return_value.limit.return_value
    )
    mock_query.stream.return_value = []

    pipeline.extract()

    # Get the arguments passed to 'where'
    call_args = mock_firestore.collection.return_value.where.call_args
    assert call_args is not None

    # Check arguments
    kwargs = call_args.kwargs
    cutoff_arg = kwargs.get("value")

    if cutoff_arg is None and "filter" in kwargs:
        # FieldFilter used: .where(filter=FieldFilter(field, op, value))
        field_filter = kwargs["filter"]
        # FieldFilter objects store the value in the 'value' attribute
        cutoff_arg = field_filter.value

    if cutoff_arg is None and len(call_args.args) >= 3:
        # Positional args: field_path, op_string, value
        cutoff_arg = call_args.args[2]

    assert cutoff_arg is not None, "Could not find cutoff value in arguments"

    # Calculate expected cutoff (approx 7 days ago)
    now = datetime.now(timezone.utc)

    # We expect the cutoff to be roughly 7 days ago.
    # Since the implementation floors to midnight, the diff could be slightly more than 7 days
    # depending on current time of day.
    # Example: Now is T+0 12:00. Cutoff should be T-7 00:00. Diff is 7 days 12 hours.
    # Current Buggy: Cutoff is T+0 00:00. Diff is 12 hours (0 days).
    diff = now - cutoff_arg

    assert diff.days >= 7, f"Expected cutoff >= 7 days ago, but got diff: {diff}"


@pytest.mark.parametrize(
    "asset_class, expected_fee_pct",
    [
        pytest.param(
            AssetClass.EQUITY.value,
            AssetClassFee.EQUITY.value,
            id="equity_zero_fee",
        ),
        pytest.param(
            AssetClass.CRYPTO.value,
            AssetClassFee.CRYPTO.value,
            id="crypto_taker_fee",
        ),
    ],
)
def test_transform_fees_by_asset_class(
    pipeline, mock_market_provider, asset_class, expected_fee_pct
):
    """Verify that theoretical fees are calculated based on asset class."""
    created_at = datetime.now(timezone.utc) - timedelta(days=8)
    entry_price = 100.0
    exit_price = 110.0  # Take Profit
    qty = 1.0

    raw_data = [
        {
            "signal_id": f"sig_fee_{asset_class}",
            "symbol": "AAPL" if asset_class == "EQUITY" else "BTC/USD",
            "asset_class": asset_class,
            "entry_price": entry_price,
            "suggested_stop": 90.0,
            "take_profit_1": exit_price,
            "side": OrderSide.BUY.value,
            "created_at": created_at,
            "pattern_name": "TEST_PATTERN",
        }
    ]

    # Mock Market Data to hit TP1 immediately
    dates = pd.date_range(created_at.date(), periods=1, freq="D", tz="UTC")
    df = pd.DataFrame(
        {
            "high": [exit_price],
            "low": [entry_price],
            "close": [exit_price],
        },
        index=dates,
    )
    mock_market_provider.get_daily_bars.return_value = df

    transformed = pipeline.transform(raw_data)

    assert len(transformed) == 1
    record = transformed[0]

    # Calculate expected fees
    expected_fees = (entry_price * qty * expected_fee_pct) + (
        exit_price * qty * expected_fee_pct
    )

    assert (
        record["theoretical_fees_usd"] == pytest.approx(expected_fees)
    ), f"Expected fees_usd == {expected_fees} for {asset_class}, got {record['theoretical_fees_usd']}"
