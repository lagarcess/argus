"""What the user was actually offered, projected and asserted.

These cover `tests/evals/measurement_outcome.py`, the projection the
measurement eval uses to decide whether a turn ended somewhere the reader
can act on. They live beside that module rather than in the harness suite
so the two grow independently.
"""

from __future__ import annotations

from tests.evals.measurement_outcome import compare_offered, offered_to_user


class TestOfferedReadsWhatTheUserSaw:
    """Review #522: both offered gates were reading the wrong thing."""

    def test_recovery_options_are_read_as_a_sibling_of_payload(self) -> None:
        # typed_clarification_contract writes options beside payload, not
        # inside it, so the old lookup made recovery_option_ids_include_any
        # impossible to pass. All 60 blocks in the first live run were empty.
        clarification = {
            "kind": "unsupported_recovery",
            "payload": {"raw_value": "options straddle", "strategy": {}},
            "options": [
                {"id": "rsi_threshold"},
                {"id": "buy_and_hold"},
            ],
        }
        offered = offered_to_user(
            final_patch={"clarification": clarification},
            interpret_patch={},
            launch_payload={},
        )
        assert offered["recovery_option_ids"] == ["rsi_threshold", "buy_and_hold"]

    def test_a_reply_that_names_nothing_does_not_pass_names_unavailable(self) -> None:
        # The exact shape that shipped green: the sidecar listed four drops
        # while the reply named none of them.
        discovery = {
            "candidates": [{"symbol": "SOL"}],
            "unverified_names": ["Wiki Cat", "Venice Token", "Bitcoin"],
        }
        silent = offered_to_user(
            final_patch={"discovery": discovery},
            interpret_patch={},
            launch_payload={},
            assistant_text="Here are the trending cryptos I can help you test.",
        )
        assert silent["named_unavailable"] == []
        assert silent["dropped_not_named"] == ["Wiki Cat", "Venice Token", "Bitcoin"]

        naming = offered_to_user(
            final_patch={"discovery": discovery},
            interpret_patch={},
            launch_payload={},
            assistant_text=(
                "Wiki Cat, Venice Token and Bitcoin came back but none could be "
                "confirmed as tradable here."
            ),
        )
        assert naming["named_unavailable"] == ["Wiki Cat", "Venice Token", "Bitcoin"]
        assert naming["dropped_not_named"] == []

    def test_naming_drops_is_owed_only_when_the_turn_offered_nothing(self) -> None:
        """A turn that hands over runnable rows owes no account of its discards.

        Founder-locked 2026-08-19. The dead end this assertion guards is the
        turn that offers nothing at all; beside three tappable rows, a list of
        what was filtered out is noise the reader did not ask for. This is also
        what lets the pipeline keep `TestDropDisclosures`'s silent-filtering
        contract instead of trading one for the other.
        """
        silent_drop = {
            "actionable": True,
            "discovery_symbols": ["SOL", "ETH", "AVAX"],
            "named_unavailable": [],
            "dropped_not_named": ["Bitcoin"],
        }
        failures: list[str] = []
        compare_offered({"names_unavailable": True}, silent_drop, failures)
        assert failures == []

        dead_end = {**silent_drop, "actionable": False, "discovery_symbols": []}
        compare_offered({"names_unavailable": True}, dead_end, failures)
        assert len(failures) == 1
        assert "did not name what it found" in failures[0]
