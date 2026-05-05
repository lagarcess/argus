from __future__ import annotations

from dataclasses import dataclass
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
    threshold_min: float
    threshold_max: float
    default_entry_threshold: float
    default_exit_threshold: float
    parameter_schema: tuple[IndicatorParameterSpec, ...]
    aliases: tuple[str, ...] = ()

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
        threshold_min=0,
        threshold_max=100,
        default_entry_threshold=30,
        default_exit_threshold=55,
        aliases=(
            "relative strength index",
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
    )
}


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
        item for item in spec.parameter_schema if item.key == "indicator_period"
    )
    if period_spec.min_value is not None and period < period_spec.min_value:
        raise ValueError("indicator_period_out_of_bounds")
    if period_spec.max_value is not None and period > period_spec.max_value:
        raise ValueError("indicator_period_out_of_bounds")


def _validate_threshold(spec: IndicatorExecutionSpec, threshold: float) -> None:
    if threshold < spec.threshold_min or threshold > spec.threshold_max:
        raise ValueError("indicator_threshold_out_of_bounds")


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
