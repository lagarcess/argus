"""Unit tests for Account Snapshot Pipeline."""

from unittest.mock import MagicMock, patch

import pytest
from alpaca.trading.models import PortfolioHistory, TradeAccount
from crypto_signals.pipelines.account_snapshot import AccountSnapshotPipeline

# -----------------------------------------------------------------------------
# FIXTURES
# -----------------------------------------------------------------------------


@pytest.fixture
def mock_settings():
    """Mock the settings object."""
    with patch("crypto_signals.pipelines.base.get_settings") as mock:
        mock.return_value.GOOGLE_CLOUD_PROJECT = "test-project"
        mock.return_value.ENVIRONMENT = "PROD"
        yield mock


@pytest.fixture
def mock_alpaca():
    """Mock the Alpaca trading client."""
    with patch("crypto_signals.pipelines.account_snapshot.get_trading_client") as mock:
        yield mock.return_value


@pytest.fixture
def mock_bq():
    """Mock the BigQuery client."""
    with patch("google.cloud.bigquery.Client") as mock:
        yield mock.return_value


@pytest.fixture
def pipeline(mock_settings, mock_alpaca, mock_bq):
    """Create an AccountSnapshotPipeline instance for testing."""
    return AccountSnapshotPipeline()


# -----------------------------------------------------------------------------
# TESTS
# -----------------------------------------------------------------------------


def test_init(pipeline):
    """Test pipeline initialization."""
    assert pipeline.job_name == "account_snapshot"
    assert pipeline.fact_table_id == "test-project.crypto_analytics.snapshot_accounts"


def test_extract(pipeline, mock_alpaca):
    """Test that extract calls Alpaca with correct parameters."""
    mock_account = MagicMock(spec=TradeAccount)
    mock_history = MagicMock(spec=PortfolioHistory)

    mock_alpaca.get_account.return_value = mock_account
    mock_alpaca.get_portfolio_history.return_value = mock_history

    result = pipeline.extract()

    assert len(result) == 1
    assert result[0]["account"] == mock_account
    assert result[0]["history"] == mock_history

    from alpaca.trading.requests import GetPortfolioHistoryRequest

    mock_alpaca.get_portfolio_history.assert_called_once()
    # Arg check: Ensure it was called with a GetPortfolioHistoryRequest
    args, _ = mock_alpaca.get_portfolio_history.call_args
    assert isinstance(args[0], GetPortfolioHistoryRequest)
    assert args[0].period == "1A"


def test_transform_calculation(pipeline):
    """Test the math: Drawdown, Calmar, and Peak Equity (> 30 days coverage)."""
    mock_account = MagicMock()
    mock_account.id = "acc_123"
    mock_account.equity = "100000.0"
    mock_account.cash = "50000.0"

    # === NEW FIELDS (Issue 116) ===
    # Buying Power / Leverage
    mock_account.buying_power = "200000.0"
    mock_account.regt_buying_power = "100000.0"
    mock_account.daytrading_buying_power = "400000.0"
    mock_account.non_marginable_buying_power = "30000.0"  # Crypto BP
    mock_account.multiplier = "4.0"

    # Margin Risk
    mock_account.initial_margin = "25000.0"
    mock_account.maintenance_margin = "20000.0"

    # Portfolio Value
    mock_account.last_equity = "99000.0"
    mock_account.long_market_value = "50000.0"
    mock_account.short_market_value = "0.0"

    # Status Flags
    mock_account.currency = "USD"
    mock_account.status = "ACTIVE"
    mock_account.pattern_day_trader = True  # Boolean in SDK (sometimes) or string "true"
    mock_account.daytrade_count = 3
    mock_account.account_blocked = False
    mock_account.trade_suspended_by_user = False
    mock_account.trading_blocked = False
    mock_account.transfers_blocked = False
    mock_account.sma = "120.5"

    # Need > 30 items to trigger Calmar calculation
    # Simulate 30 days of growth then a dip
    # Start 80k -> Peak 120k -> Current 100k

    # 29 days of flat 80k
    equity_series = [80000.0] * 29
    # Add peak and current structure
    # 80k -> 120k -> 90k (MaxDD 25%) -> 100k
    equity_series.extend([120000.0, 90000.0, 95000.0])

    # Total Len = 32 (>30).
    # Start = 80k. Current 100k.
    # Return = 25% (0.25).
    # Annualized (Trading 252): ( (100/80) ^ (252 / 32) ) - 1
    # = (1.25 ^ 7.875) - 1 ... roughly 4.8 (480%)

    # Max DD: Peak 120 -> 90 = 25%.
    # Current DD: (120 - 100) / 120 = 16.67%.
    # So denominator = 0.25.

    # Calmar = Annualized / MaxDD.

    expected_annual_return = ((100000.0 / 80000.0) ** (252 / 32)) - 1
    expected_calmar = expected_annual_return / 0.25

    mock_history = MagicMock()
    mock_history.equity = equity_series
    mock_history.timestamp = None

    raw_data = [{"account": mock_account, "history": mock_history}]

    transformed = pipeline.transform(raw_data)
    record = transformed[0]

    assert record["account_id"] == "acc_123"
    assert record["drawdown_pct"] == 16.6667

    # Verify Calmar matches logic
    assert record["calmar_ratio"] == round(expected_calmar, 2)

    # === VERIFY NEW FIELDS ===
    assert record["buying_power"] == 200000.0
    assert record["crypto_buying_power"] == 30000.0  # Mapped from non_marginable
    assert record["pattern_day_trader"] is True
    assert record["daytrade_count"] == 3
    assert record["multiplier"] == 4.0
    assert record["currency"] == "USD"
    assert record["sma"] == 120.5


