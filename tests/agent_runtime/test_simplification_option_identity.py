"""A value-bearing option kind labels; it never identifies.

The starting-capital kinds carry the amount as their whole point, so kind
equality must not stand in for the option: two different amounts are two
different offers, in selection matching and in the typed-option id/dedup.
"""

from __future__ import annotations

from argus.agent_runtime.clarification_contract import _typed_options
from argus.agent_runtime.simplification_option_contract import (
    simplification_option_identity,
    simplification_option_kind,
    simplification_option_matches_selection,
)


class TestValueBearingKindsNeverIdentify:
    def test_different_amounts_are_different_options(self) -> None:
        assert not simplification_option_matches_selection(
            option_replacement_values={"initial_capital": 5000},
            selected_replacement_values={"initial_capital": 50000},
        )

    def test_equal_amounts_still_match(self) -> None:
        assert simplification_option_matches_selection(
            option_replacement_values={"initial_capital": 5000},
            selected_replacement_values={"initial_capital": 5000},
        )

    def test_value_free_kinds_still_short_circuit(self) -> None:
        assert simplification_option_matches_selection(
            option_replacement_values={"simplify_logic": "rsi_only"},
            selected_replacement_values={"entry_rule": {"type": "rsi_threshold"}},
        )

    def test_identity_is_none_for_value_bearing_kinds(self) -> None:
        for values in (
            {"initial_capital": 5000},
            {"strategy_type": "buy_and_hold", "initial_capital": 5000},
        ):
            assert simplification_option_kind(values) is not None
            assert simplification_option_identity(values) is None

    def test_two_starting_capital_options_both_survive_typed_options(self) -> None:
        options = _typed_options(
            {
                "options": [
                    {
                        "label": "Use $5,000 as starting capital",
                        "replacement_values": {"initial_capital": 5000},
                    },
                    {
                        "label": "Use $50,000 as starting capital",
                        "replacement_values": {"initial_capital": 50000},
                    },
                ],
            }
        )
        amounts = sorted(
            option["replacement_values"]["initial_capital"] for option in options
        )
        assert amounts == [5000, 50000]
        ids = [option["id"] for option in options]
        assert len(set(ids)) == 2
