from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Iterable, Mapping

from argus.api.chat.legacy_onboarding_markers import is_legacy_onboarding_marker
from argus.api.memory_ownership import memory_object_visible
from argus.api.schemas import User
from argus.api.search_utils import score_search_item, search_rank_key
from argus.domain.conversation_recall import (
    conversation_has_untaken_suggestion,
    valid_next_experiments_metadata,
)
from argus.domain.search_text import (
    normalize_search_symbol,
    normalize_search_text,
    search_text_matches_query,
)
from argus.domain.store import AlphaStore

_MEMORY_MATCH_OVERSAMPLE = 10
_MEMORY_MATCH_LIMIT_MAX = 1_010
_SOURCE_LAYERS = (
    "conversation",
    "message",
    "run",
    "idea",
    "evidence",
    "decision",
)


@dataclass(frozen=True)
class MemorySearchSnapshot:
    conversations: list[dict[str, Any]]
    runs: list[dict[str, Any]]
    ideas: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    decisions: list[dict[str, Any]]
    messages: list[dict[str, Any]]
    asset_runs: list[dict[str, Any]]
    asset_evidence: list[dict[str, Any]]
    asset_decisions: list[dict[str, Any]]
    ledger_counts: dict[str, int] | None


@dataclass(frozen=True)
class _Candidate:
    conversation_id: str
    source_id: str
    activity: datetime
    text: str


@dataclass(frozen=True)
class _ConversationQueryMatch:
    conversation_id: str
    candidate: _Candidate
    layer: str
    layer_rank: int
    score: int
    symbol_exact_match: bool
    match_count: int = 1


@dataclass(frozen=True)
class _MemorySearchIndex:
    revision: int
    conversations: dict[str, dict[str, Any]]
    recent_conversation_ids: tuple[str, ...]
    runs_by_conversation: dict[str, list[dict[str, Any]]]
    ideas_by_conversation: dict[str, list[dict[str, Any]]]
    evidence_by_conversation: dict[str, list[dict[str, Any]]]
    decisions_by_conversation: dict[str, list[dict[str, Any]]]
    messages_by_id: dict[str, dict[str, Any]]
    candidates_by_layer: dict[str, tuple[_Candidate, ...]]
    postings_by_layer: dict[str, dict[str, frozenset[int]]]
    run_by_id: dict[str, dict[str, Any]]
    evidence_by_run: dict[str, list[dict[str, Any]]]
    decisions_by_evidence: dict[str, list[dict[str, Any]]]
    asset_symbols: tuple[str, ...]
    asset_run_ids: dict[str, frozenset[str]]
    decision_states_by_conversation: dict[str, frozenset[str]]
    conversation_activity_by_id: dict[str, datetime]
    conversation_symbols_by_id: dict[str, frozenset[str]]


_INDEX_CACHE: dict[tuple[int, str], _MemorySearchIndex] = {}
_INDEX_CACHE_LOCK = RLock()


