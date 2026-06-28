from __future__ import annotations

from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import Any


@dataclass(frozen=True)
class IndicatorInfo:
    key: str
    label: str
    description: str
    support_status: str = "draft_only"
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class IndicatorParameterSpec:
    key: str
    label: str
    default: int | float | str
    min_value: int | float | None = None
    max_value: int | float | None = None
    value_type: str = "number"


@dataclass(frozen=True)
class IndicatorExecutionSpec:
    key: str
    label: str
    description: str
    default_period: int
    output_selector: str
    warmup_bars: int
    threshold_min: float
    threshold_max: float
    default_entry_threshold: float
    default_exit_threshold: float
    parameter_schema: tuple[IndicatorParameterSpec, ...]
    required_columns: tuple[str, ...] = ("close",)
    category: str = "momentum"
    aliases: tuple[str, ...] = ()
    support_status: str = "executable"
    provider_source: str = "native"
    default_parameters: dict[str, int | float | str] = field(default_factory=dict)
    output_roles: dict[str, str] = field(default_factory=dict)

    def format_threshold_rule(
        self,
        side: str,
        *,
        threshold: float | None = None,
        period: int | None = None,
    ) -> str:
        resolved_period = period or self.default_period
        if side == "entry":
            resolved_threshold = (
                self.default_entry_threshold if threshold is None else threshold
            )
            return (
                f"Buy when {self.label}({resolved_period}) drops to "
                f"{_format_number(resolved_threshold)} or below"
            )
        resolved_threshold = (
            self.default_exit_threshold if threshold is None else threshold
        )
        return (
            f"Sell when {self.label}({resolved_period}) rises to "
            f"{_format_number(resolved_threshold)} or above"
        )


