from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from math import ceil
from typing import Any, Callable, Sequence

import pandas as pd
from loguru import logger
from pydantic import BaseModel

from argus.domain.backtesting.types import CoverageAdjustmentReason
from argus.domain.market_data import fetch_ohlcv as _DEFAULT_FETCH_OHLC
from argus.domain.market_data.capabilities import (
    EASTERN,
    PROVIDER_TIMEFRAME_MINUTES,
    EquityMarketSession,
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
    adjustment_reason: CoverageAdjustmentReason | None
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
        payload = {
            "schema_version": "market_data_coverage_v1",
            "outcome": self.outcome,
            "requested_date_range": self.requested_date_range.model_dump(),
            "effective_date_range": self.effective_date_range.model_dump(),
            "dataset_id": self.dataset_id,
            "observations_by_symbol": dict(self.observations_by_symbol),
        }
        if self.adjustment_reason is not None:
            payload["adjustment_reason"] = self.adjustment_reason
        return payload


FetchOhlcv = Callable[..., pd.DataFrame]


FetchMarketCalendar = Callable[..., Sequence[EquityMarketSession]]


def prepare_market_data(
    config: dict[str, Any],
    *,
    fetch_ohlcv_func: FetchOhlcv | None = None,
    fetch_market_calendar_func: FetchMarketCalendar | None = None,
    approved_coverage: dict[str, Any] | None = None,
    approved_adjustment_reason: CoverageAdjustmentReason | None = None,
    now: datetime | None = None,
) -> PreparedMarketData:
    uses_default_market_data_provider = fetch_ohlcv_func is _DEFAULT_FETCH_OHLC
    if fetch_ohlcv_func is None:
        from argus.domain.market_data import fetch_ohlcv

        fetch_ohlcv_func = fetch_ohlcv
        uses_default_market_data_provider = fetch_ohlcv_func is _DEFAULT_FETCH_OHLC

    fetch_calendar = _calendar_fetcher(
        fetch_market_calendar_func,
        uses_default_market_data_provider=uses_default_market_data_provider,
    )
    requested = _requested_date_range(config)
    fetch_start = date.fromisoformat(str(config["start_date"]))
    fetch_end = _completed_data_end(
        asset_class=str(config["asset_class"]),
        timeframe=str(config["timeframe"]),
        fetch_end=date.fromisoformat(str(config["end_date"])),
        fetch_calendar=fetch_calendar,
        now=now,
    )
    if fetch_end < fetch_start:
        raise MarketDataCoverageError("no_common_data_window")
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
    equity_market_sessions = _equity_market_sessions_for_window(
        asset_class=str(config["asset_class"]),
        start_date=fetch_start,
        end_date=fetch_end,
        fetch_calendar=fetch_calendar,
    )
    _validate_observation_density(
        trimmed,
        asset_class=str(config["asset_class"]),
        timeframe=str(config["timeframe"]),
        start_date=pd.Timestamp(common_start).date(),
        end_date=pd.Timestamp(common_end).date(),
        equity_market_sessions=equity_market_sessions,
    )

    effective = CoverageDateRange(
        start=pd.Timestamp(common_start).date().isoformat(),
        end=pd.Timestamp(common_end).date().isoformat(),
    )
    dataset_id = _dataset_id(trimmed)
    _validate_approved_window(
        approved_coverage,
        requested=requested,
        effective=effective,
        dataset_id=dataset_id,
    )
    outcome = "full_coverage" if effective == requested else "adjusted_coverage"
    if approved_coverage is not None:
        adjustment_reason = approved_adjustment_reason
    else:
        adjustment_reason = _coverage_adjustment_reason(
            asset_class=str(config["asset_class"]),
            requested=requested,
            effective=effective,
            candidate_start=fetch_start,
            candidate_end=fetch_end,
            equity_market_sessions=equity_market_sessions,
        )
    observations = {symbol: len(frame) for symbol, frame in trimmed.items()}
    return PreparedMarketData(
        requested_date_range=requested,
        effective_date_range=effective,
        outcome=outcome,
        adjustment_reason=adjustment_reason,
        dataset_id=dataset_id,
        bars_by_symbol=trimmed,
        observations_by_symbol=observations,
    )


def _coverage_adjustment_reason(
    *,
    asset_class: str,
    requested: CoverageDateRange,
    effective: CoverageDateRange,
    candidate_start: date,
    candidate_end: date,
    equity_market_sessions: Sequence[EquityMarketSession] | None,
) -> CoverageAdjustmentReason:
    if effective == requested:
        return "none"

    expected_start = candidate_start
    expected_end = candidate_end
    if asset_class == "equity" and equity_market_sessions:
        expected_start = min(session.session_date for session in equity_market_sessions)
        expected_end = max(session.session_date for session in equity_market_sessions)

    if (
        effective.start == expected_start.isoformat()
        and effective.end == expected_end.isoformat()
    ):
        return "calendar_alignment"
    return "provider_coverage_adjustment"


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
    equity_market_sessions: Sequence[EquityMarketSession] | None = None,
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
        equity_market_sessions=equity_market_sessions,
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
    equity_market_sessions: Sequence[EquityMarketSession] | None = None,
) -> int:
    interval_minutes = PROVIDER_TIMEFRAME_MINUTES.get(_normalized_timeframe(timeframe))
    if interval_minutes is None:
        return 2
    if asset_class == "equity":
        calendar_expected = _calendar_expected_equity_observations(
            sessions=equity_market_sessions,
            start_date=start_date,
            end_date=end_date,
            interval_minutes=interval_minutes,
        )
        if calendar_expected is not None:
            return max(2, ceil(calendar_expected * _MIN_OBSERVATION_COVERAGE))
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


