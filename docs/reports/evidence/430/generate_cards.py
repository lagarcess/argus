"""Regenerate controlled backend cards: poetry run python <this file>."""

import asyncio
import json
from pathlib import Path

from loguru import logger
from pytest import MonkeyPatch

from tests.agent_runtime._pending_edit_outcome_support import card_for_edit_plan


async def main():
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
    )
    for language in ("en", "es-419"):
        cards[language] = {}
        for name, plan, recurring in scenarios:
            with MonkeyPatch.context() as patch:
                outcome, card = await card_for_edit_plan(
                    patch, {"outcome": "ready_to_confirm", **plan},
                    language=language, recurring=recurring,
                )
            assert outcome == "await_approval", (name, outcome)
            assert card["kind"] == "backtest"
            if recurring:
                assert card["display_facts"]["starting_capital"] == 10000
            cards[language][name] = card
    Path(__file__).with_name("cards.json").write_text(
        json.dumps(cards, indent=2, ensure_ascii=False) + "\n"
    )


if __name__ == "__main__":
    logger.remove()
    asyncio.run(main())
