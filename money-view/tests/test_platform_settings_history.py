"""Both history owners participate in one bounded settings lifecycle."""

import pytest
from fastapi.testclient import TestClient
from platform_identity_factory import identity_context
from server.app import create_app
from server.interpreter import FixtureInterpreter
from server.platform import assistant, chat, settings_history
from server.platform.assistant_contracts import Ask, ConversationUpdate, TrashAll
from server.platform.chat_contracts import ConversationCreate, ConversationPatch
from server.platform.common import PlatformError, get_context

SOURCES = ("chat", "assistant")
CONFIRMATION = {"confirmation": "TRASH HOUSEHOLD CONVERSATIONS"}


def conversation(store, context, source, state="active"):
    if source == "chat":
        item = chat.create_conversation(
            ConversationCreate(title="Household question"), store, context
        )
        chat.update_conversation(
            item["id"], ConversationPatch(state=state), store, context
        )
        return item["id"]
    result = assistant.answer_question(store, context, Ask(action="net_worth"))
    assistant.update_conversation(
        store, context, result["conversation_id"], ConversationUpdate(state=state)
    )
    return result["conversation_id"]


@pytest.fixture
def history(tmp_path):
    app = create_app(tmp_path / "history.sqlite", FixtureInterpreter())
    with TestClient(app) as client:
        store = app.state.store
        owner = identity_context(
            store, user_id="history-owner", household_id="history-household"
        )
        foreign = identity_context(
            store, user_id="foreign-owner", household_id="foreign-household"
        )
        app.dependency_overrides[get_context] = lambda: owner
        records = {
            source: {
                state: conversation(store, owner, source, state)
                for state in ("active", "archived", "trashed")
            }
            for source in SOURCES
        }
        outside = {
            source: conversation(store, foreign, source, "archived") for source in SOURCES
        }
        yield client, store, owner, foreign, records, outside


@pytest.mark.parametrize("source", SOURCES)
def test_pages_preserve_source_visibility_restore_and_export(history, source):
    client, store, owner, _, records, outside = history
    for _ in range(21):
        conversation(store, owner, source, "archived")
    pages = [
        client.get(
            "/api/platform/settings/history",
            params={"source": source, "state": "archived", "offset": offset},
        ).json()
        for offset in (0, 20)
    ]
    assert [len(page["items"]) for page in pages] == [20, 2]
    assert all(page["source"] == source and page["total"] == 22 for page in pages)
    ids = [item["id"] for page in pages for item in page["items"]]
    assert len(set(ids)) == len(ids)
    assert outside[source] not in ids
    target = records[source]["archived"]
    assert target in ids
    export = client.get(f"/api/platform/{source}/conversations/{target}/export")
    assert export.status_code == 200
    assert export.json()["conversation"]["id"] == target
    restored = client.patch(
        f"/api/platform/{source}/conversations/{target}", json={"state": "active"}
    )
    assert restored.status_code == 200
    assert restored.json()["state"] == "active"
    assert (
        client.get(
            "/api/platform/settings/history",
            params={"source": source, "state": "archived"},
        ).json()["total"]
        == 21
    )
    assert (
        client.patch(
            f"/api/platform/{source}/conversations/{outside[source]}",
            json={"state": "active"},
        ).status_code
        == 404
    )


def test_bulk_covers_all_pages_and_household_members_once(history):
    client, store, owner, foreign, records, outside = history
    member = identity_context(
        store, user_id="history-member", household_id=owner.household_id, role="editor"
    )
    for source in SOURCES:
        for _ in range(21):
            conversation(store, member, source)
    result = client.post("/api/platform/settings/history/trash-all", json=CONFIRMATION)
    assert result.status_code == 200, result.text
    assert result.json() == {
        "trashed": 46,
        "counts": {"chat": 23, "assistant": 23},
        "scope": "household",
        "restorable": True,
    }
    for source in SOURCES:
        page = client.get(
            "/api/platform/settings/history",
            params={"source": source, "state": "trashed"},
        ).json()
        assert page["total"] == 24
        assert (
            client.get(
                f"/api/platform/{source}/conversations/{records[source]['archived']}/export"
            ).status_code
            == 200
        )
        assert (
            settings_history.history(source, store, foreign)["items"][0]["id"]
            == outside[source]
        )
    assert (
        client.post("/api/platform/settings/history/trash-all", json=CONFIRMATION).json()[
            "trashed"
        ]
        == 0
    )


def test_bulk_failure_rolls_back_both_owners(history, monkeypatch):
    client, store, owner, _, records, _ = history
    original = chat.trash_all_conversations

    def fail_after_chat(connection, context):
        original(connection, context)
        raise PlatformError("injected_history_failure", 409)

    monkeypatch.setattr(chat, "trash_all_conversations", fail_after_chat)
    assert (
        client.post(
            "/api/platform/settings/history/trash-all", json=CONFIRMATION
        ).status_code
        == 409
    )
    for source in SOURCES:
        for state, record_id in records[source].items():
            assert [
                item["id"]
                for item in settings_history.history(source, store, owner, state)["items"]
            ] == [record_id]


@pytest.mark.parametrize("role", ["viewer", "editor"])
def test_bulk_requires_owner_and_confirmation(history, role):
    client, store, owner, _, _, _ = history
    assert (
        client.post(
            "/api/platform/settings/history/trash-all", json={"confirmation": "wrong"}
        ).status_code
        == 422
    )
    context = identity_context(
        store, user_id=f"history-{role}", household_id=owner.household_id, role=role
    )
    client.app.dependency_overrides[get_context] = lambda: context
    assert (
        client.post(
            "/api/platform/settings/history/trash-all", json=CONFIRMATION
        ).status_code
        == 403
    )
    for source in SOURCES:
        assert (
            client.get(
                "/api/platform/settings/history", params={"source": source}
            ).status_code
            == 200
        )


def test_bulk_rechecks_captured_owner_authority(history):
    _, store, owner, _, records, _ = history
    with store.connection(write=True) as connection:
        connection.execute(
            "UPDATE p_memberships SET role='viewer' WHERE household_id=? AND user_id=?",
            (owner.household_id, owner.user_id),
        )
    with pytest.raises(PlatformError, match="household_access_changed"):
        settings_history.trash_all(TrashAll(**CONFIRMATION), store, owner)
    assert (
        assistant.list_conversations(store, owner)["items"][0]["id"]
        == records["assistant"]["active"]
    )


@pytest.mark.parametrize(
    "params",
    [
        {"source": "unknown"},
        {"source": "chat", "state": "unknown"},
        {"source": "chat", "limit": 101},
        {"source": "assistant", "offset": -1},
    ],
)
def test_validates_source_state_and_page(history, params):
    client, *_ = history
    assert client.get("/api/platform/settings/history", params=params).status_code == 422
