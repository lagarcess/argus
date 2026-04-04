"""
Signal Generator Module.

This module orchestrates the fetching of market data, application of technical
indicators, and detection of price patterns to generate trading signals.
"""

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Type

import pandas as pd
from crypto_signals.analysis.harmonics import HarmonicAnalyzer
from crypto_signals.analysis.indicators import TechnicalIndicators
from crypto_signals.analysis.patterns import PatternAnalyzer
from crypto_signals.config import get_settings
from crypto_signals.domain.schemas import (
    QUALITY_GATE_THRESHOLDS_BY_ASSET_CLASS,
    AssetClass,
    ExitReason,
    OrderSide,
    Signal,
    SignalStatus,
    StrategyConfig,
    get_deterministic_id,
)
from crypto_signals.engine.parameters import SignalParameterFactory
from crypto_signals.market.data_provider import MarketDataProvider
from loguru import logger


class SignalGenerator:
    """Orchestrates signal generation from market data."""

    def __init__(
        self,
        market_provider: MarketDataProvider,
        indicators: Optional[TechnicalIndicators] = None,
        pattern_analyzer_cls: Type[PatternAnalyzer] = PatternAnalyzer,
        signal_repo: Optional[Any] = None,
        strategy_configs: Optional[List[StrategyConfig]] = None,
    ):
        """
        Initialize the SignalGenerator.

        Args:
            market_provider: Provider for fetching market data.
            indicators: Instance for adding technical indicators (dependency
                injection). Defaults to new TechnicalIndicators instance.
            pattern_analyzer_cls: Class for verifying patterns (dependency
                injection).
        """
        self.market_provider = market_provider
        self.indicators = indicators or TechnicalIndicators()
        self.pattern_analyzer_cls = pattern_analyzer_cls
        self.parameter_factory = SignalParameterFactory()
        self._strategy_configs = strategy_configs or []

        if signal_repo:
            self.signal_repo = signal_repo
        else:
            # Issue #117: Initialize for cooldown checks
            from crypto_signals.repository.firestore import SignalRepository

            self.signal_repo = SignalRepository()

        # Lazy init PositionRepository for Pyramiding Protection
        from crypto_signals.repository.firestore import PositionRepository

        self.position_repo = PositionRepository()

    def _resolve_strategy_config(
        self, symbol: str, asset_class: AssetClass, pattern_name: str
    ) -> Optional[StrategyConfig]:
        """Resolve StrategyConfig for a given symbol and asset class.

        Enforces the SCD (Slowly Changing Dimension) constraint:
        Only ONE strategy is active per asset combination at any time.
        The database guarantees uniqueness, so the first active match
        is the only match.

        Args:
            symbol: Trading symbol (e.g., "BTC/USD").
            asset_class: Asset class (CRYPTO or EQUITY).
            pattern_name: Pattern name (kept for future pattern-specific overrides).

        Returns:
            The unique active StrategyConfig for this asset, or None.
        """
        for cfg in self._strategy_configs:
            # 1. SCD constraint: Must be the 'current' active record
            if not cfg.active:
                continue

            # 2. Asset constraint: Must explicitly govern the traded instrument
            if cfg.asset_class == asset_class and symbol in cfg.assets:
                return cfg

        # Strict Failure: Only occurs if Cold Start bootstrapper has not run.
        return None

    def _is_in_cooldown(
        self, symbol: str, current_price: float, pattern_name: str | None = None
    ) -> bool:
        """Check if symbol is in post-exit cooldown period (Issue #117).

        Implements hybrid cooldown logic: 48-hour time window + 10% price
        movement threshold to prevent double-signal noise and revenge trading.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USD")
            current_price: Current market price for the symbol
            pattern_name: Optional pattern filter (only apply cooldown if patterns match)

        Returns:
            True if in cooldown (block trade), False if allowed or no recent exit

        Algorithm:
            1. Query for recent exit (TP/INVALIDATED) within 48h.
            2. If recent exit found, check price movement from exit level.
            3. If move < 10%, block trade.
        """
        COOLDOWN_HOURS = 48
        PRICE_THRESHOLD_PCT = 10.0

        # Use COOLDOWN_SCOPE config to determine blocking behavior
        settings = get_settings()
        cooldown_scope = getattr(settings, "COOLDOWN_SCOPE", "SYMBOL")

        # Query Firestore for recent exits
        # If COOLDOWN_SCOPE is SYMBOL: pass pattern_name=None to query all patterns
        # If COOLDOWN_SCOPE is PATTERN: pass pattern_name to query only same pattern
        query_pattern_name = None if cooldown_scope == "SYMBOL" else pattern_name

        recent_exit = self.signal_repo.get_most_recent_exit(
            symbol=symbol, hours=COOLDOWN_HOURS, pattern_name=query_pattern_name
        )

        if not recent_exit:
            return False  # No recent exit, allow trade

        # Determine actual exit level based on signal status
        # Include INVALIDATED to prevent revenge trading
        exit_level_map = {
            SignalStatus.TP1_HIT: recent_exit.take_profit_1,
            SignalStatus.TP2_HIT: recent_exit.take_profit_2,
            SignalStatus.TP3_HIT: recent_exit.take_profit_3,
            SignalStatus.INVALIDATED: recent_exit.suggested_stop,
        }

        exit_level = exit_level_map.get(recent_exit.status)
        if not exit_level:
            logger.warning(
                f"[COOLDOWN] Unexpected status {recent_exit.status}, allowing trade",
                extra={"symbol": symbol, "status": recent_exit.status},
            )
            return False

        # Calculate price movement from ACTUAL EXIT LEVEL
        price_change_pct = abs(current_price - exit_level) / exit_level * 100

        if price_change_pct >= PRICE_THRESHOLD_PCT:
            logger.debug(
                f"[COOLDOWN_ESCAPE] {symbol}: {price_change_pct:.1f}% move from exit level "
                f"≥ {PRICE_THRESHOLD_PCT}% threshold",
                extra={
                    "symbol": symbol,
                    "exit_level": exit_level,
                    "current_price": current_price,
                    "price_change_pct": price_change_pct,
                    "cooldown_scope": cooldown_scope,
                },
            )
            return False  # Significant move, allow trade

        logger.debug(
            f"[COOLDOWN_ACTIVE] {symbol}: Blocked ({price_change_pct:.1f}% < {PRICE_THRESHOLD_PCT}%)",
            extra={
                "symbol": symbol,
                "exit_level": exit_level,
                "current_price": current_price,
                "price_change_pct": price_change_pct,
                "hours_ago": COOLDOWN_HOURS,
                "cooldown_scope": cooldown_scope,
            },
        )
        return True  # Block trade

    def generate_signals(
        self,
        symbol: str,
        asset_class: AssetClass,
        dataframe: Optional[pd.DataFrame] = None,
    ) -> Optional[Signal]:
        """
        Generate a trading signal for a given symbol if a pattern is detected.

        Process:
        1. Fetch 365 days of daily bars (if not provided).
        2. Add technical indicators.
        3. Analyze for patterns.
        4. Construct a Signal object if a pattern is confirmed.

        Args:
            symbol: Ticker symbol (e.g. "BTC/USD", "AAPL").
            asset_class: Asset class for the symbol.
            dataframe: Optional cached dataframe to avoid redundant fetching.

        Returns:
            Signal: Validated signal object if a pattern is found, else None.
        """
        # 0. Check for existing open position (Pyramiding Protection)
        if self.position_repo.get_open_position_by_symbol(symbol):
            logger.info(
                f"Skipping signal generation for {symbol} - Open position exists."
            )
            return None

        # 1. Fetch Data
        if dataframe is not None:
            df = dataframe
        else:
            df = self.market_provider.get_daily_bars(
                symbol=symbol, asset_class=asset_class, lookback_days=365
            )

        if df.empty:
            return None

        # 2. Add Indicators
        self.indicators.add_all_indicators(df)

        # 3. Analyze Patterns
        analyzer = self.pattern_analyzer_cls(dataframe=df)
        analyzed_df = analyzer.check_patterns()

        if analyzed_df.empty:
            return None

        # Check the LATEST completed candle (last row)
        latest = analyzed_df.iloc[-1]

        # 3a. Analyze Harmonic Patterns
        harmonic_pattern = None
        if hasattr(analyzer, "pivots") and analyzer.pivots:
            harmonic_analyzer = HarmonicAnalyzer(analyzer.pivots)
            harmonic_patterns = harmonic_analyzer.scan_all_patterns()
            # Select the most recent harmonic pattern if multiple detected
            harmonic_pattern = harmonic_patterns[-1] if harmonic_patterns else None

        pattern_name = None
        geometric_pattern_name = None

        # Check patterns in order of priority (Highest Historical Success First)
        # NOTE: Priority rankings based on crypto historical win rates.
        # Equity win rates may differ; reassess after backtest data is available.
        # See GitHub Issue "Quality Gate Threshold Audit" for equity threshold audit.
        if latest.get("inverse_head_shoulders"):
            geometric_pattern_name = "INVERSE_HEAD_SHOULDERS"  # 89%
        elif latest.get("bullish_kicker"):
            geometric_pattern_name = "BULLISH_KICKER"  # 75%
        elif latest.get("falling_wedge"):
            geometric_pattern_name = "FALLING_WEDGE"  # 74%
        elif latest.get("rising_three_methods"):
            geometric_pattern_name = "RISING_THREE_METHODS"  # 70%
        elif latest.get("morning_star"):
            geometric_pattern_name = "MORNING_STAR"  # 70%
        elif latest.get("ascending_triangle"):
            geometric_pattern_name = "ASCENDING_TRIANGLE"  # 68%
        elif latest.get("three_inside_up"):
            geometric_pattern_name = "THREE_INSIDE_UP"  # 65%
        elif latest.get("dragonfly_doji"):
            geometric_pattern_name = "DRAGONFLY_DOJI"  # 65%
        elif latest.get("three_white_soldiers"):
            geometric_pattern_name = "THREE_WHITE_SOLDIERS"  # 64%
        elif latest.get("cup_and_handle"):
            geometric_pattern_name = "CUP_AND_HANDLE"  # 63%
        elif latest.get("double_bottom"):
            geometric_pattern_name = "DOUBLE_BOTTOM"  # 62%
        elif latest.get("bull_flag"):
            geometric_pattern_name = "BULL_FLAG"  # 61%
        elif latest.get("bullish_belt_hold"):
            geometric_pattern_name = "BULLISH_BELT_HOLD"  # 60%
        elif latest.get("bullish_engulfing"):
            geometric_pattern_name = "BULLISH_ENGULFING"  # 58%
        elif latest.get("bullish_hammer"):
            geometric_pattern_name = "BULLISH_HAMMER"  # 57%
        elif latest.get("piercing_line"):
            geometric_pattern_name = "PIERCING_LINE"  # 55%
        elif latest.get("inverted_hammer"):
            geometric_pattern_name = "INVERTED_HAMMER"  # 55%
        elif latest.get("bullish_marubozu"):
            geometric_pattern_name = "BULLISH_MARUBOZU"  # 54%
        elif latest.get("bullish_harami"):
            geometric_pattern_name = "BULLISH_HARAMI"  # 53%
        elif latest.get("tweezer_bottoms"):
            geometric_pattern_name = "TWEEZER_BOTTOMS"  # 52%
        elif latest.get("elliott_impulse_wave"):
            geometric_pattern_name = "ELLIOTT_IMPULSE_WAVE"  # ATR-based stop (Issue 99)

        if harmonic_pattern and geometric_pattern_name:
            # Multi-Layer Architecture: Geometric is the tactical trigger,
            # harmonic provides structural context (stored in structural_context field)
            pattern_name = geometric_pattern_name
        elif geometric_pattern_name:
            # Only geometric pattern detected — tactical trigger without structural context
            pattern_name = geometric_pattern_name
        elif harmonic_pattern:
            # Harmonic-only: no tactical trigger → no signal
            # Structural context alone doesn't produce an entry signal
            logger.debug(
                f"[{symbol}] Harmonic pattern ({harmonic_pattern.pattern_type}) detected, "
                f"but missing geometric tactical trigger. Skipping signal generation."
            )
            return None
        else:
            # No patterns detected
            return None

        # ============================================================
        # CONVICTION TIER (Phase 2: Multi-Layer Architecture)
        # ============================================================
        # Derive conviction tier BEFORE quality gates to allow threshold relaxation
        conviction_tier = (
            "HIGH" if harmonic_pattern and geometric_pattern_name else "STANDARD"
        )

        # ============================================================
        # SIGNAL QUALITY FILTERS (Confluence Validation)
        # ============================================================
        # Collect all rejection reasons and indicator values for transparency
        rejection_reasons: List[str] = []

        # Extract indicator values for confluence snapshot
        current_volume = float(latest.get("volume", 0))
        vol_sma_20 = float(latest.get("VOL_SMA_20", 1.0))
        if vol_sma_20 <= 0:
            vol_sma_20 = 1.0
        volume_ratio = current_volume / vol_sma_20 if vol_sma_20 > 0 else 0

        rsi_value = float(latest.get("RSI_14", 50))  # Default to neutral
        adx_value = float(latest.get("ADX_14", 25))  # Default to moderate trend
        sma_200 = float(latest.get("SMA_200", 0))
        close_price = float(latest.get("close", 0))
        sma_trend = "Above" if close_price > sma_200 and sma_200 > 0 else "Below"

        # Conviction-aware thresholds (Phase 2)
        thresholds = QUALITY_GATE_THRESHOLDS_BY_ASSET_CLASS[asset_class]
        adx_threshold = (
            thresholds.relaxed_adx_threshold
            if conviction_tier == "HIGH"
            else thresholds.base_adx_threshold
        )

        # Define pattern categories for targeted validation
        breakout_patterns = (
            "ASCENDING_TRIANGLE",
            "CUP_AND_HANDLE",
            "FALLING_WEDGE",
            "INVERSE_HEAD_SHOULDERS",
            "BULL_FLAG",
            "DOUBLE_BOTTOM",
            "BULLISH_MARUBOZU",
            "ELLIOTT_WAVE_135",
            "ELLIOTT_IMPULSE_WAVE",
        )
        trend_following_patterns = (
            "BULL_FLAG",
            "ASCENDING_TRIANGLE",
            "RISING_THREE_METHODS",
            "THREE_WHITE_SOLDIERS",
            "ELLIOTT_WAVE_135",
            "ELLIOTT_IMPULSE_WAVE",
        )

        # 1. VOLUME CONFIRMATION FILTER (Breakout patterns only)
        # Conviction-aware thresholds (Phase 2)
        volume_threshold = (
            thresholds.relaxed_volume_threshold
            if conviction_tier == "HIGH"
            else thresholds.base_volume_threshold
        )
        if pattern_name in breakout_patterns and volume_ratio < volume_threshold:
            rejection_reasons.append(f"Volume {volume_ratio:.1f}x < {volume_threshold}x")

        # 2. RSI OVERBOUGHT FILTER (Bullish patterns)
        # Reject if RSI > 70 (overbought) - reduces chasing extended moves
        # NOTE: RSI overbought levels are standard across asset classes (70).
        # See GitHub Issue "Quality Gate Threshold Audit" for equity threshold audit.
        if rsi_value > 70:
            rejection_reasons.append(f"RSI {rsi_value:.0f} > 70 (Overbought)")

        # 3. ADX WEAK TREND FILTER (Trend-following patterns only)
        # Conviction-aware thresholds (Phase 2)
        adx_threshold = (
            thresholds.relaxed_adx_threshold
            if conviction_tier == "HIGH"
            else thresholds.base_adx_threshold
        )
        # Reject if ADX below threshold - trend is too weak for trend-following setups
        # NOTE: ADX trend strength threshold (25) is also standard.
        # Current thresholds (20/15) are calibrated for crypto.
        # See GitHub Issue "Quality Gate Threshold Audit" for equity threshold audit.
        if pattern_name in trend_following_patterns and adx_value < adx_threshold:
            rejection_reasons.append(
                f"ADX {adx_value:.0f} < {adx_threshold} (Weak Trend)"
            )

        # Build confluence snapshot for persistence
        confluence_snapshot = {
            "rsi": round(rsi_value, 1),
            "adx": round(adx_value, 1),
            "sma_trend": sma_trend,
            "volume_ratio": round(volume_ratio, 2),
        }

        # If quality gate failures exist at this point, reject early
        if rejection_reasons:
            combined_reason = " AND ".join(rejection_reasons)
            logger.warning(
                f"[REJECTION] {symbol} {pattern_name} rejected: {combined_reason}"
            )
            return self._create_rejected_signal(
                symbol,
                asset_class,
                pattern_name,
                latest,
                analyzer,
                combined_reason,
                confluence_snapshot,
                harmonic_pattern=harmonic_pattern,
            )

        # 4. Construct Signal
        sig_id = get_deterministic_id(f"{symbol}|{pattern_name}|{latest.name}")

        # Resolve StrategyConfig for injection
        strategy_config = self._resolve_strategy_config(symbol, asset_class, pattern_name)

        signal = self._create_signal(
            symbol,
            asset_class,
            pattern_name,
            latest,
            sig_id,
            analyzer,
            harmonic_pattern=harmonic_pattern,
            geometric_pattern_name=geometric_pattern_name,
            strategy_config=strategy_config,
        )

        # Early validation failed (negative stop-loss, zero TP, etc.)
        if signal is None:
            return None

        # 5. RISK-TO-REWARD (R:R) FILTER
        # Logic is now handled internally by _create_signal during pre-construction validation
        # (check validation block ~lines 550+) to support Shadow Validation.

        return self._create_signal(
            symbol,
            asset_class,
            pattern_name,
            latest,
            sig_id,
            analyzer,
            harmonic_pattern=harmonic_pattern,
            geometric_pattern_name=geometric_pattern_name,
            confluence_snapshot=confluence_snapshot,  # PASS SNAPSHOT
            strategy_config=strategy_config,
        )

    def _validate_signal_parameters(
        self,
        params: Dict[str, Any],
        confluence_snapshot: Optional[Dict[str, Any]] = None,
        conviction_tier: Optional[str] = None,
    ) -> List[str]:
        """Pure logic validation of signal parameters."""
        rejection_reasons = []
        suggested_stop = params.get("suggested_stop")
        take_profit_1 = params.get("take_profit_1")
        entry_ref = params.get("entry_price")
        asset_class = params.get("asset_class", AssetClass.CRYPTO)

        # 1. Negative Stop Loss
        if suggested_stop is None or suggested_stop <= 0:
            rejection_reasons.append(f"Invalid Stop: {suggested_stop}")

        # 2. Invalid Take Profit
        if take_profit_1 is None or take_profit_1 <= 0:
            rejection_reasons.append(f"Invalid TP1: {take_profit_1}")

        # 3. R:R Validation
        if (
            suggested_stop is not None
            and suggested_stop > 0
            and take_profit_1 is not None
            and entry_ref is not None
            and entry_ref > 0
        ):
            potential_profit = abs(take_profit_1 - entry_ref)
            potential_risk = abs(entry_ref - suggested_stop)

            if potential_risk > 0:
                rr_ratio = potential_profit / potential_risk
                if confluence_snapshot:
                    confluence_snapshot["rr_ratio"] = round(rr_ratio, 2)

                # Load dynamic asset-class thresholds
                thresholds = QUALITY_GATE_THRESHOLDS_BY_ASSET_CLASS[asset_class]

                rr_threshold = (
                    thresholds.relaxed_rr_threshold
                    if conviction_tier == "HIGH"
                    else thresholds.base_rr_threshold
                )
                if rr_ratio < rr_threshold:
                    rejection_reasons.append(f"R:R {rr_ratio:.1f} < {rr_threshold}")

        return rejection_reasons

    @staticmethod
    def compute_diversity_metrics(signals: list["Signal"]) -> Dict[str, Any]:
        """Compute pattern distribution, structural context, and entropy metrics.

        Args:
            signals: List of Signal objects from the current run.

        Returns:
            Dictionary with pattern_distribution, structural_context_distribution,
            conviction_distribution, shannon_entropy, and total_signals.
        """

        total = len(signals)
        if total == 0:
            return {
                "total_signals": 0,
                "pattern_distribution": {},
                "structural_context_distribution": {},
                "conviction_distribution": {},
                "shannon_entropy": 0.0,
            }

        # Pattern counts
        pattern_counts: Dict[str, int] = {}
        context_counts: Dict[str, int] = {}
        conviction_counts: Dict[str, int] = {}

        for sig in signals:
            # Pattern distribution
            name = sig.pattern_name
            pattern_counts[name] = pattern_counts.get(name, 0) + 1

            # Structural context distribution
            ctx = sig.structural_context
            if ctx is not None:
                context_counts[ctx] = context_counts.get(ctx, 0) + 1

            # Conviction tier distribution
            tier = sig.conviction_tier
            conviction_counts[tier] = conviction_counts.get(tier, 0) + 1

        # Pattern distribution with percentages
        pattern_dist = {
            name: {"count": count, "pct": round(count / total * 100, 1)}
            for name, count in sorted(pattern_counts.items(), key=lambda x: -x[1])
        }

        # Shannon entropy: H = -Σ p(x) * log2(p(x))
        entropy = 0.0
        for count in pattern_counts.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)

        return {
            "total_signals": total,
            "pattern_distribution": pattern_dist,
            "structural_context_distribution": dict(context_counts),
            "conviction_distribution": dict(conviction_counts),
            "shannon_entropy": round(entropy, 4),
        }

    def _construct_signal(
        self,
        params: Dict[str, Any],
        status: SignalStatus,
        rejection_reason: Optional[str] = None,
        rejection_metadata: Optional[Dict[str, Any]] = None,
    ) -> Signal:
        """Pure Factory: Builds the Signal object."""
        return Signal(
            signal_id=params["signal_id"],
            strategy_id=params["strategy_id"],
            symbol=params["symbol"],
            ds=params["ds"],
            asset_class=params["asset_class"],
            confluence_factors=params.get("confluence_factors", []),
            entry_price=params["entry_price"],
            pattern_name=params["pattern_name"],
            status=status,
            suggested_stop=params["suggested_stop"],
            invalidation_price=params.get("invalidation_price"),
            take_profit_1=params["take_profit_1"],
            take_profit_2=params.get("take_profit_2"),
            take_profit_3=params.get("take_profit_3"),
            valid_until=params["valid_until"],
            delete_at=params.get("delete_at"),
            pattern_duration_days=params.get("pattern_duration_days"),
            pattern_span_days=params.get("pattern_span_days"),
            pattern_classification=params.get("pattern_classification"),
            structural_anchors=params.get("structural_anchors"),
            harmonic_metadata=params.get("harmonic_metadata"),
            structural_context=params.get("structural_context"),
            conviction_tier=params.get("conviction_tier"),
            created_at=params["created_at"],
            rejection_reason=rejection_reason,
            rejection_metadata=rejection_metadata,
            confluence_snapshot=params.get("confluence_snapshot"),
            side=params.get("side", OrderSide.BUY),
        )

    def _create_signal(
        self,
        symbol: str,
        asset_class: AssetClass,
        pattern_name: str,
        latest: pd.Series,
        sig_id: str,
        analyzer: PatternAnalyzer,
        harmonic_pattern=None,
        geometric_pattern_name: Optional[str] = None,
        confluence_snapshot: Optional[Dict[str, Any]] = None,
        force_rejection_reason: Optional[str] = None,
        strategy_config: Optional[StrategyConfig] = None,
    ) -> Signal:
        """Orchestrates signal creation: Calculate -> Validate -> Construct."""

        # 1. Get Parameters from Factory
        params = self.parameter_factory.get_parameters(
            symbol=symbol,
            asset_class=asset_class,
            pattern_name=pattern_name,
            latest=latest,
            sig_id=sig_id,
            analyzer=analyzer,
            harmonic_pattern=harmonic_pattern,
            geometric_pattern_name=geometric_pattern_name,
            strategy_config=strategy_config,
        )

        # Manually attach confluence snapshot (removed from factory for cleaner signature)
        params["confluence_snapshot"] = confluence_snapshot

        # Status Logic
        final_status = SignalStatus.WAITING
        final_reason = None
        rejection_metadata = None

        if force_rejection_reason:
            final_status = SignalStatus.REJECTED_BY_FILTER
            final_reason = force_rejection_reason
            # Op Bloat Fix: 24h TTL
            params["delete_at"] = datetime.now(timezone.utc) + timedelta(hours=24)
            # Hydrate to be safe
            params = self.parameter_factory.hydrate_safe_values(params)
        else:
            # Internal Validation
            errors = self._validate_signal_parameters(
                params, confluence_snapshot, conviction_tier=params.get("conviction_tier")
            )
            if errors:
                final_status = SignalStatus.REJECTED_BY_FILTER
                final_reason = f"VALIDATION_FAILED: {', '.join(errors)}"
                # Capture Forensic Data
                rejection_metadata = {
                    "original_stop": params.get("suggested_stop"),
                    "original_tp1": params.get("take_profit_1"),
                    "entry_price": params.get("entry_price"),
                }
                logger.warning(
                    f"[SHADOW REJECTION] {symbol} {pattern_name}: {final_reason}"
                )

                # Op Bloat Fix: 24h TTL
                params["delete_at"] = datetime.now(timezone.utc) + timedelta(hours=24)

                # Hydrate
                params = self.parameter_factory.hydrate_safe_values(params)

        return self._construct_signal(
            params, final_status, final_reason, rejection_metadata
        )

    def _create_rejected_signal(
        self,
        symbol: str,
        asset_class: AssetClass,
        pattern_name: str,
        latest: pd.Series,
        analyzer: PatternAnalyzer,
        rejection_reason: str,
        confluence_snapshot: Optional[Dict[str, Any]] = None,
        harmonic_pattern=None,
    ) -> Signal:
        """Create a shadow signal for rejected patterns (failed quality gates).

        These signals have status REJECTED_BY_FILTER and are used for:
        - Firestore auditing (rejected_signals collection)
        - Discord shadow channel visibility
        - Phase 8 backtesting analysis

        Args:
            symbol: Trading symbol
            asset_class: Asset class (CRYPTO/EQUITY)
            pattern_name: Name of detected pattern
            latest: Latest candle data
            analyzer: Pattern analyzer with pivot data
            rejection_reason: Why the signal was rejected
            confluence_snapshot: Indicator values at rejection time
            harmonic_pattern: Optional HarmonicPattern object for harmonic metadata
        """
        sig_id = get_deterministic_id(f"{symbol}|{pattern_name}|{latest.name}|REJECTED")

        # Create base signal with structural metadata
        # ENABLE SKIP_VALIDATION to permit safe hydration of invalid parameters
        signal = self._create_signal(
            symbol,
            asset_class,
            pattern_name,
            latest,
            sig_id,
            analyzer,
            harmonic_pattern=harmonic_pattern,
            confluence_snapshot=confluence_snapshot,
            force_rejection_reason=rejection_reason,  # Force shadow path
        )

        # Override status and add rejection metadata
        signal.status = SignalStatus.REJECTED_BY_FILTER
        signal.rejection_reason = rejection_reason
        signal.confluence_snapshot = confluence_snapshot

        # Rejected signals have shorter TTL (24 hours) - for operational audit only (Staff Review P4)
        now = datetime.now(timezone.utc)
        signal.delete_at = now + timedelta(hours=24)
        signal.exit_time = now

        return signal

    def check_exits(
        self,
        active_signals: list[Signal],
        symbol: str,
        asset_class: AssetClass,
        dataframe: Optional[pd.DataFrame] = None,
    ) -> list[Signal]:
        """
        Check active signals for exit conditions and trailing stop updates.

        Returns signals requiring persistence updates, including:
        - Status changes (TP1/TP2/TP3 hits, invalidations)
        - Trailing stop updates for Runner positions (TP1_HIT or TP2_HIT status)

        Exit Rules:
        1. Take Profit: Latest High >= Signal.take_profit_1/2
        2. Structural Invalidation: Latest Close < Signal.invalidation_price
        3. Color Flip: Latest candle is a Bearish Engulfing candle.
        4. Hard Sells: RSI > 80 or ADX Peaking.

        Active Trailing (Runner Phase):
        - For signals in TP1_HIT or TP2_HIT, updates take_profit_3 when
          Chandelier Exit moves higher than current value.
        - Sets _trail_updated attribute to distinguish from status exits.
        - Sets _previous_tp3 attribute for notification threshold calculation.
        """
        # 1. Fetch Data
        if dataframe is not None:
            df = dataframe
        else:
            df = self.market_provider.get_daily_bars(
                symbol=symbol, asset_class=asset_class, lookback_days=365
            )
        if df.empty:
            return []

        # 2. Add Indicators & Patterns
        self.indicators.add_all_indicators(df)
        analyzer = self.pattern_analyzer_cls(dataframe=df)
        analyzed_df = analyzer.check_patterns()

        logger.debug(
            f"analyzed_df type={type(analyzed_df)}, "
            f"empty check: {getattr(analyzed_df, 'empty', 'N/A')}"
        )

        if analyzed_df.empty:
            logger.debug("analyzed_df is empty, returning early")
            return []

        latest = analyzed_df.iloc[-1]
        exited_signals = []

        # Current Candle Metrics
        current_high = float(latest["high"])
        current_low = float(latest["low"])
        current_close = float(latest["close"])

        logger.debug(
            f"check_exits: analyzed_df has {len(analyzed_df)} rows, "
            f"high={current_high}, low={current_low}, close={current_close}"
        )

        # Chandelier Exit for Runner (direction-aware)
        chandelier_exit_long = (
            float(latest["CHANDELIER_EXIT_LONG"])
            if "CHANDELIER_EXIT_LONG" in latest
            else None
        )
        chandelier_exit_short = (
            float(latest["CHANDELIER_EXIT_SHORT"])
            if "CHANDELIER_EXIT_SHORT" in latest
            else None
        )

        # Invalidation triggers
        is_bearish_engulfing = latest.get("bearish_engulfing", False)

        # Check RSI > 80
        rsi_val = latest.get("RSI_14", 50)
        if pd.isna(rsi_val):
            rsi_val = 50
        rsi_overbought = rsi_val > 80

        # Check ADX Peaking
        adx_val = latest.get("ADX_14", 0)
        # Get prev row
        if len(analyzed_df) > 1:
            prev = analyzed_df.iloc[-2]
            adx_prev = prev.get("ADX_14", 0)
        else:
            adx_prev = 0

        adx_peaking = (adx_val > 50) and (adx_val < adx_prev)

        for signal in active_signals:
            exit_triggered = False
            trail_updated = False
            original_status = signal.status

            # ============================================================
            # SKIP-ON-CREATION GATE (Issue 99 Fix)
            # Prevent same-run evaluation of newly created signals.
            # Signals created within the last 5 minutes are skipped to avoid
            # "Immediate Invalidation" where a signal is invalidated using the
            # same candle data that triggered its creation.
            # ============================================================
            now_utc = datetime.now(timezone.utc)
            if signal.created_at:
                signal_age_seconds = (now_utc - signal.created_at).total_seconds()
                if signal_age_seconds < 300:  # 5-minute cooldown
                    logger.debug(
                        f"Skip newly created signal {signal.signal_id} "
                        f"(age={signal_age_seconds:.0f}s < 300s cooldown)"
                    )
                    continue

            # ============================================================
            # STALE SIGNAL GUARD (Defense-in-Depth)
            # Skip WAITING signals that are past their valid_until date.
            # These should be handled by the expiration logic in main.py,
            # but we guard here to prevent false exits on stale data.
            # ============================================================
            if (
                signal.status == SignalStatus.WAITING
                and signal.valid_until
                and now_utc > signal.valid_until
            ):
                logger.debug(
                    f"Skip expired WAITING signal {signal.signal_id} "
                    f"(valid_until={signal.valid_until})"
                )
                continue

            # Determine side once for this signal
            is_long = signal.side != OrderSide.SELL

            logger.debug(
                f"Processing signal {signal.signal_id}: status={signal.status}, "
                f"side={signal.side}, is_long={is_long}, tp1={signal.take_profit_1}, "
                f"tp2={signal.take_profit_2}, tp3={signal.take_profit_3}"
            )

            # --- ACTIVE TRAILING (Runner Phase) ---
            # For signals in TP1_HIT or TP2_HIT, update trailing stop
            # Long: trailing stop moves UP (chandelier_exit_long > current)
            # Short: trailing stop moves DOWN (chandelier_exit_short < current)
            if signal.status in (SignalStatus.TP1_HIT, SignalStatus.TP2_HIT):
                current_tp3 = signal.take_profit_3 or 0.0
                is_long = signal.side != OrderSide.SELL

                if is_long and chandelier_exit_long:
                    # Long: update if new trailing stop is HIGHER
                    # (initialization when current_tp3 == 0 is handled implicitly: any positive > 0)
                    if chandelier_exit_long > current_tp3:
                        object.__setattr__(signal, "_previous_tp3", current_tp3)
                        signal.take_profit_3 = chandelier_exit_long
                        trail_updated = True
                elif not is_long and chandelier_exit_short:
                    # Short: update if new trailing stop is LOWER
                    # For shorts, lower is better (locking in more profit as price falls)
                    # Initialization: when current_tp3 == 0, always set initial stop
                    # Trailing: only update if new stop is lower (more favorable)
                    should_update = (
                        current_tp3 == 0.0  # Initialization
                        or chandelier_exit_short < current_tp3  # Trailing down
                    )
                    if should_update:
                        object.__setattr__(signal, "_previous_tp3", current_tp3)
                        signal.take_profit_3 = chandelier_exit_short
                        trail_updated = True

            # Get appropriate chandelier exit based on side
            is_long = signal.side != OrderSide.SELL
            chandelier_exit = chandelier_exit_long if is_long else chandelier_exit_short

            # --- PROFIT TAKING ---

            # 1. Check TP3 (Runner) - Chandelier Exit
            # Long: exit if close < chandelier (price fell below trailing stop)
            # Short: exit if close > chandelier (price rose above trailing stop)
            tp3_exit_triggered = False
            if chandelier_exit and signal.status in (
                SignalStatus.TP1_HIT,
                SignalStatus.TP2_HIT,
            ):
                if is_long and current_close < chandelier_exit:
                    tp3_exit_triggered = True
                elif not is_long and current_close > chandelier_exit:
                    tp3_exit_triggered = True

            if tp3_exit_triggered:
                # Determine if profitable
                is_profitable = (
                    (current_close > signal.entry_price)
                    if is_long
                    else (current_close < signal.entry_price)
                )
                if is_profitable:
                    signal.status = SignalStatus.TP3_HIT
                    signal.exit_reason = ExitReason.TP_HIT
                else:
                    signal.status = SignalStatus.INVALIDATED
                    signal.exit_reason = ExitReason.STOP_LOSS

                exit_triggered = True

            # 2. Check TP2
            # Guard: Only trigger if already TP1_HIT.
            # Long: price rises above TP2 (high >= target)
            # Short: price falls below TP2 (low <= target)
            if (
                not exit_triggered
                and signal.take_profit_2
                and signal.status == SignalStatus.TP1_HIT
            ):
                tp2_hit = False
                if is_long and current_high >= signal.take_profit_2:
                    tp2_hit = True
                elif not is_long and current_low <= signal.take_profit_2:
                    tp2_hit = True

                if tp2_hit:
                    signal.status = SignalStatus.TP2_HIT
                    signal.exit_reason = ExitReason.TP2
                    exit_triggered = True

            # 3. Check TP1
            # Guard: Only trigger if WAITING or ACTIVE.
            # If already TP1_HIT, we want to skip this and check TP2 (handled above).
            # Long: price rises above TP1 (high >= target)
            # Short: price falls below TP1 (low <= target)
            if (
                not exit_triggered
                and signal.take_profit_1
                and signal.status in (SignalStatus.WAITING, SignalStatus.ACTIVE)
            ):
                tp1_hit = False
                if is_long and current_high >= signal.take_profit_1:
                    tp1_hit = True
                elif not is_long and current_low <= signal.take_profit_1:
                    tp1_hit = True

                logger.debug(
                    f"TP1 check: is_long={is_long}, high={current_high}, "
                    f"tp1={signal.take_profit_1}, tp1_hit={tp1_hit}"
                )

                if tp1_hit:
                    signal.status = SignalStatus.TP1_HIT
                    signal.suggested_stop = signal.entry_price
                    signal.exit_reason = ExitReason.TP1
                    exit_triggered = True
                    logger.debug("TP1 HIT! exit_triggered=True")

            # --- INVALIDATION ---
            if not exit_triggered:
                # 1. Structural Invalidation
                # Long: price falls below invalidation level
                # Short: price rises above invalidation level
                invalidation_triggered = False
                if signal.invalidation_price:
                    if is_long and current_close < signal.invalidation_price:
                        invalidation_triggered = True
                    elif not is_long and current_close > signal.invalidation_price:
                        invalidation_triggered = True

                if invalidation_triggered:
                    signal.status = SignalStatus.INVALIDATED
                    signal.exit_reason = ExitReason.STRUCTURAL_INVALIDATION
                    exit_triggered = True

                # 2. Dynamic Invalidation (Color Flip / Indicators)
                # Note: bearish_engulfing, rsi_overbought, adx_peaking are Long-specific
                # For Short positions, these would indicate favorable conditions, not invalidation
                # NOTE: Bullish equivalents for Short invalidation not yet implemented.
                # Short signals use structural invalidation only for now.
                elif is_long and (is_bearish_engulfing or rsi_overbought or adx_peaking):
                    signal.status = SignalStatus.INVALIDATED
                    signal.exit_reason = ExitReason.COLOR_FLIP
                    exit_triggered = True

            # Include signal if exit triggered OR if trail updated
            logger.debug(
                f"End of loop: exit_triggered={exit_triggered}, trail_updated={trail_updated}"
            )
            if exit_triggered:
                # Set exit_time for cooldown tracking (Issue #117)
                signal.exit_time = now_utc

                # Log signal age at exit for Issue 99 debugging
                if signal.created_at:
                    system_age_hours = (
                        now_utc - signal.created_at
                    ).total_seconds() / 3600

                    # Calculate Market Age (time since candle date) for pattern debugging
                    market_age_hours = 0.0
                    try:
                        # ds is date, convert to datetime at midnight UTC
                        ds_dt = datetime.combine(signal.ds, datetime.min.time()).replace(
                            tzinfo=timezone.utc
                        )
                        market_age_hours = (now_utc - ds_dt).total_seconds() / 3600
                    except Exception:
                        pass  # robust fallback

                    logger.info(
                        f"Exit triggered for {signal.signal_id}: "
                        f"system_age={system_age_hours:.1f}h, market_age={market_age_hours:.1f}h, "
                        f"reason={signal.exit_reason}, pattern={signal.pattern_name}"
                    )

                # Detect Status Jump (e.g., WAITING -> TP2_HIT)
                if (
                    original_status in (SignalStatus.WAITING, SignalStatus.ACTIVE)
                    and signal.status == SignalStatus.TP2_HIT
                ):
                    logger.info(
                        f"Status Jump detected for {signal.signal_id}: WAITING -> TP2_HIT"
                    )
                    object.__setattr__(signal, "_status_jump", True)

                exited_signals.append(signal)
                logger.debug("Appended signal to exited_signals (exit_triggered)")
            elif trail_updated:
                # Mark for main.py to distinguish from status changes
                # Use object.__setattr__ to bypass Pydantic's validation
                object.__setattr__(signal, "_trail_updated", True)
                exited_signals.append(signal)
                logger.debug("Appended signal to exited_signals (trail_updated)")

        logger.debug(f"Returning {len(exited_signals)} exited signals")
        return exited_signals
