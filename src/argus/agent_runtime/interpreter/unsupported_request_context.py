"""Draft-only context enrichment for unsupported/out-of-scope replies.

Never invent constraints, displace the model's refusal, or backfill run
fields like date_range — filled run fields suppress the focused repair of
wrongly-refused supported ideas.
"""

from __future__ import annotations

from argus.agent_runtime.interpreter.shared import _llm_value_is_empty
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
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
            "reason_codes": list(
                dict.fromkeys([*response.reason_codes, *reason_codes])
            ),
        }
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
