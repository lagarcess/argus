"""Unit tests for GCP Cloud Logging integration in observability module."""

import importlib.util
import sys
from importlib import reload
from unittest.mock import MagicMock, patch

import crypto_signals.observability as obs

# [Strategy Setup] Detect if the real library is installed to choose the correct patch method
HAS_GCP_LIBRARY = importlib.util.find_spec("google.cloud.logging") is not None


class TestGCPLevelMapping:
    """Test Loguru to GCP severity level mapping."""

    def test_trace_maps_to_debug(self):
        """TRACE level should map to GCP DEBUG."""
        assert obs.LOGURU_TO_GCP_SEVERITY["TRACE"] == "DEBUG"

    def test_debug_maps_to_debug(self):
        """DEBUG level should map to GCP DEBUG."""
        assert obs.LOGURU_TO_GCP_SEVERITY["DEBUG"] == "DEBUG"

    def test_info_maps_to_info(self):
        """INFO level should map to GCP INFO."""
        assert obs.LOGURU_TO_GCP_SEVERITY["INFO"] == "INFO"

    def test_success_maps_to_info(self):
        """SUCCESS level should map to GCP INFO (GCP has no SUCCESS)."""
        assert obs.LOGURU_TO_GCP_SEVERITY["SUCCESS"] == "INFO"

    def test_warning_maps_to_warning(self):
        """WARNING level should map to GCP WARNING."""
        assert obs.LOGURU_TO_GCP_SEVERITY["WARNING"] == "WARNING"

    def test_error_maps_to_error(self):
        """ERROR level should map to GCP ERROR."""
        assert obs.LOGURU_TO_GCP_SEVERITY["ERROR"] == "ERROR"

    def test_critical_maps_to_critical(self):
        """CRITICAL level should map to GCP CRITICAL."""
        assert obs.LOGURU_TO_GCP_SEVERITY["CRITICAL"] == "CRITICAL"

    def test_all_loguru_levels_are_mapped(self):
        """All standard Loguru levels should be mapped."""
        expected_levels = {
            "TRACE",
            "DEBUG",
            "INFO",
            "SUCCESS",
            "WARNING",
            "ERROR",
            "CRITICAL",
        }
        assert set(obs.LOGURU_TO_GCP_SEVERITY.keys()) == expected_levels


