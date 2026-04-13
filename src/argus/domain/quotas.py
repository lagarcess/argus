from typing import Any, Dict

# Multi-Dimensional Tier Gating Configuration
TIER_CONFIG: Dict[str, Dict[str, Any]] = {
    "free": {
        "max_symbols": 1,
        "daily_lookback_days": 365,
        "intraday_lookback_days": 3,
    },
    "plus": {
        "max_symbols": 5,
        "daily_lookback_days": 1095,
        "intraday_lookback_days": 7,
    },
    "pro": {
        "max_symbols": 15,
        "daily_lookback_days": 1825,
        "intraday_lookback_days": 14,
    },
    "max": {
        "max_symbols": 100,
        "daily_lookback_days": 2555,
        "intraday_lookback_days": 30,
    },
}
