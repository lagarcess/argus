from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Mapping, Sequence, cast

from argus.api.schemas import (
    DecisionState,
    SearchAssetDecisionCounts,
    SearchAssetRollup,
    SearchDecisionAction,
    SearchDossier,
    SearchDossierDecision,
    SearchDossierLeftOff,
    SearchDossierMetric,
    SearchDossierOutcome,
    SearchDossierTested,
    SearchItem,
    SearchMatch,
    SearchMatchLayer,
    SearchRunFreshAction,
    SearchRunFreshSetup,
)
from argus.api.search_utils import score_search_item
from argus.domain.evidence import (
    decision_recall_preview,
    evidence_preview_from_payload,
)
from argus.domain.search_text import (
    normalize_search_symbol,
    normalize_search_text,
    search_text_matches_query,
)

_MAX_SYMBOLS = 5
_MAX_FAMILIES = 5
_MAX_METRICS = 4
_MAX_LABEL_LENGTH = 160
_MAX_MATCH_LENGTH = 500
_DECISION_STATES: tuple[DecisionState, ...] = (
    "promising",
    "watching",
    "rejected",
    "revisit_later",
)
_LAYER_BY_RANK: dict[int, SearchMatchLayer] = {
    1: "conversation",
    2: "message",
    3: "run",
    4: "idea",
    5: "evidence",
    6: "decision",
}
_NEXT_EXPERIMENTS_VERSION = "argus_next_experiments/v1"
_RUN_FRESH_STRATEGIES = {
    "buy_and_hold",
    "dca_accumulation",
    "indicator_threshold",
    "signal_strategy",
}
_RUN_FRESH_CADENCES = {
    "daily",
    "weekly",
    "biweekly",
    "monthly",
    "quarterly",
}
_RUN_FRESH_PARAMETER_KEYS = (
    "indicator",
    "indicator_period",
    "entry_threshold",
    "exit_threshold",
    "fast_period",
    "slow_period",
    "moving_average_type",
)
_ISO_FRACTION_RE = re.compile(
    r"^(?P<prefix>.*\d{2}:\d{2}:\d{2}\.)"
    r"(?P<fraction>\d{1,6})"
    r"(?P<zone>Z|[+-]\d{2}(?::?\d{2})?)$"
)


@dataclass(frozen=True)
class _MatchCandidate:
    object_rank: int
    updated_at: datetime
    text: str
    layer: SearchMatchLayer
    message_id: str | None = None


def project_asset_rollup(
    *,
    runs: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    decisions: Sequence[Mapping[str, Any]],
    query: str,
) -> SearchAssetRollup | None:
    """Summarize one unambiguous canonical symbol from owned completed runs."""
    normalized_query = normalize_search_symbol(query)
    if normalized_query is None:
        return None

    completed_by_id: dict[str, Mapping[str, Any]] = {}
    symbols_by_normalized: dict[str, str] = {}
    run_symbols: dict[str, set[str]] = {}
    for run in runs:
        if run.get("status") != "completed":
            continue
        run_id = _text(run.get("id"))
        if run_id is None:
            continue
        completed_by_id[run_id] = run
        normalized_symbols: set[str] = set()
        for symbol in _run_symbols(run):
            normalized_symbol = normalize_search_symbol(symbol)
            if normalized_symbol is None:
                continue
            normalized_symbols.add(normalized_symbol)
            symbols_by_normalized.setdefault(normalized_symbol, symbol)
        run_symbols[run_id] = normalized_symbols

    matching_symbols = sorted(
        symbol for symbol in symbols_by_normalized if symbol.startswith(normalized_query)
    )
    exact = [symbol for symbol in matching_symbols if symbol == normalized_query]
    if exact:
        resolved_symbol = exact[0]
    elif len(matching_symbols) == 1:
        resolved_symbol = matching_symbols[0]
    else:
        return None

    matching_run_ids = {
        run_id for run_id, symbols in run_symbols.items() if resolved_symbol in symbols
    }
    if not matching_run_ids:
        return None

    artifact_run_ids: dict[str, str] = {}
    artifact_conversation_ids: dict[str, str] = {}
    touched_at_by_run = {
        run_id: _row_activity(completed_by_id[run_id]) for run_id in matching_run_ids
    }
    for artifact in evidence:
        artifact_id = _text(artifact.get("id"))
        run_id = _text(artifact.get("source_run_id"))
        if artifact_id is None or run_id not in matching_run_ids:
            continue
        run_conversation_id = _text(completed_by_id[run_id].get("conversation_id"))
        artifact_conversation_id = _text(artifact.get("source_conversation_id"))
        if run_conversation_id is None or artifact_conversation_id != run_conversation_id:
            continue
        artifact_run_ids[artifact_id] = run_id
        artifact_conversation_ids[artifact_id] = artifact_conversation_id
        touched_at_by_run[run_id] = max(
            touched_at_by_run[run_id],
            _row_activity(artifact),
        )

    latest_decision_by_run: dict[str, Mapping[str, Any]] = {}
    for decision in decisions:
        artifact_id = _text(decision.get("evidence_artifact_id"))
        run_id = artifact_run_ids.get(artifact_id or "")
        if run_id is None or _text(
            decision.get("source_conversation_id")
        ) != artifact_conversation_ids.get(artifact_id or ""):
            continue
        touched_at_by_run[run_id] = max(
            touched_at_by_run[run_id],
            _row_activity(decision),
        )
        current = latest_decision_by_run.get(run_id)
        if current is None or (
            _row_activity(decision),
            _text(decision.get("id")) or "",
        ) > (
            _row_activity(current),
            _text(current.get("id")) or "",
        ):
            latest_decision_by_run[run_id] = decision

    decision_counts: dict[DecisionState, int] = {state: 0 for state in _DECISION_STATES}
    for decision in latest_decision_by_run.values():
        state = decision.get("decision_state")
        if state in decision_counts:
            decision_counts[cast(DecisionState, state)] += 1

    return SearchAssetRollup(
        symbol=symbols_by_normalized[resolved_symbol],
        run_count=len(matching_run_ids),
        decision_counts=SearchAssetDecisionCounts(**decision_counts),
        last_touched_at=max(touched_at_by_run.values()),
    )


