import re

with open("src/argus/engine.py", "r") as f:
    content = f.read()

# Replace the run method with the one that contains dual sim orchestration and metrics
new_run_method = """    def run(
        self,
        config: StrategyInput,
        asset_class: AssetClass = AssetClass.CRYPTO,
    ) -> EngineBacktestResults:
        \"\"\"
        Run a single or multi-symbol backtest using VectorBT's native Portfolio.
        Implements Dual-Sim architecture to calculate Reality Gap metrics.
        \"\"\"
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
            self.data_provider, asset_class, start_dt, end_dt
        )

        # Determine signals
        entries_dict: Dict[str, pd.Series] = {}
        pattern_counts: Dict[str, int] = {}

        for sym in config.symbols:
            try:
                if sym not in close_df.columns:
                    continue
                sym_data = pd.DataFrame({
                    "open": open_df[sym],
                    "high": high_df[sym],
                    "low": low_df[sym],
                    "close": close_df[sym],
                    "volume": volume_df[sym],
                })

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
                                h for h in harmonic_patterns
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
            raise ValueError(f"No valid signals could be generated for any of {config.symbols}")

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
                fidelity_score = float(np.corrcoef(ideal_returns_series.values, real_returns_series.values)[0, 1])
            else:
                fidelity_score = 1.0

        if pd.isna(fidelity_score):
            fidelity_score = 1.0

        portfolio_slip_only = vbt.Portfolio.from_signals(
            close=close_df, entries=entries_df, exits=exits_df,
            sl_stop=sl_stop, tp_stop=tp_stop, fees=0.0, slippage=config.slippage, freq=freq,
        )
        portfolio_fee_only = vbt.Portfolio.from_signals(
            close=close_df, entries=entries_df, exits=exits_df,
            sl_stop=sl_stop, tp_stop=tp_stop, fees=config.fees, slippage=0.0, freq=freq,
        )

        slip_return = float(portfolio_slip_only.total_return().mean()) if isinstance(portfolio_slip_only.total_return(), pd.Series) else float(portfolio_slip_only.total_return())
        fee_return = float(portfolio_fee_only.total_return().mean()) if isinstance(portfolio_fee_only.total_return(), pd.Series) else float(portfolio_fee_only.total_return())
        ideal_return_scalar = float(ideal_return.mean()) if isinstance(ideal_return, pd.Series) else float(ideal_return)

        slippage_impact_pct = float(ideal_return_scalar - slip_return) if ideal_return_scalar != 0 else 0.0
        fee_impact_pct = float(ideal_return_scalar - fee_return) if ideal_return_scalar != 0 else 0.0

        if ideal_return_scalar != 0:
            slippage_impact_pct = (slippage_impact_pct / ideal_return_scalar) * 100
            fee_impact_pct = (fee_impact_pct / ideal_return_scalar) * 100

        if fidelity_score < 0.9:
            logger.warning(f"REALITY GAP ALERT: Fidelity Score is unusually low ({fidelity_score:.3f}). High variance detected between ideal and real execution.")

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
                "fidelity_score": float(fidelity_score)
            },
            pattern_breakdown=pattern_counts,
        )"""

# Substitute the run function
content = re.sub(
    r"    def run\([\s\S]*?pattern_breakdown=pattern_counts,\n        \)",
    new_run_method,
    content,
)
content = re.sub(
    r'    def _run_single_symbol\([\s\S]*?return data\["close"\], entries, data, pattern_counts\n\n',
    "",
    content,
)

with open("src/argus/engine.py", "w") as f:
    f.write(content)
