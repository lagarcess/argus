from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from heapq import heappush, heappushpop
from itertools import islice
from typing import Any, Callable, Iterable

from argus.domain.search_text import normalize_search_text


@dataclass(frozen=True)
class RankedGroups:
    ordered: tuple[str, ...]
    members: frozenset[str]
    positions: dict[str, int]


@dataclass(frozen=True)
class RankedPosting:
    ordered: tuple[int, ...]
    members: frozenset[int]
    groups: RankedGroups


@dataclass(frozen=True)
class BoundedRankedCandidates:
    indexes: tuple[int, ...]
    match_counts: dict[str, int]


@dataclass(frozen=True)
class RankedCandidateCursor:
    group_id: str
    best_index: int
    match_count: int
    maximum_key: tuple[Any, ...]
    tier: tuple[bool, bool, bool]
    activity: datetime
    layer_rank: int


@dataclass(frozen=True)
class _GroupMatch:
    group_id: str
    best_index: int
    count: int


def ranked_groups(group_ids: Iterable[str]) -> RankedGroups:
    ordered = tuple(dict.fromkeys(group_ids))
    return RankedGroups(
        ordered=ordered,
        members=frozenset(ordered),
        positions={
            group_id: position for position, group_id in enumerate(ordered)
        },
    )


def build_ranked_postings(
    candidates: Iterable[tuple[str, str]],
) -> dict[str, RankedPosting]:
    postings: defaultdict[str, list[int]] = defaultdict(list)
    groups: defaultdict[str, list[str]] = defaultdict(list)
    for index, (group_id, text) in enumerate(candidates):
        for trigram in _trigrams(normalize_search_text(text)):
            postings[trigram].append(index)
            groups[trigram].append(group_id)
    return {
        trigram: RankedPosting(
            ordered=tuple(candidate_indexes),
            members=frozenset(candidate_indexes),
            groups=ranked_groups(groups[trigram]),
        )
        for trigram, candidate_indexes in postings.items()
    }


def indexes_by_group(group_ids: Iterable[str]) -> dict[str, tuple[int, ...]]:
    indexes: defaultdict[str, list[int]] = defaultdict(list)
    for index, group_id in enumerate(group_ids):
        indexes[group_id].append(index)
    return {
        group_id: tuple(group_indexes)
        for group_id, group_indexes in indexes.items()
    }


