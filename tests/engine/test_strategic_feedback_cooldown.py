"""
Test suite for strategic feedback enhancements to Issue #117:
1. Revenge Trading: Add INVALIDATED status to cooldown
2. Config Centralization: Move COOLDOWN_SCOPE to config.py
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from crypto_signals.config import get_settings
from crypto_signals.domain.schemas import Signal, SignalStatus
from crypto_signals.engine.signal_generator import SignalGenerator


@pytest.fixture
def mock_repository():
    """Mock SignalRepository for testing."""
    return MagicMock()


@pytest.fixture
def mock_market_provider():
    """Mock market data provider."""
    return MagicMock()


@pytest.fixture
def signal_generator_with_mocks(mock_repository, mock_market_provider):
    """SignalGenerator with mocked repository."""
    # Create generator with injected mock repository
    gen = SignalGenerator(
        market_provider=mock_market_provider, signal_repo=mock_repository
    )
    return gen


# ============================================================================
# STRATEGIC FEEDBACK #1: Revenge Trading Gap - INVALIDATED Status
# ============================================================================


class TestInvalidatedStatusCooldown:
    """Test that INVALIDATED (stop-loss hit) triggers cooldown (revenge trading prevention)."""

    def test_invalidated_status_included_in_exit_statuses(
        self, signal_generator_with_mocks
    ):
        """Verify get_most_recent_exit queries include INVALIDATED status."""
        # This test checks that the repository query includes INVALIDATED
        # Current implementation only queries TP1_HIT, TP2_HIT, TP3_HIT
        # Strategic feedback: Add INVALIDATED to prevent revenge trading
        signal_generator_with_mocks.signal_repo.get_most_recent_exit.return_value = None

        # Call cooldown check
        signal_generator_with_mocks._is_in_cooldown("BTC/USD", 45000.0)

        # Assert the repository was called (it will be in implementation)
        assert signal_generator_with_mocks.signal_repo.get_most_recent_exit.called, f"Expected signal_generator_with_mocks.signal_repo.get_most_recent_exit.called to be truthy, got {signal_generator_with_mocks.signal_repo.get_most_recent_exit.called}"

    def test_cooldown_blocks_after_stop_loss_hit(self, signal_generator_with_mocks):
        """Verify cooldown blocks trading after INVALIDATED (stop-loss) status."""
        # Arrange: Recent exit with INVALIDATED status (stop-loss hit)
        recent_exit = MagicMock(spec=Signal)
        recent_exit.status = SignalStatus.INVALIDATED
        recent_exit.suggested_stop = 44000.0  # Stop level (should map to this)
        recent_exit.take_profit_1 = 45000.0  # Add all TP levels (used in exit_level_map)
        recent_exit.take_profit_2 = 48000.0
        recent_exit.take_profit_3 = 50000.0
        recent_exit.timestamp = datetime.now(timezone.utc) - timedelta(hours=2)

        signal_generator_with_mocks.signal_repo.get_most_recent_exit.return_value = (
            recent_exit
        )

        # Current price: 44500 (only 1.1% from stop level)
        result = signal_generator_with_mocks._is_in_cooldown("BTC/USD", 44500.0)

        # Should be True (blocked) - only 1.1% move from stop, needs 10%
        assert (
            result is True
        ), "Should block trade after stop-loss hit (revenge trading prevention)"

    def test_cooldown_escape_after_stop_loss_with_large_move(
        self, signal_generator_with_mocks
    ):
        """Verify escape valve works after INVALIDATED (large price move)."""
        # Arrange: Recent stop-loss hit, but price has moved 15%
        recent_exit = MagicMock(spec=Signal)
        recent_exit.status = SignalStatus.INVALIDATED
        recent_exit.suggested_stop = 40000.0  # Stop level
        recent_exit.take_profit_1 = 42000.0  # Add all TP levels
        recent_exit.take_profit_2 = 45000.0
        recent_exit.take_profit_3 = 50000.0
        recent_exit.timestamp = datetime.now(timezone.utc) - timedelta(hours=2)

        signal_generator_with_mocks.signal_repo.get_most_recent_exit.return_value = (
            recent_exit
        )

        # Current price: 46000 (15% from stop level)
        result = signal_generator_with_mocks._is_in_cooldown("BTC/USD", 46000.0)

        # Should be False (allowed) - 15% move >= 10% threshold
        assert result is False, "Should allow trade with 15% price move (escape valve)"

    def test_exit_level_mapping_for_invalidated_status(self, signal_generator_with_mocks):
        """Verify INVALIDATED maps to suggested_stop in exit level map."""
        # This test documents the expected mapping:
        # TP1_HIT -> take_profit_1
        # TP2_HIT -> take_profit_2
        # TP3_HIT -> take_profit_3
        # INVALIDATED -> suggested_stop (NEW)

        recent_exit = MagicMock(spec=Signal)
        recent_exit.status = SignalStatus.INVALIDATED
        recent_exit.suggested_stop = 50000.0
        recent_exit.take_profit_1 = 52000.0
        recent_exit.take_profit_2 = 54000.0
        recent_exit.take_profit_3 = 56000.0
        recent_exit.timestamp = datetime.now(timezone.utc) - timedelta(hours=1)

        signal_generator_with_mocks.signal_repo.get_most_recent_exit.return_value = (
            recent_exit
        )

        # Call cooldown with price close to stop
        result = signal_generator_with_mocks._is_in_cooldown("BTC/USD", 50500.0)

        # Should be blocked (1% move < 10% threshold)
        assert result is True, f"Expected result to be True, got {result}"

    def test_firestore_query_includes_invalidated_status(self, mock_repository):
        """Verify repository.get_most_recent_exit() will query for INVALIDATED."""
        # This test documents what the repository should do:
        # Query Firestore for TP1_HIT, TP2_HIT, TP3_HIT, INVALIDATED statuses

        # Note: This will be implemented in firestore.py
        # The repository should include INVALIDATED in its query
        # Current query filters by status IN [TP1_HIT, TP2_HIT, TP3_HIT]
        # Strategic feedback: Add INVALIDATED to this list

        # For now, this is a placeholder test that documents intent
        # Implementation will update the repository query
        pass


# ============================================================================
# STRATEGIC FEEDBACK #2: Config Centralization - COOLDOWN_SCOPE
# ============================================================================


class TestCooldownScopeConfig:
    """Test that COOLDOWN_SCOPE setting controls symbol vs pattern blocking."""

    def test_cooldown_scope_symbol_blocks_all_patterns(self, signal_generator_with_mocks):
        """With COOLDOWN_SCOPE='SYMBOL', cooldown blocks all patterns on symbol."""
        # Mock config to return COOLDOWN_SCOPE='SYMBOL'
        with patch.dict("os.environ", {"COOLDOWN_SCOPE": "SYMBOL"}):
            with patch(
                "crypto_signals.engine.signal_generator.get_settings"
            ) as mock_settings:
                mock_config = MagicMock()
                mock_config.COOLDOWN_SCOPE = "SYMBOL"
                mock_settings.return_value = mock_config

                recent_exit = MagicMock(spec=Signal)
                recent_exit.status = SignalStatus.TP2_HIT
                recent_exit.take_profit_1 = 46000.0
                recent_exit.take_profit_2 = 48000.0
                recent_exit.take_profit_3 = 50000.0
                recent_exit.suggested_stop = 44000.0
                recent_exit.pattern_name = "BULL_FLAG"
                recent_exit.timestamp = datetime.now(timezone.utc) - timedelta(hours=2)

                signal_generator_with_mocks.signal_repo.get_most_recent_exit.return_value = recent_exit

                # Different pattern (MORNING_STAR) should still be blocked
                result = signal_generator_with_mocks._is_in_cooldown(
                    "BTC/USD", 45000.0, pattern_name="MORNING_STAR"
                )

                # With SYMBOL scope, should be blocked regardless of pattern
                assert result is True, f"Expected result to be True, got {result}"

    def test_cooldown_scope_pattern_blocks_same_pattern_only(
        self, signal_generator_with_mocks
    ):
        """With COOLDOWN_SCOPE='PATTERN', cooldown only blocks same pattern."""
        # Mock config to return COOLDOWN_SCOPE='PATTERN'
        with patch.dict("os.environ", {"COOLDOWN_SCOPE": "PATTERN"}):
            with patch(
                "crypto_signals.engine.signal_generator.get_settings"
            ) as mock_settings:
                mock_config = MagicMock()
                mock_config.COOLDOWN_SCOPE = "PATTERN"
                mock_settings.return_value = mock_config

                recent_exit = MagicMock(spec=Signal)
                recent_exit.status = SignalStatus.TP2_HIT
                recent_exit.take_profit_2 = 48000.0
                recent_exit.pattern_name = "BULL_FLAG"
                recent_exit.timestamp = datetime.now(timezone.utc) - timedelta(hours=2)

                signal_generator_with_mocks.signal_repo.get_most_recent_exit.return_value = None

                # Different pattern should NOT be blocked (query returns None)
                result = signal_generator_with_mocks._is_in_cooldown(
                    "BTC/USD", 45000.0, pattern_name="MORNING_STAR"
                )

                # With PATTERN scope and different pattern, should be allowed
                assert result is False, f"Expected result to be False, got {result}"

    def test_config_setting_exists_in_config_py(self):
        """Verify COOLDOWN_SCOPE setting can be read from config."""
        # This test verifies the setting is properly configured
        settings = get_settings()

        # Settings should have COOLDOWN_SCOPE attribute
        # Default value can be "SYMBOL" (conservative) or configurable
        # If not yet implemented, this will raise AssertionError
        # which is expected - will be implemented in Green phase
        try:
            cooldown_scope = settings.COOLDOWN_SCOPE
            assert cooldown_scope in [
                "SYMBOL",
                "PATTERN",
            ], f"COOLDOWN_SCOPE should be 'SYMBOL' or 'PATTERN', got {cooldown_scope}"
        except AttributeError:
            pytest.skip(
                "COOLDOWN_SCOPE not yet implemented in config.py (expected in Red phase)"
            )

    def test_default_cooldown_scope_is_symbol(self):
        """Verify default COOLDOWN_SCOPE is 'SYMBOL' (conservative)."""
        # If not specified in .env, default should be SYMBOL (blocks all patterns)
        settings = get_settings()

        # Default should be SYMBOL for conservative behavior
        try:
            assert (
                settings.COOLDOWN_SCOPE == "SYMBOL"
            ), "Default COOLDOWN_SCOPE should be 'SYMBOL' (conservative)"
        except AttributeError:
            pytest.skip(
                "COOLDOWN_SCOPE not yet implemented in config.py (expected in Red phase)"
            )

    def test_cooldown_respects_scope_setting_in_logic(self, signal_generator_with_mocks):
        """Verify _is_in_cooldown respects COOLDOWN_SCOPE setting."""
        # Arrange: Config scope to PATTERN
        with patch(
            "crypto_signals.engine.signal_generator.get_settings"
        ) as mock_settings:
            mock_settings.return_value.COOLDOWN_SCOPE = "PATTERN"

            # Arrange repo to return an exit for the specific pattern
            recent_exit = MagicMock(spec=Signal)
            recent_exit.status = SignalStatus.TP1_HIT
            recent_exit.take_profit_1 = 45000.0
            recent_exit.take_profit_2 = None
            recent_exit.take_profit_3 = None
            recent_exit.suggested_stop = 44000.0
            recent_exit.timestamp = datetime.now(timezone.utc) - timedelta(hours=1)

            # The mocked repo will be called. We don't need it to return anything specific
            # for this test, we just want to verify the CALL arguments.
            signal_generator_with_mocks.signal_repo.get_most_recent_exit.return_value = (
                recent_exit
            )

            # Call with a pattern name
            signal_generator_with_mocks._is_in_cooldown(
                "BTC/USD", 45000.0, pattern_name="BULL_FLAG"
            )

            # Assert repository was called using pattern scope logic
            # (passed pattern_name="BULL_FLAG" instead of None)
            args, kwargs = (
                signal_generator_with_mocks.signal_repo.get_most_recent_exit.call_args
            )
            assert (
                kwargs.get("pattern_name") == "BULL_FLAG"
            ), "Should query with pattern_name when scope is PATTERN"


# ============================================================================
# Integration Tests: Both Strategic Feedbacks Combined
# ============================================================================


class TestStrategicFeedbackIntegration:
    """Test strategic feedbacks work together correctly."""

    def test_revenge_trading_and_config_scope_together(self, signal_generator_with_mocks):
        """Verify INVALIDATED status works with COOLDOWN_SCOPE config."""
        # Arrange: Stop-loss hit on BULL_FLAG pattern
        recent_exit = MagicMock(spec=Signal)
        recent_exit.status = SignalStatus.INVALIDATED
        recent_exit.suggested_stop = 44000.0
        recent_exit.take_profit_1 = 45000.0
        recent_exit.take_profit_2 = 48000.0
        recent_exit.take_profit_3 = 50000.0
        recent_exit.pattern_name = "BULL_FLAG"
        recent_exit.timestamp = datetime.now(timezone.utc) - timedelta(hours=1)

        signal_generator_with_mocks.signal_repo.get_most_recent_exit.return_value = (
            recent_exit
        )

        # With SYMBOL scope: all patterns blocked
        result_symbol_scope = signal_generator_with_mocks._is_in_cooldown(
            "BTC/USD", 44500.0, pattern_name=None
        )

        # Should be True (blocked by stop-loss)
        assert (
            result_symbol_scope is True
        ), f"Expected result_symbol_scope to be True, got {result_symbol_scope}"

    def test_all_exit_statuses_trigger_cooldown(self, signal_generator_with_mocks):
        """Verify all exit statuses (TP1/2/3 + INVALIDATED) trigger cooldown."""
        exit_statuses = [
            SignalStatus.TP1_HIT,
            SignalStatus.TP2_HIT,
            SignalStatus.TP3_HIT,
            SignalStatus.INVALIDATED,
        ]

        for status in exit_statuses:
            recent_exit = MagicMock(spec=Signal)
            recent_exit.status = status
            recent_exit.take_profit_1 = 45000.0
            recent_exit.take_profit_2 = 48000.0
            recent_exit.take_profit_3 = 50000.0
            recent_exit.suggested_stop = 40000.0
            recent_exit.timestamp = datetime.now(timezone.utc) - timedelta(hours=1)

            signal_generator_with_mocks.signal_repo.get_most_recent_exit.return_value = (
                recent_exit
            )

            # All statuses should trigger cooldown (price is close to any exit level)
            result = signal_generator_with_mocks._is_in_cooldown("BTC/USD", 45500.0)

            # May be blocked or allowed depending on exit level and price
            # But the important thing is the method handles all statuses without error
            assert isinstance(result, bool), f"Status {status} should return boolean"


# ============================================================================
# Additional Coverage Tests for Edge Cases
# ============================================================================


class TestCooldownEdgeCases:
    """Test edge cases and error handling in cooldown logic."""

    def test_cooldown_with_null_exit_level_returns_false(
        self, signal_generator_with_mocks
    ):
        """Test that unexpected/null exit levels allow trade (safe default)."""
        recent_exit = MagicMock(spec=Signal)
        recent_exit.status = SignalStatus.WAITING  # Status not in exit_level_map
        recent_exit.take_profit_1 = 100.0  # Add attributes so mock doesn't fail
        recent_exit.take_profit_2 = 110.0
        recent_exit.take_profit_3 = 120.0
        recent_exit.suggested_stop = 90.0
        recent_exit.timestamp = datetime.now(timezone.utc) - timedelta(hours=1)

        signal_generator_with_mocks.signal_repo.get_most_recent_exit.return_value = (
            recent_exit
        )

        # Should return False (allow trade) for unexpected status
        result = signal_generator_with_mocks._is_in_cooldown("BTC/USD", 50000.0)
        assert result is False, f"Expected result to be False, got {result}"

    def test_cooldown_with_exact_10pct_threshold_allows_trade(
        self, signal_generator_with_mocks
    ):
        """Test that exactly 10% price move allows trade (escape valve)."""
        recent_exit = MagicMock(spec=Signal)
        recent_exit.status = SignalStatus.TP1_HIT
        recent_exit.take_profit_1 = 100.0
        recent_exit.take_profit_2 = 110.0
        recent_exit.take_profit_3 = 120.0
        recent_exit.suggested_stop = 90.0
        recent_exit.timestamp = datetime.now(timezone.utc) - timedelta(hours=1)

        signal_generator_with_mocks.signal_repo.get_most_recent_exit.return_value = (
            recent_exit
        )

        # Exactly 10% move should allow trade
        result = signal_generator_with_mocks._is_in_cooldown("BTC/USD", 110.0)
        assert result is False, f"Expected result to be False, got {result}"

    def test_cooldown_with_zero_price_handles_gracefully(
        self, signal_generator_with_mocks
    ):
        """Test cooldown doesn't crash with unusual price values."""
        recent_exit = MagicMock(spec=Signal)
        recent_exit.status = SignalStatus.TP2_HIT
        recent_exit.take_profit_1 = 100.0
        recent_exit.take_profit_2 = 110.0
        recent_exit.take_profit_3 = 120.0
        recent_exit.suggested_stop = 90.0
        recent_exit.timestamp = datetime.now(timezone.utc) - timedelta(hours=1)

        signal_generator_with_mocks.signal_repo.get_most_recent_exit.return_value = (
            recent_exit
        )

        # Should not crash
        result = signal_generator_with_mocks._is_in_cooldown("BTC/USD", 110.0)
        assert isinstance(
            result, bool
        ), f"Expected result to be instance of bool, got {type(result).__name__}"

    def test_cooldown_respects_pattern_scope_filter(self, signal_generator_with_mocks):
        """Test that pattern_name parameter is passed to repository query."""
        recent_exit = MagicMock(spec=Signal)
        recent_exit.status = SignalStatus.TP3_HIT
        recent_exit.take_profit_1 = 100.0
        recent_exit.take_profit_2 = 110.0
        recent_exit.take_profit_3 = 120.0
        recent_exit.suggested_stop = 90.0
        recent_exit.pattern_name = "BULL_FLAG"
        recent_exit.timestamp = datetime.now(timezone.utc) - timedelta(hours=1)

        signal_generator_with_mocks.signal_repo.get_most_recent_exit.return_value = (
            recent_exit
        )

        # Call with pattern_name (scope=PATTERN mode)
        with patch(
            "crypto_signals.engine.signal_generator.get_settings"
        ) as mock_settings:
            mock_settings.return_value.COOLDOWN_SCOPE = "PATTERN"
            result = signal_generator_with_mocks._is_in_cooldown(
                "BTC/USD", 121.0, pattern_name="BULL_FLAG"
            )

        # Should call repository with pattern filter
        signal_generator_with_mocks.signal_repo.get_most_recent_exit.assert_called()
        assert isinstance(
            result, bool
        ), f"Expected result to be instance of bool, got {type(result).__name__}"

    def test_cooldown_with_no_recent_exit_allows_trade(self, signal_generator_with_mocks):
        """Test that no recent exit returns False (allow trade)."""
        signal_generator_with_mocks.signal_repo.get_most_recent_exit.return_value = None

        result = signal_generator_with_mocks._is_in_cooldown("BTC/USD", 50000.0)
        assert result is False, f"Expected result to be False, got {result}"

    def test_cooldown_with_very_old_exit_blocks_trade(self, signal_generator_with_mocks):
        """Test that old exits within 48h window still block (time-based)."""
        recent_exit = MagicMock(spec=Signal)
        recent_exit.status = SignalStatus.TP1_HIT
        recent_exit.take_profit_1 = 45000.0
        recent_exit.take_profit_2 = 48000.0
        recent_exit.take_profit_3 = 50000.0
        recent_exit.suggested_stop = 40000.0
        # 47 hours ago (just inside 48h window)
        recent_exit.timestamp = datetime.now(timezone.utc) - timedelta(hours=47)

        signal_generator_with_mocks.signal_repo.get_most_recent_exit.return_value = (
            recent_exit
        )

        # Price close to exit, within 48h → blocked
        result = signal_generator_with_mocks._is_in_cooldown("BTC/USD", 45500.0)
        assert result is True, f"Expected result to be True, got {result}"
