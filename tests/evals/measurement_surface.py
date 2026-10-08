"""Business chat eval cases: their own fixture set, run on their own surface.

The router reads a turn's surface from its stored conversation; a case names
it as ``surface``. Business cases live in their own fixture set so the
Personal suite's fixture identity and case count stay as measured.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from argus.domain.chat_surface import ChatSurface, turn_surface_scope

from tests.evals.measurement_eval_harness import EvalCase, run_eval_case
from tests.evals.measurement_eval_scorecard import (
    BUSINESS_FIXTURE_DIR,
    FIXTURE_SETS,
    FixtureSet,
)

__all__ = [
    "BUSINESS_FIXTURE_DIR",
    "case_surface",
    "live_eval_fixture_set",
    "run_case_on_its_surface",
]
FIXTURE_SET_ENV = "ARGUS_EVAL_FIXTURE_SET"


def live_eval_fixture_set(environ: Mapping[str, str]) -> FixtureSet:
    """The fixture set a live run measures: Personal unless the run names one."""
    raw = (environ.get(FIXTURE_SET_ENV) or "personal").strip()
    for name in FIXTURE_SETS:
        if name == raw:
            return name
    raise RuntimeError(f"{FIXTURE_SET_ENV} must be one of {sorted(FIXTURE_SETS)}")


def case_surface(case: EvalCase) -> ChatSurface:
    surface = case.raw.get("surface", "personal")
    if surface not in ("personal", "business"):
        raise ValueError(f"{case.id}: unknown chat surface {surface!r}")
    return "business" if surface == "business" else "personal"


def run_case_on_its_surface(case: EvalCase, **options: Any) -> dict[str, Any]:
    """Run a case in the chat it names; a Personal case runs as before."""
    with turn_surface_scope(case_surface(case)):
        return run_eval_case(case, **options)

