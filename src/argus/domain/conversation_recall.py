from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable, Mapping, Sequence, cast

from argus.api.schemas import (
    DecisionState,
    SearchDossier,
    SearchDossierDecision,
    SearchDossierLeftOff,
    SearchDossierMetric,
    SearchDossierOutcome,
    SearchDossierTested,
    SearchItem,
)
from argus.api.search_utils import score_search_item
from argus.domain.evidence import (
    decision_recall_preview,
    evidence_preview_from_payload,
)
from argus.domain.search_text import search_text_matches_query

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


def project_conversation_recall(
    *,
    conversation: Mapping[str, Any],
    runs: Sequence[Mapping[str, Any]],
    ideas: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    decisions: Sequence[Mapping[str, Any]],
    query: str,
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
    completed_runs = [
        row for row in relevant_runs if row.get("status", "completed") == "completed"
    ]

    candidates = _match_candidates(
        conversation=conversation,
        runs=completed_runs,
        ideas=relevant_ideas,
        evidence=relevant_evidence,
        decisions=relevant_decisions,
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
        hinted_activity = _datetime(recall_match.get("activity_at")) or _row_activity(
            conversation
        )
        hinted_symbol_match = bool(recall_match.get("symbol_exact_match"))
        matches = [(hinted_layer * 10, hinted_activity, hinted_text)]
    elif query:
        matches = [
            candidate
            for candidate in candidates
            if search_text_matches_query(query=query, text=candidate[2])
        ]
        if not matches:
            return None
    else:
        matches = candidates[:1]

    scored_matches = [
        (
            score_search_item(
                query=query,
                title=title,
                matched_text=text,
                pinned=pinned,
                symbol_exact_match=(
                    hinted_symbol_match
                    if hinted_symbol_match is not None
                    else any(
                        query == symbol.lower()
                        for symbol in _symbols_from_runs(completed_runs)
                    )
                ),
                match_layer_rank=object_rank // 10,
            ),
            object_rank,
            updated_at,
            text,
        )
        for object_rank, updated_at, text in matches
    ]
    score, _, _, matched_text = max(
        scored_matches,
        key=lambda row: (row[0], row[1], row[2], row[3]),
    )

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
        _text(artifacts_by_id.get(_text(row.get("evidence_artifact_id")), {}).get(
            "source_run_id"
        ))
        for row in relevant_decisions
    }
    latest_run_decided = summary.get("latest_run_decided")
    left_off = _left_off_projection(
        run=latest_run,
        is_decided=(
            bool(latest_run_decided)
            if latest_run_decided is not None
            else bool(
                latest_run and _text(latest_run.get("id")) in decided_run_ids
            )
        ),
    )
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
    return (
        score,
        SearchItem(
            type="conversation",
            id=conversation_id,
            title=title,
            matched_text=_bounded_text(matched_text, _MAX_MATCH_LENGTH) or title,
            updated_at=updated_at,
            conversation_id=conversation_id,
            dossier=SearchDossier(
                decision=decision,
                tested=_tested_projection(sorted_runs, summary=summary),
                outcome=outcome,
                left_off=left_off,
            ),
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
) -> list[tuple[int, datetime, str]]:
    candidates: list[tuple[int, datetime, str]] = []
    for conversation_text in (
        _text(conversation.get("title")),
        _text(conversation.get("last_message_preview")),
    ):
        if conversation_text:
            candidates.append(
                (10, _row_activity(conversation), conversation_text)
            )
    for run in runs:
        candidates.append((20, _row_activity(run), _run_search_text(run)))
    for idea in ideas:
        candidates.append(
            (
                30,
                _row_activity(idea),
                " ".join(
                    part
                    for part in (
                        _text(idea.get("title")),
                        _text(idea.get("summary")),
                    )
                    if part
                ),
            )
        )
    for artifact in evidence:
        candidates.append(
            (
                40,
                _row_activity(artifact),
                " ".join(
                    part
                    for part in (
                        _text(artifact.get("title")),
                        _text(artifact.get("digest")),
                    )
                    if part
                ),
            )
        )
    for decision in decisions:
        candidates.append(
            (
                50,
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
    source_run_id = _text(
        artifact.get("source_run_id") or latest.get("source_run_id")
    )
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
        symbols=(
            _text_list(summary.get("symbols")) or _symbols_from_runs(runs)
        )[:_MAX_SYMBOLS],
        strategy_families=(
            _text_list(summary.get("strategy_families"))
            or _strategy_families(runs)
        )[:_MAX_FAMILIES],
        run_count=int(
            summary.get("run_count") or max(run_counts, default=len(runs))
        ),
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
        (
            row
            for row in evidence
            if _text(row.get("source_run_id")) == run_id
        ),
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
) -> SearchDossierLeftOff | None:
    if run is None:
        return None
    completed_at = _row_activity(run)
    nudge = "undecided" if not is_decided else None
    if nudge is None and _is_stale_result(completed_at):
        nudge = "stale_result"
    return SearchDossierLeftOff(
        run_label=_run_label(run),
        completed_at=completed_at,
        nudge=nudge,
    )


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
    return list(
        dict.fromkeys(
            symbol
            for run in runs
            for symbol in _run_symbols(run)
        )
    )


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
    card = run.get("conversation_result_card")
    date_range = card.get("date_range") if isinstance(card, dict) else None
    if not isinstance(date_range, dict):
        date_range = {}
    return (
        _date(config.get("start_date") or date_range.get("start")),
        _date(config.get("end_date") or date_range.get("end")),
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
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else None
    return None


def _row_activity(row: Mapping[str, Any]) -> datetime:
    for key in ("updated_at", "created_at"):
        value = row.get(key)
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                continue
            if parsed.tzinfo is not None:
                return parsed
    return datetime.min.astimezone()


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


def _text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        text
        for item in value
        if (text := _bounded_text(item, 40)) is not None
    ]


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
