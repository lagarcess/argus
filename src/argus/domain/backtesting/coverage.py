from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from math import ceil
from typing import Any, Callable

import pandas as pd
from pydantic import BaseModel

from argus.domain.market_data.capabilities import (
    PROVIDER_TIMEFRAME_MINUTES,
    expected_candle_count,
)

_MIN_OBSERVATION_COVERAGE = 0.8
_EQUITY_SESSION_MINUTES = 390


class CoverageDateRange(BaseModel):
    start: str
    end: str


class MarketDataCoverageError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PreparedMarketData:
    requested_date_range: CoverageDateRange
    effective_date_range: CoverageDateRange
    outcome: str
    dataset_id: str
    bars_by_symbol: dict[str, pd.DataFrame]
    observations_by_symbol: dict[str, int]

    def bars_for(self, symbol: str) -> pd.DataFrame:
        try:
            bars = self.bars_by_symbol[symbol.strip().upper()]
        except KeyError as exc:
            raise MarketDataCoverageError("market_data_unavailable") from exc
        return bars.copy(deep=True)

    def price_series_for(self, symbol: str) -> pd.Series:
        return self.bars_for(symbol)["close"].copy()

    def coverage_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "market_data_coverage_v1",
            "outcome": self.outcome,
            "requested_date_range": self.requested_date_range.model_dump(),
            "effective_date_range": self.effective_date_range.model_dump(),
            "dataset_id": self.dataset_id,
            "observations_by_symbol": dict(self.observations_by_symbol),
        }


FetchOhlcv = Callable[..., pd.DataFrame]


def prepare_market_data(
    config: dict[str, Any],
    *,
    fetch_ohlcv_func: FetchOhlcv | None = None,
    approved_coverage: dict[str, Any] | None = None,
) -> PreparedMarketData:
    if fetch_ohlcv_func is None:
        from argus.domain.market_data import fetch_ohlcv

        fetch_ohlcv_func = fetch_ohlcv

    requested = _requested_date_range(config)
    fetch_start = date.fromisoformat(str(config["start_date"]))
    fetch_end = date.fromisoformat(str(config["end_date"]))
    symbols = _required_symbols(config)
    frames: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        try:
            raw = fetch_ohlcv_func(
                symbol=symbol,
                asset_class=config["asset_class"],
                start_date=fetch_start,
                end_date=fetch_end,
                timeframe=config["timeframe"],
            )
            frames[symbol] = _clip_to_requested_window(
                _normalize_frame(raw),
                start_date=fetch_start,
                end_date=fetch_end,
            )
        except MarketDataCoverageError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise MarketDataCoverageError("market_data_unavailable") from exc

    common_observations: pd.DatetimeIndex | None = None
    for frame in frames.values():
        common_observations = (
            frame.index
            if common_observations is None
            else common_observations.intersection(frame.index)
        )
    if common_observations is None or len(common_observations) < 2:
        raise MarketDataCoverageError("no_common_data_window")
    common_observations = common_observations.unique().sort_values()
    common_start = common_observations[0]
    common_end = common_observations[-1]

    trimmed = {
        symbol: frame.loc[(frame.index >= common_start) & (frame.index <= common_end)]
        for symbol, frame in frames.items()
    }
    if any(frame.empty for frame in trimmed.values()):
        raise MarketDataCoverageError("no_common_data_window")
    _validate_observation_density(
        trimmed,
        asset_class=str(config["asset_class"]),
        timeframe=str(config["timeframe"]),
        start_date=pd.Timestamp(common_start).date(),
        end_date=pd.Timestamp(common_end).date(),
    )

    effective = CoverageDateRange(
        start=pd.Timestamp(common_start).date().isoformat(),
        end=pd.Timestamp(common_end).date().isoformat(),
    )
    _validate_approved_window(
        approved_coverage,
        requested=requested,
        effective=effective,
    )
    outcome = "full_coverage" if effective == requested else "adjusted_coverage"
    observations = {symbol: len(frame) for symbol, frame in trimmed.items()}
    return PreparedMarketData(
        requested_date_range=requested,
        effective_date_range=effective,
        outcome=outcome,
        dataset_id=_dataset_id(trimmed),
        bars_by_symbol=trimmed,
        observations_by_symbol=observations,
    )


def apply_coverage_to_config(
    config: dict[str, Any],
    prepared: PreparedMarketData,
) -> dict[str, Any]:
    effective = prepared.effective_date_range.model_dump()
    result = dict(config)
    result["start_date"] = effective["start"]
    result["end_date"] = effective["end"]
    result["requested_date_range"] = prepared.requested_date_range.model_dump()
    result["effective_date_range"] = effective
    result["data_coverage"] = prepared.coverage_payload()
    return result


def _requested_date_range(config: dict[str, Any]) -> CoverageDateRange:
    raw = config.get("requested_date_range")
    if isinstance(raw, dict):
        start = raw.get("start")
        end = raw.get("end")
        if isinstance(start, str) and isinstance(end, str):
            return CoverageDateRange(start=start, end=end)
    return CoverageDateRange(
        start=str(config["start_date"]),
        end=str(config["end_date"]),
    )


