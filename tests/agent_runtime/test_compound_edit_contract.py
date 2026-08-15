"""Compound edits never drop silently (§3.2) and scoped entry points widen (§3.3).

Every requested change is applied, or explicitly surfaced as not applied with
a reason; there is no third outcome. Card turns drop assistant prose, so the
disclosure is typed and rides the card the edit produced. A user who opened a
narrow entry point and asked for more gets the whole request served.
"""

from __future__ import annotations

import asyncio

from argus.agent_runtime.artifact_edit_planner import (
    ArtifactAssumptionEditPlan,
    EditOperation,
    _completed_with_stated_operations,
    plan_artifact_assumption_edit,
)
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.interpreter.artifact_assumption_edit import (
    ARTIFACT_EDIT_PENDING_FIELDS,
    _response_from_artifact_assumption_edit_plan,
)
from argus.agent_runtime.llm_interpreter_types import LLMDateRangeIntent
from argus.agent_runtime.stages.confirm import confirm_stage
from argus.agent_runtime.stages.interpret_types import (
    InterpretationRequest,
    UserState,
)
from argus.agent_runtime.state.models import (
    ArtifactReference,
    RunState,
    StrategySummary,
    TaskSnapshot,
)
from argus.api.chat.confirmation import runtime_confirmation_card


def _snapshot() -> TaskSnapshot:
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        asset_universe=["NFLX"],
        asset_class="equity",
        timeframe="1D",
        date_range={"start": "2023-01-02", "end": "2023-06-30"},
        capital_amount=10000,
    )
    return TaskSnapshot(
        pending_strategy_summary=pending,
        active_confirmation_reference=ArtifactReference(
            artifact_kind="confirmation",
            artifact_id="conf-1",
            metadata={"confirmation_id": "conf-1"},
        ),
    )


def _request(message: str, requested_field: str | None = None) -> InterpretationRequest:
    metadata: dict[str, object] = {}
    if requested_field is not None:
        metadata = {
            "requested_field": requested_field,
            "last_stage_outcome": "await_user_reply",
        }
    return InterpretationRequest(
        user=UserState(user_id="user-32"),
        current_user_message=message,
        recent_thread_history=[],
        latest_task_snapshot=_snapshot(),
        selected_thread_metadata=metadata,
    )


class TestScopedEntryPointsWiden:
    def test_broadened_date_reply_reaches_the_planner(self) -> None:
        """§3.3: a change-dates prompt answered with more than a date widens;
        a pure date answer keeps its specialized paths."""
        from argus.agent_runtime.interpreter.artifact_assumption_edit import (
            _scoped_date_reply_carries_broader_edit,
        )
        from argus.agent_runtime.llm_interpreter_types import LLMStrategyDraft

        request = _request("2024, add MSFT and $5,000", requested_field="date_range")
        broadened = LLMStrategyDraft(
            date_range={"start": "2024-01-02", "end": "2024-12-31"},
            capital_amount=5000,
            field_provenance={
                "date_range": "explicit_user",
                "capital_amount": "starting_capital",
            },
        )
        assert _scoped_date_reply_carries_broader_edit(request, broadened)

        pure_date = LLMStrategyDraft(
            date_range={"start": "2024-01-02", "end": "2024-12-31"},
            field_provenance={"date_range": "explicit_user"},
        )
        assert not _scoped_date_reply_carries_broader_edit(request, pure_date)
        assert "date_range" not in ARTIFACT_EDIT_PENDING_FIELDS

    def test_broadened_reply_after_change_dates_applies_every_change(self) -> None:
        """The alpha regression: tapped change dates, then asked for more."""
        plan = ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(
                    op="set",
                    target="date_window",
                    date_window=LLMDateRangeIntent(
                        kind="explicit_range",
                        start="2024-01-02",
                        end="2024-12-31",
                        confidence=1.0,
                    ),
                ),
                EditOperation(op="add", target="asset", symbols=["MSFT"]),
                EditOperation(op="set", target="capital", number=5000),
            ],
        )
        response = _response_from_artifact_assumption_edit_plan(
            plan=plan,
            request=_request(
                "use 2024, add MSFT, and make it $5,000",
                requested_field="date_range",
            ),
        )
        draft = response.candidate_strategy_draft
        assert response.requires_clarification is False
        assert draft.date_range == {"start": "2024-01-02", "end": "2024-12-31"}
        assert "MSFT" in draft.asset_universe
        # The planner layer carries capital as initial_capital; the turn-level
        # merge maps it onto the pending strategy's capital_amount.
        assert draft.initial_capital == 5000
        assert (
            "edit_disclosure" not in draft.extra_parameters
        ), "a fully applied compound edit needs no disclosure"


