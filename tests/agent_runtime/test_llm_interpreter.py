from dataclasses import dataclass
from datetime import date

from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.llm_interpreter import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
    OpenRouterStructuredInterpreter,
)
from argus.agent_runtime.stages.interpret import InterpretationRequest
from argus.agent_runtime.state.models import StrategySummary, TaskSnapshot, UserState
from argus.agent_runtime.strategy_contract import resolve_date_range


@dataclass(frozen=True)
class ResolvedAssetStub:
    canonical_symbol: str
    asset_class: str
    name: str = ""
    raw_symbol: str = ""


def test_llm_interpreter_validates_asset_class_with_alpaca_resolver(monkeypatch) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        calls.append(symbol)
        return ResolvedAssetStub(
            canonical_symbol=symbol.upper(),
            asset_class="crypto" if symbol.upper() == "BTC" else "equity",
        )

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Backtest Tesla and Bitcoin together.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Backtest Tesla and Bitcoin together.",
            strategy_type="buy_and_hold",
            strategy_thesis="Hold Tesla and Bitcoin together.",
            asset_universe=["tsla", "btc"],
            date_range="last 2 years",
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="Backtest Tesla and Bitcoin together.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert calls == ["TSLA", "BTC"]
    assert result.candidate_strategy_draft.asset_universe == ["TSLA", "BTC"]
    assert result.candidate_strategy_draft.asset_class == "mixed"
    assert result.unsupported_constraints[0].category == "unsupported_asset_mix"


def test_llm_interpreter_merges_refinement_with_pending_strategy(monkeypatch) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="refine",
        user_goal_summary="Make the pending DCA strategy weekly.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Actually make that weekly instead.",
            strategy_type="dca_accumulation",
            cadence="weekly",
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="Actually make that weekly instead.",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
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
                    sizing_mode="capital_amount",
                ),
            ),
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    assert strategy.asset_universe == ["BTC"]
    assert strategy.capital_amount == 500
    assert strategy.date_range == "since 2021"
    assert strategy.cadence == "weekly"


def test_llm_interpreter_marks_moving_average_crossover_as_unsupported(monkeypatch) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Buy Nvidia on a 50/200 moving-average crossover.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Buy Nvidia when its 50-day moving average crosses above the 200-day"
            ),
            strategy_type="indicator_threshold",
            strategy_thesis="Buy Nvidia on a 50/200 moving-average crossover.",
            asset_universe=["NVDA"],
            entry_logic="50-day moving average crosses above the 200-day moving average",
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message=(
                "Buy Nvidia when its 50-day moving average crosses above the 200-day"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert result.candidate_strategy_draft.entry_logic == (
        "50-day moving average crosses above the 200-day moving average"
    )
    assert result.unsupported_constraints[0].category == "unsupported_indicator_rule"


def test_llm_interpreter_humanizes_unsupported_simplification_labels(monkeypatch) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Buy Nvidia on a 50/200 moving-average crossover.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="indicator_threshold",
            strategy_thesis="Buy Nvidia on a 50/200 moving-average crossover.",
            asset_universe=["NVDA"],
            entry_logic="50-day moving average crosses above the 200-day moving average",
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_indicator_rule",
                raw_value="50/200 moving-average crossover",
                explanation="Moving-average crossovers are not directly executable.",
                simplification_labels=["rsi_preset", "buy_and_hold", "dca_accumulation"],
            )
        ],
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message=(
                "Buy Nvidia when its 50-day moving average crosses above the 200-day"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    labels = [
        option.label
        for option in result.unsupported_constraints[0].simplification_options
    ]
    assert labels == [
        "Use the supported RSI rule",
        "Compare with buy and hold",
        "Try recurring buys",
    ]
    assert result.unsupported_constraints[0].explanation.startswith("I understand")


def test_llm_interpreter_accepts_structured_date_ranges(monkeypatch) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Buy and hold Bitcoin from last year to date.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "let's try a basic buy and hold on BTC from jan first last year to date"
            ),
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Bitcoin from January 1 last year to date.",
            asset_universe=["BTC"],
            date_range={"start": "2024-01-01", "end": "today"},
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message=(
                "let's try a basic buy and hold on BTC from jan first last year to date"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    assert strategy.date_range == {"start": "2025-01-01", "end": "today"}
    assert resolve_date_range(strategy.date_range, today=date(2026, 5, 3)).payload == {
        "start": "2025-01-01",
        "end": "2026-05-03",
    }


def test_llm_interpreter_preserves_user_since_year_when_model_defaults_period(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Invest $500 in Bitcoin every month since 2021.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Invest $500 in Bitcoin every month since 2021.",
            strategy_type="dca_accumulation",
            strategy_thesis="Invest $500 in Bitcoin every month since 2021.",
            asset_universe=["BTC"],
            asset_class="crypto",
            date_range="past year",
            cadence="monthly",
            capital_amount=500,
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="Invest $500 in Bitcoin every month since 2021.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    assert strategy.date_range == "since 2021"
    assert strategy.capital_amount == 500
    assert strategy.cadence == "monthly"


def test_llm_interpreter_honors_explicit_buy_and_hold_over_entry_like_phrase(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Buy and hold Bitcoin from January 1 last year.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "let's try a basic buy and hold on BTC from jan first last year to date"
            ),
            strategy_type="indicator_threshold",
            strategy_thesis="Buy Bitcoin on January 1 last year.",
            asset_universe=["BTC"],
            date_range={"start": "2024-01-01", "end": "today"},
            entry_logic="buying on jan 1 last year",
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message=(
                "let's try a basic buy and hold on BTC from jan first last year to date"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.entry_logic is None
    assert strategy.exit_logic is None
    assert result.requires_clarification is False


def test_llm_interpreter_preserves_actual_user_phrasing_when_model_rewrites_it(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )

    user_message = "let's try a basic buy and hold on BTC from jan first last year to date"
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        user_goal_summary="Buy and hold BTC.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="buy and hold on BTC from jan first last 1 year to date",
            strategy_type="buy_and_hold",
            asset_universe=["BTC"],
            date_range={"start": "2024-01-01", "end": "present"},
            capital_amount=10000,
            comparison_baseline="BTC",
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message=user_message,
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    assert strategy.raw_user_phrasing == user_message
    assert strategy.strategy_thesis == user_message
    assert strategy.date_range == {"start": "2025-01-01", "end": "today"}