def _required_symbols(config: dict[str, Any]) -> list[str]:
    required: list[str] = []
    for raw_symbol in [*config["symbols"], config["benchmark_symbol"]]:
        symbol = str(raw_symbol).strip().upper()
        if symbol and symbol not in required:
            required.append(symbol)
    if not required:
        raise MarketDataCoverageError("market_data_unavailable")
    return required


def _normalize_frame(raw: pd.DataFrame) -> pd.DataFrame:
    if raw is None or raw.empty:
        raise MarketDataCoverageError("market_data_unavailable")
    frame = raw.copy(deep=True)
    frame.index = pd.to_datetime(frame.index, utc=True)
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    required = ["open", "high", "low", "close", "volume"]
    if any(column not in frame.columns for column in required):
        raise MarketDataCoverageError("market_data_unavailable")
    frame = frame.loc[:, required].apply(pd.to_numeric, errors="coerce").dropna()
    if len(frame) < 2:
        raise MarketDataCoverageError("insufficient_common_data")
    return frame.astype(float)


def _clip_to_requested_window(
    frame: pd.DataFrame,
    *,
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    start = pd.Timestamp(start_date, tz="UTC")
    end = (
        pd.Timestamp(end_date, tz="UTC")
        + pd.Timedelta(days=1)
        - pd.Timedelta(nanoseconds=1)
    )
    clipped = frame.loc[(frame.index >= start) & (frame.index <= end)]
    if len(clipped) < 2:
        raise MarketDataCoverageError("insufficient_common_data")
    return clipped


def _validate_observation_density(
    frames: dict[str, pd.DataFrame],
    *,
    asset_class: str,
    timeframe: str,
    start_date: date,
    end_date: date,
) -> None:
    target = pd.DatetimeIndex([])
    for frame in frames.values():
        target = target.union(frame.index)
    target = target.unique().sort_values()
    if len(target) < 2:
        raise MarketDataCoverageError("insufficient_common_data")
    minimum_observations = _minimum_observations_for_window(
        asset_class=asset_class,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
    )
    if len(target) < minimum_observations:
        raise MarketDataCoverageError("insufficient_common_data")
    minimum_ratio = 1.0 if len(target) <= 2 else 0.8
    for frame in frames.values():
        observed_ratio = float(frame.index.isin(target).sum()) / float(len(target))
        if observed_ratio < minimum_ratio:
            raise MarketDataCoverageError("insufficient_common_data")


def _minimum_observations_for_window(
    *,
    asset_class: str,
    timeframe: str,
    start_date: date,
    end_date: date,
) -> int:
    interval_minutes = PROVIDER_TIMEFRAME_MINUTES.get(_normalized_timeframe(timeframe))
    if interval_minutes is None:
        return 2
    if asset_class == "equity":
        session_days = len(pd.bdate_range(start=start_date, end=end_date))
        observations_per_session = max(
            1,
            ceil(_EQUITY_SESSION_MINUTES / interval_minutes),
        )
        expected = session_days * observations_per_session
        holiday_tolerant_expected = max(
            2,
            expected - observations_per_session,
        )
        return max(
            2,
            min(
                holiday_tolerant_expected,
                ceil(expected * _MIN_OBSERVATION_COVERAGE),
            ),
        )
    else:
        expected = expected_candle_count(
            start_date=start_date,
            end_date=end_date,
            interval_minutes=interval_minutes,
        )
    return max(2, ceil(expected * _MIN_OBSERVATION_COVERAGE))


def _normalized_timeframe(value: str) -> str:
    normalized = value.strip().lower()
    aliases = {
        "1d": "1D",
        "1day": "1D",
        "daily": "1D",
        "day": "1D",
        "60m": "1h",
        "120m": "2h",
        "240m": "4h",
        "360m": "6h",
        "720m": "12h",
    }
    return aliases.get(normalized, normalized)


def _validate_approved_window(
    approved: dict[str, Any] | None,
    *,
    requested: CoverageDateRange,
    effective: CoverageDateRange,
) -> None:
    if approved is None:
        return
    try:
        approved_requested = CoverageDateRange.model_validate(
            approved["requested_date_range"]
        )
        approved_effective = CoverageDateRange.model_validate(
            approved["effective_date_range"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MarketDataCoverageError("approved_data_window_unavailable") from exc
    if approved_requested != requested or approved_effective != effective:
        raise MarketDataCoverageError("approved_data_window_unavailable")


def _dataset_id(frames: dict[str, pd.DataFrame]) -> str:
    digest = hashlib.sha256()
    for symbol in sorted(frames):
        frame = frames[symbol]
        digest.update(symbol.encode("utf-8"))
        digest.update(
            json.dumps(
                [str(column) for column in frame.columns],
                separators=(",", ":"),
            ).encode("utf-8")
        )
        digest.update(pd.util.hash_pandas_object(frame, index=True).values.tobytes())
    return f"sha256:{digest.hexdigest()}"
