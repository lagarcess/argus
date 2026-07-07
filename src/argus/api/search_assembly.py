from __future__ import annotations

from typing import Any, cast

from argus.api import state as api_state
from argus.api.memory_ownership import memory_object_visible
from argus.api.schemas import DecisionState, SearchItem, User
from argus.api.search_utils import score_search_item
from argus.domain.evidence import (
    evidence_preview_from_artifact,
    evidence_preview_from_payload,
)
from argus.domain.search_text import search_text_matches_query

ScoredSearchItem = tuple[int, SearchItem]


def _latest_decision_state_by_idea(
    decisions: list[tuple[Any, Any, Any]],
) -> dict[str, DecisionState]:
    """Map each idea_id to its most-recent decision_state."""
    latest: dict[str, tuple[Any, DecisionState]] = {}
    for idea_id, decision_state, updated_at in decisions:
        if not idea_id or not decision_state:
            continue
        key = str(idea_id)
        state = cast(DecisionState, str(decision_state))
        prior = latest.get(key)
        if prior is None:
            latest[key] = (updated_at, state)
        elif updated_at is not None and (prior[0] is None or updated_at >= prior[0]):
            latest[key] = (updated_at, state)
    return {idea_id: state for idea_id, (_ts, state) in latest.items()}


def scored_supabase_search_items(
    *,
    raw: dict[str, list[dict[str, object]]],
    query: str,
) -> list[ScoredSearchItem]:
    scored_items: list[ScoredSearchItem] = []
    for row in raw.get("conversations", []):
        item = SearchItem(
            type="chat",
            id=str(row["id"]),
            title=str(row["title"]),
            matched_text=str(row.get("last_message_preview") or row["title"]),
            updated_at=row["updated_at"],
        )
        scored_items.append(
            (
                score_search_item(
                    query=query,
                    title=str(row["title"]),
                    matched_text=item.matched_text,
                    pinned=bool(row.get("pinned", False)),
                ),
                item,
            )
        )
    for row in raw.get("strategies", []):
        symbols = row.get("symbols") or []
        matched_text = ", ".join(str(symbol) for symbol in symbols) or str(row["name"])
        symbol_exact_match = any(query == str(symbol).lower() for symbol in symbols)
        item = SearchItem(
            type="strategy",
            id=str(row["id"]),
            title=str(row["name"]),
            matched_text=matched_text,
            updated_at=row["updated_at"],
        )
        scored_items.append(
            (
                score_search_item(
                    query=query,
                    title=str(row["name"]),
                    matched_text=matched_text,
                    pinned=bool(row.get("pinned", False)),
                    symbol_exact_match=symbol_exact_match,
                ),
                item,
            )
        )
    for row in raw.get("collections", []):
        item = SearchItem(
            type="collection",
            id=str(row["id"]),
            title=str(row["name"]),
            matched_text=str(row["name"]),
            updated_at=row["updated_at"],
        )
        scored_items.append(
            (
                score_search_item(
                    query=query,
                    title=str(row["name"]),
                    matched_text=str(row["name"]),
                    pinned=bool(row.get("pinned", False)),
                ),
                item,
            )
        )
    for row in raw.get("runs", []):
        scored_items.append(_scored_supabase_run(row=row, query=query))
    for row in raw.get("ideas", []):
        item = SearchItem(
            type="idea",
            id=str(row["id"]),
            title=str(row["title"]),
            matched_text=str(row.get("summary") or row["title"]),
            updated_at=row["updated_at"],
            conversation_id=row.get("source_conversation_id"),
            lifecycle=row.get("lifecycle"),
            decision_state=cast("DecisionState | None", row.get("decision_state")),
            preview={
                "digest": row.get("summary"),
            },
        )
        scored_items.append(
            (
                score_search_item(
                    query=query,
                    title=str(row["title"]),
                    matched_text=item.matched_text,
                    pinned=False,
                ),
                item,
            )
        )
    for row in raw.get("evidence", []):
        preview = _evidence_preview_from_search_row(row)
        item = SearchItem(
            type="evidence",
            id=str(row["id"]),
            title=str(row["title"]),
            matched_text=str(row.get("digest") or row["title"]),
            updated_at=row["updated_at"],
            conversation_id=row.get("source_conversation_id"),
            lifecycle=row.get("lifecycle"),
            preview=preview,
        )
        scored_items.append(
            (
                score_search_item(
                    query=query,
                    title=str(row["title"]),
                    matched_text=item.matched_text,
                    pinned=False,
                    symbol_exact_match=any(
                        query == str(symbol).lower()
                        for symbol in preview.get("symbols") or []
                    ),
                ),
                item,
            )
        )
    for row in raw.get("decisions", []):
        scored_items.append(_scored_decision_row(row=row, query=query))
    return scored_items


