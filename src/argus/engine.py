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
    symbol: str
    timeframe: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    entry_criteria: List[Dict[str, Any]] = Field(default_factory=list)
    exit_criteria: Dict[str, Any] = Field(default_factory=dict)
    indicators_config: Dict[str, Any] = Field(default_factory=dict)
    patterns: List[str] = Field(default_factory=list)
    slippage: float = Field(default=0.001)
    fees: float = Field(default=0.001)


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
        # Normalize and map
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
                    # Note: pandas-ta naming can vary, but usually matches IND_PERIOD
                    # We look for the new column
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
        asset_class: AssetClass = AssetClass.CRYPTO,
    ) -> EngineBacktestResults:
        """
        Run a single-symbol backtest based on StrategyInput.
        """
        if not self.data_provider:
            raise ValueError("MarketDataProvider is required for ArgusEngine.run")

        # 1. Fetch Data
        end_dt = config.end_date or (datetime.now(timezone.utc) - timedelta(minutes=15))
        start_dt = config.start_date or (end_dt - timedelta(days=365))

        data = self.data_provider.get_historical_bars(
            symbol=config.symbol,
            asset_class=asset_class,
            timeframe_str=config.timeframe,
            start_dt=start_dt,
            end_dt=end_dt,
        )

        if data.empty:
            raise ValueError(f"No data found for {config.symbol} on {config.timeframe}")

        # 2. Add technical indicators (standard stack)
        TechnicalIndicators.add_all_indicators(data)

        # 3. Pattern Recognition (Trigger)
        pattern_analyzer = PatternAnalyzer(data)
        pattern_results = pattern_analyzer.check_patterns()

        harmonic_analyzer = HarmonicAnalyzer(pattern_analyzer.pivots)
        harmonic_patterns = harmonic_analyzer.scan_all_patterns()

        # Build trigger mask (OR patterns)
        trigger_mask = pd.Series(False, index=data.index)
        pattern_counts = {}

        if config.patterns:
            for p_name in config.patterns:
                # Check standard patterns
                if p_name in pattern_results.columns:
                    trigger_mask |= pattern_results[p_name].fillna(False)
                    pattern_counts[p_name] = int(pattern_results[p_name].sum())
                # Check harmonic patterns
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

        # 4. Filter Evaluation (AND criteria)
        filter_mask = self._evaluate_criteria(data, config.entry_criteria)

        # 5. Signal Combination (Trigger & Filter)
        # If no patterns requested, criteria themselves act as triggers
        if not config.patterns:
            entries = filter_mask
        else:
            entries = trigger_mask & filter_mask

        # For exits, we currently use the exit_criteria from contract (SL/TP handles it)
        # But we create an empty exits_df for from_signals
        exits = pd.Series(False, index=data.index)

        # 6. VectorBT Simulation
        portfolio = vbt.Portfolio.from_signals(
            close=data["close"],
            entries=entries,
            exits=exits,
            sl_stop=config.exit_criteria.get("stop_loss_pct"),
            tp_stop=config.exit_criteria.get("take_profit_pct"),
            fees=config.fees,
            slippage=config.slippage,
            freq=self._to_pandas_freq(config.timeframe),
        )

        # 7. Metrics Extraction
        stats = portfolio.stats(silence_warnings=True)

        def get_stat(key, default=0.0):
            val = stats.get(key, default)
            return float(val) if not pd.isna(val) else default

        # Equity Curve (Flattened as list of floats)
        equity_curve = portfolio.value().tolist()

        # Trades (Strict TradeSnippet format)
        trades = []
        if not portfolio.trades.records_readable.empty:
            for t in portfolio.trades.records_readable.to_dict("records"):
                # Handle potential key variations in VectorBT output
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
            reality_gap_metrics={"slippage_impact_pct": 0.0, "fee_impact_pct": 0.0},
            pattern_breakdown=pattern_counts,
        )
