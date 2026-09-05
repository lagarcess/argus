from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from argus.api import state as api_state
from argus.api.conversation_previews import conversation_previews
from argus.api.schemas import Conversation, Message, User
from argus.domain.conversation_previews import project_conversation_preview
from argus.domain.store import AlphaStore


@pytest.mark.parametrize(
    "marker,kind",
    [
        ("result_card", "result"),
        ("confirmation_card", "confirmation"),
        ("result_fact_bank", "result"),
    ],
)
def test_old_artifact_prose_never_enters_preview(marker, kind):
    projected = project_conversation_preview(
        {
            "role": "assistant",
            "content": "Saved English prose",
            "metadata": {marker: {"symbols": ["NVDA"]}},
        }
    )
    assert projected.kind == kind
    assert projected.text is None
    assert "Saved English" not in projected.model_dump_json()


def test_user_text_remains_verbatim_even_with_artifact_metadata():
    projected = project_conversation_preview(
        {"role": "user", "content": "My English idea", "metadata": {"result_card": {}}}
    )
    assert projected.kind == "text"
    assert projected.text == "My English idea"


def test_confirmation_preview_symbols_come_from_canonical_payload():
    symbols = ["AAPL", "MSFT"]
    projected = project_conversation_preview(
        {
            "role": "assistant",
            "content": "PRIVATE CONFIRMATION PROSE",
            "metadata": {
                "confirmation_card": {
                    "title": "Wrong rendered asset label",
                    "symbols": ["STALE"],
                    "strategy_type": "dca_accumulation",
                },
                "confirmation_payload": {"strategy": {"asset_universe": symbols}},
            },
        }
    )
    assert projected.kind == "confirmation"
    assert projected.symbols == symbols
    assert projected.template == "dca_accumulation"
    assert projected.text is None
    assert "Wrong rendered asset label" not in projected.model_dump_json()


@pytest.mark.parametrize("role", ["system", "tool"])
def test_internal_message_content_is_never_a_public_preview(role):
    projected = project_conversation_preview(
        {"role": role, "content": "INTERNAL PROVIDER DETAILS", "metadata": {}}
    )
    assert projected.kind == "unavailable"
    assert projected.text is None
    assert "INTERNAL PROVIDER DETAILS" not in projected.model_dump_json()


def test_batch_read_failure_returns_unavailable_without_error_detail(monkeypatch, capfd):
    calls = []

    def failing_read(**kwargs):
        calls.append(kwargs)
        raise RuntimeError("PRIVATE DATABASE ERROR DETAIL")

    monkeypatch.setattr(
        api_state,
        "supabase_gateway",
        SimpleNamespace(read_conversation_preview_messages=failing_read),
    )
    previews = conversation_previews(user_id="owner", conversation_ids=["a", "b"])
    assert len(calls) == 1
    assert set(previews) == {"a", "b"}
    assert all(preview.kind == "unavailable" for preview in previews.values())
    assert all(preview.text is None for preview in previews.values())
    assert "PRIVATE DATABASE ERROR DETAIL" not in capfd.readouterr().err


def test_memory_preview_selects_latest_owned_message(monkeypatch):
    now = datetime.now(timezone.utc)
    messages = {
        "owned": [
            Message(
                id="a",
                conversation_id="owned",
                role="assistant",
                content="English",
                metadata={"result_card": {}},
                created_at=now,
            )
        ],
        "other": [
            Message(
                id="b",
                conversation_id="other",
                role="user",
                content="Private",
                created_at=now,
            )
        ],
    }
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    monkeypatch.setattr(
        api_state,
        "store",
        AlphaStore(
            messages=messages,
            conversation_owners={"owned": "owner", "other": "someone-else"},
        ),
    )
    previews = conversation_previews(user_id="owner", conversation_ids=["owned", "other"])
    assert previews["owned"].kind == "result"
    assert previews["other"].kind == "unavailable"


def test_persistent_projection_is_one_bounded_batch(monkeypatch):
    calls = []

    def read(**kwargs):
        calls.append(kwargs)
        return [
            {
                "conversation_id": value,
                "role": "assistant",
                "metadata": {"confirmation_card": {}},
            }
            for value in kwargs["conversation_ids"]
        ]

    monkeypatch.setattr(
        api_state,
        "supabase_gateway",
        SimpleNamespace(read_conversation_preview_messages=read),
    )
    previews = conversation_previews(user_id="owner", conversation_ids=["a", "b", "a"])
    assert len(calls) == 1
    assert calls[0] == {"user_id": "owner", "conversation_ids": ["a", "b"]}
    assert all(item.kind == "confirmation" for item in previews.values())
    with pytest.raises(ValueError):
        conversation_previews(
            user_id="owner", conversation_ids=[str(index) for index in range(101)]
        )


@pytest.mark.parametrize("archived", [False, True])
def test_existing_artifact_previews_reach_conversation_and_history_reads(
    monkeypatch, archived
):
    from argus.api.guest_access import registered_account_context, store_account_context
    from argus.api.routers.conversations import list_conversations
    from argus.api.routers.history import history
    from starlette.requests import Request

    now = datetime.now(timezone.utc)
    conversation = Conversation(
        id="chat",
        title="NVDA",
        title_source="user_renamed",
        language="en",
        archived=archived,
        created_at=now,
        updated_at=now,
        last_message_preview="Saved English result",
    )
    message = Message(
        id="result",
        conversation_id=conversation.id,
        role="assistant",
        content="Saved English result",
        metadata={
            "result_fact_bank": {
                "symbols": ["NVDA"],
                "config_snapshot": {"template": "dca_accumulation"},
            }
        },
        created_at=now,
    )
    store = AlphaStore(
        conversations={conversation.id: conversation},
        conversation_owners={conversation.id: "owner"},
        messages={conversation.id: [message]},
    )
    monkeypatch.setattr(api_state, "store", store)
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    user = User(
        id="owner",
        email=None,
        language="es-419",
        locale="es-419",
        created_at=now,
        updated_at=now,
    )
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    store_account_context(request, registered_account_context(user_id=user.id))
    rows = list_conversations(
        request=request,
        limit=20,
        cursor=None,
        archived=archived,
        deleted=False,
        user=user,
    )
    historical = history(
        request=request,
        limit=20,
        cursor=None,
        archived=archived,
        deleted=False,
        user=user,
    )
    assert rows.items[0].preview == historical.items[0].preview
    assert rows.items[0].preview.kind == "result"
    assert rows.items[0].preview.symbols == ["NVDA"]
    assert rows.items[0].preview.template == "dca_accumulation"
    assert "Saved English result" not in rows.model_dump_json()
    assert "Saved English result" not in historical.model_dump_json()
    assert store.messages[conversation.id][0].content == "Saved English result"