def project_conversation_recall(
    *,
    conversation: Mapping[str, Any],
    runs: Sequence[Mapping[str, Any]],
    ideas: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    decisions: Sequence[Mapping[str, Any]],
    messages: Sequence[Mapping[str, Any]] = (),
    query: str,
    allow_decision_action: bool = True,
    language: str = "en",
) -> tuple[int, SearchItem] | None:
    """Build one bounded search row from existing conversation-owned truth."""
    conversation_id = _text(conversation.get("id"))
    if conversation_id is None:
        return None
    title = _text(conversation.get("title")) or "Untitled conversation"
    pinned = bool(conversation.get("pinned"))

    relevant_runs = [
        row for row in runs if _text(row.get("conversation_id")) == conversation_id
    ]
    relevant_ideas = [
        row
        for row in ideas
        if _text(row.get("source_conversation_id")) == conversation_id
    ]
    relevant_evidence = [
        row
        for row in evidence
        if _text(row.get("source_conversation_id")) == conversation_id
    ]
    relevant_decisions = [
        row
        for row in decisions
        if _text(row.get("source_conversation_id")) == conversation_id
    ]
    conversation_messages = [
        row
        for row in messages
        if _text(row.get("conversation_id")) == conversation_id
    ]
    relevant_messages = [
        row
        for row in conversation_messages
        if row.get("role") == "user"
    ]
    completed_runs = [
        row for row in relevant_runs if row.get("status", "completed") == "completed"
    ]

    candidates = _match_candidates(
        conversation=conversation,
        runs=completed_runs,
        ideas=relevant_ideas,
        evidence=relevant_evidence,
        decisions=relevant_decisions,
        messages=relevant_messages,
    )
    recall_match = conversation.get("_recall_match")
    hinted_symbol_match: bool | None = None
    if (
        query
        and isinstance(recall_match, Mapping)
        and (hinted_text := _text(recall_match.get("matched_text"))) is not None
        and search_text_matches_query(query=query, text=hinted_text)
    ):
        hinted_layer = int(recall_match.get("layer_rank") or 0)
        layer = recall_match.get("layer") or _LAYER_BY_RANK.get(hinted_layer)
        if layer not in _LAYER_BY_RANK.values():
            return None
        hinted_activity = _datetime(recall_match.get("activity_at")) or _row_activity(
            conversation
        )
        hinted_symbol_match = bool(recall_match.get("symbol_exact_match"))
        matches = [
            _MatchCandidate(
                object_rank=hinted_layer * 10,
                updated_at=hinted_activity,
                text=hinted_text,
                layer=cast(SearchMatchLayer, layer),
                message_id=_text(recall_match.get("message_id")),
            )
        ]
        match_count = max(int(recall_match.get("match_count") or 1), 1)
    elif query:
        matches = [
            candidate
            for candidate in candidates
            if search_text_matches_query(query=query, text=candidate.text)
        ]
        if not matches:
            return None
        match_count = 0
    else:
        matches = candidates[:1]
        match_count = 1

    scored_matches = [
        (
            score_search_item(
                query=query,
                title=title,
                matched_text=candidate.text,
                pinned=pinned,
                symbol_exact_match=(
                    hinted_symbol_match
                    if hinted_symbol_match is not None
                    else any(
                        query == symbol.lower()
                        for symbol in _symbols_from_runs(completed_runs)
                    )
                ),
                match_layer_rank=candidate.object_rank // 10,
            ),
            candidate,
        )
        for candidate in matches
    ]
    score, winning_match = max(
        scored_matches,
        key=lambda row: (
            row[0],
            row[1].object_rank,
            row[1].updated_at,
            row[1].text,
        ),
    )
    if match_count == 0:
        match_count = sum(candidate.layer == winning_match.layer for candidate in matches)

    sorted_runs = sorted(
        completed_runs,
        key=_row_activity,
        reverse=True,
    )
    sorted_decisions = sorted(
        relevant_decisions,
        key=_row_activity,
        reverse=True,
    )
    artifacts_by_id = {
        _text(row.get("id")): row
        for row in relevant_evidence
        if _text(row.get("id")) is not None
    }
    runs_by_id = {
        _text(row.get("id")): row
        for row in relevant_runs
        if _text(row.get("id")) is not None
    }

    recall_summary = conversation.get("_recall_summary")
    summary = recall_summary if isinstance(recall_summary, Mapping) else {}
    decision = _decision_projection(
        decisions=sorted_decisions,
        artifacts_by_id=artifacts_by_id,
        runs_by_id=runs_by_id,
        include_run_label=int(summary.get("run_count") or len(sorted_runs)) > 1,
    )
    latest_run = sorted_runs[0] if sorted_runs else None
    outcome = _outcome_projection(
        run=latest_run,
        evidence=relevant_evidence,
    )
    decided_run_ids = {
        _text(
            artifacts_by_id.get(_text(row.get("evidence_artifact_id")), {}).get(
                "source_run_id"
            )
        )
        for row in relevant_decisions
    }
    latest_run_decided = summary.get("latest_run_decided")
    latest_suggestion_untaken = summary.get("latest_suggestion_untaken")
    left_off = _left_off_projection(
        run=latest_run,
        is_decided=(
            bool(latest_run_decided)
            if latest_run_decided is not None
            else bool(latest_run and _text(latest_run.get("id")) in decided_run_ids)
        ),
        suggestion_untaken=(
            bool(latest_suggestion_untaken)
            if latest_suggestion_untaken is not None
            else conversation_has_untaken_suggestion(
                run=latest_run,
                messages=conversation_messages,
            )
        ),
    )
    actions = []
    run_fresh_action = _run_fresh_action(run=latest_run, language=language)
    if run_fresh_action is not None:
        actions.append(run_fresh_action)
    decision_action = _decision_action(
        run=latest_run,
        evidence=relevant_evidence,
        decisions=relevant_decisions,
        allow=allow_decision_action,
    )
    if decision_action is not None:
        actions.append(decision_action)
    summary_states = _text_list(summary.get("decision_states"))
    decision_states = tuple(
        state
        for state in _DECISION_STATES
        if state in summary_states
        or (
            not summary_states
            and any(row.get("decision_state") == state for row in relevant_decisions)
        )
    )
    summary_activity = _datetime(summary.get("latest_activity"))
    updated_at = summary_activity or max(
        (
            _row_activity(row)
            for row in candidates_as_rows(
                conversation,
                relevant_runs,
                relevant_ideas,
                relevant_evidence,
                relevant_decisions,
            )
        ),
        default=_row_activity(conversation),
    )
    match_fragment = (
        _query_centered_fragment(
            winning_match.text,
            query=query,
            maximum=_MAX_MATCH_LENGTH,
        )
        or title
    )
    return (
        score,
        SearchItem(
            type="conversation",
            id=conversation_id,
            title=title,
            matched_text=match_fragment,
            updated_at=updated_at,
            conversation_id=conversation_id,
            match=SearchMatch(
                layer=winning_match.layer,
                fragment=match_fragment,
                count=match_count,
                message_id=winning_match.message_id,
            ),
            dossier=SearchDossier(
                decision=decision,
                tested=_tested_projection(sorted_runs, summary=summary),
                outcome=outcome,
                left_off=left_off,
            ),
            actions=actions,
            decision_states=decision_states,
        ),
    )


