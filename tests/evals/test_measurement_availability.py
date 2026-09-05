"""Provider outages are missing measurements, never prose-quality verdicts."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest
from argus.agent_runtime.stages import interpret
from argus.llm import openrouter

from tests.evals import measurement_eval_harness as harness
from tests.evals import measurement_eval_scorecard as scorecards
from tests.evals.measurement_prose import (
    composer_unavailability,
    unavailable_prose_result,
)
from tests.evals.test_measurement_eval_scorecard import _valid_scorecard_provenance


@pytest.fixture
def capability_run(monkeypatch: Any) -> Any:
    """Use the real composer retry and localized recovery, with fake transport."""
    case = next(
        case
        for case in harness.load_eval_cases()
        if case.id == "asset_discovery_not_capability_question_issue_244"
    )
    monkeypatch.setattr(openrouter, "resolve_openrouter_api_key", lambda: "unit-fixture")
    monkeypatch.setattr(
        openrouter,
        "openrouter_model_candidates",
        lambda *_args, **_kwargs: ["fixture/primary", "fixture/fallback"],
    )
    judge = Mock(
        return_value={
            "pass": False,
            "failed_criteria": ["honesty"],
            "notes": "unsupported claim",
            "rubric_version": harness.PROSE_JUDGE_RUBRIC_VERSION,
        }
    )
    monkeypatch.setattr(harness, "judge_prose_quality", judge)

    def run(
        *, language: str = "en", fallback_text: str = "", bad_route: bool = False
    ) -> Any:
        active_case = replace(case, user_language=language, ui_language=language)

        async def post(**kwargs: Any) -> Any:
            if kwargs["payload"]["model"] == "fixture/primary":
                raise TimeoutError("fixture timeout")
            return SimpleNamespace(
                json=lambda: {
                    "choices": [{"message": {"content": fallback_text}}],
                    "usage": {"completion_tokens": 3, "prompt_tokens": 7, "cost": 0.001},
                }
            )

        def interpret_stage(**_kwargs: Any) -> Any:
            text = asyncio.run(
                interpret._capability_answer_if_applicable(
                    focus="general",
                    semantic_turn_act="educational_question",
                    expects_strategy_route=False,
                    requires_clarification=False,
                    assistant_response=None,
                    current_user_message=active_case.prompt,
                    capability_contract=harness.build_default_capability_contract(),
                    language=language,
                )
            )
            return SimpleNamespace(
                outcome="ready_to_respond",
                patch={
                    "intent": "conversation_followup",
                    "semantic_turn_act": "asset_discovery"
                    if bad_route
                    else "educational_question",
                    "assistant_response": text,
                },
            )

        monkeypatch.setattr(openrouter, "_post_openrouter_json_schema", post)
        monkeypatch.setattr(harness, "interpret_stage", interpret_stage)
        return harness.run_eval_case(active_case), judge

    return run


@pytest.mark.parametrize("language", ["en", "es-419"])
def test_timeout_then_empty_fallback_is_unavailable_not_dishonest(
    capability_run: Any, language: str
) -> None:
    result, judge = capability_run(language=language)
    assert result["status"] == "infrastructure_error"
    assert result["failed_checks"] == []
    judge.assert_not_called()
    assert result["prose_judge"]["pass"] is None
    assert result["prose_judge"]["failed_criteria"] == []
    assert "judged_assistant_text" not in result["prose_judge"]
    from argus.agent_runtime.recovery_messages import recovery_message

    assert result["prose_judge"]["observed_assistant_text"]["text"] == recovery_message(
        "capability_answer_unavailable",
        language=language,
    )
    assert [r["failure_mode"] for r in result["route_receipts"]] == [
        "TimeoutError",
        "empty_response",
    ]
    assert result["route_receipts"][-1]["usage_cost_usd"] == 0.001
    assert result["infrastructure_errors"][0]["component"] == "runtime_composer"
    assert harness.blocking_eval_results([result]) == [result]


def test_available_fallback_still_fails_real_honesty_rubric(capability_run: Any) -> None:
    result, judge = capability_run(fallback_text="I can run an options straddle for you.")
    judge.assert_called_once()
    assert result["status"] == "failed"
    assert result["failed_checks"] == ["prose_judge:honesty"]
    assert not result["infrastructure_errors"]


def test_outage_does_not_mask_a_typed_route_failure(capability_run: Any) -> None:
    result, judge = capability_run(bad_route=True)
    assert result["status"] == "failed"
    assert any(
        check.startswith("semantic_turn_act:") for check in result["failed_checks"]
    )
    assert not any(check.startswith("prose_judge:") for check in result["failed_checks"])
    assert result["infrastructure_errors"]
    judge.assert_not_called()


def test_judge_without_structured_result_is_unavailable(monkeypatch: Any) -> None:
    async def no_judge(**_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(harness, "invoke_openrouter_json_schema", no_judge)
    case = next(c for c in harness.load_eval_cases() if c.prose_judge_criteria)
    result = harness.judge_prose_quality(case=case, assistant_text="A composed answer.")
    assert result["pass"] is None
    assert result["failed_criteria"] == []
    assert result["status"] == "unavailable"


@pytest.mark.parametrize("include_quality_result", [False, True])
def test_scorecard_excludes_outages_from_quality_denominator(
    include_quality_result: bool,
) -> None:
    results = [
        {
            "id": "outage",
            "category": "capability_honesty",
            "status": "infrastructure_error",
        }
    ]
    if include_quality_result:
        results.append(
            {"id": "answered", "category": "capability_honesty", "status": "passed"}
        )
    scorecard = scorecards.scorecard_for_results(
        results,
        provenance=_valid_scorecard_provenance(*(r["id"] for r in results)),
    )
    bucket = scorecard["category_pass_rates"]["capability_honesty"]
    assert bucket["infrastructure_error"] == 1
    assert bucket["failed"] == 0
    assert bucket["pass_rate"] == (1.0 if include_quality_result else None)
    assert scorecard["totals"]["infrastructure_error"] == 1


def test_unavailable_judge_cannot_be_an_expected_failure(monkeypatch: Any) -> None:
    case = harness.EvalCase(
        id="judge-outage",
        category="capability_honesty",
        prompt="A capability question",
        user_language="en",
        ui_language="en",
        expected=harness.TypedExpectations(
            intent="conversation_followup", capability_verdict="answer_only"
        ),
        prose_judge_criteria=("honesty",),
        expected_fail=harness.ExpectedFail(
            issue="#365", reason="fixture", allowed_failures=("prose_judge:",)
        ),
    )
    monkeypatch.setattr(
        harness,
        "interpret_stage",
        lambda **_kwargs: SimpleNamespace(
            outcome="ready_to_respond",
            patch={"intent": "conversation_followup", "assistant_response": "An answer."},
        ),
    )
    monkeypatch.setattr(
        harness,
        "judge_prose_quality",
        lambda **_kwargs: unavailable_prose_result("fixture"),
    )
    result = harness.run_eval_case(case)
    assert result["status"] == "infrastructure_error"
    assert result["failed_checks"] == []
    assert result["infrastructure_errors"] == [
        {"component": "prose_judge", "code": "no_structured_result"}
    ]
    assert harness.blocking_eval_results([result]) == [result]


def test_only_runtime_chat_attempts_establish_composer_unavailability() -> None:
    composer = {
        "task": "chat_composer",
        "mode": "chat_model",
        "outcome": "skipped",
        "failure_mode": "missing_api_key",
    }
    assert composer_unavailability([composer])
    assert not composer_unavailability([])
    assert not composer_unavailability([{**composer, "mode": "json_schema"}])
    assert not composer_unavailability([{**composer, "task": "interpret"}])
    assert not composer_unavailability([composer, {**composer, "outcome": "succeeded"}])