def scored_memory_search_items(*, user: User, query: str) -> list[ScoredSearchItem]:
    scored_items: list[ScoredSearchItem] = []
    for conversation in api_state.store.conversations.values():
        if not memory_object_visible(
            owner_map=api_state.store.conversation_owners,
            object_id=conversation.id,
            user_id=user.id,
        ):
            continue
        if conversation.deleted_at:
            continue
        haystack = f"{conversation.title} {conversation.last_message_preview or ''}"
        if search_text_matches_query(query=query, text=haystack):
            item = SearchItem(
                type="chat",
                id=conversation.id,
                title=conversation.title,
                matched_text=conversation.last_message_preview or conversation.title,
                updated_at=conversation.updated_at,
            )
            scored_items.append(
                (
                    score_search_item(
                        query=query,
                        title=conversation.title,
                        matched_text=item.matched_text,
                        pinned=conversation.pinned,
                    ),
                    item,
                )
            )
    for strategy in api_state.store.strategies.values():
        if not memory_object_visible(
            owner_map=api_state.store.strategy_owners,
            object_id=strategy.id,
            user_id=user.id,
        ):
            continue
        if strategy.deleted_at:
            continue
        haystack = f"{strategy.name} {' '.join(strategy.symbols)} {strategy.template}"
        if search_text_matches_query(query=query, text=haystack):
            matched_text = ", ".join(strategy.symbols) or strategy.name
            item = SearchItem(
                type="strategy",
                id=strategy.id,
                title=strategy.name,
                matched_text=matched_text,
                updated_at=strategy.updated_at,
            )
            scored_items.append(
                (
                    score_search_item(
                        query=query,
                        title=strategy.name,
                        matched_text=matched_text,
                        pinned=strategy.pinned,
                        symbol_exact_match=any(
                            query == symbol.lower() for symbol in strategy.symbols
                        ),
                    ),
                    item,
                )
            )
    for collection in api_state.store.collections.values():
        if not memory_object_visible(
            owner_map=api_state.store.collection_owners,
            object_id=collection.id,
            user_id=user.id,
        ):
            continue
        if collection.deleted_at:
            continue
        if search_text_matches_query(query=query, text=collection.name):
            item = SearchItem(
                type="collection",
                id=collection.id,
                title=collection.name,
                matched_text=collection.name,
                updated_at=collection.updated_at,
            )
            scored_items.append(
                (
                    score_search_item(
                        query=query,
                        title=collection.name,
                        matched_text=collection.name,
                        pinned=collection.pinned,
                    ),
                    item,
                )
            )
    for run in api_state.store.backtest_runs.values():
        if not memory_object_visible(
            owner_map=api_state.store.backtest_run_owners,
            object_id=run.id,
            user_id=user.id,
        ):
            continue
        title = run.conversation_result_card.get("title", "Backtest run")
        haystack = f"{title} {' '.join(run.symbols)} {run.config_snapshot.get('template', '')}"
        if search_text_matches_query(query=query, text=haystack):
            scored_items.append(_scored_memory_run(run=run, query=query))
    decision_state_by_idea = _latest_decision_state_by_idea(
        [
            (decision.idea_id, decision.decision_state, decision.updated_at)
            for decision in api_state.store.decision_notes.values()
            if api_state.store.decision_note_owners.get(decision.id) == user.id
        ]
    )
    for idea in api_state.store.ideas.values():
        if api_state.store.idea_owners.get(idea.id) != user.id:
            continue
        haystack = f"{idea.title} {idea.summary}"
        # Empty-query browse (q="" + decision_state filter) must still surface
        # ideas so the router can narrow them by state, matching the Supabase path.
        if not query or search_text_matches_query(query=query, text=haystack):
            item = SearchItem(
                type="idea",
                id=idea.id,
                title=idea.title,
                matched_text=idea.summary or idea.title,
                updated_at=idea.updated_at,
                conversation_id=idea.source_conversation_id,
                lifecycle=idea.lifecycle,
                decision_state=decision_state_by_idea.get(idea.id),
                preview={
                    "digest": idea.summary,
                },
            )
            scored_items.append(
                (
                    score_search_item(
                        query=query,
                        title=idea.title,
                        matched_text=idea.summary,
                        pinned=False,
                    ),
                    item,
                )
            )
    for artifact in api_state.store.evidence_artifacts.values():
        if api_state.store.evidence_artifact_owners.get(artifact.id) != user.id:
            continue
        haystack = f"{artifact.title} {artifact.digest}"
        if search_text_matches_query(query=query, text=haystack):
            preview = evidence_preview_from_artifact(artifact)
            item = SearchItem(
                type="evidence",
                id=artifact.id,
                title=artifact.title,
                matched_text=artifact.digest,
                updated_at=artifact.updated_at,
                conversation_id=artifact.source_conversation_id,
                lifecycle=artifact.lifecycle,
                preview=preview,
            )
            scored_items.append(
                (
                    score_search_item(
                        query=query,
                        title=artifact.title,
                        matched_text=artifact.digest,
                        pinned=False,
                        symbol_exact_match=any(
                            query == str(symbol).lower()
                            for symbol in preview.get("symbols") or []
                        ),
                    ),
                    item,
                )
            )
    for decision in api_state.store.decision_notes.values():
        if api_state.store.decision_note_owners.get(decision.id) != user.id:
            continue
        artifact = api_state.store.evidence_artifacts.get(decision.evidence_artifact_id)
        if artifact is None:
            continue
        artifact_text = f"{artifact.title} {artifact.digest}"
        note = decision.note or ""
        haystack = f"{decision.decision_state} {note} {artifact_text}"
        if search_text_matches_query(query=query, text=haystack):
            title = artifact.title
            matched_text = _decision_preview_digest(
                note=note,
                artifact_digest=artifact.digest,
            )
            item = SearchItem(
                type="decision",
                id=decision.id,
                title=title,
                matched_text=matched_text,
                updated_at=decision.updated_at,
                conversation_id=decision.source_conversation_id,
                lifecycle="decided",
                preview={
                    "digest": matched_text,
                    "decision_state": decision.decision_state,
                },
            )
            scored_items.append(
                (
                    score_search_item(
                        query=query,
                        title=title,
                        matched_text=haystack,
                        pinned=False,
                    ),
                    item,
                )
            )
    return scored_items


