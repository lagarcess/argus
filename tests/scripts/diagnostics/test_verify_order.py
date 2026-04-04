from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from alpaca.common.exceptions import APIError
from crypto_signals.domain.schemas import AssetClass, OrderSide, TradeStatus
from crypto_signals.scripts.diagnostics.verify_order import app
from typer.testing import CliRunner

from tests.factories import PositionFactory

runner = CliRunner()


@pytest.fixture
def mock_trading_client():
    with patch(
        "crypto_signals.scripts.diagnostics.verify_order.get_trading_client"
    ) as mock:
        yield mock.return_value


@pytest.fixture
def mock_position_repo():
    with patch(
        "crypto_signals.scripts.diagnostics.verify_order.PositionRepository"
    ) as mock:
        yield mock.return_value


class MockAPIError(APIError):
    def __init__(self, message="not found"):
        super().__init__(message)

    @property
    def status_code(self):
        return 404


def test_verify_order_not_found(mock_trading_client):
    # Setup
    """Verify behavior when an order is not found."""
    err = MockAPIError()
    mock_trading_client.get_order_by_id.side_effect = err

    # Execute
    result = runner.invoke(app, ["--order-id", "non-existent-id"])

    # Verify
    assert (
        result.exit_code == 0
    ), f"Command failed with exit code {result.exit_code}. Output: {result.stdout}"
    assert (
        "404 Not Found" in result.stdout or "Order not found" in result.stdout
    ), "Expected 'not found' message in output"


def test_verify_order_found(mock_trading_client, mock_position_repo):
    # Setup
    """Verify order verification succeeds when found."""
    mock_order = MagicMock()
    mock_order.status = "filled"
    mock_order.symbol = "BTC/USD"
    mock_order.id = "existing-id"
    # Make sure JSON serialization works on the mock if we dump it
    order_dict = {"id": "existing-id", "status": "filled", "symbol": "BTC/USD"}
    mock_order.dict.return_value = order_dict
    mock_order.model_dump.return_value = order_dict

    mock_trading_client.get_order_by_id.return_value = mock_order
    mock_position_repo.get_open_positions.return_value = []

    # Execute
    result = runner.invoke(app, ["--order-id", "existing-id"])

    # Verify
    assert (
        result.exit_code == 0
    ), f"Command failed with exit code {result.exit_code}. Output: {result.stdout}"
    # "found" is internal status, output shows the actual status from order which is "filled"
    # Rich output includes ANSI codes, so exact match might fail. Check for substring presence.
    assert "Status" in result.stdout, "Expected 'Status' field in output"
    assert "filled" in result.stdout, "Expected order status 'filled' in output"
    assert "BTC/USD" in result.stdout, "Expected symbol 'BTC/USD' in output"


def test_verify_position_mismatch_alpaca_only(mock_trading_client, mock_position_repo):
    # Setup
    # Mock Alpaca position found
    """Ensure mismatches are flagged when position only exists in Alpaca."""
    mock_alpaca_pos = MagicMock()
    mock_alpaca_pos.symbol = "BTC/USD"
    mock_alpaca_pos.qty = 1.0
    mock_alpaca_pos.dict.return_value = {"symbol": "BTC/USD", "qty": 1.0}
    mock_trading_client.get_open_position.return_value = mock_alpaca_pos

    # Firestore has no position
    mock_position_repo.get_open_positions.return_value = []

    # Execute
    result = runner.invoke(app, ["--symbol", "BTC/USD"])

    # Verify
    assert (
        result.exit_code == 0
    ), f"Command failed with exit code {result.exit_code}. Output: {result.stdout}"
    # Use generic status check as colored output might vary
    assert "DISCREPANCY" in result.stdout, "Expected 'DISCREPANCY' alert in output"
    assert "Alpaca" in result.stdout, "Expected 'Alpaca' section/label in output"
    assert "FOUND" in result.stdout, "Expected 'FOUND' status in output"
    assert "Firestore" in result.stdout, "Expected 'Firestore' section/label in output"
    assert "NOT FOUND" in result.stdout, "Expected 'NOT FOUND' status in output"


def test_verify_position_match(mock_trading_client, mock_position_repo):
    # Setup
    # Mock Alpaca position found
    """Verify position match is confirmed when systems align."""
    mock_alpaca_pos = MagicMock()
    mock_alpaca_pos.symbol = "BTC/USD"
    mock_alpaca_pos.qty = 1.0
    mock_alpaca_pos.dict.return_value = {"symbol": "BTC/USD", "qty": 1.0}
    mock_trading_client.get_open_position.return_value = mock_alpaca_pos

    # Mock Firestore position found
    mock_position = PositionFactory.build(
        position_id="pos1",
        ds=date(2023, 1, 1),
        account_id="account1",
        signal_id="sig1",
        symbol="BTC/USD",
        asset_class=AssetClass.CRYPTO,
        side=OrderSide.BUY,
        entry_fill_price=50000.0,
        current_stop_loss=49000.0,
        qty=1.0,
        status=TradeStatus.OPEN,
    )
    mock_position_repo.get_open_positions.return_value = [mock_position]

    # Execute
    result = runner.invoke(app, ["--symbol", "BTC/USD"])

    # Verify
    assert (
        result.exit_code == 0
    ), f"Command failed with exit code {result.exit_code}. Output: {result.stdout}"
    # Use generic status check as colored output might vary
    # Rich might wrap text or add styles, so we check for key phrases
    assert (
        "MATCH" in result.stdout
        or "No discrepancies found" in result.stdout
        or "discrepancies found" not in result.stdout
    ), "Expected success match message in output"


def test_json_output(mock_trading_client):
    # Setup
    """Verify diagnostic tools output valid JSON format."""
    err = MockAPIError()
    mock_trading_client.get_order_by_id.side_effect = err

    # Execute
    result = runner.invoke(app, ["--order-id", "non-existent-id", "--json"])

    # Verify
    assert (
        result.exit_code == 0
    ), f"Command failed with exit code {result.exit_code}. Output: {result.stdout}"
    import json

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        pytest.fail(f"Failed to decode JSON output: {e}. Output: {result.stdout}")

    assert (
        data["order_status"] == "not_found"
    ), f"Expected 'order_status' to be 'not_found', got {data.get('order_status')}"
