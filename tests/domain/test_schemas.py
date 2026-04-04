"""
Tests for Crypto Sentinel Data Schemas.

Verifies the data contract defined in src/schemas.py:
- Deterministic ID generation (P0 Risk)
- Asset class validation (Refinement)
- Position model completeness
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from crypto_signals.domain.schemas import (
    AssetClass,
    ConfluenceConfig,
    ExitReason,
    FactTheoreticalSignal,
    OrderSide,
    Position,
    Signal,
    SignalStatus,
    StrategyConfig,
    StructuralAnchor,
    TradeExecution,
    TradeStatus,
    get_deterministic_id,
)
from pydantic import ValidationError

# =============================================================================
# P0 RISK - DETERMINISTIC IDS
# =============================================================================


class TestDeterministicIds:
    """Test get_deterministic_id for idempotency guarantees."""

    @pytest.mark.parametrize(
        "input_a,input_b,expected_equal",
        [
            pytest.param("A", "A", True, id="same_input"),
            pytest.param("A", "B", False, id="different_input"),
            pytest.param(
                "2024-01-15|momentum|BTC/USD",
                "2024-01-15|momentum|BTC/USD",
                True,
                id="complex_key",
            ),
        ],
    )
    def test_deterministic_id_idempotency(self, input_a, input_b, expected_equal):
        """Verify that get_deterministic_id is deterministic or different based on input."""
        id_1 = get_deterministic_id(input_a)
        id_2 = get_deterministic_id(input_b)

        assert (id_1 == id_2) is expected_equal

    def test_returns_valid_uuid_string(self):
        """Output must be a valid UUID string format."""
        result = get_deterministic_id("test")

        # UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        assert len(result) == 36
        assert result.count("-") == 4


# =============================================================================
# REFINEMENT - ASSET CLASS VALIDATION
# =============================================================================


class TestAssetClassValidation:
    """Test AssetClass enum validation in StrategyConfig."""

    @pytest.mark.parametrize(
        "asset_class,expected_enum,expected_value",
        [
            pytest.param(
                AssetClass.CRYPTO, AssetClass.CRYPTO, "CRYPTO", id="crypto_enum"
            ),
            pytest.param(
                AssetClass.EQUITY, AssetClass.EQUITY, "EQUITY", id="equity_enum"
            ),
            pytest.param("CRYPTO", AssetClass.CRYPTO, "CRYPTO", id="crypto_string"),
        ],
    )
    def test_strategy_config_accepts_valid_asset_classes(
        self, asset_class, expected_enum, expected_value
    ):
        """Ensure StrategyConfig accepts valid AssetClass values."""
        config = StrategyConfig(
            strategy_id="test_strategy",
            active=True,
            timeframe="1D",
            asset_class=asset_class,
            assets=["BTC/USD"],
            risk_params={},
        )
        assert config.asset_class == expected_enum
        assert config.asset_class.value == expected_value

    def test_rejects_invalid_asset_class(self):
        """Ensure StrategyConfig rejects invalid asset class like 'FOREX'."""
        with pytest.raises(ValidationError) as exc_info:
            StrategyConfig(
                strategy_id="invalid_strategy",
                active=True,
                timeframe="1D",
                asset_class="FOREX",  # Invalid!
                assets=["EUR/USD"],
                risk_params={},
            )

        # Verify the error mentions the invalid value
        error_str = str(exc_info.value)
        assert "asset_class" in error_str.lower() or "FOREX" in error_str


# =============================================================================
# COMPLETENESS - POSITION MODEL
# =============================================================================


class TestPositionModel:
    """Test Position model for required fields and validation."""

    @pytest.mark.parametrize(
        "side,qty,expected_side_value",
        [
            pytest.param(OrderSide.BUY, 0.5, "buy", id="buy_side"),
            pytest.param(OrderSide.SELL, 1.0, "sell", id="sell_side"),
        ],
    )
    def test_position_valid_qty_and_side(self, side, qty, expected_side_value):
        """Position must accept qty and side fields."""
        position = Position(
            position_id="order_123",
            ds=date(2024, 1, 15),
            account_id="account_abc",
            symbol="BTC/USD",
            signal_id="signal_xyz",
            status=TradeStatus.OPEN,
            entry_fill_price=50000.00,
            current_stop_loss=48000.00,
            qty=qty,
            side=side,
        )

        assert position.qty == qty
        assert position.side == side
        assert position.side.value == expected_side_value

    @pytest.mark.parametrize("missing_field", ["qty", "side"])
    def test_position_fails_missing_required_fields(self, missing_field):
        """Position must fail validation if required fields are missing."""
        base_data = {
            "position_id": "order_789",
            "ds": date(2024, 1, 15),
            "account_id": "account_abc",
            "symbol": "BTC/USD",
            "signal_id": "signal_xyz",
            "status": TradeStatus.OPEN,
            "entry_fill_price": 50000.00,
            "current_stop_loss": 48000.00,
            "qty": 0.5,
            "side": OrderSide.BUY,
        }
        del base_data[missing_field]

        with pytest.raises(ValidationError) as exc_info:
            Position(**base_data)

        assert missing_field in str(exc_info.value).lower()

    @pytest.mark.parametrize("discord_id", [None, "1234567890"])
    def test_position_discord_thread_id(self, discord_id):
        """Position must handle discord_thread_id (optional)."""
        position = Position(
            position_id="order_123",
            ds=date(2024, 1, 15),
            account_id="account_abc",
            symbol="BTC/USD",
            signal_id="signal_xyz",
            status=TradeStatus.OPEN,
            entry_fill_price=50000.00,
            current_stop_loss=48000.00,
            qty=0.5,
            side=OrderSide.BUY,
            discord_thread_id=discord_id,
        )

        assert position.discord_thread_id == discord_id


# =============================================================================
# BONUS - SIGNAL MODEL TESTS
# =============================================================================


class TestSignalModel:
    """Additional tests for Signal model completeness."""

    def test_signal_with_suggested_stop(self):
        """Signal must include suggested_stop field."""
        signal = Signal(
            signal_id=get_deterministic_id("2024-01-15|momentum|BTC/USD"),
            ds=date(2024, 1, 15),
            strategy_id="momentum",
            symbol="BTC/USD",
            asset_class=AssetClass.CRYPTO,
            confluence_factors=[],
            entry_price=50000.0,
            pattern_name="bullish_engulfing",
            status=SignalStatus.WAITING,
            suggested_stop=48000.00,
            valid_until=datetime(2024, 1, 16, tzinfo=timezone.utc),
        )

        assert signal.suggested_stop == 48000.00

    def test_signal_status_default(self):
        """Signal status should default to WAITING."""
        signal = Signal(
            signal_id="test_signal",
            ds=date(2024, 1, 15),
            strategy_id="momentum",
            symbol="BTC/USD",
            asset_class=AssetClass.CRYPTO,
            entry_price=50000.0,
            pattern_name="bullish_engulfing",
            suggested_stop=48000.00,
        )

        assert signal.status == SignalStatus.WAITING

    @pytest.mark.parametrize("discord_id", [None, "1234567890"])
    def test_signal_discord_thread_id(self, discord_id):
        """Signal must handle discord_thread_id (optional)."""
        signal = Signal(
            signal_id="test_signal",
            ds=date(2024, 1, 15),
            strategy_id="momentum",
            symbol="BTC/USD",
            asset_class=AssetClass.CRYPTO,
            entry_price=50000.0,
            pattern_name="bullish_engulfing",
            suggested_stop=48000.00,
            discord_thread_id=discord_id,
        )

        assert signal.discord_thread_id == discord_id

        serialized = signal.model_dump(mode="json")
        assert serialized["discord_thread_id"] == discord_id

    @pytest.mark.parametrize(
        "classification,expected_delta_hours",
        [
            pytest.param("STANDARD_PATTERN", 48, id="standard"),
            pytest.param("MACRO_PATTERN", 120, id="macro"),
            pytest.param(None, 120, id="none_fallback"),
        ],
    )
    def test_signal_legacy_fallback_created_at(
        self, classification, expected_delta_hours
    ):
        """Signal must populate created_at from valid_until for legacy data (Issue 99)."""
        valid_until = datetime(2024, 1, 16, 12, 0, tzinfo=timezone.utc)
        signal = Signal(
            signal_id="legacy_signal",
            ds=date(2024, 1, 15),
            strategy_id="momentum",
            symbol="BTC/USD",
            asset_class=AssetClass.CRYPTO,
            entry_price=50000.0,
            pattern_name="bullish_engulfing",
            suggested_stop=48000.00,
            valid_until=valid_until,
            pattern_classification=classification,
            created_at=None,
        )

        expected_created_at = valid_until - timedelta(hours=expected_delta_hours)
        assert signal.created_at == expected_created_at


# =============================================================================
# TRADE EXECUTION MODEL TESTS
# =============================================================================


class TestTradeExecutionModel:
    """Test TradeExecution model for pnl_usd field validation."""

    @pytest.mark.parametrize("missing_pnl_field", ["pnl_pct", "pnl_usd"])
    def test_trade_execution_pnl_fields_required(
        self, missing_pnl_field, trade_execution_base_data
    ):
        """TradeExecution must require both pnl_pct and pnl_usd."""
        data = trade_execution_base_data.copy()
        del data[missing_pnl_field]

        with pytest.raises(ValidationError) as exc_info:
            TradeExecution(**data)

        assert missing_pnl_field in str(exc_info.value).lower()

    @pytest.mark.parametrize("exit_order_id", [None, "exit-order-123"])
    def test_trade_execution_exit_order_id(
        self, exit_order_id, trade_execution_base_data
    ):
        """TradeExecution must handle exit_order_id (optional)."""
        data = trade_execution_base_data.copy()
        if exit_order_id:
            data["exit_order_id"] = exit_order_id

        trade = TradeExecution(**data)
        assert trade.exit_order_id == exit_order_id

        serialized = trade.model_dump(mode="json")
        assert serialized.get("exit_order_id") == exit_order_id

    @pytest.fixture
    def trade_execution_base_data(self):
        """Base data for TradeExecution tests."""
        return {
            "ds": date(2024, 1, 15),
            "trade_id": "trade_123",
            "account_id": "account_abc",
            "asset_class": AssetClass.CRYPTO,
            "symbol": "BTC/USD",
            "side": OrderSide.BUY,
            "qty": 1.0,
            "entry_price": 50000.0,
            "exit_price": 52000.0,
            "entry_time": datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
            "exit_time": datetime(2024, 1, 16, 10, 0, tzinfo=timezone.utc),
            "exit_reason": ExitReason.TP1,
            "pnl_pct": 4.0,
            "pnl_usd": 2000.0,
            "fees_usd": 10.0,
            "slippage_pct": 0.1,
            "trade_duration": 86400,
        }

    @pytest.mark.parametrize(
        "trade_input",
        [
            pytest.param({"strategy_id": None}, id="strategy_id_is_none"),
            pytest.param({}, id="strategy_id_is_missing"),
        ],
    )
    def test_trade_execution_defaults_strategy_id_to_unknown(
        self, trade_input, trade_execution_base_data
    ):
        """TradeExecution must default strategy_id to 'UNKNOWN' if None or missing (Issue #253)."""
        trade_data = {**trade_execution_base_data, **trade_input}
        trade = TradeExecution(**trade_data)

        assert trade.strategy_id == "UNKNOWN"


# =============================================================================
# STRATEGY CONFIG MODEL TESTS (Issue #198)
# =============================================================================


class TestStrategyConfigDefaults:
    """Tests for StrategyConfig defaults and completeness."""

    def test_strategy_config_defaults(self):
        """Test that new fields default to empty dicts when missing."""
        config = StrategyConfig(
            strategy_id="test_strategy",
            active=True,
            timeframe="1D",
            asset_class=AssetClass.CRYPTO,
            assets=["BTC/USD"],
            risk_params={"stop_loss_pct": 0.02},
        )

        assert config.confluence_config == ConfluenceConfig()
        assert isinstance(config.confluence_config, ConfluenceConfig)
        assert config.pattern_overrides == {}
        assert isinstance(config.pattern_overrides, dict)

    def test_strategy_config_explicit_values(self):
        """Test that new fields accept explicit values."""
        confluence_config = {"rsi_period": 14}
        pattern_overrides = {"bullish_engulfing": {"priority": 1}}

        config = StrategyConfig(
            strategy_id="test_strategy",
            active=True,
            timeframe="1D",
            asset_class=AssetClass.CRYPTO,
            assets=["BTC/USD"],
            risk_params={"stop_loss_pct": 0.02},
            confluence_config=confluence_config,
            pattern_overrides=pattern_overrides,
        )

        # ConfluenceConfig defaults will be applied to missing fields
        assert config.confluence_config.rsi_period == 14
        assert config.confluence_config.adx_threshold == 25.0
        assert config.pattern_overrides == pattern_overrides

    def test_strategy_config_json_serialization(self):
        """Verify JSON serialization for BigQuery compatibility."""
        confluence_config = {"rsi_period": 14}
        pattern_overrides = {"bullish_engulfing": {"priority": 1}}

        config = StrategyConfig(
            strategy_id="test_strategy",
            active=True,
            timeframe="1D",
            asset_class=AssetClass.CRYPTO,
            assets=["BTC/USD"],
            risk_params={"stop_loss_pct": 0.02},
            confluence_config=confluence_config,
            pattern_overrides=pattern_overrides,
        )

        serialized = config.model_dump(mode="json")

        assert "confluence_config" in serialized
        # ConfluenceConfig defaults are included
        assert serialized["confluence_config"]["rsi_period"] == 14
        assert serialized["confluence_config"]["adx_threshold"] == 25.0
        assert "pattern_overrides" in serialized
        assert serialized["pattern_overrides"] == pattern_overrides

    def test_strategy_config_json_serialization_defaults(self):
        """Verify JSON serialization includes defaults."""
        config = StrategyConfig(
            strategy_id="test_strategy",
            active=True,
            timeframe="1D",
            asset_class=AssetClass.CRYPTO,
            assets=["BTC/USD"],
            risk_params={"stop_loss_pct": 0.02},
        )

        serialized = config.model_dump(mode="json")

        # Usually defaults are included by default in model_dump unless exclude_defaults=True.
        # We want them included for BigQuery schema consistency.
        assert "confluence_config" in serialized
        # Should contain default values for ConfluenceConfig
        assert serialized["confluence_config"] == ConfluenceConfig().model_dump(
            mode="json"
        )
        assert "pattern_overrides" in serialized
        assert serialized["pattern_overrides"] == {}


# =============================================================================
# FACT THEORETICAL SIGNAL (Issue #360 — Unified Backtesting Schema)
# =============================================================================


class TestFactTheoreticalSignal:
    """Tests for the unified FactTheoreticalSignal schema (Issue #360).

    Covers all 4 signal outcome scenarios, dict-to-JSON coercion,
    and BigQuery serialization.
    """

    @pytest.mark.parametrize(
        "overrides,expected_status,expected_key_field",
        [
            pytest.param(
                {
                    "status": SignalStatus.REJECTED_BY_FILTER,
                    "trade_type": "FILTERED",
                    "rejection_reason": "Volume 1.2x < 1.5x Required",
                    "confluence_snapshot": {"rsi": 30.5, "adx": 18.0},
                },
                SignalStatus.REJECTED_BY_FILTER,
                "rejection_reason",
                id="rejected",
            ),
            pytest.param(
                {
                    "status": SignalStatus.EXPIRED,
                    "trade_type": "FILTERED",
                    "distance_to_trigger_pct": 2.5,
                    "theoretical_pnl_usd": -150.0,
                    "theoretical_pnl_pct": -0.3,
                },
                SignalStatus.EXPIRED,
                "distance_to_trigger_pct",
                id="expired",
            ),
            pytest.param(
                {
                    "status": SignalStatus.INVALIDATED,
                    "trade_type": "THEORETICAL",
                    "exit_reason": ExitReason.STRUCTURAL_INVALIDATION,
                },
                SignalStatus.INVALIDATED,
                "exit_reason",
                id="invalidated",
            ),
            pytest.param(
                {
                    "status": SignalStatus.TP1_HIT,
                    "trade_type": "EXECUTED",
                    "linked_trade_id": "trade-abc-123",
                    "harmonic_metadata": {"B_ratio": 0.618},
                    "conviction_tier": "HIGH",
                },
                SignalStatus.TP1_HIT,
                "linked_trade_id",
                id="executed",
            ),
        ],
    )
    def test_signal_outcome_scenarios(
        self, overrides, expected_status, expected_key_field
    ):
        """Verify FactTheoreticalSignal handles all 4 signal outcome types."""
        from tests.factories import FactTheoreticalSignalFactory

        signal = FactTheoreticalSignalFactory.build(**overrides)

        assert (
            signal.status == expected_status
        ), f"Expected status={expected_status!r}, got {signal.status!r}"
        key_value = getattr(signal, expected_key_field)
        expected_value = overrides.get(expected_key_field)
        assert (
            key_value == expected_value
        ), f"Expected {expected_key_field}={expected_value!r}, got {key_value!r}"

    def test_dict_to_json_coercion_on_input(self):
        """Verify that dict inputs for JSON blob fields are preserved as dicts in Python."""
        from tests.factories import FactTheoreticalSignalFactory

        snapshot_dict = {"rsi": 45.2, "adx": 28.0, "volume_ratio": 1.8}
        signal = FactTheoreticalSignalFactory.build(
            confluence_snapshot=snapshot_dict,
        )

        # Python-side: remains dict for attribute access
        assert isinstance(
            signal.confluence_snapshot, dict
        ), f"Expected confluence_snapshot to be dict, got {type(signal.confluence_snapshot)}"
        assert (
            signal.confluence_snapshot["rsi"] == 45.2
        ), f"Expected rsi=45.2, got {signal.confluence_snapshot.get('rsi')!r}"

    def test_json_string_input_coercion(self):
        """Verify that JSON string inputs for blob fields are parsed to dicts."""
        from tests.factories import FactTheoreticalSignalFactory

        json_str = '{"rsi": 55.0, "adx": 30.0}'
        signal = FactTheoreticalSignalFactory.build(
            confluence_snapshot=json_str,
        )

        # model_validator should parse JSON string to dict
        assert isinstance(signal.confluence_snapshot, dict), (
            f"Expected confluence_snapshot to be dict after coercion, "
            f"got {type(signal.confluence_snapshot)}"
        )
        assert (
            signal.confluence_snapshot["rsi"] == 55.0
        ), f"Expected rsi=55.0, got {signal.confluence_snapshot.get('rsi')!r}"

    def test_bq_serialization_of_nested_fields(self):
        """Ensure nested fields serialize properly to BQ-compatible primitives via model_dump."""
        import json

        signal = FactTheoreticalSignal(
            doc_id="test_doc",
            ds=date(2024, 1, 15),
            signal_id="sig_123",
            strategy_id="strat_abc",
            symbol="BTC/USD",
            asset_class=AssetClass.CRYPTO,
            side=OrderSide.BUY,
            entry_price=50000.0,
            pattern_name="bullish_engulfing",
            suggested_stop=48000.0,
            valid_until=datetime(2024, 1, 16, tzinfo=timezone.utc),
            status=SignalStatus.EXPIRED,
            trade_type="FILTERED",
            created_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
            confluence_snapshot={"rsi": 30.5, "adx": 25.0},
            harmonic_metadata={"B_ratio": 0.618},
            structural_anchors=[
                StructuralAnchor(
                    price=49000.0,
                    pivot_type="swing_low",
                    index=1,
                    timestamp=datetime(2024, 1, 14, tzinfo=timezone.utc),
                )
            ],
            rejection_metadata={"reason": "volume_too_low"},
        )

        serialized = signal.model_dump(mode="json")

        # STRING (JSON Blob) mapping tests
        assert isinstance(
            serialized["confluence_snapshot"], str
        ), f"Expected confluence_snapshot as str, got {type(serialized['confluence_snapshot'])}"
        deserialized_confluence = json.loads(serialized["confluence_snapshot"])
        assert (
            deserialized_confluence["rsi"] == 30.5
        ), f"Expected rsi=30.5, got {deserialized_confluence.get('rsi')!r}"

        assert isinstance(
            serialized["harmonic_metadata"], str
        ), f"Expected harmonic_metadata as str, got {type(serialized['harmonic_metadata'])}"
        deserialized_harmonic = json.loads(serialized["harmonic_metadata"])
        assert (
            deserialized_harmonic["B_ratio"] == 0.618
        ), f"Expected B_ratio=0.618, got {deserialized_harmonic.get('B_ratio')!r}"

        assert isinstance(
            serialized["rejection_metadata"], str
        ), f"Expected rejection_metadata as str, got {type(serialized['rejection_metadata'])}"
        deserialized_rejection = json.loads(serialized["rejection_metadata"])
        assert (
            deserialized_rejection["reason"] == "volume_too_low"
        ), f"Expected reason='volume_too_low', got {deserialized_rejection.get('reason')!r}"

        # REPEATED RECORD mapping check
        assert isinstance(
            serialized["structural_anchors"], list
        ), f"Expected structural_anchors as list, got {type(serialized['structural_anchors'])}"
        assert (
            len(serialized["structural_anchors"]) == 1
        ), f"Expected 1 anchor, got {len(serialized['structural_anchors'])}"
        assert (
            serialized["structural_anchors"][0]["price"] == 49000.0
        ), f"Expected price=49000.0, got {serialized['structural_anchors'][0].get('price')!r}"

    def test_bq_serialization_empty_defaults(self):
        """Ensure defaults play nicely with BigQuery missing/empty constraints."""
        signal = FactTheoreticalSignal(
            ds=date(2024, 1, 15),
            signal_id="sig_123",
            strategy_id="strat_abc",
            symbol="BTC/USD",
            asset_class=AssetClass.CRYPTO,
            side=OrderSide.BUY,
            entry_price=50000.0,
            pattern_name="bullish_engulfing",
            suggested_stop=48000.0,
            valid_until=datetime(2024, 1, 16, tzinfo=timezone.utc),
            status=SignalStatus.EXPIRED,
            trade_type="FILTERED",
            created_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
        )

        serialized = signal.model_dump(mode="json")
        assert (
            serialized.get("confluence_snapshot") is None
        ), f"Expected None, got {serialized.get('confluence_snapshot')!r}"
        assert (
            serialized.get("harmonic_metadata") is None
        ), f"Expected None, got {serialized.get('harmonic_metadata')!r}"
        assert (
            serialized.get("structural_anchors") is None
        ), f"Expected None, got {serialized.get('structural_anchors')!r}"
        assert (
            serialized.get("rejection_metadata") is None
        ), f"Expected None, got {serialized.get('rejection_metadata')!r}"
        # New fields should also be None
        assert (
            serialized.get("theoretical_pnl_usd") is None
        ), f"Expected None, got {serialized.get('theoretical_pnl_usd')!r}"
        assert (
            serialized.get("linked_trade_id") is None
        ), f"Expected None, got {serialized.get('linked_trade_id')!r}"
        assert (
            serialized.get("distance_to_trigger_pct") is None
        ), f"Expected None, got {serialized.get('distance_to_trigger_pct')!r}"

    def test_factory_produces_valid_model(self):
        """Verify that FactTheoreticalSignalFactory.build() produces a valid model."""
        from tests.factories import FactTheoreticalSignalFactory

        signal = FactTheoreticalSignalFactory.build()

        assert signal.signal_id is not None, "signal_id must not be None"
        assert (
            signal.strategy_id == "BULLISH_ENGULFING"
        ), f"Expected strategy_id='BULLISH_ENGULFING', got {signal.strategy_id!r}"
        assert (
            signal.trade_type == "FILTERED"
        ), f"Expected trade_type='FILTERED', got {signal.trade_type!r}"
        assert (
            signal.theoretical_pnl_usd is None
        ), f"Expected theoretical_pnl_usd=None, got {signal.theoretical_pnl_usd!r}"