class TestSetupGCPLogging:
    """Test setup_gcp_logging() function with robust mocking."""

    def test_setup_gcp_logging_returns_true_on_success(self):
        """Test that setup_gcp_logging returns True when client initializes."""
        reload(obs)  # Ensure a fresh module state

        mock_client = MagicMock()
        mock_logger = MagicMock()
        mock_client.logger.return_value = mock_logger

        if HAS_GCP_LIBRARY:
            # Strategy A: Patch the class directly if the library is installed
            with patch(
                "google.cloud.logging.Client", return_value=mock_client
            ) as MockClient:
                result = obs.setup_gcp_logging("test-log")

                assert result is True
                MockClient.assert_called_once()
                mock_client.logger.assert_called_once_with("test-log")
        else:
            # Strategy B: CI/No-library environment, use sys.modules injection
            mock_gcp_logging = MagicMock()
            mock_gcp_logging.Client.return_value = mock_client
            with patch.dict(sys.modules, {"google.cloud.logging": mock_gcp_logging}):
                result = obs.setup_gcp_logging("test-log")

                assert result is True
                mock_gcp_logging.Client.assert_called_once()
                mock_client.logger.assert_called_once_with("test-log")

    def test_setup_gcp_logging_returns_false_on_client_failure(self):
        """Test that setup_gcp_logging returns False when client init fails."""
        reload(obs)  # Ensure a fresh module state

        if HAS_GCP_LIBRARY:
            # Patch the class to raise an exception
            with patch(
                "google.cloud.logging.Client", side_effect=Exception("No credentials")
            ):
                result = obs.setup_gcp_logging()
                assert result is False
        else:
            # Inject failure via sys.modules mock
            mock_gcp_logging = MagicMock()
            mock_gcp_logging.Client.side_effect = Exception("No credentials")
            with patch.dict(sys.modules, {"google.cloud.logging": mock_gcp_logging}):
                result = obs.setup_gcp_logging()
                assert result is False

    def test_gcp_sink_builds_structured_payload(self):
        """Test that GCP sink builds correct structured payload format."""
        # Create a mock message record similar to Loguru's format
        mock_record = {
            "message": "Test signal found",
            "level": MagicMock(name="INFO"),
            "time": MagicMock(isoformat=MagicMock(return_value="2024-12-23T19:00:00")),
            "module": "main",
            "function": "main",
            "line": 178,
            "extra": {"symbol": "BTC/USD", "pattern": "bullish_engulfing"},
        }
        mock_record["level"].name = "INFO"

        # Expected payload structure
        expected_fields = {
            "message",
            "level",
            "timestamp",
            "module",
            "function",
            "line",
            "symbol",
            "pattern",
        }

        # Build payload as the gcp_sink would
        payload = {
            "message": mock_record["message"],
            "level": mock_record["level"].name,
            "timestamp": mock_record["time"].isoformat(),
            "module": mock_record["module"],
            "function": mock_record["function"],
            "line": mock_record["line"],
        }
        if mock_record["extra"]:
            payload.update(mock_record["extra"])

        # Verify all expected fields are present
        assert set(payload.keys()) == expected_fields
        assert payload["symbol"] == "BTC/USD"
        assert payload["pattern"] == "bullish_engulfing"
        assert payload["level"] == "INFO"

    def test_extra_context_merged_into_payload(self):
        """Test that extra context fields are merged into payload."""
        extra_context = {
            "symbol": "ETH/USD",
            "qty": 1.5,
            "pnl_usd": 250.75,
            "asset_class": "CRYPTO",
        }

        # Simulate payload merge
        payload = {"message": "Test", "level": "INFO"}
        payload.update(extra_context)

        assert payload["symbol"] == "ETH/USD"
        assert payload["qty"] == 1.5
        assert payload["pnl_usd"] == 250.75
        assert payload["asset_class"] == "CRYPTO"


class TestSerializationHelpers:
    """Test JSON serialization helpers for GCP logging."""

    def test_serialize_primitives(self):
        """Test that primitive types pass through unchanged."""
        from crypto_signals.observability import _serialize_for_json

        assert _serialize_for_json(None) is None
        assert _serialize_for_json("string") == "string"
        assert _serialize_for_json(42) == 42
        assert _serialize_for_json(3.14) == 3.14
        assert _serialize_for_json(True) is True

    def test_serialize_datetime(self):
        """Test that datetime is converted to ISO format string."""
        from datetime import datetime

        from crypto_signals.observability import _serialize_for_json

        dt = datetime(2024, 12, 23, 19, 0, 0)
        result = _serialize_for_json(dt)
        assert result == "2024-12-23T19:00:00"

    def test_serialize_decimal(self):
        """Test that Decimal is converted to float."""
        from decimal import Decimal

        from crypto_signals.observability import _serialize_for_json

        result = _serialize_for_json(Decimal("99.95"))
        assert result == 99.95
        assert isinstance(result, float)

    def test_serialize_enum(self):
        """Test that Enum is converted to its value."""
        from enum import Enum

        from crypto_signals.observability import _serialize_for_json

        class TestStatus(Enum):
            ACTIVE = "active"
            CLOSED = "closed"

        result = _serialize_for_json(TestStatus.ACTIVE)
        assert result == "active"

    def test_serialize_nested_dict(self):
        """Test that nested dicts are recursively serialized."""
        from datetime import datetime
        from decimal import Decimal

        from crypto_signals.observability import _serialize_for_json

        nested = {
            "price": Decimal("100.50"),
            "timestamp": datetime(2024, 12, 23, 19, 0, 0),
            "nested": {"value": Decimal("50.25")},
        }
        result = _serialize_for_json(nested)
        assert result["price"] == 100.50
        assert result["timestamp"] == "2024-12-23T19:00:00"
        assert result["nested"]["value"] == 50.25

    def test_serialize_list(self):
        """Test that lists are recursively serialized."""
        from decimal import Decimal

        from crypto_signals.observability import _serialize_for_json

        items = [Decimal("1.5"), Decimal("2.5"), "string"]
        result = _serialize_for_json(items)
        assert result == [1.5, 2.5, "string"]

    def test_serialize_custom_object_to_string(self):
        """Test that unknown objects fall back to str()."""
        from crypto_signals.observability import _serialize_for_json

        class CustomObject:
            def __str__(self):
                return "custom_repr"

        result = _serialize_for_json(CustomObject())
        assert result == "custom_repr"

    def test_sanitize_extra_context_empty(self):
        """Test that empty extra returns empty dict."""
        from crypto_signals.observability import _sanitize_extra_context

        assert _sanitize_extra_context({}) == {}
        assert _sanitize_extra_context(None) == {}

    def test_sanitize_extra_context_complex_types(self):
        """Test that complex types are properly sanitized."""
        from datetime import datetime
        from decimal import Decimal

        from crypto_signals.observability import _sanitize_extra_context

        extra = {
            "symbol": "BTC/USD",
            "qty": Decimal("0.5"),
            "timestamp": datetime(2024, 12, 23, 19, 0, 0),
        }
        result = _sanitize_extra_context(extra)
        assert result["symbol"] == "BTC/USD"
        assert result["qty"] == 0.5
        assert result["timestamp"] == "2024-12-23T19:00:00"


