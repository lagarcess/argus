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


@pytest.mark.asyncio
async def test_dca_budget_audit_clears_the_fabricated_recurring_copy(
    monkeypatch,
) -> None:
    """Ceiling case, run-2 signature: the focused repair's schema has no
    budget slot, so it re-typed "$5,000 total" as recurring_contribution=5000
    and the plan reported nothing missing. When the audit concludes no
    explicit contribution exists, a contribution equal to the budget is the
    same money re-roled and must not survive as a fundable plan."""
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
        "I only have $5,000 to invest. Can you test putting money into VOO "
        "every month through 2024?"
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        user_goal_summary="Monthly plan bounded by a total budget.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=message,
            strategy_type="dca_accumulation",
            asset_universe=["VOO"],
            asset_class="equity",
            cadence="monthly",
            capital_amount=5000.0,
            recurring_contribution=5000.0,
            total_capital=5000.0,
            field_provenance={
                "total_capital": "explicit_user",
                "recurring_contribution": "explicit_user",
                "cadence": "explicit_user",
            },
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
    assert draft.recurring_contribution is None
    assert draft.capital_amount is None
    assert draft.total_capital == 5000.0
    assert "capital_amount" in audited.missing_required_fields
    assert "dca_budget_recurring_copy_cleared" in audited.reason_codes


class TestBareAssetAnswerOperationLabel:
    """Bare-ticker case (#190): 'TSLA' answering the asset slot carries no
    words that could express an operation, so a filled
    asset_universe_operation is an unevidenced single-choice guess; trusting
    a guessed 'replace' wiped a multi-asset card."""

    @staticmethod
    def _request() -> InterpretationRequest:
        return _card_request("TSLA")

    @staticmethod
    def _response(**draft_overrides: Any) -> LLMInterpretationResponse:
        draft = {
            "raw_user_phrasing": "TSLA",
            "asset_universe": ["TSLA"],
            "asset_universe_operation": "replace",
            **draft_overrides,
        }
        return LLMInterpretationResponse(
            intent="strategy_drafting",
            task_relation="continue",
            user_goal_summary="User answered the asset chip with Tesla.",
            candidate_strategy_draft=LLMStrategyDraft(**draft),
            semantic_turn_act="answer_pending_need",
        )

    @staticmethod
    def _resolver(symbol_map: dict[str, str]):
        class _Asset:
            def __init__(self, symbol: str) -> None:
                self.canonical_symbol = symbol
                self.asset_class = "equity"

        class _Resolution:
            def __init__(self, symbol: str) -> None:
                self.status = "resolved"
                self.asset = _Asset(symbol)

        def resolve(query: str, *, field: str, source: str):
            del field, source
            normalized = query.strip().upper()
            if normalized in symbol_map:
                return _Resolution(symbol_map[normalized])
            raise ValueError("invalid_symbol")

        return resolve

    def _assert_typed_as_inclusion(self, updated: Any) -> None:
        draft = updated.candidate_strategy_draft
        assert draft.asset_universe_operation is None
        assert draft.asset_universe == ["TSLA"]
        assert draft.asset_inclusions == ["TSLA"]
        assert "bare_asset_answer_typed_as_inclusion" in updated.reason_codes

    def test_a_guessed_replace_label_becomes_an_inclusion(self) -> None:
        from argus.agent_runtime.interpreter.readiness_helpers import (
            _bare_asset_answer_without_unevidenced_operation,
        )

        self._assert_typed_as_inclusion(
            _bare_asset_answer_without_unevidenced_operation(
                response=self._response(),
                request=self._request(),
                resolve_asset_candidate=self._resolver({"TSLA": "TSLA"}),
            )
        )

    def test_a_bare_answer_typed_as_its_own_inclusion_is_still_bare(self) -> None:
        """Live tip4 trace: the model sometimes types the bare answer as
        asset_inclusions=["TSLA"] alongside the guessed replace label; an
        inclusion naming exactly the answered symbol is the same bare shape."""
        from argus.agent_runtime.interpreter.readiness_helpers import (
            _bare_asset_answer_without_unevidenced_operation,
        )

        self._assert_typed_as_inclusion(
            _bare_asset_answer_without_unevidenced_operation(
                response=self._response(asset_inclusions=["TSLA"]),
                request=self._request(),
                resolve_asset_candidate=self._resolver({"TSLA": "TSLA"}),
            )
        )

    def test_an_empty_universe_bare_answer_is_typed_instead_of_requestioned(
        self,
    ) -> None:
        """Live A/B mode: a truly bare draft (empty universe, no label) used
        to fall into a second add-or-replace question; #190 says the answer
        appends."""
        from argus.agent_runtime.interpreter.readiness_helpers import (
            _bare_asset_answer_without_unevidenced_operation,
        )

        self._assert_typed_as_inclusion(
            _bare_asset_answer_without_unevidenced_operation(
                response=self._response(asset_universe=[], asset_universe_operation=None),
                request=self._request(),
                resolve_asset_candidate=self._resolver({"TSLA": "TSLA"}),
            )
        )

    def test_a_refine_act_does_not_block_the_bare_shape(self) -> None:
        from argus.agent_runtime.interpreter.readiness_helpers import (
            _bare_asset_answer_without_unevidenced_operation,
        )

        response = self._response()
        response = response.model_copy(
            update={"semantic_turn_act": "refine_current_idea"}
        )
        self._assert_typed_as_inclusion(
            _bare_asset_answer_without_unevidenced_operation(
                response=response,
                request=self._request(),
                resolve_asset_candidate=self._resolver({"TSLA": "TSLA"}),
            )
        )

    def test_an_answer_with_more_than_the_bare_mention_keeps_its_label(self) -> None:
        from argus.agent_runtime.interpreter.readiness_helpers import (
            _bare_asset_answer_without_unevidenced_operation,
        )

        request = _card_request("replace them all with TSLA")
        updated = _bare_asset_answer_without_unevidenced_operation(
            response=self._response(),
            request=request,
            resolve_asset_candidate=self._resolver({"TSLA": "TSLA"}),
        )
        draft = updated.candidate_strategy_draft
        assert draft.asset_universe_operation == "replace"
        assert "bare_asset_answer_typed_as_inclusion" not in updated.reason_codes


