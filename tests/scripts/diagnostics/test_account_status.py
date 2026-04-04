from unittest.mock import MagicMock, patch

from alpaca.trading.models import Position
from crypto_signals.scripts.diagnostics.account_status import (
    get_account_summary,
    write_report,
)


def test_get_account_summary_mocked():
    """Test get_account_summary with mocked Alpaca client."""
    mock_settings = MagicMock()
    mock_settings.ALPACA_API_KEY = "test_key"
    mock_settings.ALPACA_SECRET_KEY = "test_secret"
    mock_settings.is_paper_trading = True

    mock_account = MagicMock()
    mock_account.status = "ACTIVE"
    mock_account.cash = "10000.0"
    mock_account.portfolio_value = "15000.0"
    mock_account.equity = "15000.0"
    mock_account.buying_power = "20000.0"
    mock_account.last_equity = "14000.0"

    mock_pos = MagicMock(spec=Position)
    mock_pos.symbol = "BTC/USD"
    mock_pos.qty = "1.0"
    mock_pos.avg_entry_price = "50000.0"
    mock_pos.current_price = "60000.0"
    mock_pos.market_value = "60000.0"
    mock_pos.unrealized_pl = "10000.0"
    mock_pos.unrealized_plpc = "0.2"

    with (
        patch("crypto_signals.config.get_settings", return_value=mock_settings),
        patch("alpaca.trading.client.TradingClient") as mock_client_cls,
    ):
        mock_client = mock_client_cls.return_value
        mock_client.get_account.return_value = mock_account
        mock_client.get_all_positions.return_value = [mock_pos]

        summary = get_account_summary()

        assert summary["cash"] == 10000.0, "Cash balance mismatch in summary"
        assert (
            summary["portfolio_value"] == 15000.0
        ), "Portfolio value mismatch in summary"
        assert len(summary["positions"]) == 1, "Expected exactly 1 position in summary"
        assert (
            summary["positions"][0]["symbol"] == "BTC/USD"
        ), "Position symbol mismatch in summary"


def test_write_report(tmp_path):
    """Test write_report generates a file."""
    summary = {
        "timestamp": "2024-01-22T00:00:00Z",
        "account_status": "ACTIVE",
        "is_paper": True,
        "cash": 1000.0,
        "portfolio_value": 2000.0,
        "equity": 2000.0,
        "buying_power": 4000.0,
        "last_equity": 1500.0,
        "open_positions_count": 0,
        "positions": [],
        "total_unrealized_pl": 0.0,
    }
    output_path = tmp_path / "report.txt"
    write_report(summary, output_path)

    assert output_path.exists(), "Report file was not created"
    content = output_path.read_text()
    assert (
        "ALPACA ACCOUNT STATUS REPORT" in content
    ), "Report title missing in generated file"
    assert "Cash: $1,000.00" in content, "Formatted cash value missing in report"