EXECUTABLE_INDICATORS: dict[str, IndicatorExecutionSpec] = {
    "rsi": IndicatorExecutionSpec(
        key="rsi",
        label="RSI",
        description="Relative Strength Index; a momentum gauge from 0 to 100.",
        default_period=14,
        output_selector="RSI_{period}",
        warmup_bars=14,
        threshold_min=0,
        threshold_max=100,
        default_entry_threshold=30,
        default_exit_threshold=55,
        aliases=(
            "relative strength index",
            "rsi threshold",
            "rsi_threshold",
            "rsi mean reversion",
            "rsi_mean_reversion",
            "oversold",
            "overbought",
            "momentum gauge",
        ),
        parameter_schema=(
            IndicatorParameterSpec(
                key="indicator_period",
                label="RSI period",
                default=14,
                min_value=2,
                max_value=100,
            ),
            IndicatorParameterSpec(
                key="entry_threshold",
                label="Entry threshold",
                default=30,
                min_value=0,
                max_value=100,
            ),
            IndicatorParameterSpec(
                key="exit_threshold",
                label="Exit threshold",
                default=55,
                min_value=0,
                max_value=100,
            ),
        ),
        default_parameters={"period": 14},
        output_roles={"value": "RSI_{period}"},
    ),
    "sma": IndicatorExecutionSpec(
        key="sma",
        label="SMA",
        description="Simple moving average over a fixed number of bars.",
        default_period=20,
        output_selector="SMA_{period}",
        warmup_bars=20,
        threshold_min=-1_000_000_000,
        threshold_max=1_000_000_000,
        default_entry_threshold=0,
        default_exit_threshold=0,
        required_columns=("close",),
        category="trend",
        aliases=("simple moving average", "moving average", "average price"),
        parameter_schema=(
            IndicatorParameterSpec(
                key="indicator_period",
                label="SMA period",
                default=20,
                min_value=2,
                max_value=300,
            ),
        ),
        default_parameters={"period": 20},
        output_roles={"value": "SMA_{period}"},
    ),
    "ema": IndicatorExecutionSpec(
        key="ema",
        label="EMA",
        description="Exponential moving average over a fixed number of bars.",
        default_period=20,
        output_selector="EMA_{period}",
        warmup_bars=20,
        threshold_min=-1_000_000_000,
        threshold_max=1_000_000_000,
        default_entry_threshold=0,
        default_exit_threshold=0,
        required_columns=("close",),
        category="trend",
        aliases=("exponential moving average", "moving average"),
        parameter_schema=(
            IndicatorParameterSpec(
                key="indicator_period",
                label="EMA period",
                default=20,
                min_value=2,
                max_value=300,
            ),
        ),
        default_parameters={"period": 20},
        output_roles={"value": "EMA_{period}"},
    ),
    "macd": IndicatorExecutionSpec(
        key="macd",
        label="MACD",
        description="Moving Average Convergence Divergence momentum lines.",
        default_period=26,
        output_selector="MACD_{fast}_{slow}_{signal}",
        warmup_bars=35,
        threshold_min=-1_000_000_000,
        threshold_max=1_000_000_000,
        default_entry_threshold=0,
        default_exit_threshold=0,
        required_columns=("close",),
        category="momentum",
        aliases=("moving average convergence divergence", "macd crossover"),
        provider_source="pandas_ta_classic",
        default_parameters={"fast": 12, "slow": 26, "signal": 9},
        output_roles={
            "macd": "MACD_{fast}_{slow}_{signal}",
            "signal": "MACDs_{fast}_{slow}_{signal}",
            "histogram": "MACDh_{fast}_{slow}_{signal}",
        },
        parameter_schema=(
            IndicatorParameterSpec(
                key="fast",
                label="Fast EMA",
                default=12,
                min_value=2,
                max_value=300,
            ),
            IndicatorParameterSpec(
                key="slow",
                label="Slow EMA",
                default=26,
                min_value=3,
                max_value=400,
            ),
            IndicatorParameterSpec(
                key="signal",
                label="Signal EMA",
                default=9,
                min_value=2,
                max_value=200,
            ),
        ),
    ),
    "bbands": IndicatorExecutionSpec(
        key="bbands",
        label="Bollinger Bands",
        description="Volatility bands around a moving average.",
        default_period=20,
        output_selector="BBM_{length}_{std}",
        warmup_bars=20,
        threshold_min=-1_000_000_000,
        threshold_max=1_000_000_000,
        default_entry_threshold=0,
        default_exit_threshold=0,
        required_columns=("close",),
        category="volatility",
        aliases=("bollinger", "bollinger bands", "volatility bands"),
        provider_source="pandas_ta_classic",
        default_parameters={"length": 20, "std": 2.0},
        output_roles={
            "lower": "BBL_{length}_{std}",
            "middle": "BBM_{length}_{std}",
            "upper": "BBU_{length}_{std}",
            "bandwidth": "BBB_{length}_{std}",
            "percent": "BBP_{length}_{std}",
        },
        parameter_schema=(
            IndicatorParameterSpec(
                key="length",
                label="Band length",
                default=20,
                min_value=2,
                max_value=300,
            ),
            IndicatorParameterSpec(
                key="std",
                label="Standard deviation",
                default=2.0,
                min_value=0.1,
                max_value=10,
            ),
        ),
    ),
}


# Catalog metadata for the curated indicators surfaced in discovery/search. The
# `support_status` of each entry is DERIVED (not hand-maintained) from
# EXECUTABLE_INDICATORS membership below: an indicator is "executable" iff the engine
# has an execution spec that computes it, otherwise it is "draft_only" (catalog/draft).
# This keeps a single source of truth for "does this indicator compute".
_CATALOG_INDICATORS: tuple[IndicatorInfo, ...] = (
    IndicatorInfo(
        "rsi",
        "RSI",
        "Relative Strength Index; a momentum gauge from 0 to 100.",
        aliases=("relative strength index", "oversold", "overbought", "momentum gauge"),
    ),
    IndicatorInfo(
        "sma",
        "Simple moving average",
        "Average price over a set number of bars.",
        aliases=("simple moving average", "moving average", "average price"),
    ),
    IndicatorInfo(
        "ema",
        "Exponential moving average",
        "Moving average that reacts faster to recent prices.",
        aliases=("exponential moving average", "moving average"),
    ),
    IndicatorInfo(
        "macd",
        "MACD",
        "Momentum indicator based on two moving averages.",
        aliases=("moving average convergence divergence", "momentum", "macd crossover"),
    ),
    IndicatorInfo(
        "bbands",
        "Bollinger Bands",
        "Volatility bands around a moving average.",
        aliases=("bollinger", "bollinger bands", "volatility bands"),
    ),
    IndicatorInfo(
        "atr",
        "ATR",
        "Average true range, commonly used to estimate volatility.",
        aliases=("average true range", "volatility"),
    ),
    IndicatorInfo(
        "vwap",
        "VWAP",
        "Volume-weighted average price.",
        aliases=("volume weighted average price",),
    ),
    IndicatorInfo(
        "obv",
        "OBV",
        "On-balance volume, a volume momentum indicator.",
        aliases=("on balance volume", "volume momentum"),
    ),
    IndicatorInfo(
        "stoch",
        "Stochastic oscillator",
        "Momentum indicator comparing close to recent range.",
        aliases=("stochastic", "stochastic oscillator"),
    ),
)


