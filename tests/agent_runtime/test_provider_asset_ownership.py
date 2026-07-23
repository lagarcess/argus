"""Issue #241: `provider_resolved_assets` is runtime-owned, never model-owned.

`LLMStrategyDraft.extra_parameters` is model-writable. A hallucinated
`provider_resolved_assets` record must not masquerade as provider truth: the
provider-context normalization boundary strips any incoming value and only the
actual runtime provider-context rows repopulate it. Downstream consumers (the
refusal-conservation helper, canonical-asset repair) then trust the key.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest
from argus.agent_runtime.interpreter.provider_context_assets import (
    response_with_provider_context_assets,
)
from argus.agent_runtime.interpreter.strategy_builder import _strategy_from_llm
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
    LLMUnsupportedConstraint,
)
from argus.agent_runtime.stages.interpret import (
    StructuredInterpretation,
    interpret_stage,
)
from argus.agent_runtime.state.models import (
    RunState,
    UnsupportedConstraint,
    UserState,
)

FAKE_RECORD = {
    "raw_text": "Zorbcoin",
    "symbol": "ZORB",
    "asset_class": "crypto",
    "name": "Zorbcoin",
    "raw_symbol": "ZORB/USD",
    "provider": "alpaca",
    "exchange": "AssetExchange.CRYPTO",
}

BTC_CONTEXT_ROW = {
    "raw_text": "Bitcoin",
    "role": "traded_asset",
    "status": "resolved",
    "symbol": "BTC",
    "asset_class": "crypto",
    "name": "Bitcoin / US Dollar",
    "raw_symbol": "BTC/USD",
    "provider": "alpaca",
    "exchange": "AssetExchange.CRYPTO",
}


@dataclass(frozen=True)
class ResolvedAssetStub:
    canonical_symbol: str
    asset_class: str
    name: str = ""
    raw_symbol: str = ""


class RecordingInterpreter:
    def __init__(self, response: StructuredInterpretation | None) -> None:
        self.response = response

    def __call__(self, request):
        return self.response


def _stub_crypto_asset_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    def resolve_stub(symbol: str, **_: Any) -> ResolvedAssetStub:
        return ResolvedAssetStub(symbol.upper(), "crypto")

    monkeypatch.setattr(interpret_module, "resolve_asset", resolve_stub)


def _refusal_response_with_model_records() -> LLMInterpretationResponse:
    return LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Predict Zorbcoin's future value.",
        assistant_response=(
            "I can't predict what Zorbcoin will be worth, and it is not in the "
            "supported market data."
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=[],
            asset_class="crypto",
            capital_amount=5000,
            extra_parameters={"provider_resolved_assets": [dict(FAKE_RECORD)]},
        ),
        unsupported_constraints=[
            LLMUnsupportedConstraint(
                category="unsupported_symbol",
                raw_value="Zorbcoin",
                explanation="Zorbcoin is not available in supported market data.",
            )
        ],
        semantic_turn_act="unsupported_request",
    )


def _context(rows: list[dict[str, Any]]) -> str:
    return json.dumps({"asset_resolution_candidates": rows})


def test_model_supplied_provider_records_are_stripped_without_runtime_context() -> None:
    normalized = response_with_provider_context_assets(
        _refusal_response_with_model_records(),
        asset_resolution_context=None,
        include_unsupported_request=True,
    )
    extra = normalized.candidate_strategy_draft.extra_parameters or {}
    assert "provider_resolved_assets" not in extra
    assert normalized.candidate_strategy_draft.asset_universe == []


def test_fake_record_cannot_reach_pending_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_crypto_asset_resolution(monkeypatch)
    normalized = response_with_provider_context_assets(
        _refusal_response_with_model_records(),
        asset_resolution_context=None,
        include_unsupported_request=True,
    )
    strategy = _strategy_from_llm(normalized.candidate_strategy_draft)
    result = interpret_stage(
        state=RunState.new(
            current_user_message="If I put $5,000 into Zorbcoin, what will it become?",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=None,
        selected_thread_metadata={},
        structured_interpreter=RecordingInterpreter(
            StructuredInterpretation(
                intent="unsupported_or_out_of_scope",
                task_relation="new_task",
                requires_clarification=True,
                user_goal_summary="Predict Zorbcoin's future value.",
                candidate_strategy_draft=strategy,
                unsupported_constraints=[
                    UnsupportedConstraint(
                        category="unsupported_symbol",
                        raw_value="Zorbcoin",
                        explanation=(
                            "Zorbcoin is not available in supported market data."
                        ),
                    )
                ],
                semantic_turn_act="unsupported_request",
            )
        ),
    )
    assert result.outcome == "needs_clarification"
    assert result.patch.get("confirmation_payload") is None
    draft = result.decision.candidate_strategy_draft
    assert draft.asset_universe == []
    assert "ZORB" not in [str(s).upper() for s in draft.asset_universe]


def test_runtime_context_rows_still_inject_and_conserve_real_assets() -> None:
    normalized = response_with_provider_context_assets(
        _refusal_response_with_model_records(),
        asset_resolution_context=_context([dict(BTC_CONTEXT_ROW)]),
        include_unsupported_request=True,
    )
    draft = normalized.candidate_strategy_draft
    extra = draft.extra_parameters or {}
    records = extra.get("provider_resolved_assets")
    assert isinstance(records, list) and len(records) == 1
    assert records[0]["symbol"] == "BTC"
    # The fake model record is gone; only the runtime row survives.
    assert all(record["symbol"] != "ZORB" for record in records)
    assert draft.asset_universe == ["BTC"]


def test_ambiguous_runtime_context_never_becomes_executable_identity() -> None:
    ambiguous_row = {
        "raw_text": "Sun",
        "role": "traded_asset",
        "status": "ambiguous",
        "candidates": [
            {"symbol": "SUN", "asset_class": "equity"},
            {"symbol": "SUNE", "asset_class": "equity"},
        ],
    }
    normalized = response_with_provider_context_assets(
        _refusal_response_with_model_records(),
        asset_resolution_context=_context([ambiguous_row]),
        include_unsupported_request=True,
    )
    draft = normalized.candidate_strategy_draft
    extra = draft.extra_parameters or {}
    assert "provider_resolved_assets" not in extra
    assert draft.asset_universe == []


def test_benchmark_role_rows_never_become_provider_records() -> None:
    """PR #266 review T5 counter-evidence: typed benchmark rows stay out."""

    benchmark_row = {
        "raw_text": "S&P 500",
        "role": "benchmark",
        "status": "resolved",
        "symbol": "SPY",
        "asset_class": "equity",
        "name": "SPDR S&P 500",
        "raw_symbol": "SPY",
        "provider": "alpaca",
        "exchange": "ARCA",
    }
    normalized = response_with_provider_context_assets(
        _refusal_response_with_model_records(),
        asset_resolution_context=_context([benchmark_row]),
        include_unsupported_request=True,
    )
    draft = normalized.candidate_strategy_draft
    assert "provider_resolved_assets" not in (draft.extra_parameters or {})
    assert draft.asset_universe == []


def test_partial_basket_context_preserves_fuller_draft_without_model_records() -> None:
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="Hold NVDA and MSFT.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=["NVDA", "MSFT"],
            asset_class="equity",
            capital_amount=4000,
            extra_parameters={"provider_resolved_assets": [dict(FAKE_RECORD)]},
        ),
    )
    nvda_row = {
        "raw_text": "NVDA",
        "role": "traded_asset",
        "status": "resolved",
        "symbol": "NVDA",
        "asset_class": "equity",
        "name": "NVIDIA",
        "raw_symbol": "NVDA",
        "provider": "alpaca",
        "exchange": "NASDAQ",
    }
    normalized = response_with_provider_context_assets(
        response,
        asset_resolution_context=_context([nvda_row]),
        include_unsupported_request=True,
    )
    draft = normalized.candidate_strategy_draft
    # The fuller model draft is preserved; runtime records replace the fake one.
    assert set(draft.asset_universe) == {"NVDA", "MSFT"}
    records = (draft.extra_parameters or {}).get("provider_resolved_assets") or []
    assert [record["symbol"] for record in records] == ["NVDA"]
