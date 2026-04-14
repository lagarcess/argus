from typing import Any, Dict

# Multi-Dimensional Tier Gating Configuration
TIER_CONFIG: Dict[str, Dict[str, Any]] = {
    "free": {
        "max_symbols": 1,
        "daily_lookback_days": 365,
        "intraday_lookback_days": 3,
        "max_participation_rate": 0.01,  # 1% cap for Free users
        "allow_va_slippage": False,
        "allow_strategy_duel": False,
    },
    "plus": {
        "max_symbols": 5,
        "daily_lookback_days": 1095,
        "intraday_lookback_days": 7,
        "max_participation_rate": 0.05,  # 5% cap for Plus users
        "allow_va_slippage": False,
        "allow_strategy_duel": False,
    },
    "pro": {
        "max_symbols": 15,
        "daily_lookback_days": 1825,
        "intraday_lookback_days": 14,
        "max_participation_rate": 0.1,   # 10% standard cap
        "allow_va_slippage": True,
        "allow_strategy_duel": True,
    },
    "max": {
        "max_symbols": 100,
        "daily_lookback_days": 2555,
        "intraday_lookback_days": 30,
        "max_participation_rate": 1.0,   # Full unrestricted depth
        "allow_va_slippage": True,
        "allow_strategy_duel": True,
    },
}
