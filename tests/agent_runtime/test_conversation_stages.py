from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.stages.clarify import clarify_stage
from argus.agent_runtime.stages.confirm import confirm_stage
from argus.agent_runtime.stages.interpret import interpret_stage
from argus.agent_runtime.stages.next_step import next_step_stage
from argus.agent_runtime.state.models import RunState, StrategySummary, UserState


def test_clarify_asks_only_for_first_missing_required_field() -> None:
    state = RunState.new(current_user_message="Backtest Tesla", recent_thread_history=[])
    state.intent = "backtest_execution"
    state.missing_required_fields = ["entry_logic", "exit_logic", "date_range"]
    contract = build_default_capability_contract()

    result = clarify_stage(state=state, contract=contract)

    assert result.outcome == "await_user_reply"
    assert result.patch["requested_field"] == "entry_logic"
    assert "trigger the buy" in result.patch["assistant_prompt"].lower()
    assert "exit logic" not in result.patch["assistant_prompt"].lower()
    assert "date range" not in result.patch["assistant_prompt"].lower()


def test_interpret_and_clarify_preserve_under_specified_thesis_handoff() -> None:
    user = UserState(user_id="u1", expertise_level="advanced")
    state = RunState.new(current_user_message="Backtest Tesla", recent_thread_history=[])

    interpreted = interpret_stage(state=state, user=user, latest_task_snapshot=None)
    interpreted_state = RunState.new(
        current_user_message=state.current_user_message,
        recent_thread_history=[],
    )
    interpreted_state.intent = interpreted.patch["intent"]
    interpreted_state.task_relation = interpreted.patch["task_relation"]
    interpreted_state.missing_required_fields = interpreted.patch["missing_required_fields"]
    interpreted_state.optional_parameter_status = interpreted.patch["optional_parameter_status"]
    interpreted_state.candidate_strategy_draft = interpreted.patch["candidate_strategy_draft"]

    clarified = clarify_stage(
        state=interpreted_state,
        contract=build_default_capability_contract(),
    )

    assert interpreted.patch["candidate_strategy_draft"]["strategy_thesis"] == "Backtest Tesla"
    assert interpreted.patch["missing_required_fields"] == [
        "entry_logic",
        "exit_logic",
        "date_range",
    ]
    assert clarified.outcome == "await_user_reply"
    assert clarified.patch["requested_field"] == "entry_logic"
    assert "investing idea" not in clarified.patch["assistant_prompt"].lower()


def test_clarify_uses_beginner_guidance_when_no_required_field_is_selected() -> None:
    state = RunState.new(
        current_user_message="I am new to this. Can you help?",
        recent_thread_history=[],
    )
    state.intent = "beginner_guidance"

    result = clarify_stage(state=state, contract=build_default_capability_contract())

    assert result.outcome == "await_user_reply"
    assert result.patch["requested_field"] is None
    assert "starting point" in result.patch["assistant_prompt"].lower()


def test_clarify_groups_multiple_ambiguous_fields() -> None:
    state = RunState.new(current_user_message="test", recent_thread_history=[])
    state.requires_clarification = True
    state.optional_parameter_status = {
        "ambiguous_fields": [
            {
                "field_name": "entry_logic",
                "raw_value": "buy if RSI is kind of weak",
                "candidate_normalized_value": "enter when RSI drops below 30",
                "reason_code": "semantic_category_shift",
            },
            {
                "field_name": "exit_logic",
                "raw_value": "sell if RSI is not above 70",
                "candidate_normalized_value": "exit when RSI rises above 70",
                "reason_code": "negation_or_conditional_reversal",
            },
        ]
    }

    result = clarify_stage(state=state, contract=build_default_capability_contract())

    assert result.outcome == "await_user_reply"
    assert result.patch["ambiguous_fields"][0]["field_name"] == "entry_logic"
    assert result.patch["ambiguous_fields"][1]["field_name"] == "exit_logic"
    assert "interpreted it as" in result.patch["assistant_prompt"].lower()


def test_clarify_entry_logic_ambiguity_asks_for_rule_not_none_mapping() -> None:
    state = RunState.new(
        current_user_message="What if I bought Apple on significant dips?",
        recent_thread_history=[],
    )
    state.requires_clarification = True
    state.optional_parameter_status = {
        "ambiguous_fields": [
            {
                "field_name": "entry_logic",
                "raw_value": "significant dips",
                "candidate_normalized_value": None,
                "reason_code": "entry_rule_needs_definition",
            }
        ]
    }

    result = clarify_stage(state=state, contract=build_default_capability_contract())

    assert result.outcome == "await_user_reply"
    assert "buying on significant dips" in result.patch["assistant_prompt"]
    assert "interpreted it as 'None'" not in result.patch["assistant_prompt"]
    assert "percent drop" in result.patch["assistant_prompt"]


