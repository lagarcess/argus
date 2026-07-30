from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Mapping

from argus.api import state as api_state
from argus.api.chat.legacy_onboarding_markers import is_legacy_onboarding_marker
from argus.api.memory_ownership import memory_object_visible
from argus.api.schemas import SearchAssetRollup, SearchItem, User
from argus.domain.conversation_recall import (
    project_asset_rollup,
    project_conversation_recall,
)

ScoredSearchItem = tuple[int, SearchItem]


@dataclass(frozen=True)
class MemorySearchRead:
    scored_items: list[ScoredSearchItem]
    asset_rollup: SearchAssetRollup | None


def memory_search_read(*, user: User, query: str) -> MemorySearchRead:
    """Project owned memory records through the same conversation read model."""
    with api_state.store.backtest_finalization_lock:
        conversations = [
            conversation.model_dump()
            for conversation in api_state.store.conversations.values()
            if memory_object_visible(
                owner_map=api_state.store.conversation_owners,
                object_id=conversation.id,
                user_id=user.id,
            )
            and conversation.deleted_at is None
        ]
        runs = [
            run.model_dump()
            for run in api_state.store.backtest_runs.values()
            if memory_object_visible(
                owner_map=api_state.store.backtest_run_owners,
                object_id=run.id,
                user_id=user.id,
            )
        ]
        ideas = [
            idea.model_dump()
            for idea in api_state.store.ideas.values()
            if memory_object_visible(
                owner_map=api_state.store.idea_owners,
                object_id=idea.id,
                user_id=user.id,
            )
        ]
        evidence = [
            artifact.model_dump()
            for artifact in api_state.store.evidence_artifacts.values()
            if memory_object_visible(
                owner_map=api_state.store.evidence_artifact_owners,
                object_id=artifact.id,
                user_id=user.id,
            )
        ]
        decisions = [
            decision.model_dump()
            for decision in api_state.store.decision_notes.values()
            if memory_object_visible(
                owner_map=api_state.store.decision_note_owners,
                object_id=decision.id,
                user_id=user.id,
            )
        ]
        visible_conversation_ids = {
            str(conversation["id"]) for conversation in conversations
        }
        runs = [
            run
            for run in runs
            if str(run.get("conversation_id") or "") in visible_conversation_ids
        ]
        evidence = [
            artifact
            for artifact in evidence
            if str(artifact.get("source_conversation_id") or "")
            in visible_conversation_ids
        ]
        decisions = [
            decision
            for decision in decisions
            if str(decision.get("source_conversation_id") or "")
            in visible_conversation_ids
        ]
        messages = [
            message.model_dump()
            for conversation_id, conversation_messages in api_state.store.messages.items()
            if conversation_id in visible_conversation_ids
            for message in conversation_messages
            if message.role != "user"
            or not is_legacy_onboarding_marker(message.content)
        ]
    return MemorySearchRead(
        scored_items=_project_rows(
            conversations=conversations,
            runs=runs,
            ideas=ideas,
            evidence=evidence,
            decisions=decisions,
            messages=messages,
            query=query,
        ),
        asset_rollup=project_asset_rollup(
            runs=runs,
            evidence=evidence,
            decisions=decisions,
            query=query,
        ),
    )


def scored_memory_search_items(*, user: User, query: str) -> list[ScoredSearchItem]:
    return memory_search_read(user=user, query=query).scored_items


def scored_supabase_search_items(
    *,
    raw: dict[str, list[dict[str, object]]],
    query: str,
) -> list[ScoredSearchItem]:
    """Adapt persistent and injected-gateway rows to the shared projector."""
    if "conversation_recall" in raw:
        rows = raw["conversation_recall"]
        return [
            (int(row.get("score") or 0), SearchItem.model_validate(row["item"]))
            for row in rows
            if isinstance(row.get("item"), dict)
        ]

    conversations: dict[str, dict[str, Any]] = {
        str(row["id"]): dict(row)
        for row in raw.get("conversations", [])
        if row.get("id") is not None and row.get("deleted_at") is None
    }
    runs = [dict(row) for row in raw.get("runs", [])]
    ideas = [dict(row) for row in raw.get("ideas", [])]
    evidence = [dict(row) for row in raw.get("evidence", [])]
    decisions = [dict(row) for row in raw.get("decisions", [])]
    messages = [dict(row) for row in raw.get("messages", [])]

    # Compatibility for narrow injected gateways: production readers include
    # canonical conversations, while test doubles may return only a matched
    # child record.
    for row in (*runs, *ideas, *evidence, *decisions):
        conversation_id = _conversation_id(row)
        if conversation_id is None or conversation_id in conversations:
            continue
        conversations[conversation_id] = {
            "id": conversation_id,
            "title": row.get("title")
            or row.get("artifact_title")
            or row.get("artifact_digest")
            or "Untitled conversation",
            "last_message_preview": None,
            "pinned": False,
            "updated_at": row.get("updated_at") or row.get("created_at"),
        }

    # The old bounded reader hydrates a decision's evidence inline.
    for decision in decisions:
        artifact_id = decision.get("evidence_artifact_id")
        if artifact_id is None or any(
            str(row.get("id")) == str(artifact_id) for row in evidence
        ):
            continue
        evidence.append(
            {
                "id": artifact_id,
                "source_conversation_id": decision.get("source_conversation_id"),
                "source_run_id": decision.get("source_run_id"),
                "title": decision.get("artifact_title"),
                "digest": decision.get("artifact_digest"),
                "payload": decision.get("artifact_payload"),
                "created_at": decision.get("created_at"),
                "updated_at": decision.get("updated_at"),
            }
        )

    return _project_rows(
        conversations=list(conversations.values()),
        runs=runs,
        ideas=ideas,
        evidence=evidence,
        decisions=decisions,
        messages=messages,
        query=query,
    )


def _project_rows(
    *,
    conversations: list[Mapping[str, Any]],
    runs: list[Mapping[str, Any]],
    ideas: list[Mapping[str, Any]],
    evidence: list[Mapping[str, Any]],
    decisions: list[Mapping[str, Any]],
    messages: list[Mapping[str, Any]],
    query: str,
) -> list[ScoredSearchItem]:
    runs_by_conversation = _group_by_conversation(runs)
    ideas_by_conversation = _group_by_conversation(ideas)
    evidence_by_conversation = _group_by_conversation(evidence)
    decisions_by_conversation = _group_by_conversation(decisions)
    messages_by_conversation = _group_by_conversation(messages)
    projected: list[ScoredSearchItem] = []
    for conversation in conversations:
        conversation_id = str(conversation.get("id") or "")
        item = project_conversation_recall(
            conversation=conversation,
            runs=runs_by_conversation[conversation_id],
            ideas=ideas_by_conversation[conversation_id],
            evidence=evidence_by_conversation[conversation_id],
            decisions=decisions_by_conversation[conversation_id],
            messages=messages_by_conversation[conversation_id],
            query=query,
        )
        if item is not None:
            projected.append(item)
    return projected


def _group_by_conversation(
    rows: list[Mapping[str, Any]],
) -> defaultdict[str, list[Mapping[str, Any]]]:
    grouped: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        conversation_id = _conversation_id(row)
        if conversation_id is not None:
            grouped[conversation_id].append(row)
    return grouped


def _conversation_id(row: Mapping[str, Any]) -> str | None:
    value = row.get("conversation_id") or row.get("source_conversation_id")
    return str(value) if value is not None else None
