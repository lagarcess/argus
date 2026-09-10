"""The no-turn editor retains blank inputs and loses stale writes through CAS."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from argus.api import state as api_state
from argus.api.main import app
from argus.api.message_store import create_message, update_message_artifact
from argus.domain.tool_contracts import (
    LocalizedText,
    ToolCall,
    ToolCardPresentation,
    ToolFact,
    ToolInputFact,
    ToolOutcome,
)
from faker import Faker
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict

fake = Faker()


class IdentityArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    known: float | None = None
    unknown: float | None = None


class IdentityResult(BaseModel):
    value: float


@pytest.fixture
def surface(monkeypatch):
    from argus.api.routers import tool_results
    from argus.domain.tool_declaration import (
        ExactlyOneUnknown,
        ToolCardBinding,
        ToolCatalog,
        ToolDeclaration,
        ToolPolicy,
        ToolProgressTemplate,
    )

    executions: list[dict[str, Any]] = []
    hooks: list[Any] = []

    async def identity(arguments: IdentityArguments) -> IdentityResult:
        executions.append(arguments.model_dump())
        for hook in hooks:
            hook()
        return IdentityResult(value=arguments.known)

    def present(
        arguments: IdentityArguments, outcome: ToolOutcome
    ) -> ToolCardPresentation:
        return ToolCardPresentation(
            title=LocalizedText(locale_key="chat.tools.identity.title"),
            answer=(
                ToolFact(
                    name="value",
                    label=LocalizedText(locale_key="chat.tools.identity.value"),
                    value=outcome.result["value"],
                )
                if outcome.result is not None
                else None
            ),
            inputs=[
                ToolInputFact(
                    name=name,
                    label=LocalizedText(locale_key=f"chat.tools.identity.{name}"),
                    value=value,
                    visibility="public",
                )
                for name, value in arguments.model_dump().items()
            ],
        )

    declaration = ToolDeclaration(
        name="identity_value",
        description="Return a provided value.",
        handler=identity,
        policy=ToolPolicy(
            execution="local",
            external_calls=0,
            confirmation="never",
            editable_fields=("known",),
        ),
        progress=ToolProgressTemplate(
            locale_key="chat.tools.identity.progress", argument_fields=("known",)
        ),
        card=ToolCardBinding(card_type="identity_value", version=1, presenter=present),
        rules=(ExactlyOneUnknown(fields=("known", "unknown")),),
    )
    monkeypatch.setattr(
        tool_results, "get_tool_catalog", lambda: ToolCatalog((declaration,))
    )
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    owner = client.get("/api/v1/me").json()["user"]["id"]
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]
    call = ToolCall(
        tool_name=declaration.name,
        call_id=fake.uuid4(),
        arguments={"known": 1, "unknown": None},
    )
    card = declaration.result_card(
        call=call,
        outcome=ToolOutcome(status="succeeded", result={"value": 1}),
        artifact_id=fake.uuid4(),
    )
    message = create_message(
        user_id=owner,
        conversation_id=conversation["id"],
        role="assistant",
        content="",
        metadata={
            "tool_result_cards": [card.model_dump(mode="json")],
            "retained": {"value": fake.word()},
        },
    )
    url = f"/api/v1/conversations/{conversation['id']}/tool-results/{card.artifact_id}/recompute"
    return client, owner, message, card, executions, hooks, url


def test_known_zero_recomputes_same_message_and_retains_unknown(surface) -> None:
    client, owner, message, card, executions, _, url = surface
    before = client.get("/api/v1/me/usage").json()
    response = client.post(
        url,
        json={"message_id": message.id, "input_revision": 0, "arguments": {"known": 0}},
    )
    assert response.status_code == 200, response.text
    updated = response.json()["message"]
    result = updated["metadata"]["tool_result_cards"][0]
    assert updated["id"] == message.id
    assert result["artifact_id"] == card.artifact_id
    assert result["input_revision"] == 1
    assert result["arguments"] == {"known": 0, "unknown": None}
    assert result["outcome"]["result"] == {"value": 0}
    inputs = {fact["name"]: fact for fact in result["presentation"]["inputs"]}
    assert inputs["known"]["editable"] is True and inputs["known"]["unknown"] is False
    assert inputs["unknown"]["editable"] is False and inputs["unknown"]["unknown"] is True
    assert updated["metadata"]["retained"] == message.metadata["retained"]
    assert executions == [{"known": 0, "unknown": None}]
    assert len(api_state.store.messages[message.conversation_id]) == 1
    assert not api_state.store.backtest_runs
    assert client.get("/api/v1/me/usage").json() == before


@pytest.mark.parametrize("arguments", [{"unknown": 2}, {"known": None}, {"surprise": 2}])
def test_forbidden_or_invalid_edit_executes_nothing(surface, arguments) -> None:
    client, _, message, _, executions, _, url = surface
    response = client.post(
        url, json={"message_id": message.id, "input_revision": 0, "arguments": arguments}
    )
    assert response.status_code == 422, response.text
    assert not executions
    assert api_state.store.messages[message.conversation_id][0] == message


def test_stale_revision_refuses_duplicate_compute(surface) -> None:
    client, _, message, _, executions, _, url = surface
    body = {"message_id": message.id, "input_revision": 0, "arguments": {"known": 2}}
    assert client.post(url, json=body).status_code == 200
    stale = client.post(url, json=body)
    assert stale.status_code == 409
    assert stale.json()["code"] == "tool_result_changed"
    assert len(executions) == 1


def test_next_turn_derives_recomputed_reference_from_message(surface) -> None:
    from argus.api.chat.recovery import ordinary_turn_metadata_fallback_context

    client, owner, message, card, _, _, url = surface
    assert (
        client.post(
            url,
            json={
                "message_id": message.id,
                "input_revision": 0,
                "arguments": {"known": 0},
            },
        ).status_code
        == 200
    )
    fallback = ordinary_turn_metadata_fallback_context(
        user_id=owner, conversation_id=message.conversation_id
    )
    assert fallback is not None
    assert fallback.latest_task_snapshot.latest_task_type is None
    assert "latest_task_type" not in fallback.selected_thread_metadata
    reference = next(
        item
        for item in fallback.artifact_references
        if item.artifact_id == card.artifact_id
    )
    assert reference.metadata["input_revision"] == 1
    assert reference.metadata["arguments"] == {"known": 0, "unknown": None}


@pytest.mark.parametrize("race", ["edit", "append"])
def test_losing_recompute_cannot_replace_newer_result_or_checkpoint(
    surface, race
) -> None:
    client, owner, message, _, _, hooks, url = surface
    winner = copy.deepcopy(message.metadata)
    winner["tool_result_cards"][0]["input_revision"] = 4

    def concurrent_change() -> None:
        if race == "append":
            create_message(
                user_id=owner,
                conversation_id=message.conversation_id,
                role="user",
                content=fake.sentence(),
            )
        else:
            update_message_artifact(
                user_id=owner,
                conversation_id=message.conversation_id,
                message_id=message.id,
                content="",
                metadata=winner,
                expected_source_metadata=message.metadata,
                expected_latest_message_id=message.id,
            )

    hooks.append(concurrent_change)
    response = client.post(
        url,
        json={"message_id": message.id, "input_revision": 0, "arguments": {"known": 0}},
    )
    assert response.status_code == 409, response.text
    stored = api_state.store.messages[message.conversation_id][0]
    assert stored.metadata == (message.metadata if race == "append" else winner)


def test_another_owners_message_and_an_inactive_result_cannot_compute(surface) -> None:
    client, owner, message, _, executions, _, url = surface
    api_state.store.conversation_owners[message.conversation_id] = fake.uuid4()
    foreign = client.post(
        url,
        json={"message_id": message.id, "input_revision": 0, "arguments": {"known": 2}},
    )
    assert foreign.status_code == 404
    api_state.store.conversation_owners[message.conversation_id] = owner
    create_message(
        user_id=api_state.store.conversation_owners[message.conversation_id],
        conversation_id=message.conversation_id,
        role="user",
        content=fake.sentence(),
    )
    inactive = client.post(
        url,
        json={"message_id": message.id, "input_revision": 0, "arguments": {"known": 2}},
    )
    assert inactive.status_code == 409
    assert not executions


def test_tool_fallback_keeps_existing_result_owner_and_all_completed_calls(
    surface, monkeypatch
) -> None:
    from argus.agent_runtime.state.models import ArtifactReference, TaskSnapshot
    from argus.api.chat import recovery

    from tests.test_tool_result_publication import card_document

    _, owner, message, original, _, _, _ = surface
    result_ref = ArtifactReference(
        artifact_kind="backtest_result",
        artifact_id=fake.uuid4(),
        metadata={"run_id": fake.uuid4()},
    )
    monkeypatch.setattr(
        recovery,
        "latest_result_fallback_context",
        lambda **_: recovery.RuntimeFallbackContext(
            latest_task_snapshot=TaskSnapshot(
                latest_task_type="results_explanation",
                completed=True,
                latest_backtest_result_reference=result_ref,
                artifact_references=[result_ref],
            ),
            artifact_references=[result_ref],
        ),
    )
    update_message_artifact(
        user_id=owner,
        conversation_id=message.conversation_id,
        message_id=message.id,
        content="",
        metadata={**message.metadata, "result_card": {"title": "Result"}},
        expected_source_metadata=message.metadata,
        expected_latest_message_id=message.id,
    )
    second = card_document()
    create_message(
        user_id=owner,
        conversation_id=message.conversation_id,
        role="assistant",
        content="",
        metadata={"tool_result_cards": [second]},
    )
    fallback = recovery.ordinary_turn_metadata_fallback_context(
        user_id=owner, conversation_id=message.conversation_id
    )
    assert fallback.latest_task_snapshot.latest_backtest_result_reference == result_ref
    assert {ref.artifact_id for ref in fallback.artifact_references} == {
        result_ref.artifact_id,
        original.artifact_id,
        second["artifact_id"],
    }
