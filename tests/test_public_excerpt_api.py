"""End-to-end API behaviour for public evidence receipts.

Covers the flag gate, the rate limit, revocation following deletion, and the
construction guard on the public route module.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from argus.api import state as api_state
from argus.api.main import app
from argus.api.routers import evidence_receipts, public_receipts
from argus.domain.public_excerpts import PUBLIC_EXCERPT_PATH_PREFIX
from fastapi.testclient import TestClient

from tests.public_excerpt_factories import (
    ARTIFACT_ID,
    CONVERSATION_ID,
    build_artifact,
    build_conversation,
    build_run,
)

CREATE_PATH = f"/api/v1/evidence-artifacts/{ARTIFACT_ID}/public-excerpt"
LIST_PATH = "/api/v1/public-excerpts"


@pytest.fixture(autouse=True)
def _memory_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    evidence_receipts.reset_receipt_create_limiter_for_tests()
    public_receipts.reset_receipt_funnel_limiter_for_tests()


@pytest.fixture
def sharing_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARGUS_EVIDENCE_RECEIPT_SHARING_ENABLED", "true")


@pytest.fixture
def sharing_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARGUS_EVIDENCE_RECEIPT_SHARING_ENABLED", raising=False)


def _client() -> TestClient:
    client = TestClient(app)
    api_state.store.reset()
    return client


def _seed(client: TestClient) -> str:
    user_id = api_state.store.get_or_create_dev_user().id
    conversation = build_conversation()
    artifact = build_artifact()
    run = build_run()
    api_state.store.conversations[conversation.id] = conversation
    api_state.store.conversation_owners[conversation.id] = user_id
    api_state.store.evidence_artifacts[artifact.id] = artifact
    api_state.store.evidence_artifact_owners[artifact.id] = user_id
    api_state.store.backtest_runs[run.id] = run
    api_state.store.backtest_run_owners[run.id] = user_id
    return user_id


def _create(client: TestClient, note: str | None = None) -> dict[str, Any]:
    response = client.post(CREATE_PATH, json={"owner_note": note})
    assert response.status_code == 200, response.text
    return response.json()["receipt"]


# ── The default-off flag ──────────────────────────────────────────────────────


def test_every_receipt_route_is_absent_while_the_flag_is_off(
    sharing_off: None,
) -> None:
    client = _client()
    _seed(client)
    assert client.post(CREATE_PATH, json={}).status_code == 404
    assert client.get(LIST_PATH).status_code == 404
    assert client.delete(f"{LIST_PATH}/anything").status_code == 404
    assert client.get("/api/v1/public/receipts/abcdefghijklmnopqrstuvwx").status_code == (
        404
    )
    assert client.post(
        "/api/v1/public/receipt-funnel", json={"stage": "try_argus"}
    ).status_code == 404


def test_flag_off_leaves_no_receipt_state_behind(sharing_off: None) -> None:
    client = _client()
    _seed(client)
    client.post(CREATE_PATH, json={"owner_note": "hello"})
    assert api_state.store.public_excerpt_snapshots == {}


def test_flag_off_responses_are_byte_identical_to_a_route_that_never_existed(
    sharing_off: None,
) -> None:
    """Pins the flag-off byte identity so it cannot drift back.

    A distinctive problem body would answer 404 and still advertise that receipt
    code is deployed. The reference is a path that genuinely does not exist.
    """
    client = _client()
    _seed(client)
    reference = client.get("/api/v1/definitely-not-a-route")
    assert reference.status_code == 404

    for method, path, body in (
        ("POST", CREATE_PATH, {}),
        ("GET", LIST_PATH, None),
        ("DELETE", f"{LIST_PATH}/anything", None),
        ("GET", "/api/v1/public/receipts/abcdefghijklmnopqrstuvwx", None),
        ("POST", "/api/v1/public/receipt-funnel", {"stage": "try_argus"}),
    ):
        response = client.request(method, path, json=body)
        assert response.status_code == reference.status_code, path
        assert response.content == reference.content, path
        assert response.headers.get("content-type") == reference.headers.get(
            "content-type"
        ), path


# ── The happy path ────────────────────────────────────────────────────────────


def test_created_receipt_is_readable_anonymously_and_carries_only_the_payload(
    sharing_on: None,
) -> None:
    client = _client()
    _seed(client)
    receipt = _create(client, note="Surprised by the drawdown.")

    assert receipt["path"] == f"{PUBLIC_EXCERPT_PATH_PREFIX}{receipt['public_id']}"
    view = client.get(f"/api/v1/public/receipts/{receipt['public_id']}")
    assert view.status_code == 200
    body = view.json()
    assert body["status"] == "available"
    assert body["indexing"] == "noindex, nofollow"
    assert body["payload"]["owner_note"] == "Surprised by the drawdown."
    assert set(body) == {"public_id", "status", "indexing", "created_at", "payload"}


def test_public_read_response_contains_no_private_identifier(sharing_on: None) -> None:
    client = _client()
    user_id = _seed(client)
    receipt = _create(client)
    raw = client.get(f"/api/v1/public/receipts/{receipt['public_id']}").text
    for private_id in (user_id, CONVERSATION_ID, ARTIFACT_ID, build_run().id):
        assert private_id not in raw


def test_owner_list_shows_the_receipt_without_a_source_reference(
    sharing_on: None,
) -> None:
    client = _client()
    _seed(client)
    receipt = _create(client)
    listed = client.get(LIST_PATH).json()["items"]
    assert [item["id"] for item in listed] == [receipt["id"]]
    assert set(listed[0]) == {
        "id",
        "public_id",
        "path",
        "title",
        "symbols",
        "date_range_display",
        "created_at",
        "revoked_at",
        "revocation_reason",
    }


# ── Revocation ────────────────────────────────────────────────────────────────


def test_owner_revocation_takes_effect_on_the_next_read(sharing_on: None) -> None:
    client = _client()
    _seed(client)
    receipt = _create(client)

    revoked = client.delete(f"{LIST_PATH}/{receipt['id']}")
    assert revoked.status_code == 200
    assert revoked.json()["receipt"]["revocation_reason"] == "owner_revoked"

    view = client.get(f"/api/v1/public/receipts/{receipt['public_id']}").json()
    assert view["status"] == "revoked"
    assert view["payload"] is None


def test_deleting_the_conversation_revokes_its_receipt(sharing_on: None) -> None:
    client = _client()
    _seed(client)
    receipt = _create(client)

    deleted = client.delete(f"/api/v1/conversations/{CONVERSATION_ID}")
    assert deleted.status_code == 200

    view = client.get(f"/api/v1/public/receipts/{receipt['public_id']}").json()
    assert view["status"] == "revoked"
    listed = client.get(LIST_PATH).json()["items"]
    assert listed[0]["revocation_reason"] == "source_deleted"


def test_deleting_all_conversations_revokes_every_receipt(sharing_on: None) -> None:
    client = _client()
    _seed(client)
    receipt = _create(client)

    assert client.delete("/api/v1/conversations").status_code == 200

    view = client.get(f"/api/v1/public/receipts/{receipt['public_id']}").json()
    assert view["status"] == "revoked"


def test_a_revoked_link_answers_a_tombstone_not_a_not_found(sharing_on: None) -> None:
    client = _client()
    _seed(client)
    receipt = _create(client)
    client.delete(f"{LIST_PATH}/{receipt['id']}")

    response = client.get(f"/api/v1/public/receipts/{receipt['public_id']}")
    assert response.status_code == 200
    assert response.json()["status"] == "revoked"


def test_an_unknown_link_is_indistinguishable_from_a_revoked_one(
    sharing_on: None,
) -> None:
    client = _client()
    _seed(client)
    known = _create(client)
    client.delete(f"{LIST_PATH}/{known['id']}")

    revoked = client.get(f"/api/v1/public/receipts/{known['public_id']}").json()
    unknown = client.get("/api/v1/public/receipts/zzzzzzzzzzzzzzzzzzzzzzzz").json()
    assert revoked["status"] == unknown["status"] == "revoked"
    assert revoked["payload"] is unknown["payload"] is None


def test_revoking_twice_is_not_an_error_and_does_not_reverse(sharing_on: None) -> None:
    client = _client()
    _seed(client)
    receipt = _create(client)
    first = client.delete(f"{LIST_PATH}/{receipt['id']}").json()["receipt"]
    second = client.delete(f"{LIST_PATH}/{receipt['id']}").json()["receipt"]
    assert first["revoked_at"] == second["revoked_at"]


def test_a_revoked_result_can_be_shared_again_as_a_new_link(sharing_on: None) -> None:
    client = _client()
    _seed(client)
    first = _create(client)
    client.delete(f"{LIST_PATH}/{first['id']}")

    second = _create(client)
    assert second["public_id"] != first["public_id"]
    assert (
        client.get(f"/api/v1/public/receipts/{first['public_id']}").json()["status"]
        == "revoked"
    )
    assert (
        client.get(f"/api/v1/public/receipts/{second['public_id']}").json()["status"]
        == "available"
    )


# ── Abuse posture ─────────────────────────────────────────────────────────────


def test_receipt_creation_is_rate_limited(sharing_on: None) -> None:
    client = _client()
    user_id = _seed(client)
    # Each new artifact is a distinct receipt, so the limit is what stops the run.
    for index in range(evidence_receipts.RECEIPT_CREATE_LIMIT):
        artifact = build_artifact(artifact_id=f"artifact-{index:04d}")
        api_state.store.evidence_artifacts[artifact.id] = artifact
        api_state.store.evidence_artifact_owners[artifact.id] = user_id
        response = client.post(
            f"/api/v1/evidence-artifacts/{artifact.id}/public-excerpt", json={}
        )
        assert response.status_code == 200, response.text

    blocked = build_artifact(artifact_id="artifact-blocked")
    api_state.store.evidence_artifacts[blocked.id] = blocked
    api_state.store.evidence_artifact_owners[blocked.id] = user_id
    refused = client.post(
        f"/api/v1/evidence-artifacts/{blocked.id}/public-excerpt", json={}
    )
    assert refused.status_code == 429
    assert refused.headers["Retry-After"]


def test_a_note_with_a_credential_shaped_token_is_refused(sharing_on: None) -> None:
    client = _client()
    _seed(client)
    response = client.post(
        CREATE_PATH, json={"owner_note": "token EXAMPLENOTAREALCREDENTIALTOKEN"}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "receipt_note_rejected"
    assert api_state.store.public_excerpt_snapshots == {}


def test_a_note_longer_than_the_bound_is_refused_by_the_schema(
    sharing_on: None,
) -> None:
    client = _client()
    _seed(client)
    response = client.post(CREATE_PATH, json={"owner_note": "word " * 200})
    assert response.status_code == 422


def test_an_unowned_artifact_cannot_be_shared(sharing_on: None) -> None:
    client = _client()
    _seed(client)
    artifact = build_artifact(artifact_id="artifact-owned-by-someone-else")
    api_state.store.evidence_artifacts[artifact.id] = artifact
    api_state.store.evidence_artifact_owners[artifact.id] = "another-user"
    response = client.post(
        f"/api/v1/evidence-artifacts/{artifact.id}/public-excerpt", json={}
    )
    assert response.status_code == 404


def test_the_funnel_endpoint_stores_nothing_and_accepts_one_stage(
    sharing_on: None,
) -> None:
    client = _client()
    assert (
        client.post(
            "/api/v1/public/receipt-funnel", json={"stage": "try_argus"}
        ).status_code
        == 204
    )
    assert (
        client.post(
            "/api/v1/public/receipt-funnel", json={"stage": "receipt_viewed"}
        ).status_code
        == 422
    )
    assert api_state.store.public_excerpt_snapshots == {}


# ── Construction guard on the public route module ─────────────────────────────

PUBLIC_ROUTER_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "argus"
    / "api"
    / "routers"
    / "public_receipts.py"
)

FORBIDDEN_IDENTIFIER_FRAGMENTS = (
    "conversation",
    "message",
    "backtest",
    "evidence_artifact",
    "idea",
    "decision",
    "memory",
    "supabase_gateway",
    "current_user",
    "store",
)


def test_the_public_route_module_names_nothing_private() -> None:
    """The public read cannot reach private data because it cannot name it.

    A behavioural proof lives in test_public_excerpt_receipts.py; this is the
    cheap structural guard that stops a private read being added here later.
    """
    tree = ast.parse(PUBLIC_ROUTER_SOURCE.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.alias):
            names.add(node.asname or node.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    offenders = {
        name
        for name in names
        for fragment in FORBIDDEN_IDENTIFIER_FRAGMENTS
        if fragment in name.lower()
    }
    assert offenders == set(), f"public route module names private data: {offenders}"


def test_the_public_route_module_holds_only_the_reader_and_the_funnel() -> None:
    tree = ast.parse(PUBLIC_ROUTER_SOURCE.read_text(encoding="utf-8"))
    functions = [
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
    ]
    assert functions == [
        "reset_receipt_funnel_limiter_for_tests",
        "read_public_receipt",
        "record_receipt_funnel_stage",
    ]
