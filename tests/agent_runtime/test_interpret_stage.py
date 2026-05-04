from dataclasses import dataclass

from argus.agent_runtime.signals.task_relation import extract_signals
from argus.agent_runtime.stages.interpret import (
    ArbitrationDecision,
    StructuredInterpretation,
    interpret_stage,
)
from argus.agent_runtime.state.models import (
    RunState,
    StrategySummary,
    TaskSnapshot,
    UserState,
)


@dataclass(frozen=True)
class ResolvedAssetStub:
    canonical_symbol: str
    asset_class: str
    name: str = ""
    raw_symbol: str = ""


def test_interpret_answers_beginner_help_without_generic_opener() -> None:
    user = UserState(user_id="u1", expertise_level="beginner")
    state = RunState.new(
        current_user_message="I don't know anything about finance, can you help me test an idea?",
        recent_thread_history=[],
    )

    result = interpret_stage(state=state, user=user, latest_task_snapshot=None)

    assert result.outcome == "ready_to_respond"
    assert result.decision.intent == "conversation_followup"
    assert result.decision.task_relation == "continue"
    assert result.decision.requires_clarification is False
    assert "one idea or market question" not in result.patch["assistant_response"].lower()
    assert "beginner_language_detected" in result.decision.reason_codes
    assert result.decision.missing_required_fields == []


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
    assert result.decision.field_status == {
        "strategy_thesis": "resolved",
        "asset_universe": "resolved",
        "entry_logic": "missing",
        "exit_logic": "missing",
        "date_range": "missing",
    }
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


def test_interpret_uses_extraction_sell_synonym_for_exit_logic() -> None:
    user = UserState(user_id="u1", expertise_level="advanced")
    state = RunState.new(
        current_user_message=(
            "Backtest Tesla over the last 2 years, buy when RSI drops below 30, "
            "sell when RSI is above 55."
        ),
        recent_thread_history=[],
    )

    result = interpret_stage(state=state, user=user, latest_task_snapshot=None)

    assert result.outcome == "ready_for_confirmation"
    assert result.decision.missing_required_fields == []
    assert result.decision.candidate_strategy_draft.entry_logic == "RSI drops below 30"
    assert result.decision.candidate_strategy_draft.exit_logic == "RSI rises above 55"
    assert result.decision.field_status["exit_logic"] == "resolved"


def test_interpret_requires_clarification_for_unsupported_constraints() -> None:
    user = UserState(user_id="u1", expertise_level="advanced")
    state = RunState.new(
        current_user_message=(
            "Backtest Tesla at market open over the last 2 years, enter when RSI "
            "drops below 30, exit when RSI rises above 55."
        ),
        recent_thread_history=[],
    )

    result = interpret_stage(state=state, user=user, latest_task_snapshot=None)

    assert result.outcome == "needs_clarification"
    assert result.decision.intent == "backtest_execution"
    assert result.decision.task_relation == "new_task"
    assert result.decision.requires_clarification is True
    assert result.decision.missing_required_fields == []
    assert result.decision.reason_codes.count("unsupported_time_granularity") == 1
    assert result.decision.unsupported_constraints[0].category == (
        "unsupported_time_granularity"
    )
    assert result.patch["unsupported_constraints"][0]["category"] == (
        "unsupported_time_granularity"
    )


def test_interpret_product_question_returns_conversational_response_not_opener() -> None:
    user = UserState(user_id="u1", expertise_level="beginner")
    state = RunState.new(
        current_user_message="what can you do?",
        recent_thread_history=[],
    )

    result = interpret_stage(state=state, user=user, latest_task_snapshot=None)

    assert result.outcome == "ready_to_respond"
    assert result.patch["assistant_response"]
    assert "one idea or market question" not in result.patch["assistant_response"].lower()
    assert result.decision.intent == "conversation_followup"


def test_interpret_symbol_only_llm_response_offers_starting_paths() -> None:
    user = UserState(user_id="u1", expertise_level="beginner")
    state = RunState.new(current_user_message="tesla", recent_thread_history=[])

    def fake_interpreter(_request: object) -> StructuredInterpretation:
        return StructuredInterpretation(
            intent="strategy_drafting",
            task_relation="new_task",
            requires_clarification=False,
            user_goal_summary="User mentioned Tesla.",
            candidate_strategy_draft=StrategySummary(
                raw_user_phrasing="tesla",
                strategy_thesis="Explore Tesla.",
                asset_universe=["TSLA"],
                asset_class="equity",
            ),
            assistant_response="Tesla (TSLA)",
        )

    result = interpret_stage(
        state=state,
        user=user,
        latest_task_snapshot=None,
        structured_interpreter=fake_interpreter,
    )

    assert result.outcome == "ready_to_respond"
    assert "I can work with TSLA" in result.patch["assistant_response"]
    assert "Buy and hold TSLA" in result.patch["assistant_response"]
    assert "Tesla (TSLA)" not in result.patch["assistant_response"]


