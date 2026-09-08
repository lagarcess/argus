"""Researched peer assets riding the Try-next row surface below a card turn.

The persisted research sidecar is the only source; runtime state never
carries peers, so every completion path agrees by reading the transcript.
"""

from __future__ import annotations

from typing import Any


def attach_research_peer_rows(
    runtime_result: dict[str, Any],
    metadata: dict[str, Any],
    *,
    user_id: str,
    conversation_id: str,
    language: str,
) -> None:
    """Attach remaining researched peers as Try-next rows on a card turn.

    Peers come from the persisted research sidecar, not runtime state: inline
    turns, the dev synchronous fallback, and the background job finalizer all
    persist the same sidecar, so the transcript is the one contract every
    completion path already honors."""
    if not isinstance(runtime_result.get("confirmation_payload"), dict):
        return
    from argus.domain.research.config import research_rail_enabled

    if not research_rail_enabled():
        return
    strategy = runtime_result["confirmation_payload"].get("strategy")
    if not isinstance(strategy, dict):
        return
    peers = research_peers_from_transcript(
        user_id=user_id,
        conversation_id=conversation_id,
        basket_symbols=[
            str(symbol).strip().upper()
            for symbol in strategy.get("asset_universe") or []
            if str(symbol).strip()
        ],
    )
    rows = research_peer_add_rows_for_confirmation(
        peers,
        confirmation_payload=runtime_result["confirmation_payload"],
        language=language,
    )
    if rows is not None:
        metadata["next_experiments"] = rows
        runtime_result["next_experiments"] = rows


def research_peers_from_transcript(
    *,
    user_id: str,
    conversation_id: str,
    basket_symbols: list[str],
    limit: int = 20,
) -> list[dict[str, Any]]:
    """The most recent research about these assets decides the peers.

    Newest-first over the persisted transcript, the first research sidecar
    whose anchors or peers overlap the basket wins; unrelated research in
    between neither offers its peers here nor hides the relevant ones. An
    empty peer list on the winning sidecar is honest truth, not a miss."""
    basket = {symbol for symbol in basket_symbols if symbol}
    if not basket:
        return []
    from argus.api.chat.recovery import _recent_messages_for_conversation

    try:
        messages = _recent_messages_for_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
            limit=limit,
        )
    except Exception:  # noqa: BLE001
        messages = []
    for message in reversed(messages):
        if message.role != "assistant" or not isinstance(message.metadata, dict):
            continue
        sidecar = message.metadata.get("research")
        if not isinstance(sidecar, dict):
            continue
        peers = [p for p in sidecar.get("peers") or [] if isinstance(p, dict)]
        anchors = {
            str(symbol).strip().upper()
            for symbol in sidecar.get("anchor_symbols") or []
            if str(symbol).strip()
        }
        peer_symbols = {str(p.get("symbol") or "").strip().upper() for p in peers} - {""}
        if basket & (anchors | peer_symbols):
            return peers
    return []


def research_peer_add_rows_for_confirmation(
    peers: list[dict[str, Any]],
    *,
    confirmation_payload: dict[str, Any],
    language: str,
) -> dict[str, Any] | None:
    """Researched peers still outside the basket ride the ordinary Try-next
    surface below the card's turn; composition lives with the materializer."""
    from argus.domain.research.config import research_rail_enabled

    if not research_rail_enabled():
        return None
    if not peers:
        return None
    strategy = confirmation_payload.get("strategy")
    if not isinstance(strategy, dict):
        return None
    from argus.agent_runtime.research_basket import peer_add_rows

    return peer_add_rows(
        peers,
        basket_symbols=[
            str(symbol).strip().upper()
            for symbol in strategy.get("asset_universe") or []
            if str(symbol).strip()
        ],
        basket_asset_class=str(strategy.get("asset_class") or "equity"),
        language=language,
    )
