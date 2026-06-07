from __future__ import annotations

from typing import Any

import pandas as pd

from argus.domain.indicators import IndicatorExecutionSpec, indicator_parameters_from_ref


def compute_indicator_output(
    data: pd.DataFrame,
    spec: IndicatorExecutionSpec,
    ref: dict[str, Any],
) -> pd.Series:
    parameters = indicator_parameters_from_ref(spec, ref)
    output = str(ref.get("output") or _default_output_role(spec)).lower()
    source_column = str(ref.get("field") or spec.required_columns[0])

    if source_column not in data.columns:
        raise ValueError("market_data_unavailable")
    source = data[source_column].astype(float)

    if spec.key == "rsi":
        return _rsi(source, int(parameters["period"]))
    if spec.key == "sma":
        period = int(parameters["period"])
        return source.rolling(period, min_periods=period).mean().astype(float)
    if spec.key == "ema":
        period = int(parameters["period"])
        return (
            source.ewm(span=period, adjust=False, min_periods=period).mean().astype(float)
        )
    if spec.key == "macd":
        return _macd_output(source, parameters, output)
    if spec.key == "bbands":
        return _bbands_output(source, parameters, output)
    raise ValueError("unsupported_indicator")


def _default_output_role(spec: IndicatorExecutionSpec) -> str:
    if spec.key in {"macd"}:
        return "macd"
    if spec.key in {"bbands"}:
        return "middle"
    return "value"


def _format_output_template(
    template: str, parameters: dict[str, int | float | str]
) -> str:
    formatted = dict(parameters)
    if "std" in formatted:
        formatted["std"] = f"{float(formatted['std']):.1f}"
    return template.format(**formatted)


def _select_output(
    frame: pd.DataFrame,
    spec: IndicatorExecutionSpec,
    output: str,
    parameters: dict[str, int | float | str],
) -> pd.Series:
    template = spec.output_roles.get(output)
    if template is None:
        raise ValueError("unsupported_indicator_output")
    column = _format_output_template(template, parameters)
    if column not in frame.columns:
        raise ValueError("unsupported_indicator_output")
    return frame[column].astype(float)


def _macd_output(
    close: pd.Series,
    parameters: dict[str, int | float | str],
    output: str,
) -> pd.Series:
    fast = int(parameters["fast"])
    slow = int(parameters["slow"])
    signal = int(parameters["signal"])
    try:
        import pandas_ta_classic as ta  # type: ignore[import-untyped]

        frame = ta.macd(close, fast=fast, slow=slow, signal=signal)
        if isinstance(frame, pd.DataFrame):
            from argus.domain.indicators import EXECUTABLE_INDICATORS

            return _select_output(
                frame, EXECUTABLE_INDICATORS["macd"], output, parameters
            )
    except Exception:
        pass

    macd = (
        close.ewm(span=fast, adjust=False, min_periods=fast).mean()
        - close.ewm(
            span=slow,
            adjust=False,
            min_periods=slow,
        ).mean()
    )
    signal_line = macd.ewm(span=signal, adjust=False, min_periods=signal).mean()
    if output == "macd":
        return macd.astype(float)
    if output == "signal":
        return signal_line.astype(float)
    if output == "histogram":
        return (macd - signal_line).astype(float)
    raise ValueError("unsupported_indicator_output")


def _bbands_output(
    close: pd.Series,
    parameters: dict[str, int | float | str],
    output: str,
) -> pd.Series:
    length = int(parameters["length"])
    std = float(parameters["std"])
    try:
        import pandas_ta_classic as ta  # type: ignore[import-untyped]

        frame = ta.bbands(close, length=length, std=std)
        if isinstance(frame, pd.DataFrame):
            from argus.domain.indicators import EXECUTABLE_INDICATORS

            return _select_output(
                frame, EXECUTABLE_INDICATORS["bbands"], output, parameters
            )
    except Exception:
        pass

    middle = close.rolling(length, min_periods=length).mean()
    deviation = close.rolling(length, min_periods=length).std(ddof=0)
    if output == "lower":
        return (middle - deviation * std).astype(float)
    if output == "middle":
        return middle.astype(float)
    if output == "upper":
        return (middle + deviation * std).astype(float)
    if output == "bandwidth":
        return (((deviation * std * 2) / middle) * 100).astype(float)
    if output == "percent":
        lower = middle - deviation * std
        upper = middle + deviation * std
        return ((close - lower) / (upper - lower)).astype(float)
    raise ValueError("unsupported_indicator_output")


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).rolling(period, min_periods=period).mean()
    rs = gain / loss.where(loss != 0)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.mask((loss == 0) & (gain > 0), 100.0)
    rsi = rsi.mask((loss == 0) & (gain == 0), 50.0)
    return rsi.astype(float)