def test_interpret_strategy_draft_ignores_bare_llm_echo() -> None:
    user = UserState(user_id="u1", expertise_level="advanced")
    state = RunState.new(
        current_user_message=(
            "Buy Nvidia when its 50-day moving average crosses above the 200-day"
        ),
        recent_thread_history=[],
    )

    def fake_interpreter(_request: object) -> StructuredInterpretation:
        return StructuredInterpretation(
            intent="backtest_execution",
            task_relation="new_task",
            requires_clarification=False,
            user_goal_summary="Buy Nvidia on a 50/200 moving-average crossover.",
            candidate_strategy_draft=StrategySummary(
                raw_user_phrasing=(
                    "Buy Nvidia when its 50-day moving average crosses above the 200-day"
                ),
                strategy_type="indicator_threshold",
                strategy_thesis="Buy Nvidia on a 50/200 moving-average crossover.",
                asset_universe=["NVDA"],
                asset_class="equity",
                entry_logic="50-day moving average crosses above the 200-day moving average",
            ),
            assistant_response="Buy NVDA when 50-day SMA crosses above 200-day SMA",
        )

    result = interpret_stage(
        state=state,
        user=user,
        latest_task_snapshot=None,
        structured_interpreter=fake_interpreter,
    )

    assert result.outcome == "needs_clarification"
    assert "assistant_response" not in result.patch
    assert result.decision.candidate_strategy_draft.entry_logic == (
        "50-day moving average crosses above the 200-day moving average"
    )
    assert result.decision.missing_required_fields == ["exit_logic", "date_range"]


def test_interpret_short_strategy_fragment_from_llm_becomes_clarification() -> None:
    user = UserState(user_id="u1", expertise_level="beginner")
    state = RunState.new(
        current_user_message="What if I bought Apple on significant dips?",
        recent_thread_history=[],
    )

    def fake_interpreter(_request: object) -> StructuredInterpretation:
        return StructuredInterpretation(
            intent="strategy_drafting",
            task_relation="new_task",
            requires_clarification=False,
            user_goal_summary="Explore buying Apple on significant dips.",
            candidate_strategy_draft=StrategySummary(
                raw_user_phrasing="What if I bought Apple on significant dips?",
                strategy_thesis="Buy Apple on significant dips.",
                asset_universe=["AAPL"],
                asset_class="equity",
            ),
            assistant_response="Significant dips",
        )

    result = interpret_stage(
        state=state,
        user=user,
        latest_task_snapshot=None,
        structured_interpreter=fake_interpreter,
    )

    assert result.outcome == "needs_clarification"
    assert "assistant_response" not in result.patch
    assert result.decision.ambiguous_fields[0].raw_value == "significant dips"


def test_interpret_executable_llm_strategy_ignores_fragment_assistant_response() -> None:
    user = UserState(user_id="u1", expertise_level="advanced")
    state = RunState.new(
        current_user_message=(
            "let's try a basic buy and hold on BTC from jan first last year to date"
        ),
        recent_thread_history=[],
    )

    def fake_interpreter(_request: object) -> StructuredInterpretation:
        return StructuredInterpretation(
            intent="strategy_drafting",
            task_relation="new_task",
            requires_clarification=False,
            user_goal_summary="Buy and hold BTC.",
            candidate_strategy_draft=StrategySummary(
                raw_user_phrasing=(
                    "let's try a basic buy and hold on BTC from jan first last year to date"
                ),
                strategy_type="buy_and_hold",
                strategy_thesis="Simple buy-and-hold on Bitcoin",
                asset_universe=["BTC"],
                asset_class="crypto",
                date_range={"start": "2025-01-01", "end": "today"},
            ),
            assistant_response="buying on last year",
        )

    result = interpret_stage(
        state=state,
        user=user,
        latest_task_snapshot=None,
        structured_interpreter=fake_interpreter,
    )

    assert result.outcome == "ready_for_confirmation"
    assert "assistant_response" not in result.patch
    assert result.decision.missing_required_fields == []


