from __future__ import annotations

import pytest
from argus.domain.tool_contracts import ToolCall, ToolOutcome
from faker import Faker

fake = Faker()


def test_unknown_completion_binding_retains_identity_and_withholds_answer(
    monkeypatch,
) -> None:
    from argus.domain import capability_registry
    from argus.domain.tool_declaration import ToolCatalog
    from argus.domain.tool_job_binding import tool_card_for_job_completion

    monkeypatch.setattr(
        capability_registry, "get_tool_catalog", lambda **_: ToolCatalog(())
    )
    call = ToolCall(tool_name="retired_tool", call_id=fake.uuid4(), arguments={})
    artifact_id = fake.uuid4()
    binding = {
        "call": call.model_dump(mode="json"),
        "artifact_id": artifact_id,
        "card_type": "retired_card",
        "card_version": 1,
    }
    card = tool_card_for_job_completion(
        binding, ToolOutcome(status="succeeded", result={"value": 0})
    )
    assert card.call_id == call.call_id and card.artifact_id == artifact_id
    assert card.card_type == "retired_card" and card.card_version == 1
    assert card.outcome.status == "unavailable"
    assert card.presentation.answer is None


@pytest.mark.parametrize("missing", ["call", "artifact_id", "card_type", "card_version"])
def test_incomplete_job_binding_is_rejected(missing) -> None:
    from argus.domain.tool_job_binding import tool_card_for_job_completion

    binding = {
        "call": {"tool_name": "example", "call_id": fake.uuid4(), "arguments": {}},
        "artifact_id": fake.uuid4(),
        "card_type": "example",
        "card_version": 1,
    }
    binding.pop(missing)
    with pytest.raises(ValueError):
        tool_card_for_job_completion(binding, ToolOutcome(status="succeeded", result={}))