def test_clarify_surfaces_simplification_options_for_unsupported_constraints() -> None:
    state = RunState.new(current_user_message="test", recent_thread_history=[])
    state.requires_clarification = True
    state.optional_parameter_status = {
        "unsupported_constraints": [
            {
                "category": "unsupported_time_granularity",
                "raw_value": "market open",
                "explanation": "Market-open execution timing is not supported.",
                "simplification_options": [
                    {
                        "label": "Retry with daily bars",
                        "replacement_values": {"timeframe": "1D"},
                    }
                ],
            }
        ]
    }

    result = clarify_stage(state=state, contract=build_default_capability_contract())

    assert result.outcome == "await_user_reply"
    assert result.patch["simplification_options"][0]["label"] == "Retry with daily bars"
    assert "not supported" in result.patch["assistant_prompt"].lower()
    assert "I can Retry with daily bars" in result.patch["assistant_prompt"]
    assert "Which direction should I take?" in result.patch["assistant_prompt"]


def test_clarify_offers_optional_parameters_as_bounded_opt_in() -> None:
    state = RunState.new(current_user_message="Use defaults unless I change them", recent_thread_history=[])
    state.intent = "strategy_drafting"
    state.task_relation = "new_task"
    state.optional_parameter_status = {
        "optional_parameter_opportunity": [
            "initial_capital",
            "timeframe",
            "fees",
            "slippage",
        ],
        "user_preference_overridden_for_turn": False,
        "confidence": 0.84,
        "arbitration_mode": "deterministic",
    }

    result = clarify_stage(state=state, contract=build_default_capability_contract())

    assert result.outcome == "await_user_reply"
    assert result.patch["requested_field"] is None
    assert result.patch["optional_parameter_choices"] == [
        "initial_capital",
        "timeframe",
        "fees",
    ]
    assert "optional settings" in result.patch["assistant_prompt"].lower()
    assert "Initial capital" in result.patch["assistant_prompt"]
    assert "Timeframe" in result.patch["assistant_prompt"]
    assert "Starting cash for the simulated backtest." in result.patch["assistant_prompt"]
    assert "slippage" not in result.patch["assistant_prompt"].lower()
    assert "initial_capital" not in result.patch["assistant_prompt"]


def test_clarify_ambiguous_turn_disambiguates_before_optional_opt_in() -> None:
    state = RunState.new(
        current_user_message="Should we keep going or start over?",
        recent_thread_history=[],
    )
    state.intent = "conversation_followup"
    state.task_relation = "ambiguous"
    state.user_goal_summary = "User intent needs clarification."
    state.optional_parameter_status = {
        "optional_parameter_opportunity": [
            "initial_capital",
            "timeframe",
            "fees",
        ],
        "user_preference_overridden_for_turn": False,
        "confidence": 0.35,
        "arbitration_mode": "structured_arbitration",
    }

    result = clarify_stage(state=state, contract=build_default_capability_contract())

    assert result.outcome == "await_user_reply"
    assert result.patch["requested_field"] is None
    assert "current idea" in result.patch["assistant_prompt"].lower()
    assert "optional settings" not in result.patch["assistant_prompt"].lower()
    assert "optional_parameter_choices" not in result.patch


def test_clarify_uses_distinct_prompt_for_ambiguous_non_beginner_turns() -> None:
    state = RunState.new(
        current_user_message="Should we keep going or start over?",
        recent_thread_history=[],
    )
    state.intent = "conversation_followup"
    state.task_relation = "ambiguous"
    state.user_goal_summary = "User intent needs clarification."

    result = clarify_stage(state=state, contract=build_default_capability_contract())

    assert result.outcome == "await_user_reply"
    assert result.patch["requested_field"] is None
    assert "current idea" in result.patch["assistant_prompt"].lower()
    assert "new backtest" in result.patch["assistant_prompt"].lower()
    assert "one idea or market question" not in result.patch["assistant_prompt"].lower()
    assert "user intent needs clarification" not in result.patch["assistant_prompt"].lower()