def candidates_as_rows(
    conversation: Mapping[str, Any],
    runs: Sequence[Mapping[str, Any]],
    ideas: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    decisions: Sequence[Mapping[str, Any]],
) -> Iterable[Mapping[str, Any]]:
    yield conversation
    yield from runs
    yield from ideas
    yield from evidence
    yield from decisions


def _match_candidates(
    *,
    conversation: Mapping[str, Any],
    runs: Sequence[Mapping[str, Any]],
    ideas: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    decisions: Sequence[Mapping[str, Any]],
    messages: Sequence[Mapping[str, Any]],
) -> list[_MatchCandidate]:
    candidates: list[_MatchCandidate] = []
    for conversation_text in (
        _text(conversation.get("title")),
        _text(conversation.get("last_message_preview")),
    ):
        if conversation_text:
            candidates.append(
                _MatchCandidate(
                    10,
                    _row_activity(conversation),
                    conversation_text,
                    "conversation",
                )
            )
    for message in messages:
        content = _text(message.get("content"))
        message_id = _text(message.get("id"))
        if content and message_id:
            candidates.append(
                _MatchCandidate(
                    20,
                    _row_activity(message),
                    content,
                    "message",
                    message_id,
                )
            )
    for run in runs:
        candidates.append(
            _MatchCandidate(30, _row_activity(run), _run_search_text(run), "run")
        )
    for idea in ideas:
        candidates.append(
            _MatchCandidate(
                40,
                _row_activity(idea),
                " ".join(
                    part
                    for part in (
                        _text(idea.get("title")),
                        _text(idea.get("summary")),
                    )
                    if part
                ),
                "idea",
            )
        )
    for artifact in evidence:
        candidates.append(
            _MatchCandidate(
                50,
                _row_activity(artifact),
                " ".join(
                    part
                    for part in (
                        _text(artifact.get("title")),
                        _text(artifact.get("digest")),
                    )
                    if part
                ),
                "evidence",
            )
        )
    for decision in decisions:
        candidates.append(
            _MatchCandidate(
                60,
                _row_activity(decision),
                " ".join(
                    part
                    for part in (
                        _text(decision.get("note")),
                        _text(decision.get("decision_state")),
                        _text(decision.get("artifact_title")),
                        _text(decision.get("artifact_digest")),
                    )
                    if part
                ),
                "decision",
            )
        )
    return candidates