def _catalog_support_status(key: str) -> str:
    return "executable" if key in EXECUTABLE_INDICATORS else "draft_only"


_KNOWN_INDICATORS = {
    info.key: replace(info, support_status=_catalog_support_status(info.key))
    for info in _CATALOG_INDICATORS
}


_EXECUTABLE_INDICATOR_ALIASES: dict[str, str] = {
    alias: spec.key
    for spec in EXECUTABLE_INDICATORS.values()
    for alias in (spec.key, spec.label.lower(), *spec.aliases)
}

_PERIOD_KEYS = {"period", "length", "rsi_period", "indicator_period"}
_ENTRY_THRESHOLD_KEYS = {"entry_threshold", "buy_threshold", "lower_threshold"}
_EXIT_THRESHOLD_KEYS = {"exit_threshold", "sell_threshold", "upper_threshold"}


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


def executable_indicator_spec(value: str | None) -> IndicatorExecutionSpec | None:
    if not value:
        return None
    normalized = " ".join(str(value).strip().lower().replace("-", " ").split())
    key = _EXECUTABLE_INDICATOR_ALIASES.get(normalized)
    if key is None:
        compact = normalized.replace(" ", "_")
        key = _EXECUTABLE_INDICATOR_ALIASES.get(compact)
    return EXECUTABLE_INDICATORS.get(key or normalized)


def detect_executable_indicator_key(
    text: str,
    *,
    default: str = "rsi",
) -> str:
    normalized = " ".join(text.lower().replace("-", " ").split())
    for spec in EXECUTABLE_INDICATORS.values():
        aliases = (spec.key, spec.label.lower(), *spec.aliases)
        if any(alias in normalized for alias in aliases):
            return spec.key
    fallback = executable_indicator_spec(default)
    return fallback.key if fallback is not None else default