def bounded_ranked_candidate_indexes(
    *,
    query: str,
    postings: dict[str, RankedPosting],
    candidate_indexes_by_group: dict[str, tuple[int, ...]],
    exact_title_groups: RankedGroups,
    symbol_groups: RankedGroups,
    eligible_groups: RankedGroups,
    cursor: RankedCandidateCursor | None,
    layer_rank: int,
    candidate_limit: int,
    group_id_for_index: Callable[[int], str],
    group_is_pinned: Callable[[str], bool],
    group_activity: Callable[[str], datetime],
    candidate_matches: Callable[[int], bool],
    cursor_group_match: Callable[[str], RankedCandidateCursor | None],
    rank_key: Callable[[int], tuple[Any, ...]],
) -> BoundedRankedCandidates:
    """Select exact top-K groups without materializing a full posting match."""
    required_postings = _required_postings(query=query, postings=postings)
    if not required_postings:
        return BoundedRankedCandidates(indexes=(), match_counts={})
    anchor_groups = min(
        required_postings,
        key=lambda posting: len(posting.groups.ordered),
    ).groups
    match_cache: dict[str, _GroupMatch] = {}
    if cursor is not None and layer_rank == cursor.layer_rank:
        match_cache[cursor.group_id] = _GroupMatch(
            group_id=cursor.group_id,
            best_index=cursor.best_index,
            count=cursor.match_count,
        )

    def matching_group(group_id: str) -> _GroupMatch | None:
        cached = match_cache.get(group_id)
        if cached is not None:
            return cached
        best_index: int | None = None
        count = 0
        for candidate_index in candidate_indexes_by_group.get(group_id, ()):
            if not all(
                candidate_index in posting.members
                for posting in required_postings
            ):
                continue
            if not candidate_matches(candidate_index):
                continue
            count += 1
            if (
                best_index is None
                or rank_key(candidate_index) > rank_key(best_index)
            ):
                best_index = candidate_index
        if best_index is None:
            return None
        return _GroupMatch(
            group_id=group_id,
            best_index=best_index,
            count=count,
        )

    def tier_for_group(group_id: str) -> tuple[bool, bool, bool]:
        return (
            group_is_pinned(group_id),
            group_id in exact_title_groups.members,
            group_id in symbol_groups.members,
        )

    def driver_for_tier(
        tier: tuple[bool, bool, bool],
    ) -> RankedGroups:
        _, exact_title, symbol = tier
        choices = [anchor_groups, eligible_groups]
        if exact_title:
            choices.append(exact_title_groups)
        if symbol:
            choices.append(symbol_groups)
        return min(choices, key=lambda groups: len(groups.ordered))

    tiers = tuple(
        (pinned, exact_title, symbol)
        for pinned in (True, False)
        for exact_title in (True, False)
        for symbol in (True, False)
    )

    def collect_window(
        *,
        maximum_key: tuple[Any, ...] | None = None,
        cursor_tier: tuple[bool, bool, bool] | None = None,
        cursor_activity: datetime | None = None,
    ) -> list[_GroupMatch]:
        selected: list[_GroupMatch] = []
        for tier in tiers:
            if cursor_tier is not None and tier > cursor_tier:
                continue
            if (
                cursor_tier is not None
                and tier == cursor_tier
                and cursor is not None
                and layer_rank > cursor.layer_rank
            ):
                continue
            driver = driver_for_tier(tier)
            start = _cursor_tier_start(
                driver=driver,
                cursor_group_id=cursor.group_id if cursor is not None else None,
                cursor_tier=cursor_tier,
                current_tier=tier,
                cursor_activity=(
                    cursor_activity
                    if cursor is not None and layer_rank == cursor.layer_rank
                    else None
                ),
                group_activity=group_activity,
            )
            remaining = candidate_limit - len(selected)
            tier_heap: list[
                tuple[tuple[Any, ...], int, _GroupMatch]
            ] = []
            found = 0
            cutoff_activity: datetime | None = None
            for group_id in islice(driver.ordered, start, None):
                if (
                    group_id not in eligible_groups.members
                    or group_id not in anchor_groups.members
                    or tier_for_group(group_id) != tier
                ):
                    continue
                activity = group_activity(group_id)
                if cutoff_activity is not None and activity < cutoff_activity:
                    break
                global_match: RankedCandidateCursor | None = None
                if maximum_key is not None:
                    global_match = cursor_group_match(group_id)
                    if (
                        global_match is None
                        or global_match.maximum_key > maximum_key
                    ):
                        continue
                group_match = (
                    _GroupMatch(
                        group_id=group_id,
                        best_index=global_match.best_index,
                        count=global_match.match_count,
                    )
                    if (
                        global_match is not None
                        and global_match.layer_rank == layer_rank
                    )
                    else matching_group(group_id)
                )
                if group_match is None:
                    continue
                best_key = rank_key(group_match.best_index)
                if maximum_key is not None and best_key > maximum_key:
                    continue
                found += 1
                heap_entry = (
                    best_key,
                    group_match.best_index,
                    group_match,
                )
                if len(tier_heap) < remaining:
                    heappush(tier_heap, heap_entry)
                else:
                    heappushpop(tier_heap, heap_entry)
                if found >= remaining:
                    cutoff_activity = activity
            tier_selected = [
                entry[2]
                for entry in sorted(tier_heap, reverse=True)
            ]
            selected.extend(tier_selected)
            match_cache.update(
                (match.group_id, match) for match in tier_selected
            )
            if len(selected) >= candidate_limit:
                break
        return selected

    head = collect_window()
    combined = list(head)
    if cursor is not None:
        cursor_window = collect_window(
            maximum_key=cursor.maximum_key,
            cursor_tier=cursor.tier,
            cursor_activity=cursor.activity,
        )
        combined.extend(cursor_window)
    selected_by_group = {
        group_id_for_index(match.best_index): match
        for match in combined
    }
    return BoundedRankedCandidates(
        indexes=tuple(
            match.best_index for match in selected_by_group.values()
        ),
        match_counts={
            group_id: match.count
            for group_id, match in selected_by_group.items()
        },
    )


def matching_candidate_indexes(
    *,
    query: str,
    postings: dict[str, RankedPosting],
) -> frozenset[int] | set[int]:
    """Return complete membership only for exact ledger counts."""
    required_postings = _required_postings(query=query, postings=postings)
    if not required_postings:
        return frozenset()
    candidate_indexes: frozenset[int] | set[int] | None = None
    for posting in required_postings:
        candidate_indexes = (
            posting.members
            if candidate_indexes is None
            else candidate_indexes.intersection(posting.members)
        )
        if not candidate_indexes:
            return frozenset()
    assert candidate_indexes is not None
    return candidate_indexes


def posting_candidate_might_match(
    *,
    query: str,
    postings: dict[str, RankedPosting],
    candidate_index: int,
) -> bool:
    required_postings = _required_postings(query=query, postings=postings)
    return bool(required_postings) and all(
        candidate_index in posting.members for posting in required_postings
    )


def _required_postings(
    *,
    query: str,
    postings: dict[str, RankedPosting],
) -> tuple[RankedPosting, ...]:
    trigrams = {
        trigram
        for token in normalize_search_text(query).split()
        if len(token) >= 3
        for trigram in _trigrams(token)
    }
    if not trigrams:
        return ()
    required: list[RankedPosting] = []
    for trigram in trigrams:
        posting = postings.get(trigram)
        if posting is None:
            return ()
        required.append(posting)
    return tuple(required)


def _cursor_tier_start(
    *,
    driver: RankedGroups,
    cursor_group_id: str | None,
    cursor_tier: tuple[bool, bool, bool] | None,
    current_tier: tuple[bool, bool, bool],
    cursor_activity: datetime | None,
    group_activity: Callable[[str], datetime],
) -> int:
    if (
        cursor_group_id is None
        or cursor_tier != current_tier
        or cursor_activity is None
    ):
        return 0
    position = driver.positions.get(cursor_group_id)
    if position is None:
        return 0
    while (
        position > 0
        and group_activity(driver.ordered[position - 1]) == cursor_activity
    ):
        position -= 1
    return position


def _trigrams(value: str) -> set[str]:
    return {
        value[index : index + 3]
        for index in range(max(0, len(value) - 2))
    }