def _provider_mode_is_synthetic() -> bool:
    provider_mode = (
        (os.getenv("ARGUS_MARKET_DATA_PROVIDER_MODE") or "live_provider").strip().lower()
    )
    return provider_mode == "synthetic_unit_fixture"


def _calendar_fetcher(
    fetch_market_calendar_func: FetchMarketCalendar | None,
    *,
    uses_default_market_data_provider: bool,
) -> FetchMarketCalendar | None:
    if _provider_mode_is_synthetic():
        return None
    if fetch_market_calendar_func is not None:
        return fetch_market_calendar_func
    if uses_default_market_data_provider:
        from argus.domain.market_data.capabilities import fetch_alpaca_market_calendar

        return fetch_alpaca_market_calendar
    return None


_COMPLETED_SESSION_LOOKBACK_DAYS = 13


def _completed_data_end(
    *,
    asset_class: str,
    timeframe: str,
    fetch_end: date,
    fetch_calendar: FetchMarketCalendar | None,
    now: datetime | None,
) -> date:
    """A bar may enter coverage only once its trading day can no longer change.

    Continuous markets finalize a daily bar when its UTC day ends; an equity
    session's bar can still receive corrections after hours, so its day is
    complete only once its Eastern date has passed. Intraday timeframes keep
    the current day: their completed candles are valid data, and completion
    for them is a per-bar boundary, not a day boundary.
    """
    if _provider_mode_is_synthetic():
        return fetch_end
    if _normalized_timeframe(timeframe) != "1D":
        return fetch_end
    at = now if now is not None else datetime.now(timezone.utc)
    if at.tzinfo is None:
        raise ValueError("completed_data_end_requires_aware_datetime")
    if asset_class != "equity":
        today_utc = at.astimezone(timezone.utc).date()
        return min(fetch_end, today_utc - timedelta(days=1))
    today_eastern = at.astimezone(EASTERN).date()
    if fetch_end < today_eastern:
        # Historical windows need no calendar round-trip.
        return fetch_end
    completed_cap = today_eastern - timedelta(days=1)
    if fetch_calendar is None:
        return min(fetch_end, completed_cap)
    lookback_start = completed_cap - timedelta(days=_COMPLETED_SESSION_LOOKBACK_DAYS)
    try:
        completed_session_dates = [
            session.session_date
            for session in fetch_calendar(
                start_date=lookback_start, end_date=completed_cap
            )
            if lookback_start <= session.session_date <= completed_cap
        ]
        if not completed_session_dates:
            raise ValueError("market_calendar_window_empty")
    except MarketDataCoverageError:
        raise
    except Exception as exc:
        raise MarketDataCoverageError("market_data_unavailable") from exc
    return min(fetch_end, max(completed_session_dates))


def _equity_market_sessions_for_window(
    *,
    asset_class: str,
    start_date: date,
    end_date: date,
    fetch_calendar: FetchMarketCalendar | None,
) -> tuple[EquityMarketSession, ...] | None:
    if asset_class != "equity":
        return None
    if fetch_calendar is None:
        return None
    try:
        sessions = tuple(fetch_calendar(start_date=start_date, end_date=end_date))
        session_dates = [session.session_date for session in sessions]
        if (
            not sessions
            or any(not isinstance(session, EquityMarketSession) for session in sessions)
            or len(set(session_dates)) != len(session_dates)
            or any(
                not isinstance(session.session_date, date)
                or not isinstance(session.opens_at, datetime)
                or not isinstance(session.closes_at, datetime)
                or session.session_date < start_date
                or session.session_date > end_date
                or session.closes_at <= session.opens_at
                for session in sessions
            )
        ):
            raise ValueError("market_calendar_unavailable")
    except Exception as exc:
        raise MarketDataCoverageError("market_data_unavailable") from exc
    return sessions


def _calendar_expected_equity_observations(
    *,
    sessions: Sequence[EquityMarketSession] | None,
    start_date: date,
    end_date: date,
    interval_minutes: int,
) -> int | None:
    if sessions is None:
        return None
    unique_sessions: dict[date, EquityMarketSession] = {}
    try:
        for session in sessions:
            if start_date <= session.session_date <= end_date:
                if session.closes_at <= session.opens_at:
                    return None
                unique_sessions[session.session_date] = session
    except (AttributeError, TypeError):
        return None
    if not unique_sessions:
        return None
    return sum(
        max(
            1,
            ceil(
                (session.closes_at - session.opens_at).total_seconds()
                / 60
                / interval_minutes
            ),
        )
        for session in unique_sessions.values()
    )


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
    dataset_id: str,
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
        approved_preflight_id = approved["preflight_id"]
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning(
            "Approved data window rejected: malformed approval payload error={error}",
            error=str(exc),
        )
        raise MarketDataCoverageError("approved_data_window_unavailable") from exc
    mismatches: list[str] = []
    if approved_requested != requested:
        mismatches.append(
            "requested_range approved="
            f"{approved_requested.start}..{approved_requested.end}"
            f" current={requested.start}..{requested.end}"
        )
    if approved_effective != effective:
        mismatches.append(
            "effective_range approved="
            f"{approved_effective.start}..{approved_effective.end}"
            f" current={effective.start}..{effective.end}"
        )
    if not isinstance(approved_preflight_id, str) or approved_preflight_id != dataset_id:
        mismatches.append(
            f"dataset_id approved={approved_preflight_id} current={dataset_id}"
        )
    if mismatches:
        logger.warning(
            "Approved data window rejected: {mismatches}",
            mismatches="; ".join(mismatches),
        )
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
