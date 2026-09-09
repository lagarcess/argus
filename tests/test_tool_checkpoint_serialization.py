"""Exercise the production checkpoint serializer with nested tool contracts."""

from __future__ import annotations

from argus.agent_runtime.state.models import (
    ArtifactReference,
    FinalResponsePayload,
    RunState,
    TaskSnapshot,
    ToolCallRecord,
)
from argus.api.state import build_agent_runtime_checkpoint_serde
from argus.domain.tool_contracts import (
    LocalizedText,
    ToolCall,
    ToolCardPresentation,
    ToolFact,
    ToolFailure,
    ToolInputFact,
    ToolOutcome,
    ToolResultCard,
)


def test_nested_tool_records_rehydrate_through_production_checkpoint_serializer(
    faker,
) -> None:
    calls = [
        ToolCall(
            tool_name="identity_value",
            call_id=faker.uuid4(),
            arguments={"known": 0, "unknown": None},
        )
        for _ in range(2)
    ]
    outcomes = [
        ToolOutcome(status="succeeded", result={"value": 0}),
        ToolOutcome(
            status="bounded",
            failure=ToolFailure(code="test_bound_reached", fields=["known"]),
        ),
    ]
    label = LocalizedText(locale_key="chat.tools.identity.value")
    cards = [
        ToolResultCard(
            tool_name=call.tool_name,
            call_id=call.call_id,
            artifact_id=faker.uuid4(),
            card_type="identity_value",
            card_version=1,
            arguments=call.arguments,
            outcome=outcome,
            presentation=ToolCardPresentation(
                title=label,
                answer=(
                    ToolFact(name="value", label=label, value=0)
                    if outcome.status == "succeeded"
                    else None
                ),
                inputs=[
                    ToolInputFact(name="known", label=label, value=0, editable=True),
                    ToolInputFact(name="unknown", label=label, value=None, unknown=True),
                ],
            ),
        )
        for call, outcome in zip(calls, outcomes, strict=True)
    ]
    state = {
        "run_state": RunState(
            current_user_message=faker.sentence(),
            intent="calculate",
            tool_calls=calls,
            tool_call_records=[
                ToolCallRecord(
                    call_id=call.call_id,
                    tool_name=call.tool_name,
                    payload=call.arguments,
                    outcome=outcome.status,
                    tool_outcome=outcome,
                )
                for call, outcome in zip(calls, outcomes, strict=True)
            ],
            final_response_payload=FinalResponsePayload(tool_result_cards=cards),
        ),
        "latest_task_snapshot": TaskSnapshot(
            latest_task_type="calculate",
            pending_tool_calls=calls,
            artifact_references=[
                ArtifactReference(
                    artifact_kind="tool_result",
                    artifact_id=card.artifact_id,
                    metadata=card.model_dump(mode="json"),
                )
                for card in cards
            ],
        ),
    }

    serde = build_agent_runtime_checkpoint_serde()
    serialized = serde.dumps_typed(state)
    assert serialized[0] == "msgpack", "This proof must not use pickle fallback."
    restored = serde.loads_typed(serialized)

    assert restored == state
    run_state = restored["run_state"]
    snapshot = restored["latest_task_snapshot"]
    assert isinstance(run_state, RunState)
    assert isinstance(snapshot, TaskSnapshot)
    assert all(isinstance(call, ToolCall) for call in run_state.tool_calls)
    assert all(isinstance(call, ToolCall) for call in snapshot.pending_tool_calls)
    assert [call.call_id for call in run_state.tool_calls] == [call.call_id for call in calls]
    assert run_state.tool_calls[0].arguments == {"known": 0, "unknown": None}

    final = run_state.final_response_payload
    assert isinstance(final, FinalResponsePayload)
    assert all(isinstance(card, ToolResultCard) for card in final.tool_result_cards)
    assert isinstance(final.tool_result_cards[0].presentation.answer, ToolFact)
    assert isinstance(final.tool_result_cards[0].presentation.inputs[1], ToolInputFact)
    assert final.tool_result_cards[0].presentation.inputs[1].unknown
    assert final.tool_result_cards[1].presentation.answer is None
    assert isinstance(run_state.tool_call_records[1].tool_outcome, ToolOutcome)
    assert isinstance(run_state.tool_call_records[1].tool_outcome.failure, ToolFailure)
    assert final.tool_result_cards[1].outcome.result is None
