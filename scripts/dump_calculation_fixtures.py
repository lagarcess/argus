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
    return {"generated_by": "scripts/dump_calculation_fixtures.py", "cards": cards}


def render() -> str:
    return (
        json.dumps(build_fixture(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    FIXTURE_PATH.write_text(render(), encoding="utf-8")
    print(f"wrote {FIXTURE_PATH.relative_to(REPO_ROOT)}")
