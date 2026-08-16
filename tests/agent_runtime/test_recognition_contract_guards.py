"""The recognition contract: no layer downstream of the primary interpretation
may silently discard a typed fact the model produced.

Live traces (docs/reports/evidence/2026-08-15-recognition-contract/TRACES.md)
showed correct primary reads destroyed by post-read layers: context asset
injection manufacturing a universe/exclusion contradiction, the edit
materializer refusing correct plans over it, the knowledge/research rail
claiming typed unsupported_request turns, and a DCA sidecar audit re-typing an
explicitly-provenance-tagged seed as a budget. Each lock here pins the guard
that stops one drop site and the receipt it leaves behind.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from argus.agent_runtime import knowledge_answer as ka
from argus.agent_runtime.artifact_edit_planner import (
    ArtifactAssumptionEditPlan,
    EditOperation,
)
from argus.agent_runtime.interpreter.provider_context_assets import (
    response_with_provider_context_assets,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.stages.interpret_types import (
    InterpretationRequest,
    StructuredInterpretation,
    UserState,
)
from argus.agent_runtime.state.models import (
    RunState,
    StrategySummary,
    TaskSnapshot,
    UnsupportedConstraint,
)

AAPL_ROW = {
    "raw_text": "AAPL",
    "role": "traded_asset",
    "status": "resolved",
    "symbol": "AAPL",
    "asset_class": "equity",
    "name": "Apple Inc. Common Stock",
    "raw_symbol": "AAPL",
    "provider": "alpaca",
    "exchange": "AssetExchange.NASDAQ",
}
TSLA_ROW = {
    "raw_text": "TSLA",
    "role": "traded_asset",
    "status": "resolved",
    "symbol": "TSLA",
    "asset_class": "equity",
    "name": "Tesla, Inc. Common Stock",
    "raw_symbol": "TSLA",
    "provider": "alpaca",
    "exchange": "AssetExchange.NASDAQ",
}


def _context(rows: list[dict[str, Any]]) -> str:
    return json.dumps(
        {
            "asset_resolution_candidates": rows,
            "all_traded_asset_mentions_accounted_for": True,
        }
    )


def _exclusion_response(**draft_overrides: Any) -> LLMInterpretationResponse:
    draft = {
        "raw_user_phrasing": "remove AAPL",
        "asset_exclusions": ["AAPL"],
        "asset_universe_operation": "replace",
        "field_provenance": {"asset_exclusions": "explicit_user"},
        "evidence_spans": {"asset_exclusions": "remove AAPL"},
        **draft_overrides,
    }
    return LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="refine",
        user_goal_summary="Remove AAPL from the pending setup.",
        candidate_strategy_draft=LLMStrategyDraft(**draft),
        semantic_turn_act="refine_current_idea",
    )


class TestContextInjectionRespectsTypedExclusions:
    """Trace 1, step 2: 'remove AAPL' mentions AAPL, and the injection wrote
    that mention into asset_universe, manufacturing the contradiction that
    downstream coherence checks punished."""

    def test_an_excluded_mention_is_never_injected_as_a_traded_asset(self) -> None:
        normalized = response_with_provider_context_assets(
            _exclusion_response(),
            asset_resolution_context=_context([dict(AAPL_ROW)]),
        )
        draft = normalized.candidate_strategy_draft
        assert draft.asset_universe == []
        assert draft.asset_exclusions == ["AAPL"]
        assert "context_asset_injection_respected_exclusion" in normalized.reason_codes
        # Provider provenance is retained; only the traded-role write is vetoed.
        records = (draft.extra_parameters or {}).get("provider_resolved_assets")
        assert records and records[0]["symbol"] == "AAPL"

    def test_non_excluded_mentions_still_inject(self) -> None:
        normalized = response_with_provider_context_assets(
            _exclusion_response(raw_user_phrasing="swap AAPL for TSLA"),
            asset_resolution_context=_context([dict(AAPL_ROW), dict(TSLA_ROW)]),
        )
        draft = normalized.candidate_strategy_draft
        assert draft.asset_universe == ["TSLA"]
        assert "context_asset_injection_respected_exclusion" in normalized.reason_codes


def _card_request(message: str) -> InterpretationRequest:
    return InterpretationRequest(
        user=UserState(user_id="user-recognition"),
        current_user_message=message,
        recent_thread_history=[],
        latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=StrategySummary(
                strategy_type="buy_and_hold",
                asset_universe=["AAPL", "MSFT", "NVDA"],
                asset_class="equity",
                date_range={"start": "2024-01-01", "end": "2024-12-31"},
                comparison_baseline="SPY",
                capital_amount=1000,
            )
        ),
        selected_thread_metadata={
            "requested_field": "asset_universe",
            "last_stage_outcome": "await_user_reply",
        },
    )


class TestExclusionsOutrankCarriedUniverseCopies:
    """Trace 1, step 5: three correct model reads were refused because the
    injected copy of the excluded symbol overlapped asset_universe."""

    def test_the_traced_remove_shape_is_materialized(self, monkeypatch) -> None:
        from argus.agent_runtime.interpreter import artifact_assumption_edit

        monkeypatch.setattr(
            artifact_assumption_edit,
            "_grounded_asset_symbols_from_message",
            lambda *_args, **_kwargs: {"AAPL"},
        )
        primary = LLMStrategyDraft(
            raw_user_phrasing="remove AAPL",
            asset_universe=["AAPL"],
            asset_exclusions=["AAPL"],
            asset_universe_operation="replace",
            field_provenance={"asset_exclusions": "explicit_user"},
        )
        plan = ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[EditOperation(op="remove", target="asset", symbols=["AAPL"])],
        )
        covered = artifact_assumption_edit.materialized_artifact_edit_targets(
            plan,
            request=_card_request("remove AAPL"),
            primary_draft=primary,
        )
        assert covered is not None
        assert "asset" in covered

    def test_a_compound_swap_keeps_unnamed_card_members(self, monkeypatch) -> None:
        """'remove AAPL and replace with TSLA and GOOGL' keeps MSFT and NVDA:
        typed exclusions of card members license exactly those removals,
        whatever the single-choice operation label says."""
        from argus.agent_runtime.interpreter import artifact_assumption_edit

        monkeypatch.setattr(
            artifact_assumption_edit,
            "_grounded_asset_symbols_from_message",
            lambda *_args, **_kwargs: {"AAPL", "TSLA", "GOOGL"},
        )
        primary = LLMStrategyDraft(
            raw_user_phrasing="remove AAPL and replace with TSLA and GOOGL",
            asset_universe=["TSLA", "GOOGL"],
            asset_inclusions=["TSLA", "GOOGL"],
            asset_exclusions=["AAPL"],
            asset_universe_operation="replace",
            field_provenance={"asset_exclusions": "explicit_user"},
        )
        plan = ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(op="remove", target="asset", symbols=["AAPL"]),
                EditOperation(op="add", target="asset", symbols=["TSLA", "GOOGL"]),
            ],
        )
        covered = artifact_assumption_edit.materialized_artifact_edit_targets(
            plan,
            request=_card_request("remove AAPL and replace with TSLA and GOOGL"),
            primary_draft=primary,
        )
        assert covered is not None
        assert "asset" in covered

    def test_an_inclusion_exclusion_contradiction_is_still_refused(
        self, monkeypatch
    ) -> None:
        from argus.agent_runtime.interpreter import artifact_assumption_edit

        monkeypatch.setattr(
            artifact_assumption_edit,
            "_grounded_asset_symbols_from_message",
            lambda *_args, **_kwargs: {"AAPL"},
        )
        primary = LLMStrategyDraft(
            raw_user_phrasing="add AAPL and remove AAPL",
            asset_inclusions=["AAPL"],
            asset_exclusions=["AAPL"],
            field_provenance={"asset_exclusions": "explicit_user"},
        )
        plan = ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[EditOperation(op="remove", target="asset", symbols=["AAPL"])],
        )
        assert (
            artifact_assumption_edit.materialized_artifact_edit_targets(
                plan,
                request=_card_request("add AAPL and remove AAPL"),
                primary_draft=primary,
            )
            is None
        )


def _unsupported_interpretation(**overrides: Any) -> StructuredInterpretation:
    payload: dict[str, Any] = {
        "intent": "unsupported_or_out_of_scope",
        "task_relation": "new_task",
        "user_goal_summary": "Backtest weekly options on AAPL.",
        "semantic_turn_act": "unsupported_request",
        "requires_clarification": False,
        "candidate_strategy_draft": StrategySummary(
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
        ),
        "unsupported_constraints": [
            UnsupportedConstraint(
                category="strategy_type",
                raw_value="weekly options",
                explanation="Options backtesting is not supported.",
            )
        ],
    }
    payload.update(overrides)
    return StructuredInterpretation(**payload)


def _run_knowledge(
    interpretation: StructuredInterpretation,
    message: str = "please backtest weekly options on apple from 2024-01-01",
) -> Any:
    return asyncio.run(
        ka.knowledge_answer_stage_result(
            interpretation=interpretation,
            state=RunState.new(current_user_message=message, recent_thread_history=[]),
            user=UserState(user_id="recognition", language_preference="en"),
            snapshot=None,
            selected_thread_metadata={},
        )
    )


class TestTypedUnsupportedPayloadKeepsItsRecoveryRoute:
    """Trace 2: the rail classifier answered a typed unsupported RUN request
    with asset statistics, erasing the constraint, the assets, the window,
    and the ready-made simplification options."""

    @pytest.fixture(autouse=True)
    def _no_classifier(self, monkeypatch):
        async def _must_not_classify(**_kwargs: Any):
            raise AssertionError(
                "a typed unsupported payload must never reach the classifier"
            )

        monkeypatch.setattr(ka, "_classify_question", _must_not_classify)
        import argus.agent_runtime.research_answer as research_answer

        async def _must_not_rail(**_kwargs: Any):
            raise AssertionError(
                "a typed unsupported payload must never reach the research rail"
            )

        monkeypatch.setattr(
            research_answer, "research_answer_stage_result", _must_not_rail
        )

    def test_flag_on_the_rail_never_sees_the_turn(self, monkeypatch) -> None:
        monkeypatch.setattr(ka, "research_rail_enabled", lambda: True)
        interpretation = _unsupported_interpretation()
        assert _run_knowledge(interpretation) is None
        assert "unsupported_payload_kept_recovery_route" in interpretation.reason_codes

    def test_flag_off_the_legacy_answerer_never_sees_the_turn(self, monkeypatch) -> None:
        monkeypatch.setattr(ka, "research_rail_enabled", lambda: False)
        interpretation = _unsupported_interpretation()
        assert _run_knowledge(interpretation) is None
        assert "unsupported_payload_kept_recovery_route" in interpretation.reason_codes

    def test_an_unset_act_with_unsupported_intent_also_stands_down(
        self, monkeypatch
    ) -> None:
        monkeypatch.setattr(ka, "research_rail_enabled", lambda: True)
        interpretation = _unsupported_interpretation(semantic_turn_act=None)
        assert _run_knowledge(interpretation) is None
        assert "unsupported_payload_kept_recovery_route" in interpretation.reason_codes


def test_an_unsupported_act_without_a_payload_still_reaches_the_classifier(
    monkeypatch,
) -> None:
    """The veto routes on the typed payload, not the act label: a payloadless
    unsupported_request turn may still be a statistics question, and the
    classifier keeps owning that boundary."""
    calls: list[str] = []

    async def classify(**_kwargs: Any):
        calls.append("classified")
        return ka.KnowledgeQueryExtraction(question_kind="none")

    monkeypatch.setattr(ka, "_classify_question", classify)
    monkeypatch.setattr(ka, "research_rail_enabled", lambda: False)
    interpretation = _unsupported_interpretation(unsupported_constraints=[])
    assert _run_knowledge(interpretation) is None
    assert calls == ["classified"]
    assert "unsupported_payload_kept_recovery_route" not in interpretation.reason_codes


@pytest.mark.asyncio
async def test_dca_budget_audit_cannot_retype_an_explicit_seed(monkeypatch) -> None:
    """Trace 3: the sidecar audit re-typed '$5,000 to start' (explicit
    starting_capital provenance) into a total budget, and semantic integrity
    then fabricated a ceiling refusal from it."""
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, messages, schema_model, model_name
        assert schema_name == "DcaContributionRoleAudit"
        return interpreter_module.DcaContributionRoleAudit(
            recurring_contribution_explicit=False,
            total_budget_not_recurring=True,
            confidence=0.9,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )
    message = (
        "Set up a monthly recurring plan on SPY for 2024: $5,000 to start "
        "and $0 added each month."
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        user_goal_summary="Monthly recurring plan with an explicit seed.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=message,
            strategy_type="dca_accumulation",
            asset_universe=["SPY"],
            asset_class="equity",
            cadence="monthly",
            initial_capital=5000.0,
            capital_amount=5000.0,
            recurring_contribution=0.0,
            field_provenance={
                "initial_capital": "starting_capital",
                "cadence": "explicit_user",
            },
            evidence_spans={"initial_capital": "$5,000 to start"},
        ),
        semantic_turn_act="new_idea",
    )

    audited = await interpreter_module._dca_contribution_role_audited_response(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=message,
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    draft = audited.candidate_strategy_draft
    assert draft.initial_capital == 5000.0
    assert draft.total_capital is None
    assert draft.field_provenance.get("initial_capital") == "starting_capital"
    # The duplicated amount may not masquerade as the recurring contribution.
    assert draft.capital_amount is None
    assert draft.recurring_contribution == 0.0
    assert "dca_seed_provenance_kept_over_budget_audit" in audited.reason_codes
    assert "dca_total_budget_role_audited" not in audited.reason_codes
    assert "capital_amount" not in audited.missing_required_fields