def _decision_projection(
    *,
    decisions: Sequence[Mapping[str, Any]],
    artifacts_by_id: Mapping[str | None, Mapping[str, Any]],
    runs_by_id: Mapping[str | None, Mapping[str, Any]],
    include_run_label: bool,
) -> SearchDossierDecision | None:
    if not decisions:
        return None
    latest = decisions[0]
    artifact = artifacts_by_id.get(_text(latest.get("evidence_artifact_id")), {})
    payload = artifact.get("payload")
    preview = decision_recall_preview(
        decision_state=latest.get("decision_state"),
        note=latest.get("note"),
        artifact_title=artifact.get("title") or latest.get("artifact_title"),
        artifact_digest=artifact.get("digest") or latest.get("artifact_digest"),
        artifact_payload=(
            payload
            if isinstance(payload, dict)
            else cast(dict[str, Any] | None, latest.get("artifact_payload"))
        ),
    )
    state = preview.get("decision_state")
    if state not in _DECISION_STATES:
        return None
    source_run_id = _text(artifact.get("source_run_id") or latest.get("source_run_id"))
    judged_run = runs_by_id.get(source_run_id)
    return SearchDossierDecision(
        state=cast(DecisionState, state),
        note=cast(str | None, preview.get("note")),
        run_label=_run_label(judged_run) if include_run_label and judged_run else None,
    )


def _tested_projection(
    runs: Sequence[Mapping[str, Any]],
    *,
    summary: Mapping[str, Any] | None = None,
) -> SearchDossierTested:
    summary = summary or {}
    start_dates: list[date] = []
    end_dates: list[date] = []
    for run in runs:
        start, end = _run_date_span(run)
        if start is not None:
            start_dates.append(start)
        if end is not None:
            end_dates.append(end)
    run_counts = [
        int(run.get("conversation_run_count") or 0)
        for run in runs
        if run.get("conversation_run_count")
    ]
    return SearchDossierTested(
        symbols=(_text_list(summary.get("symbols")) or _symbols_from_runs(runs))[
            :_MAX_SYMBOLS
        ],
        strategy_families=(
            _text_list(summary.get("strategy_families")) or _strategy_families(runs)
        )[:_MAX_FAMILIES],
        run_count=int(summary.get("run_count") or max(run_counts, default=len(runs))),
        start_date=_date(summary.get("start_date"))
        or (min(start_dates) if start_dates else None),
        end_date=_date(summary.get("end_date"))
        or (max(end_dates) if end_dates else None),
    )


def _outcome_projection(
    *,
    run: Mapping[str, Any] | None,
    evidence: Sequence[Mapping[str, Any]],
) -> SearchDossierOutcome | None:
    if run is None:
        return None
    run_id = _text(run.get("id"))
    artifact = max(
        (row for row in evidence if _text(row.get("source_run_id")) == run_id),
        key=_row_activity,
        default={},
    )
    payload = artifact.get("payload")
    preview = evidence_preview_from_payload(
        digest=artifact.get("digest"),
        title=artifact.get("title"),
        payload=payload if isinstance(payload, dict) else None,
    )
    metrics = preview.get("metrics_summary")
    metric_rows: list[SearchDossierMetric] = []
    if isinstance(metrics, dict):
        for name, value in metrics.items():
            if len(metric_rows) >= _MAX_METRICS:
                break
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                metric_rows.append(SearchDossierMetric(name=name, value=value))
    return SearchDossierOutcome(
        run_label=_run_label(run),
        completed_at=_row_activity(run),
        benchmark_symbol=_text(
            preview.get("benchmark_symbol") or run.get("benchmark_symbol")
        ),
        quick_take=_bounded_text(preview.get("quick_take"), 500),
        metrics=metric_rows,
    )


