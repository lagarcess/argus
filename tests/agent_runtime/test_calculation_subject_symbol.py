"""A calculation that names no symbol borrows the answer's subject only when the
answer names exactly one."""

from __future__ import annotations

from argus.agent_runtime.research_calculation import _only_symbol


def test_a_card_borrows_the_answers_subject_only_when_there_is_exactly_one() -> None:
    assert _only_symbol([{"symbol": "AAPL", "name": "Apple"}]) == "AAPL"
    assert _only_symbol([{"symbol": "AAPL"}, {"symbol": "AAPL"}]) == "AAPL"
    assert _only_symbol([{"symbol": "AAPL"}, {"symbol": "MSFT"}]) is None
    assert _only_symbol([]) is None
