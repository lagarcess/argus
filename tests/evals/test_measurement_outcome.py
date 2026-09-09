"""What the user was actually offered, projected and asserted.

These cover `tests/evals/measurement_outcome.py`, the projection the
measurement eval uses to decide whether a turn ended somewhere the reader
can act on. They live beside that module rather than in the harness suite
so the two grow independently.
"""

from __future__ import annotations

import json

import pytest
from argus.domain.research.contracts import ResearchSource
from argus.domain.tool_contracts import (
    LocalizedText,
    ToolCardPresentation,
    ToolFact,
    ToolInputFact,
    ToolResultCard,
)
from faker import Faker

from tests.evals.measurement_outcome import (
    compare_offered,
    offered_to_user,
    rendered_beside_reply,
)
from tests.evals.test_measurement_registry_observation import _delivered_call

fake = Faker()


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


class TestRenderedBesideReply:
    """Issue #516: the prose judge must see what the reader had on screen."""

    def test_discovery_rows_sources_and_escalation_are_projected(self) -> None:
        discovery = {
            "schema_version": 1,
            "kind": "asset_discovery",
            "relationship": "category",
            "query_summary": "stocks that have recently IPO'ed",
            "retrieved_at": "2026-08-16T14:02:11+00:00",
            "can_request_search": True,
            "sources": [
                {
                    "title": "Recent IPO listings",
                    "domain": "nasdaq.com",
                    "url": "https://nasdaq.com/recent-ipos",
                    "source_date": "2026-08-14",
                },
            ],
            "candidates": [
                {
                    "symbol": "MDLN",
                    "name": "Medline Industries",
                    "asset_class": "equity",
                    "reason_text": "Listed in early August 2026.",
                    "source_indices": [0],
                },
            ],
            "unverified_names": ["Private Holdings LLC"],
        }
        surface = rendered_beside_reply(
            final_patch={"discovery": discovery},
            interpret_patch={},
        )
        assert surface["discovery_rows"] == [
            {
                "symbol": "MDLN",
                "name": "Medline Industries",
                "reason_text": "Listed in early August 2026.",
            }
        ]
        # The reader sees titles and domains, not raw URLs or row indices.
        assert surface["discovery_sources"] == [
            {
                "title": "Recent IPO listings",
                "domain": "nasdaq.com",
                "source_date": "2026-08-14",
            }
        ]
        assert surface["retrieved_at"] == "2026-08-16T14:02:11+00:00"
        assert surface["can_request_search_action"] is True
        # The sidecar's ungated drop list is parsed but never rendered, so
        # showing it to the judge would misstate what the reader had.
        assert "Private Holdings LLC" not in str(surface)

    def test_recovery_options_experiments_and_retry_are_projected(self) -> None:
        surface = rendered_beside_reply(
            final_patch={
                "clarification": {
                    "kind": "unsupported_recovery",
                    "payload": {"raw_value": "golden cross forecast"},
                    "options": [
                        {
                            "id": "option_0",
                            "compatibility_label": (
                                "Test this idea over a historical period"
                            ),
                            "replacement_values": {"requested_field": "date_range"},
                        },
                        {"id": "buy_and_hold"},
                    ],
                },
                "next_experiments": {
                    "rows": [{"kind": "benchmark_compare", "label": "Compare vs SPY"}]
                },
                "recovery": {"code": "discovery_search_failed", "retryable": True},
            },
            interpret_patch={},
        )
        assert surface["recovery_options"] == [
            {"id": "option_0", "label": "Test this idea over a historical period"},
            {"id": "buy_and_hold"},
        ]
        assert surface["next_experiment_rows"] == [
            {"kind": "benchmark_compare", "label": "Compare vs SPY"}
        ]
        assert surface["recovery"] == {
            "code": "discovery_search_failed",
            "retryable": True,
        }

    def test_a_turn_that_rendered_nothing_projects_to_an_empty_surface(self) -> None:
        assert (
            rendered_beside_reply(
                final_patch={"assistant_response": "Plain prose only."},
                interpret_patch={},
            )
            == {}
        )

    def test_final_patch_wins_over_interpret_patch(self) -> None:
        surface = rendered_beside_reply(
            final_patch={"discovery": {"candidates": [{"symbol": "SOL"}]}},
            interpret_patch={"discovery": {"candidates": [{"symbol": "BTC"}]}},
        )
        assert surface["discovery_rows"] == [{"symbol": "SOL"}]

    def test_malformed_payload_shapes_are_ignored(self) -> None:
        surface = rendered_beside_reply(
            final_patch={
                "discovery": {
                    "candidates": ["not-a-dict", {"symbol": ""}],
                    "sources": [None, {"title": ""}],
                },
                "clarification": {"options": ["not-a-dict", {}]},
                "next_experiments": {"rows": [{"reason": "no kind or label"}]},
                "recovery": "not-a-dict",
            },
            interpret_patch={},
        )
        assert surface == {}


