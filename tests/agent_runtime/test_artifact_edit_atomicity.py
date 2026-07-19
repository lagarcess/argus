"""#238 — every edit corridor is one atomic typed patch over the canonical
artifact.

The planner's ResolvedArtifactEdit is the single typed patch contract. These
regressions pin: legacy flat plans and operation plans emit the identical
patch (one merge corridor, no drift); sparse patches carry only touched
fields; the summary applier preserves every untouched canonical field; the
clarification-answer corridor preserves the pending asset set (the
originally claimed overwrite does not reproduce and must stay that way);
and both edit surfaces share one asset symbol resolver.
"""

from __future__ import annotations

from argus.agent_runtime.artifact_edit_planner import (
    ArtifactAssumptionEditPlan,
    EditOperation,
)
from argus.agent_runtime.interpreter.artifact_assumption_edit import (
    _response_from_artifact_assumption_edit_plan,
)
from argus.agent_runtime.stages.interpret_internal.confirmation_artifact_edits import (
    apply_resolved_artifact_edit_to_strategy_summary,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import (
    StrategySummary,
    TaskSnapshot,
    UserState,
)


def _request_with_pending(strategy: StrategySummary) -> InterpretationRequest:
    return InterpretationRequest(
        current_user_message="add microsoft",
        latest_task_snapshot=TaskSnapshot(pending_strategy_summary=strategy),
        selected_thread_metadata={"requested_field": "assumption"},
        user=UserState(user_id="user-1", language_preference="en"),
    )


def _pending_aapl() -> StrategySummary:
    return StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Hold AAPL for a year.",
        asset_universe=["AAPL"],
        asset_class="equity",
        timeframe="1D",
        capital_amount=1000.0,
    )


def test_legacy_flat_plan_emits_the_same_typed_patch_as_operations() -> None:
    """One merge corridor: a legacy flat plan (no operations) and the
    equivalent typed-operation plan must emit the identical patch — the
    resolved final asset set as a replace, never a raw add fragment."""

    operations_plan = ArtifactAssumptionEditPlan(
        outcome="ready_to_confirm",
        operations=[EditOperation(op="add", target="asset", symbols=["MSFT"])],
    )
    legacy_plan = ArtifactAssumptionEditPlan(
        outcome="ready_to_confirm",
        asset_universe=["MSFT"],
        asset_universe_operation="add",
    )

    from_operations = _response_from_artifact_assumption_edit_plan(
        plan=operations_plan,
        request=_request_with_pending(_pending_aapl()),
    )
    from_legacy = _response_from_artifact_assumption_edit_plan(
        plan=legacy_plan,
        request=_request_with_pending(_pending_aapl()),
    )

    ops_draft = from_operations.candidate_strategy_draft
    legacy_draft = from_legacy.candidate_strategy_draft
    assert ops_draft.asset_universe == ["AAPL", "MSFT"]
    assert ops_draft.asset_universe_operation == "replace"
    assert legacy_draft.asset_universe == ops_draft.asset_universe
    assert legacy_draft.asset_universe_operation == (
        ops_draft.asset_universe_operation
    )
    assert legacy_draft.extra_parameters.get("asset_universe_operation") == (
        ops_draft.extra_parameters.get("asset_universe_operation")
    )


def test_capital_edit_emits_a_sparse_patch_only() -> None:
    """A capital-only edit touches capital and nothing else — untouched
    canonical fields are preserved by never appearing in the patch."""

    plan = ArtifactAssumptionEditPlan(
        outcome="ready_to_confirm",
        operations=[EditOperation(op="set", target="capital", number=5000)],
    )

    response = _response_from_artifact_assumption_edit_plan(
        plan=plan,
        request=_request_with_pending(_pending_aapl()),
    )

    draft = response.candidate_strategy_draft
    assert draft.initial_capital == 5000.0
    assert draft.field_provenance == {"initial_capital": "starting_capital"}
    assert draft.asset_universe == []
    assert draft.asset_universe_operation is None
    assert draft.comparison_baseline is None
    assert draft.timeframe is None
    assert draft.cadence is None
    assert draft.date_range is None


def test_summary_applier_preserves_every_untouched_field() -> None:
    """Applying a date-only patch to the canonical summary changes the date
    and provenance — and nothing else."""

    from argus.agent_runtime.artifact_edit_planner import apply_edit_operations
    from argus.agent_runtime.llm_interpreter_types import LLMDateRangeIntent

    candidate = StrategySummary(
        strategy_type="dca_accumulation",
        strategy_thesis="DCA into BTC.",
        asset_universe=["BTC"],
        asset_class="crypto",
        timeframe="1D",
        cadence="weekly",
        capital_amount=125.0,
        comparison_baseline="BTC",
        extra_parameters={"recurring_contribution": 125.0},
    )
    before = candidate.model_copy(deep=True)
    resolved = apply_edit_operations(
        [
            EditOperation(
                op="set",
                target="date_window",
                date_window=LLMDateRangeIntent(kind="calendar_year", year=2024),
            )
        ],
        current_asset_universe=candidate.asset_universe,
    )
    provenance: dict[str, str] = {}

    apply_resolved_artifact_edit_to_strategy_summary(
        resolved,
        candidate=candidate,
        field_provenance=provenance,
    )

    assert candidate.date_range is not None
    assert provenance == {"date_range": "explicit_user"}
    assert candidate.asset_universe == before.asset_universe
    assert candidate.strategy_type == before.strategy_type
    assert candidate.strategy_thesis == before.strategy_thesis
    assert candidate.timeframe == before.timeframe
    assert candidate.cadence == before.cadence
    assert candidate.capital_amount == before.capital_amount
    assert candidate.comparison_baseline == before.comparison_baseline
    assert candidate.extra_parameters.get("recurring_contribution") == 125.0


def test_pending_option_answer_preserves_the_pending_asset_set() -> None:
    """The originally claimed pending-option asset overwrite does not
    reproduce: a clarification answer patches only its named field and the
    pending asset universe survives byte-identical."""

    from argus.agent_runtime.interpreter.pending_option import (
        _apply_pending_response_option_replacement,
        _llm_draft_from_strategy_summary,
    )

    pending = StrategySummary(
        strategy_type="buy_and_hold",
        asset_universe=["AAPL", "MSFT", "NVDA"],
        asset_class="equity",
        timeframe="1D",
    )
    draft = _llm_draft_from_strategy_summary(pending)

    repaired = _apply_pending_response_option_replacement(
        draft=draft,
        replacement_values={
            "requested_field": "initial_capital",
            "initial_capital": 2500,
        },
        current_missing=["initial_capital"],
    )["draft"]

    assert repaired.initial_capital == 2500.0
    assert repaired.asset_universe == ["AAPL", "MSFT", "NVDA"]
    assert repaired.timeframe == "1D"


def test_both_edit_surfaces_share_one_asset_symbol_resolver() -> None:
    """One resolver, two importers — the interpreter and interpret-stage
    corridors cannot drift on symbol resolution."""

    from argus.agent_runtime.interpreter import artifact_assumption_edit
    from argus.agent_runtime.stages.interpret_internal import (
        confirmation_artifact_edits,
    )

    assert (
        artifact_assumption_edit.asset_edit_symbol_resolver
        is confirmation_artifact_edits.asset_edit_symbol_resolver
    )
