"""Reachability proof includes planner admission and downstream normalization."""

from __future__ import annotations

import pytest

from tests.agent_runtime._pending_edit_outcome_support import card_for_edit_plan


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["en", "es-419"])
@pytest.mark.parametrize(
    ("plan", "recurring", "target"),
    [
        (
            {
                "outcome": "needs_clarification",
                "assistant_response": "More detail needed.",
                "missing_required_fields": ["assumption"],
            },
            False,
            "requested_change",
        ),
        ({"initial_capital": 10000}, False, "requested_change"),
        ({"timeframe": "1D"}, False, "requested_change"),
        (
            {"asset_universe": [], "asset_universe_operation": "replace"},
            False,
            "asset",
        ),
        (
            {"operations": [{"op": "add", "target": "asset", "symbols": []}]},
            False,
            "requested_change",
        ),
        ({"initial_capital": 9000, "fee_rate": 0.9}, False, "fees"),
        ({"cadence": "never"}, True, "cadence"),
        ({"comparison_baseline": " "}, False, "benchmark"),
        ({"timeframe": "bad-frame"}, False, "timeframe"),
        ({"timeframe": ""}, False, "timeframe"),
        (
            {"operations": [{"op": "set", "target": "timeframe", "value": "bad-frame"}]},
            False,
            "timeframe",
        ),
    ],
    ids=[
        "clarification-reconfirm",
        "copied-capital",
        "copied-timeframe",
        "empty-replacement",
        "empty-add",
        "partial-flat",
        "invalid-cadence",
        "blank-benchmark",
        "invalid-timeframe",
        "empty-timeframe",
        "invalid-typed-timeframe",
    ],
)
async def test_every_reachable_silent_card_path_discloses(
    monkeypatch, language, plan, recurring, target
):
    outcome, card = await card_for_edit_plan(
        monkeypatch,
        {"outcome": "ready_to_confirm", **plan},
        language=language,
        recurring=recurring,
    )
    assert outcome == "await_approval"
    assert card["kind"] == "backtest"
    assert target in {entry["target"] for entry in card["edit_disclosure"]["unapplied"]}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("plan", "outcome"),
    [
        ({"outcome": "ready_to_confirm"}, "planner_declined"),
        (
            {"outcome": "unsupported", "assistant_response": "Unsupported change."},
            "needs_clarification",
        ),
        ({"outcome": "ready_to_confirm", "initial_capital": -10}, "needs_clarification"),
        (
            {
                "outcome": "ready_to_confirm",
                "operations": [{"op": "clear", "target": "benchmark"}],
            },
            "needs_clarification",
        ),
    ],
)
async def test_existing_rejections_do_not_reissue_a_card(monkeypatch, plan, outcome):
    actual, card = await card_for_edit_plan(monkeypatch, plan)
    assert actual == outcome
    assert card is None
