"""A result follow-up asking what to try next answers with the latest result's
Try next rows on both follow-up paths, in the workspace language, for every
strategy family; the recovery appears only when no row can be built (#590)."""

from __future__ import annotations

from typing import Any

import pytest
from argus.agent_runtime import result_followup_answers as answers_module
from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.next_experiments import (
    NEXT_EXPERIMENTS_ROW_CAP,
    NEXT_EXPERIMENTS_VERSION,
    next_experiments_lead_in,
)
from argus.agent_runtime.profile.response_profile import (
    resolve_effective_response_profile,
)
from argus.agent_runtime.response_style import result_followup_response_intent
from argus.agent_runtime.result_followup_answers import (
    composed_result_followup_patch,
    next_experiment_followup_patch,
    unavailable_result_followup_patch,
)
from argus.agent_runtime.runtime import run_agent_turn
from argus.agent_runtime.stages import interpret as interpret_module
from argus.agent_runtime.stages import interpret_actions as interpret_actions_module
from argus.agent_runtime.stages.interpret_types import (
    InterpretDecision,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import (
    ArtifactReference,
    StrategySummary,
    TaskSnapshot,
    UserState,
)
from argus.domain.engine_launch.result_facts import structured_next_experiments
from langgraph.checkpoint.memory import MemorySaver

LANGUAGES = ("en", "es-419")
# One completed run per supported family; the rows must come from the family
# that actually ran, never from the oldest shape.
FAMILY_CONFIGS: dict[str, dict[str, Any]] = {
    "buy_and_hold": {"symbols": ["AAPL"], "initial_capital": 1000},
    "dca_accumulation": {
        "symbols": ["COST"],
        "initial_capital": 1000,
        "cadence": "monthly",
        "recurring_contribution": 500,
    },
    "indicator_threshold": {
        "symbols": ["TSLA"],
        "initial_capital": 1000,
        "resolved_parameters": {
            "indicator": "rsi",
            "indicator_period": 14,
            "entry_threshold": 30,
            "exit_threshold": 70,
        },
    },
}
RECOVERY_CODE = "latest_result_followup_unavailable"


def _result_metadata(
    template: str,
    *,
    benchmark_delta: float | None = None,
    max_drawdown: float | None = None,
) -> dict[str, Any]:
    config = dict(FAMILY_CONFIGS[template])
    metadata: dict[str, Any] = {
        "run_id": f"run-590-{template}",
        "asset_class": "equity",
        "symbols": list(config["symbols"]),
        "benchmark_symbol": "SPY",
        "config_snapshot": {
            "template": template,
            "date_range": {"start": "2024-01-02", "end": "2024-12-31"},
            **config,
        },
    }
    performance: dict[str, Any] = {"total_return_pct": 30.7, "benchmark_return_pct": 24.9}
    if benchmark_delta is not None:
        performance["delta_vs_benchmark_pct"] = benchmark_delta
    metadata["metrics"] = {"aggregate": {"performance": performance}}
    if max_drawdown is not None:
        metadata["metrics"]["aggregate"]["risk"] = {"max_drawdown_pct": max_drawdown}
    return metadata


def _snapshot(template: str, **metrics: float | None) -> TaskSnapshot:
    return TaskSnapshot(
        latest_task_type="results_explanation",
        completed=True,
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id=f"run-590-{template}",
            artifact_status="completed",
            metadata=_result_metadata(template, **metrics),
        ),
    )


def _user(language: str) -> UserState:
    return UserState(user_id="u590", language_preference=language)


def _decision(user: UserState, *, focus: str = "next_experiment") -> InterpretDecision:
    return InterpretDecision(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks what to try next from the latest result.",
        candidate_strategy_draft=StrategySummary(),
        confidence=0.9,
        reason_codes=["llm_interpreter_used"],
        effective_response_profile=resolve_effective_response_profile(
            user=user,
            explicit_overrides=None,
        ),
        semantic_turn_act="result_followup",
        result_followup_focus=focus,
        artifact_target="latest_result",
    )


def _forbid_composer(monkeypatch: pytest.MonkeyPatch) -> None:
    """The rows are the answer; a what-next turn never spends a composer call."""

    async def unexpected_composer(**kwargs: Any) -> str | None:
        raise AssertionError(f"composer called for a next_experiment follow-up: {kwargs}")

    monkeypatch.setattr(
        interpret_module, "compose_result_followup_response", unexpected_composer
    )
    monkeypatch.setattr(
        interpret_actions_module, "compose_result_followup_response", unexpected_composer
    )