def bounded_memory_search_snapshot(
    *,
    store: AlphaStore,
    user: User,
    query: str,
    source_limit: int,
    include_conversation_rows: bool,
    cursor_updated_at: datetime | None = None,
    cursor_id: str | None = None,
    decision_state: str | None = None,
    include_ledger_groups: bool = False,
    guest_conversation_id: str | None = None,
    conversation_ids: Iterable[str] | None = None,
) -> MemorySearchSnapshot:
    """Read a bounded query page from a revision-keyed, non-durable index."""
    if source_limit < 1:
        raise ValueError("Memory search source limit must be positive.")
    requested_conversation_ids = tuple(
        dict.fromkeys(str(value) for value in (conversation_ids or ()))
    )
    if len(requested_conversation_ids) > 50:
        raise ValueError("Visible conversation recall accepts at most 50 ids.")
    if len(requested_conversation_ids) > source_limit:
        raise ValueError("Visible conversation recall exceeds its source limit.")
    candidate_limit = min(
        max(source_limit * _MEMORY_MATCH_OVERSAMPLE, _MEMORY_MATCH_OVERSAMPLE),
        _MEMORY_MATCH_LIMIT_MAX,
    )
    index = _memory_search_index(store=store, user=user)
    eligible_conversation_ids = set(index.conversations)
    if guest_conversation_id is not None:
        eligible_conversation_ids.intersection_update({guest_conversation_id})
    if decision_state is not None:
        eligible_conversation_ids = {
            conversation_id
            for conversation_id in eligible_conversation_ids
            if decision_state
            in index.decision_states_by_conversation.get(
                conversation_id,
                frozenset(),
            )
        }

    selected_conversation_ids: set[str] = set()
    selected_message_ids: set[str] = set()
    selected_query_matches: dict[str, _ConversationQueryMatch] = {}
    if requested_conversation_ids:
        selected_conversation_ids.update(
            conversation_id
            for conversation_id in requested_conversation_ids
            if conversation_id in eligible_conversation_ids
        )
    elif include_conversation_rows:
        if query:
            selected_query_matches = _query_conversation_window(
                index,
                query=query,
                candidate_limit=candidate_limit,
                eligible_conversation_ids=eligible_conversation_ids,
                cursor_updated_at=cursor_updated_at,
                cursor_id=cursor_id,
            )
            selected_conversation_ids.update(selected_query_matches)
            selected_message_ids.update(
                match.candidate.source_id
                for match in selected_query_matches.values()
                if match.layer == "message"
            )
        else:
            selected_conversation_ids.update(
                _recent_conversation_window(
                    index,
                    candidate_limit=candidate_limit,
                    eligible_conversation_ids=eligible_conversation_ids,
                    cursor_updated_at=cursor_updated_at,
                    cursor_id=cursor_id,
                )
            )

    resolved_symbol = _resolve_asset_symbol(index, query=query)
    asset_run_ids = (
        index.asset_run_ids.get(resolved_symbol, frozenset())
        if resolved_symbol is not None
        else frozenset()
    )
    asset_evidence = [
        artifact
        for run_id in asset_run_ids
        for artifact in index.evidence_by_run.get(run_id, [])
    ]
    asset_evidence_ids = {str(artifact["id"]) for artifact in asset_evidence}
    ledger_counts = (
        _ledger_counts(
            index,
            query=query,
            eligible_conversation_ids=(
                {guest_conversation_id}
                if guest_conversation_id is not None
                else set(index.conversations)
            ),
        )
        if include_ledger_groups
        else None
    )

    return MemorySearchSnapshot(
        conversations=[
            _conversation_with_query_match(
                index.conversations[conversation_id],
                selected_query_matches.get(conversation_id),
            )
            for conversation_id in selected_conversation_ids
            if conversation_id in index.conversations
        ],
        runs=[
            row
            for conversation_id in selected_conversation_ids
            for row in index.runs_by_conversation.get(conversation_id, [])
        ],
        ideas=[
            row
            for conversation_id in selected_conversation_ids
            for row in index.ideas_by_conversation.get(conversation_id, [])
        ],
        evidence=[
            row
            for conversation_id in selected_conversation_ids
            for row in index.evidence_by_conversation.get(conversation_id, [])
        ],
        decisions=[
            row
            for conversation_id in selected_conversation_ids
            for row in index.decisions_by_conversation.get(conversation_id, [])
        ],
        messages=[
            index.messages_by_id[message_id]
            for message_id in selected_message_ids
            if message_id in index.messages_by_id
        ],
        asset_runs=sorted(
            (
                index.run_by_id[run_id]
                for run_id in asset_run_ids
                if run_id in index.run_by_id
            ),
            key=_mapping_activity,
            reverse=True,
        ),
        asset_evidence=asset_evidence,
        asset_decisions=[
            decision
            for evidence_id in asset_evidence_ids
            for decision in index.decisions_by_evidence.get(evidence_id, [])
        ],
        ledger_counts=ledger_counts,
    )


def _memory_search_index(*, store: AlphaStore, user: User) -> _MemorySearchIndex:
    cache_key = (id(store), user.id)
    with _INDEX_CACHE_LOCK:
        cached = _INDEX_CACHE.get(cache_key)
        if cached is not None and cached.revision == store.search_revision:
            return cached
        built = _build_memory_search_index(store=store, user=user)
        _INDEX_CACHE[cache_key] = built
        return built


