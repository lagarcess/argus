"""Tool receipts freeze only shareable card facts, with source-owned identity."""

from __future__ import annotations

import copy
import json

import pytest
from argus.api import state as api_state
from argus.api.main import app
from argus.api.message_store import create_message
from argus.domain.tool_contracts import ToolResultCard
from faker import Faker
from fastapi.testclient import TestClient

from tests.test_tool_result_publication import card_document

fake = Faker()


def test_public_receipt_strips_private_narrative_and_keeps_public_sources() -> None:
    from argus.domain.public_excerpts import build_tool_public_excerpt_payload

    document = card_document()
    document["presentation"]["narrative"] = fake.sentence()
    document["presentation"]["sources"] = [
        {
            "url": "https://www.sec.gov/Archives/edgar/data/example",
            "title": "Filing",
            "source_date": "2026-09-01",
        }
    ]
    card = ToolResultCard.model_validate(document)
    result = build_tool_public_excerpt_payload(
        card=card, owner_note=None, content_language="en"
    )
    assert result.presentation.narrative is None
    assert result.presentation.sources == card.presentation.sources


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "https://user:password@example.com/report",
        "https://example.com/" + "11111111-1111-1111-1111-111111111111",
    ],
)
def test_unsafe_or_private_citation_refuses_public_receipt(url) -> None:
    from argus.domain.public_excerpts import (
        PublicExcerptSanitizationError,
        build_tool_public_excerpt_payload,
    )

    document = card_document()
    document["presentation"]["sources"] = [
        {"url": url, "title": "Filing", "source_date": None}
    ]
    with pytest.raises(PublicExcerptSanitizationError):
        build_tool_public_excerpt_payload(
            card=ToolResultCard.model_validate(document),
            owner_note=None,
            content_language="en",
        )


def test_tool_receipt_uses_shared_facts_without_private_execution_records() -> None:
    from argus.domain.public_excerpts import build_tool_public_excerpt_payload
    from argus.domain.supabase_public_excerpts import _public_view_from_row

    card = ToolResultCard.model_validate(card_document())
    payload = build_tool_public_excerpt_payload(
        card=card, owner_note=None, content_language="es-419"
    )
    document = payload.model_dump(mode="json")
    assert document["schema_version"] == 2
    assert document["presentation"] == card.presentation.model_dump(mode="json")
    assert document["card_type"] == card.card_type
    assert not {
        "tool_name",
        "call_id",
        "artifact_id",
        "arguments",
        "outcome",
    }.intersection(document)
    assert card.call_id not in json.dumps(document)
    assert card.artifact_id not in json.dumps(document)
    view = _public_view_from_row(fake.uuid4(), {"payload": document})
    assert view.payload == payload


@pytest.mark.parametrize(
    "carrier", ["value", "locale_key", "interpolation_args", "value_text"]
)
def test_a_private_identity_in_any_display_fact_refuses_publication(carrier) -> None:
    from argus.domain.public_excerpts import (
        PublicExcerptSanitizationError,
        build_tool_public_excerpt_payload,
    )

    document = card_document()
    leaked = document["call_id"]
    if carrier == "value":
        document["presentation"]["answer"]["value"] = leaked
    elif carrier == "locale_key":
        document["presentation"]["title"]["locale_key"] = leaked
    elif carrier == "interpolation_args":
        document["presentation"]["title"]["interpolation_args"]["subject"] = leaked
    else:
        document["presentation"]["answer"]["value_text"] = {
            "locale_key": "chat.tools.identity.value",
            "interpolation_args": {"value": leaked},
        }
    with pytest.raises(PublicExcerptSanitizationError):
        build_tool_public_excerpt_payload(
            card=ToolResultCard.model_validate(document),
            owner_note=None,
            content_language="en",
        )


