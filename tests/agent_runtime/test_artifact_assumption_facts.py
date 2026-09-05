from __future__ import annotations

import pytest
from argus.agent_runtime.stages.artifact_context import draft_assumptions_response
from argus.agent_runtime.stages.interpret_actions import (
    pending_artifact_followup_stage_result_if_applicable,
)
from argus.agent_runtime.stages.interpret_types import InterpretDecision
from argus.agent_runtime.state.models import (
    ArtifactReference,
    ResponseProfile,
    StrategySummary,
    TaskSnapshot,
)


@pytest.fixture
def snapshot(faker) -> TaskSnapshot:
    return TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="dca_accumulation",
            asset_class="equity",
            asset_universe=["AAPL"],
            capital_amount=500,
            cadence="monthly",
            assumptions=["Private legacy draft prose"],
        ),
        active_confirmation_reference=ArtifactReference(
            artifact_kind="confirmation",
            artifact_id=f"confirmation-{faker.uuid4()}",
            artifact_status="active",
            metadata={
                "confirmation_card": {
                    "asset_class": "equity",
                    "assumptions": ["Private legacy card prose"],
                    "display_facts": {
                        "starting_capital": 0,
                        "recurring_contribution": 500,
                        "contribution_period": "monthly",
                        "fees": 0,
                        "slippage": 0,
                        "timeframe": "1D",
                        "benchmark_symbol": "SPY",
                    },
                }
            },
        ),
    )


def test_assumptions_answer_uses_only_the_visible_cards_typed_facts(snapshot):
    intent = draft_assumptions_response(snapshot)

    assert intent["kind"] == "artifact_assumptions"
    assert intent["facts"]["artifact_kind"] == "confirmation"
    assert (
        intent["facts"]["display_facts"]
        == snapshot.active_confirmation_reference.metadata["confirmation_card"][
            "display_facts"
        ]
    )
    assert "Private legacy" not in str(intent)


def test_assumption_followup_transports_facts_without_backend_prose(snapshot):
    result = pending_artifact_followup_stage_result_if_applicable(
        decision=InterpretDecision(
            intent="conversation_followup",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="Explain the artifact assumptions.",
            confidence=1.0,
            effective_response_profile=ResponseProfile(
                effective_tone="friendly",
                effective_verbosity="medium",
                effective_expertise_mode="beginner",
            ),
            semantic_turn_act="result_followup",
            result_followup_focus="assumptions",
        ),
        snapshot=snapshot,
    )

    assert result is not None
    assert result.stage_patch["assistant_response"] == ""
    assert result.stage_patch["response_intent"]["kind"] == "artifact_assumptions"
    assert "confirmation_payload" not in result.stage_patch
    assert "confirmation_card" not in result.stage_patch


@pytest.mark.parametrize("state", ["cancelled", "superseded", "consumed"])
def test_dead_confirmation_cannot_supply_an_assumptions_answer(snapshot, state):
    snapshot.active_confirmation_reference.artifact_status = state
    assert draft_assumptions_response(snapshot) is None


def test_legacy_confirmation_uses_typed_payload_not_english_assumption_strings(snapshot):
    reference = snapshot.active_confirmation_reference
    reference.metadata["confirmation_card"].pop("display_facts")
    reference.metadata["confirmation_payload"] = {
        "strategy": snapshot.pending_strategy_summary.model_dump(mode="json"),
        "optional_parameters": {
            "initial_capital": {"source": "user", "value": 250},
            "fees": {"source": "default", "value": 0},
            "slippage": {"source": "default", "value": 0},
        },
        "launch_payload": {},
    }

    intent = draft_assumptions_response(snapshot)

    facts = intent["facts"]["display_facts"]
    assert facts["starting_capital"] == 250
    assert facts["recurring_contribution"] == 500
    assert facts["contribution_period"] == "monthly"
    assert facts["fees"] == facts["slippage"] == 0
    assert "Private legacy" not in str(intent)
