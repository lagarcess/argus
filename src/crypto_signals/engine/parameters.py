"""
Signal Parameter Factory.

Extracts signal parameter calculation logic from SignalGenerator.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from crypto_signals.analysis.patterns import PatternAnalyzer
from crypto_signals.config import get_settings
from crypto_signals.domain.schemas import AssetClass, OrderSide, StrategyConfig
from loguru import logger


class SignalParameterFactory:
    """Factory for calculating signal parameters."""

    # Safe Hydration Constants (for Shadow Validation)
    # P0: Use 1e-8 to accommodate micro-cap tokens (e.g. SHIB) while staying positive
    SAFE_STOP_VAL = 0.00000001
    SAFE_TP1_VAL = 0.00000001
    SAFE_TP2_VAL = 0.00000002
    SAFE_TP3_VAL = 0.00000003

    STRUCTURAL_PATTERNS = {
        "DOUBLE_BOTTOM": "double_bottom",
        "INVERSE_HEAD_SHOULDERS": "inv_hs",
        "BULL_FLAG": "bull_flag",
        "CUP_AND_HANDLE": "cup_handle",
        "FALLING_WEDGE": "falling_wedge",
        "ASCENDING_TRIANGLE": "asc_triangle",
    }

    CONFLUENCE_WHITELIST = [
        "rsi_bullish_divergence",
        "volatility_contraction",
        "volume_expansion",
        "trend_bullish",
    ]

    def get_parameters(
        self,
        symbol: str,
        asset_class: AssetClass,
        pattern_name: str,
        latest: pd.Series,
        sig_id: str,
        analyzer: PatternAnalyzer,
        harmonic_pattern=None,
        geometric_pattern_name: Optional[str] = None,
        strategy_config: Optional[StrategyConfig] = None,
        # confluence_snapshot removed as per review comment
    ) -> Dict[str, Any]:
        """
        Calculate signal parameters based on pattern and market data.
        """
        # Extract Prices
        close_price = float(latest["close"])
        low_price = float(latest["low"])
        open_price = float(latest["open"])
        entry_ref = close_price  # Entry is always close of signal candle

        # ATR for Dynamic Exits
        atr = float(latest.get("ATRr_14") or latest.get("ATR_14", 0.0))

        # Stop Loss: 1% below Low by default
        suggested_stop = low_price * 0.99
        invalidation_price = None

        # Take profit targets (pattern-specific logic may override these)
        take_profit_1 = None
        take_profit_2 = None
        take_profit_3 = None

        # Specific Structural Invalidation
        if pattern_name in ("BULLISH_HAMMER", "MORNING_STAR"):
            invalidation_price = low_price
            suggested_stop = invalidation_price * 0.99

        elif pattern_name == "BULLISH_ENGULFING":
            invalidation_price = open_price
            suggested_stop = invalidation_price * 0.99

        elif pattern_name == "BULLISH_MARUBOZU":
            midpoint = (open_price + close_price) / 2
            invalidation_price = midpoint
            suggested_stop = invalidation_price * 0.99

        elif pattern_name == "BULL_FLAG":
            pole_high = float(latest.get("high", close_price))
            pole_low = low_price

            if "ATRr_14" in latest:
                flagpole_height = max(atr * 3.0, pole_high - pole_low)
            else:
                flagpole_height = pole_high - pole_low

            take_profit_1 = close_price + (0.5 * flagpole_height)
            take_profit_2 = close_price + (1.0 * flagpole_height)
            take_profit_3 = close_price + (1.5 * flagpole_height)
            invalidation_price = low_price
            suggested_stop = invalidation_price * 0.99

        elif "ELLIOTT" in pattern_name:
            # =====================================================================
            # MICRO-CAP HANDLING (Issue #136: Negative Stop Loss)
            # =====================================================================
            if atr > 0:
                # Prevent negative stops for micro-caps (low price + high volatility)
                suggested_stop = max(self.SAFE_STOP_VAL, low_price - (0.5 * atr))
            else:
                suggested_stop = low_price * 0.99
            invalidation_price = low_price

        # Take Profits (ATR Based) - Only set if not already defined
        if take_profit_1 is None:
            take_profit_1 = entry_ref + (2.0 * atr) if atr > 0 else entry_ref * 1.03
        if take_profit_2 is None:
            take_profit_2 = entry_ref + (4.0 * atr) if atr > 0 else entry_ref * 1.06
        if take_profit_3 is None:
            take_profit_3 = entry_ref + (6.0 * atr) if atr > 0 else entry_ref * 1.10

        # Strategy ID
        if strategy_config and strategy_config.strategy_id:
            strategy_id = strategy_config.strategy_id
        else:
            strategy_id = f"{pattern_name}_{asset_class.value}"
            logger.warning(
                "No StrategyConfig injected for pattern. Falling back to structured pattern_name as strategy_id.",
                extra={"pattern_name": pattern_name, "strategy_id": strategy_id},
            )

        # DS
        ds = latest.name.date() if hasattr(latest.name, "date") else latest.name

        # Confluence Factors
        confluence_factors = [
            col
            for col in self.CONFLUENCE_WHITELIST
            if col in latest.index
            and isinstance(latest[col], (bool, np.bool_))
            and latest[col]
        ]
        # Multi-Layer Architecture: harmonic context has its own field,
        # no longer appended as a confluence factor

        # Structural Metadata
        pattern_duration_days = None
        pattern_classification = None
        structural_anchors = None

        if pattern_name in self.STRUCTURAL_PATTERNS:
            col_prefix = self.STRUCTURAL_PATTERNS[pattern_name]
            duration_col = f"{col_prefix}_duration"
            class_col = f"{col_prefix}_classification"

            if duration_col in latest.index and pd.notna(latest.get(duration_col)):
                pattern_duration_days = int(latest[duration_col])

            if class_col in latest.index and pd.notna(latest.get(class_col)):
                pattern_classification = str(latest[class_col])

        pattern_span_days = None
        if hasattr(analyzer, "pivots") and analyzer.pivots:
            recent_pivots = sorted(analyzer.pivots[-5:], key=lambda p: p.index)
            structural_anchors = [
                {
                    "price": p.price,
                    "timestamp": str(p.timestamp) if p.timestamp else None,
                    "pivot_type": p.pivot_type,
                    "index": p.index,
                }
                for p in recent_pivots
            ]
            if len(structural_anchors) >= 2:
                pivot_indices = [
                    int(float(p.get("index") or 0))
                    for p in structural_anchors
                    if p.get("index") is not None
                ]
                if pivot_indices:
                    pattern_span_days = max(pivot_indices) - min(pivot_indices)

        if pattern_span_days is not None:
            if pattern_span_days > 90:
                pattern_classification = "MACRO_PATTERN"
            else:
                pattern_classification = "STANDARD_PATTERN"

        # Harmonic Metadata & Multi-Layer Architecture
        harmonic_metadata = None
        structural_context = None
        conviction_tier = "STANDARD"
        if harmonic_pattern:
            # Multi-Layer: harmonic is context, not primary strategy
            # strategy_id stays as geometric pattern_name
            structural_context = harmonic_pattern.pattern_type
            conviction_tier = "HIGH"
            harmonic_metadata = (
                harmonic_pattern.ratios.copy()
                if hasattr(harmonic_pattern, "ratios")
                else None
            )
            if harmonic_pattern.is_macro:
                pattern_classification = "MACRO_PATTERN"

        # Timestamp Calculations
        candle_timestamp = latest.name
        if hasattr(candle_timestamp, "to_pydatetime"):
            candle_timestamp = candle_timestamp.to_pydatetime()

        # Issue #153: Fix timezone handling. If aware but not UTC, convert. If naive, assume UTC.
        if candle_timestamp.tzinfo is None:
            candle_timestamp = candle_timestamp.replace(tzinfo=timezone.utc)
        else:
            candle_timestamp = candle_timestamp.astimezone(timezone.utc)

        valid_time = (
            120 if pattern_classification and "MACRO" in pattern_classification else 48
        )
        valid_until = candle_timestamp + timedelta(hours=valid_time)
        created_at = datetime.now(timezone.utc)

        # Pack Parameters
        params = {
            "signal_id": sig_id,
            "strategy_id": strategy_id,
            "symbol": symbol,
            "ds": ds,
            "asset_class": asset_class,
            "confluence_factors": confluence_factors,
            "entry_price": entry_ref,
            "pattern_name": pattern_name,
            "suggested_stop": suggested_stop,
            "invalidation_price": invalidation_price,
            "take_profit_1": take_profit_1,
            "take_profit_2": take_profit_2,
            "take_profit_3": take_profit_3,
            "valid_until": valid_until,
            "delete_at": None,
            "pattern_duration_days": pattern_duration_days,
            "pattern_span_days": pattern_span_days,
            "pattern_classification": pattern_classification,
            "structural_anchors": structural_anchors,
            "harmonic_metadata": harmonic_metadata,
            "structural_context": structural_context,
            "conviction_tier": conviction_tier,
            "created_at": created_at,
            # confluence_snapshot removed from params packing as per review
            "side": OrderSide.BUY,
        }

        # Delete At
        settings = get_settings()
        ttl_days = (
            settings.TTL_DAYS_PROD
            if settings.ENVIRONMENT == "PROD"
            else settings.TTL_DAYS_DEV
        )
        params["delete_at"] = datetime.now(timezone.utc) + timedelta(days=ttl_days)

        return params

    def hydrate_safe_values(self, params: dict) -> dict:
        """Hydrates invalid parameters with safe constants."""
        safe_params = params.copy()
        if safe_params.get("suggested_stop", 0) <= 0:
            safe_params["suggested_stop"] = self.SAFE_STOP_VAL
        if safe_params.get("take_profit_1", 0) <= 0:
            safe_params["take_profit_1"] = self.SAFE_TP1_VAL
        if safe_params.get("take_profit_2") is None or safe_params["take_profit_2"] <= 0:
            safe_params["take_profit_2"] = self.SAFE_TP2_VAL
        if safe_params.get("take_profit_3") is None or safe_params["take_profit_3"] <= 0:
            safe_params["take_profit_3"] = self.SAFE_TP3_VAL
        return safe_params