def _build_memory_search_index(
    *,
    store: AlphaStore,
    user: User,
) -> _MemorySearchIndex:
    """Rebuild only when canonical memory changes, never for each keystroke."""
    revision = store.search_revision
    with store.conversation_message_lock:
        conversation_refs = [
            conversation
            for conversation in store.conversations.values()
            if memory_object_visible(
                owner_map=store.conversation_owners,
                object_id=conversation.id,
                user_id=user.id,
            )
            and conversation.deleted_at is None
        ]
        visible_conversation_ids = {
            str(conversation.id) for conversation in conversation_refs
        }
        message_refs = [
            message
            for conversation_id, conversation_messages in store.messages.items()
            if conversation_id in visible_conversation_ids
            for message in conversation_messages
            if (
                message.role == "user"
                or (
                    message.role == "assistant"
                    and valid_next_experiments_metadata(
                        getattr(message, "metadata", None)
                    )
                )
            )
            and not is_legacy_onboarding_marker(message.content)
        ]
    with store.backtest_finalization_lock:
        run_refs = [
            run
            for run in store.backtest_runs.values()
            if memory_object_visible(
                owner_map=store.backtest_run_owners,
                object_id=run.id,
                user_id=user.id,
            )
            and str(run.conversation_id or "") in visible_conversation_ids
        ]
        idea_refs = [
            idea
            for idea in store.ideas.values()
            if memory_object_visible(
                owner_map=store.idea_owners,
                object_id=idea.id,
                user_id=user.id,
            )
            and str(idea.source_conversation_id or "")
            in visible_conversation_ids
        ]
        evidence_refs = [
            artifact
            for artifact in store.evidence_artifacts.values()
            if memory_object_visible(
                owner_map=store.evidence_artifact_owners,
                object_id=artifact.id,
                user_id=user.id,
            )
            and str(artifact.source_conversation_id or "")
            in visible_conversation_ids
        ]
        decision_refs = [
            decision
            for decision in store.decision_notes.values()
            if memory_object_visible(
                owner_map=store.decision_note_owners,
                object_id=decision.id,
                user_id=user.id,
            )
            and str(decision.source_conversation_id or "")
            in visible_conversation_ids
        ]

    conversations = [row.model_dump() for row in conversation_refs]
    messages = [row.model_dump() for row in message_refs]
    runs = [row.model_dump() for row in run_refs]
    ideas = [row.model_dump() for row in idea_refs]
    evidence = [row.model_dump() for row in evidence_refs]
    decisions = [row.model_dump() for row in decision_refs]
    evidence_by_id = {str(row["id"]): row for row in evidence}
    runs_by_conversation = _group_rows(runs, field="conversation_id")
    ideas_by_conversation = _group_rows(ideas, field="source_conversation_id")
    evidence_by_conversation = _group_rows(
        evidence,
        field="source_conversation_id",
    )
    decisions_by_conversation = _group_rows(
        decisions,
        field="source_conversation_id",
    )
    messages_by_conversation = _group_rows(messages, field="conversation_id")
    for conversation in conversations:
        conversation_id = str(conversation["id"])
        latest_run = max(
            (
                run
                for run in runs_by_conversation.get(conversation_id, [])
                if run.get("status") == "completed"
            ),
            key=_mapping_activity,
            default=None,
        )
        conversation["_recall_summary"] = {
            "latest_suggestion_untaken": conversation_has_untaken_suggestion(
                run=latest_run,
                messages=messages_by_conversation.get(conversation_id, []),
            )
        }

    candidates: dict[str, list[_Candidate]] = {
        layer: [] for layer in _SOURCE_LAYERS
    }
    for conversation in conversations:
        conversation_id = str(conversation["id"])
        for suffix, text in (
            ("title", conversation.get("title")),
            ("preview", conversation.get("last_message_preview")),
        ):
            if text:
                candidates["conversation"].append(
                    _candidate(
                        conversation_id=conversation_id,
                        source_id=f"{conversation_id}:{suffix}",
                        row=conversation,
                        text=str(text),
                    )
                )
    for message in messages:
        if message.get("role") != "user":
            continue
        candidates["message"].append(
            _candidate(
                conversation_id=str(message["conversation_id"]),
                source_id=str(message["id"]),
                row=message,
                text=str(message["content"]),
            )
        )
    for run in runs:
        if run.get("status") == "completed":
            candidates["run"].append(
                _candidate(
                    conversation_id=str(run["conversation_id"]),
                    source_id=str(run["id"]),
                    row=run,
                    text=_run_search_text(run),
                )
            )
    for idea in ideas:
        candidates["idea"].append(
            _candidate(
                conversation_id=str(idea["source_conversation_id"]),
                source_id=str(idea["id"]),
                row=idea,
                text=f"{idea.get('title') or ''} {idea.get('summary') or ''}",
            )
        )
    for artifact in evidence:
        candidates["evidence"].append(
            _candidate(
                conversation_id=str(artifact["source_conversation_id"]),
                source_id=str(artifact["id"]),
                row=artifact,
                text=f"{artifact.get('title') or ''} {artifact.get('digest') or ''}",
            )
        )
    for decision in decisions:
        artifact = evidence_by_id.get(str(decision.get("evidence_artifact_id") or ""))
        candidates["decision"].append(
            _candidate(
                conversation_id=str(decision["source_conversation_id"]),
                source_id=str(decision["id"]),
                row=decision,
                text=_decision_search_text(decision, evidence=artifact),
            )
        )

    sorted_candidates = {
        layer: tuple(
            sorted(
                rows,
                key=lambda row: (row.activity, row.source_id),
                reverse=True,
            )
        )
        for layer, rows in candidates.items()
    }
    postings = {
        layer: _candidate_postings(rows)
        for layer, rows in sorted_candidates.items()
    }
    run_by_id = {str(row["id"]): row for row in runs}
    evidence_by_run = _group_rows(evidence, field="source_run_id")
    decisions_by_evidence = _group_rows(decisions, field="evidence_artifact_id")
    asset_display_symbol: dict[str, str] = {}
    asset_run_ids: defaultdict[str, set[str]] = defaultdict(set)
    for run in sorted(runs, key=_mapping_activity, reverse=True):
        if run.get("status") != "completed":
            continue
        for symbol in run.get("symbols") or []:
            normalized = normalize_search_symbol(symbol)
            if normalized is None:
                continue
            asset_display_symbol.setdefault(normalized, str(symbol))
            asset_run_ids[normalized].add(str(run["id"]))
    decision_states_by_conversation: defaultdict[str, set[str]] = defaultdict(set)
    for decision in decisions:
        conversation_id = decision.get("source_conversation_id")
        decision_state = decision.get("decision_state")
        if conversation_id is not None and decision_state is not None:
            decision_states_by_conversation[str(conversation_id)].add(
                str(decision_state)
            )
    conversation_activity_by_id = {
        conversation_id: max(
            _mapping_activity(row)
            for row in (
                conversation,
                *runs_by_conversation.get(conversation_id, []),
                *ideas_by_conversation.get(conversation_id, []),
                *evidence_by_conversation.get(conversation_id, []),
                *decisions_by_conversation.get(conversation_id, []),
            )
        )
        for conversation_id, conversation in (
            (str(row["id"]), row) for row in conversations
        )
    }
    conversation_symbols_by_id = {
        conversation_id: frozenset(
            symbol.lower()
            for run in runs_by_conversation.get(conversation_id, [])
            if run.get("status", "completed") == "completed"
            for symbol in _run_symbols(run)
        )
        for conversation_id in conversation_activity_by_id
    }

    return _MemorySearchIndex(
        revision=revision,
        conversations={str(row["id"]): row for row in conversations},
        recent_conversation_ids=tuple(
            str(row["id"])
            for row in sorted(
                conversations,
                key=lambda row: _recent_conversation_seek_key(
                    conversation_id=str(row["id"]),
                    conversation=row,
                    activity=conversation_activity_by_id[str(row["id"])],
                ),
                reverse=True,
            )
        ),
        runs_by_conversation=runs_by_conversation,
        ideas_by_conversation=ideas_by_conversation,
        evidence_by_conversation=evidence_by_conversation,
        decisions_by_conversation=decisions_by_conversation,
        messages_by_id={str(row["id"]): row for row in messages},
        candidates_by_layer=sorted_candidates,
        postings_by_layer=postings,
        run_by_id=run_by_id,
        evidence_by_run=evidence_by_run,
        decisions_by_evidence=decisions_by_evidence,
        asset_symbols=tuple(sorted(asset_display_symbol)),
        asset_run_ids={
            symbol: frozenset(run_ids)
            for symbol, run_ids in asset_run_ids.items()
        },
        decision_states_by_conversation={
            conversation_id: frozenset(states)
            for conversation_id, states in decision_states_by_conversation.items()
        },
        conversation_activity_by_id=conversation_activity_by_id,
        conversation_symbols_by_id=conversation_symbols_by_id,
    )


