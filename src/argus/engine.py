from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional

import pandas as pd
import vectorbt as vbt
from loguru import logger
from pydantic import BaseModel, Field

from argus.analysis.harmonics import HarmonicAnalyzer
from argus.analysis.indicators import IndicatorAnalyzer
from argus.analysis.patterns import PatternAnalyzer
from argus.domain.schemas import AssetClass
from argus.market.data_provider import MarketDataProvider

# --- Data Schemas ---


class StrategyConfig(BaseModel):
    """Configuration for signal generation strategy."""

    entry_patterns: List[str] = Field(
        default_factory=list, description="List of pattern names for entry signals."
    )
    exit_patterns: List[str] = Field(
        default_factory=list, description="List of pattern names for exit signals."
    )
    confluence_mode: Literal["OR", "AND"] = Field(
        default="OR", description="Combine patterns with OR vs AND logic."
    )
    slippage: float = Field(
        default=0.001, description="Slippage percentage (0.001 = 0.1%)."
    )
    fees: float = Field(
        default=0.001, description="Trading fees percentage (0.001 = 0.1%)."
    )
    # --- Indicator Confluence ---
    rsi_period: Optional[int] = Field(
        default=None,
        ge=2,
        le=200,
        description="RSI period. When set, RSI is computed and used as confluence filter.",
    )
    rsi_oversold: float = Field(
        default=30.0,
        ge=0.0,
        le=100.0,
        description="RSI threshold below which market is considered oversold (entry signal).",
    )
    rsi_overbought: float = Field(
        default=70.0,
        ge=0.0,
        le=100.0,
        description="RSI threshold above which market is considered overbought (exit signal).",
    )
    ema_period: Optional[int] = Field(
        default=None,
        ge=2,
        le=500,
        description="EMA period. When set, price-vs-EMA crossover used as confluence filter.",
    )
    symbols: Optional[List[str]] = Field(
        default=None,
        max_length=3,
        description="Up to 3 symbols to backtest (max 3 per PRD batch limit).",
    )
    benchmark_symbol: Optional[str] = Field(
        default="SPY",
        description="Benchmark symbol for relative metrics.",
    )


class EquityCurvePoint(BaseModel):
    timestamp: str
    value: float


class TradeResult(BaseModel):
    symbol: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float
    duration_bars: int
    direction: Literal["Long", "Short"]


class MetricsResult(BaseModel):
    total_return_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    win_rate_pct: float
    total_trades: int
    alpha: float
    beta: float
    calmar_ratio: float
    avg_trade_duration: str
    avg_trade_duration_bars: int


class BacktestResult(BaseModel):
    metrics: MetricsResult
    equity_curve: List[EquityCurvePoint]
    benchmark_equity_curve: Optional[List[EquityCurvePoint]] = None
    trades: List[TradeResult]


# --- Argus Engine ---


