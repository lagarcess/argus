"""Free replays of #647 and research replaced by calculation input recovery."""

from __future__ import annotations

from copy import deepcopy

import pytest
from argus.agent_runtime import research_calculation, research_grounded
from argus.agent_runtime.calculated_answer import CalculatedAnswer
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import UserState
from argus.domain.research.contracts import ResearchPacket, ResearchSource, ResearchUsage
from loguru import logger

# Name/value/source pairs copied from the saved Agent calculation in issue #647.
BTC_CALCULATION = {
    "name": "bitcoin_hold",
    "kind": "valuation_scenarios",
    "solve_for": None,
    "inputs": [
        {"name": name, "value": value, "source": source, "currency": currency}
        for name, value, source, currency in (
            ("currency", "USD", "user", None),
            ("symbol", "BTC", "user", None),
            ("price", None, "market_data", "USD"),
            ("per_share", 1, "assumption", "USD"),
            ("growth_low_pct", -100, "assumption", None),
            ("growth_base_pct", 0, "assumption", None),
            ("growth_high_pct", 20, "assumption", None),
            ("multiple_low", None, "assumption", None),
            ("multiple_base", None, "assumption", None),
            ("multiple_high", None, "assumption", None),
            ("horizon_years", 10, "user", None),
            ("amount", 10000, "user", "USD"),
        )
    ],
}
QUESTION = (
    "If I invest $10,000 in Bitcoin and hold it, what will it be worth in ten years?"
)
SOURCE = "https://www.reuters.com/markets/bitcoin-outlook/"
SUBJECTS = [{"symbol": "BTC", "name": "Bitcoin", "asset_class": "crypto"}]


@pytest.fixture
def skip_reasons():
    reasons = []
    sink = logger.add(
        lambda event: reasons.append(event.record["extra"].get("failure_classification"))
    )
    yield reasons
    logger.remove(sink)


@pytest.fixture
def compose(monkeypatch):
    monkeypatch.setattr(
        research_calculation, "latest_market_close", lambda _: (60000, "2026-09-14")
    )
    monkeypatch.setattr(
        research_grounded, "research_next_experiment_rows", lambda **_: None
    )
    # The observed recovery asks for inputs. It must never displace retrieved prose.
    monkeypatch.setattr(
        research_calculation,
        "answer_without_lookup",
        lambda **_: CalculatedAnswer(
            answer_text="What are the starting value, annual rate and number of periods?",
            patch={},
            template=None,
            question_field="start_value",
            pending=None,
        ),
    )

    def run(packet, path, language="en"):
        if path == "background":
            result = research_grounded.compose_completed_research(
                job_request={
                    "question": QUESTION,
                    "question_kind": "current_external",
                    "scenario_question": True,
                    "requires_publisher_sources": True,
                    "subjects": SUBJECTS,
                    "language": language,
                },
                packet=packet,
            )
            assert "question" not in result
            return result["answer"], result["research"], result.get("computed") or {}
        interpretation = StructuredInterpretation(
            intent="unsupported_or_out_of_scope",
            task_relation="new_task",
            user_goal_summary=QUESTION,
            semantic_turn_act="educational_question",
            requires_clarification=False,
        )
        result = research_grounded._packet_stage_result(
            packet=packet,
            subjects=SUBJECTS,
            shape="balanced",
            capability_class="balanced_lookup",
            language=language,
            interpretation=interpretation,
            user=UserState(user_id="regression"),
            cache_status="hit" if path == "cache" else "miss",
            question_kind="current_external",
            scenario=True,
            message=QUESTION,
        )
        assert result.outcome == "ready_to_respond"
        assert "clarification" not in result.stage_patch
        return (
            result.stage_patch["assistant_response"],
            result.stage_patch["research"],
            result.stage_patch,
        )

    return run


def packet(prose, calculations):
    return ResearchPacket(
        answer_markdown=prose,
        calculations=tuple(calculations),
        sources=(ResearchSource(url=SOURCE),),
        usage=ResearchUsage(web_search_invocations=1),
    )


