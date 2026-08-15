"""Draft-only context enrichment for unsupported/out-of-scope replies.

Never invent constraints, displace the model's refusal, or backfill run
fields like date_range — filled run fields suppress the focused repair of
wrongly-refused supported ideas.
"""

from __future__ import annotations

from typing import Any

from argus.agent_runtime.interpreter.shared import _llm_value_is_empty
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import StrategySummary, UnsupportedConstraint
from argus.agent_runtime.strategy_contract import (
    SUPPORTED_STRATEGY_TYPES,
    executable_strategy_type,
)
from argus.domain.backtesting.config import default_benchmark


def response_with_unsupported_request_runtime_facts(
    response: LLMInterpretationResponse,
    *,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    if response.intent != "unsupported_or_out_of_scope":
        return response
    if response.semantic_turn_act != "unsupported_request":
        return response

    draft = response.candidate_strategy_draft.model_copy(deep=True)
    reason_codes: list[str] = []
    if _llm_value_is_empty(draft.comparison_baseline):
        benchmark = _default_benchmark_for_draft_asset_class(draft)
        if benchmark is not None:
            draft.comparison_baseline = benchmark
            reason_codes.append("unsupported_request_default_benchmark_applied")

    if not reason_codes:
        return response
    return response.model_copy(
        update={
            "candidate_strategy_draft": draft,
            "reason_codes": list(dict.fromkeys([*response.reason_codes, *reason_codes])),
        }
    )


def materialized_unsupported_request_constraint(
    *,
    interpretation: Any,
    strategy: StrategySummary,
    existing_constraints: list[UnsupportedConstraint],
    has_future_horizon: bool,
    contract: Any,
) -> UnsupportedConstraint | None:
    """The typed unsupported route keeps its recovery shape without a payload.

    This does not invent a refusal: the model already typed one through
    intent/semantic_turn_act. It may still omit the constraint payload, and
    without one the turn dissolves into plain chat and the user's asset,
    window, and capital dissolve with it. Rebuilding the constraint from the
    typed fields keeps the recovery route, which names the limit and
    preserves every supported fact.
    """
    if existing_constraints or has_future_horizon:
        return None
    if (
        interpretation.intent != "unsupported_or_out_of_scope"
        and interpretation.semantic_turn_act != "unsupported_request"
    ):
        return None
    if executable_strategy_type(strategy) in SUPPORTED_STRATEGY_TYPES:
        return None
    if not _strategy_carries_current_run_facts(strategy):
        return None
    raw_value = next(
        (
            text
            for value in (
                strategy.entry_logic,
                strategy.strategy_thesis,
                strategy.raw_user_phrasing,
                interpretation.user_goal_summary,
            )
            if (text := str(value or "").strip())
        ),
        "unsupported strategy logic",
    )
    return UnsupportedConstraint(
        category="unsupported_strategy_logic",
        raw_value=raw_value,
        explanation=(
            "That idea needs a rule or data source the current backtest engine "
            "cannot execute directly yet."
        ),
        simplification_options=contract.get_simplification_options(
            "unsupported_strategy_logic"
        ),
    )


def _strategy_carries_current_run_facts(strategy: StrategySummary) -> bool:
    """User-supplied run facts worth preserving through unsupported recovery."""
    return any(
        value not in (None, "", [], {})
        for value in (
            strategy.asset_universe,
            strategy.date_range,
            strategy.capital_amount,
        )
    )


def _default_benchmark_for_draft_asset_class(draft: LLMStrategyDraft) -> str | None:
    asset_class = str(draft.asset_class or "").strip().lower()
    symbols = [str(symbol or "").strip().upper() for symbol in draft.asset_universe]
    if asset_class == "equity":
        return default_benchmark("equity", symbols)
    if asset_class == "crypto":
        return default_benchmark("crypto", symbols)
    if asset_class == "currency_pair":
        return default_benchmark("currency_pair", symbols)
    return None