def normalize_indicator_parameters(
    indicator: str | None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_parameters = dict(parameters or {})
    raw_indicator = raw_parameters.pop("indicator", indicator or "rsi")
    spec = executable_indicator_spec(str(raw_indicator))
    if spec is None:
        raise ValueError("unsupported_indicator")

    unknown_parameters = dict(raw_parameters)
    period = _consume_number(
        unknown_parameters,
        keys=_PERIOD_KEYS,
        default=spec.default_period,
        cast=int,
    )
    entry_threshold = _consume_number(
        unknown_parameters,
        keys=_ENTRY_THRESHOLD_KEYS,
        default=spec.default_entry_threshold,
        cast=float,
    )
    exit_threshold = _consume_number(
        unknown_parameters,
        keys=_EXIT_THRESHOLD_KEYS,
        default=spec.default_exit_threshold,
        cast=float,
    )

    _validate_period(spec, period)
    _validate_threshold(spec, entry_threshold)
    _validate_threshold(spec, exit_threshold)

    return {
        "indicator": spec.key,
        "indicator_period": period,
        "entry_threshold": entry_threshold,
        "exit_threshold": exit_threshold,
        **unknown_parameters,
    }


def indicator_parameters_from_ref(
    spec: IndicatorExecutionSpec,
    ref: dict[str, Any],
) -> dict[str, int | float | str]:
    raw = dict(spec.default_parameters)
    if "period" in ref:
        raw["period" if spec.key in {"rsi", "sma", "ema"} else "length"] = ref["period"]
    raw.update(ref.get("parameters") if isinstance(ref.get("parameters"), dict) else {})

    normalized: dict[str, int | float | str] = {}
    for parameter in spec.parameter_schema:
        raw_value = raw.get(parameter.key)
        if raw_value is None and parameter.key == "indicator_period":
            raw_value = raw.get("period", parameter.default)
        if raw_value is None:
            raw_value = parameter.default
        value = _coerce_indicator_ref_parameter(raw_value, parameter.value_type)
        if parameter.min_value is not None and float(value) < float(parameter.min_value):
            raise ValueError("invalid_indicator_parameter")
        if parameter.max_value is not None and float(value) > float(parameter.max_value):
            raise ValueError("invalid_indicator_parameter")
        normalized[parameter.key] = value

    if spec.key in {"rsi", "sma", "ema"}:
        period = int(
            float(
                normalized.get(
                    "indicator_period",
                    raw.get("period", spec.default_period),
                )
            )
        )
        normalized["period"] = period
    if spec.key == "macd":
        fast = int(float(normalized["fast"]))
        slow = int(float(normalized["slow"]))
        signal = int(float(normalized["signal"]))
        if fast >= slow:
            raise ValueError("invalid_indicator_parameter")
        normalized.update({"fast": fast, "slow": slow, "signal": signal})
    if spec.key == "bbands":
        normalized["length"] = int(float(normalized["length"]))
        normalized["std"] = float(normalized["std"])

    return normalized


def indicator_warmup_from_ref(
    spec: IndicatorExecutionSpec,
    ref: dict[str, Any],
) -> int:
    parameters = indicator_parameters_from_ref(spec, ref)
    if spec.key == "macd":
        return max(
            int(spec.warmup_bars),
            int(parameters["slow"]) + int(parameters["signal"]),
        )
    if spec.key == "bbands":
        return max(int(spec.warmup_bars), int(parameters["length"]))
    return max(int(spec.warmup_bars), int(parameters.get("period", spec.default_period)))


def indicator_assumption_lines(parameters: dict[str, Any]) -> list[str]:
    spec = executable_indicator_spec(str(parameters.get("indicator") or "rsi"))
    if spec is None:
        return []
    normalized = normalize_indicator_parameters(spec.key, parameters)
    period = int(normalized["indicator_period"])
    entry_threshold = float(normalized["entry_threshold"])
    exit_threshold = float(normalized["exit_threshold"])
    return [
        f"Indicator: {spec.label}({period}).",
        f"Buy threshold: {spec.label} at or below {_format_number(entry_threshold)}.",
        f"Exit threshold: {spec.label} at or above {_format_number(exit_threshold)}.",
    ]


def _consume_number(
    parameters: dict[str, Any],
    *,
    keys: set[str],
    default: int | float,
    cast: type[int] | type[float],
) -> int | float:
    for key in keys:
        if key in parameters:
            raw_value = parameters.pop(key)
            try:
                return cast(float(raw_value))
            except (TypeError, ValueError) as exc:
                raise ValueError("invalid_indicator_parameter") from exc
    return default


def _validate_period(spec: IndicatorExecutionSpec, period: int | float) -> None:
    period_spec = next(
        (item for item in spec.parameter_schema if item.key == "indicator_period"),
        None,
    )
    if period_spec is None:
        return
    if period_spec.min_value is not None and period < period_spec.min_value:
        raise ValueError("indicator_period_out_of_bounds")
    if period_spec.max_value is not None and period > period_spec.max_value:
        raise ValueError("indicator_period_out_of_bounds")


def _validate_threshold(spec: IndicatorExecutionSpec, threshold: float) -> None:
    if threshold < spec.threshold_min or threshold > spec.threshold_max:
        raise ValueError("indicator_threshold_out_of_bounds")


def _coerce_indicator_ref_parameter(value: object, value_type: str) -> int | float | str:
    if value_type == "string":
        return str(value)
    if value_type == "integer":
        return int(float(value))
    numeric = float(value)
    return int(numeric) if numeric.is_integer() else numeric


def _format_number(value: float | int) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{float(value):.2f}".rstrip("0").rstrip(".")


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
