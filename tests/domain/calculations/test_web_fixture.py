"""The committed web fixture is the declarations' own output, never hand-written."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _script():
    spec = importlib.util.spec_from_file_location(
        "dump_calculation_fixtures",
        REPO_ROOT / "scripts" / "dump_calculation_fixtures.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_committed_calculation_fixture_matches_the_declarations() -> None:
    script = _script()
    committed = script.FIXTURE_PATH.read_text(encoding="utf-8")
    assert committed == script.render(), (
        "web/__tests__/fixtures/calculation-cards.json drifted; "
        "run scripts/dump_calculation_fixtures.py"
    )


def test_fixture_covers_every_free_calculation_and_a_typed_failure() -> None:
    from argus.domain.calculations import (
        get_calculation_declarations,
        is_free_calculation,
    )

    fixture = _script().build_fixture()
    names = {
        declaration.name
        for declaration in get_calculation_declarations()
        if is_free_calculation(declaration)
    }
    assert names <= set(fixture["cards"])
    failing = fixture["cards"]["time_value_payment_below_interest"]["card"]
    assert failing["outcome"]["status"] == "invalid"
    assert failing["outcome"]["failure"]["repair"]["kind"] == "set_inputs"
