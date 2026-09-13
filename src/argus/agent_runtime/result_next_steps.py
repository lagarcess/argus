"""One ordered list of next steps after an answer about a result.

The model orders the steps; Argus attaches each runnable test's typed Try next
row and cleans each question. A test step runs exactly as its Try next row
does and a question step sends its text as an ordinary turn. Under the first
result, before any answer exists, the Try next rows alone are the list.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from argus.domain.visible_reply import rewrite_visible_reply

NEXT_STEPS_VERSION = "argus_next_steps/v1"
MAX_NEXT_STEPS = 5
QUESTION_STEP = "question"
_MAX_QUESTION_CHARS = 160


@dataclass(frozen=True)
class NextStep:
    """A runnable test by its Try next kind, or a question by its text."""

    kind: str
    text: str = ""


def accepted_next_steps(
    values: object, *, test_kinds: Sequence[str]
) -> tuple[NextStep, ...]:
    """Offered tests and readable questions, once each, in the model's order."""
    steps: list[NextStep] = []
    seen: set[tuple[str, str]] = set()
    for value in values if isinstance(values, list) else []:
        item = value if isinstance(value, dict) else {}
        kind = str(item.get("kind") or "")
        if kind == QUESTION_STEP:
            step = NextStep(kind=kind, text=visible_question(item.get("text")))
            if not step.text:
                continue
        elif kind in test_kinds:
            step = NextStep(kind=kind)
        else:
            continue
        identity = (step.kind, step.text.casefold())
        if identity in seen:
            continue
        seen.add(identity)
        steps.append(step)
    return tuple(steps[:MAX_NEXT_STEPS])


def visible_question(value: object) -> str:
    """One line of reader text; format characters such as zero-width spaces never ship."""
    text = "".join(
        character
        for character in str(value or "")
        if unicodedata.category(character) != "Cf"
    )
    text = (
        rewrite_visible_reply(" ".join(text.split()), surface="result_followup").text
        or ""
    )
    return text if len(text) <= _MAX_QUESTION_CHARS else ""


def offered_test_steps(rows_sidecar: dict[str, Any] | None) -> tuple[NextStep, ...]:
    return tuple(NextStep(kind=str(row["kind"])) for row in _rows(rows_sidecar))


def next_steps_patch(
    rows_sidecar: dict[str, Any] | None, steps: Sequence[NextStep]
) -> dict[str, Any]:
    """The ordered list, and the typed rows for the tests it names in its order.

    Rows under an answer carry no reason caption; the answer gives the reasons.
    """
    rows = {str(row["kind"]): row for row in _rows(rows_sidecar)}
    listed = [step for step in steps if step.kind == QUESTION_STEP or step.kind in rows]
    if not listed:
        return {}
    patch: dict[str, Any] = {
        "next_steps": {
            "version": NEXT_STEPS_VERSION,
            "items": [
                {"type": "question", "text": step.text}
                if step.kind == QUESTION_STEP
                else {"type": "test", "kind": step.kind}
                for step in listed
            ],
        }
    }
    tested = [
        {key: value for key, value in rows[step.kind].items() if key != "why"}
        for step in listed
        if step.kind != QUESTION_STEP
    ]
    if tested:
        patch["next_experiments"] = {**(rows_sidecar or {}), "rows": tested}
    return patch


def _rows(sidecar: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = sidecar.get("rows") if isinstance(sidecar, dict) else None
    return [row for row in rows or [] if isinstance(row, dict) and row.get("kind")]
