with open("src/argus/config.py", "r") as f:
    content = f.read()

replacement = """    ENABLE_MARKET_DATA_CACHE: bool = Field(
        default=False,
        description="Enable disk caching for market data. Useful for backtesting/dev.",
    )

    MARKET_DATA_CACHE_TTL: int = Field(
        default=900,
        description="Time-to-live for market data cache in seconds (15 minutes).",
    )"""

content = content.replace(
    '    ENABLE_MARKET_DATA_CACHE: bool = Field(\n        default=False,\n        description="Enable disk caching for market data. Useful for backtesting/dev.",\n    )',
    replacement,
)

with open("src/argus/config.py", "w") as f:
    f.write(content)
