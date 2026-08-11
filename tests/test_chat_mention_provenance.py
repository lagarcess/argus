from __future__ import annotations

from argus.agent_runtime.resolution import mention_to_provenance
from argus.api.chat.request_admission import persisted_chat_mentions
from argus.api.schemas import ChatStreamRequest


def test_chat_mention_accepts_an_optional_display_range() -> None:
    request = ChatStreamRequest.model_validate(
        {
            "conversation_id": "conversation-1",
            "message": "Buy AAPL when RSI falls",
            "mentions": [
                {
                    "id": "asset:equity:AAPL",
                    "type": "asset",
                    "label": "AAPL · Apple Inc.",
                    "symbol": "AAPL",
                    "asset_class": "equity",
                    "description": "Apple Inc.",
                    "insert_text": "AAPL",
                    "provider": "alpaca",
                    "message_range": {"start": 4, "end": 8},
                }
            ],
        }
    )

    assert request.mentions[0].model_dump()["message_range"] == {
        "start": 4,
        "end": 8,
    }


def test_admission_drops_an_invalid_display_range_without_changing_provenance() -> None:
    message = "Buy AAPL when RSI falls"
    request = ChatStreamRequest.model_validate(
        {
            "conversation_id": "conversation-1",
            "message": message,
            "mentions": [
                {
                    "id": "asset:equity:AAPL",
                    "type": "asset",
                    "label": "AAPL · Apple Inc.",
                    "symbol": "AAPL",
                    "asset_class": "equity",
                    "description": "Apple Inc.",
                    "insert_text": "AAPL",
                    "provider": "alpaca",
                    "message_range": {"start": 4, "end": 20},
                }
            ],
        }
    )

    persisted = persisted_chat_mentions(request, message)
    provenance = mention_to_provenance(
        request.mentions[0].model_dump(mode="python"), index=0
    ).model_dump()

    assert persisted[0]["insert_text"] == "AAPL"
    assert "message_range" not in persisted[0]
    assert provenance == {
        "field": "asset_universe[0]",
        "raw_text": "AAPL",
        "source": "user_mention",
        "candidate_kind": "asset",
        "resolution_status": "resolved",
        "canonical_symbol": "AAPL",
        "asset_class": "equity",
        "validated_by": "client_mention",
        "confidence": "high",
    }


def test_malformed_range_is_ignored_instead_of_rejecting_the_chat_request() -> None:
    request = ChatStreamRequest.model_validate(
        {
            "conversation_id": "conversation-1",
            "message": "Buy AAPL",
            "mentions": [
                {
                    "id": "asset:equity:AAPL",
                    "type": "asset",
                    "label": "AAPL · Apple Inc.",
                    "symbol": "AAPL",
                    "asset_class": "equity",
                    "description": "Apple Inc.",
                    "insert_text": "AAPL",
                    "provider": "alpaca",
                    "message_range": {"start": "four", "end": 8},
                }
            ],
        }
    )

    assert request.mentions[0].message_range is None
    assert "message_range" not in persisted_chat_mentions(request, "Buy AAPL")[0]


def test_admission_uses_utf16_offsets_for_a_ticker_after_an_emoji() -> None:
    message = "🚀 Buy AAPL"
    request = ChatStreamRequest.model_validate(
        {
            "conversation_id": "conversation-1",
            "message": message,
            "mentions": [
                {
                    "id": "asset:equity:AAPL",
                    "type": "asset",
                    "label": "AAPL · Apple Inc.",
                    "symbol": "AAPL",
                    "asset_class": "equity",
                    "description": "Apple Inc.",
                    "insert_text": "AAPL",
                    "provider": "alpaca",
                    "message_range": {"start": 7, "end": 11},
                }
            ],
        }
    )

    assert persisted_chat_mentions(request, message)[0]["message_range"] == {
        "start": 7,
        "end": 11,
    }
