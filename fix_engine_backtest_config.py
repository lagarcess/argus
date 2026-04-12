import re

with open("src/argus/engine.py", "r") as f:
    content = f.read()

# Someone reverted BacktestConfig to StrategyInput. We need to restore the full BacktestConfig implementation
new_backtest_config = """
# BacktestConfig is a semantic alias used at the API boundary.
class BacktestConfig:
    \"\"\"
    Modular Interceptor wrapper around StrategyInput.
    Responsible for fetching data and producing Aligned N-Dimensional Arrays
    for multi-asset vectorization.
    \"\"\"
    def __init__(self, config: StrategyInput):
        self.config = config

    def prepare_vectors(
        self,
        data_provider: MarketDataProvider,
        asset_class: AssetClass,
        start_dt: datetime,
        end_dt: datetime,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        \"\"\"
        Fetch data for all symbols and align them into orthagonal matrices (Time x Assets).
        Handles UTC normalization and ffill/bfill for missing bars.
        \"\"\"
        close_dict = {}
        open_dict = {}
        high_dict = {}
        low_dict = {}
        volume_dict = {}

        for sym in self.config.symbols:
            try:
                data = data_provider.get_historical_bars(
                    symbol=sym,
                    asset_class=asset_class,
                    timeframe_str=self.config.timeframe,
                    start_dt=start_dt,
                    end_dt=end_dt,
                )
                if data.empty:
                    logger.warning(f"No data found for {sym} on {self.config.timeframe}")
                    continue

                # Ensure UTC normalization
                if data.index.tz is None:
                    data.index = data.index.tz_localize('UTC')
                else:
                    data.index = data.index.tz_convert('UTC')

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
        try:
            import psutil
            est_rows = max(len(s) for s in close_dict.values())
            est_bytes = 5 * 8 * est_rows * len(close_dict)

            if est_bytes > 1_073_741_824:
                logger.warning(f"Memory Sanity Gate Warning: Aligned matrix footprint estimated at {est_bytes / (1024*1024):.2f} MB! Potential OOM risk.")
        except Exception as e:
            logger.debug(f"Failed to estimate memory footprint: {e}")

        close_df = pd.DataFrame(close_dict).ffill().bfill()
        open_df = pd.DataFrame(open_dict).reindex(close_df.index).ffill().bfill()
        high_df = pd.DataFrame(high_dict).reindex(close_df.index).ffill().bfill()
        low_df = pd.DataFrame(low_dict).reindex(close_df.index).ffill().bfill()
        volume_df = pd.DataFrame(volume_dict).reindex(close_df.index).fillna(0)

        return open_df, high_df, low_df, close_df, volume_df
"""

# Find StrategyInput and insert BacktestConfig
content = re.sub(
    r"# BacktestConfig is a semantic alias used at the API boundary.\nBacktestConfig = StrategyInput",
    new_backtest_config,
    content,
)

with open("src/argus/engine.py", "w") as f:
    f.write(content)