def _left_off_projection(
    *,
    run: Mapping[str, Any] | None,
    is_decided: bool,
    suggestion_untaken: bool,
) -> SearchDossierLeftOff | None:
    if run is None:
        return None
    completed_at = _row_activity(run)
    nudge = "undecided" if not is_decided else None
    if nudge is None and suggestion_untaken:
        nudge = "suggestion_untaken"
    if nudge is None and _is_stale_result(completed_at):
        nudge = "stale_result"
    return SearchDossierLeftOff(
        run_label=_run_label(run),
        completed_at=completed_at,
        nudge=nudge,
    )


def _run_fresh_action(
    *,
    run: Mapping[str, Any] | None,
    language: str,
) -> SearchRunFreshAction | None:
    if run is None:
        return None
    run_id = _text(run.get("id"))
    config = _config(run)
    resolved_strategy = _mapping(config.get("resolved_strategy"))
    resolved_parameters = _mapping(config.get("resolved_parameters"))
    resolved_engine_config = _mapping(resolved_parameters.get("engine_config"))
    snapshot_engine_config = _mapping(config.get("engine_config"))
    strategy_type = _text(
        resolved_strategy.get("strategy_type") or config.get("template")
    )
    if strategy_type not in _RUN_FRESH_STRATEGIES or run_id is None:
        return None

    symbols = _run_symbols(run)
    asset_class = _text(
        resolved_strategy.get("asset_class") or run.get("asset_class")
    )
    timeframe = _text(resolved_parameters.get("timeframe") or config.get("timeframe"))
    benchmark_symbol = _text(
        resolved_parameters.get("benchmark_symbol")
        or config.get("benchmark_symbol")
        or run.get("benchmark_symbol")
    )
    original_start, original_end = _run_date_span(run)
    if (
        not symbols
        or asset_class not in {"equity", "crypto", "currency_pair"}
        or timeframe is None
        or benchmark_symbol is None
        or original_start is None
        or original_end is None
        or original_end < original_start
    ):
        return None

    sizing_mode = _text(resolved_parameters.get("sizing_mode"))
    capital_amount = _number(
        resolved_parameters.get("capital_amount")
        or config.get("starting_capital")
        or config.get("capital_amount")
    )
    position_size = _number(resolved_parameters.get("position_size"))
    if sizing_mode is None:
        sizing_mode = "position_size" if position_size is not None else "capital_amount"
    if sizing_mode == "capital_amount":
        position_size = None
    elif sizing_mode == "position_size":
        capital_amount = None
    else:
        return None
    cadence = _text(resolved_parameters.get("cadence") or config.get("cadence"))
    if strategy_type == "dca_accumulation":
        if cadence not in _RUN_FRESH_CADENCES:
            return None
        recurring_contribution = _consistent_number(
            resolved_parameters.get("recurring_contribution"),
            resolved_engine_config.get("recurring_contribution"),
            snapshot_engine_config.get("recurring_contribution"),
        )
        starting_principal = _consistent_number(
            resolved_parameters.get("starting_principal"),
            resolved_engine_config.get("starting_principal"),
            snapshot_engine_config.get("starting_principal"),
            allow_zero=True,
        )
        if (
            recurring_contribution is None
            or starting_principal != 0
            or capital_amount != recurring_contribution
        ):
            return None
    else:
        cadence = None
        recurring_contribution = None
        starting_principal = None

    today = date.today()
    current_start = today - timedelta(days=(original_end - original_start).days)
    parameters = {
        key: resolved_parameters[key]
        for key in _RUN_FRESH_PARAMETER_KEYS
        if key in resolved_parameters
        and isinstance(resolved_parameters[key], (str, int, float, bool))
    }
    execution_realism_valid, execution_realism = _consistent_mapping(
        resolved_engine_config.get("_execution_realism"),
        snapshot_engine_config.get("_execution_realism"),
        resolved_parameters.get("_execution_realism"),
        resolved_parameters.get("execution_realism"),
        config.get("_execution_realism"),
    )
    if not execution_realism_valid:
        return None
    try:
        setup = SearchRunFreshSetup(
            strategy_type=strategy_type,
            symbols=symbols,
            asset_class=asset_class,
            timeframe=timeframe,
            date_range={"start": current_start, "end": today},
            sizing_mode=sizing_mode,
            capital_amount=capital_amount,
            position_size=position_size,
            cadence=cadence,
            recurring_contribution=recurring_contribution,
            starting_principal=starting_principal,
            benchmark_symbol=benchmark_symbol,
            entry_rule=_mapping_or_none(resolved_strategy.get("entry_rule")),
            exit_rule=_mapping_or_none(resolved_strategy.get("exit_rule")),
            rule_spec=_mapping_or_none(
                resolved_strategy.get("rule_spec")
                or resolved_parameters.get("rule_spec")
                or config.get("rule_spec")
            ),
            parameters=parameters,
            execution_realism=execution_realism,
        )
        return SearchRunFreshAction(
            source_run_id=run_id,
            run_label=_run_label(run),
            canonical_setup=setup,
            send_text=_run_fresh_send_text(setup=setup, language=language),
        )
    except ValueError:
        return None


