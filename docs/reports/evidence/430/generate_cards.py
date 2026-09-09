"""Regenerate controlled backend cards: poetry run python <this file>."""

import asyncio
import json
from pathlib import Path

from loguru import logger
from pytest import MonkeyPatch

from tests.agent_runtime._pending_edit_outcome_support import card_for_edit_plan


def preserve_verified_identity(card, previous):
    """Keep receipt ids only after verifying every regenerated fact agrees."""
    if previous is None:
        return card
    generated_id = card["confirmation_id"]
    retained_id = previous["confirmation_id"]

    def retain(value):
        if isinstance(value, dict):
            return {key: retain(item) for key, item in value.items()}
        if isinstance(value, list):
            return [retain(item) for item in value]
        return retained_id if value == generated_id else value

    retained = retain(card)
    assert retained == previous, "Existing scenario facts changed; review before replacing evidence"
    return retained


async def main():
    output_path = Path(__file__).with_name("cards.json")
    previous = json.loads(output_path.read_text()) if output_path.exists() else {}
    cards = {}
    scenarios = (
        ("no_change", {"initial_capital": 10000}, False),
        (
            "refused",
            {"operations": [{"op": "remove", "target": "asset", "symbols": ["TSLA"]}]},
            False,
        ),
        ("applied", {"initial_capital": 9000}, False),
        ("dca_no_change", {"initial_capital": 10000}, True),
        (
            "dca_applied",
            {"operations": [{"op": "set", "target": "recurring_contribution", "number": 650}]},
            True,
        ),
        (
            "asset_replace_append_conflict",
            {
                "operations": [{"op": "replace", "target": "asset", "symbols": ["MSFT"]}],
                "asset_universe": ["MSFT"],
                "asset_universe_operation": "append",
            },
            False,
        ),
        (
            "asset_add_append_equivalent",
            {
                "operations": [{"op": "add", "target": "asset", "symbols": ["MSFT"]}],
                "asset_universe": ["MSFT"],
                "asset_universe_operation": "append",
            },
            False,
        ),
    )
    for language in ("en", "es-419"):
        cards[language] = {}
        for name, plan, recurring in scenarios:
            with MonkeyPatch.context() as patch:
                patch.setenv("ARGUS_IN_PLACE_CARD_EDITS_ENABLED", "true")
                patch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
                outcome, card = await card_for_edit_plan(
                    patch, {"outcome": "ready_to_confirm", **plan},
                    language=language, recurring=recurring,
                )
            assert outcome == "await_approval", (name, outcome)
            assert card["kind"] == "backtest"
            if recurring:
                assert card["display_facts"]["starting_capital"] == 10000
            cards[language][name] = preserve_verified_identity(
                card, previous.get(language, {}).get(name)
            )
    output_path.write_text(
        json.dumps(cards, indent=2, ensure_ascii=False) + "\n"
    )


if __name__ == "__main__":
    logger.remove()
    asyncio.run(main())