def test_clarify_beginner_guidance_stays_in_idea_shaping_before_optional_opt_in() -> None:
    state = RunState.new(
        current_user_message="I am new to this. Can you help?",
        recent_thread_history=[],
    )
    state.intent = "beginner_guidance"
    state.task_relation = "new_task"
    state.optional_parameter_status = {
        "optional_parameter_opportunity": [
            "initial_capital",
            "timeframe",
            "fees",
        ],
        "user_preference_overridden_for_turn": True,
        "confidence": 0.92,
        "arbitration_mode": "deterministic",
    }

    result = clarify_stage(state=state, contract=build_default_capability_contract())

    assert result.outcome == "await_user_reply"
    assert result.patch["requested_field"] is None
    assert "starting point" in result.patch["assistant_prompt"].lower()
    assert "optional settings" not in result.patch["assistant_prompt"].lower()
    assert "optional_parameter_choices" not in result.patch


def test_clarify_non_beginner_ready_turn_does_not_ask_unrelated_question() -> None:
    state = RunState.new(
        current_user_message="Backtest Tesla with the strategy we already defined.",
        recent_thread_history=[],
    )
    state.intent = "backtest_execution"
    state.task_relation = "new_task"
    state.missing_required_fields = []
    state.optional_parameter_status = {
        "optional_parameter_opportunity": [],
        "user_preference_overridden_for_turn": False,
        "confidence": 0.9,
        "arbitration_mode": "deterministic",
    }

    result = clarify_stage(state=state, contract=build_default_capability_contract())

    assert result.outcome == "ready_for_confirmation"
    assert result.patch["requested_field"] is None
    assert result.patch["assistant_prompt"] is None


def test_confirm_stage_includes_defaults_for_undisclosed_optional_fields() -> None:
    state = RunState.new(current_user_message="run it", recent_thread_history=[])
    state.intent = "backtest_execution"
    state.candidate_strategy_draft = StrategySummary(
        strategy_thesis="Buy Tesla on pullbacks",
        asset_universe=["TSLA"],
        entry_logic="RSI below 30",
        exit_logic="RSI above 55",
        date_range="2024-01-01 to 2025-01-01",
    )
    contract = build_default_capability_contract()

    result = confirm_stage(state=state, contract=contract)

    assert result.outcome == "await_approval"
    assert (
        result.patch["confirmation_payload"]["optional_parameters"]["initial_capital"]["value"]
        == 10000.0
    )
    assert (
        result.patch["confirmation_payload"]["optional_parameters"]["initial_capital"]["source"]
        == "default"
    )
    assert (
        result.patch["confirmation_payload"]["optional_parameters"]["initial_capital"]["label"]
        == "Initial capital"
    )
    assert "I read this as an indicator threshold backtest for TSLA" in result.patch["assistant_prompt"]
    assert "buy when RSI below 30" in result.patch["assistant_prompt"]
    assert "exit when RSI above 55" in result.patch["assistant_prompt"]
    assert "$10,000 starting capital" in result.patch["assistant_prompt"]
    assert "no trading fees" in result.patch["assistant_prompt"]
    assert "initial_capital=" not in result.patch["assistant_prompt"]


def test_confirm_stage_formats_structured_date_range_in_prompt() -> None:
    state = RunState.new(current_user_message="run it", recent_thread_history=[])
    state.intent = "backtest_execution"
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Bitcoin from January 1 last year.",
        asset_universe=["BTC"],
        date_range={"start": "2025-01-01", "end": "today"},
    )

    result = confirm_stage(state=state, contract=build_default_capability_contract())

    assert result.outcome == "await_approval"
    assert "{'start'" not in result.patch["assistant_prompt"]
    assert "January 1, 2025" in result.patch["assistant_prompt"]


def test_confirm_stage_blocks_ranges_longer_than_engine_limit() -> None:
    state = RunState.new(current_user_message="run it", recent_thread_history=[])
    state.intent = "backtest_execution"
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple from 2010 to 2020.",
        asset_universe=["AAPL"],
        date_range={"start": "2010-01-01", "end": "2020-12-31"},
    )

    result = confirm_stage(state=state, contract=build_default_capability_contract())

    assert result.outcome == "await_user_reply"
    assert result.patch["requested_field"] == "date_range"
    assert "longer than the current backtest engine can run" in result.patch["assistant_prompt"]
    assert "up to 3 years" in result.patch["assistant_prompt"]
    assert "January 1, 2010" not in result.patch["assistant_prompt"]


def test_confirm_stage_blocks_since_ipo_without_past_year_fallback() -> None:
    state = RunState.new(current_user_message="take META since IPO", recent_thread_history=[])
    state.intent = "backtest_execution"
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="indicator_threshold",
        strategy_thesis="Backtest META RSI since IPO.",
        asset_universe=["META"],
        entry_logic="RSI below 30",
        exit_logic="RSI above 60",
        date_range="since_ipo",
    )

    result = confirm_stage(state=state, contract=build_default_capability_contract())

    assert result.outcome == "await_user_reply"
    assert result.patch["requested_field"] == "date_range"
    assert "Since IPO is longer" in result.patch["assistant_prompt"]
    assert "past year" not in result.patch["assistant_prompt"]