def _matching_candidate_indexes(
    index: _MemorySearchIndex,
    *,
    layer: str,
    query: str,
) -> frozenset[int] | set[int]:
    normalized_tokens = normalize_search_text(query).split()
    trigrams = {
        trigram
        for token in normalized_tokens
        if len(token) >= 3
        for trigram in _trigrams(token)
    }
    if not trigrams:
        return frozenset()
    postings = index.postings_by_layer[layer]
    candidate_indexes: frozenset[int] | set[int] | None = None
    for trigram in trigrams:
        matches = postings.get(trigram, frozenset())
        candidate_indexes = (
            matches
            if candidate_indexes is None
            else candidate_indexes.intersection(matches)
        )
        if not candidate_indexes:
            return frozenset()
    assert candidate_indexes is not None
    return candidate_indexes


def _query_conversation_window(
    index: _MemorySearchIndex,
    *,
    query: str,
    candidate_limit: int,
    eligible_conversation_ids: set[str],
    cursor_updated_at: datetime | None,
    cursor_id: str | None,
) -> dict[str, _ConversationQueryMatch]:
    matches = _conversation_query_matches(
        index,
        query=query,
        eligible_conversation_ids=eligible_conversation_ids,
    )
    ordered = sorted(
        matches.values(),
        key=lambda match: _conversation_query_rank_key(index, match),
        reverse=True,
    )
    selected = ordered[:candidate_limit]
    if cursor_updated_at is not None and cursor_id is not None:
        cursor_match = matches.get(cursor_id)
        if (
            cursor_match is not None
            and index.conversation_activity_by_id[cursor_id] == cursor_updated_at
        ):
            cursor_key = _conversation_query_rank_key(index, cursor_match)
            cursor_window = [
                match
                for match in ordered
                if _conversation_query_rank_key(index, match) <= cursor_key
            ][:candidate_limit]
            selected.extend(cursor_window)
    return {match.conversation_id: match for match in selected}


