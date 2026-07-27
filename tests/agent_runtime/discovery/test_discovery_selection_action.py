from __future__ import annotations

from argus.api.chat.actions import chat_request_message, persisted_chat_action
from argus.api.chat.request_admission import ChatRequestAdmission
from argus.api.schemas import ChatActionPayload, ChatStreamRequest


def _selection_request() -> ChatStreamRequest:
    return ChatStreamRequest(
        conversation_id="conversation-1",
        message="Backtest CRWD",
        action=ChatActionPayload(
            type="select_discovery_candidate",
            label="Backtest CRWD",
            labelKey="chat.discovery_results.test_candidate",
            payload={"symbol": "CRWD", "name": "CrowdStrike Holdings"},
        ),
    )


class TestDiscoverySelectionAction:
    def test_runtime_message_is_the_chip_label(self) -> None:
        assert chat_request_message(_selection_request()) == "Backtest CRWD"
        assert (
            chat_request_message(_selection_request(), language="es-419")
            == "Backtest CRWD"
        )

    def test_chat_action_metadata_persists_for_transcript_chips(self) -> None:
        persisted = persisted_chat_action(_selection_request())
        assert persisted is not None
        assert persisted["type"] == "select_discovery_candidate"
        assert persisted["label"] == "Backtest CRWD"
        assert persisted["labelKey"] == "chat.discovery_results.test_candidate"
        assert persisted["payload"] == {
            "symbol": "CRWD",
            "name": "CrowdStrike Holdings",
        }

    def test_runtime_receives_no_structured_action_context(self) -> None:
        admission = ChatRequestAdmission(
            payload=_selection_request(),
            request=None,  # type: ignore[arg-type]
            user_id="user-1",
            conversation_id="conversation-1",
            language="en",
            request_message_candidate=None,
        )
        assert admission.runtime_action_context() is None