def _decision_action(
    *,
    run: Mapping[str, Any] | None,
    evidence: Sequence[Mapping[str, Any]],
    decisions: Sequence[Mapping[str, Any]],
    allow: bool,
) -> SearchDecisionAction | None:
    if not allow or run is None:
        return None
    run_id = _text(run.get("id"))
    artifact = max(
        (row for row in evidence if _text(row.get("source_run_id")) == run_id),
        key=_row_activity,
        default=None,
    )
    if artifact is None or (artifact_id := _text(artifact.get("id"))) is None:
        return None
    latest_decision = max(
        (
            row
            for row in decisions
            if _text(row.get("evidence_artifact_id")) == artifact_id
        ),
        key=_row_activity,
        default=None,
    )
    state = latest_decision.get("decision_state") if latest_decision else None
    return SearchDecisionAction(
        evidence_artifact_id=artifact_id,
        decision_state=cast(DecisionState | None, state)
        if state in _DECISION_STATES
        else None,
        note=_bounded_text(latest_decision.get("note"), 2000)
        if latest_decision
        else None,
        run_label=_run_label(run),
    )


def _run_fresh_send_text(*, setup: SearchRunFreshSetup, language: str) -> str:
    symbols = ", ".join(setup.symbols)
    amount = (
        _format_number(setup.capital_amount)
        if setup.sizing_mode == "capital_amount"
        else _format_number(setup.position_size)
    )
    if language == "es-419":
        cadence = {
            "daily": "diaria",
            "weekly": "semanal",
            "biweekly": "quincenal",
            "monthly": "mensual",
            "quarterly": "trimestral",
        }.get(setup.cadence or "", setup.cadence or "")
        strategy = {
            "buy_and_hold": "comprar y mantener",
            "dca_accumulation": f"acumulación DCA {cadence}",
            "indicator_threshold": "estrategia de umbral de indicador",
            "signal_strategy": "estrategia de señales",
        }[setup.strategy_type]
        if setup.strategy_type == "dca_accumulation":
            sizing = (
                f"un aporte recurrente de "
                f"${_format_number(setup.recurring_contribution)} {cadence} y "
                f"capital inicial de ${_format_number(setup.starting_principal)}"
            )
        else:
            sizing = (
                f"${amount} de capital inicial"
                if setup.sizing_mode == "capital_amount"
                else f"{amount} por posición"
            )
        prefix = (
            "Prueba nuevamente esta configuración compatible exacta del "
            f"{setup.date_range.start.isoformat()} al "
            f"{setup.date_range.end.isoformat()}: {strategy} {symbols} en "
            f"{setup.timeframe} con {sizing}, referencia "
            f"{setup.benchmark_symbol}, solo posiciones largas y pesos iguales"
        )
        suffix = (
            ". Muestra la confirmación Lista para ejecutar; todavía no la ejecutes."
        )
        detail_labels = {
            "entry_rule": "regla de entrada",
            "exit_rule": "regla de salida",
            "rule_spec": "especificación de reglas",
            "parameters": "parámetros",
            "execution_realism": "costos modelados",
        }
    else:
        cadence = setup.cadence or ""
        strategy = {
            "buy_and_hold": "buy and hold",
            "dca_accumulation": f"{cadence} DCA accumulation",
            "indicator_threshold": "indicator threshold strategy",
            "signal_strategy": "signal strategy",
        }[setup.strategy_type]
        if setup.strategy_type == "dca_accumulation":
            sizing = (
                f"a ${_format_number(setup.recurring_contribution)} {cadence} "
                "recurring contribution and "
                f"${_format_number(setup.starting_principal)} starting principal"
            )
        else:
            sizing = (
                f"${amount} starting capital"
                if setup.sizing_mode == "capital_amount"
                else f"{amount} per position"
            )
        prefix = (
            "Test this exact supported setup again from "
            f"{setup.date_range.start.isoformat()} to "
            f"{setup.date_range.end.isoformat()}: {strategy} {symbols} on "
            f"{setup.timeframe} with {sizing}, benchmark "
            f"{setup.benchmark_symbol}, long only and equal weight"
        )
        suffix = (
            ". Show the Ready-to-run confirmation; do not run it yet."
        )
        detail_labels = {
            "entry_rule": "entry rule",
            "exit_rule": "exit rule",
            "rule_spec": "rule spec",
            "parameters": "parameters",
            "execution_realism": "execution realism",
        }
    details = [
        (detail_id, value)
        for detail_id, value in (
            ("entry_rule", setup.entry_rule),
            ("exit_rule", setup.exit_rule),
            ("rule_spec", setup.rule_spec),
            ("parameters", setup.parameters or None),
            ("execution_realism", setup.execution_realism),
        )
        if value is not None
    ]
    if setup.strategy_type == "buy_and_hold":
        details = [
            pair
            for pair in details
            if pair[0] not in {"entry_rule", "exit_rule"}
        ]
    detail_text = "".join(
        f"; {detail_labels[detail_id]} {_stable_json(value)}"
        for detail_id, value in details
    )
    return f"{prefix}{detail_text}{suffix}"


