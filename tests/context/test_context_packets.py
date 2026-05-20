from __future__ import annotations

from datetime import date

import pytest
from argus.context import (
    DEFAULT_FRED_CONTEXT_SERIES,
    ContextPacket,
    attach_context_packet_to_run,
    build_alpaca_corporate_actions_packet,
    build_alpaca_market_movers_packet,
    build_alpaca_most_actives_packet,
    build_alpaca_news_packet,
    build_fred_macro_packet,
    fred_context_series_from_env,
)
from argus.context.rendering import context_packet_fact_summary
from pydantic import ValidationError


def test_fred_macro_packet_is_context_only_and_replayable_snapshot() -> None:
    packet = build_fred_macro_packet(
        series_id="FEDFUNDS",
        observation_start=date(2024, 1, 1),
        observation_end=date(2024, 3, 31),
        observations=[
            {"date": "2024-01-01", "value": "5.33"},
            {"date": "2024-02-01", "value": "5.33"},
            {"date": "2024-03-01", "value": "5.25"},
        ],
    )

    assert packet.provider == "fred"
    assert packet.packet_type == "macro"
    assert packet.not_for == "simulation_truth"
    assert packet.coverage_start == date(2024, 1, 1)
    assert packet.facts[0].label == "FEDFUNDS latest observation"
    assert packet.facts[1].kind == "macro_observation_change"

    attachment = attach_context_packet_to_run(packet, run_id="run-1")
    assert attachment.packet_id == packet.id
    assert attachment.immutable_snapshot is True
    with pytest.raises(ValidationError):
        ContextPacket.model_validate(
            {**packet.model_dump(mode="python"), "not_for": "execution_truth"}
        )


def test_default_fred_context_series_prefers_adjusted_macro_context() -> None:
    assert DEFAULT_FRED_CONTEXT_SERIES == (
        "FEDFUNDS",
        "DGS10",
        "DGS2",
        "T10Y2Y",
        "CPIAUCSL",
        "CPILFESL",
        "UNRATE",
        "PAYEMS",
        "INDPRO",
        "USREC",
    )
    assert fred_context_series_from_env(" unrate, cpiaucsl, UNRATE ") == (
        "UNRATE",
        "CPIAUCSL",
    )
    assert fred_context_series_from_env("") == DEFAULT_FRED_CONTEXT_SERIES


def test_alpaca_news_packet_is_symbol_scoped_not_feed() -> None:
    packet = build_alpaca_news_packet(
        symbols=["NVDA"],
        start=date(2024, 5, 1),
        end=date(2024, 5, 31),
        news_items=[
            {
                "id": 123,
                "headline": "Nvidia reports earnings",
                "symbols": ["NVDA"],
                "source": "benzinga",
                "url": "https://example.test/news",
                "updated_at": "2024-05-23T12:00:00Z",
            }
        ],
    )

    assert packet.provider == "alpaca"
    assert packet.packet_type == "news"
    assert packet.scope == {"symbols": ["NVDA"]}
    assert packet.source_ids == ("123",)
    assert "not an executable signal" in packet.limitations[0]


def test_alpaca_corporate_action_packet_preserves_event_facts() -> None:
    packet = build_alpaca_corporate_actions_packet(
        symbols=["AAPL"],
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        corporate_actions=[
            {
                "id": "split-1",
                "symbol": "AAPL",
                "type": "split",
                "ex_date": "2024-06-10",
            }
        ],
    )

    assert packet.packet_type == "corporate_actions"
    assert packet.facts[0].kind == "corporate_action"
    assert packet.facts[0].value["symbol"] == "AAPL"


def test_alpaca_market_movers_packet_is_short_lived_context() -> None:
    packet = build_alpaca_market_movers_packet(
        market_type="stocks",
        movers={
            "gainers": [{"symbol": "TSLA", "percent_change": 5.1}],
            "losers": [{"symbol": "AAPL", "percent_change": -2.1}],
        },
    )

    assert packet.packet_type == "market_movers"
    assert {fact.kind for fact in packet.facts} == {
        "market_mover_gainer",
        "market_mover_loser",
    }
    assert "not a dashboard feed" in packet.limitations[0]


def test_alpaca_most_actives_packet_is_narrow_stocks_context() -> None:
    packet = build_alpaca_most_actives_packet(
        by="volume",
        most_actives=[
            {"symbol": "NVDA", "volume": 123_000_000, "trade_count": 400_000}
        ],
    )

    assert packet.packet_type == "most_actives"
    assert packet.scope == {"market_type": "stocks", "by": "volume"}
    assert packet.facts[0].kind == "most_active_stock"
    assert "not a product feed" in packet.limitations[0]


def test_market_movers_render_only_when_they_match_run_symbols() -> None:
    packet = build_alpaca_market_movers_packet(
        market_type="stocks",
        movers={
            "gainers": [{"symbol": "TSLA", "percent_change": 5.1}],
            "losers": [{"symbol": "AAPL", "percent_change": -2.1}],
        },
    ).storage_payload()

    matching = context_packet_fact_summary([packet], symbols=["TSLA"])
    unrelated = context_packet_fact_summary([packet], symbols=["MSFT"])

    assert "TSLA changed 5.1%" in matching["context_packet_facts"]
    assert "AAPL" not in matching["context_packet_facts"]
    assert "context_packet_facts" not in unrelated


def test_movers_and_most_actives_do_not_render_as_generic_feed_without_symbols() -> None:
    movers = build_alpaca_market_movers_packet(
        market_type="stocks",
        movers={"gainers": [{"symbol": "INM", "percent_change": 135.05}]},
    ).storage_payload()
    actives = build_alpaca_most_actives_packet(
        by="volume",
        most_actives=[{"symbol": "NVDA", "volume": 123_000_000}],
    ).storage_payload()

    summary = context_packet_fact_summary([movers, actives])

    assert "context_packet_facts" not in summary
    assert "context_packet_limitations" in summary
