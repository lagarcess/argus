from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from argus.agent_runtime.stages.interpret import (
    StructuredInterpretation,
    interpret_stage,
)
from argus.agent_runtime.state.models import (
    ResponseProfileOverrides,
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


class RecordingInterpreter:
    def __init__(self, response: StructuredInterpretation | None) -> None:
        self.response = response
        self.requests = []
        self.last_status = "unused"

    def __call__(self, request):
        self.requests.append(request)
        self.last_status = "used"
        return self.response


def run_interpret_with_llm(
    *,
    message: str,
    response: StructuredInterpretation,
    user: UserState | None = None,
    snapshot: TaskSnapshot | None = None,
    history: list[dict[str, str]] | None = None,
):
    interpreter = RecordingInterpreter(response)
    state = RunState.new(
        current_user_message=message,
        recent_thread_history=history or [],
    )
    result = interpret_stage(
        state=state,
        user=user or UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=snapshot,
        structured_interpreter=interpreter,
    )
    return result, interpreter


def test_interpret_passes_raw_message_to_llm_without_regex_normalization() -> None:
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User is checking the product.",
        assistant_response="I can help turn an investing idea into a supported backtest.",
        semantic_turn_act="educational_question",
    )

    result, interpreter = run_interpret_with_llm(
        message="  Actually make that weekly instead.  ",
        response=response,
    )

    assert len(interpreter.requests) == 1
    assert (
        interpreter.requests[0].current_user_message
        == "  Actually make that weekly instead.  "
    )
    assert result.outcome == "ready_to_respond"


def test_interpret_social_opener_uses_llm_response() -> None:
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User greeted Argus.",
        assistant_response="Hi. Tell me the investing idea you want to test.",
        confidence=0.94,
        semantic_turn_act="educational_question",
    )

    result, interpreter = run_interpret_with_llm(message="hello", response=response)

    assert len(interpreter.requests) == 1
    assert result.outcome == "ready_to_respond"
    assert result.patch["assistant_response"] == response.assistant_response
    assert result.decision.reason_codes[0] == "llm_interpreter_used"
    assert "beginner_language_detected" not in result.decision.reason_codes


def test_interpret_uses_llm_extracted_strategy_fields(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User supplied an RSI strategy.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing=(
                "Backtest Tesla and sell when RSI is above 70 over the last 2 years"
            ),
            strategy_type="indicator_threshold",
            strategy_thesis="Backtest Tesla RSI exit rule.",
            asset_universe=["TSLA"],
            entry_logic="RSI drops below 30",
            exit_logic="RSI rises above 70",
            date_range="last 2 years",
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(
        message="Backtest Tesla and sell when RSI is above 70 over the last 2 years",
        response=response,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["TSLA"]
    assert strategy.exit_logic == "RSI rises above 70"
    assert strategy.date_range == "last 2 years"


def test_interpret_approval_uses_semantic_turn_act() -> None:
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Tesla.",
        asset_universe=["TSLA"],
        date_range="past year",
    )
    snapshot = TaskSnapshot(pending_strategy_summary=pending)
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User approved the pending backtest.",
        candidate_strategy_draft=pending,
        assistant_response="I will run the backtest now.",
        semantic_turn_act="approval",
    )

    result, _ = run_interpret_with_llm(
        message="Run backtest",
        response=response,
        snapshot=snapshot,
        history=[
            {"role": "user", "content": "Buy and hold Tesla over the past year."},
            {"role": "assistant", "content": "Please confirm this backtest."},
        ],
    )

    assert result.outcome == "approved_for_execution"
    assert result.patch["confirmation_payload"]["strategy"]["asset_universe"] == ["TSLA"]
    assert result.decision.semantic_turn_act == "approval"


def test_interpret_does_not_approve_when_llm_does_not_mark_approval() -> None:
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Tesla.",
        asset_universe=["TSLA"],
        date_range="past year",
    )
    snapshot = TaskSnapshot(pending_strategy_summary=pending)
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asked a follow-up.",
        candidate_strategy_draft=pending,
        assistant_response="I can explain the assumptions first.",
        semantic_turn_act="result_followup",
    )

    result, _ = run_interpret_with_llm(
        message="Can you explain the assumptions?",
        response=response,
        snapshot=snapshot,
    )

    assert result.outcome == "ready_to_respond"
    assert result.patch["assistant_response"] == "I can explain the assumptions first."


def test_interpret_canonicalizes_symbols_through_market_data(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub("TSLA", "equity", raw_symbol=symbol),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User supplied a buy-and-hold strategy.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Tesla.",
            asset_universe=["Tesla"],
            date_range="past year",
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(message="Buy and hold Tesla", response=response)

    assert result.outcome == "ready_for_confirmation"
    assert result.decision.candidate_strategy_draft.asset_universe == ["TSLA"]
    assert result.decision.candidate_strategy_draft.asset_class == "equity"


def test_interpret_applies_llm_response_profile_overrides() -> None:
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asked for a concise explanation.",
        assistant_response="Here is the short version.",
        response_profile_overrides=ResponseProfileOverrides(verbosity="low"),
        semantic_turn_act="educational_question",
    )

    result, _ = run_interpret_with_llm(
        message="Explain this briefly.",
        response=response,
        user=UserState(user_id="u1", response_verbosity="high"),
    )

    assert result.decision.effective_response_profile.effective_verbosity == "low"
    assert result.decision.user_preference_overridden_for_turn is True


def test_interpret_stage_has_no_regex_nlu_imports() -> None:
    source = Path("src/argus/agent_runtime/stages/interpret.py").read_text()
    forbidden = [
        "extract_signals(",
        "extract_strategy_fields(",
        "resolve_response_profile_overrides(",
        "resolve_intent(",
        "resolve_task_relation(",
        "resolve_gray_case_arbitration(",
        "_direct_conversational_response(",
        "_is_educational_turn(",
        "_is_approval_message(",
    ]
    for token in forbidden:
        assert token not in source


def test_symbol_alias_dictionaries_are_deleted() -> None:
    paths = [
        Path("src/argus/agent_runtime/signals/task_relation.py"),
        Path("src/argus/agent_runtime/stages/interpret.py"),
    ]
    source = "\n".join(path.read_text() for path in paths)
    for token in ["SYMBOL_ALIASES", "COMMON_NAMES", "NON_SYMBOLS"]:
        assert token not in source
