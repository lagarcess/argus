from unittest.mock import MagicMock, patch

from crypto_signals.scripts.diagnostics.state_analysis import (
    analyze_firestore_state,
    write_report,
)


def test_analyze_firestore_state_mocked():
    """Test analyze_firestore_state with mocked Firestore client."""
    mock_settings = MagicMock()
    mock_settings.GOOGLE_CLOUD_PROJECT = "test-project"
    mock_settings.ENVIRONMENT = "PROD"

    mock_doc = MagicMock()
    mock_doc.to_dict.return_value = {"status": "OPEN", "symbol": "BTC/USD"}
    mock_doc.id = "test_id"

    with (
        patch("crypto_signals.config.get_settings", return_value=mock_settings),
        patch("google.cloud.firestore.Client") as mock_db_cls,
    ):
        mock_db = mock_db_cls.return_value
        # Mocking the stream for different collections
        mock_db.collection.return_value.where.return_value.stream.return_value = [
            mock_doc
        ]

        summary = analyze_firestore_state()

        assert summary["environment"] == "PROD", "Environment mismatch in summary"
        assert (
            summary["positions"]["OPEN"] == 1
        ), "Incorrect count of OPEN positions in summary"
        assert (
            len(summary["open_positions"]) == 1
        ), "Incorrect length of open_positions list in summary"


def test_write_report_state(tmp_path):
    """Test write_report for state analysis."""
    summary = {
        "timestamp": "2024-01-22T00:00:00Z",
        "environment": "PROD",
        "positions_collection": "live_positions",
        "signals_collection": "live_signals",
        "positions": {"OPEN": 5, "CLOSED": 10},
        "signals": {
            "WAITING": 2,
            "TP1_HIT": 0,
            "TP2_HIT": 0,
            "TP3_HIT": 0,
            "INVALIDATED": 0,
            "EXPIRED": 18,
        },
        "open_positions": [],
        "active_signals": [],
    }
    output_path = tmp_path / "state_report.txt"
    write_report(summary, output_path)

    assert output_path.exists(), "Report file was not created"
    content = output_path.read_text(encoding="utf-8")
    assert "FIRESTORE STATE ANALYSIS REPORT" in content, "Report title missing in content"
    assert "Environment: PROD" in content, "Environment info missing in report content"