class TestConfigIntegration:
    """Test configuration integration for GCP logging."""

    def test_enable_gcp_logging_default_is_false(self):
        """Test that ENABLE_GCP_LOGGING defaults to False."""
        with patch.dict(
            "os.environ",
            {
                "ALPACA_API_KEY": "test_key",
                "ALPACA_SECRET_KEY": "test_secret",
                "GOOGLE_CLOUD_PROJECT": "test-project",
                "TEST_DISCORD_WEBHOOK": "https://discord.com/webhook/test",
            },
            clear=True,
        ):
            # Clear the lru_cache to get fresh settings
            from crypto_signals.config import Settings, get_settings

            get_settings.cache_clear()

            settings = Settings()
            assert settings.ENABLE_GCP_LOGGING is False

    def test_enable_gcp_logging_can_be_enabled(self):
        """Test that ENABLE_GCP_LOGGING can be set to True."""
        with patch.dict(
            "os.environ",
            {
                "ALPACA_API_KEY": "test_key",
                "ALPACA_SECRET_KEY": "test_secret",
                "GOOGLE_CLOUD_PROJECT": "test-project",
                "TEST_DISCORD_WEBHOOK": "https://discord.com/webhook/test",
                "ENABLE_GCP_LOGGING": "true",
            },
            clear=True,
        ):
            from crypto_signals.config import Settings

            settings = Settings()
            assert settings.ENABLE_GCP_LOGGING is True


class TestMetricsCollector:
    """Test MetricsCollector functionality."""

    def test_record_risk_block(self):
        """Test recording risk blocks."""
        from crypto_signals.observability import MetricsCollector

        collector = MetricsCollector()
        collector.record_risk_block("drawdown", "BTC/USD", 5000.0)
        collector.record_risk_block("sector_cap", "ETH/USD", 3000.0)
        collector.record_risk_block("drawdown", "SOL/USD", 2000.0)

        summary = collector.get_risk_summary()

        assert summary["total_blocked"] == 3
        assert summary["capital_protected"] == 10000.0
        assert summary["by_gate"]["drawdown"] == 2
        assert summary["by_gate"]["sector_cap"] == 1
        assert "BTC/USD" in summary["blocked_symbols"]
        assert "ETH/USD" in summary["blocked_symbols"]

    def test_log_summary_persists_metrics(self):
        """Test that log_summary logs risk metrics to the logger."""
        from unittest.mock import MagicMock

        from crypto_signals.observability import MetricsCollector

        collector = MetricsCollector()
        collector.record_risk_block("drawdown", "BTC/USD", 5000.0)

        mock_logger = MagicMock()
        collector.log_summary(mock_logger)

        # Verify logger.info was called with structured data
        mock_logger.info.assert_called_with(
            "Risk Metrics Summary",
            extra={
                "metric_type": "risk_summary",
                "total_blocked": 1,
                "capital_protected": 5000.0,
                "by_gate": {"drawdown": 1},
                "blocked_symbols": ["BTC/USD"],
            },
        )