class ArgusEngine:
    """
    Stateless, pure facade for Argus Backtesting Engine.
    Orchestrates Data Ingestion, Signal Generation, and Simulation.
    """

    def __init__(self, data_provider: Optional[MarketDataProvider] = None):
        self.data_provider = data_provider

    def run(
        self,
        config: StrategyConfig,
        data: Optional[pd.DataFrame] = None,
        symbols: Optional[List[str]] = None,
        asset_class: AssetClass = AssetClass.CRYPTO,
        lookback_days: int = 365,
        timeframe: str = "1Day",
        freq: str = "1d",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> BacktestResult:
        """
        Run the backtest.

        Args:
            config: StrategyConfig for signal combinations
            data: Optional OHLCV DataFrame with MultiIndex [symbol, timestamp] or single [timestamp]
            symbols: Optional list of symbols to fetch if data is not provided
            asset_class: Type of asset being backtested
            lookback_days: Days to look back if fetching data (used if start_date is None)
            timeframe: Timeframe for Alpaca if fetching (e.g., '1Day', '1Min', '15Min')
            freq: Pandas frequency string for VectorBT (e.g., '1d', '1min')
            start_date: Optional start datetime for fetching data
            end_date: Optional end datetime for fetching data (maxes out at now - 15min)

        Returns:
            BacktestResult: Fully Pydantic validated output.
        """
        # Ensure start_dt/end_dt are defined even if data is provided
        if data is not None and not data.empty:
            if hasattr(data.index, "levels"):  # MultiIndex
                times = data.index.get_level_values(1)
            else:
                times = data.index
            start_dt = pd.to_datetime(times.min()).to_pydatetime()
            end_dt = pd.to_datetime(times.max()).to_pydatetime()
        else:
            if not self.data_provider or not symbols:
                raise ValueError(
                    "Must provide either 'data' DataFrame or both 'data_provider' and 'symbols' list."
                )

            # Fetch data with safety buffer
            max_end_dt = datetime.now(timezone.utc) - timedelta(minutes=15)
            if end_date is None or end_date > max_end_dt:
                end_dt = max_end_dt
            else:
                end_dt = end_date

            if start_date is None:
                start_dt = end_dt - timedelta(days=lookback_days)
            else:
                start_dt = start_date

            data = self.data_provider.get_historical_bars(
                symbol=symbols,
                asset_class=asset_class,
                timeframe_str=timeframe,
                start_dt=start_dt,
                end_dt=end_dt,
            )

        if data.empty:
            raise ValueError(
                "Data is empty after fetching and applying 15-minute safety buffer."
            )

        # Fetch benchmark data
        benchmark_data = None
        if config.benchmark_symbol and self.data_provider:
            # Determine asset class from symbol (simple heuristic: contains '/')
            bench_asset_class = (
                AssetClass.CRYPTO if "/" in config.benchmark_symbol else AssetClass.EQUITY
            )
            try:
                # Need to resolve start_dt/end_dt if data was provided directly
                benchmark_data = self.data_provider.get_historical_bars(
                    symbol=[config.benchmark_symbol],
                    asset_class=bench_asset_class,
                    timeframe_str=timeframe,
                    start_dt=start_dt,
                    end_dt=end_dt,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to fetch benchmark data for {config.benchmark_symbol}: {e}"
                )

        # 1. Standardize Data format for multi-asset broadcasting
        # We need data to be aligned columns per symbol for vectorbt if it's not already
        is_multi_index = isinstance(data.index, pd.MultiIndex)

        # Unstack if multi-index to get flat time index with symbol columns
        if is_multi_index:
            unstacked_close = data["close"].unstack(level=0)
            unstacked_open = data["open"].unstack(level=0)
            unstacked_high = data["high"].unstack(level=0)
            unstacked_low = data["low"].unstack(level=0)
            unstacked_volume = data["volume"].unstack(level=0)
        else:
            # Fake a symbol 'ASSET' if no symbol present
            symbol = data.columns.name if data.columns.name else "ASSET"
            unstacked_close = data[["close"]]
            unstacked_open = data[["open"]]
            unstacked_high = data[["high"]]
            unstacked_low = data[["low"]]
            unstacked_volume = data[["volume"]]
            unstacked_close.columns = [symbol]
            unstacked_open.columns = [symbol]
            unstacked_high.columns = [symbol]
            unstacked_low.columns = [symbol]
            unstacked_volume.columns = [symbol]

        # Extract Symbols
        symbols = list(unstacked_close.columns)

        # 2. Signal Generation per symbol
        # Initialize signal dataframes with False
        entries_df = pd.DataFrame(False, index=unstacked_close.index, columns=symbols)
        exits_df = pd.DataFrame(False, index=unstacked_close.index, columns=symbols)

        for symbol in symbols:
            # Reconstruct per-symbol OHLCV
            if is_multi_index:
                symbol_data = data.xs(symbol, level=0).copy()
            else:
                symbol_data = data.copy()

            # Run Analyzers
            pattern_analyzer = PatternAnalyzer(symbol_data)
            pattern_results = pattern_analyzer.check_patterns()

            harmonic_analyzer = HarmonicAnalyzer(pattern_analyzer.pivots)
            harmonic_patterns = harmonic_analyzer.scan_all_patterns()

            # Map harmonic patterns to a dataframe for boolean indexing aligned with time
            harmonic_df = pd.DataFrame(
                False,
                index=symbol_data.index,
                columns=[p.pattern_type for p in harmonic_patterns],
            )
            for h_pattern in harmonic_patterns:
                # Signal triggered at the last pivot (D point)
                h_pattern_time = h_pattern.pivots[-1].index
                harmonic_df.loc[h_pattern_time, h_pattern.pattern_type] = True

            # Combine into a single symbol signal space
            # Exclude Int64/float columns from fillna(False) to avoid pandas TypeErrors with nullable types
            symbol_signals = pd.concat([pattern_results, harmonic_df], axis=1)
            for col in symbol_signals.columns:
                if pd.api.types.is_bool_dtype(
                    symbol_signals[col]
                ) or pd.api.types.is_object_dtype(symbol_signals[col]):
                    # Silence Pandas 3.0 downcasting FutureWarnings during fillna
                    with pd.option_context("future.no_silent_downcasting", True):
                        symbol_signals[col] = (
                            symbol_signals[col].fillna(False).infer_objects(copy=False)
                        )

            # Extract configured entries and exits
            entry_sigs = pd.Series(False, index=symbol_data.index)
            exit_sigs = pd.Series(False, index=symbol_data.index)

            # Base boolean mapping
            if config.confluence_mode == "OR":
                for p_name in config.entry_patterns:
                    if p_name in symbol_signals.columns:
                        entry_sigs = entry_sigs | symbol_signals[p_name]
                for p_name in config.exit_patterns:
                    if p_name in symbol_signals.columns:
                        exit_sigs = exit_sigs | symbol_signals[p_name]
            elif config.confluence_mode == "AND":
                # Only use AND if there are patterns configured
                if config.entry_patterns:
                    entry_sigs = pd.Series(True, index=symbol_data.index)
                    for p_name in config.entry_patterns:
                        if p_name in symbol_signals.columns:
                            entry_sigs = entry_sigs & symbol_signals[p_name]
                        else:
                            entry_sigs = pd.Series(False, index=symbol_data.index)
                            break
                if config.exit_patterns:
                    exit_sigs = pd.Series(True, index=symbol_data.index)
                    for p_name in config.exit_patterns:
                        if p_name in symbol_signals.columns:
                            exit_sigs = exit_sigs & symbol_signals[p_name]
                        else:
                            exit_sigs = pd.Series(False, index=symbol_data.index)
                            break

            entries_df[symbol] = entry_sigs
            exits_df[symbol] = exit_sigs

            # --- Indicator Confluence Filters ---
            # Applied AFTER pattern signals, always AND-gate indicators
            # regardless of confluence_mode (indicators are always additive gates)
            try:
                indicator_analyzer = IndicatorAnalyzer(symbol_data)
                indicator_entry_mask = pd.Series(True, index=symbol_data.index)
                indicator_exit_mask = pd.Series(True, index=symbol_data.index)

                if config.rsi_period is not None:
                    rsi = indicator_analyzer.get_rsi(config.rsi_period)
                    if rsi is not None and not rsi.empty:
                        # Entry: price is oversold (RSI below threshold)
                        indicator_entry_mask = indicator_entry_mask & (
                            rsi <= config.rsi_oversold
                        )
                        # Exit: price is overbought (RSI above threshold)
                        indicator_exit_mask = indicator_exit_mask & (
                            rsi >= config.rsi_overbought
                        )

                if config.ema_period is not None:
                    ema = indicator_analyzer.get_ema(config.ema_period)
                    if ema is not None and not ema.empty:
                        # Entry: price is above EMA (bullish context)
                        indicator_entry_mask = indicator_entry_mask & (
                            symbol_data["close"] > ema
                        )
                        # Exit: price is below EMA (bearish context)
                        indicator_exit_mask = indicator_exit_mask & (
                            symbol_data["close"] < ema
                        )

                # Apply indicator masks
                if config.rsi_period is not None or config.ema_period is not None:
                    entries_df[symbol] = entries_df[symbol] & indicator_entry_mask.fillna(
                        False
                    )
                    exits_df[symbol] = exits_df[symbol] & indicator_exit_mask.fillna(
                        False
                    )

            except Exception as e:  # noqa: BLE001
                # If indicator computation fails, log the error rather than skipping silently
                logger.error(f"Indicator computation failed for {symbol}: {e}")

        # 3. VectorBT Simulation
        portfolio = vbt.Portfolio.from_signals(
            close=unstacked_close,
            entries=entries_df,
            exits=exits_df,
            fees=config.fees,
            slippage=config.slippage,
            freq=freq,
        )

        # 4. Result Formatting
        # We pass silence_warnings=True to explicitly acknowledge the multiple columns aggregation and suppress the vectorbt UserWarning
        metrics = portfolio.stats(silence_warnings=True)

        # Extract individual metrics safely
        def safe_metric(key: str, default: float = 0.0) -> float:
            try:
                val = metrics.get(key, default)
                return float(val) if not pd.isna(val) else default
            except (ValueError, TypeError):
                return default

        # --- Relative Metrics (Alpha & Beta) ---
        alpha = 0.0
        beta = 0.0
        calmar_ratio = 0.0
        avg_trade_duration_str = "0s"
        avg_trade_duration_bars = 0

        # Safe Calmar Ratio
        calmar_ratio = safe_metric("Calmar Ratio")
        if calmar_ratio == 0.0:
            # Fallback if Calmar is not calculated
            ann_ret = safe_metric("Ann. Return [%]")
            max_dd = safe_metric("Max Drawdown [%]")
            if max_dd != 0:
                calmar_ratio = ann_ret / abs(max_dd)

        # Average Trade Duration
        trade_records = portfolio.trades.records_readable
        if (
            not trade_records.empty
            and "Entry Timestamp" in trade_records.columns
            and "Exit Timestamp" in trade_records.columns
        ):
            durations = pd.to_datetime(trade_records["Exit Timestamp"]) - pd.to_datetime(
                trade_records["Entry Timestamp"]
            )
            avg_duration = durations.mean()

            # Format string e.g., "2d 4h 15m"
            if not pd.isna(avg_duration):
                days = avg_duration.components.days
                hours = avg_duration.components.hours
                minutes = avg_duration.components.minutes

                parts = []
                if days > 0:
                    parts.append(f"{days}d")
                if hours > 0:
                    parts.append(f"{hours}h")
                if minutes > 0:
                    parts.append(f"{minutes}m")

                # If everything is 0, show "0m"
                if not parts:
                    parts.append("0m")

                avg_trade_duration_str = " ".join(parts)

            # Avg duration bars
            if "Duration" in trade_records.columns:
                avg_trade_duration_bars = int(trade_records["Duration"].mean())
            else:
                raw_records = portfolio.trades.records
                if (
                    not raw_records.empty
                    and "entry_idx" in raw_records.columns
                    and "exit_idx" in raw_records.columns
                ):
                    avg_trade_duration_bars = int(
                        (raw_records["exit_idx"] - raw_records["entry_idx"]).mean()
                    )

        # Alpha and Beta calculation
        if benchmark_data is not None and not benchmark_data.empty:
            # Use total portfolio value pct change (Equity)
            portfolio_value = portfolio.value()
            if isinstance(portfolio_value, pd.DataFrame):
                portfolio_value = portfolio_value.sum(axis=1)

            strat_equity = portfolio_value.rename("strat")

            # Prepare benchmark price series
            if isinstance(benchmark_data.index, pd.MultiIndex):
                bench_price = benchmark_data["close"].unstack(level=0).iloc[:, 0]
            else:
                bench_price = benchmark_data["close"]
            bench_price = bench_price.rename("bench")

            # Institutional Beta alignment: Resample both to Daily ('D')
            # Use forward fill for prices to handle weekend/holiday gaps
            strat_daily = strat_equity.resample("D").last().ffill()
            bench_daily = bench_price.resample("D").last().ffill()

            # Calculate daily returns
            strat_returns = strat_daily.pct_change()
            bench_returns = bench_daily.pct_change()

            # Final alignment: merge daily returns and drop NaNs
            aligned_returns = pd.concat([strat_returns, bench_returns], axis=1).dropna()

            if not aligned_returns.empty and len(aligned_returns) > 1:
                cov_matrix = aligned_returns.cov()
                var_bench = cov_matrix.loc["bench", "bench"]
                cov_strat_bench = cov_matrix.loc["strat", "bench"]

                if var_bench != 0:
                    beta = cov_strat_bench / var_bench

                    # Annualize returns for Alpha calculation
                    # Strategy annualized return from vectorbt
                    ann_ret_strat = safe_metric("Ann. Return [%]") / 100.0

                    # Calculate benchmark annualized return dynamically
                    days_diff = (
                        aligned_returns.index.max() - aligned_returns.index.min()
                    ).days
                    if days_diff > 0:
                        bench_total_ret = (bench_daily.iloc[-1] / bench_daily.iloc[0]) - 1
                        ann_ret_bench = (1 + bench_total_ret) ** (365.25 / days_diff) - 1
                    else:
                        ann_ret_bench = 0.0

                    # Formula: alpha = R_strat - (beta * R_bench)
                    alpha = ann_ret_strat - (beta * ann_ret_bench)

        metrics_result = MetricsResult(
            total_return_pct=safe_metric("Total Return [%]"),
            sharpe_ratio=safe_metric("Sharpe Ratio"),
            sortino_ratio=safe_metric("Sortino Ratio"),
            max_drawdown_pct=safe_metric("Max Drawdown [%]"),
            win_rate_pct=safe_metric("Win Rate [%]"),
            total_trades=int(safe_metric("Total Trades", 0)),
            alpha=alpha,
            beta=beta,
            calmar_ratio=calmar_ratio,
            avg_trade_duration=avg_trade_duration_str,
            avg_trade_duration_bars=avg_trade_duration_bars,
        )

        # Equity Curve
        equity_series = portfolio.value()
        # If multi-asset, value() returns total portfolio value
        if isinstance(equity_series, pd.DataFrame):
            equity_series = equity_series.sum(
                axis=1
            )  # Or keep individual, depending on needs. Let's do total.

        equity_curve = [
            EquityCurvePoint(
                timestamp=idx.isoformat() if hasattr(idx, "isoformat") else str(idx),
                value=float(val),
            )
            for idx, val in equity_series.items()
        ]

        # Trades
        trades = []
        # In multi-asset, count() might return a Series. sum() works robustly
        trade_count = portfolio.trades.count()
        total_trades = (
            trade_count.sum() if isinstance(trade_count, pd.Series) else trade_count
        )
        if total_trades > 0:
            trade_records = portfolio.trades.records_readable
            for trade in trade_records.to_dict("records"):
                # Handling vectorbt trade records
                col_name = trade.get("Column", "ASSET")
                symbol_name = str(col_name) if pd.notna(col_name) else symbols[0]

                entry_ts = trade["Entry Timestamp"]
                exit_ts = trade["Exit Timestamp"]
                entry_time_str = (
                    entry_ts.isoformat()
                    if hasattr(entry_ts, "isoformat")
                    else str(entry_ts)
                )
                exit_time_str = (
                    exit_ts.isoformat() if hasattr(exit_ts, "isoformat") else str(exit_ts)
                )

                trades.append(
                    TradeResult(
                        symbol=symbol_name,
                        entry_time=entry_time_str,
                        exit_time=exit_time_str,
                        entry_price=float(
                            trade.get("Entry Price", trade.get("Avg Entry Price", 0.0))
                        ),
                        exit_price=float(
                            trade.get("Exit Price", trade.get("Avg Exit Price", 0.0))
                        ),
                        pnl=float(trade.get("PnL", 0.0)),
                        pnl_pct=float(trade.get("Return", 0.0)),
                        duration_bars=int(
                            trade.get("Duration", 0)
                            if not pd.isna(trade.get("Duration"))
                            else 0
                        ),
                        direction="Long"
                        if trade.get("Direction", "Long") == "Long"
                        else "Short",
                    )
                )

        # Benchmark Equity Curve
        benchmark_equity_curve = None
        if benchmark_data is not None and not benchmark_data.empty:
            # We already have bench_daily from Alpha/Beta block if it reached there.
            # But let's be safe and re-extract or use the prices.
            # To match the strategy curve's timestamps/values:
            bench_series = bench_daily if "bench_daily" in locals() else bench_price
            benchmark_equity_curve = [
                EquityCurvePoint(
                    timestamp=idx.isoformat() if hasattr(idx, "isoformat") else str(idx),
                    value=float(val),
                )
                for idx, val in bench_series.items()
            ]

        return BacktestResult(
            metrics=metrics_result,
            equity_curve=equity_curve,
            benchmark_equity_curve=benchmark_equity_curve,
            trades=trades,
        )