class TestUnappliedChangesAreDisclosed:
    def _mixed_plan(self) -> ArtifactAssumptionEditPlan:
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(op="set", target="capital", number=5000),
                # Removing an asset that is not in the basket cannot apply.
                EditOperation(op="remove", target="asset", symbols=["TSLA"]),
            ],
            assistant_response="TSLA is not part of this test, so there was nothing to remove.",
        )

    def test_mixed_edit_carries_a_typed_disclosure(self) -> None:
        response = _response_from_artifact_assumption_edit_plan(
            plan=self._mixed_plan(),
            request=_request("make it $5,000 and drop TSLA"),
        )
        draft = response.candidate_strategy_draft
        assert draft.initial_capital == 5000
        disclosure = draft.extra_parameters["edit_disclosure"]
        assert disclosure["unapplied"] == [
            {"op": "remove", "target": "asset", "reason": "unsupported_operation"}
        ]
        assert "nothing to remove" in disclosure["note"]

    def test_note_only_mixed_edit_still_discloses(self) -> None:
        """The planner names an unsupported part in prose without an op."""
        plan = ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[EditOperation(op="set", target="capital", number=5000)],
            assistant_response="I cannot add short selling; this stays long only.",
        )
        response = _response_from_artifact_assumption_edit_plan(
            plan=plan,
            request=_request("make it $5,000 and short it on the way down"),
        )
        disclosure = response.candidate_strategy_draft.extra_parameters["edit_disclosure"]
        assert disclosure["unapplied"] == []
        assert "short selling" in disclosure["note"]

    def test_disclosure_rides_the_card_and_does_not_stick(self) -> None:
        """Confirm pops the disclosure into the card payload, single-use."""
        response = _response_from_artifact_assumption_edit_plan(
            plan=self._mixed_plan(),
            request=_request("make it $5,000 and drop TSLA"),
        )
        merged = _snapshot().pending_strategy_summary.model_copy(deep=True)
        merged.capital_amount = 5000
        merged.extra_parameters["edit_disclosure"] = (
            response.candidate_strategy_draft.extra_parameters["edit_disclosure"]
        )
        state = RunState.new(
            current_user_message="make it $5,000 and drop TSLA",
            recent_thread_history=[],
        )
        state = state.model_copy(update={"candidate_strategy_draft": merged})
        result = confirm_stage(
            state=state,
            contract=build_default_capability_contract(),
            language="en",
        )
        assert result.outcome == "await_approval"
        payload = result.stage_patch["confirmation_payload"]
        assert payload["edit_disclosure"]["unapplied"][0]["target"] == "asset"
        assert "edit_disclosure" not in (
            payload["strategy"].get("extra_parameters") or {}
        ), "the disclosure describes this transition only and must not persist"

        # The runtime state channel validates the payload into a typed model;
        # a field the model does not declare dies here, invisibly to tests
        # that read the raw stage patch. Round-trip it like the server does.
        from argus.agent_runtime.state.models import ConfirmationPayload

        channel_payload = {
            **payload,
            **ConfirmationPayload.model_validate(payload).model_dump(mode="python"),
        }
        assert (
            channel_payload["edit_disclosure"] == payload["edit_disclosure"]
        ), "the state channel must carry the disclosure, not strip it"

        card = runtime_confirmation_card(
            {"stage_outcome": "await_approval", "confirmation_payload": channel_payload},
            confirmation_id=str(payload.get("confirmation_id")),
            conversation_id="c1",
            language="en",
        )
        assert card is not None
        assert card["edit_disclosure"]["unapplied"][0]["target"] == "asset"
        assert "nothing to remove" in card["edit_disclosure"]["note"]

    def test_fully_refused_edit_reissues_the_card_with_the_disclosure(self) -> None:
        """ "Quita TSLA" with no TSLA in the basket: the planner reads the
        removal correctly, the resolver refuses it, and the reply is the same
        card carrying the typed refusal, never a clean re-issue and never an
        invented TSLA card."""
        plan = ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[EditOperation(op="remove", target="asset", symbols=["TSLA"])],
            assistant_response="TSLA no es parte de esta prueba.",
        )
        response = _response_from_artifact_assumption_edit_plan(
            plan=plan,
            request=_request("Quita TSLA"),
        )
        assert response.requires_clarification is False
        assert response.semantic_turn_act == "answer_pending_need"
        draft = response.candidate_strategy_draft
        assert "TSLA" not in (draft.asset_universe or [])
        disclosure = draft.extra_parameters["edit_disclosure"]
        assert disclosure["unapplied"] == [
            {"op": "remove", "target": "asset", "reason": "unsupported_operation"}
        ]
        assert "TSLA" in disclosure["note"]