def _format_number(value: float | None) -> str:
    if value is None:
        return "0"
    return f"{value:g}"


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_or_none(value: object) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, Mapping) else None


def _consistent_mapping(*values: object) -> tuple[bool, dict[str, Any] | None]:
    present = [value for value in values if value is not None]
    if not present:
        return True, None
    if any(not isinstance(value, Mapping) for value in present):
        return False, None
    mappings = [dict(cast(Mapping[str, Any], value)) for value in present]
    if any(value != mappings[0] for value in mappings[1:]):
        return False, None
    return True, mappings[0]


def _consistent_number(
    *values: object,
    allow_zero: bool = False,
) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    parsed = [
        _nonnegative_number(value) if allow_zero else _number(value)
        for value in present
    ]
    if any(value is None for value in parsed):
        return None
    numbers = cast(list[float], parsed)
    if any(value != numbers[0] for value in numbers[1:]):
        return None
    return numbers[0]


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if value > 0 else None


def _nonnegative_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if value >= 0 else None


def _run_search_text(run: Mapping[str, Any]) -> str:
    return " ".join(
        part
        for part in (
            _run_label(run),
            " ".join(_run_symbols(run)),
            _text(_config(run).get("template")),
        )
        if part
    )


def _run_label(run: Mapping[str, Any] | None) -> str:
    if run is None:
        return "Backtest run"
    card = run.get("conversation_result_card")
    if isinstance(card, dict):
        label = _bounded_text(card.get("title"), _MAX_LABEL_LENGTH)
        if label:
            return label
    symbols = ", ".join(_run_symbols(run))
    return _bounded_text(f"{symbols} Backtest", _MAX_LABEL_LENGTH) or "Backtest run"


def _symbols_from_runs(runs: Sequence[Mapping[str, Any]]) -> list[str]:
    return list(dict.fromkeys(symbol for run in runs for symbol in _run_symbols(run)))


def _strategy_families(runs: Sequence[Mapping[str, Any]]) -> list[str]:
    values: list[str] = []
    for run in runs:
        card = run.get("conversation_result_card")
        family = _text(_config(run).get("template")) or (
            _text(card.get("strategy_label")) if isinstance(card, dict) else None
        )
        if family and family not in values:
            values.append(family)
    return values


def _run_symbols(run: Mapping[str, Any]) -> list[str]:
    symbols = _text_list(run.get("symbols"))
    if symbols:
        return symbols
    card = run.get("conversation_result_card")
    return _text_list(card.get("symbols")) if isinstance(card, dict) else []


def _config(run: Mapping[str, Any]) -> Mapping[str, Any]:
    value = run.get("config_snapshot")
    return value if isinstance(value, dict) else {}


def _run_date_span(run: Mapping[str, Any]) -> tuple[date | None, date | None]:
    config = _config(run)
    config_date_range = _mapping(config.get("date_range"))
    card = run.get("conversation_result_card")
    date_range = card.get("date_range") if isinstance(card, dict) else None
    if not isinstance(date_range, dict):
        date_range = {}
    return (
        _date(
            config.get("start_date")
            or config_date_range.get("start")
            or date_range.get("start")
        ),
        _date(
            config.get("end_date")
            or config_date_range.get("end")
            or date_range.get("end")
        ),
    )


def _date(value: object) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _datetime(value: object) -> datetime | None:
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value
    if isinstance(value, str):
        parsed = _parse_iso_datetime(value)
        if parsed is None:
            return None
        return parsed if parsed.tzinfo is not None else None
    return None


def _row_activity(row: Mapping[str, Any]) -> datetime:
    for key in ("updated_at", "created_at"):
        value = row.get(key)
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            parsed = _parse_iso_datetime(value)
            if parsed is None:
                continue
            if parsed.tzinfo is not None:
                return parsed
    return datetime.min.astimezone()


def _parse_iso_datetime(value: str) -> datetime | None:
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        match = _ISO_FRACTION_RE.fullmatch(value)
        if match is None:
            return None
        normalized = (
            f"{match.group('prefix')}"
            f"{match.group('fraction').ljust(6, '0')}"
            f"{match.group('zone').replace('Z', '+00:00')}"
        )
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _bounded_text(value: object, maximum: int) -> str | None:
    text = _text(value)
    if text is None:
        return None
    return text[:maximum]


def _normalized_text_with_source_indexes(value: str) -> tuple[str, list[int]]:
    normalized: list[str] = []
    source_indexes: list[int] = []
    pending_separator = False
    for source_index, character in enumerate(value):
        for folded in character.casefold():
            if folded == "_" or not folded.isalnum():
                pending_separator = bool(normalized)
                continue
            if pending_separator:
                normalized.append(" ")
                source_indexes.append(source_index)
                pending_separator = False
            normalized.append(folded)
            source_indexes.append(source_index)
    return "".join(normalized), source_indexes