class TestBareAssetAnswerGatesArePinned:
    """Review round 1, finding 4: every eligibility gate survived mutation.
    One negative per gate, each asserting the response is returned unchanged
    and no receipt is stamped, so deleting any gate fails a test."""

    _resolver = staticmethod(TestBareAssetAnswerOperationLabel._resolver)
    _response = staticmethod(TestBareAssetAnswerOperationLabel._response)

    @staticmethod
    def _guard():
        from argus.agent_runtime.interpreter.readiness_helpers import (
            _bare_asset_answer_without_unevidenced_operation,
        )

        return _bare_asset_answer_without_unevidenced_operation

    def _assert_untouched(self, updated: Any, response: Any) -> None:
        assert updated is response
        assert "bare_asset_answer_typed_as_inclusion" not in updated.reason_codes

    def test_wrong_requested_field_is_untouched(self) -> None:
        request = _card_request("TSLA")
        request = InterpretationRequest(
            user=request.user,
            current_user_message=request.current_user_message,
            recent_thread_history=[],
            latest_task_snapshot=request.latest_task_snapshot,
            selected_thread_metadata={
                "requested_field": "date_range",
                "last_stage_outcome": "await_user_reply",
            },
        )
        response = self._response()
        self._assert_untouched(
            self._guard()(
                response=response,
                request=request,
                resolve_asset_candidate=self._resolver({"TSLA": "TSLA"}),
            ),
            response,
        )

    @pytest.mark.parametrize(
        "act",
        ["approval", "retry_failed_action", "new_idea", "educational_question", None],
    )
    def test_acts_outside_the_allow_list_fail_closed(self, act) -> None:
        response = self._response().model_copy(update={"semantic_turn_act": act})
        self._assert_untouched(
            self._guard()(
                response=response,
                request=_card_request("TSLA"),
                resolve_asset_candidate=self._resolver({"TSLA": "TSLA"}),
            ),
            response,
        )

    def test_a_typed_discovery_payload_is_untouched(self) -> None:
        from argus.agent_runtime.stages.interpret_types import AssetDiscoveryRequest

        response = self._response().model_copy(
            update={
                "asset_discovery": AssetDiscoveryRequest(
                    relationship="peer", anchor_symbols=["TSLA"]
                )
            }
        )
        self._assert_untouched(
            self._guard()(
                response=response,
                request=_card_request("TSLA"),
                resolve_asset_candidate=self._resolver({"TSLA": "TSLA"}),
            ),
            response,
        )

    def test_typed_exclusions_are_untouched(self) -> None:
        response = self._response(asset_exclusions=["AAPL"])
        self._assert_untouched(
            self._guard()(
                response=response,
                request=_card_request("TSLA"),
                resolve_asset_candidate=self._resolver({"TSLA": "TSLA"}),
            ),
            response,
        )

    @pytest.mark.parametrize("label", [None, "append"])
    def test_non_replace_labels_with_a_universe_are_untouched(self, label) -> None:
        """An append label is already the product rule, and an unlabeled
        non-empty draft takes the provider-resolution corridor unmodified;
        only a wipe-shaped replace guess or a truly bare draft rewrites."""
        response = self._response(asset_universe_operation=label)
        self._assert_untouched(
            self._guard()(
                response=response,
                request=_card_request("TSLA"),
                resolve_asset_candidate=self._resolver({"TSLA": "TSLA"}),
            ),
            response,
        )

    def test_a_single_asset_card_is_untouched(self) -> None:
        request = InterpretationRequest(
            user=UserState(user_id="user-recognition"),
            current_user_message="TSLA",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                )
            ),
            selected_thread_metadata={
                "requested_field": "asset_universe",
                "last_stage_outcome": "await_user_reply",
            },
        )
        response = self._response()
        self._assert_untouched(
            self._guard()(
                response=response,
                request=request,
                resolve_asset_candidate=self._resolver({"TSLA": "TSLA"}),
            ),
            response,
        )

    def test_an_unresolvable_answer_is_untouched(self) -> None:
        response = self._response()
        self._assert_untouched(
            self._guard()(
                response=response,
                request=_card_request("TSLA"),
                resolve_asset_candidate=self._resolver({}),
            ),
            response,
        )

    def test_an_answer_already_on_the_card_is_untouched(self) -> None:
        response = self._response(asset_universe=["MSFT"])
        self._assert_untouched(
            self._guard()(
                response=response,
                request=_card_request("MSFT"),
                resolve_asset_candidate=self._resolver({"MSFT": "MSFT"}),
            ),
            response,
        )

    def test_a_draft_naming_more_than_the_answer_is_untouched(self) -> None:
        response = self._response(asset_universe=["TSLA", "GOOGL"])
        self._assert_untouched(
            self._guard()(
                response=response,
                request=_card_request("TSLA"),
                resolve_asset_candidate=self._resolver({"TSLA": "TSLA"}),
            ),
            response,
        )

    def test_inclusions_beyond_the_answer_are_untouched(self) -> None:
        response = self._response(asset_inclusions=["TSLA", "GOOGL"])
        self._assert_untouched(
            self._guard()(
                response=response,
                request=_card_request("TSLA"),
                resolve_asset_candidate=self._resolver({"TSLA": "TSLA"}),
            ),
            response,
        )


