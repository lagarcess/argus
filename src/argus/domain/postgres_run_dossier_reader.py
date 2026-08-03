from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

_ACQUIRE_TIMEOUT_SECONDS = 2.0


class RunDossierCursorError(ValueError):
    """Raised when a dossier cursor no longer names an eligible owned run."""


@dataclass(frozen=True)
class RunDossierSourceRow:
    run: dict[str, Any]
    artifact: dict[str, Any]
    decision: dict[str, Any] | None
    result_message_id: str | None


@dataclass(frozen=True)
class RunDossierSourcePage:
    rows: tuple[RunDossierSourceRow, ...]
    total_runs: int
    decided_runs: int


_CURSOR_PIVOT_SQL = """
select coalesce(br.updated_at, br.created_at) as completed_at
from public.backtest_runs as br
where br.user_id = %(user_id)s
  and br.conversation_id = %(conversation_id)s
  and br.id = %(cursor_run_id)s
  and br.status = 'completed'
  and exists (
      select 1
      from public.evidence_artifacts as evidence
      where evidence.user_id = %(user_id)s
        and evidence.source_conversation_id = %(conversation_id)s
        and evidence.source_run_id = br.id
  )
limit 1
"""


_COUNTS_SQL = """
select
    count(*)::integer as total_runs,
    count(decision.id)::integer as decided_runs
from public.backtest_runs as br
join lateral (
    select evidence.id
    from public.evidence_artifacts as evidence
    where evidence.user_id = %(user_id)s
      and evidence.source_conversation_id = %(conversation_id)s
      and evidence.source_run_id = br.id
    order by evidence.updated_at desc, evidence.id desc
    limit 1
) as artifact on true
left join lateral (
    select current_decision.id
    from public.decision_notes as current_decision
    where current_decision.user_id = %(user_id)s
      and current_decision.source_conversation_id = %(conversation_id)s
      and current_decision.evidence_artifact_id = artifact.id
    order by current_decision.updated_at desc, current_decision.id desc
    limit 1
) as decision on true
where br.user_id = %(user_id)s
  and br.conversation_id = %(conversation_id)s
  and br.status = 'completed'
"""


_PAGE_SQL = """
select
    jsonb_build_object(
        'id', br.id,
        'conversation_id', br.conversation_id,
        'status', br.status,
        'asset_class', br.asset_class,
        'symbols', br.symbols,
        'benchmark_symbol', br.benchmark_symbol,
        'config_snapshot', br.config_snapshot,
        'conversation_result_card', br.conversation_result_card,
        'created_at', br.created_at,
        'updated_at', br.updated_at,
        'completed_at', coalesce(br.updated_at, br.created_at)
    ) as run_payload,
    artifact.payload as artifact_payload,
    decision.payload as decision_payload,
    result_message.id::text as result_message_id
from public.backtest_runs as br
join lateral (
    select jsonb_build_object(
        'id', evidence.id,
        'idea_id', evidence.idea_id,
        'idea_version_id', evidence.idea_version_id,
        'source_conversation_id', evidence.source_conversation_id,
        'source_run_id', evidence.source_run_id,
        'artifact_type', evidence.artifact_type,
        'lifecycle', evidence.lifecycle,
        'title', evidence.title,
        'digest', evidence.digest,
        'payload', evidence.payload,
        'created_at', evidence.created_at,
        'updated_at', evidence.updated_at
    ) as payload,
    evidence.id
    from public.evidence_artifacts as evidence
    where evidence.user_id = %(user_id)s
      and evidence.source_conversation_id = %(conversation_id)s
      and evidence.source_run_id = br.id
    order by evidence.updated_at desc, evidence.id desc
    limit 1
) as artifact on true
left join lateral (
    select jsonb_build_object(
        'id', current_decision.id,
        'idea_id', current_decision.idea_id,
        'idea_version_id', current_decision.idea_version_id,
        'evidence_artifact_id', current_decision.evidence_artifact_id,
        'source_conversation_id', current_decision.source_conversation_id,
        'decision_state', current_decision.decision_state,
        'note', current_decision.note,
        'created_at', current_decision.created_at,
        'updated_at', current_decision.updated_at
    ) as payload
    from public.decision_notes as current_decision
    where current_decision.user_id = %(user_id)s
      and current_decision.source_conversation_id = %(conversation_id)s
      and current_decision.evidence_artifact_id = artifact.id
    order by current_decision.updated_at desc, current_decision.id desc
    limit 1
) as decision on true
left join lateral (
    select message.id
    from public.messages as message
    where message.user_id = %(user_id)s
      and message.conversation_id = %(conversation_id)s
      and message.role = 'assistant'
      and (
          message.metadata->>'result_run_id' = br.id::text
          or message.metadata->>'latest_run_id' = br.id::text
      )
    order by
        case
            when jsonb_typeof(message.metadata->'result_card') = 'object'
             and message.metadata->'result_card' <> '{}'::jsonb
                then 0
            else 1
        end,
        message.created_at desc,
        message.id desc
    limit 1
) as result_message on true
where br.user_id = %(user_id)s
  and br.conversation_id = %(conversation_id)s
  and br.status = 'completed'
  and (
      %(cursor_completed_at)s::timestamptz is null
      or row(coalesce(br.updated_at, br.created_at), br.id)
         < row(
             %(cursor_completed_at)s::timestamptz,
             %(cursor_run_id)s::uuid
         )
  )
order by coalesce(br.updated_at, br.created_at) desc, br.id desc
limit %(limit)s
"""


