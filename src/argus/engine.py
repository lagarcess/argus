from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import vectorbt as vbt
from loguru import logger
from pydantic import BaseModel, Field

from argus.analysis.harmonics import HarmonicAnalyzer
from argus.analysis.indicators import TechnicalIndicators
from argus.analysis.patterns import PatternAnalyzer
from argus.domain.schemas import AssetClass
from argus.market.data_provider import MarketDataProvider

# --- Data Schemas ---


class StrategyInput(BaseModel):
    """Domain-level configuration for signal generation, mirroring API StrategyCreate."""

    name: str = Field(default="Unnamed Strategy")
    symbols: list[str] = Field(default_factory=list, min_length=1)
    timeframe: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    entry_criteria: List[Dict[str, Any]] = Field(default_factory=list)
    exit_criteria: Dict[str, Any] = Field(default_factory=dict)
    indicators_config: Dict[str, Any] = Field(default_factory=dict)
    patterns: List[str] = Field(default_factory=list)
    slippage: float = Field(default=0.001)
    fees: float = Field(default=0.001)

    @property
    def symbol(self) -> str:
        """Backward-compat accessor for single-symbol internal paths."""
        return self.symbols[0] if self.symbols else ""


# BacktestConfig is a semantic alias used at the API boundary.
class BacktestConfig:
    """
    Modular Interceptor wrapper around StrategyInput.
    Responsible for fetching data and producing Aligned N-Dimensional Arrays
    for multi-asset vectorization.
    """

    def __init__(self, config: StrategyInput):
        self.config = config

    def prepare_vectors(
        self,
        data_provider: MarketDataProvider,
        start_dt: datetime,
        end_dt: datetime,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Fetch data for all symbols and align them into orthagonal matrices (Time x Assets).
        Handles UTC normalization and institutional ffill bias correction.
        """
        close_dict = {}
        open_dict = {}
        high_dict = {}
        low_dict = {}
        volume_dict = {}

        for sym in self.config.symbols:
            try:
                # Dynamic Asset Class deduction per symbol
                sym_asset_class = AssetClass.from_symbol(sym)

                data = data_provider.get_historical_bars(
                    symbol=sym,
                    asset_class=sym_asset_class,
                    timeframe_str=self.config.timeframe,
                    start_dt=start_dt,
                    end_dt=end_dt,
                )
                if data.empty:
                    logger.warning(f"No data found for {sym} on {self.config.timeframe}")
                    continue

                if data.index.tz is None:
                    data.index = data.index.tz_localize("UTC")
                else:
                    data.index = data.index.tz_convert("UTC")

                close_dict[sym] = data["close"]
                open_dict[sym] = data["open"]
                high_dict[sym] = data["high"]
                low_dict[sym] = data["low"]
                volume_dict[sym] = data["volume"]

            except ValueError as e:
                logger.warning(f"Skipping {sym}: {e}")

        if not close_dict:
            raise ValueError(f"No valid data found for any of {self.config.symbols}")

        # Memory Sanity Gate
        est_rows = max(len(s) for s in close_dict.values())
        est_bytes = 5 * 8 * est_rows * len(close_dict)

        if est_bytes > 1_073_741_824:  # > 1GB
            logger.error(
                f"Allocation Guard Violation: Aligned matrix footprint estimated at {est_bytes / (1024*1024):.2f} MB."
            )
            raise MemoryError(
                "Requested simulation exceeds maximum memory allocation limits. Please reduce symbol count or timeframe range."
            )

        # Institutional Alignment: ffill ONLY. Drop rows where all assets are NaN.
        # This prevents look-ahead bias and correctly handles assets with different inception dates.
        close_df = pd.DataFrame(close_dict).ffill().dropna(how="all")
        open_df = pd.DataFrame(open_dict).reindex(close_df.index).ffill()
        high_df = pd.DataFrame(high_dict).reindex(close_df.index).ffill()
        low_df = pd.DataFrame(low_dict).reindex(close_df.index).ffill()
        volume_df = pd.DataFrame(volume_dict).reindex(close_df.index).fillna(0)

        return open_df, high_df, low_df, close_df, volume_df


class EngineBacktestResults(BaseModel):
    """Flattened backtest results matching the V1 API contract."""

    total_return_pct: float
    win_rate: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    profit_factor: float
    expectancy: float
    max_drawdown_pct: float
    equity_curve: List[float]
    trades: List[Dict[str, Any]]
    reality_gap_metrics: Dict[str, float]
    pattern_breakdown: Dict[str, int]


# --- Argus Engine ---


class ArgusEngine:
    """
    Stateless, pure facade for Argus Backtesting Engine.
    Orchestrates Data Ingestion, Signal Generation, and Simulation.
    Supports single-symbol and multi-symbol (vectorized VectorBT Portfolio) modes.
    """

    def __init__(self, data_provider: Optional[MarketDataProvider] = None):
        self.data_provider = data_provider

    def _resolve_target(self, df: pd.DataFrame, target: Any) -> pd.Series | float:
        """Resolves target to a Series (if column name) or a float."""
        if isinstance(target, (int, float)):
            return float(target)
        if isinstance(target, str):
            # Try to resolve as an indicator
            if target in df.columns:
                return df[target]
            # Handle standard names like 'close'
            if target.lower() in df.columns:
                return df[target.lower()]
        return 0.0

    def _to_pandas_freq(self, timeframe: str) -> str:
        """Maps Argus timeframe strings to standard Pandas frequency aliases."""
        mapping = {
            "1day": "D",
            "1d": "D",
            "1hour": "h",
            "1h": "h",
            "4hour": "4h",
            "4h": "4h",
            "15min": "15T",
            "15m": "15T",
            "1min": "1T",
            "1m": "1T",
            "month": "M",
            "mo": "M",
            "week": "W",
            "w": "W",
        }
        clean = timeframe.lower().replace(" ", "")
        return mapping.get(clean, timeframe)

    def _evaluate_criteria(
        self, df: pd.DataFrame, criteria: List[Dict[str, Any]]
    ) -> pd.Series:
        """Dynamically evaluates a list of technical criteria into a boolean mask."""
        mask = pd.Series(True, index=df.index)
        if not criteria:
            return mask

        for c in criteria:
            indicator_name = c.get("indicator", "").lower()
            period = c.get("period", 14)
            condition = c.get("condition", "is_above")
            target_raw = c.get("target")

            # 1. Ensure indicator exists in DF
            col_name = f"{indicator_name.upper()}_{period}"
            if col_name not in df.columns:
                try:
                    # pandas-ta dynamic call with validation
                    if not hasattr(df.ta, indicator_name):
                        logger.warning(
                            f"Indicator '{indicator_name}' not supported by pandas-ta"
                        )
                        continue

                    func = getattr(df.ta, indicator_name)
                    func(length=period, append=True)
                    potential_cols = [
                        col
                        for col in df.columns
                        if str(period) in col and indicator_name.upper() in col.upper()
                    ]
                    if potential_cols:
                        col_name = potential_cols[0]
                    else:
                        logger.warning(
                            f"Could not find generated column for {indicator_name}({period})"
                        )
                        continue
                except Exception as e:
                    logger.error(f"Failed to calculate indicator {indicator_name}: {e}")
                    continue

            source = df[col_name]
            target = self._resolve_target(df, target_raw)

            # 2. Evaluate condition
            if condition == "crosses_above":
                condition_met = (source > target) & (
                    source.shift(1)
                    <= (target.shift(1) if isinstance(target, pd.Series) else target)
                )
            elif condition == "crosses_below":
                condition_met = (source < target) & (
                    source.shift(1)
                    >= (target.shift(1) if isinstance(target, pd.Series) else target)
                )
            elif condition == "is_above":
                condition_met = source > target
            elif condition == "is_below":
                condition_met = source < target
            else:
                condition_met = pd.Series(True, index=df.index)

            mask &= condition_met.fillna(False)

        return mask

    def run(
        self,
        config: StrategyInput,
    ) -> EngineBacktestResults:
        """
        Run a single or multi-symbol backtest using VectorBT's native Portfolio.
        Implements Dual-Sim architecture to calculate Reality Gap metrics.
        """
        if not self.data_provider:
            raise ValueError("MarketDataProvider is required for ArgusEngine.run")

        end_dt = config.end_date or (datetime.now(timezone.utc) - timedelta(minutes=15))
        start_dt = config.start_date or (end_dt - timedelta(days=365))

        freq = self._to_pandas_freq(config.timeframe)
        sl_stop = config.exit_criteria.get("stop_loss_pct")
        tp_stop = config.exit_criteria.get("take_profit_pct")

        # ── Vector Preparation Layer ─────────────────────────────────────
        bc = BacktestConfig(config)
        open_df, high_df, low_df, close_df, volume_df = bc.prepare_vectors(
            self.data_provider, start_dt, end_dt
        )

        # Determine signals
        entries_dict: Dict[str, pd.Series] = {}
        pattern_counts: Dict[str, int] = {}

        for sym in config.symbols:
            try:
                if sym not in close_df.columns:
                    continue
                sym_data = pd.DataFrame(
                    {
                        "open": open_df[sym],
                        "high": high_df[sym],
                        "low": low_df[sym],
                        "close": close_df[sym],
                        "volume": volume_df[sym],
                    }
                )

                # Tech Indicators & Patterns
                TechnicalIndicators.add_all_indicators(sym_data)

                pattern_analyzer = PatternAnalyzer(sym_data)
                pattern_results = pattern_analyzer.check_patterns()

                harmonic_analyzer = HarmonicAnalyzer(pattern_analyzer.pivots)
                harmonic_patterns = harmonic_analyzer.scan_all_patterns()

                trigger_mask = pd.Series(False, index=sym_data.index)
                sym_patterns = {}

                if config.patterns:
                    for p_name in config.patterns:
                        if p_name in pattern_results.columns:
                            trigger_mask |= pattern_results[p_name].fillna(False)
                            sym_patterns[p_name] = int(pattern_results[p_name].sum())
                        else:
                            h_matches = [
                                h
                                for h in harmonic_patterns
                                if h.pattern_type.lower() == p_name.lower()
                            ]
                            if h_matches:
                                for h in h_matches:
                                    trigger_mask.loc[h.pivots[-1].index] = True
                                sym_patterns[p_name] = len(h_matches)

                filter_mask = self._evaluate_criteria(sym_data, config.entry_criteria)

                if not config.patterns:
                    entries_s = filter_mask
                else:
                    entries_s = trigger_mask & filter_mask

                entries_dict[sym] = entries_s
                for k, v in sym_patterns.items():
                    pattern_counts[k] = pattern_counts.get(k, 0) + v

            except ValueError as e:
                logger.warning(f"Skipping signal generation for {sym}: {e}")

        if not list(entries_dict.keys()):
            raise ValueError(
                f"No valid signals could be generated for any of {config.symbols}"
            )

        entries_df = pd.DataFrame(entries_dict).reindex(close_df.index).fillna(False)
        exits_df = pd.DataFrame(False, index=close_df.index, columns=close_df.columns)

        # ── Dual-Sim Orchestration ───────────────────────────────────────

        # 1. Ideal Portfolio (0 slippage, 0 fees)
        portfolio_ideal = vbt.Portfolio.from_signals(
            close=close_df,
            entries=entries_df,
            exits=exits_df,
            sl_stop=sl_stop,
            tp_stop=tp_stop,
            fees=0.0,
            slippage=0.0,
            freq=freq,
        )

        # 2. Real Portfolio (configured slippage & fees)
        portfolio_real = vbt.Portfolio.from_signals(
            close=close_df,
            entries=entries_df,
            exits=exits_df,
            sl_stop=sl_stop,
            tp_stop=tp_stop,
            fees=config.fees,
            slippage=config.slippage,
            freq=freq,
        )

        # ── Attribution Engine (Reality Gap) ─────────────────────────────
        ideal_return = portfolio_ideal.total_return()

        ideal_returns_series = portfolio_ideal.returns()
        real_returns_series = portfolio_real.returns()

        # Fidelity Score: Correlation Coefficient
        if isinstance(ideal_returns_series, pd.DataFrame):
            ideal_var = ideal_returns_series.var().mean()
            real_var = real_returns_series.var().mean()
            if ideal_var > 0 and real_var > 0:
                ideal_arr = ideal_returns_series.sum(axis=1).values
                real_arr = real_returns_series.sum(axis=1).values
                fidelity_score = float(np.corrcoef(ideal_arr, real_arr)[0, 1])
            else:
                fidelity_score = 1.0
        else:
            if ideal_returns_series.var() > 0 and real_returns_series.var() > 0:
                fidelity_score = float(
                    np.corrcoef(ideal_returns_series.values, real_returns_series.values)[
                        0, 1
                    ]
                )
            else:
                fidelity_score = 1.0

        if pd.isna(fidelity_score):
            fidelity_score = 1.0

        portfolio_slip_only = vbt.Portfolio.from_signals(
            close=close_df,
            entries=entries_df,
            exits=exits_df,
            sl_stop=sl_stop,
            tp_stop=tp_stop,
            fees=0.0,
            slippage=config.slippage,
            freq=freq,
        )
        portfolio_fee_only = vbt.Portfolio.from_signals(
            close=close_df,
            entries=entries_df,
            exits=exits_df,
            sl_stop=sl_stop,
            tp_stop=tp_stop,
            fees=config.fees,
            slippage=0.0,
            freq=freq,
        )

        slip_return = (
            float(portfolio_slip_only.total_return().mean())
            if isinstance(portfolio_slip_only.total_return(), pd.Series)
            else float(portfolio_slip_only.total_return())
        )
        fee_return = (
            float(portfolio_fee_only.total_return().mean())
            if isinstance(portfolio_fee_only.total_return(), pd.Series)
            else float(portfolio_fee_only.total_return())
        )
        ideal_return_scalar = (
            float(ideal_return.mean())
            if isinstance(ideal_return, pd.Series)
            else float(ideal_return)
        )

        slippage_impact_pct = (
            float(ideal_return_scalar - slip_return) if ideal_return_scalar != 0 else 0.0
        )
        fee_impact_pct = (
            float(ideal_return_scalar - fee_return) if ideal_return_scalar != 0 else 0.0
        )

        if ideal_return_scalar != 0:
            slippage_impact_pct = (slippage_impact_pct / ideal_return_scalar) * 100
            fee_impact_pct = (fee_impact_pct / ideal_return_scalar) * 100

        if fidelity_score < 0.9:
            logger.warning(
                f"REALITY GAP ALERT: Fidelity Score is unusually low ({fidelity_score:.3f}). High variance detected between ideal and real execution."
            )

        # ── Metrics Extraction ───────────────────────────────────────────

        portfolio = portfolio_real
        stats = portfolio.stats(silence_warnings=True)

        def get_stat(key: str, default: float = 0.0) -> float:
            val = stats.get(key, default)
            if isinstance(val, pd.Series):
                val = val.mean()
            return float(val) if not pd.isna(val) else default

        equity_vals = portfolio.value()
        if isinstance(equity_vals, pd.DataFrame):
            equity_curve = equity_vals.sum(axis=1).tolist()
        else:
            equity_curve = equity_vals.tolist()

        trades: List[Dict[str, Any]] = []
        if not portfolio.trades.records_readable.empty:
            for t in portfolio.trades.records_readable.to_dict("records"):
                entry_price = t.get("Entry Price") or t.get("Avg Entry Price") or 0.0
                exit_price = t.get("Exit Price") or t.get("Avg Exit Price") or 0.0
                pnl = t.get("Return") or t.get("PnL") or 0.0

                trades.append(
                    {
                        "entry_time": str(t.get("Entry Timestamp", "")),
                        "entry_price": float(entry_price),
                        "exit_price": float(exit_price),
                        "pnl_pct": float(pnl) * 100.0,
                    }
                )

        return EngineBacktestResults(
            total_return_pct=get_stat("Total Return [%]"),
            win_rate=get_stat("Win Rate [%]"),
            sharpe_ratio=get_stat("Sharpe Ratio"),
            sortino_ratio=get_stat("Sortino Ratio"),
            calmar_ratio=get_stat("Calmar Ratio"),
            profit_factor=get_stat("Profit Factor"),
            expectancy=get_stat("Expectancy"),
            max_drawdown_pct=get_stat("Max Drawdown [%]"),
            equity_curve=equity_curve,
            trades=trades,
            reality_gap_metrics={
                "slippage_impact_pct": float(slippage_impact_pct),
                "fee_impact_pct": float(fee_impact_pct),
                "fidelity_score": float(fidelity_score),
            },
            pattern_breakdown=pattern_counts,
        )
