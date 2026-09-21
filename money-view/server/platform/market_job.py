"""Manual read-only market price loader for Clara's local SQLite database."""

from __future__ import annotations

import argparse
import json
import os
import sys

from ..store import Store
from .market_data import (
    AlpacaMarketDataAdapter,
    FixtureMarketDataAdapter,
    MarketDataAdapter,
    MarketDataLoadError,
    _stock_symbol,
    initialize,
    load_market_prices,
)


def _symbols(value: str) -> list[str]:
    try:
        result = list(dict.fromkeys(_stock_symbol(item) for item in value.split(",")))
    except MarketDataLoadError as exc:
        raise argparse.ArgumentTypeError(exc.code) from exc
    if not result:
        raise argparse.ArgumentTypeError("invalid_market_symbols")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    load = commands.add_parser("load")
    load.add_argument("--database", required=True)
    load.add_argument("--provider", choices=("fixture", "alpaca"), default="fixture")
    load.add_argument("--symbols", required=True, type=_symbols)
    load.add_argument(
        "--feed",
        choices=("iex", "sip", "delayed_sip", "boats", "overnight", "otc"),
        default="iex",
    )
    return parser


def _adapter(args: argparse.Namespace) -> MarketDataAdapter:
    if args.provider == "fixture":
        return FixtureMarketDataAdapter(symbols=args.symbols)
    return AlpacaMarketDataAdapter(
        api_key=os.environ.get("CLARA_ALPACA_API_KEY", ""),
        api_secret=os.environ.get("CLARA_ALPACA_API_SECRET", ""),
        symbols=args.symbols,
        feed=args.feed,
    )


def _write(document: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(document, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        adapter = _adapter(args)
    except MarketDataLoadError as exc:
        _write(
            {
                "provider": args.provider,
                "status": "failed",
                "error_code": exc.code,
            }
        )
        return 2
    store = Store(args.database)
    initialize(store)
    result = load_market_prices(store, adapter)
    _write(
        {
            "provider": args.provider,
            "symbols": args.symbols,
            "load": result,
        }
    )
    return 0 if result["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