def _conversation_query_matches(
    index: _MemorySearchIndex,
    *,
    query: str,
    eligible_conversation_ids: set[str],
) -> dict[str, _ConversationQueryMatch]:
    matches: dict[str, _ConversationQueryMatch] = {}
    layer_match_counts: defaultdict[tuple[str, str], int] = defaultdict(int)
    for layer_rank, layer in enumerate(_SOURCE_LAYERS, start=1):
        rows = index.candidates_by_layer[layer]
        for candidate_index in _matching_candidate_indexes(
            index,
            layer=layer,
            query=query,
        ):
            candidate = rows[candidate_index]
            conversation_id = candidate.conversation_id
            if (
                conversation_id not in eligible_conversation_ids
                or not search_text_matches_query(query=query, text=candidate.text)
            ):
                continue
            layer_match_counts[(conversation_id, layer)] += 1
            conversation = index.conversations[conversation_id]
            symbol_exact_match = (
                query in index.conversation_symbols_by_id[conversation_id]
            )
            proposed = _ConversationQueryMatch(
                conversation_id=conversation_id,
                candidate=candidate,
                layer=layer,
                layer_rank=layer_rank,
                score=score_search_item(
                    query=query,
                    title=str(
                        conversation.get("title") or "Untitled conversation"
                    ),
                    matched_text=candidate.text,
                    pinned=bool(conversation.get("pinned")),
                    symbol_exact_match=symbol_exact_match,
                    match_layer_rank=layer_rank,
                ),
                symbol_exact_match=symbol_exact_match,
            )
            current = matches.get(conversation_id)
            if current is None or _winning_match_key(proposed) > _winning_match_key(
                current
            ):
                matches[conversation_id] = proposed
    return {
        conversation_id: replace(
            match,
            match_count=layer_match_counts[(conversation_id, match.layer)],
        )
        for conversation_id, match in matches.items()
    }


