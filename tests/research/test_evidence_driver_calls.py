"""Retained probe drivers still build their requests with today's signature.

The drivers under docs/reports/evidence re-record provider behavior when a
retrieval text or configuration changes. A signature change that strands one
breaks the next re-recording before any request is sent, so every call is bound
against the function's own declaration rather than a list of expected keywords.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
from argus.domain.research.config import retrieval_spec

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "reports" / "evidence"


def _retrieval_spec_calls() -> list[tuple[Path, ast.Call]]:
    calls: list[tuple[Path, ast.Call]] = []
    for path in sorted(EVIDENCE.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "retrieval_spec(" not in source:
            continue
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Call) and (
                getattr(node.func, "id", None) == "retrieval_spec"
                or getattr(node.func, "attr", None) == "retrieval_spec"
            ):
                calls.append((path, node))
    return calls


CALLS = _retrieval_spec_calls()


def test_the_sweep_reaches_the_retained_drivers() -> None:
    assert {path.relative_to(EVIDENCE).parts[0] for path, _ in CALLS} >= {
        "545",
        "decision-10",
        "open-the-gates",
    }


@pytest.mark.parametrize(
    ("path", "call"),
    CALLS,
    ids=[f"{path.relative_to(EVIDENCE)}:{call.lineno}" for path, call in CALLS],
)
def test_every_driver_call_binds_to_the_current_signature(
    path: Path, call: ast.Call
) -> None:
    keywords = {keyword.arg: None for keyword in call.keywords if keyword.arg}
    inspect.signature(retrieval_spec).bind(*[None] * len(call.args), **keywords)
