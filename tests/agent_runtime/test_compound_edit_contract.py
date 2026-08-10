"""Compound edits never drop silently (§3.2) and scoped entry points widen (§3.3).

Every requested change is applied, or explicitly surfaced as not applied with
a reason; there is no third outcome. Card turns drop assistant prose, so the
disclosure is typed and rides the card the edit produced. A user who opened a
narrow entry point and asked for more gets the whole request served.
"""

from __future__ import annotations

from argus.agent_runtime.artifact_edit_planner import (
    ArtifactAssumptionEditPlan,
    EditOperation,
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
        assert "edit_disclosure" not in draft.extra_parameters, (
            "a fully applied compound edit needs no disclosure"
        )


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
        disclosure = response.candidate_strategy_draft.extra_parameters[
            "edit_disclosure"
        ]
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

        card = runtime_confirmation_card(
            {"stage_outcome": "await_approval", "confirmation_payload": payload},
            confirmation_id=str(payload.get("confirmation_id")),
            conversation_id="c1",
            language="en",
        )
        assert card is not None
        assert card["edit_disclosure"]["unapplied"][0]["target"] == "asset"
        assert "nothing to remove" in card["edit_disclosure"]["note"]
