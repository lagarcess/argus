from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

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
    exit_criteria: List[Dict[str, Any]] = Field(default_factory=list)
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    indicators_config: Dict[str, Any] = Field(default_factory=dict)
    patterns: List[str] = Field(default_factory=list)
    slippage: float = Field(default=0.001)
    fees: float = Field(default=0.001)

    # Execution Forge (Institutional Physics)
    participation_rate: float = Field(default=0.1)
    execution_priority: float = Field(default=1.0)
    va_sensitivity: float = Field(default=1.0)
    slippage_model: str = Field(default="vol_adjusted")

    @property
    def symbol(self) -> str:
        """Backward-compat accessor for single-symbol internal paths."""
        return self.symbols[0] if self.symbols else ""


# BacktestConfig is a semantic alias used at the API boundary.
BacktestConfig = StrategyInput


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
    ideal_equity_curve: List[float] = Field(default_factory=list)
    benchmark_equity_curve: List[float] = Field(default_factory=list)
    benchmark_symbol: Optional[str] = None
    fidelity_score: float = 1.0
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

    def _get_benchmark_data(
        self,
        asset_class: AssetClass,
        start_dt: datetime,
        end_dt: datetime,
        timeframe: str,
        target_index: pd.DatetimeIndex,
    ) -> tuple[Optional[str], List[float]]:
        """
        Fetch benchmark data (SPY or BTC) and return (symbol, normalized_curve).
        The curve is normalized to 100.0 at the first overlapping point.
        """
        benchmark_symbol = "SPY" if asset_class == AssetClass.EQUITY else "BTC/USD"

        try:
            # Note: We use the same data_provider but a fixed benchmark asset class mapping
            bench_ac = (
                AssetClass.EQUITY if benchmark_symbol == "SPY" else AssetClass.CRYPTO
            )

            df = self.data_provider.get_historical_bars(
                symbol=benchmark_symbol,
                asset_class=bench_ac,
                timeframe_str=timeframe,
                start_dt=start_dt,
                end_dt=end_dt,
            )

            if df.empty:
                return None, []

            # Reindex to match the simulation timeline
            bench_close = df["close"].reindex(target_index).ffill().bfill()

            # Normalize to 100.0
            if not bench_close.empty and bench_close.iloc[0] != 0:
                normalized = (bench_close / bench_close.iloc[0]) * 100.0
                return benchmark_symbol, normalized.tolist()

            return benchmark_symbol, []
        except Exception as e:
            logger.warning(f"Failed to fetch benchmark {benchmark_symbol}: {e}")
            return None, []

    def _run_single_symbol(
        self,
        symbol: str,
        config: StrategyInput,
        asset_class: AssetClass,
        start_dt: datetime,
        end_dt: datetime,
    ) -> tuple[pd.Series, pd.Series, pd.DataFrame, Dict[str, int], pd.Series]:
        """
        Fetch data and generate entry/exit signal Series for one symbol.
        Returns (close_series, entries_series, data_df, pattern_counts, vol_drag).
        """
        if not self.data_provider:
            raise ValueError("MarketDataProvider is required for ArgusEngine.run")

        data = self.data_provider.get_historical_bars(
            symbol=symbol,
            asset_class=asset_class,
            timeframe_str=config.timeframe,
            start_dt=start_dt,
            end_dt=end_dt,
        )

        if data.empty:
            raise ValueError(f"No data found for {symbol} on {config.timeframe}")

        # Add technical indicators
        TechnicalIndicators.add_all_indicators(data)

        # Calculate Volatility Drag for the Execution Forge
        vol_drag = TechnicalIndicators.get_vol_drag_series(data)

        # Pattern Recognition
        pattern_analyzer = PatternAnalyzer(data)
        pattern_results = pattern_analyzer.check_patterns()

        harmonic_analyzer = HarmonicAnalyzer(pattern_analyzer.pivots)
        harmonic_patterns = harmonic_analyzer.scan_all_patterns()

        # Build trigger mask (OR patterns)
        trigger_mask = pd.Series(False, index=data.index)
        pattern_counts: Dict[str, int] = {}

        if config.patterns:
            for p_name in config.patterns:
                if p_name in pattern_results.columns:
                    trigger_mask |= pattern_results[p_name].fillna(False)
                    pattern_counts[p_name] = int(pattern_results[p_name].sum())
                else:
                    h_matches = [
                        h
                        for h in harmonic_patterns
                        if h.pattern_type.lower() == p_name.lower()
                    ]
                    if h_matches:
                        for h in h_matches:
                            trigger_mask.loc[h.pivots[-1].index] = True
                        pattern_counts[p_name] = len(h_matches)

            if not any(pattern_counts.values()):
                logger.debug("No requested patterns found in the dataset.")

        # Filter Evaluation (AND criteria)
        filter_mask = self._evaluate_criteria(data, config.entry_criteria)

        # Signal Combination
        if not config.patterns:
            entries = filter_mask
        else:
            entries = trigger_mask & filter_mask

        return data["close"], entries, data, pattern_counts, vol_drag

    def run(
        self,
        config: StrategyInput,
        asset_class: AssetClass = AssetClass.CRYPTO,
    ) -> EngineBacktestResults:
        """
        Run a single or multi-symbol backtest using VectorBT's native Portfolio.
        Single-symbol: standard from_signals flow.
        Multi-symbol: vectorized Portfolio with one column per symbol — no Python loops
        for simulation (signals are generated per-symbol, portfolio runs in one pass).
        """
        if not self.data_provider:
            raise ValueError("MarketDataProvider is required for ArgusEngine.run")

        end_dt = config.end_date or (datetime.now(timezone.utc) - timedelta(minutes=15))
        start_dt = config.start_date or (end_dt - timedelta(days=365))

        freq = self._to_pandas_freq(config.timeframe)
        sl_stop = config.stop_loss_pct
        tp_stop = config.take_profit_pct

        if len(config.symbols) == 1:
            # ── Single-symbol path ──────────────────────────────────────────
            symbol = config.symbols[0]
            close, entries, data, pattern_counts, vol_drag = self._run_single_symbol(
                symbol, config, asset_class, start_dt, end_dt
            )
            exits = pd.Series(False, index=close.index)

            # PASS 1: Ideal Simulation (Zero drag)
            ideal_portfolio = vbt.Portfolio.from_signals(
                close=close,
                entries=entries,
                exits=exits,
                sl_stop=sl_stop,
                tp_stop=tp_stop,
                fees=0,
                slippage=0,
                freq=freq,
            )

            # PASS 2: Realistic Simulation (Execution Forge)
            # 1. Volatility-Adjusted Slippage
            va_sensitivity = getattr(config, "va_sensitivity", 1.0)
            execution_priority = getattr(config, "execution_priority", 1.0)

            # Asymmetric Execution Model: Exits/Sells are ~50% more expensive than Buys.
            # We apply a 1.25x "Reality Factor" to the base slippage to model this asymmetry.
            base_slippage = config.slippage * execution_priority * 1.25
            adjusted_slippage = base_slippage * (1.0 + (vol_drag - 1.0) * va_sensitivity)

            # 2. POV Gating (Participation of Volume)
            # Default to 10% (0.1) if not specified (Standard institutional cap)
            participation_rate = getattr(config, "participation_rate", 0.1)
            # size is in 'units' (shares/contracts). We cap units based on bar volume.
            size = data["volume"] * participation_rate

            portfolio = vbt.Portfolio.from_signals(
                close=close,
                entries=entries,
                exits=exits,
                sl_stop=sl_stop,
                tp_stop=tp_stop,
                fees=config.fees,
                slippage=adjusted_slippage,
                size=size,
                size_type="amount",  # Fixed units cap
                freq=freq,
            )

            # Calculate Fidelity Score (Robust Threshold Model)
            # Deviations > 20% in return result in 0% fidelity.
            ideal_return = float(ideal_portfolio.total_return())
            real_return = float(portfolio.total_return())
            fidelity_score = max(0.0, 1.0 - (abs(ideal_return - real_return) / 0.20))
        else:
            # ── Multi-symbol vectorized path ─────────────────────────────────
            logger.info(
                f"Running multi-symbol backtest for {len(config.symbols)} symbols"
            )
            close_dict: Dict[str, pd.Series] = {}
            entries_dict: Dict[str, pd.Series] = {}
            vol_drag_dict: Dict[str, pd.Series] = {}
            volume_dict: Dict[str, pd.Series] = {}
            pattern_counts: Dict[str, int] = {}

            for sym in config.symbols:
                try:
                    close_s, entries_s, data_s, sym_patterns, vol_drag_s = (
                        self._run_single_symbol(
                            sym, config, asset_class, start_dt, end_dt
                        )
                    )
                    close_dict[sym] = close_s
                    entries_dict[sym] = entries_s
                    vol_drag_dict[sym] = vol_drag_s
                    volume_dict[sym] = data_s["volume"]

                    # Aggregate pattern counts across symbols
                    for k, v in sym_patterns.items():
                        pattern_counts[k] = pattern_counts.get(k, 0) + v
                except ValueError as e:
                    logger.warning(f"Skipping {sym}: {e}")

            if not close_dict:
                raise ValueError(f"No valid data found for any of {config.symbols}")

            # Align all series to a common index
            close_df = pd.DataFrame(close_dict).dropna(how="all")
            entries_df = pd.DataFrame(entries_dict).reindex(close_df.index).fillna(False)
            exits_df = pd.DataFrame(False, index=close_df.index, columns=close_df.columns)
            vol_drag_df = pd.DataFrame(vol_drag_dict).reindex(close_df.index).fillna(1.0)
            volume_df = pd.DataFrame(volume_dict).reindex(close_df.index).fillna(0)

            # PASS 1: Ideal Simulation
            ideal_portfolio = vbt.Portfolio.from_signals(
                close=close_df,
                entries=entries_df,
                exits=exits_df,
                sl_stop=sl_stop,
                tp_stop=tp_stop,
                fees=0,
                slippage=0,
                freq=freq,
            )

            # PASS 2: Realistic Simulation
            va_sensitivity = getattr(config, "va_sensitivity", 1.0)
            execution_priority = getattr(config, "execution_priority", 1.0)

            # Option A: Scaled Slippage (Priority 1.0 = Taker, 0.0 = Maker)
            # 1.25x Reality Factor applied for Sell-Side asymmetry
            base_slippage = config.slippage * execution_priority * 1.25
            adjusted_slippage = base_slippage * (
                1.0 + (vol_drag_df - 1.0) * va_sensitivity
            )

            participation_rate = getattr(config, "participation_rate", 0.1)
            size_df = volume_df * participation_rate

            portfolio = vbt.Portfolio.from_signals(
                close=close_df,
                entries=entries_df,
                exits=exits_df,
                sl_stop=sl_stop,
                tp_stop=tp_stop,
                fees=config.fees,
                slippage=adjusted_slippage,
                size=size_df,
                size_type="amount",
                freq=freq,
            )

            # Calculate Fidelity Score (Robust Threshold Model)
            ideal_return = (
                float(ideal_portfolio.total_return().mean())
                if hasattr(ideal_portfolio.total_return(), "mean")
                else float(ideal_portfolio.total_return())
            )
            real_return = (
                float(portfolio.total_return().mean())
                if hasattr(portfolio.total_return(), "mean")
                else float(portfolio.total_return())
            )
            fidelity_score = max(0.0, 1.0 - (abs(ideal_return - real_return) / 0.20))

        # ── Reality Gap Attribution (Post-Sim Decomposition) ────────────
        # Instead of redundant runs, we decompose the Realistic Pass (portfolio)
        # by comparing its trade records against the theoretical Ideal state.

        total_pnl = (
            float(portfolio.total_profit().sum())
            if hasattr(portfolio.total_profit(), "sum")
            else float(portfolio.total_profit())
        )
        ideal_pnl = (
            float(ideal_portfolio.total_profit().sum())
            if hasattr(ideal_portfolio.total_profit(), "sum")
            else float(ideal_portfolio.total_profit())
        )

        # 1. Fee Attrition (Directly from Trade Ledger)
        total_fees = 0.0
        if not portfolio.trades.records.empty:
            fees_sr = (
                portfolio.trades.records["entry_fees"]
                + portfolio.trades.records["exit_fees"]
            )
            total_fees = float(fees_sr.sum())

        # 2. Slippage Drag (Base cost vs Vol Hazard)
        # We isolate the 'Fixed' component of slippage by summing volume * config.slippage
        total_volume = 0.0
        fixed_slippage_drag = 0.0
        if not portfolio.trades.records.empty:
            # size is the quantity, we need price * size for volume
            # We use entry_price * size as a proxy for total volume (in and out)
            volume_sr = (
                portfolio.trades.records["entry_price"] * portfolio.trades.records["size"]
            )
            total_volume = float(volume_sr.sum()) * 2.0  # Approximation for round trip

            fixed_slippage_drag = total_volume * base_slippage  # Use scaled base slippage

        # 3. Vol Hazard (The "Execution Forge" special)
        # Residual Gap = (Ideal PnL - Realistic PnL) - Fees - Fixed Slippage
        # This captures both VA-Slippage and POV Opportunity Cost (missed fills).
        total_gap = ideal_pnl - total_pnl
        vol_hazard = max(0.0, total_gap - total_fees - fixed_slippage_drag)

        # Normalize metrics to Percentage of Initial Capital
        init_cap = (
            float(portfolio.init_cash.sum())
            if hasattr(portfolio.init_cash, "sum")
            else float(portfolio.init_cash)
        )
        reality_gap_metrics = {
            "fee_impact_pct": (total_fees / init_cap) * 100.0 if init_cap > 0 else 0.0,
            "slippage_impact_pct": (fixed_slippage_drag / init_cap) * 100.0
            if init_cap > 0
            else 0.0,
            "vol_hazard_pct": (vol_hazard / init_cap) * 100.0 if init_cap > 0 else 0.0,
            "fidelity_score": fidelity_score * 100.0,
        }

        # ── Metrics Extraction (same for both paths) ─────────────────────
        stats = portfolio.stats(silence_warnings=True)

        def get_stat(key: str, default: float = 0.0) -> float:
            val = stats.get(key, default)
            return float(val) if not pd.isna(val) else default

        # Equity curves: portfolio total value flattened to list of floats
        _val = portfolio.value()
        if hasattr(_val, "sum"):
            equity_curve: List[float] = (
                _val.sum(axis=1).tolist() if hasattr(_val, "columns") else _val.tolist()
            )
        else:
            equity_curve = list(_val)

        _val_ideal = ideal_portfolio.value()
        if hasattr(_val_ideal, "sum"):
            ideal_equity_curve: List[float] = (
                _val_ideal.sum(axis=1).tolist()
                if hasattr(_val_ideal, "columns")
                else _val_ideal.tolist()
            )
        else:
            ideal_equity_curve = list(_val_ideal)

        # Trades (Strict TradeSnippet format)
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

        # ── Benchmark Comparison ──────────────────────────────────────────
        bench_sym, bench_curve = self._get_benchmark_data(
            asset_class=asset_class,
            start_dt=start_dt,
            end_dt=end_dt,
            timeframe=config.timeframe,
            target_index=portfolio.wrapper.index,
        )

        return EngineBacktestResults(
            total_return_pct=get_stat("Total Return [%]"),
            win_rate=get_stat("Win Rate [%]"),
            sharpe_ratio=get_stat("Sharpe Ratio"),
            sortino_ratio=get_stat("Sortino Ratio"),
            calmar_ratio=get_stat("Calmar Ratio"),
            profit_factor=get_stat("Profit Factor"),
            expectancy=get_stat("Expectancy"),
            max_drawdown_pct=float(get_stat("Max Drawdown [%]")),
            equity_curve=equity_curve,
            ideal_equity_curve=ideal_equity_curve,
            benchmark_equity_curve=bench_curve,
            benchmark_symbol=bench_sym,
            fidelity_score=float(fidelity_score),
            trades=trades,
            reality_gap_metrics=reality_gap_metrics,
            pattern_breakdown=pattern_counts,
        )
