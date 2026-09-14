#!/usr/bin/env python3
"""Write the web test fixture of calculation cards from the real declarations.

Card and fixture data come from the declarations, never hand-written card JSON.
``tests/domain/calculations/test_web_fixture.py`` fails when this file drifts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "web" / "__tests__" / "fixtures" / "calculation-cards.json"
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))


def build_fixture() -> dict[str, object]:
    from argus.domain.computation_marker import computation_from_tool_card

    from tests.domain.calculations import FAILING_ARGUMENTS, WORKED_ARGUMENTS
    from tests.domain.calculations.support import run_calculation

    cards: dict[str, object] = {}
    for name, arguments in WORKED_ARGUMENTS.items():
        card = run_calculation(name, arguments)
        computation = computation_from_tool_card(card)
        cards[name] = {
            "card": card.model_dump(mode="json"),
            "computation": computation.model_dump(mode="json") if computation else None,
        }
    for name, arguments in FAILING_ARGUMENTS.items():
        kind = name.rsplit("_", 1)[0] if name.startswith("time_value") else name
        kind = next(
            declared for declared in WORKED_ARGUMENTS if name.startswith(declared)
        )
        card = run_calculation(kind, arguments)
        computation = computation_from_tool_card(card)
        cards[name] = {
            "card": card.model_dump(mode="json"),
            "computation": computation.model_dump(mode="json") if computation else None,
        }
    return {
        "generated_by": "scripts/dump_calculation_fixtures.py",
        "cards": cards,
        "receipt_turn": _receipt_turn(),
        "comparison": _comparison(),
        "ranked_comparison": _comparison(ranked=True),
    }


# A fixed stamp and identities keep the generated fixture byte-stable.
_STAMP = "2026-09-11T12:00:00+00:00"
_RECEIPT_ARGUMENTS = {
    "currency": "USD",
    "symbol": "AAPL",
    "price": 150,
    "per_share": 6.25,
    "multiple": None,
    "sources": {
        "price": {
            "kind": "page",
            "title": "Apple quote",
            "url": "https://www.nasdaq.com/market-activity/stocks/aapl",
            "date": "2026-09-10",
        }
    },
}


def _receipt_turn() -> dict[str, object]:
    """A calculation receipt turn from the real projector, never hand-written."""
    from datetime import datetime

    from argus.api.schemas import Message
    from argus.domain.computation_marker import computation_from_tool_card
    from argus.domain.public_excerpt_turns import project_calculation_turn

    from tests.domain.calculations.support import run_calculation

    card = run_calculation("price_multiple", _RECEIPT_ARGUMENTS)
    message = Message(
        id="00000000-0000-4000-8000-000000000001",
        conversation_id="00000000-0000-4000-8000-000000000002",
        role="assistant",
        content="Here is that multiple.",
        created_at=datetime.fromisoformat(_STAMP),
        metadata={
            "tool_result_cards": [card.model_dump(mode="json")],
            "computation": computation_from_tool_card(card).model_dump(mode="json"),
        },
    )
    turn = project_calculation_turn(
        message=message,
        question="Is Apple expensive at this P/E?",
        owner_note=None,
        language="en",
        private_ids=(),
    )
    return turn.model_dump(mode="json")


def _comparison(*, ranked: bool = False) -> dict[str, object]:
    """Worked answers through the backend's own differences owner."""
    from dataclasses import asdict
    from datetime import datetime

    from argus.api.computation_contract import (
        ComparedAnswer,
        ComputationComparison,
        ComputationDifference,
    )
    from argus.domain.computation_compare import card_differences

    from tests.domain.calculations import WORKED_ARGUMENTS
    from tests.domain.calculations.support import run_calculation

    base = {key: value for key, value in _RECEIPT_ARGUMENTS.items() if key != "sources"}
    left = run_calculation("price_multiple", {**base, "price": 150})
    right = run_calculation("price_multiple", {**base, "price": 180})
    questions = ("Apple at 150?", "Apple at 180?")
    if ranked:
        base = WORKED_ARGUMENTS["ranked_comparison"]
        items = base["items"][:2]
        left = run_calculation("ranked_comparison", {**base, "items": items})
        right = run_calculation(
            "ranked_comparison",
            {
                **base,
                "items": [
                    {**item, "value": other["value"]}
                    for item, other in zip(items, reversed(items), strict=True)
                ],
            },
        )
        questions = ("Compare annual rates", "Compare the updated annual rates")
    stamp = datetime.fromisoformat(_STAMP)
    comparison = ComputationComparison(
        kind=left.tool_name,
        left=ComparedAnswer(
            conversation_id="c-left",
            message_id="m-left",
            asked=questions[0],
            computed_at=stamp,
            card=left.model_dump(mode="json"),
        ),
        right=ComparedAnswer(
            conversation_id="c-right",
            message_id="m-right",
            asked=questions[1],
            computed_at=stamp,
            card=right.model_dump(mode="json"),
        ),
        differences=[
            ComputationDifference(
                **{
                    **asdict(item),
                    "label": item.label,
                    "unit": item.unit,
                }
            )
            for item in card_differences(left, right)
        ],
    )
    return comparison.model_dump(mode="json")


def render() -> str:
    return (
        json.dumps(build_fixture(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    FIXTURE_PATH.write_text(render(), encoding="utf-8")
    print(f"wrote {FIXTURE_PATH.relative_to(REPO_ROOT)}")
