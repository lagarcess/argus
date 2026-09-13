"""A decision attaches to exactly one computation owner."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from argus.api import decision_contract, schemas
from argus.api.decision_contract import (
    COMPUTATION_INPUTS_MAX_KEYS,
    DecisionComputation,
    DecisionNote,
    DecisionRerun,
    DecisionRerunRequest,
    SearchRetestAction,
)
from faker import Faker
from pydantic import ValidationError

fake = Faker()
NOW = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)


def _base_fields() -> dict[str, object]:
    return {
        "id": fake.uuid4(),
        "source_conversation_id": fake.uuid4(),
        "decision_state": "watching",
        "note": None,
        "created_at": NOW,
        "updated_at": NOW,
    }


def test_schemas_re_exports_the_decision_contract_classes() -> None:
    assert schemas.DecisionNote is decision_contract.DecisionNote
    assert schemas.DecisionNoteCreate is decision_contract.DecisionNoteCreate
    assert schemas.SearchDossierDecision is decision_contract.SearchDossierDecision
    assert schemas.SearchDecisionAction is decision_contract.SearchDecisionAction
    assert schemas.SearchRetestAction is SearchRetestAction
    assert schemas.DECISION_NOTE_WRITE_MAX_LENGTH == 500


def test_backtest_decision_keeps_its_artifact_spine_and_stores_no_computation() -> None:
    decision = DecisionNote(
        **_base_fields(),
        idea_id=fake.uuid4(),
        idea_version_id=fake.uuid4(),
        evidence_artifact_id=fake.uuid4(),
    )

    assert decision.computation is None
    assert decision.source_message_id is None
    dumped = decision.model_dump(mode="json")
    assert dumped["computation"] is None
    assert dumped["source_message_id"] is None


def test_computed_answer_decision_stores_its_computation_without_a_spine() -> None:
    decision = DecisionNote(
        **_base_fields(),
        source_message_id=fake.uuid4(),
        computation=DecisionComputation(
            kind="savings_projection",
            inputs={"monthly_amount": 5000, "months": 9},
        ),
    )

    assert decision.evidence_artifact_id is None
    assert decision.idea_id is None
    assert decision.idea_version_id is None
    assert decision.computation is not None
    assert decision.computation.inputs["months"] == 9


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {
            "evidence_artifact_id": "artifact-1",
            "idea_id": "idea-1",
            "idea_version_id": "version-1",
            "computation": DecisionComputation(kind="savings_projection"),
        },
        {"evidence_artifact_id": "artifact-1"},
        {"evidence_artifact_id": "artifact-1", "idea_id": "idea-1"},
        {
            "computation": DecisionComputation(kind="savings_projection"),
            "idea_id": "idea-1",
            "idea_version_id": "version-1",
        },
    ],
    ids=[
        "no_attachment",
        "both_attachments",
        "artifact_without_lineage",
        "artifact_with_partial_lineage",
        "computation_with_stray_lineage",
    ],
)
def test_decision_rejects_every_shape_with_zero_or_two_owners(
    fields: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        DecisionNote(**_base_fields(), **fields)


def test_computation_kind_is_a_slug_and_inputs_are_bounded_json() -> None:
    with pytest.raises(ValidationError):
        DecisionComputation(kind="Savings Projection")
    with pytest.raises(ValidationError):
        DecisionComputation(kind="")
    with pytest.raises(ValidationError):
        DecisionComputation(
            kind="wide",
            inputs={
                f"key_{index}": index for index in range(COMPUTATION_INPUTS_MAX_KEYS + 1)
            },
        )
    with pytest.raises(ValidationError):
        DecisionComputation(kind="long", inputs={"blob": "x" * 9_000})
    with pytest.raises(ValidationError):
        DecisionRerunRequest(inputs={"blob": "x" * 9_000})
    with pytest.raises(ValidationError):
        DecisionRerunRequest(inputs={}, kind="stray")  # type: ignore[call-arg]

    computation = DecisionComputation(kind="savings_projection", inputs={"months": 9})
    assert computation.model_dump() == {
        "kind": "savings_projection",
        "inputs": {"months": 9},
    }


def test_rerun_shape_pins_result_retest_and_reason_to_their_status() -> None:
    computed = DecisionRerun(
        kind="savings_projection",
        inputs={"months": 9},
        status="computed",
        result={"saved_total": 45_000},
    )
    assert computed.reason_code is None

    with pytest.raises(ValidationError):
        DecisionRerun(kind="savings_projection", inputs={}, status="computed")
    with pytest.raises(ValidationError):
        DecisionRerun(kind="backtest", inputs={}, status="confirmation_required")
    with pytest.raises(ValidationError):
        DecisionRerun(kind="backtest", inputs={}, status="unavailable")
    with pytest.raises(ValidationError):
        DecisionRerun(
            kind="backtest",
            inputs={},
            status="unavailable",
            reason_code="run_unavailable",
            result={"stray": True},
        )
    with pytest.raises(ValidationError):
        DecisionRerun(
            kind="savings_projection",
            inputs={},
            status="computed",
            result={},
            reason_code="invalid_inputs",
        )