def test_interpret_buy_and_hold_is_complete_without_entry_or_exit_logic(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    user = UserState(user_id="u1", expertise_level="advanced")
    state = RunState.new(
        current_user_message="Buy and hold Tesla over the last 2 years.",
        recent_thread_history=[],
    )

    result = interpret_stage(state=state, user=user, latest_task_snapshot=None)

    assert result.outcome == "ready_for_confirmation"
    assert result.decision.missing_required_fields == []
    assert result.decision.candidate_strategy_draft.strategy_type == "buy_and_hold"
    assert result.decision.candidate_strategy_draft.asset_universe == ["TSLA"]
    assert result.decision.candidate_strategy_draft.entry_logic is None
    assert result.decision.candidate_strategy_draft.exit_logic is None


def test_interpret_buy_and_hold_accepts_natural_january_last_year_period(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )
    user = UserState(user_id="u1", expertise_level="advanced")
    state = RunState.new(
        current_user_message=(
            "let's try a basic buy and hold on BTC from jan first last year to date"
        ),
        recent_thread_history=[],
    )

    result = interpret_stage(
        state=state,
        user=user,
        latest_task_snapshot=None,
        structured_interpreter=lambda _request: None,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.asset_universe == ["BTC"]
    assert strategy.date_range == {"start": "2025-01-01", "end": "today"}
    assert strategy.entry_logic is None
    assert strategy.exit_logic is None


def test_interpret_buy_and_hold_accepts_explicit_month_name_period(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    user = UserState(user_id="u1", expertise_level="advanced")
    state = RunState.new(
        current_user_message="Buy and hold Apple from Jan 1 2010 to Dec 31 2020.",
        recent_thread_history=[],
    )

    result = interpret_stage(
        state=state,
        user=user,
        latest_task_snapshot=None,
        structured_interpreter=lambda _request: None,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.date_range == {"start": "2010-01-01", "end": "2020-12-31"}
    assert strategy.entry_logic is None
    assert strategy.exit_logic is None


def test_interpret_followup_cadence_refines_pending_dca_strategy(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )
    user = UserState(user_id="u1", expertise_level="advanced")
    state = RunState.new(
        current_user_message="Actually make that weekly instead.",
        recent_thread_history=[
            {"role": "user", "content": "Invest $500 in Bitcoin every month since 2021."},
            {"role": "assistant", "content": "Please confirm this DCA backtest."},
        ],
    )
    snapshot = TaskSnapshot(
        latest_task_type="backtest_execution",
        completed=False,
        pending_strategy_summary=StrategySummary(
            raw_user_phrasing="Invest $500 in Bitcoin every month since 2021.",
            strategy_type="dca_accumulation",
            strategy_thesis="Invest $500 in Bitcoin every month since 2021.",
            asset_universe=["BTC"],
            date_range="since 2021",
            cadence="monthly",
            capital_amount=500,
        ),
    )

    result = interpret_stage(state=state, user=user, latest_task_snapshot=snapshot)

    assert result.outcome == "ready_for_confirmation"
    assert result.decision.task_relation == "refine"
    assert result.decision.candidate_strategy_draft.asset_universe == ["BTC"]
    assert result.decision.candidate_strategy_draft.strategy_type == "dca_accumulation"
    assert result.decision.candidate_strategy_draft.cadence == "weekly"
    assert result.decision.candidate_strategy_draft.capital_amount == 500


def test_interpret_date_followup_refines_pending_dca_to_confirmation(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )
    user = UserState(user_id="u1", expertise_level="advanced")
    state = RunState.new(
        current_user_message="Use May 4 2023 to May 3 2026",
        recent_thread_history=[
            {"role": "user", "content": "Invest $500 in Bitcoin every month since 2021."},
            {
                "role": "assistant",
                "content": "That range is too long. Choose a shorter date range.",
            },
        ],
    )
    snapshot = TaskSnapshot(
        latest_task_type="backtest_execution",
        completed=False,
        pending_strategy_summary=StrategySummary(
            raw_user_phrasing="Invest $500 in Bitcoin every month since 2021.",
            strategy_type="dca_accumulation",
            strategy_thesis="Invest $500 in Bitcoin every month since 2021.",
            asset_universe=["BTC"],
            asset_class="crypto",
            date_range="since 2021",
            cadence="monthly",
            capital_amount=500,
        ),
    )

    result = interpret_stage(
        state=state,
        user=user,
        latest_task_snapshot=snapshot,
        structured_interpreter=lambda _request: None,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.date_range == {"start": "2023-05-04", "end": "2026-05-03"}
    assert strategy.capital_amount == 500
    assert "assistant_response" not in result.patch


def test_interpret_run_backtest_action_approves_pending_strategy() -> None:
    user = UserState(user_id="u1", expertise_level="advanced")
    state = RunState.new(
        current_user_message="Run backtest",
        recent_thread_history=[
            {"role": "user", "content": "Buy and hold Tesla over the past year."},
            {"role": "assistant", "content": "I read this as TSLA buy and hold."},
        ],
    )
    snapshot = TaskSnapshot(
        latest_task_type="backtest_execution",
        completed=False,
        pending_strategy_summary=StrategySummary(
            raw_user_phrasing="Buy and hold Tesla over the past year.",
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Tesla over the past year.",
            asset_universe=["TSLA"],
            date_range="past year",
        ),
    )

    result = interpret_stage(state=state, user=user, latest_task_snapshot=snapshot)

    assert result.outcome == "approved_for_execution"
    assert result.patch["confirmation_payload"]["strategy"]["asset_universe"] == ["TSLA"]


def test_interpret_run_backtest_action_approves_semantically_executable_strategy_alias() -> None:
    user = UserState(user_id="u1", expertise_level="advanced")
    state = RunState.new(
        current_user_message="Run backtest",
        recent_thread_history=[
            {"role": "user", "content": "What if I bought Apple on significant dips?"},
            {"role": "assistant", "content": "I read this as AAPL dip buying."},
        ],
    )
    snapshot = TaskSnapshot(
        latest_task_type="backtest_execution",
        completed=False,
        pending_strategy_summary=StrategySummary(
            raw_user_phrasing="What if I bought Apple on significant dips?",
            strategy_type="dip_buying",
            strategy_thesis="Buy Apple on RSI-defined dips.",
            asset_universe=["AAPL"],
            date_range="year_to_date",
            entry_logic="Buy when RSI <= 30",
            exit_logic="Sell when RSI >= 55",
        ),
    )

    result = interpret_stage(state=state, user=user, latest_task_snapshot=snapshot)

    assert result.outcome == "approved_for_execution"
    assert result.patch["confirmation_payload"]["strategy"]["strategy_type"] == "dip_buying"


def test_interpret_run_backtest_action_does_not_approve_incomplete_pending_draft() -> None:
    user = UserState(user_id="u1", expertise_level="advanced")
    state = RunState.new(
        current_user_message="Run backtest",
        recent_thread_history=[
            {"role": "user", "content": "Backtest the RSI preset"},
            {"role": "assistant", "content": "Which asset should I use?"},
        ],
    )
    snapshot = TaskSnapshot(
        latest_task_type="strategy_drafting",
        completed=False,
        pending_strategy_summary=StrategySummary(
            strategy_type="indicator_threshold",
            strategy_thesis="Backtest the RSI preset",
        ),
    )

    result = interpret_stage(state=state, user=user, latest_task_snapshot=snapshot)

    assert result.outcome != "approved_for_execution"


def test_interpret_confirmation_action_chips_ask_natural_followups() -> None:
    user = UserState(user_id="u1", expertise_level="advanced")
    snapshot = TaskSnapshot(
        latest_task_type="backtest_execution",
        completed=False,
        pending_strategy_summary=StrategySummary(
            raw_user_phrasing="Backtest GOOGL RSI over the past year.",
            strategy_type="rsi_threshold",
            strategy_thesis="Backtest GOOGL RSI over the past year.",
            asset_universe=["GOOGL"],
            date_range="past year",
            entry_logic="RSI drops below 30",
            exit_logic="RSI rises above 55",
        ),
    )

    cases = {
        "Change the date range": ("date_range", "What time period should I test instead?"),
        "Use a different asset": ("asset_universe", "Which asset should I use instead?"),
        "Change the assumptions": (None, "Which assumption do you want to change"),
    }

    for message, (requested_field, expected_prompt) in cases.items():
        state = RunState.new(
            current_user_message=message,
            recent_thread_history=[
                {"role": "user", "content": "Backtest GOOGL RSI over the past year."},
                {"role": "assistant", "content": "I read this as GOOGL RSI."},
            ],
        )

        result = interpret_stage(state=state, user=user, latest_task_snapshot=snapshot)

        assert result.outcome == "await_user_reply"
        assert result.patch["requested_field"] == requested_field
        assert expected_prompt in result.patch["assistant_prompt"]
        assert result.patch["candidate_strategy_draft"]["asset_universe"] == ["GOOGL"]


def test_interpret_mixed_asset_request_preserves_intent_with_simplification(monkeypatch) -> None:
    from argus.agent_runtime.extraction import structured as extraction_module
    from argus.agent_runtime.stages import interpret as interpret_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        asset_class = "crypto" if symbol.upper() == "BTC" else "equity"
        return ResolvedAssetStub(symbol.upper(), asset_class)

    monkeypatch.setattr(extraction_module, "resolve_asset", resolve_stub)
    monkeypatch.setattr(interpret_module, "resolve_asset", resolve_stub)
    user = UserState(user_id="u1", expertise_level="advanced")
    state = RunState.new(
        current_user_message="Backtest Tesla and Bitcoin together.",
        recent_thread_history=[],
    )

    result = interpret_stage(state=state, user=user, latest_task_snapshot=None)

    assert result.outcome == "needs_clarification"
    assert result.decision.candidate_strategy_draft.asset_universe == ["TSLA", "BTC"]
    assert result.decision.unsupported_constraints
    assert result.decision.unsupported_constraints[0].category == "unsupported_asset_mix"
    assert "split" in result.patch["unsupported_constraints"][0]["simplification_options"][2]["label"].lower()
