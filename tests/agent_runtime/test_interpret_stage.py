from argus.agent_runtime.signals.task_relation import extract_signals
from argus.agent_runtime.stages.interpret import ArbitrationDecision, interpret_stage
from argus.agent_runtime.state.models import RunState, TaskSnapshot, UserState


def test_interpret_marks_beginner_guidance_for_novice_prompt() -> None:
    user = UserState(user_id="u1", expertise_level="beginner")
    state = RunState.new(
        current_user_message="I don't know anything about finance, can you help me test an idea?",
        recent_thread_history=[],
    )

    result = interpret_stage(state=state, user=user, latest_task_snapshot=None)

    assert result.outcome == "needs_clarification"
    assert result.decision.intent == "beginner_guidance"
    assert result.decision.task_relation == "new_task"
    assert result.decision.requires_clarification is True
    assert "beginner_language_detected" in result.decision.reason_codes
    assert result.decision.missing_required_fields == [
        "strategy_thesis",
        "asset_universe",
        "entry_logic",
        "exit_logic",
        "date_range",
    ]


def test_interpret_marks_new_task_when_symbols_change_after_completed_run() -> None:
    user = UserState(user_id="u1", expertise_level="advanced")
    state = RunState.new(
        current_user_message="Now backtest Tesla instead",
        recent_thread_history=[
            {"role": "user", "content": "Backtest Apple over the last 2 years"},
            {"role": "assistant", "content": "Your Apple backtest is ready."},
        ],
    )
    snapshot = TaskSnapshot(
        latest_task_type="backtest_execution",
        completed=True,
        confirmed_strategy_summary={"asset_universe": ["AAPL"]},
    )

    result = interpret_stage(state=state, user=user, latest_task_snapshot=snapshot)

    assert result.outcome == "needs_clarification"
    assert result.decision.task_relation == "new_task"
    assert result.decision.intent == "backtest_execution"
    assert result.decision.candidate_strategy_draft.asset_universe == ["TSLA"]
    assert "symbols_changed" in result.decision.reason_codes


def test_interpret_treats_under_specified_backtest_as_drafting_not_ambiguous() -> None:
    user = UserState(user_id="u1", expertise_level="advanced")
    state = RunState.new(
        current_user_message="Backtest Tesla",
        recent_thread_history=[],
    )

    result = interpret_stage(state=state, user=user, latest_task_snapshot=None)

    assert result.outcome == "needs_clarification"
    assert result.decision.intent == "strategy_drafting"
    assert result.decision.task_relation == "new_task"
    assert result.decision.requires_clarification is True
    assert result.decision.missing_required_fields == [
        "entry_logic",
        "exit_logic",
        "date_range",
    ]
    assert "request_is_under_specified" in result.decision.reason_codes


def test_interpret_applies_turn_level_response_profile_overrides() -> None:
    user = UserState(
        user_id="u1",
        preferred_tone="concise",
        expertise_level="advanced",
        response_verbosity="low",
    )
    state = RunState.new(
        current_user_message="Explain it like I'm 5 and walk me through each step in detail.",
        recent_thread_history=[],
    )

    result = interpret_stage(state=state, user=user, latest_task_snapshot=None)

    assert result.decision.effective_response_profile.effective_expertise_mode == (
        "beginner"
    )
    assert result.decision.effective_response_profile.effective_verbosity == "high"
    assert result.decision.user_preference_overridden_for_turn is True


def test_interpret_uses_structured_arbitration_for_gray_case() -> None:
    user = UserState(user_id="u1", expertise_level="advanced")
    state = RunState.new(
        current_user_message="Should we continue this or start over?",
        recent_thread_history=[],
    )

    result = interpret_stage(state=state, user=user, latest_task_snapshot=None)

    assert result.outcome == "needs_clarification"
    assert result.decision.task_relation == "ambiguous"
    assert result.decision.intent == "conversation_followup"
    assert result.decision.arbitration_mode == "structured_arbitration"
    assert "structured_arbitration_used" in result.decision.reason_codes
    assert "gray_case_detected" in result.decision.reason_codes


