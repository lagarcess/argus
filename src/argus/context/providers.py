from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Any

import httpx

from argus.context.packets import ContextPacket, ContextPacketFact

FRED_API_BASE = "https://api.stlouisfed.org/fred"
ALPACA_DATA_BASE = "https://data.alpaca.markets"


def fetch_fred_macro_packet(
    *,
    series_id: str,
    observation_start: date,
    observation_end: date,
    api_key: str | None = None,
) -> ContextPacket:
    key = (api_key or os.getenv("FRED_API_KEY") or "").strip()
    if not key:
        raise ValueError("fred_api_key_required")
    response = httpx.get(
        f"{FRED_API_BASE}/series/observations",
        params={
            "series_id": series_id,
            "api_key": key,
            "file_type": "json",
            "observation_start": observation_start.isoformat(),
            "observation_end": observation_end.isoformat(),
        },
        timeout=8.0,
    )
    response.raise_for_status()
    payload = response.json()
    observations = payload.get("observations")
    if not isinstance(observations, list):
        observations = []
    return build_fred_macro_packet(
        series_id=series_id,
        observations=observations,
        observation_start=observation_start,
        observation_end=observation_end,
    )


def build_fred_macro_packet(
    *,
    series_id: str,
    observations: list[dict[str, Any]],
    observation_start: date,
    observation_end: date,
) -> ContextPacket:
    parsed = [
        observation
        for observation in (
            _fred_observation_fact(series_id=series_id, observation=item)
            for item in observations
        )
        if observation is not None
    ]
    facts: list[ContextPacketFact] = []
    if parsed:
        facts.append(parsed[-1])
    if len(parsed) >= 2:
        previous = parsed[-2]
        latest = parsed[-1]
        change = _as_float(latest.value) - _as_float(previous.value)
        facts.append(
            ContextPacketFact(
                kind="macro_observation_change",
                label=f"{series_id} change from previous observation",
                value=round(change, 4),
                observed_at=latest.observed_at,
                source_id=latest.source_id,
            )
        )
    return ContextPacket(
        provider="fred",
        packet_type="macro",
        scope={"series_id": series_id},
        source_ids=tuple(f"{series_id}:{fact.observed_at}" for fact in facts),
        coverage_start=observation_start,
        coverage_end=observation_end,
        freshness="unknown",
        facts=tuple(facts),
        limitations=(
            "FRED macro observations are contextual backdrop only.",
            "This packet cannot alter simulation metrics, trades, or benchmarks.",
        ),
    )


def fetch_alpaca_news_packet(
    *,
    symbols: list[str],
    start: date | datetime,
    end: date | datetime,
    limit: int = 10,
    api_key: str | None = None,
    secret_key: str | None = None,
) -> ContextPacket:
    response = httpx.get(
        f"{ALPACA_DATA_BASE}/v1beta1/news",
        params={
            "symbols": ",".join(_normalize_symbols(symbols)),
            "start": _dateish_to_api_value(start),
            "end": _dateish_to_api_value(end),
            "sort": "desc",
            "limit": max(1, min(limit, 50)),
            "include_content": "false",
        },
        headers=_alpaca_headers(api_key=api_key, secret_key=secret_key),
        timeout=8.0,
    )
    response.raise_for_status()
    payload = response.json()
    items = payload.get("news")
    if not isinstance(items, list):
        items = []
    return build_alpaca_news_packet(symbols=symbols, news_items=items, start=start, end=end)


def build_alpaca_news_packet(
    *,
    symbols: list[str],
    news_items: list[dict[str, Any]],
    start: date | datetime,
    end: date | datetime,
) -> ContextPacket:
    normalized_symbols = _normalize_symbols(symbols)
    facts = tuple(
        fact
        for fact in (_alpaca_news_fact(item) for item in news_items[:10])
        if fact is not None
    )
    return ContextPacket(
        provider="alpaca",
        packet_type="news",
        scope={"symbols": normalized_symbols},
        source_ids=tuple(str(fact.source_id) for fact in facts if fact.source_id),
        coverage_start=_coerce_date(start),
        coverage_end=_coerce_date(end),
        freshness="fresh",
        facts=facts,
        limitations=(
            "News is symbol/date scoped context only, not an executable signal.",
            "This packet cannot alter simulation truth or claim causality by itself.",
        ),
    )


