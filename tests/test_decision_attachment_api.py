"""The proof: a decision on a non-backtest computation, retrieved, and re-run.

A computed answer is an assistant message that declares ``metadata.computation``.
Its decision attaches to that message, carries the computation, and opens by
re-running it, with changed inputs on request. A backtest decision keeps its
evidence spine and opens by offering the typed retest. Both live in the same
decision index and answer the same search.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from argus.api import state as api_state
from argus.api.guest_access import guest_account_context, store_account_context
from argus.api.main import app
from argus.api.message_store import memory_message
from argus.api.routers.decisions import create_message_decision
from argus.api.schemas import BacktestRun, DecisionNoteCreate, EvidenceArtifact, User
from argus.domain.computations import ComputationKernel
from argus.domain.guest_workspaces import GuestWorkspace
from computation_harness import (
    SAVINGS_PROJECTION_KIND,
    registered_savings_projection,
)
from faker import Faker
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

fake = Faker()


@pytest.fixture
def harness_kernel() -> Iterator[ComputationKernel]:
    with registered_savings_projection() as kernel:
        yield kernel


def _client() -> TestClient:
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    return client


def _computed_answer(
    conversation_id: str,
    *,
    inputs: dict[str, Any] | None = None,
    content: str = "Nine months of 5,000 a month is 45,000, short of the iPad by 15,000.",
) -> str:
    message = memory_message(
        conversation_id=conversation_id,
        role="assistant",
        content=content,
        metadata={
            "computation": {
                "kind": SAVINGS_PROJECTION_KIND,
                "inputs": inputs
                or {"monthly_amount": 5000, "months": 9, "target_amount": 60_000},
            }
        },
    )
    return message.id


def _decision_path(conversation_id: str, message_id: str) -> str:
    return f"/api/v1/conversations/{conversation_id}/messages/{message_id}/decision"


def test_decision_on_a_computed_answer_is_recorded_retrieved_and_rerun(
    harness_kernel: ComputationKernel,
) -> None:
    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]
    message_id = _computed_answer(conversation["id"])

    recorded = client.post(
        _decision_path(conversation["id"], message_id),
        json={"decision_state": "promising", "note": "Put 5,000 a month toward it."},
    )

    assert recorded.status_code == 200, recorded.text
    decision = recorded.json()["decision"]
    assert decision["decision_state"] == "promising"
    assert decision["note"] == "Put 5,000 a month toward it."
    assert decision["source_conversation_id"] == conversation["id"]
    assert decision["source_message_id"] == message_id
    assert decision["computation"] == {
        "kind": SAVINGS_PROJECTION_KIND,
        "inputs": {"monthly_amount": 5000, "months": 9, "target_amount": 60_000},
    }
    assert decision["evidence_artifact_id"] is None
    assert decision["idea_id"] is None
    assert decision["idea_version_id"] is None
    # Nothing in the idea scaffolding was touched.
    assert api_state.store.ideas == {}
    assert api_state.store.idea_versions == {}
    assert api_state.store.evidence_artifacts == {}

    opened = client.get(f"/api/v1/decisions/{decision['id']}")

    assert opened.status_code == 200, opened.text
    body = opened.json()
    assert body["decision"]["id"] == decision["id"]
    assert body["computation"] == decision["computation"]
    assert body["rerun"]["status"] == "computed"
    assert body["rerun"]["kind"] == SAVINGS_PROJECTION_KIND
    assert body["rerun"]["result"] == {"saved_total": 45_000.0, "shortfall": 15_000.0}
    assert body["rerun"]["retest"] is None
    assert body["rerun"]["reason_code"] is None

    rerun = client.post(
        f"/api/v1/decisions/{decision['id']}/rerun",
        json={"inputs": {"months": 12}},
    )

    assert rerun.status_code == 200, rerun.text
    changed = rerun.json()
    assert changed["rerun"]["status"] == "computed"
    assert changed["rerun"]["inputs"]["months"] == 12
    assert changed["rerun"]["result"] == {"saved_total": 60_000.0, "shortfall": 0.0}
    # A re-run never rewrites the decision or its stored inputs.
    assert changed["decision"] == decision
    assert changed["computation"] == decision["computation"]
    assert (
        client.get(f"/api/v1/decisions/{decision['id']}").json()["computation"]
        == (decision["computation"])
    )


def test_the_answer_message_carries_the_decision_after_reload(
    harness_kernel: ComputationKernel,
) -> None:
    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]
    message_id = _computed_answer(conversation["id"])
    decision = client.post(
        _decision_path(conversation["id"], message_id),
        json={"decision_state": "watching"},
    ).json()["decision"]

    reloaded = client.get(f"/api/v1/conversations/{conversation['id']}/messages")

    assert reloaded.status_code == 200
    answer = next(item for item in reloaded.json()["items"] if item["id"] == message_id)
    assert answer["metadata"]["decision_note_id"] == decision["id"]
    assert answer["metadata"]["decision_state"] == "watching"
    assert answer["metadata"]["computation"]["kind"] == SAVINGS_PROJECTION_KIND


def test_the_transcript_read_takes_the_decision_from_its_owner_not_the_copy(
    harness_kernel: ComputationKernel,
) -> None:
    """A lost or stale stamp on the message cannot disagree with decision_notes."""
    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]
    message_id = _computed_answer(conversation["id"])
    decision = client.post(
        _decision_path(conversation["id"], message_id),
        json={"decision_state": "promising"},
    ).json()["decision"]

    with api_state.store.conversation_message_lock:
        messages = api_state.store.messages[conversation["id"]]
        for index, message in enumerate(messages):
            if message.id == message_id:
                messages[index] = message.model_copy(
                    update={
                        "metadata": {
                            **(message.metadata or {}),
                            "decision_note_id": "stale-copy",
                            "decision_state": "rejected",
                        }
                    }
                )

    reloaded = client.get(f"/api/v1/conversations/{conversation['id']}/messages")
    answer = next(item for item in reloaded.json()["items"] if item["id"] == message_id)
    assert answer["metadata"]["decision_note_id"] == decision["id"]
    assert answer["metadata"]["decision_state"] == "promising"

    del api_state.store.decision_notes[decision["id"]]
    reloaded = client.get(f"/api/v1/conversations/{conversation['id']}/messages")
    answer = next(item for item in reloaded.json()["items"] if item["id"] == message_id)
    assert "decision_note_id" not in answer["metadata"]
    assert "decision_state" not in answer["metadata"]


def test_decision_is_idempotent_per_answer_and_keeps_its_first_computation(
    harness_kernel: ComputationKernel,
) -> None:
    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]
    message_id = _computed_answer(conversation["id"])

    first = client.post(
        _decision_path(conversation["id"], message_id),
        json={"decision_state": "watching", "note": "Track it."},
    ).json()["decision"]
    second = client.post(
        _decision_path(conversation["id"], message_id),
        json={"decision_state": "rejected", "note": "Too slow."},
    ).json()["decision"]

    assert second["id"] == first["id"]
    assert second["decision_state"] == "rejected"
    assert second["note"] == "Too slow."
    assert second["computation"] == first["computation"]
    assert second["created_at"] == first["created_at"]
    assert (
        sum(
            1
            for row in api_state.store.decision_notes.values()
            if row.source_message_id == message_id
        )
        == 1
    )


def test_a_message_without_a_computation_offers_no_decision(
    harness_kernel: ComputationKernel,
) -> None:
    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]
    plain = memory_message(
        conversation_id=conversation["id"],
        role="assistant",
        content="Saving is a habit, not a number.",
        metadata={},
    )
    malformed = memory_message(
        conversation_id=conversation["id"],
        role="assistant",
        content="Malformed declaration.",
        metadata={"computation": {"kind": "Not A Slug", "inputs": {}}},
    )
    question = memory_message(
        conversation_id=conversation["id"],
        role="user",
        content="How much should I save?",
        metadata={"computation": {"kind": SAVINGS_PROJECTION_KIND, "inputs": {}}},
    )

    for message_id in (plain.id, malformed.id):
        refused = client.post(
            _decision_path(conversation["id"], message_id),
            json={"decision_state": "watching"},
        )
        assert refused.status_code == 409, refused.text
        assert refused.json()["code"] == "decision_attachment_unsupported"

    user_turn = client.post(
        _decision_path(conversation["id"], question.id),
        json={"decision_state": "watching"},
    )
    assert user_turn.status_code == 404
    assert user_turn.json()["code"] == "not_found"


def test_foreign_or_missing_targets_do_not_leak(
    harness_kernel: ComputationKernel,
) -> None:
    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]
    message_id = _computed_answer(conversation["id"])
    other_conversation = client.post("/api/v1/conversations", json={}).json()[
        "conversation"
    ]

    wrong_conversation = client.post(
        _decision_path(other_conversation["id"], message_id),
        json={"decision_state": "watching"},
    )
    missing_message = client.post(
        _decision_path(conversation["id"], fake.uuid4()),
        json={"decision_state": "watching"},
    )
    missing_decision = client.get(f"/api/v1/decisions/{fake.uuid4()}")
    missing_rerun = client.post(
        f"/api/v1/decisions/{fake.uuid4()}/rerun", json={"inputs": {}}
    )

    for response in (
        wrong_conversation,
        missing_message,
        missing_decision,
        missing_rerun,
    ):
        assert response.status_code == 404, response.text
        assert response.json()["code"] == "not_found"


def test_invalid_rerun_inputs_are_a_validation_problem_and_change_nothing(
    harness_kernel: ComputationKernel,
) -> None:
    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]
    message_id = _computed_answer(conversation["id"])
    decision = client.post(
        _decision_path(conversation["id"], message_id),
        json={"decision_state": "watching"},
    ).json()["decision"]

    rejected = client.post(
        f"/api/v1/decisions/{decision['id']}/rerun",
        json={"inputs": {"months": 0}},
    )
    stray_field = client.post(
        f"/api/v1/decisions/{decision['id']}/rerun",
        json={"inputs": {}, "kind": "backtest"},
    )

    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["code"] == "validation_error"
    assert "months" in str(rejected.json()["context"]["errors"])
    assert stray_field.status_code == 422
    assert (
        client.get(f"/api/v1/decisions/{decision['id']}").json()["computation"]
        == (decision["computation"])
    )


def test_a_decision_whose_kind_is_no_longer_registered_opens_as_unavailable() -> None:
    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]
    message_id = _computed_answer(conversation["id"])
    with registered_savings_projection():
        decision = client.post(
            _decision_path(conversation["id"], message_id),
            json={"decision_state": "watching"},
        ).json()["decision"]

    opened = client.get(f"/api/v1/decisions/{decision['id']}")

    assert opened.status_code == 200
    assert opened.json()["rerun"]["status"] == "unavailable"
    assert opened.json()["rerun"]["reason_code"] == "kernel_unavailable"
    assert opened.json()["computation"] == decision["computation"]


def test_computed_answer_decisions_join_the_decision_index(
    harness_kernel: ComputationKernel,
) -> None:
    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]
    message_id = _computed_answer(
        conversation["id"],
        content="Nine months of 5,000 a month reaches the iPad in December.",
    )
    client.post(
        _decision_path(conversation["id"], message_id),
        json={"decision_state": "promising", "note": "Commit to the plan."},
    )

    by_note = client.get("/api/v1/search?q=Commit%20to%20the%20plan&limit=20")
    by_answer = client.get("/api/v1/search?q=iPad%20in%20December&limit=20")
    filtered = client.get(
        "/api/v1/search?q=iPad&decision_state=promising&include_ledger_groups=true&limit=20"
    )
    excluded = client.get("/api/v1/search?q=iPad&decision_state=rejected&limit=20")

    for response in (by_note, by_answer):
        assert response.status_code == 200, response.text
        items = response.json()["items"]
        assert [item["id"] for item in items] == [conversation["id"]]
        assert items[0]["match"]["layer"] == "decision"
        assert items[0]["dossier"] is None
        assert items[0]["total_runs"] == 0
        assert items[0]["decision_states"] == ["promising"]
    assert [item["id"] for item in filtered.json()["items"]] == [conversation["id"]]
    ledger = {
        group["decision_state"]: group["count"]
        for group in filtered.json()["ledger_groups"]
    }
    assert ledger["promising"] == 1
    assert excluded.json()["items"] == []


def test_existing_backtest_decisions_open_with_a_derived_computation_and_retest(
    harness_kernel: ComputationKernel,
) -> None:
    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]
    user_id = api_state.store.get_or_create_dev_user().id
    now = datetime.now(timezone.utc)
    artifact_id = fake.uuid4()
    run_id = fake.uuid4()
    run = BacktestRun(
        id=run_id,
        conversation_id=conversation["id"],
        strategy_id=None,
        status="completed",
        asset_class="equity",
        symbols=["TSLA"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={},
        config_snapshot={
            "template": "buy_and_hold",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "timeframe": "1D",
            "starting_capital": 10_000,
            "resolved_strategy": {
                "strategy_type": "buy_and_hold",
                "asset_class": "equity",
            },
            "resolved_parameters": {
                "timeframe": "1D",
                "benchmark_symbol": "SPY",
                "sizing_mode": "capital_amount",
                "capital_amount": 10_000,
            },
        },
        conversation_result_card={
            "title": "TSLA buy and hold",
            "evidence_artifact_id": artifact_id,
            "idea_id": f"{artifact_id}-idea",
            "idea_version_id": f"{artifact_id}-version",
        },
        created_at=now,
    )
    artifact = EvidenceArtifact(
        id=artifact_id,
        idea_id=f"{artifact_id}-idea",
        idea_version_id=f"{artifact_id}-version",
        source_conversation_id=conversation["id"],
        source_run_id=run_id,
        artifact_type="backtest",
        lifecycle="captured",
        title="TSLA evidence",
        digest="TSLA returned 12.5%.",
        payload={},
        created_at=now,
        updated_at=now,
    )
    api_state.store.backtest_runs[run_id] = run
    api_state.store.backtest_run_owners[run_id] = user_id
    api_state.store.evidence_artifacts[artifact_id] = artifact
    api_state.store.evidence_artifact_owners[artifact_id] = user_id

    recorded = client.post(
        f"/api/v1/evidence-artifacts/{artifact_id}/decision",
        json={"decision_state": "watching", "note": "Hold."},
    )
    decision = recorded.json()["decision"]
    assert recorded.status_code == 200
    assert decision["evidence_artifact_id"] == artifact_id
    assert decision["idea_id"] and decision["idea_version_id"]
    assert decision["computation"] is None
    assert decision["source_message_id"] is None

    opened = client.get(f"/api/v1/decisions/{decision['id']}")

    assert opened.status_code == 200, opened.text
    body = opened.json()
    assert body["computation"] == {
        "kind": "backtest",
        "inputs": {"source_run_id": run_id},
    }
    assert body["rerun"]["status"] == "confirmation_required"
    assert body["rerun"]["retest"]["type"] == "retest_run"
    assert body["rerun"]["retest"]["source_run_id"] == run_id
    assert body["rerun"]["result"] is None

    edited = client.post(
        f"/api/v1/decisions/{decision['id']}/rerun",
        json={"inputs": {"source_run_id": fake.uuid4()}},
    )
    assert edited.status_code == 200
    assert edited.json()["rerun"]["status"] == "unavailable"
    assert edited.json()["rerun"]["reason_code"] == "inputs_not_editable"

    # The run-keyed dossier surfaces are exactly as before.
    dossiers = client.get(f"/api/v1/conversations/{conversation['id']}/run-dossiers")
    assert dossiers.status_code == 200
    assert dossiers.json()["decided_runs"] == 1
    assert dossiers.json()["items"][0]["decision"]["state"] == "watching"

    # The result card's decision is read from decision_notes too: wiping the
    # stored stamp changes nothing the transcript shows.
    result_message = memory_message(
        conversation_id=conversation["id"],
        role="assistant",
        content="",
        metadata={
            "result_run_id": run_id,
            "result_card": {
                "title": "TSLA buy and hold",
                "evidence_artifact_id": artifact_id,
            },
        },
    )
    reloaded = client.get(f"/api/v1/conversations/{conversation['id']}/messages")
    card = next(
        item for item in reloaded.json()["items"] if item["id"] == result_message.id
    )
    assert card["metadata"]["decision_note_id"] == decision["id"]
    assert card["metadata"]["decision_state"] == "watching"
    assert card["metadata"]["result_card"]["decision_state"] == "watching"
    assert card["metadata"]["result_card"]["evidence_lifecycle"] == "decided"


def test_guests_are_asked_to_sign_in_before_deciding_on_a_computed_answer(
    harness_kernel: ComputationKernel,
) -> None:
    now = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)
    user = User(id="guest-1", email=None, created_at=now, updated_at=now)
    workspace = GuestWorkspace(
        user_id=user.id,
        conversation_id="conversation-1",
        status="active",
        created_at=now,
        expires_at=now + timedelta(days=7),
        claimed_by=None,
        claimed_at=None,
        updated_at=now,
    )
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})
    request.state.request_id = "decision-attachment-guest-test"
    store_account_context(request, guest_account_context(workspace))

    with pytest.raises(HTTPException) as excinfo:
        create_message_decision(
            conversation_id=workspace.conversation_id,
            message_id="message-1",
            payload=DecisionNoteCreate(decision_state="watching"),
            request=request,
            user=user,
        )

    assert excinfo.value.status_code == 403
    assert excinfo.value.detail["code"] == "account_conversion_required"
    assert excinfo.value.detail["context"] == {"reason": "save_decision"}
