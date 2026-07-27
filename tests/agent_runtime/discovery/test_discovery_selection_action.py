from __future__ import annotations

from argus.agent_runtime.resolution import mention_to_provenance
from argus.api.chat.actions import chat_request_message, persisted_chat_action
from argus.api.chat.request_admission import ChatRequestAdmission
from argus.api.schemas import (
    ChatActionPayload,
    ChatMentionPayload,
    ChatStreamRequest,
)


def _selection_request(*, with_identity: bool = False) -> ChatStreamRequest:
    return ChatStreamRequest(
        conversation_id="conversation-1",
        message="Backtest CRWD",
        action=ChatActionPayload(
            type="select_discovery_candidate",
            label="Backtest CRWD",
            labelKey="chat.discovery_results.test_candidate",
            payload={
                "symbol": "CRWD",
                "name": "CrowdStrike Holdings",
                "asset_class": "equity",
            },
        ),
        mentions=(
            [
                ChatMentionPayload(
                    id="discovery-candidate-CRWD",
                    type="asset",
                    label="CrowdStrike Holdings",
                    symbol="CRWD",
                    asset_class="equity",
                    insert_text="CRWD",
                )
            ]
            if with_identity
            else []
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
        # asset_class rides along so a transcript chip still knows what the
        # resolver decided after a reload, not just which ticker was tapped.
        assert persisted["payload"] == {
            "symbol": "CRWD",
            "name": "CrowdStrike Holdings",
            "asset_class": "equity",
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


class TestDiscoverySelectionIdentity:
    """A tapped candidate already passed resolve_asset(); the turn keeps that."""

    def test_selection_carries_resolver_identity_as_a_mention(self) -> None:
        request = _selection_request(with_identity=True)
        provenance = [
            mention_to_provenance(mention.model_dump(mode="python"), index=index)
            for index, mention in enumerate(request.mentions)
        ]
        assert len(provenance) == 1
        entry = provenance[0]
        assert entry.raw_text == "CRWD"
        assert entry.candidate_kind == "asset"
        assert entry.source == "user_mention"
        assert entry.resolution_status == "resolved"

    def test_identity_is_not_a_prepared_action(self) -> None:
        """Identity travels; interpretation and confirmation still run."""
        admission = ChatRequestAdmission(
            payload=_selection_request(with_identity=True),
            request=None,  # type: ignore[arg-type]
            user_id="user-1",
            conversation_id="conversation-1",
            language="en",
            request_message_candidate=None,
        )
        assert admission.runtime_action_context() is None
        assert admission.admit_response_option() is None

    def test_selection_turn_keeps_its_mentions(self) -> None:
        """Only replayed response-option turns drop mention provenance."""
        request = _selection_request(with_identity=True)
        assert request.action is not None
        assert not request.action.payload.get("request_message_id")
        assert [mention.symbol for mention in request.mentions] == ["CRWD"]
