"""No recovery path may direct a user to a confirmation that is not live.

A snapshot can carry a leftover draft whose card was cancelled or superseded,
or an emptied draft beside a stale reference. Existence is not liveness:
every recovery surface reads through live_pending_confirmation, so Argus
never contradicts its own card. The end-to-end case is the observed defect:
cancel a draft, resend the idea while the interpreter is unavailable, and the
reply must not claim the visible confirmation is still ready.
"""

from __future__ import annotations

from typing import Any

import pytest
from argus.agent_runtime.recovery_messages import recovery_message
from argus.agent_runtime.stages.artifact_context import (
    has_pending_confirmation_context,
    live_pending_confirmation,
)
from argus.agent_runtime.stages.interpret_internal.offline_recovery import (
    _offline_recovery_message,
)
from argus.agent_runtime.state.models import (
    ArtifactReference,
    StrategySummary,
    TaskSnapshot,
)

GUIDANCE = recovery_message("confirmation_action_guidance", language="en")


def _pending() -> StrategySummary:
    return StrategySummary(
        strategy_type="buy_and_hold",
        asset_universe=["AAPL"],
        asset_class="equity",
        timeframe="1D",
        date_range={"start": "2023-01-02", "end": "2023-12-29"},
        capital_amount=10000,
    )


def _reference(**metadata_overrides: Any) -> ArtifactReference:
    metadata: dict[str, Any] = {
        "confirmation_id": "conf-live-1",
        "launch_payload_hash": "hash-1",
        "confirmation_payload": {
            "strategy": _pending().model_dump(mode="python"),
            "optional_parameters": {},
            "launch_payload": {},
            "validation": {"status": "ready_to_run", "executable": True},
        },
    }
    metadata.update(metadata_overrides)
    return ArtifactReference(
        artifact_kind="confirmation",
        artifact_id="conf-live-1",
        artifact_status="active",
        metadata=metadata,
    )


def _live_snapshot() -> TaskSnapshot:
    return TaskSnapshot(
        pending_strategy_summary=_pending(),
        active_confirmation_reference=_reference(),
    )


def _dead_snapshots() -> dict[str, TaskSnapshot]:
    cancelled_status = _reference()
    cancelled_status.artifact_status = "cancelled"
    cancelled_card = _reference(
        confirmation_card={
            "confirmation_id": "conf-live-1",
            "confirmation_state": "cancelled",
        }
    )
    superseded_card = _reference(
        confirmation_card={
            "confirmation_id": "conf-live-1",
            "confirmation_state": "superseded",
        }
    )
    return {
        # The post-cancel leftover: an emptied draft beside a reference.
        "emptied_draft": TaskSnapshot(
            pending_strategy_summary=StrategySummary(),
            active_confirmation_reference=_reference(),
        ),
        "cancelled_status": TaskSnapshot(
            pending_strategy_summary=_pending(),
            active_confirmation_reference=cancelled_status,
        ),
        "cancelled_card": TaskSnapshot(
            pending_strategy_summary=_pending(),
            active_confirmation_reference=cancelled_card,
        ),
        "superseded_card": TaskSnapshot(
            pending_strategy_summary=_pending(),
            active_confirmation_reference=superseded_card,
        ),
    }


class TestLivenessAccessor:
    def test_live_snapshot_is_live(self) -> None:
        live = live_pending_confirmation(_live_snapshot())
        assert live is not None
        assert live.pending.asset_universe == ["AAPL"]

    @pytest.mark.parametrize("name", sorted(_dead_snapshots()))
    def test_dead_snapshots_are_not_live(self, name: str) -> None:
        assert live_pending_confirmation(_dead_snapshots()[name]) is None

    @pytest.mark.parametrize("name", sorted(_dead_snapshots()))
    def test_dead_snapshots_offer_no_pending_context(self, name: str) -> None:
        snapshot = _dead_snapshots()[name]
        if name == "emptied_draft":
            assert not has_pending_confirmation_context(snapshot)
        else:
            # A dead card with a real leftover draft is not pending context
            # either: the reference is dead and the draft belongs to it.
            assert not has_pending_confirmation_context(
                TaskSnapshot(
                    pending_strategy_summary=None,
                    active_confirmation_reference=(
                        snapshot.active_confirmation_reference
                    ),
                )
            )

    def test_referenceless_draft_still_counts_as_pending_context(self) -> None:
        assert has_pending_confirmation_context(
            TaskSnapshot(pending_strategy_summary=_pending())
        )


