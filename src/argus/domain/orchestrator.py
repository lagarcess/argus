from __future__ import annotations

import re
from typing import Any

TEMPLATE_ALIASES: list[tuple[str, str]] = [
    ("rsi_mean_reversion", "rsi"),
    ("rsi_mean_reversion", "dip"),
    ("moving_average_crossover", "moving average"),
    ("dca_accumulation", "dca"),
    ("momentum_breakout", "momentum"),
    ("momentum_breakout", "breakout"),
    ("trend_follow", "trend"),
]

NON_SYMBOLS = {
    "WHAT",
    "IF",
    "WHENEVER",
    "WHEN",
    "BOUGHT",
    "BUY",
    "DIPPED",
    "HARD",
    "THE",
    "AND",
    "FOR",
    "WITH",
    "STOCK",
    "CRYPTO",
}
COMMON_NAMES = {
    "TESLA": "TSLA",
    "APPLE": "AAPL",
    "MICROSOFT": "MSFT",
    "NVIDIA": "NVDA",
    "BITCOIN": "BTC",
    "ETHEREUM": "ETH",
    "SOLANA": "SOL",
}


def extract_strategy_request(message: str) -> dict[str, Any]:
    upper = message.upper()
    symbols = [symbol for name, symbol in COMMON_NAMES.items() if name in upper]
    symbols.extend(
        token
        for token in re.findall(r"\b[A-Z]{2,5}\b", upper)
        if token not in NON_SYMBOLS and token not in symbols
    )
    template = "rsi_mean_reversion"
    lower = message.lower()
    for candidate, alias in TEMPLATE_ALIASES:
        if alias in lower:
            template = candidate
            break
    asset_class = "crypto" if any(symbol in {"BTC", "ETH", "SOL"} for symbol in symbols) else "equity"
    return {
        "template": template,
        "asset_class": asset_class,
        "symbols": symbols[:5] or ["TSLA"],
    }


def assistant_copy_for_result(symbols: list[str], language: str) -> str:
    joined = ", ".join(symbols)
    if language == "es":
        return (
            f"Probé la idea con {joined}. Usé una simulación larga, ponderada por igual "
            "y sin comisiones ni deslizamiento para mantener clara la comparación."
        )
    return (
        f"I tested that idea with {joined}. I used a long-only, equal-weight simulation "
        "with no fees or slippage so the comparison stays easy to understand."
    )