def test_interpret_uses_injected_structured_arbitrator_for_gray_case() -> None:
    user = UserState(user_id="u1", expertise_level="advanced")
    state = RunState.new(
        current_user_message="Should we continue this or start over?",
        recent_thread_history=[],
    )

    def fake_arbitrator(_request: object) -> ArbitrationDecision:
        return ArbitrationDecision(
            intent="strategy_drafting",
            task_relation="refine",
            confidence=0.61,
            reason_codes=["fake_structured_decision"],
        )

    result = interpret_stage(
        state=state,
        user=user,
        latest_task_snapshot=None,
        structured_arbitrator=fake_arbitrator,
    )

    assert result.outcome == "needs_clarification"
    assert result.decision.intent == "strategy_drafting"
    assert result.decision.task_relation == "refine"
    assert result.decision.confidence == 0.61
    assert result.decision.arbitration_mode == "structured_arbitration"
    assert "fake_structured_decision" in result.decision.reason_codes


def test_interpret_keeps_gray_case_ambiguous_when_structured_arbitrator_unresolved() -> None:
    user = UserState(user_id="u1", expertise_level="advanced")
    state = RunState.new(
        current_user_message="Should we continue this or start over?",
        recent_thread_history=[],
    )

    result = interpret_stage(
        state=state,
        user=user,
        latest_task_snapshot=None,
        structured_arbitrator=lambda _request: None,
    )

    assert result.outcome == "needs_clarification"
    assert result.decision.intent == "conversation_followup"
    assert result.decision.task_relation == "ambiguous"
    assert result.decision.requires_clarification is True
    assert result.decision.arbitration_mode == "structured_arbitration"
    assert "structured_arbitration_unresolved" in result.decision.reason_codes


def test_interpret_applies_tone_override_before_user_preference() -> None:
    user = UserState(
        user_id="u1",
        preferred_tone="friendly",
        expertise_level="advanced",
        response_verbosity="medium",
    )
    state = RunState.new(
        current_user_message="Be concise and explain it like I'm 5.",
        recent_thread_history=[],
    )

    result = interpret_stage(state=state, user=user, latest_task_snapshot=None)

    assert result.decision.effective_response_profile.effective_tone == "concise"
    assert result.decision.effective_response_profile.effective_expertise_mode == (
        "beginner"
    )
    assert result.decision.user_preference_overridden_for_turn is True


def test_extract_signals_captures_overrides_and_gray_case() -> None:
    signals = extract_signals(
        message="Be concise and explain it like I'm 5. Should we continue this or start over?",
        latest_task_snapshot=None,
    )

    assert signals.continuation_request_detected is True
    assert signals.explicit_new_request is True
    assert signals.gray_case_detected is True
    assert signals.response_profile_overrides.tone == "concise"
    assert signals.response_profile_overrides.expertise_mode == "beginner"


def test_interpret_followup_does_not_force_execution_missing_fields() -> None:
    user = UserState(user_id="u1", expertise_level="advanced")
    state = RunState.new(
        current_user_message="Why did it do that?",
        recent_thread_history=[],
    )

    result = interpret_stage(state=state, user=user, latest_task_snapshot=None)

    assert result.decision.intent == "conversation_followup"
    assert result.decision.task_relation == "continue"
    assert result.decision.missing_required_fields == []
    assert result.decision.requires_clarification is False


def test_interpret_marks_fully_specified_backtest_ready_for_confirmation() -> None:
    user = UserState(user_id="u1", expertise_level="advanced")
    state = RunState.new(
        current_user_message=(
            "Backtest Tesla over the last 2 years, enter when RSI drops below 30, "
            "exit when RSI rises above 55."
        ),
        recent_thread_history=[],
    )

    result = interpret_stage(state=state, user=user, latest_task_snapshot=None)

    assert result.outcome == "ready_for_confirmation"
    assert result.decision.intent == "backtest_execution"
    assert result.decision.task_relation == "new_task"
    assert result.decision.requires_clarification is False
    assert (
        result.decision.user_goal_summary
        == "User is ready to confirm a new backtest with the supplied strategy details."
    )
    assert result.decision.missing_required_fields == []
    assert result.decision.candidate_strategy_draft.asset_universe == ["TSLA"]
    assert result.decision.candidate_strategy_draft.date_range == "last 2 years"
    assert result.decision.candidate_strategy_draft.entry_logic == "RSI drops below 30"
    assert result.decision.candidate_strategy_draft.exit_logic == "RSI rises above 55"