def _winning_match_key(
    match: _ConversationQueryMatch,
) -> tuple[int, int, datetime, str]:
    return (
        match.score,
        match.layer_rank,
        match.candidate.activity,
        match.candidate.text,
    )


def _conversation_query_rank_key(
    index: _MemorySearchIndex,
    match: _ConversationQueryMatch,
) -> tuple[int, int, int, int, datetime, int, int, str]:
    return search_rank_key(
        score=match.score,
        kind="conversation",
        updated_at=index.conversation_activity_by_id[match.conversation_id],
        item_id=match.conversation_id,
    )


def _conversation_with_query_match(
    conversation: dict[str, Any],
    match: _ConversationQueryMatch | None,
) -> dict[str, Any]:
    if match is None:
        return conversation
    projected = dict(conversation)
    projected["_recall_match"] = {
        "matched_text": match.candidate.text,
        "layer": match.layer,
        "layer_rank": match.layer_rank,
        "activity_at": match.candidate.activity,
        "symbol_exact_match": match.symbol_exact_match,
        "message_id": (
            match.candidate.source_id if match.layer == "message" else None
        ),
        "match_count": match.match_count,
    }
    return projected


def _recent_conversation_window(
    index: _MemorySearchIndex,
    *,
    candidate_limit: int,
    eligible_conversation_ids: set[str],
    cursor_updated_at: datetime | None,
    cursor_id: str | None,
) -> list[str]:
    eligible = [
        conversation_id
        for conversation_id in index.recent_conversation_ids
        if conversation_id in eligible_conversation_ids
    ]
    if cursor_updated_at is None or cursor_id is None:
        return eligible[:candidate_limit]
    cursor_conversation = index.conversations.get(cursor_id)
    cursor_activity = index.conversation_activity_by_id.get(cursor_id)
    if (
        cursor_conversation is None
        or cursor_activity is None
        or cursor_activity != cursor_updated_at
    ):
        return eligible[:candidate_limit]
    cursor_key = _recent_conversation_seek_key(
        conversation_id=cursor_id,
        conversation=cursor_conversation,
        activity=cursor_activity,
    )
    cursor_window = [
        conversation_id
        for conversation_id in eligible
        if _recent_conversation_seek_key(
            conversation_id=conversation_id,
            conversation=index.conversations[conversation_id],
            activity=index.conversation_activity_by_id[conversation_id],
        )
        <= cursor_key
    ][:candidate_limit]
    return list(dict.fromkeys((*eligible[:candidate_limit], *cursor_window)))


def _recent_conversation_seek_key(
    *,
    conversation_id: str,
    conversation: Mapping[str, Any],
    activity: datetime,
) -> tuple[int, datetime, str]:
    return (
        int(bool(conversation.get("pinned"))),
        activity,
        conversation_id,
    )


def _ledger_counts(
    index: _MemorySearchIndex,
    *,
    query: str,
    eligible_conversation_ids: set[str],
) -> dict[str, int]:
    matching_conversation_ids = (
        _all_matching_conversation_ids(index, query=query)
        if query
        else set(index.conversations)
    )
    matching_conversation_ids.intersection_update(eligible_conversation_ids)
    return {
        state: sum(
            state
            in index.decision_states_by_conversation.get(
                conversation_id,
                frozenset(),
            )
            for conversation_id in matching_conversation_ids
        )
        for state in ("promising", "watching", "rejected", "revisit_later")
    }