def test_receipt_input_visibility_is_declared_and_zero_stays_known() -> None:
    from argus.domain.public_excerpts import build_tool_public_excerpt_payload
    from argus.domain.tool_contracts import LocalizedText, ToolInputFact

    card = ToolResultCard.model_validate(card_document())
    inputs = [
        ToolInputFact(
            name="known",
            label=LocalizedText(locale_key="chat.tools.identity.known"),
            value=0,
            editable=True,
            visibility="public",
        ),
        ToolInputFact(
            name="unknown",
            label=LocalizedText(locale_key="chat.tools.identity.unknown"),
            value=None,
            unknown=True,
            visibility="public",
        ),
        ToolInputFact(
            name="request",
            label=LocalizedText(locale_key="chat.tools.identity.request"),
            value=fake.sentence(),
        ),
    ]
    card = card.model_copy(
        update={"presentation": card.presentation.model_copy(update={"inputs": inputs})}
    )
    receipt = build_tool_public_excerpt_payload(
        card=card, owner_note=None, content_language="en"
    )
    assert [fact.name for fact in receipt.presentation.inputs] == ["known", "unknown"]
    assert receipt.presentation.inputs[0].value == 0
    assert receipt.presentation.inputs[0].unknown is False
    assert receipt.presentation.inputs[1].value is None
    assert all(not fact.editable for fact in receipt.presentation.inputs)


@pytest.mark.parametrize("status", ["invalid", "ambiguous", "bounded", "unavailable"])
def test_nonanswers_are_never_shareable_successes(status) -> None:
    from argus.domain.public_excerpts import (
        PublicExcerptSourceError,
        build_tool_public_excerpt_payload,
    )

    document = card_document()
    document["outcome"] = {
        "status": status,
        "result": None,
        "failure": {"code": "test_failure", "fields": []},
    }
    document["presentation"]["answer"] = None
    with pytest.raises(PublicExcerptSourceError):
        build_tool_public_excerpt_payload(
            card=ToolResultCard.model_validate(document),
            owner_note=None,
            content_language="en",
        )


def test_owned_tool_receipt_reuses_same_revision_and_revokes_with_source(
    monkeypatch,
) -> None:
    from argus.domain import public_excerpt_tool_turns
    from argus.domain.tool_declaration import ToolCatalog

    from tests.public_excerpt_tool_factories import identity_declaration

    monkeypatch.setenv("ARGUS_EVIDENCE_RECEIPT_SHARING_ENABLED", "true")
    monkeypatch.setattr(
        public_excerpt_tool_turns,
        "get_tool_catalog",
        lambda **_: ToolCatalog((identity_declaration(),)),
    )
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    owner = client.get("/api/v1/me").json()["user"]["id"]
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]
    create_message(
        user_id=owner,
        conversation_id=conversation["id"],
        role="user",
        content="What is the provided value?",
    )
    card = card_document()
    message = create_message(
        user_id=owner,
        conversation_id=conversation["id"],
        role="assistant",
        content="",
        metadata={
            "tool_result_cards": [card],
            "agent_runtime_turn": {"terminal": True, "status": "completed"},
        },
    )
    url = f"/api/v1/conversations/{conversation['id']}/tool-results/{card['artifact_id']}/public-excerpt"
    request = {"message_id": message.id, "input_revision": 0, "owner_note": None}
    first = client.post(url, json=request)
    assert first.status_code == 200, first.text
    repeated = client.post(url, json=request)
    assert repeated.json()["receipt"]["id"] == first.json()["receipt"]["id"]
    receipt = first.json()["receipt"]
    snapshot = api_state.store.public_excerpt_snapshots[receipt["id"]]
    assert snapshot.evidence_artifact_id is None and snapshot.source_run_id is None
    assert snapshot.source_message_ids == [message.id]
    assert snapshot.source_tool_bindings[0].model_dump(mode="json") == {
        "message_id": message.id,
        "artifact_id": card["artifact_id"],
        "input_revision": 0,
    }
    assert not api_state.store.evidence_artifacts and not api_state.store.backtest_runs
    assert (
        client.post(url, json={**request, "message_id": fake.uuid4()}).status_code == 404
    )
    assert client.post(url, json={**request, "input_revision": 1}).status_code == 409
    client.delete(f"/api/v1/conversations/{conversation['id']}")
    assert (
        client.get(f"/api/v1/public/receipts/{receipt['public_id']}").json()["status"]
        == "revoked"
    )


@pytest.mark.parametrize("body", [{}, {"unknown": True}])
def test_tool_receipt_flag_off_is_the_same_unmatched_route(body, monkeypatch) -> None:
    monkeypatch.delenv("ARGUS_EVIDENCE_RECEIPT_SHARING_ENABLED", raising=False)
    client = TestClient(app)
    result = client.post(
        f"/api/v1/conversations/{fake.uuid4()}/tool-results/{fake.uuid4()}/public-excerpt",
        json=copy.deepcopy(body),
    )
    assert result.status_code == 404
    assert result.json() == {"detail": "Not Found"}
