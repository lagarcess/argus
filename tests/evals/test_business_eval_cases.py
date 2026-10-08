"""The Business chat eval cases: valid fixtures, kept apart, and passing offline.

Each case runs through the real harness with a scripted interpreter and no
provider key, so this proves the cases measure the Business gates without
spending a call. The live run measures the model.
"""

from __future__ import annotations

from typing import Any

import pytest
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import StrategySummary

from tests.evals import measurement_eval_harness as harness
from tests.evals.measurement_eval_harness import FIXTURE_DIR, load_eval_cases
from tests.evals.measurement_eval_scorecard import measurement_fixture_case_ids
from tests.evals.measurement_surface import (
    BUSINESS_FIXTURE_DIR,
    case_surface,
    run_case_on_its_surface,
)

BUSINESS_CASES = load_eval_cases(BUSINESS_FIXTURE_DIR)


def test_business_cases_are_bilingual_business_turns_outside_the_personal_set() -> None:
    assert 10 <= len(BUSINESS_CASES) <= 15
    assert {case.category for case in BUSINESS_CASES} == {"business_chat_surface"}
    assert {case_surface(case) for case in BUSINESS_CASES} == {"business"}
    assert all(
        (case.expected.offered or {}).get("personal_reach") == []
        for case in BUSINESS_CASES
    )
    languages = [case.user_language for case in BUSINESS_CASES]
    assert sorted(set(languages)) == ["en", "es-419"]
    assert min(languages.count("en"), languages.count("es-419")) >= 5
    personal = load_eval_cases(FIXTURE_DIR)
    assert {case_surface(case) for case in personal} == {"personal"}
    assert len(measurement_fixture_case_ids(FIXTURE_DIR)) == 73
    assert not {case.id for case in BUSINESS_CASES} & {case.id for case in personal}


def _scripted(case: harness.EvalCase) -> StructuredInterpretation:
    if "backtest_execution" in case.expected.intent:
        return StructuredInterpretation(
            intent="backtest_execution",
            task_relation="new_task",
            requires_clarification=False,
            user_goal_summary=case.prompt,
            candidate_strategy_draft=StrategySummary(
                raw_user_phrasing=case.prompt,
                strategy_type="buy_and_hold",
                asset_universe=["AAPL"],
                asset_class="equity",
                date_range={"start": "2024-01-02", "end": "2024-12-31"},
                capital_amount=5000,
            ),
            semantic_turn_act="new_idea",
        )
    return StructuredInterpretation(
        intent="conversation_followup",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary=case.prompt,
        candidate_strategy_draft=StrategySummary(),
        semantic_turn_act="educational_question",
        assistant_response="Una respuesta."
        if case.user_language != "en"
        else "An answer.",
    )


@pytest.mark.parametrize("case", BUSINESS_CASES, ids=lambda case: case.id)
def test_each_business_case_passes_offline_with_no_personal_reach(
    monkeypatch: pytest.MonkeyPatch, case: harness.EvalCase
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    interpretation = _scripted(case)

    class Interpreter:
        async def ainvoke(self, request: Any) -> StructuredInterpretation:
            del request
            return interpretation.model_copy(deep=True)

    monkeypatch.setattr(
        harness, "OpenRouterStructuredInterpreter", lambda **_kwargs: Interpreter()
    )

    result = run_case_on_its_surface(case, run_prose_judge=False)

    assert result["typed_outcome"]["offered"]["personal_reach"] == []
    assert result["failed_checks"] == []
    assert result["route_receipts"] == []


def test_a_business_case_run_off_its_surface_fails_on_the_personal_tool_it_reaches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    case = next(c for c in BUSINESS_CASES if c.id == "business_chat_backtest_request_en")
    interpretation = _scripted(case)

    class Interpreter:
        async def ainvoke(self, request: Any) -> StructuredInterpretation:
            del request
            return interpretation.model_copy(deep=True)

    monkeypatch.setattr(
        harness, "OpenRouterStructuredInterpreter", lambda **_kwargs: Interpreter()
    )

    leaked = harness.run_eval_case(case, run_prose_judge=False)

    assert leaked["typed_outcome"]["offered"]["personal_reach"] == [
        "backtest_confirmation"
    ]
    assert (
        "offered.personal_reach: expected [], got ['backtest_confirmation']"
        in leaked["failed_checks"]
    )
