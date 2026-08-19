"""Guards for the prebaked-chip completion path.

A chip is a fully specified, pre-tested ask. Its facts (the asset, the
cadence, the window) are captured on the first turn and carried in the
pending strategy; every later layer must treat a follow-up answer as adding
to those facts, never as grounds to discard the turn.

Production 2026-08-19 (chip q3 -> "How much should I use?" -> "200$"): the
DCA budget audit re-roled the answer into ``total_capital``, and the replay
detector, blind to every money role except ``capital_amount``, judged the
audited draft a replay of the pending strategy and killed the candidate.
With the turn's call allowance already spent on audits, the last-resort
repair was permit-denied and the turn died in the no-progress fallback.
"""

from __future__ import annotations

import pytest
from argus.agent_runtime import turn_execution
from argus.agent_runtime.interpreter.draft_shape import (
    _response_replays_prior_strategy_without_current_turn_update,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import (
    RunState,
    StrategySummary,
    TaskSnapshot,
    UserState,
)

CHIP_PENDING_STRATEGY = StrategySummary(
    strategy_type="dca_accumulation",
    strategy_thesis="Buy Coca-Cola every month for the last five years.",
    asset_universe=["KO"],
    asset_class="equity",
    cadence="monthly",
    date_range={"start": "2021-08-19", "end": "2026-08-19"},
)


def _request(message: str) -> InterpretationRequest:
    return InterpretationRequest(
        current_user_message=message,
        latest_task_snapshot=TaskSnapshot(
            latest_task_type="strategy_drafting",
            completed=False,
            pending_needs=["sizing_amount"],
            last_unresolved_follow_up="How much should I use?",
            pending_strategy_summary=CHIP_PENDING_STRATEGY,
        ),
        selected_thread_metadata={
            "ui_language": "en",
            "last_stage_outcome": "await_user_reply",
            "requested_field": "capital_amount",
        },
        user=UserState(
            user_id="guard",
            language_preference="en",
            expertise_level="beginner",
        ),
    )


def _pending_shaped_draft(**overrides: object) -> LLMStrategyDraft:
    payload: dict[str, object] = {
        "raw_user_phrasing": "200$",
        "strategy_type": "dca_accumulation",
        "strategy_thesis": "Buy Coca-Cola every month for the last five years.",
        "asset_universe": ["KO"],
        "asset_class": "equity",
        "cadence": "monthly",
        "date_range": {"start": "2021-08-19", "end": "2026-08-19"},
    }
    payload.update(overrides)
    return LLMStrategyDraft.model_validate(payload)


def _response(draft: LLMStrategyDraft, **overrides: object) -> LLMInterpretationResponse:
    payload: dict[str, object] = {
        "intent": "strategy_drafting",
        "task_relation": "continue",
        "requires_clarification": False,
        "user_goal_summary": "200$",
        "candidate_strategy_draft": draft,
        "semantic_turn_act": "answer_pending_need",
    }
    payload.update(overrides)
    return LLMInterpretationResponse.model_validate(payload)


class TestMoneyRoleAnswersAreCurrentTurnUpdates:
    """An answer whose only new fact is money, in any role, is an update."""

    @pytest.mark.parametrize(
        "money_field",
        ["capital_amount", "recurring_contribution", "initial_capital", "total_capital"],
    )
    def test_money_role_answer_is_not_a_replay(self, money_field: str) -> None:
        draft = _pending_shaped_draft(**{money_field: 200.0})
        assert not _response_replays_prior_strategy_without_current_turn_update(
            response=_response(draft),
            request=_request("200$"),
        )

    def test_budget_audited_answer_is_not_a_replay(self) -> None:
        # The exact production shape: the budget audit moved the amount into
        # total_capital, cleared capital_amount, and re-asked for the amount.
        draft = _pending_shaped_draft(
            total_capital=200.0,
            field_provenance={"total_capital": "total_budget"},
        )
        response = _response(
            draft,
            requires_clarification=True,
            semantic_turn_act="new_idea",
            task_relation="new_task",
            missing_required_fields=["capital_amount"],
            reason_codes=[
                "dca_contract_audit",
                "dca_total_budget_role_audited",
                "dca_budget_recurring_copy_cleared",
            ],
        )
        assert not _response_replays_prior_strategy_without_current_turn_update(
            response=response,
            request=_request("200$"),
        )

    def test_actual_replay_is_still_detected(self) -> None:
        # The detector keeps its purpose: a draft that only restates the
        # pending strategy, with no new fact anywhere, is a replay.
        assert _response_replays_prior_strategy_without_current_turn_update(
            response=_response(_pending_shaped_draft()),
            request=_request("run the same thing"),
        )


class TestSizingAnswerSurvivesBudgetAudit:
    """The runtime's own sizing question fixes the money role: an answer the
    primary typed as the contribution is never re-roled into a budget."""

    @staticmethod
    def _audit():
        from argus.agent_runtime.interpreter.audits import DcaContributionRoleAudit

        return DcaContributionRoleAudit(
            recurring_contribution_explicit=False,
            total_budget_not_recurring=True,
            confidence=0.9,
        )

    def test_sizing_answer_contribution_survives_budget_verdict(self) -> None:
        from argus.agent_runtime.interpreter.dca_audits import (
            total_budget_audited_response,
        )

        draft = _pending_shaped_draft(
            capital_amount=200.0,
            field_provenance={"capital_amount": "recurring_contribution"},
        )
        audited = total_budget_audited_response(
            response=_response(draft),
            audit=self._audit(),
            answers_pending_sizing_question=True,
        )
        audited_draft = audited.candidate_strategy_draft
        assert audited_draft.capital_amount == 200.0
        assert audited_draft.total_capital is None
        assert (
            "dca_contribution_provenance_kept_over_budget_audit" in audited.reason_codes
        )
        assert not audited.requires_clarification

    def test_fresh_message_with_budget_verdict_still_demotes(self) -> None:
        # Outside a pending sizing question the budget verdict wins even over
        # a contribution provenance ("$200,000 of capital" mis-typed by the
        # primary must still demote).
        from argus.agent_runtime.interpreter.dca_audits import (
            total_budget_audited_response,
        )

        draft = _pending_shaped_draft(
            capital_amount=200000.0,
            field_provenance={"capital_amount": "recurring_contribution"},
        )
        audited = total_budget_audited_response(
            response=_response(draft),
            audit=self._audit(),
            answers_pending_sizing_question=False,
        )
        audited_draft = audited.candidate_strategy_draft
        assert audited_draft.capital_amount is None
        assert audited_draft.total_capital == 200000.0
        assert audited.requires_clarification

    def test_role_ambiguous_sizing_answer_still_becomes_the_budget(self) -> None:
        # Without a provenance claim, the audit's verdict applies even to a
        # sizing answer; the plan then asks for the amount by name.
        from argus.agent_runtime.interpreter.dca_audits import (
            total_budget_audited_response,
        )

        draft = _pending_shaped_draft(capital_amount=200.0)
        audited = total_budget_audited_response(
            response=_response(draft),
            audit=self._audit(),
            answers_pending_sizing_question=True,
        )
        audited_draft = audited.candidate_strategy_draft
        assert audited_draft.capital_amount is None
        assert audited_draft.total_capital == 200.0
        assert audited.requires_clarification


class TestLastResortRepairReservation:
    """Audits can spend the whole allowance; the final rescue still runs."""

    def test_repair_scope_reserves_one_call_after_exhaustion(self) -> None:
        state = RunState.new(current_user_message="200$", recent_thread_history=[])
        with turn_execution.turn_execution_scope(entry_state=state) as execution:
            for _ in range(execution.call_allowance):
                assert turn_execution.reserve_provider_call("interpretation") is not None
            # The corridor is spent: an ordinary call is refused.
            assert turn_execution.reserve_provider_call("interpretation") is None
            with turn_execution.last_resort_repair_scope():
                first = turn_execution.reserve_provider_call("interpretation_repair")
                second = turn_execution.reserve_provider_call("interpretation_repair")
            assert first is not None
            assert second is None

    def test_within_budget_repair_calls_spend_ordinary_slots(self) -> None:
        state = RunState.new(current_user_message="200$", recent_thread_history=[])
        with turn_execution.turn_execution_scope(entry_state=state) as execution:
            with turn_execution.last_resort_repair_scope():
                assert (
                    turn_execution.reserve_provider_call("interpretation_repair")
                    is not None
                )
            assert execution.calls_reserved == 1
            assert not execution.last_resort_repair_reserved