class TestRenderedToolCards:
    def test_presentation_preserves_typed_facts_and_omits_execution_internals(self):
        card = _delivered_call(completed=True)["tool_result_cards"][0]
        hidden_argument, hidden_result = fake.uuid4(), fake.uuid4()
        card["arguments"] = {"private_context": hidden_argument}
        card["outcome"]["result"]["provider_metadata"] = hidden_result
        presentation = ToolCardPresentation(
            title=LocalizedText(
                locale_key="test.echo.title", interpolation_args={"value": 0}
            ),
            answer=ToolFact(
                name="value",
                label=LocalizedText(locale_key="test.echo.value"),
                value=0,
                unit=LocalizedText(locale_key="test.echo.currency"),
            ),
            narrative=fake.paragraph(),
            sources=[ResearchSource(url=fake.url(), title=fake.sentence())],
            rows=[
                ToolFact(
                    name="eligible",
                    label=LocalizedText(locale_key="test.echo.eligible"),
                    value=False,
                )
            ],
            inputs=[
                ToolInputFact(
                    name="unknown",
                    label=LocalizedText(locale_key="test.echo.unknown"),
                    value=None,
                    unknown=True,
                )
            ],
            notes=[LocalizedText(locale_key="test.echo.assumptions")],
        )
        card["presentation"] = presentation.model_dump(mode="json")
        ToolResultCard.model_validate(card)

        surface = rendered_beside_reply(
            final_patch={"final_response_payload": {"tool_result_cards": [card]}},
            interpret_patch={},
        )

        assert surface["tool_result_cards"] == [
            {"status": "succeeded", "presentation": presentation.model_dump(mode="json")}
        ]
        encoded = json.dumps(surface)
        for internal in (
            hidden_argument,
            hidden_result,
            card["call_id"],
            card["artifact_id"],
            card["tool_name"],
            "provider_metadata",
            "arguments",
            "outcome",
        ):
            assert internal not in encoded
        # Reader projection does not mutate the separately retained result truth.
        assert card["outcome"]["result"]["provider_metadata"] == hidden_result

    @pytest.mark.parametrize("status", ["invalid", "ambiguous", "bounded", "unavailable"])
    def test_failure_status_remains_visible_without_becoming_an_answer(self, status):
        card = _delivered_call(completed=False)["tool_result_cards"][0]
        card["outcome"] = {
            "status": status,
            "result": None,
            "failure": {"code": "internal_failure_code", "fields": ["private_field"]},
        }
        card["presentation"]["notes"] = [
            LocalizedText(locale_key="test.echo.unavailable").model_dump(mode="json")
        ]
        ToolResultCard.model_validate(card)

        surface = rendered_beside_reply(
            final_patch={"final_response_payload": {"tool_result_cards": [card]}},
            interpret_patch={},
        )

        projected = surface["tool_result_cards"][0]
        assert projected == {"status": status, "presentation": card["presentation"]}
        assert projected["presentation"]["answer"] is None
        assert projected["presentation"]["narrative"] is None
        assert "internal_failure_code" not in str(surface)
        assert "private_field" not in str(surface)

    @pytest.mark.parametrize("status", ["completed", "pending"])
    def test_actual_research_presenter_retains_narrative_sources_or_pending_note(
        self, status
    ):
        from argus.agent_runtime.research_tools import (
            ResearchArguments,
            ResearchToolResult,
            research_card_presentation,
        )
        from argus.domain.tool_contracts import ToolOutcome

        narrative = fake.paragraph() if status == "completed" else None
        sources = (
            (ResearchSource(url=fake.url(), title=fake.sentence()),)
            if status == "completed"
            else ()
        )
        returned = ToolOutcome(
            status="succeeded",
            result=ResearchToolResult(
                status=status, answer=narrative, sources=sources
            ).model_dump(mode="json"),
        )
        presentation = research_card_presentation(
            ResearchArguments(request=fake.sentence()), returned
        )
        card = _delivered_call(completed=False)["tool_result_cards"][0]
        card.update(
            outcome=returned.model_dump(mode="json"),
            presentation=presentation.model_dump(mode="json"),
        )

        surface = rendered_beside_reply(
            final_patch={"final_response_payload": {"tool_result_cards": [card]}},
            interpret_patch={},
        )

        projected = surface["tool_result_cards"][0]
        assert projected == {"status": "succeeded", "presentation": card["presentation"]}
        assert projected["presentation"]["answer"] is None
        assert projected["presentation"]["narrative"] == narrative
        assert projected["presentation"]["sources"] == [
            source.model_dump(mode="json") for source in sources
        ]
        assert bool(projected["presentation"]["notes"]) is (status == "pending")

    @pytest.mark.parametrize("payload", [None, {}, {"tool_result_cards": []}])
    def test_only_final_delivered_cards_are_projected(self, payload):
        evidence = _delivered_call(completed=True)
        surface = rendered_beside_reply(
            final_patch={"final_response_payload": payload, **evidence},
            interpret_patch={"final_response_payload": evidence, **evidence},
        )

        assert surface == {}

    @pytest.mark.parametrize("cards", [None, "malformed", {}, [None, {}, "malformed"]])
    def test_malformed_cards_are_not_promoted_to_reader_evidence(self, cards):
        assert (
            rendered_beside_reply(
                final_patch={"final_response_payload": {"tool_result_cards": cards}},
                interpret_patch={},
            )
            == {}
        )

    def test_a_bounded_card_cannot_smuggle_a_successful_answer_to_the_judge(self):
        card = _delivered_call(completed=True)["tool_result_cards"][0]
        card["outcome"] = {
            "status": "bounded",
            "failure": {"code": "insufficient_evidence"},
        }

        assert (
            rendered_beside_reply(
                final_patch={"final_response_payload": {"tool_result_cards": [card]}},
                interpret_patch={},
            )
            == {}
        )