def _query_centered_fragment(
    value: object,
    *,
    query: str,
    maximum: int,
) -> str | None:
    text = _text(value)
    if text is None or len(text) <= maximum:
        return text
    normalized_text, source_indexes = _normalized_text_with_source_indexes(text)
    normalized_query = normalize_search_text(query)
    if not normalized_query or not source_indexes:
        return text[:maximum]

    contiguous_start = normalized_text.find(normalized_query)
    if contiguous_start >= 0:
        normalized_spans = [(contiguous_start, contiguous_start + len(normalized_query))]
    else:
        token_span = _smallest_token_cover(
            normalized_text,
            tuple(dict.fromkeys(normalized_query.split())),
        )
        normalized_spans = [token_span] if token_span is not None else []
    if not normalized_spans:
        return text[:maximum]

    source_start = source_indexes[min(start for start, _ in normalized_spans)]
    source_end = source_indexes[max(end for _, end in normalized_spans) - 1] + 1
    matched_length = source_end - source_start
    if matched_length >= maximum:
        return text[source_start : source_start + maximum]

    leading_context = (maximum - matched_length) // 2
    fragment_start = max(0, source_start - leading_context)
    fragment_end = min(len(text), fragment_start + maximum)
    fragment_start = max(0, fragment_end - maximum)
    return text[fragment_start:fragment_end]


def _smallest_token_cover(
    normalized_text: str,
    tokens: tuple[str, ...],
) -> tuple[int, int] | None:
    events: list[tuple[int, int, int]] = []
    for token_index, token in enumerate(tokens):
        token_start = normalized_text.find(token)
        if token_start < 0:
            return None
        while token_start >= 0:
            events.append((token_start, token_start + len(token), token_index))
            token_start = normalized_text.find(token, token_start + 1)
    events.sort()

    counts = [0] * len(tokens)
    covered_tokens = 0
    left = 0
    maximum_ends: deque[tuple[int, int]] = deque()
    best: tuple[int, int, int] | None = None

    for right, (_, token_end, token_index) in enumerate(events):
        while maximum_ends and maximum_ends[-1][1] <= token_end:
            maximum_ends.pop()
        maximum_ends.append((right, token_end))
        if counts[token_index] == 0:
            covered_tokens += 1
        counts[token_index] += 1

        while covered_tokens == len(tokens):
            span_start = events[left][0]
            span_end = maximum_ends[0][1]
            candidate = (span_end - span_start, span_start, span_end)
            if best is None or candidate < best:
                best = candidate

            left_token_index = events[left][2]
            counts[left_token_index] -= 1
            if counts[left_token_index] == 0:
                covered_tokens -= 1
            if maximum_ends[0][0] == left:
                maximum_ends.popleft()
            left += 1

    return None if best is None else (best[1], best[2])


def _text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _bounded_text(item, 40)) is not None]


def _is_stale_result(completed_at: datetime) -> bool:
    """Treat results older than the previous calendar month as stale."""
    current = datetime.now(tz=completed_at.tzinfo)
    if current.month == 1:
        previous_month_start = current.replace(year=current.year - 1, month=12, day=1)
    else:
        previous_month_start = current.replace(month=current.month - 1, day=1)
    return completed_at < previous_month_start.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def conversation_has_untaken_suggestion(
    *,
    run: Mapping[str, Any] | None,
    messages: Sequence[Mapping[str, Any]],
) -> bool:
    run_id = _text(run.get("id")) if run is not None else None
    if run_id is None:
        return False
    offers = [
        row
        for row in messages
        if row.get("role") == "assistant"
        and _text(_message_metadata(row).get("result_run_id")) == run_id
        and valid_next_experiments_metadata(_message_metadata(row))
    ]
    if not offers:
        return False
    latest_offer = max(offers, key=_message_order)
    return not any(
        row.get("role") == "user" and _message_order(row) > _message_order(latest_offer)
        for row in messages
    )


def valid_next_experiments_metadata(metadata: object) -> bool:
    if not isinstance(metadata, Mapping):
        return False
    raw_sidecar = metadata.get("next_experiments")
    sidecar = raw_sidecar if isinstance(raw_sidecar, Mapping) else {}
    return (
        sidecar.get("version") == _NEXT_EXPERIMENTS_VERSION
        and isinstance(sidecar.get("rows"), list)
        and bool(sidecar["rows"])
    )


def _message_order(row: Mapping[str, Any]) -> tuple[datetime, str]:
    return _row_activity(row), _text(row.get("id")) or ""


def _message_metadata(row: Mapping[str, Any]) -> Mapping[str, Any]:
    metadata = row.get("metadata")
    return metadata if isinstance(metadata, Mapping) else {}
