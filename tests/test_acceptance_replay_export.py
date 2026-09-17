"""Exercise the historical exporter's metadata expression without DB or replay I/O."""
from __future__ import annotations

import ast
from pathlib import Path
from types import CodeType
from typing import Any

import pytest

EXPORTER = (
    Path(__file__).resolve().parents[1]
    / "docs/reports/evidence/2026-09-17-final-acceptance-e8a4ccee"
    / "drivers/export_replay.py"
)


@pytest.fixture(scope="module")
def failure_metadata_expression() -> CodeType:
    # Importing this historical driver would connect to a database and read
    # private replay files. Compile only its pure metadata projection instead.
    tree = ast.parse(EXPORTER.read_text())
    projection = next(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Name)
            and target.value.id == "r"
            and isinstance(target.slice, ast.Constant)
            and target.slice.value == "stored_failure_metadata"
            for target in node.targets
        )
    )
    return compile(ast.Expression(projection), str(EXPORTER), "eval")


@pytest.mark.parametrize(
    ("clarification", "expected"),
    [
        pytest.param(
            {"reason_code": "unsupported_time_granularity", "payload": {}},
            "unsupported_time_granularity",
            id="top-level-reason-survives",
        ),
        pytest.param(
            {
                "reason_code": "unsupported_time_granularity",
                "payload": {"reason_code": "stale_nested_reason"},
            },
            "unsupported_time_granularity",
            id="top-level-owner-wins",
        ),
        pytest.param(
            {"payload": {"reason_code": "stale_nested_reason"}},
            None,
            id="missing-owner-does-not-borrow-nested-reason",
        ),
        pytest.param(None, None, id="no-clarification"),
    ],
)
def test_export_uses_top_level_clarification_reason(
    failure_metadata_expression: CodeType,
    clarification: dict[str, Any] | None,
    expected: str | None,
) -> None:
    exported = eval(
        failure_metadata_expression,
        {"__builtins__": {}},
        {"meta": {"clarification": clarification}, "turn_keys": []},
    )

    assert exported["clarification_reason"] == expected
    assert exported["stage_outcome"] is None
    assert exported["research_degraded_code"] is None
    assert exported["recovery_code"] is None