def test_calmar_guardrail_new_account(pipeline):
    """Test Guardrail: < 30 days history -> Calmar 0.0."""
    mock_account = MagicMock()
    mock_account.id = "acc_new"
    mock_account.equity = "100000.0"
    mock_account.cash = "100000.0"

    # 29 days Only
    equity_series = [100000.0] * 29
    mock_history = MagicMock()
    mock_history.equity = equity_series

    raw_data = [{"account": mock_account, "history": mock_history}]

    transformed = pipeline.transform(raw_data)
    record = transformed[0]

    assert record["calmar_ratio"] == 0.0
    # Drawdown should still calculate (0.0 here)
    assert record["drawdown_pct"] == 0.0


def test_calmar_guardrail_perfect_trading(pipeline):
    """Test Guardrail: Max Drawdown 0 -> Calmar 0.0."""
    mock_account = MagicMock()
    mock_account.id = "acc_perfect"
    mock_account.equity = "150000.0"  # Up from 100k

    # 35 days of pure up only
    # Start 100k -> ... -> 150k
    equity_series = [100000.0 + (i * 1000) for i in range(35)]
    # Peak is 134000 (last in history) or current 150000.
    # Current 150000. All history < 150000.
    # Max DD = 0.

    mock_history = MagicMock()
    mock_history.equity = equity_series

    raw_data = [{"account": mock_account, "history": mock_history}]

    transformed = pipeline.transform(raw_data)
    record = transformed[0]

    # Return is positive, but MaxDD is 0. Calmar should be 0.0 (or capped?)
    # My logic says guardrail sets to 0.0 if MaxDD == 0.
    assert record["calmar_ratio"] == 0.0
    assert record["drawdown_pct"] == 0.0


def test_calmar_guardrail_unfunded(pipeline):
    """Test Guardrail: Start Equity <= 0 -> Calmar 0.0."""
    mock_account = MagicMock()
    mock_account.id = "acc_weird"
    mock_account.equity = "100.0"

    # 35 days but start was 0 (unfunded)
    equity_series = [0.0] * 34 + [100.0]

    mock_history = MagicMock()
    mock_history.equity = equity_series

    raw_data = [{"account": mock_account, "history": mock_history}]

    transformed = pipeline.transform(raw_data)
    record = transformed[0]

    assert record["calmar_ratio"] == 0.0


def test_drawdown_zero_equity(pipeline):
    """Test Guardrail: Peak Equity <= 0 -> Drawdown 0.0."""
    mock_account = MagicMock()
    mock_account.id = "acc_broke"
    mock_account.equity = "0.0"  # Broke

    # History also 0
    mock_history = MagicMock()
    mock_history.equity = [0.0] * 35

    raw_data = [{"account": mock_account, "history": mock_history}]

    transformed = pipeline.transform(raw_data)
    record = transformed[0]

    assert record["drawdown_pct"] == 0.0
    assert record["equity"] == 0.0


def test_pipeline_run_validates_schema(pipeline):
    """Test that run() calls validation and merge."""
    from datetime import date

    with (
        patch.object(pipeline, "extract") as mock_ext,
        patch.object(pipeline, "transform") as mock_trans,
        patch.object(pipeline, "_merge_via_temp_table"),
        patch.object(pipeline, "cleanup") as mock_clean,
        # Mock guardian validation to avoid schema errors during test
        patch.object(pipeline.guardian, "validate_schema") as mock_validate,
    ):
        mock_ext.return_value = ["raw"]
        # Must return valid model dicts for base class run() validation
        mock_trans.return_value = [
            {
                "ds": date(2024, 1, 1),
                "account_id": "acc_123",
                "equity": 100.0,
                "cash": 100.0,
                "calmar_ratio": 1.0,
                "drawdown_pct": 0.0,
            }
        ]

        pipeline.run()

        mock_validate.assert_called_once()
        mock_ext.assert_called_once()
        # cleanup IS called now because we removed the run() override
        mock_clean.assert_called_once()