class TestStatedCostsCannotDropSilently:
    """A stated cost the planner leaves out of its operation list must still
    enter the pipeline: it becomes a required coverage target from the
    message's own numeric anchor, the plan is completed from the primary
    interpretation's typed value, and a refused value is disclosed rather
    than silently missing (the live $9,000 + 90% slippage leak)."""

    MESSAGE = "Make it $9,000 and set slippage to 90%"

    def _primary(self):
        from argus.agent_runtime.llm_interpreter_types import LLMStrategyDraft

        return LLMStrategyDraft(
            capital_amount=9000,
            extra_parameters={"slippage": 0.9},
            field_provenance={"capital_amount": "starting_capital"},
        )

    def test_message_anchored_cost_is_a_required_target(self) -> None:
        from argus.agent_runtime.interpreter.artifact_assumption_edit import (
            _current_artifact_strategy,
            _required_edit_targets_from_primary_draft,
        )

        request = _request(self.MESSAGE)
        targets = _required_edit_targets_from_primary_draft(
            self._primary(),
            current_strategy=_current_artifact_strategy(request),
            request=request,
        )
        assert "slippage" in targets, (
            "audit-time provenance does not exist at planner time; the "
            "message anchor must be enough"
        )
        assert "capital" in targets

    def test_capital_only_plan_is_completed_and_discloses_the_refusal(self) -> None:
        import argus.agent_runtime.artifact_edit_planner as planner_module
        from argus.agent_runtime.interpreter.artifact_assumption_edit import (
            _current_artifact_strategy,
            _required_edit_targets_from_primary_draft,
            materialized_artifact_edit_targets,
        )
        from argus.agent_runtime.interpreter.edit_completion import (
            stated_edit_operations,
        )

        request = _request(self.MESSAGE)
        primary = self._primary()
        current = _current_artifact_strategy(request)
        capital_only = ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[EditOperation(op="set", target="capital", number=9000)],
        )

        async def fake_invoke(**kwargs):
            return capital_only

        original = planner_module.invoke_openrouter_json_schema
        planner_module.invoke_openrouter_json_schema = fake_invoke
        try:
            plan = asyncio.run(
                plan_artifact_assumption_edit(
                    current_user_message=self.MESSAGE,
                    prior_strategy=current.model_dump(mode="json"),
                    active_confirmation=None,
                    preferred_model="test-model",
                    required_targets=_required_edit_targets_from_primary_draft(
                        primary, current_strategy=current, request=request
                    ),
                    materialized_targets_for_plan=(
                        lambda candidate: materialized_artifact_edit_targets(
                            candidate, request=request, primary_draft=primary
                        )
                    ),
                    stated_operations=stated_edit_operations(
                        primary, current_strategy=current, request=request
                    ),
                )
            )
        finally:
            planner_module.invoke_openrouter_json_schema = original

        assert plan is not None, (
            "a plan omitting a stated cost must be completed, not rejected "
            "into a silent fallback"
        )
        assert {operation.target for operation in plan.operations} == {
            "capital",
            "slippage",
        }
        response = _response_from_artifact_assumption_edit_plan(
            plan=plan, request=request, primary_draft=primary
        )
        draft = response.candidate_strategy_draft
        assert draft.initial_capital == 9000
        disclosure = draft.extra_parameters["edit_disclosure"]
        assert [entry["target"] for entry in disclosure["unapplied"]] == ["slippage"]
        assert "slippage" not in draft.extra_parameters

    def test_completion_leaves_clarification_and_flat_plans_alone(self) -> None:
        stated = [EditOperation(op="set", target="slippage", number=0.9)]
        clarification = ArtifactAssumptionEditPlan(
            outcome="needs_clarification",
            operations=[EditOperation(op="set", target="capital", number=9000)],
            assistant_response="Which slippage did you mean?",
        )
        assert _completed_with_stated_operations(clarification, stated) is (
            clarification
        )
        flat_only = ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm", initial_capital=9000
        )
        assert _completed_with_stated_operations(flat_only, stated) is flat_only

    def test_over_cap_stated_cost_is_disclosed_not_stalled(self) -> None:
        """The free-form route's cost audit refuses an unmodelable stated
        value the same way the planner route does: disclose on the card and
        let the rest of the edit land, instead of stalling the whole turn
        behind a clarification the stage then swallows."""
        from argus.agent_runtime.interpreter.audits import (
            StatedRunFieldFidelityAudit,
        )
        from argus.agent_runtime.interpreter.execution_cost_fidelity import (
            apply_cost_fidelity,
        )
        from argus.agent_runtime.llm_interpreter_types import (
            LLMInterpretationResponse,
            LLMStrategyDraft,
        )

        response = LLMInterpretationResponse(
            intent="strategy_drafting",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="edit capital and slippage",
            semantic_turn_act="refine_current_idea",
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing=self.MESSAGE,
                strategy_type="buy_and_hold",
                asset_universe=["NFLX"],
                capital_amount=9000,
                extra_parameters={"slippage": 0.9},
            ),
        )
        audit = StatedRunFieldFidelityAudit.model_validate(
            {"slippage": {"rate": 0.9, "evidence_span": "set slippage to 90%"}}
        )
        changed = apply_cost_fidelity(response, audit, self.MESSAGE, None)
        assert changed is True
        assert response.requires_clarification is False, (
            "a disclosed refusal owns the outcome; the stage would swallow a "
            "clarification about a non-contract field anyway"
        )
        draft = response.candidate_strategy_draft
        assert "slippage" not in draft.extra_parameters
        disclosure = draft.extra_parameters["edit_disclosure"]
        assert disclosure["unapplied"] == [
            {"op": "set", "target": "slippage", "reason": "unsupported_value"}
        ]
        assert "execution_cost_refusal_disclosed" in response.reason_codes

    def test_value_disagreement_still_asks_instead_of_refusing(self) -> None:
        """A modelable value the draft transcribed differently is an
        ambiguity, not a refusal: asking is honest, disclosing 'cannot' is
        not."""
        from argus.agent_runtime.interpreter.audits import (
            StatedRunFieldFidelityAudit,
        )
        from argus.agent_runtime.interpreter.execution_cost_fidelity import (
            apply_cost_fidelity,
        )
        from argus.agent_runtime.llm_interpreter_types import (
            LLMInterpretationResponse,
            LLMStrategyDraft,
        )

        message = "Use a 0.2% fee"
        response = LLMInterpretationResponse(
            intent="strategy_drafting",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="edit fees",
            semantic_turn_act="refine_current_idea",
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing=message,
                strategy_type="buy_and_hold",
                asset_universe=["NFLX"],
                extra_parameters={"fee_rate": 0.2},
            ),
        )
        audit = StatedRunFieldFidelityAudit.model_validate(
            {"fee": {"rate": 0.002, "evidence_span": "0.2% fee"}}
        )
        apply_cost_fidelity(response, audit, message, None)
        assert response.requires_clarification is True
        assert "edit_disclosure" not in (
            response.candidate_strategy_draft.extra_parameters
        )

    def test_disclosure_describes_one_transition_only(self) -> None:
        from argus.agent_runtime.stages.interpret_internal.contextual_merge import (
            _merge_contextual_extra_parameters,
        )

        stale = {"unapplied": [{"op": "set", "target": "slippage"}]}
        merged = _merge_contextual_extra_parameters(
            base={"edit_disclosure": stale, "fee_rate": 0.001},
            incoming={},
        )
        assert "edit_disclosure" not in merged
        assert merged["fee_rate"] == 0.001

        fresh = {"unapplied": [{"op": "set", "target": "fees"}]}
        merged = _merge_contextual_extra_parameters(
            base={"edit_disclosure": stale},
            incoming={"edit_disclosure": fresh},
        )
        assert merged["edit_disclosure"] == fresh

    def test_refused_cost_op_counts_as_covered(self) -> None:
        from argus.agent_runtime.interpreter.artifact_assumption_edit import (
            materialized_artifact_edit_targets,
        )

        request = _request(self.MESSAGE)
        plan = ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(op="set", target="capital", number=9000),
                EditOperation(op="set", target="slippage", number=0.9),
            ],
        )
        covered = materialized_artifact_edit_targets(
            plan, request=request, primary_draft=self._primary()
        )
        assert covered is not None
        assert "slippage" in covered, (
            "coverage guards against silence; a refusal recorded for card "
            "disclosure is not silence"
        )


