"""Project reader previews from message facts, without translating stored prose."""

from collections.abc import Mapping
from typing import Any

from argus.api.chat.previews import is_degraded_clarification_compatibility_text
from argus.api.schemas import ConversationPreview
from argus.domain.artifact_presentation_kind import artifact_presentation_kind

MAX_CONVERSATION_PREVIEWS = 100


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def project_conversation_preview(
    message: Mapping[str, Any] | None,
) -> ConversationPreview:
    if message is None or message.get("role") is None:
        return ConversationPreview(kind="empty")
    if message.get("role") not in {"user", "assistant"}:
        return ConversationPreview(kind="unavailable")
    metadata = _mapping(message.get("metadata"))
    if message.get("role") == "assistant":
        kind = artifact_presentation_kind(metadata)
        if kind is not None:
            facts = _mapping(metadata.get("result_fact_bank")) or _mapping(
                metadata.get("run")
            )
            card = _mapping(
                metadata.get(
                    "confirmation_card" if kind == "confirmation" else "result_card"
                )
            )
            config = _mapping(facts.get("config_snapshot"))
            symbols = facts.get("symbols", card.get("symbols", []))
            if kind == "confirmation":
                payload = _mapping(metadata.get("confirmation_payload"))
                strategy = _mapping(payload.get("strategy"))
                symbols = strategy.get("asset_universe", [])
            template = config.get("template", card.get("strategy_type"))
            return ConversationPreview(
                kind=kind,
                symbols=[symbol[:32] for symbol in symbols if isinstance(symbol, str)][:5]
                if isinstance(symbols, list)
                else [],
                template=template if isinstance(template, str) else None,
            )
    if is_degraded_clarification_compatibility_text(
        role=str(message.get("role")), metadata=dict(metadata)
    ):
        return ConversationPreview(kind="unavailable")
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return ConversationPreview(kind="text", text=content.strip()[:500])
    return ConversationPreview(kind="empty")