def _assert_rows_answer(patch: dict[str, Any], *, template: str, language: str) -> None:
    sidecar = patch["next_experiments"]
    assert sidecar["version"] == NEXT_EXPERIMENTS_VERSION
    rows = sidecar["rows"]
    assert 1 <= len(rows) <= NEXT_EXPERIMENTS_ROW_CAP
    supported = {
        option["kind"]
        for option in structured_next_experiments(_result_metadata(template))
    }
    assert {row["kind"] for row in rows} <= supported
    assert patch["assistant_response"] == next_experiments_lead_in(language)
    assert "recovery" not in patch
    # The Try next section is the heading; no result chrome above the lead-in.
    assert "response_intent" not in patch


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("template", sorted(FAMILY_CONFIGS))
def test_next_experiment_patch_offers_the_results_rows_in_the_workspace_language(
    template: str, language: str
) -> None:
    patch = next_experiment_followup_patch(_result_metadata(template), language=language)

    assert patch is not None
    _assert_rows_answer(patch, template=template, language=language)


def test_lead_in_follows_the_workspace_locale_and_carries_no_dash() -> None:
    assert next_experiments_lead_in("es-419") != next_experiments_lead_in("en")
    assert next_experiments_lead_in("es") == next_experiments_lead_in("es-419")
    assert next_experiments_lead_in(None) == next_experiments_lead_in("en")
    for language in LANGUAGES:
        assert "—" not in next_experiments_lead_in(language)


def test_prebaked_row_sends_its_ask_in_the_workspace_language() -> None:
    by_language = {
        language: {
            row["kind"]: row.get("send_text")
            for row in next_experiment_followup_patch(
                _result_metadata("buy_and_hold"), language=language
            )["next_experiments"]["rows"]
        }
        for language in LANGUAGES
    }

    assert by_language["en"]["recurring_monthly_buys"].startswith(
        "Try monthly recurring buys of AAPL"
    )
    assert by_language["es-419"]["recurring_monthly_buys"].startswith(
        "Probar compras mensuales recurrentes de AAPL"
    )


def test_rows_read_the_engine_figures_the_fact_bank_quotes() -> None:
    lost = next_experiment_followup_patch(
        _result_metadata("buy_and_hold", benchmark_delta=-7.5)
    )
    assert lost is not None
    assert lost["next_experiments"]["rows"][0]["why"] == {
        "code": "lost_to_benchmark",
        "params": {"points": 7.5},
    }

    deep = next_experiment_followup_patch(
        _result_metadata("indicator_threshold", benchmark_delta=12.0, max_drawdown=-22.4)
    )
    assert deep is not None
    assert deep["next_experiments"]["rows"][0]["why"] == {
        "code": "deep_drawdown",
        "params": {"drawdown": -22.4},
    }


def test_no_rows_means_no_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(answers_module, "next_experiments_sidecar", lambda *a, **k: None)

    assert next_experiment_followup_patch(_result_metadata("buy_and_hold")) is None


def test_composed_answer_wears_its_heading_and_none_stays_none() -> None:
    assert composed_result_followup_patch(None, focus="general") is None
    assert composed_result_followup_patch("It beat SPY.", focus="general") == {
        "assistant_response": "It beat SPY.",
        "response_intent": result_followup_response_intent("general"),
    }