def fetch_alpaca_corporate_actions_packet(
    *,
    symbols: list[str],
    start: date,
    end: date,
    api_key: str | None = None,
    secret_key: str | None = None,
) -> ContextPacket:
    response = httpx.get(
        f"{ALPACA_DATA_BASE}/v1/corporate-actions",
        params={
            "symbols": ",".join(_normalize_symbols(symbols)),
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        headers=_alpaca_headers(api_key=api_key, secret_key=secret_key),
        timeout=8.0,
    )
    response.raise_for_status()
    payload = response.json()
    items = payload.get("corporate_actions") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        items = []
    return build_alpaca_corporate_actions_packet(
        symbols=symbols,
        corporate_actions=items,
        start=start,
        end=end,
    )


def build_alpaca_corporate_actions_packet(
    *,
    symbols: list[str],
    corporate_actions: list[dict[str, Any]],
    start: date,
    end: date,
) -> ContextPacket:
    facts = tuple(
        fact
        for fact in (
            _alpaca_corporate_action_fact(item) for item in corporate_actions[:20]
        )
        if fact is not None
    )
    return ContextPacket(
        provider="alpaca",
        packet_type="corporate_actions",
        scope={"symbols": _normalize_symbols(symbols)},
        source_ids=tuple(str(fact.source_id) for fact in facts if fact.source_id),
        coverage_start=start,
        coverage_end=end,
        freshness="fresh",
        facts=facts,
        limitations=(
            "Corporate actions are event context only.",
            "Late provider updates may create a new packet but must not rewrite attached explanations.",
        ),
    )


def fetch_alpaca_market_movers_packet(
    *,
    market_type: str = "stocks",
    top: int = 10,
    api_key: str | None = None,
    secret_key: str | None = None,
) -> ContextPacket:
    response = httpx.get(
        f"{ALPACA_DATA_BASE}/v1beta1/screener/{market_type}/movers",
        params={"top": max(1, min(top, 50))},
        headers=_alpaca_headers(api_key=api_key, secret_key=secret_key),
        timeout=8.0,
    )
    response.raise_for_status()
    payload = response.json()
    return build_alpaca_market_movers_packet(
        market_type=market_type,
        movers=payload if isinstance(payload, dict) else {},
    )


def fetch_alpaca_most_actives_packet(
    *,
    by: str = "volume",
    top: int = 10,
    api_key: str | None = None,
    secret_key: str | None = None,
) -> ContextPacket:
    response = httpx.get(
        f"{ALPACA_DATA_BASE}/v1beta1/screener/stocks/most-actives",
        params={"by": by, "top": max(1, min(top, 100))},
        headers=_alpaca_headers(api_key=api_key, secret_key=secret_key),
        timeout=8.0,
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("most_actives") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        rows = []
    return build_alpaca_most_actives_packet(by=by, most_actives=rows)


def build_alpaca_market_movers_packet(
    *,
    market_type: str,
    movers: dict[str, Any],
) -> ContextPacket:
    facts: list[ContextPacketFact] = []
    retrieved_date = datetime.now(timezone.utc).date()
    for group in ("gainers", "losers"):
        rows = movers.get(group)
        if not isinstance(rows, list):
            continue
        for item in rows[:10]:
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            facts.append(
                ContextPacketFact(
                    kind=f"market_mover_{group[:-1]}",
                    label=f"{symbol} {group[:-1]}",
                    value={
                        "symbol": symbol,
                        "percent_change": item.get("percent_change")
                        or item.get("change_percent"),
                    },
                    source_id=f"{market_type}:{group}:{symbol}",
                )
            )
    return ContextPacket(
        provider="alpaca",
        packet_type="market_movers",
        scope={"market_type": market_type},
        source_ids=tuple(str(fact.source_id) for fact in facts if fact.source_id),
        coverage_start=retrieved_date,
        coverage_end=retrieved_date,
        freshness="fresh",
        facts=tuple(facts),
        limitations=(
            "Movers are very short-lived market context, not a dashboard feed.",
            "Movers cannot alter simulation truth or imply causality.",
        ),
    )


def build_alpaca_most_actives_packet(
    *,
    by: str,
    most_actives: list[dict[str, Any]],
) -> ContextPacket:
    retrieved_date = datetime.now(timezone.utc).date()
    facts: list[ContextPacketFact] = []
    for item in most_actives[:20]:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        facts.append(
            ContextPacketFact(
                kind="most_active_stock",
                label=f"{symbol} most active",
                value={
                    "symbol": symbol,
                    "volume": item.get("volume"),
                    "trade_count": item.get("trade_count") or item.get("trades"),
                    "rank_by": by,
                },
                source_id=f"stocks:most-actives:{by}:{symbol}",
            )
        )
    return ContextPacket(
        provider="alpaca",
        packet_type="most_actives",
        scope={"market_type": "stocks", "by": by},
        source_ids=tuple(str(fact.source_id) for fact in facts if fact.source_id),
        coverage_start=retrieved_date,
        coverage_end=retrieved_date,
        freshness="fresh",
        facts=tuple(facts),
        limitations=(
            "Most-actives data is very short-lived stocks context, not a product feed.",
            "Most-actives data cannot alter simulation truth or imply causality.",
        ),
    )


def _fred_observation_fact(
    *,
    series_id: str,
    observation: dict[str, Any],
) -> ContextPacketFact | None:
    observed_at = _parse_date(observation.get("date"))
    value = observation.get("value")
    if observed_at is None or value in (None, ".", ""):
        return None
    return ContextPacketFact(
        kind="macro_observation",
        label=f"{series_id} latest observation",
        value=_as_float(value),
        observed_at=observed_at,
        source_id=f"{series_id}:{observed_at.isoformat()}",
    )


def _alpaca_news_fact(item: dict[str, Any]) -> ContextPacketFact | None:
    headline = str(item.get("headline") or item.get("title") or "").strip()
    if not headline:
        return None
    source_id = str(item.get("id") or item.get("url") or headline)
    return ContextPacketFact(
        kind="news_headline",
        label=headline,
        value={
            "headline": headline,
            "symbols": item.get("symbols") or [],
            "url": item.get("url"),
            "source": item.get("source"),
        },
        observed_at=_parse_datetime(item.get("updated_at") or item.get("created_at")),
        source_id=source_id,
    )


def _alpaca_corporate_action_fact(item: dict[str, Any]) -> ContextPacketFact | None:
    symbol = str(item.get("symbol") or item.get("new_symbol") or "").strip().upper()
    action_type = str(item.get("type") or item.get("ca_type") or "").strip()
    if not symbol or not action_type:
        return None
    event_date = _parse_date(
        item.get("ex_date")
        or item.get("record_date")
        or item.get("payable_date")
        or item.get("date")
    )
    source_id = str(item.get("id") or f"{symbol}:{action_type}:{event_date}")
    return ContextPacketFact(
        kind="corporate_action",
        label=f"{symbol} {action_type}",
        value={
            "symbol": symbol,
            "type": action_type,
            "event_date": event_date.isoformat() if event_date else None,
            "raw": item,
        },
        observed_at=event_date,
        source_id=source_id,
    )


def _alpaca_headers(
    *,
    api_key: str | None,
    secret_key: str | None,
) -> dict[str, str]:
    key = (api_key or os.getenv("ALPACA_API_KEY") or "").strip()
    secret = (secret_key or os.getenv("ALPACA_SECRET_KEY") or "").strip()
    if not key or not secret:
        raise ValueError("alpaca_api_keys_required")
    return {
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
    }


def _normalize_symbols(symbols: list[str]) -> list[str]:
    normalized: list[str] = []
    for symbol in symbols:
        value = str(symbol).strip().upper().replace("/", "")
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def _dateish_to_api_value(value: date | datetime) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return value.isoformat()


def _coerce_date(value: date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _as_float(value: Any) -> float:
    if isinstance(value, bool) or value is None:
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value).strip().replace(",", ""))
    except ValueError:
        return 0.0
