from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal

from argus.domain.backtesting.date_window import validate_backtest_date_window
from argus.domain.backtesting.rules import validate_rule_spec
from argus.domain.indicators import normalize_indicator_parameters
from argus.domain.market_data import resolve_asset
from argus.domain.market_data.capabilities import validate_market_data_window
from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES

AssetClass = Literal["equity", "crypto", "currency_pair"]

ALLOWED_TEMPLATES = set(STRATEGY_CAPABILITIES.keys()) | {"signal_strategy"}

ALLOWED_TIMEFRAMES = {"1h", "2h", "4h", "6h", "12h", "1D"}

STABLECOINS = {"USDC", "USDT", "DAI", "BUSD", "TUSD"}


@dataclass(frozen=True)
class SymbolAsset:
    symbol: str
    asset_class: AssetClass


def classify_symbol(symbol: str, *, resolve_asset_func=resolve_asset) -> SymbolAsset:
    resolved = resolve_asset_func(symbol)
    return SymbolAsset(symbol=resolved.canonical_symbol, asset_class=resolved.asset_class)


def default_benchmark(asset_class: AssetClass, symbols: list[str] | None = None) -> str:
    if asset_class == "equity":
        return "SPY"
    if asset_class == "currency_pair":
        return symbols[0] if symbols else "EURUSD"
    return "BTC"


def _normalize_timeframe(timeframe: str | None) -> str:
    if timeframe is None:
        return "1D"
    normalized = timeframe.strip().lower()
    mapping = {
        "1d": "1D",
        "1day": "1D",
        "1h": "1h",
        "1hour": "1h",
        "2h": "2h",
        "2hour": "2h",
        "4h": "4h",
        "4hour": "4h",
        "6h": "6h",
        "6hour": "6h",
        "12h": "12h",
        "12hour": "12h",
    }
    if normalized not in mapping:
        raise ValueError("unsupported_timeframe")
    return mapping[normalized]


def _to_date(value: str | date | datetime) -> date:
    if isinstance(value, str):
        return date.fromisoformat(value)
    if isinstance(value, datetime):
        return value.date()
    return value


def _periods_per_year(timeframe: str) -> float:
    mapping = {
        "1D": 252.0,
        "1h": 24.0 * 365.0,
        "2h": 12.0 * 365.0,
        "4h": 6.0 * 365.0,
        "6h": 4.0 * 365.0,
        "12h": 2.0 * 365.0,
    }
    return mapping[timeframe]


def _vbt_freq(timeframe: str) -> str:
    mapping = {
        "1D": "1D",
        "1h": "1h",
        "2h": "2h",
        "4h": "4h",
        "6h": "6h",
        "12h": "12h",
    }
    return mapping[timeframe]


def _execution_realism_feature_enabled() -> bool:
    return os.getenv("ARGUS_ENABLE_EXECUTION_REALISM", "").strip().lower() == "true"


def _normalize_execution_realism(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    return {
        "enabled": bool(source.get("enabled", False)),
        "fee_bps": float(source.get("fee_bps", 0.0)),
        "slippage_bps": float(source.get("slippage_bps", 0.0)),
    }


def normalize_backtest_config(
    payload: dict[str, Any],
    *,
    classify_symbol_func=classify_symbol,
    default_benchmark_func=default_benchmark,
) -> dict[str, Any]:
    today = date.today()
    end_default = today - timedelta(days=1)
    end = _to_date(payload.get("end_date") or end_default)
    start = _to_date(payload.get("start_date") or (end - timedelta(days=365)))
    requested_asset_class = payload.get("asset_class")
    classified = [classify_symbol_func(s) for s in payload["symbols"]]

    actual_classes = {c.asset_class for c in classified}
    if len(actual_classes) > 1:
        raise ValueError("mixed_asset_not_supported")

    inferred_class = next(iter(actual_classes)) if actual_classes else "equity"
    asset_class = requested_asset_class or inferred_class

    if asset_class != inferred_class:
        raise ValueError("asset_class_conflict")

    symbols = [c.symbol for c in classified]
    timeframe = _normalize_timeframe(payload.get("timeframe"))

    benchmark_input = payload.get("benchmark_symbol")
    if benchmark_input:
        benchmark_asset = classify_symbol_func(benchmark_input)
        if benchmark_asset.asset_class != asset_class:
            raise ValueError("invalid_benchmark_symbol")
        benchmark_symbol = benchmark_asset.symbol
    else:
        benchmark_symbol = default_benchmark_func(asset_class, symbols)

    config = {
        "template": payload["template"],
        "asset_class": asset_class,
        "symbols": symbols,
        "timeframe": timeframe,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "side": payload.get("side") or "long",
        "starting_capital": payload.get("starting_capital") or 1000,
        "allocation_method": payload.get("allocation_method") or "equal_weight",
        "benchmark_symbol": benchmark_symbol,
        "parameters": payload.get("parameters") or {},
    }
    if _execution_realism_feature_enabled():
        config["_execution_realism"] = _normalize_execution_realism(
            payload.get("_execution_realism")
        )

    # Task 3: Handle DCA cadence
    if config["template"] == "dca_accumulation":
        cadence = (payload.get("parameters") or {}).get("dca_cadence") or "weekly"
        config["parameters"]["dca_cadence"] = cadence.lower()

    return config


def validate_backtest_config(config: dict[str, Any]) -> None:
    if config["template"] not in ALLOWED_TEMPLATES:
        raise ValueError("unsupported_template")
    if config["side"] != "long":
        raise ValueError("unsupported_side")
    if config["allocation_method"] != "equal_weight":
        raise ValueError("unsupported_allocation_method")
    if not 1000 <= float(config["starting_capital"]) <= 100000000:
        raise ValueError("invalid_starting_capital")
    if len(config["symbols"]) < 1 or len(config["symbols"]) > 5:
        raise ValueError("invalid_symbol_count")
    if config["timeframe"] not in ALLOWED_TIMEFRAMES:
        raise ValueError("unsupported_timeframe")

    start = date.fromisoformat(config["start_date"])
    end = date.fromisoformat(config["end_date"])
    validate_backtest_date_window(start=start, end=end)
    validate_market_data_window(
        asset_class=config["asset_class"],
        timeframe=config["timeframe"],
        start_date=start,
        end_date=end,
    )

    if any(symbol in STABLECOINS for symbol in config["symbols"]):
        raise ValueError("stablecoin_not_supported")

    # Registry-driven parameter validation (Task 10)
    params = dict(config.get("parameters") or {})
    template_name = config["template"]
    if template_name == "rsi_mean_reversion":
        rule_spec = params.pop("rule_spec", None)
        params = normalize_indicator_parameters(
            str(params.get("indicator") or "rsi"),
            params,
        )
        if rule_spec is not None:
            validate_rule_spec(rule_spec)
            params["rule_spec"] = rule_spec
        config["parameters"] = params
    if template_name == "signal_strategy":
        validate_rule_spec(params.get("rule_spec"))
        config["parameters"] = params
        return
    capability = STRATEGY_CAPABILITIES[template_name]

    allowed_params = set(capability.parameters.keys()) | {"rule_spec"}
    unknown = set(params.keys()) - allowed_params
    if unknown:
        raise ValueError("unsupported_parameters")

    for key, value in params.items():
        if key == "rule_spec":
            continue
        spec = capability.parameters[key]
        if spec.allowed_values and value not in spec.allowed_values:
            raise ValueError(f"unsupported_parameter_value_{key}")