def _scored_supabase_run(*, row: dict[str, object], query: str) -> ScoredSearchItem:
    card = row.get("conversation_result_card")
    if not isinstance(card, dict):
        card = {}
    title = str(card.get("title") or "Backtest run")
    result_type = (
        "backtest"
        if card.get("artifact_type") == "backtest" or card.get("evidence_artifact_id")
        else "run"
    )
    symbols = list(card.get("symbols") or [])
    item = SearchItem(
        type=result_type,
        id=str(row["id"]),
        title=title,
        matched_text=title,
        updated_at=row["created_at"],
        conversation_id=row.get("conversation_id"),
        lifecycle=card.get("evidence_lifecycle"),
        preview={
            "digest": title,
            "symbols": symbols,
            "benchmark_symbol": row.get("benchmark_symbol"),
        }
        if result_type == "backtest"
        else None,
    )
    return (
        score_search_item(
            query=query,
            title=title,
            matched_text=title,
            pinned=False,
            symbol_exact_match=any(query == str(symbol).lower() for symbol in symbols),
        ),
        item,
    )


def _scored_memory_run(*, run, query: str) -> ScoredSearchItem:  # noqa: ANN001
    card = (
        run.conversation_result_card if isinstance(run.conversation_result_card, dict) else {}
    )
    title = str(card.get("title", "Backtest run"))
    result_type = (
        "backtest"
        if card.get("artifact_type") == "backtest" or card.get("evidence_artifact_id")
        else "run"
    )
    item = SearchItem(
        type=result_type,
        id=run.id,
        title=title,
        matched_text=title,
        updated_at=run.created_at,
        conversation_id=run.conversation_id,
        lifecycle=card.get("evidence_lifecycle"),
        preview={
            "digest": title,
            "symbols": list(run.symbols),
            "benchmark_symbol": run.benchmark_symbol,
        }
        if result_type == "backtest"
        else None,
    )
    return (
        score_search_item(
            query=query,
            title=title,
            matched_text=title,
            pinned=False,
            symbol_exact_match=any(query == symbol.lower() for symbol in run.symbols),
        ),
        item,
    )


def _scored_decision_row(*, row: dict[str, object], query: str) -> ScoredSearchItem:
    title = str(row.get("artifact_title") or row.get("artifact_digest") or row["id"])
    search_text = " ".join(
        str(part)
        for part in (
            row.get("decision_state"),
            row.get("note"),
            row.get("artifact_digest"),
        )
        if part
    )
    matched_text = _decision_preview_digest(
        note=row.get("note"),
        artifact_digest=row.get("artifact_digest"),
    )
    item = SearchItem(
        type="decision",
        id=str(row["id"]),
        title=title,
        matched_text=matched_text,
        updated_at=row["updated_at"],
        conversation_id=row.get("source_conversation_id"),
        lifecycle="decided",
        preview={
            "digest": matched_text,
            "decision_state": row.get("decision_state"),
        },
    )
    return (
        score_search_item(
            query=query,
            title=title,
            matched_text=search_text,
            pinned=False,
        ),
        item,
    )


def _evidence_preview_from_search_row(row: dict[str, object]) -> dict[str, object]:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    return evidence_preview_from_payload(
        digest=row.get("digest"),
        title=row.get("title"),
        payload=payload,
    )


def _decision_preview_digest(
    *,
    note: object,
    artifact_digest: object,
) -> str:
    parts = [
        part.strip()
        for part in (note, artifact_digest)
        if isinstance(part, str) and part.strip()
    ]
    return " · ".join(parts)
