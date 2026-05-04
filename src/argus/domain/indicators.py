from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class IndicatorInfo:
    key: str
    label: str
    description: str
    support_status: str = "draft_only"
    aliases: tuple[str, ...] = ()


_KNOWN_INDICATORS = {
    "rsi": IndicatorInfo(
        "rsi",
        "RSI",
        "Relative Strength Index; a momentum gauge from 0 to 100.",
        "supported",
        ("relative strength index", "oversold", "overbought", "momentum gauge"),
    ),
    "sma": IndicatorInfo(
        "sma",
        "Simple moving average",
        "Average price over a set number of bars.",
        aliases=("simple moving average", "moving average", "average price"),
    ),
    "ema": IndicatorInfo(
        "ema",
        "Exponential moving average",
        "Moving average that reacts faster to recent prices.",
        aliases=("exponential moving average", "moving average"),
    ),
    "macd": IndicatorInfo(
        "macd",
        "MACD",
        "Momentum indicator based on two moving averages.",
        aliases=("moving average convergence divergence", "momentum"),
    ),
    "bbands": IndicatorInfo(
        "bbands",
        "Bollinger Bands",
        "Volatility bands around a moving average.",
        aliases=("bollinger", "volatility bands"),
    ),
    "atr": IndicatorInfo(
        "atr",
        "ATR",
        "Average true range, commonly used to estimate volatility.",
        aliases=("average true range", "volatility"),
    ),
    "vwap": IndicatorInfo(
        "vwap",
        "VWAP",
        "Volume-weighted average price.",
        aliases=("volume weighted average price",),
    ),
    "obv": IndicatorInfo(
        "obv",
        "OBV",
        "On-balance volume, a volume momentum indicator.",
        aliases=("on balance volume", "volume momentum"),
    ),
    "stoch": IndicatorInfo(
        "stoch",
        "Stochastic oscillator",
        "Momentum indicator comparing close to recent range.",
        aliases=("stochastic", "stochastic oscillator"),
    ),
}


@lru_cache(maxsize=1)
def indicator_catalog() -> tuple[IndicatorInfo, ...]:
    discovered = {item.key: item for item in _discover_pandas_ta_indicators()}
    discovered.update(_KNOWN_INDICATORS)
    return tuple(sorted(discovered.values(), key=lambda item: item.label))


def search_indicators(query: str, *, limit: int = 12) -> list[IndicatorInfo]:
    normalized = " ".join(query.lower().strip().split())
    if not normalized:
        return []
    scored: list[tuple[int, IndicatorInfo]] = []
    for item in indicator_catalog():
        key = item.key.lower()
        label = item.label.lower()
        description = item.description.lower()
        aliases = tuple(alias.lower() for alias in item.aliases)
        score: int | None = None
        if normalized == key or normalized == label or normalized in aliases:
            score = 0
        elif key.startswith(normalized) or label.startswith(normalized):
            score = 1
        elif any(alias.startswith(normalized) for alias in aliases):
            score = 2
        elif normalized in key or normalized in label:
            score = 3
        elif any(normalized in alias for alias in aliases):
            score = 4
        elif normalized in description:
            score = 5
        if score is not None:
            scored.append((score, item))
    scored.sort(key=lambda pair: (pair[0], pair[1].label))
    return [item for _, item in scored[: max(1, min(limit, 25))]]


def _discover_pandas_ta_indicators() -> tuple[IndicatorInfo, ...]:
    try:
        import pandas_ta_classic as ta  # type: ignore[import-untyped]
    except Exception:
        return ()

    names: set[str] = set()
    categories = getattr(ta, "Category", None)
    if isinstance(categories, dict):
        for values in categories.values():
            if isinstance(values, (list, tuple, set)):
                names.update(str(value) for value in values if str(value).strip())

    if not names:
        names.update(
            name
            for name in dir(ta)
            if not name.startswith("_")
            and name.islower()
            and callable(getattr(ta, name, None))
        )

    return tuple(
        IndicatorInfo(
            key=name.lower(),
            label=name.upper() if len(name) <= 5 else name.replace("_", " ").title(),
            description="Indicator available for strategy drafting.",
        )
        for name in sorted(names)
    )
