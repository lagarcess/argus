with open("src/argus/engine.py", "r") as f:
    content = f.read()

# Replace the inner try block in the indicator confluence logic
search_block = """
            try:
                indicator_entry_mask = pd.Series(True, index=symbol_data.index)
                indicator_exit_mask = pd.Series(True, index=symbol_data.index)

                if has_ta and config.rsi_period is not None:
                    rsi = ta.rsi(symbol_data["close"], length=config.rsi_period)
                    if rsi is not None and not rsi.empty:
                        # Entry: price is oversold (RSI below threshold)
                        indicator_entry_mask = indicator_entry_mask & (
                            rsi <= config.rsi_oversold
                        )
                        # Exit: price is overbought (RSI above threshold)
                        indicator_exit_mask = indicator_exit_mask & (
                            rsi >= config.rsi_overbought
                        )

                if has_ta and config.ema_period is not None:
                    ema = ta.ema(symbol_data["close"], length=config.ema_period)
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
                    entries_df[symbol] = entries_df[symbol] & indicator_entry_mask.fillna(False)
                    exits_df[symbol] = exits_df[symbol] & indicator_exit_mask.fillna(False)

            except Exception as e:  # noqa: BLE001
                # If indicator computation fails, log the error rather than skipping silently
                logger.error(f"Indicator computation failed for {symbol}: {e}")
"""

replace_block = """
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
                    entries_df[symbol] = entries_df[symbol] & indicator_entry_mask.fillna(False)
                    exits_df[symbol] = exits_df[symbol] & indicator_exit_mask.fillna(False)

            except Exception as e:  # noqa: BLE001
                # If indicator computation fails, log the error rather than skipping silently
                logger.error(f"Indicator computation failed for {symbol}: {e}")
"""

# Also need to add import for IndicatorAnalyzer
if "from argus.analysis.indicators import IndicatorAnalyzer" not in content:
    content = content.replace(
        "from argus.analysis.patterns import PatternAnalyzer",
        "from argus.analysis.indicators import IndicatorAnalyzer\nfrom argus.analysis.patterns import PatternAnalyzer",
    )

if search_block.strip() in content:
    content = content.replace(search_block.strip(), replace_block.strip())
else:
    print(
        "Could not find the exact block to replace. Attempting to use regex or fallback."
    )

with open("src/argus/engine.py", "w") as f:
    f.write(content)