class TestRoleConstraintEvidenceBounds:
    """Review round 1, findings 2/5/11: a materialized symbol needs typed
    evidence, a requested addition must land, and the swap-over-whole-set
    precedence is a written decision."""

    @staticmethod
    def _satisfied(**overrides: Any) -> bool:
        from argus.agent_runtime.interpreter.asset_role_constraints import (
            asset_role_constraints_satisfied,
        )

        params: dict[str, Any] = {
            "materialized": set(),
            "current": set(),
            "primary_requested": set(),
            "primary_inclusions": set(),
            "primary_exclusions": set(),
            "grounded": set(),
            "operation": None,
            "planned_asset_replacement": False,
        }
        params.update(overrides)
        return asset_role_constraints_satisfied(**params)

    def test_a_mention_is_not_an_addition(self) -> None:
        """'remove AAPL, it has been worse than NVDA lately' must not ship
        NVDA: grounded mentions are never acceptance slack."""
        assert not self._satisfied(
            materialized={"MSFT", "NVDA"},
            current={"AAPL", "MSFT"},
            primary_exclusions={"AAPL"},
            grounded={"AAPL", "NVDA"},
        )

    def test_a_requested_addition_must_land(self) -> None:
        """'add TSLA and GOOGL and drop AAPL' with GOOGL missing from the
        materialization is refused; with both landed it is accepted."""
        common: dict[str, Any] = {
            "current": {"AAPL", "MSFT"},
            "primary_requested": {"TSLA", "GOOGL"},
            "primary_exclusions": {"AAPL"},
            "grounded": {"AAPL", "TSLA", "GOOGL"},
        }
        assert not self._satisfied(materialized={"MSFT", "TSLA"}, **common)
        assert self._satisfied(materialized={"MSFT", "TSLA", "GOOGL"}, **common)

    def test_swap_precedence_over_whole_set_is_the_written_decision(self) -> None:
        """'drop AAPL, just use TSLA from now on' is refused and re-asked:
        the typed shape is identical to the locked compound-swap fixture
        with the opposite intent, and a re-ask beats a silent wipe. The
        module docstring owns this decision."""
        assert not self._satisfied(
            materialized={"TSLA"},
            current={"AAPL", "MSFT"},
            primary_requested={"TSLA"},
            primary_inclusions={"TSLA"},
            primary_exclusions={"AAPL"},
            grounded={"AAPL", "TSLA"},
            operation="replace",
        )

    def test_the_model_cannot_license_its_own_removal(self, monkeypatch) -> None:
        """Review finding 9: a hallucinated exclusion echoed into the
        universe copy must still need message or card grounding."""
        from argus.agent_runtime.interpreter import artifact_assumption_edit

        monkeypatch.setattr(
            artifact_assumption_edit,
            "_grounded_asset_symbols_from_message",
            lambda *_args, **_kwargs: set(),
        )
        primary = LLMStrategyDraft(
            raw_user_phrasing="make the rebalance monthly",
            asset_universe=["AAPL", "MSFT", "NVDA"],
            asset_exclusions=["NVDA"],
            asset_universe_operation="replace",
            field_provenance={"asset_universe": "explicit_user"},
        )
        plan = ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[EditOperation(op="remove", target="asset", symbols=["NVDA"])],
        )
        assert (
            artifact_assumption_edit.materialized_artifact_edit_targets(
                plan,
                request=_card_request("make the rebalance monthly"),
                primary_draft=primary,
            )
            is None
        )


