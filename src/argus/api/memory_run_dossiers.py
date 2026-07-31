from __future__ import annotations

import heapq
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from argus.domain.postgres_run_dossier_reader import (
    RunDossierCursorError,
    RunDossierSourcePage,
    RunDossierSourceRow,
)
from argus.domain.run_dossiers import (
    result_message_id_for,
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
        latest_artifact_by_run: dict[str, tuple[datetime, str, str]] = {}
        for artifact_key, artifact in store.evidence_artifacts.items():
            if (
                store.evidence_artifact_owners.get(artifact_key) != user_id
                or text(_field(artifact, "source_conversation_id"))
                != conversation_id
            ):
                continue
            run_id = text(_field(artifact, "source_run_id"))
            artifact_id = text(_field(artifact, "id"))
            if run_id is None or artifact_id is None:
                continue
            candidate = (
                _record_activity(artifact),
                artifact_id,
                artifact_key,
            )
            current = latest_artifact_by_run.get(run_id)
            if current is None or candidate > current:
                latest_artifact_by_run[run_id] = candidate

        latest_decision_by_artifact: dict[str, tuple[datetime, str, str]] = {}
        current_artifact_ids = {
            artifact_id
            for _, artifact_id, _ in latest_artifact_by_run.values()
        }
        for decision_key, decision in store.decision_notes.items():
            if (
                store.decision_note_owners.get(decision_key) != user_id
                or text(_field(decision, "source_conversation_id"))
                != conversation_id
            ):
                continue
            artifact_id = text(_field(decision, "evidence_artifact_id"))
            decision_id = text(_field(decision, "id"))
            if (
                artifact_id is None
                or artifact_id not in current_artifact_ids
                or decision_id is None
            ):
                continue
            candidate = (
                _record_activity(decision),
                decision_id,
                decision_key,
            )
            current = latest_decision_by_artifact.get(artifact_id)
            if current is None or candidate > current:
                latest_decision_by_artifact[artifact_id] = candidate

        total_runs = 0
        decided_runs = 0
        cursor_is_eligible = False
        page_keys: list[tuple[datetime, str, str, str, str]] = []
        for run_key, run in store.backtest_runs.items():
            if (
                store.backtest_run_owners.get(run_key) != user_id
                or text(_field(run, "conversation_id")) != conversation_id
                or _field(run, "status", "completed") != "completed"
            ):
                continue
            run_id = text(_field(run, "id"))
            artifact_ref = (
                latest_artifact_by_run.get(run_id)
                if run_id is not None
                else None
            )
            if run_id is None or artifact_ref is None:
                continue

            activity = _record_activity(run)
            artifact_id = artifact_ref[1]
            decision_ref = latest_decision_by_artifact.get(artifact_id)
            total_runs += 1
            decided_runs += decision_ref is not None
            if (
                cursor_completed_at is not None
                and run_id == cursor_run_id
                and activity == cursor_completed_at
            ):
                cursor_is_eligible = True

            page_key = (activity, run_id)
            if (
                cursor_completed_at is not None
                and cursor_run_id is not None
                and page_key >= (cursor_completed_at, cursor_run_id)
            ):
                continue
            candidate = (
                activity,
                run_id,
                run_key,
                artifact_ref[2],
                decision_ref[2] if decision_ref is not None else "",
            )
            if len(page_keys) < limit:
                heapq.heappush(page_keys, candidate)
            elif candidate > page_keys[0]:
                heapq.heapreplace(page_keys, candidate)

        if cursor_completed_at is not None and not cursor_is_eligible:
            raise RunDossierCursorError(
                "Run dossier cursor pivot is not eligible."
            )

        selected = [
            (
                _row(store.backtest_runs[run_key]),
                _row(store.evidence_artifacts[artifact_key]),
                (
                    _row(store.decision_notes[decision_key])
                    if decision_key
                    else None
                ),
            )
            for _, _, run_key, artifact_key, decision_key in sorted(
                page_keys,
                reverse=True,
            )
        ]

    selected_run_ids = {
        run_id
        for run, _, _ in selected
        if (run_id := text(run.get("id"))) is not None
    }
    with store.conversation_message_lock:
        latest_message_by_run: dict[
            str,
            tuple[datetime, str, object],
        ] = {}
        for message in store.messages.get(conversation_id, []):
            if _field(message, "role") != "assistant":
                continue
            message_id = text(_field(message, "id"))
            if message_id is None:
                continue
            metadata = _record_metadata(message)
            referenced_run_ids = {
                run_id
                for key in ("result_run_id", "latest_run_id")
                if (
                    run_id := text(metadata.get(key))
                ) is not None
                and run_id in selected_run_ids
            }
            candidate = (_record_activity(message), message_id, message)
            for run_id in referenced_run_ids:
                current = latest_message_by_run.get(run_id)
                if current is None or candidate[:2] > current[:2]:
                    latest_message_by_run[run_id] = candidate
        messages_by_run = {
            run_id: [_row(candidate[2])]
            for run_id, candidate in latest_message_by_run.items()
        }

    return RunDossierSourcePage(
        rows=tuple(
            RunDossierSourceRow(
                run=dict(run),
                artifact=dict(artifact),
                decision=dict(decision) if decision is not None else None,
                result_message_id=result_message_id_for(
                    run,
                    messages_by_run.get(text(run.get("id")) or "", []),
                ),
            )
            for run, artifact, decision in selected
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


def _field(value: object, key: str, default: object = None) -> object:
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _record_activity(value: object) -> datetime:
    for key in ("completed_at", "updated_at", "created_at"):
        candidate = _field(value, key)
        if isinstance(candidate, datetime) and candidate.tzinfo is not None:
            return candidate
        if isinstance(candidate, str):
            try:
                parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            except ValueError:
                continue
            if parsed.tzinfo is not None:
                return parsed
    return datetime.min.replace(tzinfo=timezone.utc)


def _record_metadata(message: object) -> Mapping[str, Any]:
    metadata = _field(message, "metadata")
    return metadata if isinstance(metadata, Mapping) else {}