def test_confirm_stage_formats_dca_contribution_as_recurring_money() -> None:
    state = RunState.new(current_user_message="run it", recent_thread_history=[])
    state.intent = "backtest_execution"
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="dca_accumulation",
        strategy_thesis="Invest $500 in Bitcoin every month.",
        asset_universe=["BTC"],
        cadence="monthly",
        capital_amount=500.0,
        date_range={"start": "2024-05-03", "end": "2026-05-03"},
    )

    result = confirm_stage(state=state, contract=build_default_capability_contract())

    assert result.outcome == "await_approval"
    assert "$500 recurring contribution" in result.patch["assistant_prompt"]
    assert "$10,000 starting capital" not in result.patch["assistant_prompt"]


def test_confirm_stage_does_not_enter_approval_when_required_inputs_are_missing() -> None:
    state = RunState.new(current_user_message="run it", recent_thread_history=[])
    state.intent = "backtest_execution"
    state.candidate_strategy_draft = StrategySummary(
        asset_universe=["TSLA"],
        entry_logic="RSI below 30",
    )

    result = confirm_stage(state=state, contract=build_default_capability_contract())

    assert result.outcome == "needs_clarification"
    assert result.patch["assistant_prompt"] is None
    assert result.patch["missing_required_fields"] == [
        "strategy_thesis",
        "exit_logic",
        "date_range",
    ]


def test_confirm_stage_prefers_user_optional_values_over_defaults() -> None:
    state = RunState.new(current_user_message="run it", recent_thread_history=[])
    state.intent = "backtest_execution"
    state.candidate_strategy_draft = StrategySummary(
        strategy_thesis="Buy Tesla on pullbacks",
        asset_universe=["TSLA"],
        entry_logic="RSI below 30",
        exit_logic="RSI above 55",
        date_range="2024-01-01 to 2025-01-01",
    )
    state.optional_parameter_status = {
        "initial_capital": 25000.0,
        "timeframe": "4h",
        "optional_parameter_opportunity": ["fees"],
    }

    result = confirm_stage(state=state, contract=build_default_capability_contract())

    assert (
        result.patch["confirmation_payload"]["optional_parameters"]["initial_capital"]["value"]
        == 25000.0
    )
    assert (
        result.patch["confirmation_payload"]["optional_parameters"]["initial_capital"]["source"]
        == "user"
    )
    assert (
        result.patch["confirmation_payload"]["optional_parameters"]["timeframe"]["source"]
        == "user"
    )
    assert "$25,000 starting capital" in result.patch["assistant_prompt"]
    assert "4h bars" in result.patch["assistant_prompt"]
    assert "Reply yes to run it" in result.patch["assistant_prompt"]
    assert "timeframe=" not in result.patch["assistant_prompt"]


def test_next_step_stage_limits_follow_up_actions() -> None:
    state = RunState.new(current_user_message="why did that happen?", recent_thread_history=[])
    state.final_response_payload = {"summary": "Tesla outperformed SPY"}

    result = next_step_stage(state=state)

    assert result.outcome == "end_run"
    assert result.patch["next_actions"] == [
        "refine_strategy",
        "compare_benchmark",
        "save_to_collection",
    ]
    assert result.patch["assistant_prompt"].count("\n") <= 3


def test_next_step_stage_uses_failure_relevant_actions() -> None:
    state = RunState.new(current_user_message="run it", recent_thread_history=[])
    state.requires_clarification = True
    state.failure_classification = "missing_required_input"

    result = next_step_stage(state=state)

    assert result.outcome == "end_run"
    assert result.patch["next_actions"] == [
        "provide_missing_details",
        "simplify_strategy",
        "ask_for_example",
    ]
    assert "missing strategy details" in result.patch["assistant_prompt"].lower()


def test_next_step_stage_uses_beginner_relevant_actions() -> None:
    state = RunState.new(current_user_message="help me start", recent_thread_history=[])
    state.intent = "beginner_guidance"

    result = next_step_stage(state=state)

    assert result.outcome == "end_run"
    assert result.patch["next_actions"] == [
        "share_example_strategy",
        "explain_backtests",
        "start_simple",
    ]
    assert "example strategy" in result.patch["assistant_prompt"].lower()