@pytest.mark.asyncio
async def test_dca_seed_with_a_differing_budget_moves_the_budget(monkeypatch) -> None:
    """Review round 1, finding 1: '$20,000 to invest, starting with $5,000,
    buying monthly' must not fund a $20,000 monthly contribution. The seed
    keeps its role, the budget moves to total_capital, and the monthly
    amount is asked for."""
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
        interpreter_module, "invoke_openrouter_json_schema", fake_json_schema
    )
    message = (
        "I have $20,000 to invest over 2024, starting with $5,000 in VOO "
        "today, buying monthly"
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        user_goal_summary="Budget with a seed and monthly buys.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=message,
            strategy_type="dca_accumulation",
            asset_universe=["VOO"],
            asset_class="equity",
            cadence="monthly",
            initial_capital=5000.0,
            capital_amount=20000.0,
            field_provenance={
                "initial_capital": "starting_capital",
                "cadence": "explicit_user",
            },
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
    assert draft.total_capital == 20000.0
    assert draft.capital_amount is None
    assert audited.requires_clarification is True
    assert "capital_amount" in audited.missing_required_fields
    assert "dca_seed_provenance_kept_over_budget_audit" in audited.reason_codes
    assert "dca_total_budget_role_audited" in audited.reason_codes


def test_the_veto_routes_on_the_payload_alone(monkeypatch) -> None:
    """Review round 1, finding 6: a typed refusal payload owns its recovery
    route whatever act the model guessed; educational_question was one
    relabel away from the Trace-2 stats hijack."""

    async def _must_not_classify(**_kwargs: Any):
        raise AssertionError("a constraint-carrying turn must not be classified")

    monkeypatch.setattr(ka, "_classify_question", _must_not_classify)
    monkeypatch.setattr(ka, "research_rail_enabled", lambda: False)
    interpretation = _unsupported_interpretation(
        semantic_turn_act="educational_question",
        intent="conversation_followup",
    )
    assert _run_knowledge(interpretation) is None
    assert "unsupported_payload_kept_recovery_route" in interpretation.reason_codes


class TestContextExclusionMatchingAndReceipts:
    """Review round 1, findings 3/7/8: exclusion matching uses the provider
    record, the receipt asserts the outcome, and unsupported turns keep
    their asset facts."""

    APPLE_SPAN_ROW = {
        "raw_text": "Apple",
        "role": "traded_asset",
        "status": "resolved",
        "symbol": "AAPL",
        "asset_class": "equity",
        "name": "Apple Inc. Common Stock",
        "raw_symbol": "AAPL",
        "provider": "alpaca",
        "exchange": "AssetExchange.NASDAQ",
    }
    BTC_ROW = {
        "raw_text": "BTC-USD",
        "role": "traded_asset",
        "status": "resolved",
        "symbol": "BTC",
        "asset_class": "crypto",
        "name": "Bitcoin / US Dollar",
        "raw_symbol": "BTC/USD",
        "provider": "alpaca",
        "exchange": "AssetExchange.CRYPTO",
    }

    def test_an_exclusion_in_the_users_words_is_matched(self) -> None:
        normalized = response_with_provider_context_assets(
            _exclusion_response(asset_exclusions=["Apple"]),
            asset_resolution_context=_context([dict(self.APPLE_SPAN_ROW)]),
        )
        assert normalized.candidate_strategy_draft.asset_universe == []
        assert "context_asset_injection_respected_exclusion" in normalized.reason_codes

    def test_a_dash_form_crypto_exclusion_is_matched(self) -> None:
        normalized = response_with_provider_context_assets(
            _exclusion_response(asset_exclusions=["BTC-USD"]),
            asset_resolution_context=_context([dict(self.BTC_ROW)]),
        )
        assert normalized.candidate_strategy_draft.asset_universe == []
        assert "context_asset_injection_respected_exclusion" in normalized.reason_codes

    def test_the_receipt_asserts_the_outcome_not_the_attempt(self) -> None:
        """When the partial-preserve branch keeps the model-authored copy of
        the excluded symbol, no receipt may claim the exclusion was
        respected."""
        normalized = response_with_provider_context_assets(
            _exclusion_response(
                raw_user_phrasing="keep my AAPL and MSFT basket, minus AAPL",
                asset_universe=["AAPL", "MSFT"],
            ),
            asset_resolution_context=_context([dict(AAPL_ROW)]),
        )
        assert normalized.candidate_strategy_draft.asset_universe == [
            "AAPL",
            "MSFT",
        ]
        assert (
            "context_asset_injection_respected_exclusion" not in normalized.reason_codes
        )

    def test_filtering_does_not_fabricate_a_partial_context(self) -> None:
        """An unrelated draft asset plus an excluded mention must not ask the
        user to clarify the asset they just excluded."""
        normalized = response_with_provider_context_assets(
            _exclusion_response(asset_universe=["GLD"]),
            asset_resolution_context=_context([dict(AAPL_ROW)]),
        )
        assert normalized.requires_clarification is False
        assert normalized.ambiguous_fields == []

    def test_an_all_excluded_unsupported_turn_keeps_its_asset_facts(self) -> None:
        """Review finding 3: the refusal recovery needs the asset; an empty
        universe dissolves the turn into chat."""
        response = LLMInterpretationResponse(
            intent="unsupported_or_out_of_scope",
            task_relation="new_task",
            user_goal_summary="Unsupported request naming one asset.",
            candidate_strategy_draft=LLMStrategyDraft(
                asset_universe=["AAPL"],
                asset_exclusions=["AAPL"],
            ),
            semantic_turn_act="unsupported_request",
        )
        normalized = response_with_provider_context_assets(
            response,
            asset_resolution_context=_context([dict(AAPL_ROW)]),
            include_unsupported_request=True,
        )
        assert normalized.candidate_strategy_draft.asset_universe == ["AAPL"]