@pytest.mark.parametrize("language", LANGUAGES)
def test_unavailable_answer_is_the_retryable_recovery_without_chrome(
    language: str,
) -> None:
    patch = unavailable_result_followup_patch(language=language)

    assert patch["recovery"] == {"code": RECOVERY_CODE, "retryable": True}
    assert patch["assistant_response"]
    assert "response_intent" not in patch


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("template", sorted(FAMILY_CONFIGS))
async def test_action_path_answers_what_next_with_rows(
    monkeypatch: pytest.MonkeyPatch, template: str, language: str
) -> None:
    _forbid_composer(monkeypatch)
    user = _user(language)

    result = await interpret_actions_module.artifact_followup_stage_result_if_applicable(
        decision=_decision(user),
        snapshot=_snapshot(template),
        current_user_message="ok what should I try next?",
        language=language,
    )

    assert result is not None
    assert result.outcome == "ready_to_respond"
    _assert_rows_answer(result.patch, template=template, language=language)
    assert result.decision.semantic_turn_act == "result_followup"
    assert result.decision.result_followup_focus == "next_experiment"


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("template", sorted(FAMILY_CONFIGS))
async def test_recovery_path_answers_what_next_with_rows(
    monkeypatch: pytest.MonkeyPatch, template: str, language: str
) -> None:
    _forbid_composer(monkeypatch)
    user = _user(language)

    result = await interpret_module._latest_result_followup_recovery_if_applicable(
        user=user,
        snapshot=_snapshot(template),
        current_user_message="ok what should I try next?",
        decision=_decision(user),
        assistant_response=None,
    )

    assert result is not None
    assert result.outcome == "ready_to_respond"
    _assert_rows_answer(result.patch, template=template, language=language)
    assert result.decision.result_followup_focus == "next_experiment"
    assert "latest_result_empty_turn_recovery" in result.decision.reason_codes


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGUAGES)
async def test_both_paths_recover_only_when_no_row_can_be_built(
    monkeypatch: pytest.MonkeyPatch, language: str
) -> None:
    _forbid_composer(monkeypatch)
    monkeypatch.setattr(answers_module, "next_experiments_sidecar", lambda *a, **k: None)
    user = _user(language)

    action_result = (
        await interpret_actions_module.artifact_followup_stage_result_if_applicable(
            decision=_decision(user),
            snapshot=_snapshot("buy_and_hold"),
            current_user_message="ok what should I try next?",
            language=language,
        )
    )
    recovery_result = (
        await interpret_module._latest_result_followup_recovery_if_applicable(
            user=user,
            snapshot=_snapshot("buy_and_hold"),
            current_user_message="ok what should I try next?",
            decision=_decision(user),
            assistant_response=None,
        )
    )

    for result in (action_result, recovery_result):
        assert result is not None
        assert result.patch["recovery"] == {"code": RECOVERY_CODE, "retryable": True}
        assert "next_experiments" not in result.patch
        # Failure prose never wears result chrome (issue #249).
        assert "response_intent" not in result.patch
        assert result.decision.result_followup_focus == "next_experiment"


class _StaticInterpreter:
    def __init__(self, response: StructuredInterpretation) -> None:
        self.response = response

    def __call__(self, request: Any) -> StructuredInterpretation:
        return self.response


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("language", "message"),
    [
        ("en", "ok what should I try next?"),
        ("es-419", "ok, ¿qué debería probar después?"),
    ],
)
async def test_full_turn_carries_the_rows_for_the_production_repro(
    monkeypatch: pytest.MonkeyPatch, language: str, message: str
) -> None:
    """The #590 repro: a buy-and-hold result explained, then the what-next ask.
    The reference carries only the config snapshot, as the persisted result
    reference does when the follow-up turn is hydrated."""

    _forbid_composer(monkeypatch)
    reference = ArtifactReference(
        artifact_kind="backtest_result",
        artifact_id="eval-run-244-next",
        artifact_status="completed",
        metadata={
            "run_id": "eval-run-244-next",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "benchmark_symbol": "SPY",
            "config_snapshot": {
                "template": "buy_and_hold",
                "symbols": ["AAPL"],
                "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
            },
        },
    )
    workflow = build_workflow(
        structured_interpreter=_StaticInterpreter(
            StructuredInterpretation(
                intent="conversation_followup",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="User asks what to try next.",
                semantic_turn_act="result_followup",
                result_followup_focus="next_experiment",
                artifact_target="latest_result",
                confidence=0.9,
            )
        ),
        checkpointer=MemorySaver(),
    )

    result = await run_agent_turn(
        workflow=workflow,
        user=_user(language),
        thread_id=f"thread-590-{language}",
        message=message,
        recent_thread_history=[
            {
                "role": "user",
                "content": "What if I just bought and held Apple through 2024?",
            },
            {
                "role": "assistant",
                "content": "Here is your completed buy-and-hold result for AAPL over 2024.",
            },
        ],
        fallback_latest_task_snapshot=TaskSnapshot(
            latest_task_type="results_explanation",
            completed=True,
            latest_backtest_result_reference=reference,
        ),
        fallback_selected_thread_metadata={
            "latest_task_type": "results_explanation",
            "last_stage_outcome": "ready_to_respond",
            # The first explanation already offered rows; an explicit ask
            # still gets the result's full offer.
            "next_experiments_offered_kinds": [
                "change_date_range",
                "same_setup_peer_asset",
                "recurring_monthly_buys",
            ],
        },
    )

    rows = result["next_experiments"]["rows"]
    assert len(rows) >= 1
    assert result["assistant_response"] == next_experiments_lead_in(language)
    assert RECOVERY_CODE not in str(result)
    assert "result_followup_chrome" not in str(result)
