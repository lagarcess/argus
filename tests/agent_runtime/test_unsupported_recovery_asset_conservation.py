"""Issue #241: provider-resolved asset conservation on self-authored refusals.

Shape from the sanctioned live scorecard case
``capability_honesty_future_performance_btc_regression``
(argus-eval-scorecard-20260722T203625Z): the model authored an honest refusal
for "If I invest $10,000 in Bitcoin and just hold it, what will it be worth in
ten years?", the runtime resolved Bitcoin -> BTC through the provider catalog
(``provider_resolved_assets`` + ``resolution_provenance`` both typed and
attached), capital survived, no future horizon became dates — yet the pending
recovery draft carried ``asset_universe=[]``.

Invariant: typed provider-validated traded-asset facts survive unsupported
recovery and explicit historical-alternative selection. Unresolved asset text
is never promoted to executable identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from argus.agent_runtime.interpreter.pending_option import (
    _apply_pending_response_option_replacement,
    _llm_draft_from_strategy_summary,
)
from argus.agent_runtime.stages.interpret import (
    StructuredInterpretation,
    interpret_stage,
)
from argus.agent_runtime.state.models import (
    RunState,
    StrategySummary,
    UnsupportedConstraint,
    UserState,
)

BTC_FUTURE_MESSAGE = (
    "If I invest $10,000 in Bitcoin and just hold it, what will it be worth in "
    "ten years?"
)

# Exact typed records persisted by the live run's recovery state.
PROVIDER_RESOLVED_BTC = {
    "raw_text": "Bitcoin",
    "symbol": "BTC",
    "asset_class": "crypto",
    "name": "Bitcoin  / US Dollar",
    "raw_symbol": "BTC/USD",
    "provider": "alpaca",
    "exchange": "AssetExchange.CRYPTO",
}
BTC_RESOLUTION_PROVENANCE = {
    "field": "asset_universe[0]",
    "raw_text": "Bitcoin",
    "source": "llm_extraction",
    "candidate_kind": "asset",
    "resolution_status": "resolved",
    "canonical_symbol": "BTC",
    "asset_class": "crypto",
    "validated_by": "provider_catalog",
    "confidence": "medium",
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


def _self_authored_refusal(
    *,
    with_resolved_records: bool,
) -> StructuredInterpretation:
    extra_parameters: dict[str, Any] = {
        "language": "en",
        "raw_strategy_type": "buy_and_hold",
        "evidence_spans": {
            "asset_universe": "Bitcoin",
            "capital_amount": "$10,000",
            "date_range": "in ten years",
            "strategy_type": "just hold it",
        },
    }
    provenance: list[dict[str, Any]] = []
    if with_resolved_records:
        extra_parameters["provider_resolved_assets"] = [dict(PROVIDER_RESOLVED_BTC)]
        provenance = [dict(BTC_RESOLUTION_PROVENANCE)]
    return StructuredInterpretation(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary=(
            "Predict future value of $10,000 Bitcoin buy and hold in ten years"
        ),
        assistant_response=(
            "I can't predict what Bitcoin will be worth, but I can test how a "
            "$10,000 buy and hold performed over a past period."
        ),
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis=BTC_FUTURE_MESSAGE,
            raw_user_phrasing=BTC_FUTURE_MESSAGE,
            asset_universe=[],
            asset_class="crypto",
            capital_amount=10000,
            comparison_baseline="BTC",
            extra_parameters=extra_parameters,
            resolution_provenance=provenance,
        ),
        unsupported_constraints=[
            UnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value=(
                    "Predict future value of $10,000 Bitcoin buy and hold in ten " "years"
                ),
                explanation=(
                    "Argus runs historical backtests and cannot predict future " "value."
                ),
            )
        ],
        semantic_turn_act="unsupported_request",
    )


def _run_interpret(*, response: StructuredInterpretation):
    return interpret_stage(
        state=RunState.new(
            current_user_message=BTC_FUTURE_MESSAGE, recent_thread_history=[]
        ),
        user=UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=None,
        selected_thread_metadata={},
        structured_interpreter=RecordingInterpreter(response),
    )


def test_self_authored_refusal_conserves_provider_resolved_asset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_crypto_asset_resolution(monkeypatch)
    result = _run_interpret(response=_self_authored_refusal(with_resolved_records=True))

    assert result.outcome == "needs_clarification"
    assert result.patch.get("confirmation_payload") is None
    decision = result.decision
    assert decision is not None
    assert decision.requires_clarification is True
    assert [item.category for item in decision.unsupported_constraints]
    strategy = decision.candidate_strategy_draft
    # The provider-validated canonical asset survives the refusal route.
    assert strategy.asset_universe == ["BTC"]
    assert strategy.asset_class == "crypto"
    assert strategy.capital_amount == 10000
    # The future horizon still never becomes dates on this route.
    assert strategy.date_range in (None, "", {}, [])


def test_unresolved_asset_text_is_not_promoted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_crypto_asset_resolution(monkeypatch)
    result = _run_interpret(response=_self_authored_refusal(with_resolved_records=False))

    assert result.outcome == "needs_clarification"
    assert result.patch.get("confirmation_payload") is None
    strategy = result.decision.candidate_strategy_draft
    # Evidence text alone ("Bitcoin") must not become executable identity.
    assert strategy.asset_universe == []
    assert strategy.capital_amount == 10000


def test_selection_after_refusal_reuses_resolved_asset_and_asks_period() -> None:
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        asset_universe=["BTC"],
        asset_class="crypto",
        capital_amount=10000,
        comparison_baseline="BTC",
        extra_parameters={
            "language": "en",
            "provider_resolved_assets": [dict(PROVIDER_RESOLVED_BTC)],
        },
    )
    draft = _llm_draft_from_strategy_summary(pending)
    replaced = _apply_pending_response_option_replacement(
        draft=draft,
        replacement_values={"strategy_type": "buy_and_hold"},
        current_missing=[],
    )
    repaired = replaced["draft"]
    assert repaired.asset_universe == ["BTC"]
    assert repaired.capital_amount == 10000
    assert repaired.date_range in (None, "", {}, [])
    # The historical period is still requested; no silent window default.
    assert "date_range" in replaced["missing_fields"]
