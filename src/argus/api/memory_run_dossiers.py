from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from argus.domain.postgres_run_dossier_reader import (
    RunDossierCursorError,
    RunDossierSourcePage,
    RunDossierSourceRow,
)
from argus.domain.run_dossiers import (
    current_decision_for,
    newest_evidence_backed_completed_runs,
    result_message_id_for,
    row_activity,
    text,
)


def list_memory_run_dossier_source_rows(
    *,
    store: Any,
    user_id: str,
    conversation_id: str,
    limit: int,
    cursor_completed_at: datetime | None,
    cursor_run_id: str | None,
) -> RunDossierSourcePage:
    """Select one bounded memory page under the same canonical rules as Postgres."""
    if limit < 1:
        raise ValueError("Run dossier source limit must be positive.")
    has_cursor = cursor_completed_at is not None or cursor_run_id is not None
    if has_cursor and (
        cursor_completed_at is None
        or cursor_run_id is None
        or cursor_completed_at.tzinfo is None
        or cursor_completed_at.utcoffset() is None
    ):
        raise RunDossierCursorError("Run dossier cursor is incomplete.")

    with store.backtest_finalization_lock:
        runs = [
            _row(run)
            for run_id, run in store.backtest_runs.items()
            if store.backtest_run_owners.get(run_id) == user_id
            and text(_row(run).get("conversation_id")) == conversation_id
        ]
        evidence = [
            _row(artifact)
            for artifact_id, artifact in store.evidence_artifacts.items()
            if store.evidence_artifact_owners.get(artifact_id) == user_id
            and text(_row(artifact).get("source_conversation_id"))
            == conversation_id
        ]
        decisions = [
            _row(decision)
            for decision_id, decision in store.decision_notes.items()
            if store.decision_note_owners.get(decision_id) == user_id
            and text(_row(decision).get("source_conversation_id"))
            == conversation_id
        ]
        eligible = newest_evidence_backed_completed_runs(
            runs=runs,
            evidence=evidence,
        )
        current_decisions = [
            current_decision_for(artifact, decisions) for _, artifact in eligible
        ]
        total_runs = len(eligible)
        decided_runs = sum(decision is not None for decision in current_decisions)

        if cursor_completed_at is not None and cursor_run_id is not None:
            pivot = next(
                (
                    run
                    for run, _ in eligible
                    if text(run.get("id")) == cursor_run_id
                ),
                None,
            )
            if pivot is None or row_activity(pivot) != cursor_completed_at:
                raise RunDossierCursorError(
                    "Run dossier cursor pivot is not eligible."
                )
            eligible = [
                pair
                for pair in eligible
                if (
                    row_activity(pair[0]),
                    text(pair[0].get("id")) or "",
                )
                < (cursor_completed_at, cursor_run_id)
            ]

        selected = eligible[:limit]
        selected_decisions = [
            current_decision_for(artifact, decisions) for _, artifact in selected
        ]

    selected_run_ids = {
        run_id
        for run, _ in selected
        if (run_id := text(run.get("id"))) is not None
    }
    with store.conversation_message_lock:
        messages = [
            _row(message)
            for message in store.messages.get(conversation_id, [])
            if message.role == "assistant"
            and (
                text(_metadata(_row(message)).get("result_run_id"))
                in selected_run_ids
                or text(_metadata(_row(message)).get("latest_run_id"))
                in selected_run_ids
            )
        ]

    return RunDossierSourcePage(
        rows=tuple(
            RunDossierSourceRow(
                run=dict(run),
                artifact=dict(artifact),
                decision=dict(decision) if decision is not None else None,
                result_message_id=result_message_id_for(run, messages),
            )
            for (run, artifact), decision in zip(
                selected,
                selected_decisions,
                strict=True,
            )
        ),
        total_runs=total_runs,
        decided_runs=decided_runs,
    )


def _row(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="python")
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    return {}


def _metadata(message: Mapping[str, Any]) -> Mapping[str, Any]:
    metadata = message.get("metadata")
    return metadata if isinstance(metadata, Mapping) else {}
