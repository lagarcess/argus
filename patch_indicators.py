with open("src/argus/analysis/indicators.py", "r") as f:
    content = f.read()

new_class = """
class IndicatorAnalyzer:
    \"\"\"
    Analyzes specific indicators for a given symbol dataframe.
    Centralizes technical analysis logic outside the core engine.
    \"\"\"

    def __init__(self, df: pd.DataFrame):
        self.df = df

    def get_rsi(self, period: int) -> pd.Series:
        \"\"\"Calculate Relative Strength Index.\"\"\"
        try:
            import pandas_ta_classic as ta
        except ImportError:
            import pandas_ta as ta
        return ta.rsi(self.df["close"], length=period)

    def get_ema(self, period: int) -> pd.Series:
        \"\"\"Calculate Exponential Moving Average.\"\"\"
        try:
            import pandas_ta_classic as ta
        except ImportError:
            import pandas_ta as ta
        return ta.ema(self.df["close"], length=period)
"""

if "class IndicatorAnalyzer:" not in content:
    content += "\n" + new_class

with open("src/argus/analysis/indicators.py", "w") as f:
    f.write(content)
