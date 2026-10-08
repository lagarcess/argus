"""Business chat eval cases: their own fixture set, run on their own surface.

The router reads a turn's surface from its stored conversation; a case names
it as ``surface``. Business cases live in their own fixture set so the
Personal suite's fixture identity and case count stay as measured.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from argus.domain.chat_surface import ChatSurface, turn_surface_scope

from tests.evals.measurement_eval_harness import EvalCase, run_eval_case

BUSINESS_FIXTURE_DIR = Path(__file__).with_name("business_cases")


def case_surface(case: EvalCase) -> ChatSurface:
    surface = case.raw.get("surface", "personal")
    if surface not in ("personal", "business"):
        raise ValueError(f"{case.id}: unknown chat surface {surface!r}")
    return "business" if surface == "business" else "personal"


def run_case_on_its_surface(case: EvalCase, **options: Any) -> dict[str, Any]:
    with turn_surface_scope(case_surface(case)):
        return run_eval_case(case, **options)

