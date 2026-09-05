"""Guest conversion must survive the graph/checkpoint boundary, not just execute."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest
from argus.agent_runtime.graph.workflow import _apply_stage_result
from argus.agent_runtime.runtime import _public_result
from argus.agent_runtime.stages.execute import execute_stage
from argus.agent_runtime.state.models import RunState, UserState
from argus.api.chat.backtest_job_envelopes import (
    admission_failure_reason,
    admission_rejection_envelope,
    async_backtest_job_envelope,
)
from argus.api.chat.confirmation import public_confirmation_projection
from argus.api.chat.streaming import sse_data
from argus.api.state import build_agent_runtime_checkpoint_serde


@dataclass
class AdmissionTool:
    envelope: dict[str, Any]

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.envelope


def _checkpoint_to_public_sse(graph_state: dict[str, Any]) -> dict[str, Any]:
    serde = build_agent_runtime_checkpoint_serde()
    restored = serde.loads_typed(serde.dumps_typed(graph_state))
    frame = sse_data(
        {
            "type": "final",
            "payload": public_confirmation_projection(_public_result(restored)),
        }
    )
    return json.loads(frame.removeprefix("data: "))["payload"]


@pytest.mark.parametrize("durable_receipt", [False, True], ids=["rejection", "receipt"])
def test_conversion_code_survives_graph_checkpoint_and_public_sse(
    durable_receipt: bool,
    faker,
) -> None:
    reason = admission_failure_reason("conversion_required")
    job = {
        "id": faker.uuid4(),
        "conversation_id": faker.uuid4(),
        "status": "failed",
        "failure_code": reason.failure_code,
        "failure_detail": reason.failure_detail,
        "retryable": reason.retryable,
    }
    envelope = (
        async_backtest_job_envelope(job)
        if durable_receipt
        else admission_rejection_envelope("conversion_required")
    )
    state = RunState.new(current_user_message="Run backtest", recent_thread_history=[])
    result = execute_stage(state=state, tool=AdmissionTool(envelope), max_retries=1)
    graph_state = _apply_stage_result(
        {"run_state": state, "user": UserState(user_id=faker.uuid4())}, result
    )

    payload = _checkpoint_to_public_sse(graph_state)

    assert payload["stage_outcome"] == "execution_failed_terminally"
    assert payload["final_response_payload"]["code"] == "account_conversion_required"
    if durable_receipt:
        assert payload["backtest_job"] == job
        assert payload["final_response_payload"]["backtest_job"] == job


@pytest.mark.parametrize("legacy_field", ["error", "result", "backtest_job"])
def test_legacy_final_payload_without_code_still_hydrates_and_streams(
    legacy_field: str,
    faker,
) -> None:
    legacy_value = faker.sentence() if legacy_field == "error" else {"id": faker.uuid4()}
    state = RunState.model_validate(
        {
            "current_user_message": "Run backtest",
            "final_response_payload": {legacy_field: legacy_value},
        }
    )

    payload = _checkpoint_to_public_sse({"run_state": state})["final_response_payload"]

    assert payload[legacy_field] == legacy_value
    assert payload.get("code") is None