@dataclass(frozen=True)
class PostgresRunDossierReader:
    pool: Any

    def list_source_rows(
        self,
        *,
        user_id: str,
        conversation_id: str,
        limit: int,
        cursor_completed_at: datetime | None,
        cursor_run_id: str | None,
    ) -> RunDossierSourcePage:
        if limit < 1:
            raise ValueError("Run dossier source limit must be positive.")
        try:
            owner_id = UUID(user_id)
            owned_conversation_id = UUID(conversation_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Run dossier owner and conversation ids must be UUIDs.") from exc

        has_cursor = cursor_completed_at is not None or cursor_run_id is not None
        if has_cursor and (
            cursor_completed_at is None
            or cursor_run_id is None
            or cursor_completed_at.tzinfo is None
            or cursor_completed_at.utcoffset() is None
        ):
            raise RunDossierCursorError("Run dossier cursor is incomplete.")
        cursor_run_uuid: UUID | None = None
        if cursor_run_id is not None:
            try:
                cursor_run_uuid = UUID(cursor_run_id)
            except (TypeError, ValueError) as exc:
                raise RunDossierCursorError("Run dossier cursor id is invalid.") from exc
            if str(cursor_run_uuid) != cursor_run_id:
                raise RunDossierCursorError("Run dossier cursor id is not canonical.")

        params = {
            "user_id": owner_id,
            "conversation_id": owned_conversation_id,
            "cursor_completed_at": cursor_completed_at,
            "cursor_run_id": cursor_run_uuid,
            "limit": limit,
        }
        with self.pool.connection(timeout=_ACQUIRE_TIMEOUT_SECONDS) as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                if cursor_completed_at is not None:
                    cursor.execute(_CURSOR_PIVOT_SQL, params)
                    pivots = cursor.fetchall()
                    if len(pivots) != 1 or pivots[0].get(
                        "completed_at"
                    ) != cursor_completed_at:
                        raise RunDossierCursorError(
                            "Run dossier cursor pivot is not eligible."
                        )

                cursor.execute(_COUNTS_SQL, params)
                count_rows = cursor.fetchall()
                counts = count_rows[0] if count_rows else {}

                cursor.execute(_PAGE_SQL, params)
                source_rows = cursor.fetchall()

        rows = tuple(
            RunDossierSourceRow(
                run=dict(row["run_payload"]),
                artifact=dict(row["artifact_payload"]),
                decision=(
                    dict(row["decision_payload"])
                    if isinstance(row.get("decision_payload"), dict)
                    else None
                ),
                result_message_id=(
                    str(row["result_message_id"])
                    if row.get("result_message_id") is not None
                    else None
                ),
            )
            for row in source_rows
            if isinstance(row.get("run_payload"), dict)
            and isinstance(row.get("artifact_payload"), dict)
        )
        return RunDossierSourcePage(
            rows=rows,
            total_runs=int(counts.get("total_runs") or 0),
            decided_runs=int(counts.get("decided_runs") or 0),
        )
