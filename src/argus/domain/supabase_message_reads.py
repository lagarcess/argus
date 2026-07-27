"""Bounded, owner-scoped Supabase reads for persisted conversation messages."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable
from uuid import UUID

from argus.api.chat.legacy_onboarding_markers import (
    _LEGACY_GOAL_PREFIX,
    _LEGACY_SKIP_MARKER,
)
from argus.api.schemas import BacktestRun, Message
from argus.domain.backtest_message_projection import (
    completed_backtest_job_ids,
    completed_backtest_run_ids,
    hydrate_completed_backtest_job_messages,
)
from argus.domain.postgres_keyset_reader import PostgresKeysetReader
from supabase import Client

_MESSAGE_SELECT = "id,conversation_id,role,content,metadata,created_at"
_OWNED_MESSAGE_SELECT = f"{_MESSAGE_SELECT},user_id"
_COMPLETED_RESULT_BATCH_SIZE = 100


class MessageCursorError(ValueError):
    """Raised when a message cursor cannot be applied safely."""


def _truthy_metadata_filter(field: str) -> str:
    return (
        f"and(metadata->>{field}.neq.,"
        f"metadata->{field}.neq.{{}},"
        f"metadata->{field}.neq.[],"
        f"metadata->{field}.neq.false,"
        f"metadata->{field}.neq.0)"
    )


_RELOAD_ARTIFACT_FILTER = ",".join(
    (
        _truthy_metadata_filter("active_confirmation_reference"),
        _truthy_metadata_filter("backtest_job"),
        _truthy_metadata_filter("backtest_job_id"),
        _truthy_metadata_filter("confirmation_card"),
        _truthy_metadata_filter("confirmation_payload"),
        _truthy_metadata_filter("latest_run_id"),
        _truthy_metadata_filter("result_card"),
        _truthy_metadata_filter("result_run_id"),
        'metadata->artifact_references.cs.[{"artifact_kind":"confirmation"}]',
        'metadata->artifact_references.cs.[{"artifact_kind":"result"}]',
        'metadata->artifact_references.cs.[{"artifact_kind":"backtest_result"}]',
        'metadata->artifact_references.cs.[{"artifact_kind":"backtest_job"}]',
    )
)
_LIFECYCLE_ARTIFACT_FILTER = ",".join(
    (
        _truthy_metadata_filter("backtest_job"),
        _truthy_metadata_filter("confirmation_card"),
        _truthy_metadata_filter("latest_run_id"),
        _truthy_metadata_filter("result_card"),
    )
)
_LEGACY_ONBOARDING_GOAL_LIKE = (
    _LEGACY_GOAL_PREFIX.replace("_", r"\_").replace("%", r"\%") + "*"
)


def _distinct_chunks(values: list[str], *, size: int) -> list[list[str]]:
    distinct = list(dict.fromkeys(values))
    return [distinct[start : start + size] for start in range(0, len(distinct), size)]


def _range_query(query: Any) -> Callable[[int, int], Any]:
    return lambda start, end: query.range(start, end)


def _unique_owned_rows_by_id(
    rows: list[dict[str, Any]],
    *,
    requested_ids: set[str],
    user_id: str,
    conversation_id: str,
) -> dict[str, dict[str, Any]]:
    candidates: dict[str, list[dict[str, Any]]] = {}
    for raw_row in rows:
        row = dict(raw_row)
        candidate_id = str(row.get("id") or "").strip()
        if candidate_id not in requested_ids:
            continue
        candidates.setdefault(candidate_id, []).append(row)
    return {
        candidate_id: matches[0]
        for candidate_id, matches in candidates.items()
        if len(matches) == 1
        and matches[0].get("user_id") == user_id
        and matches[0].get("conversation_id") == conversation_id
    }


def _visible_runtime_failure_request_id(message: Message) -> str | None:
    if message.role != "assistant" or not isinstance(message.metadata, dict):
        return None
    metadata = message.metadata
    if metadata.get("agent_runtime_stage_outcome") != "agent_runtime_failure":
        return None
    recovery = metadata.get("recovery")
    if not (
        metadata.get("conversation_mode") == "recovery"
        or (
            isinstance(recovery, dict)
            and recovery.get("code") in {"runtime_failure", "agent_runtime_failure"}
        )
    ):
        return None
    runtime_turn = metadata.get("agent_runtime_turn")
    if not isinstance(runtime_turn, dict):
        return None
    request_id = runtime_turn.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        return None
    return request_id.strip()


class SupabaseMessageReadMixin:
    """Message pages, projection witnesses, and result-card message reads."""

    client: Client
    keyset_reader: PostgresKeysetReader | None

    if TYPE_CHECKING:

        def _fetch_all_rows(
            self,
            query_factory: Callable[[int, int], Any],
        ) -> list[dict[str, Any]]: ...

        def get_backtest_jobs_by_ids(
            self,
            *,
            user_id: str,
            conversation_id: str,
            job_ids: list[str],
        ) -> dict[str, dict[str, Any]]: ...

        def get_backtest_runs_by_ids(
            self,
            *,
            user_id: str,
            conversation_id: str,
            run_ids: list[str],
        ) -> dict[str, BacktestRun]: ...

    def conversation_has_user_message(
        self,
        *,
        user_id: str,
        conversation_id: str,
    ) -> bool:
        result = (
            self.client.table("messages")
            .select("id")
            .eq("user_id", user_id)
            .eq("conversation_id", conversation_id)
            .eq("role", "user")
            .limit(1)
            .execute()
        )
        return bool(result.data)

    def list_messages(
        self,
        *,
        user_id: str,
        conversation_id: str,
        limit: int | None,
        cursor_created_at: datetime | None = None,
        cursor_id: str | None = None,
        page: bool = False,
    ) -> list[Message]:
        if (cursor_created_at is None) != (cursor_id is None):
            raise MessageCursorError("invalid message cursor")
        if cursor_id is not None:
            try:
                normalized_cursor_id = str(UUID(cursor_id))
            except (AttributeError, TypeError, ValueError):
                raise MessageCursorError("invalid message cursor") from None
            if normalized_cursor_id != cursor_id:
                raise MessageCursorError("invalid message cursor")
        if page and limit is None:
            raise ValueError("Message pages require a finite limit.")
        if not page and cursor_created_at is not None:
            raise ValueError("Message cursors are only valid for page reads.")

        if page and self.keyset_reader is not None:
            assert limit is not None
            keyset_rows = self.keyset_reader.list_message_rows(
                user_id=user_id,
                conversation_id=conversation_id,
                limit=limit,
                cursor_created_at=cursor_created_at,
                cursor_id=cursor_id,
            )
            messages = [Message.model_validate(row) for row in keyset_rows]
        else:
            query = (
                self.client.table("messages")
                .select(_MESSAGE_SELECT)
                .eq("user_id", user_id)
                .eq("conversation_id", conversation_id)
            )
            if page:
                query = query.or_(
                    r"role.neq.user,"
                    f"and(content.neq.{_LEGACY_SKIP_MARKER},"
                    f"content.not.like.{_LEGACY_ONBOARDING_GOAL_LIKE})"
                )
                if cursor_created_at is not None and cursor_id is not None:
                    timestamp = cursor_created_at.isoformat()
                    query = query.or_(
                        f"created_at.gt.{timestamp},"
                        f"and(created_at.eq.{timestamp},id.gt.{cursor_id})"
                    )
            ordered = query.order("created_at", desc=False).order("id", desc=False)
            rows_data: list[Any]
            if page:
                assert limit is not None
                rows_data = ordered.limit(limit + 1).execute().data or []
            elif limit is None:
                rows_data = self._fetch_all_rows(
                    lambda start, end: ordered.range(start, end)
                )
            else:
                rows_data = ordered.limit(limit).execute().data or []
            messages = [Message.model_validate(row) for row in rows_data]
        jobs_by_id = self.get_backtest_jobs_by_ids(
            user_id=user_id,
            conversation_id=conversation_id,
            job_ids=completed_backtest_job_ids(messages),
        )
        runs_by_id = self.get_backtest_runs_by_ids(
            user_id=user_id,
            conversation_id=conversation_id,
            run_ids=completed_backtest_run_ids(
                messages,
                jobs_by_id=jobs_by_id,
            ),
        )
        return hydrate_completed_backtest_job_messages(
            messages,
            jobs_by_id=jobs_by_id,
            runs_by_id=runs_by_id,
        )

    def list_message_page_context(
        self,
        *,
        user_id: str,
        conversation_id: str,
        page_messages: list[Message],
    ) -> tuple[list[Message], set[str]]:
        """Return bounded later-work witnesses needed by read-time projection."""

        if not page_messages:
            return [], set()
        last = max(page_messages, key=lambda message: (message.created_at, message.id))
        timestamp = last.created_at.isoformat()
        keyset_filter = (
            f"created_at.gt.{timestamp},"
            f"and(created_at.eq.{timestamp},id.gt.{last.id})"
        )

        def first_later(query: Any) -> Message | None:
            rows = (
                query.or_(keyset_filter)
                .order("created_at", desc=False)
                .order("id", desc=False)
                .limit(1)
                .execute()
                .data
                or []
            )
            return Message.model_validate(rows[0]) if rows else None

        def base_query() -> Any:
            return (
                self.client.table("messages")
                .select(_MESSAGE_SELECT)
                .eq("user_id", user_id)
                .eq("conversation_id", conversation_id)
            )

        witnesses: dict[str, Message] = {}
        later_user = first_later(
            base_query()
            .eq("role", "user")
            .neq("content", _LEGACY_SKIP_MARKER)
            .not_.like("content", _LEGACY_ONBOARDING_GOAL_LIKE)
        )
        if later_user is not None:
            witnesses[later_user.id] = later_user

        reload_artifact = first_later(
            base_query().eq("role", "assistant").or_(_RELOAD_ARTIFACT_FILTER)
        )
        if reload_artifact is not None:
            witnesses[reload_artifact.id] = reload_artifact

        lifecycle_artifact = first_later(
            base_query().eq("role", "assistant").or_(_LIFECYCLE_ARTIFACT_FILTER)
        )
        if lifecycle_artifact is not None:
            witnesses[lifecycle_artifact.id] = lifecycle_artifact

        request_ids = {
            request_id
            for message in page_messages
            if (request_id := _visible_runtime_failure_request_id(message)) is not None
        }
        for request_id in sorted(request_ids):
            matching_artifact = first_later(
                base_query()
                .eq("role", "assistant")
                .eq(
                    "metadata->agent_runtime_turn->>request_id",
                    request_id,
                )
                .or_(_RELOAD_ARTIFACT_FILTER)
            )
            if matching_artifact is not None:
                witnesses[matching_artifact.id] = matching_artifact

        action_message_ids = {
            message.id
            for message in page_messages
            if message.role == "user"
            and isinstance(message.metadata, dict)
            and isinstance(message.metadata.get("chat_action"), dict)
            and message.metadata["chat_action"].get("type") == "run_backtest"
        }
        represented_request_ids: set[str] = set()
        for message_id in sorted(action_message_ids):
            representation = first_later(
                base_query()
                .eq("role", "assistant")
                .eq(
                    "metadata->backtest_job->>request_message_id",
                    message_id,
                )
            )
            if representation is None:
                continue
            represented_request_ids.add(message_id)
            witnesses[representation.id] = representation

        return (
            sorted(
                witnesses.values(),
                key=lambda message: (message.created_at, message.id),
            ),
            represented_request_ids,
        )

    def _decision_result_messages(
        self,
        *,
        user_id: str,
        conversation_id: str,
        run: BacktestRun,
        evidence_artifact_id: str,
        enriched_card: dict[str, Any],
    ) -> list[Message]:
        def messages_equal_to(path: str, value: str) -> list[dict[str, Any]]:
            ordered = (
                self.client.table("messages")
                .select(_OWNED_MESSAGE_SELECT)
                .eq("user_id", user_id)
                .eq("conversation_id", conversation_id)
                .eq(path, value)
                .order("created_at", desc=False)
                .order("id", desc=False)
            )
            return self._fetch_all_rows(lambda start, end: ordered.range(start, end))

        candidate_rows = [
            *messages_equal_to("metadata->>result_run_id", run.id),
            *messages_equal_to("metadata->>latest_run_id", run.id),
            *messages_equal_to(
                "metadata->result_card->>evidence_artifact_id",
                evidence_artifact_id,
            ),
        ]

        ordered_jobs = (
            self.client.table("backtest_jobs")
            .select("*")
            .eq("user_id", user_id)
            .eq("conversation_id", conversation_id)
            .eq("status", "succeeded")
            .eq("result_run_id", run.id)
            .order("id", desc=False)
        )
        job_rows = self._fetch_all_rows(lambda start, end: ordered_jobs.range(start, end))
        job_ids = {
            str(row.get("id") or "").strip()
            for row in job_rows
            if row.get("id") is not None
        }
        jobs_by_id = _unique_owned_rows_by_id(
            job_rows,
            requested_ids=job_ids,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        jobs_by_id = {
            job_id: job
            for job_id, job in jobs_by_id.items()
            if job.get("status") == "succeeded"
            and str(job.get("result_run_id") or "").strip() == run.id
        }

        for requested in _distinct_chunks(
            list(jobs_by_id),
            size=_COMPLETED_RESULT_BATCH_SIZE,
        ):
            for path in (
                "metadata->>backtest_job_id",
                "metadata->backtest_job->>id",
            ):
                ordered_aliases = (
                    self.client.table("messages")
                    .select(_OWNED_MESSAGE_SELECT)
                    .eq("user_id", user_id)
                    .eq("conversation_id", conversation_id)
                    .in_(path, requested)
                    .order("created_at", desc=False)
                    .order("id", desc=False)
                )
                candidate_rows.extend(self._fetch_all_rows(_range_query(ordered_aliases)))

        messages_by_id: dict[str, Message] = {}
        for row in candidate_rows:
            if (
                row.get("user_id") != user_id
                or row.get("conversation_id") != conversation_id
            ):
                continue
            message = Message.model_validate(row)
            messages_by_id.setdefault(message.id, message)

        enriched_run = run.model_copy(update={"conversation_result_card": enriched_card})
        return hydrate_completed_backtest_job_messages(
            list(messages_by_id.values()),
            jobs_by_id=jobs_by_id,
            runs_by_id={run.id: enriched_run},
        )
