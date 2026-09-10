"""Project an ordered set of declared answers into one selected public turn."""

from __future__ import annotations

from urllib.parse import urlsplit

from argus.api.public_excerpt_schemas import (
    PublicExcerptResearchSource,
    PublicExcerptToolCard,
    PublicExcerptToolTurn,
)
from argus.domain.capability_registry import get_tool_catalog
from argus.domain.public_excerpt_turns import audit_cited_answer, audit_text, refuse
from argus.domain.public_excerpts import (
    PublicExcerptSanitizationError,
    audit_public_excerpt_document,
    build_tool_public_excerpt_payload,
)
from argus.domain.tool_contracts import MAX_TOOL_CALLS, ToolResultCard


def project_tool_turn(
    *,
    cards: list[ToolResultCard],
    question: str,
    owner_note: str | None,
    language: str,
    private_ids: tuple[str, ...],
) -> PublicExcerptToolTurn:
    """All siblings must be complete and safe; a selection never drops a call."""
    if not 1 <= len(cards) <= MAX_TOOL_CALLS:
        refuse("unsupported_turn")
    question = audit_text(question, field="question", private_ids=private_ids)
    note = audit_text(owner_note, field="owner_note", private_ids=private_ids)
    assert question is not None
    catalog = get_tool_catalog(include_unavailable=True)
    projected = []
    for card in cards:
        declaration = catalog.get(card.tool_name)
        if declaration is None or (
            declaration.card.card_type,
            declaration.card.version,
        ) != (card.card_type, card.card_version):
            refuse("unsupported_turn")
        policy = declaration.policy.public_receipt
        if policy == "disabled":
            refuse("unsupported_shape")
        if card.outcome.status != "succeeded" or card.presentation.answer is None:
            refuse("not_completed")
        if policy == "cited_facts":
            if not card.presentation.sources:
                refuse("missing_sources", "sources")
            sources = [
                PublicExcerptResearchSource(
                    **source.model_dump(mode="json"),
                    domain=urlsplit(source.url).netloc,
                )
                for source in card.presentation.sources
            ]
            audit_cited_answer(
                answer=card.presentation.narrative,
                sources=sources,
                private_ids=private_ids,
            )
        try:
            safe = build_tool_public_excerpt_payload(
                card=card,
                owner_note=None,
                content_language=language,
                private_ids=private_ids,
            )
        except PublicExcerptSanitizationError:
            refuse("unsafe_text", "answer")
        projected.append(
            PublicExcerptToolCard(
                card_type=safe.card_type,
                card_version=safe.card_version,
                presentation=safe.presentation,
            )
        )
    turn = PublicExcerptToolTurn(
        question=question,
        cards=projected,
        owner_note=note,
        content_language=language,
    )
    try:
        audit_public_excerpt_document(
            turn.model_dump(mode="json"),
            private_ids=tuple(
                (
                    *private_ids,
                    *(card.call_id for card in cards),
                    *(card.artifact_id for card in cards),
                )
            ),
        )
    except PublicExcerptSanitizationError:
        refuse("unsafe_text", "answer")
    return turn
