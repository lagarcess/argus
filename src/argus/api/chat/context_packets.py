from __future__ import annotations

import os
from concurrent.futures import Future, ThreadPoolExecutor, wait
from datetime import date, datetime
from typing import Any, Callable

from loguru import logger

from argus.api.schemas import BacktestRun
from argus.context import (
    ContextPacket,
    attach_context_packet_to_run,
    fetch_alpaca_corporate_actions_packet,
    fetch_alpaca_market_movers_packet,
    fetch_alpaca_most_actives_packet,
    fetch_alpaca_news_packet,
    fetch_fred_macro_packet,
    fred_context_series_from_env,
)

ContextPacketFetcher = Callable[[], ContextPacket]


def context_packet_collection_enabled() -> bool:
    raw = os.getenv("ARGUS_CONTEXT_PACKETS_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def context_packet_budget_seconds() -> float:
    raw = os.getenv("ARGUS_CONTEXT_PACKET_BUDGET_SECONDS", "4").strip()
    try:
        budget = float(raw)
    except ValueError:
        return 4.0
    return max(0.1, min(budget, 12.0))


def collect_context_packets_for_completed_run(
    run: BacktestRun,
    *,
    fred_series: tuple[str, ...] | None = None,
    budget_seconds: float | None = None,
    fetch_fred_macro_packet_func: Callable[..., ContextPacket] = fetch_fred_macro_packet,
    fetch_alpaca_news_packet_func: Callable[
        ..., ContextPacket
    ] = fetch_alpaca_news_packet,
    fetch_alpaca_corporate_actions_packet_func: Callable[
        ..., ContextPacket
    ] = fetch_alpaca_corporate_actions_packet,
    fetch_alpaca_market_movers_packet_func: Callable[
        ..., ContextPacket
    ] = fetch_alpaca_market_movers_packet,
    fetch_alpaca_most_actives_packet_func: Callable[
        ..., ContextPacket
    ] = fetch_alpaca_most_actives_packet,
) -> list[ContextPacket]:
    if not context_packet_collection_enabled():
        return []
    window = _run_context_window(run)
    if window is None:
        return []
    start, end = window
    tasks: list[tuple[str, ContextPacketFetcher]] = []

    for series_id in fred_series or fred_context_series_from_env():
        tasks.append(
            (
                f"fred:{series_id}",
                lambda series_id=series_id: fetch_fred_macro_packet_func(
                    series_id=series_id,
                    observation_start=start,
                    observation_end=end,
                ),
            )
        )

    if run.asset_class == "equity" and run.symbols:
        symbols = list(run.symbols)
        tasks.extend(
            [
                (
                    "alpaca:news",
                    lambda: fetch_alpaca_news_packet_func(
                        symbols=symbols,
                        start=start,
                        end=end,
                        limit=5,
                    ),
                ),
                (
                    "alpaca:corporate_actions",
                    lambda: fetch_alpaca_corporate_actions_packet_func(
                        symbols=symbols,
                        start=start,
                        end=end,
                    ),
                ),
                (
                    "alpaca:market_movers",
                    lambda: fetch_alpaca_market_movers_packet_func(
                        market_type="stocks",
                        top=5,
                    ),
                ),
                (
                    "alpaca:most_actives",
                    lambda: fetch_alpaca_most_actives_packet_func(
                        by="volume",
                        top=5,
                    ),
                ),
            ]
        )

    return _collect_packets_with_budget(
        tasks,
        budget_seconds=(
            context_packet_budget_seconds()
            if budget_seconds is None
            else max(0.1, budget_seconds)
        ),
    )


def enrich_run_with_context_packets(
    run: BacktestRun,
    packets: list[ContextPacket],
) -> BacktestRun:
    if not packets:
        return run
    card = dict(run.conversation_result_card)
    packet_payloads = [packet.storage_payload() for packet in packets]
    card["context_packets"] = packet_payloads
    card["context_packet_ids"] = [packet["id"] for packet in packet_payloads]
    return run.model_copy(update={"conversation_result_card": card})


def persist_context_packet_records(
    *,
    gateway: Any,
    user_id: str,
    run: BacktestRun,
    packets: list[ContextPacket],
) -> None:
    if not packets:
        return
    for packet in packets:
        gateway.create_context_packet(
            user_id=user_id,
            packet=packet.storage_payload(),
        )
        attachment = attach_context_packet_to_run(packet, run_id=run.id)
        gateway.attach_context_packet_to_run(
            user_id=user_id,
            attachment=attachment.model_dump(mode="json"),
        )


def _collect_packets_with_budget(
    tasks: list[tuple[str, ContextPacketFetcher]],
    *,
    budget_seconds: float,
) -> list[ContextPacket]:
    if not tasks:
        return []
    executor = ThreadPoolExecutor(max_workers=min(len(tasks), 8))
    futures: dict[Future[ContextPacket], str] = {
        executor.submit(fetcher): label for label, fetcher in tasks
    }
    done, pending = wait(futures, timeout=budget_seconds)
    packets: list[ContextPacket] = []
    for future in done:
        label = futures[future]
        try:
            packets.append(future.result())
        except Exception as exc:
            logger.info(
                "Context packet provider skipped",
                provider_task=label,
                error_type=type(exc).__name__,
            )
    for future in pending:
        label = futures[future]
        future.cancel()
        logger.info(
            "Context packet provider exceeded budget",
            provider_task=label,
            budget_seconds=budget_seconds,
        )
    executor.shutdown(wait=False, cancel_futures=True)
    return packets


def _run_context_window(run: BacktestRun) -> tuple[date, date] | None:
    candidates = [
        _date_range_from_mapping(run.config_snapshot),
        _date_range_from_mapping(run.conversation_result_card),
    ]
    for candidate in candidates:
        if candidate is not None:
            return candidate
    return None


def _date_range_from_mapping(value: Any) -> tuple[date, date] | None:
    if not isinstance(value, dict):
        return None
    date_range = value.get("date_range")
    if not isinstance(date_range, dict):
        return None
    start = _coerce_date(date_range.get("start"))
    end = _coerce_date(date_range.get("end"))
    if start is None or end is None or start > end:
        return None
    return start, end


def _coerce_date(value: Any) -> date | None:
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