class TestOfflineRecoveryNeverInvitesADeadCard:
    @pytest.mark.parametrize("name", sorted(_dead_snapshots()))
    def test_dead_confirmation_gets_honest_unavailable_copy(self, name: str) -> None:
        message = _offline_recovery_message(
            _dead_snapshots()[name],
            current_user_message="Buy and hold AAPL with $10,000 through 2023",
            language="en",
        )
        assert GUIDANCE not in message, (
            f"{name}: recovery invited the user to a confirmation that is not live"
        )
        assert "still ready" not in message

    def test_live_confirmation_still_gets_guidance(self) -> None:
        message = _offline_recovery_message(
            _live_snapshot(),
            current_user_message="Buy and hold AAPL with $10,000 through 2023",
            language="en",
        )
        assert GUIDANCE in message


class TestApprovalPathNeverSpeaksForADeadCard:
    @pytest.mark.parametrize("name", sorted(_dead_snapshots()))
    def test_pure_approval_on_dead_card_defers_to_interpretation(
        self, name: str
    ) -> None:
        from argus.agent_runtime.stages.interpret_actions import (
            approval_stage_result_if_applicable,
        )
        from argus.agent_runtime.stages.interpret_types import InterpretDecision
        from argus.agent_runtime.state.models import ResponseProfile, RunState

        snapshot = _dead_snapshots()[name]
        decision = InterpretDecision(
            intent="conversation_followup",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="yes",
            candidate_strategy_draft=StrategySummary(),
            missing_required_fields=[],
            confidence=0.9,
            arbitration_mode="deterministic",
            reason_codes=[],
            effective_response_profile=ResponseProfile(
                effective_tone="friendly",
                effective_verbosity="medium",
                effective_expertise_mode="beginner",
            ),
            semantic_turn_act="approval",
        )
        result = approval_stage_result_if_applicable(
            decision=decision,
            snapshot=snapshot,
            state=RunState.new(current_user_message="yes", recent_thread_history=[]),
            selected_thread_metadata={},
            language="en",
        )
        if result is not None:
            response = str(result.stage_patch.get("assistant_response") or "")
            assert GUIDANCE not in response, (
                f"{name}: approval path invited the user to a dead confirmation"
            )


def test_cancel_then_resend_never_claims_the_card_is_ready() -> None:
    """The observed defect, end to end through the real runtime.

    Plant a confirmation, cancel it through the real structured-action stage,
    then resend the idea with the interpreter unavailable (no provider key in
    this environment). The reply must not speak for the cancelled card.
    """
    from argus.agent_runtime.stages.interpret_actions import (
        structured_action_stage_result_if_applicable,
    )
    from argus.agent_runtime.state.models import RunState, StructuredActionContext

    snapshot = _live_snapshot()
    cancel_state = RunState.new(
        current_user_message="Cancel",
        recent_thread_history=[],
        action_context=StructuredActionContext(
            type="cancel_confirmation",
            payload={"confirmation_id": "conf-live-1", "artifact_id": "conf-live-1"},
            presentation="confirmation",
        ),
    )
    cancel_result = structured_action_stage_result_if_applicable(
        state=cancel_state,
        snapshot=snapshot,
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        language="en",
    )
    assert cancel_result is not None
    assert cancel_result.outcome == "ready_to_respond"
    cancelled_draft = StrategySummary.model_validate(
        cancel_result.stage_patch["candidate_strategy_draft"]
    )
    # The post-cancel snapshot as a later recovery path would see it when the
    # emptied draft leaks through beside the old reference.
    post_cancel = TaskSnapshot(
        pending_strategy_summary=cancelled_draft,
        active_confirmation_reference=snapshot.active_confirmation_reference,
    )
    assert live_pending_confirmation(post_cancel) is None
    message = _offline_recovery_message(
        post_cancel,
        current_user_message="Buy and hold AAPL with $10,000 through 2023",
        language="en",
    )
    assert GUIDANCE not in message
    assert "still ready" not in message
