from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List

from crypto_signals.domain.schemas import (
    AssetClass,
    FactTheoreticalSignal,
    OrderSide,
    Position,
    Signal,
    SignalStatus,
    TradeStatus,
    get_deterministic_id,
)
from polyfactory.decorators import post_generated
from polyfactory.factories.pydantic_factory import ModelFactory


class SignalFactory(ModelFactory[Signal]):
    __model__ = Signal

    @post_generated
    @classmethod
    def signal_id(cls, ds: date, strategy_id: str, symbol: str) -> str:
        return get_deterministic_id(f"{ds}|{strategy_id}|{symbol}")

    @classmethod
    def ds(cls) -> date:
        return date(2025, 1, 15)

    strategy_id = "BULLISH_ENGULFING"
    symbol = "BTC/USD"
    asset_class = AssetClass.CRYPTO
    entry_price = 50000.0
    pattern_name = "BULLISH_ENGULFING"
    suggested_stop = 48000.0
    status = SignalStatus.WAITING
    take_profit_1 = 55000.0
    take_profit_2 = 60000.0
    side = OrderSide.BUY

    @classmethod
    def valid_until(cls) -> datetime:
        return datetime.now(timezone.utc) + timedelta(days=1)

    @classmethod
    def created_at(cls) -> datetime:
        return datetime.now(timezone.utc) - timedelta(hours=1)

    @classmethod
    def scaled_out_prices(cls) -> List[Dict[str, Any]]:
        return []

    # Optional fields should default to None to avoid random values in tests
    invalidation_price = None
    take_profit_3 = None
    delete_at = None
    exit_reason = None
    discord_thread_id = None
    pattern_duration_days = None
    pattern_span_days = None
    pattern_classification = None
    structural_anchors = None
    rejection_reason = None
    rejection_metadata = None
    confluence_snapshot = None
    harmonic_metadata = None
    structural_context = None
    conviction_tier = None
    trade_type = "EXECUTED"


class PositionFactory(ModelFactory[Position]):
    __model__ = Position

    @post_generated
    @classmethod
    def position_id(cls, signal_id: str) -> str:
        return signal_id

    @classmethod
    def ds(cls) -> date:
        return date(2025, 1, 15)

    account_id = "paper"
    symbol = "BTC/USD"
    asset_class = AssetClass.CRYPTO

    @post_generated
    @classmethod
    def signal_id(cls, ds: date, symbol: str) -> str:
        # Default strategy for PositionFactory if none provided
        return get_deterministic_id(f"{ds}|BULLISH_ENGULFING|{symbol}")

    status = TradeStatus.OPEN
    entry_fill_price = 50000.0
    current_stop_loss = 48000.0
    qty = 0.01
    side = OrderSide.BUY
    target_entry_price = 50000.0

    @classmethod
    def created_at(cls) -> datetime:
        return datetime.now(timezone.utc) - timedelta(hours=1)

    @classmethod
    def scaled_out_prices(cls) -> List[Dict[str, Any]]:
        return []

    # Optional fields should default to None to avoid random values in tests
    alpaca_order_id = None
    discord_thread_id = None
    trailing_stop_final = None
    tp_order_id = None
    sl_order_id = None
    filled_at = None
    commission = 0.0
    failed_reason = None
    exit_fill_price = None
    exit_time = None
    exit_reason = None
    exit_order_id = None
    entry_order_id = None
    exit_commission = None
    total_fees_actual = None
    awaiting_backfill = False
    trade_type = "EXECUTED"
    original_qty = None
    scaled_out_qty = 0.0
    scaled_out_price = None
    scaled_out_at = None
    breakeven_applied = False
    entry_slippage_pct = None
    exit_slippage_pct = None
    trade_duration_seconds = None
    realized_pnl_usd = 0.0
    realized_pnl_pct = 0.0
    delete_at = None


class FactTheoreticalSignalFactory(ModelFactory[FactTheoreticalSignal]):
    __model__ = FactTheoreticalSignal

    @classmethod
    def ds(cls) -> date:
        return date(2025, 1, 15)

    strategy_id = "BULLISH_ENGULFING"
    symbol = "BTC/USD"
    asset_class = AssetClass.CRYPTO
    side = OrderSide.BUY
    status = SignalStatus.WAITING
    trade_type = "FILTERED"
    entry_price = 50000.0
    pattern_name = "BULLISH_ENGULFING"
    suggested_stop = 48000.0

    @classmethod
    def valid_until(cls) -> datetime:
        return datetime(2025, 1, 16, 12, 0, tzinfo=timezone.utc)

    @classmethod
    def created_at(cls) -> datetime:
        return datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc)

    @classmethod
    def confluence_factors(cls) -> List[str]:
        return []

    # ALL optional fields = None (prevents polyfactory random values)
    doc_id = None
    take_profit_1 = None
    take_profit_2 = None
    take_profit_3 = None
    exit_reason = None
    rejection_reason = None
    pattern_classification = None
    pattern_duration_days = None
    pattern_span_days = None
    conviction_tier = None
    structural_context = None
    confluence_snapshot = None
    harmonic_metadata = None
    rejection_metadata = None
    structural_anchors = None
    theoretical_exit_price = None
    theoretical_exit_reason = None
    theoretical_exit_time = None
    theoretical_pnl_usd = None
    theoretical_pnl_pct = None
    theoretical_fees_usd = None
    distance_to_trigger_pct = None
    linked_trade_id = None
