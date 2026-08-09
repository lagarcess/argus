"""The model never mints: resolver, class, and coverage gates on every row."""

from __future__ import annotations

from argus.agent_runtime.research_rows import (
    honest_no_next_line,
    research_next_experiment_rows,
    verified_peers,
)
from argus.domain.research.contracts import ResearchNamePair


def _pairs(*symbols: str) -> list[ResearchNamePair]:
    return [ResearchNamePair(name=f"{s} Inc", symbol=s) for s in symbols]


def test_unresolvable_names_never_become_tappable() -> None:
    peers = verified_peers(
        _pairs("NFLX", "TOTALLYFAKE"),
        exclude=set(),
        probe=lambda symbol: symbol == "NFLX",
    )
    assert [p["symbol"] for p in peers] == ["NFLX"]


def test_subjects_and_duplicates_are_excluded() -> None:
    peers = verified_peers(
        _pairs("DIS", "DIS", "NFLX"),
        exclude={"NFLX"},
        probe=lambda symbol: True,
    )
    assert [p["symbol"] for p in peers] == ["DIS"]


def test_resolver_gate_uses_the_real_catalog_in_fixture_mode() -> None:
    # Synthetic fixture catalog: NFLX resolves as equity, a fake ticker never
    # resolves, and BTC resolves but is not equity, so neither becomes a row.
    peers = verified_peers(_pairs("NFLX", "ZZZZFAKE", "BTC"), exclude=set())
    assert [p["symbol"] for p in peers] == ["NFLX"]
    assert peers[0]["asset_class"] == "equity"


def test_versus_row_uses_plain_names_with_tickers() -> None:
    rows = research_next_experiment_rows(
        subjects=[{"symbol": "NFLX", "name": "Netflix", "asset_class": "equity"}],
        peers=[
            {"symbol": "DIS", "name": "Walt Disney", "asset_class": "equity"},
            {"symbol": "CMCSA", "name": "Comcast", "asset_class": "equity"},
        ],
        language="en",
    )
    assert rows is not None
    labels = [row["label"] for row in rows["rows"]]
    assert labels[0] == "Test Netflix (NFLX) over the last 3 years"
    assert labels[1] == ("Test Netflix (NFLX) vs Walt Disney (DIS) and Comcast (CMCSA)")
    # A tap sends a fully specified ask, so nothing needs clarification.
    sends = [row["send_text"] for row in rows["rows"]]
    assert sends[1] == (
        "Test buying and holding NFLX, DIS, CMCSA over the last three years"
    )
    # Rows always carry the parser-required fields.
    for row in rows["rows"]:
        assert row["kind"] and row["label"] and row["label_key"]


def test_spanish_rows_are_native_not_rendered() -> None:
    rows = research_next_experiment_rows(
        subjects=[{"symbol": "NFLX", "name": "Netflix", "asset_class": "equity"}],
        peers=[{"symbol": "DIS", "name": "Walt Disney", "asset_class": "equity"}],
        language="es-419",
    )
    assert rows is not None
    assert rows["rows"][0]["label"] == "Probar Netflix (NFLX) en los últimos 3 años"
    assert rows["rows"][1]["send_text"] == (
        "Prueba comprar y mantener NFLX, DIS durante los últimos tres años"
    )


def test_multi_subject_questions_get_one_versus_row() -> None:
    rows = research_next_experiment_rows(
        subjects=[
            {"symbol": "NFLX", "name": "Netflix", "asset_class": "equity"},
            {"symbol": "AAPL", "name": "Apple", "asset_class": "equity"},
        ],
        peers=[],
        language="en",
    )
    assert rows is not None
    assert len(rows["rows"]) == 1
    assert " vs " in rows["rows"][0]["label"]


def test_no_testable_subject_means_no_rows_and_an_honest_line() -> None:
    rows = research_next_experiment_rows(
        subjects=[
            {"symbol": "EURUSD", "name": "EUR/USD", "asset_class": "currency_pair"}
        ],
        peers=[],
        language="en",
    )
    assert rows is None
    assert "no one-tap test" in honest_no_next_line("en")
    assert "todavía" in honest_no_next_line("es-419")


def test_rows_carry_typed_ticker_parts_and_a_matching_plain_label() -> None:
    """The badge renders from typed parts; the plain label stays the same
    sentence so aria labels and analytics read what the eye reads."""
    rows = research_next_experiment_rows(
        subjects=[
            {
                "symbol": "NFLX",
                "name": "Netflix, Inc. Common Stock",
                "asset_class": "equity",
            }
        ],
        peers=[],
        language="en",
    )
    assert rows is not None
    row = rows["rows"][0]
    assert row["label_parts"] == [
        {"type": "text", "value": "Test "},
        {"type": "text", "value": "Netflix"},
        {"type": "ticker", "value": "NFLX"},
        {"type": "text", "value": " over the last 3 years"},
    ]
    assert row["label"] == "Test Netflix (NFLX) over the last 3 years"
    # The row states the window it actually asks for, in prose and in payload.
    # The sent prompt keeps its spelled-out window; only display copy changed.
    assert "last three years" in row["send_text"]