class TestAcceptedOperationsLandOrFailLoudly:
    """Issue #498: every operation the planner accepted appears in the
    resulting card, or the whole request fails loudly. Partial application
    is unrepresentable: the materializer refuses a plan whose accepted
    operations do not all land, and the union of the primary read and the
    plan completes a half-built operation list before it can ship."""

    MESSAGE = "change the benchmark to QQQ and change the start to April 1, 2026"

    @staticmethod
    def _unresolvable_date_op() -> EditOperation:
        # Accepted by the applier (a date_window payload exists), refused by
        # date resolution (an endpoint patch with no date to patch in).
        return EditOperation(
            op="set",
            target="date_window",
            date_window=LLMDateRangeIntent(kind="endpoint_patch", endpoint="start"),
        )

    @staticmethod
    def _indicator_op() -> EditOperation:
        # Accepted by the applier, dropped by materialization on a card whose
        # strategy has no active RSI confirmation.
        return EditOperation(
            op="set", target="indicator_entry_threshold", number=25
        )

    def test_partially_materialized_plan_is_refused(self) -> None:
        from argus.agent_runtime.interpreter.artifact_assumption_edit import (
            materialized_artifact_edit_targets,
        )

        request = _request(self.MESSAGE)
        for vanishing in (self._unresolvable_date_op(), self._indicator_op()):
            plan = ArtifactAssumptionEditPlan(
                outcome="ready_to_confirm",
                operations=[
                    EditOperation(op="set", target="benchmark", value="QQQ"),
                    vanishing,
                ],
            )
            assert (
                materialized_artifact_edit_targets(plan, request=request) is None
            ), f"{vanishing.target}: a half-materialized plan must be refused"

    def test_fully_refused_plan_is_not_partial(self) -> None:
        """All-or-nothing: when nothing lands, the all-refused handling owns
        the turn (the #271 clarification), not the partial refusal."""
        from argus.agent_runtime.interpreter.artifact_assumption_edit import (
            materialized_artifact_edit_targets,
        )

        request = _request("set the RSI entry to 25")
        plan = ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[self._indicator_op()],
        )
        covered = materialized_artifact_edit_targets(plan, request=request)
        assert covered == set()
        response = _response_from_artifact_assumption_edit_plan(
            plan=plan, request=request
        )
        assert response.requires_clarification is True

    def test_planner_refuses_every_partially_materializing_candidate(self) -> None:
        import argus.agent_runtime.artifact_edit_planner as planner_module
        from argus.agent_runtime.interpreter.artifact_assumption_edit import (
            _current_artifact_strategy,
            materialized_artifact_edit_targets,
        )

        request = _request(self.MESSAGE)
        current = _current_artifact_strategy(request)
        partial = ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(op="set", target="benchmark", value="QQQ"),
                self._unresolvable_date_op(),
            ],
        )

        async def fake_invoke(**kwargs):
            return partial

        original = planner_module.invoke_openrouter_json_schema
        planner_module.invoke_openrouter_json_schema = fake_invoke
        try:
            plan = asyncio.run(
                plan_artifact_assumption_edit(
                    current_user_message=self.MESSAGE,
                    prior_strategy=current.model_dump(mode="json"),
                    active_confirmation=None,
                    preferred_model="test-model",
                    materialized_targets_for_plan=(
                        lambda candidate: materialized_artifact_edit_targets(
                            candidate, request=request
                        )
                    ),
                )
            )
        finally:
            planner_module.invoke_openrouter_json_schema = original

        assert plan is None, (
            "an accepted operation that cannot materialize fails the whole "
            "plan; no model may ship the applicable half"
        )

    def test_offline_planned_edit_declines_partial_application(self) -> None:
        from argus.agent_runtime.stages.interpret_internal.interpreter_unavailable_continuity import (
            planned_active_confirmation_edit_interpretation,
        )

        snapshot = _snapshot()

        async def half_plan(**kwargs):
            return ArtifactAssumptionEditPlan(
                outcome="ready_to_confirm",
                operations=[
                    EditOperation(op="set", target="benchmark", value="QQQ"),
                    self._unresolvable_date_op(),
                ],
            )

        interpretation = asyncio.run(
            planned_active_confirmation_edit_interpretation(
                snapshot=snapshot,
                current_user_message=self.MESSAGE,
                resolve_asset_candidate=lambda *a, **k: None,
                plan_artifact_assumption_edit_fn=half_plan,
            )
        )
        assert interpretation is None, (
            "the offline continuity path must decline a half-applied summary, "
            "not issue a card missing part of the request"
        )

    def test_primary_read_completes_a_plan_that_dropped_a_half(self) -> None:
        """The union of the two structured reads: a typed fact the primary
        interpretation extracted enters a plan that omitted it."""
        import argus.agent_runtime.artifact_edit_planner as planner_module
        from argus.agent_runtime.interpreter.artifact_assumption_edit import (
            _current_artifact_strategy,
            _required_edit_targets_from_primary_draft,
            materialized_artifact_edit_targets,
        )
        from argus.agent_runtime.interpreter.edit_completion import (
            stated_edit_operations,
        )
        from argus.agent_runtime.llm_interpreter_types import LLMStrategyDraft

        request = _request(self.MESSAGE)
        current = _current_artifact_strategy(request)
        primary = LLMStrategyDraft(
            comparison_baseline="QQQ",
            date_range_intent=LLMDateRangeIntent(
                kind="endpoint_patch", endpoint="start", start="2026-04-01"
            ),
            field_provenance={
                "comparison_baseline": "explicit_user",
                "date_range": "explicit_user",
            },
        )
        benchmark_dropped = ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(
                    op="set",
                    target="date_window",
                    date_window=LLMDateRangeIntent(
                        kind="endpoint_patch", endpoint="start", start="2026-04-01"
                    ),
                )
            ],
        )

        async def fake_invoke(**kwargs):
            return benchmark_dropped

        original = planner_module.invoke_openrouter_json_schema
        planner_module.invoke_openrouter_json_schema = fake_invoke
        try:
            plan = asyncio.run(
                plan_artifact_assumption_edit(
                    current_user_message=self.MESSAGE,
                    prior_strategy=current.model_dump(mode="json"),
                    active_confirmation=None,
                    preferred_model="test-model",
                    required_targets=_required_edit_targets_from_primary_draft(
                        primary, current_strategy=current, request=request
                    ),
                    materialized_targets_for_plan=(
                        lambda candidate: materialized_artifact_edit_targets(
                            candidate, request=request, primary_draft=primary
                        )
                    ),
                    stated_operations=stated_edit_operations(
                        primary, current_strategy=current, request=request
                    ),
                )
            )
        finally:
            planner_module.invoke_openrouter_json_schema = original

        assert plan is not None
        assert {operation.target for operation in plan.operations} == {
            "date_window",
            "benchmark",
        }
        response = _response_from_artifact_assumption_edit_plan(
            plan=plan, request=request
        )
        draft = response.candidate_strategy_draft
        assert draft.comparison_baseline == "QQQ"
        assert (draft.date_range or {}).get("start") == "2026-04-01"

    def test_completion_emits_a_receipt_naming_the_targets(self) -> None:
        """The union is a redundancy layer over the planner; every injection
        must be observable or planner decay hides behind the safety net."""
        from argus.agent_runtime.artifact_edit_planner import (
            _completed_with_stated_operations,
        )
        from loguru import logger as loguru_logger

        stated = [EditOperation(op="set", target="benchmark", value="QQQ")]
        plan = ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(
                    op="set",
                    target="date_window",
                    date_window=LLMDateRangeIntent(
                        kind="endpoint_patch", endpoint="start", start="2026-04-01"
                    ),
                )
            ],
        )
        captured: list[str] = []
        handler_id = loguru_logger.add(
            lambda message: captured.append(str(message)), level="INFO"
        )
        try:
            completed = _completed_with_stated_operations(plan, stated)
            covered = _completed_with_stated_operations(completed, stated)
        finally:
            loguru_logger.remove(handler_id)

        assert {operation.target for operation in completed.operations} == {
            "date_window",
            "benchmark",
        }
        assert covered is completed
        receipts = [
            line for line in captured if "Artifact edit plan completed" in line
        ]
        assert len(receipts) == 1, (
            "one receipt per injection, none when the plan already covers"
        )
        assert "benchmark" in receipts[0]
