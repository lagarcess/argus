"""Symbol normalization utilities."""


def normalize_alpaca_symbol(symbol: str) -> str:
    """Normalize a trading symbol for Alpaca API compatibility.

    Alpaca's crypto API expects symbols without slashes (e.g., 'BTCUSD' instead of 'BTC/USD').
    Equities are already in the correct format.

    Args:
        symbol: The trading symbol (e.g., 'BTC/USD', 'AAPL').

    Returns:
        The normalized symbol for Alpaca.
    """
    return symbol.replace("/", "")
