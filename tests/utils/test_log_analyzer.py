"""
Tests for the Cloud Run Log Analyzer utility.
"""

from unittest.mock import MagicMock, patch

import pytest
from crypto_signals.utils.workflow_log_analyzer import app
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture
def mock_gcp_client():
    """Mocks the Google Cloud Logging client."""
    with patch("google.cloud.logging.Client") as mock_client_class:
        mock_client_instance = mock_client_class.return_value

        # Sample log entries to be returned by the mock
        mock_client_instance.list_entries.return_value = [
            MagicMock(
                severity="ERROR",
                timestamp="2023-10-27T10:00:00Z",
                payload={
                    "message": "Critical error foo",
                    "context": {"signal_id": "123"},
                },
            ),
            MagicMock(
                severity="CRITICAL",
                timestamp="2023-10-27T11:00:00Z",
                payload={"message": "Zombie detected", "context": {"zombie_id": "abc"}},
            ),
            MagicMock(
                severity="WARNING",
                timestamp="2023-10-27T12:00:00Z",
                payload="This is a text payload warning.",
            ),
            MagicMock(
                severity="ERROR",
                timestamp="2023-10-27T13:00:00Z",
                payload={"message": "Orphan found", "context": {"orphan_id": "xyz"}},
            ),
        ]
        yield mock_client_instance


class TestLogAnalyzer:
    @patch("crypto_signals.utils.workflow_log_analyzer.logger.info")
    def test_analyze_command_generates_correct_summary_and_json_report(
        self, mock_logger_info: MagicMock, mock_gcp_client: MagicMock
    ):
        """
        Tests that the analyze command correctly processes logs and generates
        the expected summary and JSON report for Zombie and Orphan events.
        """
        result = runner.invoke(app, ["--service", "test-service", "--hours", "12"])

        assert result.exit_code == 0

        # Get all calls to the mocked logger.info
        all_calls = " ".join([call[0][0] for call in mock_logger_info.call_args_list])

        assert "CRITICAL Errors: 1" in all_calls
        assert "ERRORs: 2" in all_calls
        assert '"event_type": "Zombie"' in all_calls
        assert '"zombie_id": "abc"' in all_calls
        assert '"event_type": "Orphan"' in all_calls
        assert '"orphan_id": "xyz"' in all_calls