def _all_matching_conversation_ids(
    index: _MemorySearchIndex,
    *,
    query: str,
) -> set[str]:
    conversation_ids: set[str] = set()
    eligible_conversation_ids = set(index.conversations)
    for layer in _SOURCE_LAYERS:
        rows = index.candidates_by_layer[layer]
        for candidate_index in _matching_candidate_indexes(
            index,
            layer=layer,
            query=query,
        ):
            candidate = rows[candidate_index]
            if (
                candidate.conversation_id in eligible_conversation_ids
                and candidate.conversation_id not in conversation_ids
                and search_text_matches_query(query=query, text=candidate.text)
            ):
                conversation_ids.add(candidate.conversation_id)
    return conversation_ids


def _candidate_postings(
    candidates: tuple[_Candidate, ...],
) -> dict[str, frozenset[int]]:
    postings: defaultdict[str, set[int]] = defaultdict(set)
    for index, candidate in enumerate(candidates):
        for trigram in _trigrams(normalize_search_text(candidate.text)):
            postings[trigram].add(index)
    return {
        trigram: frozenset(candidate_indexes)
        for trigram, candidate_indexes in postings.items()
    }


def _trigrams(value: str) -> set[str]:
    return {
        value[index : index + 3]
        for index in range(max(0, len(value) - 2))
    }


def _resolve_asset_symbol(
    index: _MemorySearchIndex,
    *,
    query: str,
) -> str | None:
    normalized_query = normalize_search_symbol(query)
    if normalized_query is None:
        return None
    matches = [
        symbol
        for symbol in index.asset_symbols
        if symbol.startswith(normalized_query)
    ]
    if normalized_query in matches:
        return normalized_query
    return matches[0] if len(matches) == 1 else None


def _candidate(
    *,
    conversation_id: str,
    source_id: str,
    row: Mapping[str, Any],
    text: str,
) -> _Candidate:
    return _Candidate(
        conversation_id=conversation_id,
        source_id=source_id,
        activity=_mapping_activity(row),
        text=text,
    )


def _mapping_activity(row: Mapping[str, Any]) -> datetime:
    value = row.get("updated_at") or row.get("created_at")
    return (
        value
        if isinstance(value, datetime)
        else datetime.min.replace(tzinfo=timezone.utc)
    )


def _group_rows(
    rows: Iterable[dict[str, Any]],
    *,
    field: str,
) -> dict[str, list[dict[str, Any]]]:
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = row.get(field)
        if value is not None:
            grouped[str(value)].append(row)
    return dict(grouped)


def _run_search_text(run: Mapping[str, Any]) -> str:
    card = run.get("conversation_result_card")
    card = card if isinstance(card, Mapping) else {}
    config = run.get("config_snapshot")
    config = config if isinstance(config, Mapping) else {}
    return " ".join(
        value
        for value in (
            str(card.get("title") or ""),
            " ".join(str(symbol) for symbol in run.get("symbols") or []),
            str(config.get("template") or card.get("strategy_label") or ""),
        )
        if value
    )


def _run_symbols(run: Mapping[str, Any]) -> list[str]:
    symbols = run.get("symbols")
    if isinstance(symbols, list) and symbols:
        return [str(symbol) for symbol in symbols]
    card = run.get("conversation_result_card")
    card_symbols = card.get("symbols") if isinstance(card, Mapping) else None
    return (
        [str(symbol) for symbol in card_symbols]
        if isinstance(card_symbols, list)
        else []
    )


def _decision_search_text(
    decision: Mapping[str, Any],
    *,
    evidence: Mapping[str, Any] | None,
) -> str:
    return " ".join(
        value
        for value in (
            str(decision.get("note") or ""),
            str(decision.get("decision_state") or ""),
            str(evidence.get("title") or "") if evidence is not None else "",
            str(evidence.get("digest") or "") if evidence is not None else "",
        )
        if value
    )