@pytest.mark.parametrize("path", ["inline", "cache", "background"])
@pytest.mark.parametrize("trace_references", [True, False])
def test_issue_647_total_loss_keeps_labeled_scenarios_and_assumptions(
    compose, path, trace_references
):
    # Preserve the recorded aliases too: even if prose cannot resolve them,
    # the actual card must retain all three labeled cases and their assumptions.
    prose = (
        "Your investment’s value after {{horizon_years}} years cannot be known today. "
        "Under the illustrative assumptions below, the calculation shows outcomes "
        "from {{low_value}} to {{high_value}}, with a {{base_value}} base case; "
        "these are scenarios, not forecasts."
        if trace_references
        else "Illustrative scenarios, not forecasts. "
        "Bear: {{value_at_horizon_low}}. Base: {{value_at_horizon_base}}. "
        "Bull: {{value_at_horizon_high}}."
    )
    answer, research, patch = compose(packet(prose, [BTC_CALCULATION]), path)
    card = patch["final_response_payload"]["tool_result_cards"][0]
    assert card["outcome"]["status"] == "succeeded"
    rows = {row["name"]: row["value"] for row in card["presentation"]["rows"]}
    assert rows["value_at_horizon_low"] == 0
    assert rows["value_at_horizon_base"] == 10000
    assert rows["value_at_horizon_high"] == pytest.approx(61917.36)
    assert rows["annual_return_pct_low"] == -100
    if not trace_references:
        assert all(label in answer for label in ("Bear:", "Base:", "Bull:"))
    assert [row["label"] for row in card["outcome"]["result"]["scenarios"]] == [
        "low",
        "base",
        "high",
    ]
    assert "{{" not in answer
    assert card["arguments"]["sources"]["growth_low_pct"]["kind"] == "assumption"
    assert "degraded" not in research


@pytest.mark.parametrize("path", ["inline", "cache", "background"])
@pytest.mark.parametrize("language", ["en", "es-419"])
@pytest.mark.parametrize(
    "failure", ["missing_price", "missing_user", "absent", "malformed", "invalid"]
)
def test_unusable_calculation_never_replaces_retrieved_scenarios(
    compose, monkeypatch, skip_reasons, path, language, failure
):
    prose = (
        "Bear: Bitcoin loses value. Base: it holds its value. Bull: adoption grows. "
        "These are scenarios, not forecasts."
        if language == "en"
        else "Bajista: Bitcoin pierde valor. Base: conserva su valor. Alcista: aumenta su uso. "
        "Son escenarios, no pronósticos."
    ) + f" [Source]({SOURCE})"
    calculation = deepcopy(BTC_CALCULATION)
    calculation["inputs"][4]["value"] = -50
    if failure == "missing_price":
        monkeypatch.setattr(research_calculation, "latest_market_close", lambda _: None)
    elif failure == "missing_user":
        calculation["inputs"][3].update(value=None, source="user")
    elif failure == "malformed":
        calculation["inputs"] = "invalid"
    elif failure == "invalid":
        calculation["inputs"][4]["value"] = -101
    calculations = [] if failure == "absent" else [calculation]
    answer, research, patch = compose(packet(prose, calculations), path, language)
    assert prose in answer
    assert research["sources"][0]["url"] == SOURCE
    assert "degraded" not in research
    assert "final_response_payload" not in patch
    assert "—" not in answer
    assert {
        "missing_price": "calculation_inputs_not_found",
        "missing_user": "calculation_offered",
        "absent": "scenario_inputs_uncited",
        "malformed": "calculation_inputs_not_found",
        "invalid": "research_calculation_invalid",
    }[failure] in skip_reasons


@pytest.mark.parametrize("path", ["inline", "cache", "background"])
@pytest.mark.parametrize("failure", ["missing_user", "invalid"])
def test_unavailable_result_references_do_not_escape_or_trigger_a_question(
    compose, path, skip_reasons, failure
):
    calculation = deepcopy(BTC_CALCULATION)
    if failure == "missing_user":
        calculation["inputs"][3].update(value=None, source="user")
    else:
        calculation["inputs"][4]["value"] = -101
    answer, _, patch = compose(
        packet("Result: {{value_at_horizon_base}}.", [calculation]), path
    )
    assert "{{" not in answer
    assert (
        "calculation_inputs_not_found"
        if failure == "missing_user"
        else "research_calculation_invalid"
    ) in skip_reasons
    assert "couldn't look up every figure this calculation needs" in answer
    assert "final_response_payload" not in patch
