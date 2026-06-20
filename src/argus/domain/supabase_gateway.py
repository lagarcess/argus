from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import httpx

from argus.api.chat.previews import plain_text_preview
from argus.api.schemas import (
    BacktestRun,
    Collection,
    Conversation,
    DecisionNote,
    EvidenceArtifact,
    Idea,
    IdeaVersion,
    Message,
    OnboardingState,
    Strategy,
    User,
)
from argus.domain.evidence import CapturedEvidence, attach_decision_to_result_card
from argus.domain.store import utcnow
from supabase import Client, ClientOptions, create_client


class QuotaExceededError(Exception):
    pass


_USAGE_COUNTER_LOCK = threading.Lock()


def _now_iso() -> str:
    return utcnow().isoformat()


def _align_period(dt: datetime, period: str) -> tuple[datetime, datetime]:
    if period == "minute":
        start = dt.replace(second=0, microsecond=0)
        end = start + timedelta(minutes=1)
    elif period == "hour":
        start = dt.replace(minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=1)
    else:  # day
        start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    return start, end


def _row_one(result: Any) -> dict[str, Any] | None:
    data = getattr(result, "data", None)
    if not data:
        return None
    if isinstance(data, list):
        return data[0] if data else None
    return data


def _message_preview(content: str, max_length: int = 180) -> str | None:
    return plain_text_preview(content, max_length=max_length)


def _filter_history_runs_by_conversation_state(
    runs: list[dict[str, Any]],
    conversations: list[dict[str, Any]],
    *,
    archived: bool,
    deleted: bool,
) -> list[dict[str, Any]]:
    conversations_by_id = {
        str(row["id"]): row for row in conversations if row.get("id") is not None
    }
    include_orphan_runs = not archived and not deleted
    filtered: list[dict[str, Any]] = []

    for run in runs:
        conversation_id = run.get("conversation_id")
        if conversation_id is None:
            if include_orphan_runs:
                filtered.append(run)
            continue
        conversation = conversations_by_id.get(str(conversation_id))
        if conversation is None:
            if include_orphan_runs:
                filtered.append(run)
            continue
        deleted_matches = (
            conversation.get("deleted_at") is not None
            if deleted
            else conversation.get("deleted_at") is None
        )
        if deleted_matches and bool(conversation.get("archived", False)) == archived:
            filtered.append(run)

    return filtered


def _filter_history_conversations_by_message_state(
    conversations: list[dict[str, Any]],
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    conversation_ids_with_messages = {
        str(row["conversation_id"])
        for row in messages
        if row.get("conversation_id") is not None
    }
    return [
        row
        for row in conversations
        if row.get("id") is not None and str(row["id"]) in conversation_ids_with_messages
    ]


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _supabase_client_options() -> ClientOptions:
    return ClientOptions(
        httpx_client=httpx.Client(http2=False, timeout=120),
        postgrest_client_timeout=120,
    )


@dataclass
class SupabaseGateway:
    client: Client
    auth_client: Client | None = None
    mock_user_email: str | None = os.getenv("MOCK_USER_EMAIL")
    mock_user_password: str | None = os.getenv("MOCK_USER_PASSWORD")
    _cached_mock_user: User | None = None

    @classmethod
    def from_env(cls) -> SupabaseGateway:
        url = os.getenv("SUPABASE_URL") or os.getenv("SUPABASE_PROJECT_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise RuntimeError(
                "Supabase mode requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
            )
        auth_key = (
            os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_PUBLIC_KEY") or key
        )
        return cls(
            client=create_client(url, key, options=_supabase_client_options()),
            auth_client=create_client(
                url,
                auth_key,
                options=_supabase_client_options(),
            ),
        )

    def new_id(self) -> str:
        return str(uuid4())

    def _fetch_all_rows(
        self,
        query_factory: Callable[[int, int], Any],
        *,
        batch_size: int = 500,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        start = 0
        while True:
            response = query_factory(start, start + batch_size - 1).execute()
            data = response.data or []
            rows.extend(data)
            if len(data) < batch_size:
                break
            start += batch_size
        return rows

    def reset_dev_data(self) -> None:
        user = self.get_or_create_mock_user()
        user_id = user.id
        for table in (
            "feedback",
            "usage_counters",
            "collection_strategies",
            "decision_notes",
            "evidence_artifacts",
            "idea_versions",
            "ideas",
            "backtest_runs",
            "messages",
            "strategies",
            "collections",
            "conversations",
        ):
            self.client.table(table).delete().eq("user_id", user_id).execute()

    def get_or_create_mock_user(self) -> User:
        if self._cached_mock_user is not None:
            return self._cached_mock_user
        user_id: str | None = None
        try:
            created = self.client.auth.admin.create_user(
                {
                    "email": self.mock_user_email,
                    "password": self.mock_user_password,
                    "email_confirm": True,
                }
            )
            user_id = created.user.id if created and created.user else None
        except Exception:
            try:
                listed_raw = self.client.auth.admin.list_users(page=1, per_page=200)
                if isinstance(listed_raw, list):
                    listed = listed_raw
                else:
                    listed = getattr(listed_raw, "users", []) or getattr(
                        listed_raw, "data", []
                    )
                existing = next(
                    (
                        row
                        for row in listed
                        if getattr(row, "email", None) == self.mock_user_email
                    ),
                    None,
                )
                if existing is not None:
                    user_id = existing.id
            except Exception:
                pass

        if user_id is None:
            existing_profile = (
                self.client.table("profiles")
                .select("id")
                .eq("email", self.mock_user_email)
                .limit(1)
                .execute()
                .data
                or []
            )
            if existing_profile:
                user_id = existing_profile[0]["id"]

        if user_id is None:
            raise RuntimeError("Unable to resolve mock auth user.")

        existing = (
            self.client.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        )
        existing_row = _row_one(existing)
        if existing_row is not None:
            user = User.model_validate(existing_row)
            self._cached_mock_user = user
            return user

        now = _now_iso()
        profile = {
            "id": user_id,
            "email": self.mock_user_email,
            "username": "mock-developer",
            "display_name": "Mock Developer",
            "language": "en",
            "locale": "en-US",
            "theme": "dark",
            "is_admin": True,
            "onboarding": OnboardingState().model_dump(),
            "updated_at": now,
        }
        self.client.table("profiles").upsert(profile, on_conflict="id").execute()
        loaded = (
            self.client.table("profiles").select("*").eq("id", user_id).single().execute()
        )
        user = User.model_validate(_row_one(loaded))
        self._cached_mock_user = user
        return user

    def signup(
        self,
        email: str,
        password: str,
        display_name: str | None = None,
        username: str | None = None,
    ) -> dict[str, Any]:
        try:
            auth_client = self.auth_client or self.client
            response = auth_client.auth.sign_up(
                {
                    "email": email,
                    "password": password,
                    "options": {
                        "data": {"display_name": display_name, "username": username}
                    },
                }
            )
            if not response.user:
                raise RuntimeError("Signup failed: No user returned.")
            return response.model_dump(mode="json")
        except Exception as e:
            raise RuntimeError(f"Signup failed: {e}") from e

    def private_alpha_role_for_email(self, email: str) -> str | None:
        rows = (
            self.client.table("private_alpha_allowlist")
            .select("email,role,disabled_at")
            .eq("email", _normalize_email(email))
            .limit(1)
            .execute()
        )
        row = _row_one(rows)
        if not row or row.get("disabled_at") is not None:
            return None
        role = str(row.get("role") or "user").strip().lower()
        return role if role in {"admin", "developer", "user"} else "user"

    def private_alpha_email_allowed(self, email: str) -> bool:
        return self.private_alpha_role_for_email(email) is not None

    def login(self, email: str, password: str) -> dict[str, Any]:
        try:
            auth_client = self.auth_client or self.client
            response = auth_client.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
            if not response.session:
                raise RuntimeError("Login failed: No session returned.")
            return response.model_dump(mode="json")
        except Exception as e:
            raise RuntimeError(f"Login failed: {e}") from e

    def update_user(self, user_id: str, updates: dict[str, Any]) -> User:
        updates["updated_at"] = _now_iso()
        self.client.table("profiles").upsert(updates, on_conflict="id").execute()
        loaded = (
            self.client.table("profiles").select("*").eq("id", user_id).single().execute()
        )
        return User.model_validate(_row_one(loaded))

    def get_user(self, *, user_id: str) -> User | None:
        rows = (
            self.client.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        )
        row = _row_one(rows)
        return User.model_validate(row) if row else None

    def create_conversation(
        self, *, user_id: str, title: str, title_source: str, language: str | None
    ) -> Conversation:
        now = _now_iso()
        payload = {
            "user_id": user_id,
            "title": title,
            "title_source": title_source,
            "language": language,
            "created_at": now,
            "updated_at": now,
            "pinned": False,
            "archived": False,
        }
        created = self.client.table("conversations").insert(payload).execute()
        return Conversation.model_validate(_row_one(created))

    def list_conversations(
        self,
        *,
        user_id: str,
        limit: int | None,
        archived: bool | None = None,
        deleted: bool = False,
    ) -> list[Conversation]:
        query = self.client.table("conversations").select("*").eq("user_id", user_id)
        if deleted:
            query = query.not_.is_("deleted_at", "null")
        else:
            query = query.is_("deleted_at", "null")

        if archived is not None:
            query = query.eq("archived", archived)

        ordered = query.order("pinned", desc=True).order("updated_at", desc=True)
        if limit is None:
            rows_data = self._fetch_all_rows(lambda start, end: ordered.range(start, end))
        else:
            rows_data = ordered.limit(limit).execute().data or []
        return [Conversation.model_validate(row) for row in rows_data]

    def get_conversation(
        self, *, user_id: str, conversation_id: str
    ) -> Conversation | None:
        rows = (
            self.client.table("conversations")
            .select("*")
            .eq("user_id", user_id)
            .eq("id", conversation_id)
            .limit(1)
            .execute()
        )
        row = _row_one(rows)
        return Conversation.model_validate(row) if row else None

    def patch_conversation(
        self, *, user_id: str, conversation_id: str, patch: dict[str, Any]
    ) -> Conversation | None:
        patch["updated_at"] = _now_iso()
        self.client.table("conversations").update(patch).eq("id", conversation_id).eq(
            "user_id", user_id
        ).execute()
        return self.get_conversation(user_id=user_id, conversation_id=conversation_id)

    def soft_delete_conversation(self, *, user_id: str, conversation_id: str) -> bool:
        now = _now_iso()
        result = (
            self.client.table("conversations")
            .update({"deleted_at": now, "updated_at": now})
            .eq("id", conversation_id)
            .eq("user_id", user_id)
            .execute()
        )
        return bool(result.data)

    def soft_delete_all_conversations(self, *, user_id: str) -> int:
        now = _now_iso()
        result = (
            self.client.table("conversations")
            .update({"deleted_at": now, "updated_at": now})
            .eq("user_id", user_id)
            .is_("deleted_at", "null")
            .execute()
        )
        return len(result.data or [])

    def list_messages(
        self, *, user_id: str, conversation_id: str, limit: int | None
    ) -> list[Message]:
        query = (
            self.client.table("messages")
            .select("id,conversation_id,role,content,metadata,created_at")
            .eq("user_id", user_id)
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=False)
        )
        if limit is None:
            rows_data = self._fetch_all_rows(lambda start, end: query.range(start, end))
        else:
            rows_data = query.limit(limit).execute().data or []
        return [Message.model_validate(row) for row in rows_data]

    def create_message(
        self,
        *,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        conversation = self.get_conversation(
            user_id=user_id, conversation_id=conversation_id
        )
        if not conversation:
            raise ValueError("Conversation not found or not owned by user.")
        payload = {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "metadata": metadata if metadata is not None else {},
            "created_at": _now_iso(),
        }
        created = self.client.table("messages").insert(payload).execute()
        preview = _message_preview(content)
        if preview:
            self.client.table("conversations").update(
                {"last_message_preview": preview, "updated_at": _now_iso()}
            ).eq("id", conversation_id).eq("user_id", user_id).execute()
        return Message.model_validate(_row_one(created))

    def create_backtest_run(self, *, user_id: str, run: BacktestRun) -> BacktestRun:
        self._require_owned_conversation(
            user_id=user_id,
            conversation_id=run.conversation_id,
        )
        self._require_owned_strategy(
            user_id=user_id,
            strategy_id=run.strategy_id,
        )
        payload = run.model_dump(mode="json")
        payload["user_id"] = user_id
        created = self.client.table("backtest_runs").insert(payload).execute()
        return BacktestRun.model_validate(_row_one(created))

    def update_backtest_run_result_card(
        self,
        *,
        user_id: str,
        run_id: str,
        conversation_result_card: dict[str, Any],
    ) -> BacktestRun:
        self._require_owned_backtest_run_if_present(user_id=user_id, run_id=run_id)
        updated = (
            self.client.table("backtest_runs")
            .update(
                {
                    "conversation_result_card": conversation_result_card,
                }
            )
            .eq("user_id", user_id)
            .eq("id", run_id)
            .execute()
        )
        return BacktestRun.model_validate(_row_one(updated))

    def mark_result_card_decision_for_run(
        self,
        *,
        user_id: str,
        run_id: str,
        evidence_artifact_id: str,
        decision_id: str,
        decision_state: str,
    ) -> None:
        run = self.get_backtest_run(user_id=user_id, run_id=run_id)
        if run is None:
            raise ValueError("Backtest run not found or not owned by user.")
        enriched_card = attach_decision_to_result_card(
            dict(run.conversation_result_card),
            decision_id=decision_id,
            decision_state=decision_state,  # type: ignore[arg-type]
        )
        self.update_backtest_run_result_card(
            user_id=user_id,
            run_id=run_id,
            conversation_result_card=enriched_card,
        )
        if not run.conversation_id:
            return
        for message in self.list_messages(
            user_id=user_id,
            conversation_id=run.conversation_id,
            limit=None,
        ):
            metadata = dict(message.metadata or {})
            result_card = metadata.get("result_card")
            if not isinstance(result_card, dict):
                continue
            is_matching_run = (
                metadata.get("result_run_id") == run_id
                or metadata.get("latest_run_id") == run_id
            )
            is_matching_artifact = (
                result_card.get("evidence_artifact_id") == evidence_artifact_id
            )
            if not is_matching_run and not is_matching_artifact:
                continue
            metadata["result_card"] = attach_decision_to_result_card(
                result_card,
                decision_id=decision_id,
                decision_state=decision_state,  # type: ignore[arg-type]
            )
            metadata["decision_note_id"] = decision_id
            metadata["decision_state"] = decision_state
            self.client.table("messages").update({"metadata": metadata}).eq(
                "user_id", user_id
            ).eq("id", message.id).execute()

    def create_idea(self, *, user_id: str, idea: Idea) -> Idea:
        self._require_owned_conversation(
            user_id=user_id,
            conversation_id=idea.source_conversation_id,
        )
        payload = idea.model_dump(mode="json")
        payload["user_id"] = user_id
        created = self.client.table("ideas").insert(payload).execute()
        return Idea.model_validate(_row_one(created))

    def update_idea_active_version(
        self, *, user_id: str, idea_id: str, active_version_id: str
    ) -> Idea:
        self._require_owned_idea(user_id=user_id, idea_id=idea_id)
        self._require_owned_idea_version(
            user_id=user_id,
            idea_version_id=active_version_id,
        )
        updated = (
            self.client.table("ideas")
            .update({"active_version_id": active_version_id, "updated_at": _now_iso()})
            .eq("user_id", user_id)
            .eq("id", idea_id)
            .execute()
        )
        return Idea.model_validate(_row_one(updated))

    def create_idea_version(self, *, user_id: str, version: IdeaVersion) -> IdeaVersion:
        self._require_owned_idea(user_id=user_id, idea_id=version.idea_id)
        self._require_owned_conversation(
            user_id=user_id,
            conversation_id=version.source_conversation_id,
        )
        self._require_owned_backtest_run_if_present(
            user_id=user_id,
            run_id=version.source_run_id,
        )
        payload = version.model_dump(mode="json")
        payload["user_id"] = user_id
        created = self.client.table("idea_versions").insert(payload).execute()
        return IdeaVersion.model_validate(_row_one(created))

    def create_evidence_artifact(
        self, *, user_id: str, artifact: EvidenceArtifact
    ) -> EvidenceArtifact:
        self._require_owned_idea(user_id=user_id, idea_id=artifact.idea_id)
        self._require_owned_idea_version(
            user_id=user_id,
            idea_version_id=artifact.idea_version_id,
        )
        self._require_owned_conversation(
            user_id=user_id,
            conversation_id=artifact.source_conversation_id,
        )
        self._require_owned_backtest_run_if_present(
            user_id=user_id,
            run_id=artifact.source_run_id,
        )
        payload = artifact.model_dump(mode="json")
        payload["user_id"] = user_id
        created = self.client.table("evidence_artifacts").insert(payload).execute()
        return EvidenceArtifact.model_validate(_row_one(created))

    def get_evidence_capture_by_run(
        self, *, user_id: str, run_id: str
    ) -> CapturedEvidence | None:
        artifact_result = (
            self.client.table("evidence_artifacts")
            .select("*")
            .eq("user_id", user_id)
            .eq("source_run_id", run_id)
            .limit(1)
            .execute()
        )
        artifact_row = _row_one(artifact_result)
        if artifact_row is None:
            return None
        artifact = EvidenceArtifact.model_validate(artifact_row)
        idea_result = (
            self.client.table("ideas")
            .select("*")
            .eq("user_id", user_id)
            .eq("id", artifact.idea_id)
            .limit(1)
            .execute()
        )
        version_result = (
            self.client.table("idea_versions")
            .select("*")
            .eq("user_id", user_id)
            .eq("id", artifact.idea_version_id)
            .limit(1)
            .execute()
        )
        idea_row = _row_one(idea_result)
        version_row = _row_one(version_result)
        if idea_row is None or version_row is None:
            raise ValueError("Evidence artifact sidecar records are incomplete.")
        return CapturedEvidence(
            idea=Idea.model_validate(idea_row),
            idea_version=IdeaVersion.model_validate(version_row),
            evidence_artifact=artifact,
        )

    def create_backtest_evidence_capture(
        self, *, user_id: str, captured: CapturedEvidence
    ) -> CapturedEvidence:
        run_id = captured.evidence_artifact.source_run_id
        if run_id is not None:
            existing = self.get_evidence_capture_by_run(user_id=user_id, run_id=run_id)
            if existing is not None:
                return existing

        idea_for_insert = captured.idea.model_copy(update={"active_version_id": None})
        idea: Idea | None = None
        version: IdeaVersion | None = None
        try:
            idea = self.create_idea(user_id=user_id, idea=idea_for_insert)
            version = self.create_idea_version(
                user_id=user_id, version=captured.idea_version
            )
            idea = self.update_idea_active_version(
                user_id=user_id,
                idea_id=idea.id,
                active_version_id=version.id,
            )
            artifact = self.create_evidence_artifact(
                user_id=user_id,
                artifact=captured.evidence_artifact,
            )
        except Exception:
            existing_after_error = None
            if run_id is not None:
                existing_after_error = self.get_evidence_capture_by_run(
                    user_id=user_id,
                    run_id=run_id,
                )
                if (
                    existing_after_error is not None
                    and idea is not None
                    and version is not None
                    and existing_after_error.idea.id == idea.id
                    and existing_after_error.idea_version.id == version.id
                ):
                    return existing_after_error
            if idea is not None:
                self._discard_transient_evidence_sidecars(
                    user_id=user_id,
                    idea_id=idea.id,
                    idea_version_id=version.id if version is not None else None,
                )
            if existing_after_error is not None:
                return existing_after_error
            if run_id is not None:
                existing = self.get_evidence_capture_by_run(
                    user_id=user_id,
                    run_id=run_id,
                )
                if existing is not None:
                    return existing
            raise
        return CapturedEvidence(
            idea=idea,
            idea_version=version,
            evidence_artifact=artifact,
        )

    def _discard_transient_evidence_sidecars(
        self,
        *,
        user_id: str,
        idea_id: str,
        idea_version_id: str | None,
    ) -> None:
        with suppress(Exception):
            self.client.table("ideas").update({"active_version_id": None}).eq(
                "user_id", user_id
            ).eq("id", idea_id).execute()
        if idea_version_id is not None:
            with suppress(Exception):
                self.client.table("idea_versions").delete().eq("user_id", user_id).eq(
                    "id", idea_version_id
                ).execute()
        with suppress(Exception):
            self.client.table("ideas").delete().eq("user_id", user_id).eq(
                "id", idea_id
            ).execute()

    def get_evidence_artifact(
        self, *, user_id: str, artifact_id: str
    ) -> EvidenceArtifact | None:
        rows = (
            self.client.table("evidence_artifacts")
            .select("*")
            .eq("user_id", user_id)
            .eq("id", artifact_id)
            .limit(1)
            .execute()
        )
        row = _row_one(rows)
        return EvidenceArtifact.model_validate(row) if row else None

    def get_decision_note_by_artifact(
        self, *, user_id: str, artifact_id: str
    ) -> DecisionNote | None:
        rows = (
            self.client.table("decision_notes")
            .select("*")
            .eq("user_id", user_id)
            .eq("evidence_artifact_id", artifact_id)
            .limit(1)
            .execute()
        )
        row = _row_one(rows)
        return DecisionNote.model_validate(row) if row else None

    def create_decision_note(
        self, *, user_id: str, decision: DecisionNote
    ) -> DecisionNote:
        self._require_owned_idea(user_id=user_id, idea_id=decision.idea_id)
        self._require_owned_idea_version(
            user_id=user_id,
            idea_version_id=decision.idea_version_id,
        )
        self._require_owned_evidence_artifact(
            user_id=user_id,
            artifact_id=decision.evidence_artifact_id,
        )
        self._require_owned_conversation(
            user_id=user_id,
            conversation_id=decision.source_conversation_id,
        )
        payload = decision.model_dump(mode="json")
        payload["user_id"] = user_id
        created = self.client.table("decision_notes").insert(payload).execute()
        return DecisionNote.model_validate(_row_one(created))

    def upsert_decision_note(
        self, *, user_id: str, decision: DecisionNote
    ) -> DecisionNote:
        existing = self.get_decision_note_by_artifact(
            user_id=user_id,
            artifact_id=decision.evidence_artifact_id,
        )
        if existing is None:
            try:
                return self.create_decision_note(user_id=user_id, decision=decision)
            except Exception:
                existing = self.get_decision_note_by_artifact(
                    user_id=user_id,
                    artifact_id=decision.evidence_artifact_id,
                )
                if existing is None:
                    raise

        updated = (
            self.client.table("decision_notes")
            .update(
                {
                    "decision_state": decision.decision_state,
                    "note": decision.note,
                    "updated_at": _now_iso(),
                }
            )
            .eq("user_id", user_id)
            .eq("id", existing.id)
            .execute()
        )
        return DecisionNote.model_validate(_row_one(updated))

    def capture_current_decision_note(
        self, *, user_id: str, decision: DecisionNote
    ) -> tuple[DecisionNote, EvidenceArtifact, Idea, IdeaVersion]:
        result = self.client.rpc(
            "upsert_current_decision_note",
            {
                "p_user_id": user_id,
                "p_evidence_artifact_id": decision.evidence_artifact_id,
                "p_decision_id": decision.id,
                "p_decision_state": decision.decision_state,
                "p_note": decision.note,
            },
        ).execute()
        row = _row_one(result)
        if row is None:
            raise ValueError("Decision capture did not return durable artifact state.")
        return (
            DecisionNote.model_validate(row["decision"]),
            EvidenceArtifact.model_validate(row["evidence_artifact"]),
            Idea.model_validate(row["idea"]),
            IdeaVersion.model_validate(row["idea_version"]),
        )

    def mark_evidence_artifact_lifecycle(
        self,
        *,
        user_id: str,
        artifact_id: str,
        lifecycle: str,
    ) -> EvidenceArtifact:
        self._require_owned_evidence_artifact(
            user_id=user_id,
            artifact_id=artifact_id,
        )
        updated = (
            self.client.table("evidence_artifacts")
            .update({"lifecycle": lifecycle, "updated_at": _now_iso()})
            .eq("user_id", user_id)
            .eq("id", artifact_id)
            .execute()
        )
        return EvidenceArtifact.model_validate(_row_one(updated))

    def create_backtest_job(
        self,
        *,
        user_id: str,
        conversation_id: str,
        payload_hash: str,
        launch_payload: dict[str, Any],
        request_message_id: str | None = None,
        confirmation_message_id: str | None = None,
        idempotency_key: str | None = None,
        execution_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        clean_idempotency_key = (
            idempotency_key.strip()
            if isinstance(idempotency_key, str) and idempotency_key.strip()
            else None
        )
        if clean_idempotency_key is not None:
            existing = (
                self.client.table("backtest_jobs")
                .select("*")
                .eq("user_id", user_id)
                .eq("idempotency_key", clean_idempotency_key)
                .limit(1)
                .execute()
            )
            existing_row = _row_one(existing)
            if existing_row is not None:
                return dict(existing_row)

        self._require_owned_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
        )

        payload = {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "request_message_id": request_message_id,
            "confirmation_message_id": confirmation_message_id,
            "idempotency_key": clean_idempotency_key,
            "payload_hash": payload_hash,
            "launch_payload": launch_payload,
            "status": "queued",
            "priority": "normal",
            "attempts": 0,
            "max_attempts": 1,
            "execution_metadata": execution_metadata or {},
        }
        created = self.client.table("backtest_jobs").insert(payload).execute()
        return dict(_row_one(created) or {})

    def get_backtest_job(self, *, user_id: str, job_id: str) -> dict[str, Any] | None:
        result = (
            self.client.table("backtest_jobs")
            .select("*")
            .eq("user_id", user_id)
            .eq("id", job_id)
            .limit(1)
            .execute()
        )
        row = _row_one(result)
        return dict(row) if row is not None else None

    def count_backtest_jobs(
        self,
        *,
        status: str,
        user_id: str | None = None,
        limit: int = 100,
    ) -> int:
        query = self.client.table("backtest_jobs").select("id").eq("status", status)
        if user_id is not None:
            query = query.eq("user_id", user_id)
        result = query.limit(max(1, limit)).execute()
        return len(result.data or [])

    def list_backtest_jobs(
        self,
        *,
        status: str,
        user_id: str | None = None,
        limit: int = 100,
        oldest_first: bool = False,
    ) -> list[dict[str, Any]]:
        query = (
            self.client.table("backtest_jobs")
            .select("*")
            .eq("status", status)
            .order("created_at", desc=not oldest_first)
        )
        if user_id is not None:
            query = query.eq("user_id", user_id)
        result = query.limit(max(1, limit)).execute()
        return [dict(row) for row in result.data or []]

    def merge_backtest_job_execution_metadata(
        self,
        *,
        user_id: str,
        job_id: str,
        execution_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        existing = self.get_backtest_job(user_id=user_id, job_id=job_id)
        if existing is None:
            raise ValueError("Backtest job not found or not owned by user.")
        metadata = dict(existing.get("execution_metadata") or {})
        metadata.update(execution_metadata)
        updated = (
            self.client.table("backtest_jobs")
            .update({"execution_metadata": metadata, "updated_at": _now_iso()})
            .eq("user_id", user_id)
            .eq("id", job_id)
            .execute()
        )
        return dict(_row_one(updated) or {})

    def link_backtest_job_result(
        self,
        *,
        user_id: str,
        job_id: str,
        result_run_id: str,
        execution_metadata: dict[str, Any] | None = None,
        mark_succeeded: bool = False,
    ) -> dict[str, Any]:
        existing = self.get_backtest_job(user_id=user_id, job_id=job_id)
        if existing is None:
            raise ValueError("Backtest job not found or not owned by user.")
        if existing.get("result_run_id"):
            return existing

        metadata = dict(existing.get("execution_metadata") or {})
        metadata.update(execution_metadata or {})
        payload: dict[str, Any] = {
            "result_run_id": result_run_id,
            "execution_metadata": metadata,
            "updated_at": _now_iso(),
        }
        if mark_succeeded:
            payload["status"] = "succeeded"
            payload["finished_at"] = _now_iso()

        updated = (
            self.client.table("backtest_jobs")
            .update(payload)
            .eq("user_id", user_id)
            .eq("id", job_id)
            .execute()
        )
        return dict(_row_one(updated) or {})

    def mark_backtest_job_running(
        self,
        *,
        user_id: str,
        job_id: str,
        execution_metadata: dict[str, Any] | None = None,
        started_at: str | None = None,
    ) -> dict[str, Any]:
        existing = self.get_backtest_job(user_id=user_id, job_id=job_id)
        if existing is None:
            raise ValueError("Backtest job not found or not owned by user.")

        metadata = dict(existing.get("execution_metadata") or {})
        metadata.update(execution_metadata or {})
        payload = {
            "status": "running",
            "started_at": started_at or existing.get("started_at") or _now_iso(),
            "attempts": int(existing.get("attempts") or 0) + 1,
            "execution_metadata": metadata,
            "updated_at": _now_iso(),
        }
        updated = (
            self.client.table("backtest_jobs")
            .update(payload)
            .eq("user_id", user_id)
            .eq("id", job_id)
            .execute()
        )
        return dict(_row_one(updated) or {})

    def mark_backtest_job_failed(
        self,
        *,
        user_id: str,
        job_id: str,
        failure_code: str,
        failure_detail: str,
        retryable: bool,
        execution_metadata: dict[str, Any] | None = None,
        finished_at: str | None = None,
    ) -> dict[str, Any]:
        existing = self.get_backtest_job(user_id=user_id, job_id=job_id)
        if existing is None:
            raise ValueError("Backtest job not found or not owned by user.")

        metadata = dict(existing.get("execution_metadata") or {})
        metadata.update(execution_metadata or {})
        payload = {
            "status": "failed",
            "finished_at": finished_at or _now_iso(),
            "failure_code": failure_code,
            "failure_detail": failure_detail,
            "retryable": retryable,
            "execution_metadata": metadata,
            "updated_at": _now_iso(),
        }
        updated = (
            self.client.table("backtest_jobs")
            .update(payload)
            .eq("user_id", user_id)
            .eq("id", job_id)
            .execute()
        )
        return dict(_row_one(updated) or {})

    def create_context_packet(
        self,
        *,
        user_id: str,
        packet: dict[str, Any],
    ) -> dict[str, Any]:
        payload = dict(packet)
        payload["user_id"] = user_id
        payload["packet"] = dict(packet)
        created = self.client.table("context_packets").insert(payload).execute()
        return dict(_row_one(created) or {})

    def attach_context_packet_to_run(
        self,
        *,
        user_id: str,
        attachment: dict[str, Any],
    ) -> dict[str, Any]:
        run_id = str(attachment["run_id"])
        packet_id = str(attachment["packet_id"])
        self._require_owned_backtest_run(user_id=user_id, run_id=run_id)
        if not self._context_packet_owned_by_user(
            user_id=user_id,
            packet_id=packet_id,
        ):
            raise ValueError("Context packet not found or not owned by user.")

        payload = {
            "user_id": user_id,
            "run_id": run_id,
            "context_packet_id": packet_id,
            "explanation_id": attachment.get("explanation_id"),
            "attached_at": attachment.get("attached_at") or _now_iso(),
            "immutable_snapshot": bool(attachment.get("immutable_snapshot", True)),
        }
        created = self.client.table("run_context_packets").insert(payload).execute()
        return dict(_row_one(created) or {})

    def _require_owned_conversation(
        self,
        *,
        user_id: str,
        conversation_id: str | None,
    ) -> None:
        if conversation_id is None:
            return
        if self.get_conversation(user_id=user_id, conversation_id=conversation_id):
            return
        raise ValueError("Conversation not found or not owned by user.")

    def _require_owned_strategy(
        self,
        *,
        user_id: str,
        strategy_id: str | None,
    ) -> None:
        if strategy_id is None:
            return
        if self.get_strategy(user_id=user_id, strategy_id=strategy_id):
            return
        raise ValueError("Strategy not found or not owned by user.")

    def _require_owned_backtest_run(self, *, user_id: str, run_id: str) -> None:
        if self.get_backtest_run(user_id=user_id, run_id=run_id):
            return
        raise ValueError("Backtest run not found or not owned by user.")

    def _require_owned_backtest_run_if_present(
        self, *, user_id: str, run_id: str | None
    ) -> None:
        if run_id is None:
            return
        self._require_owned_backtest_run(user_id=user_id, run_id=run_id)

    def _require_owned_idea(self, *, user_id: str, idea_id: str | None) -> None:
        if idea_id is None:
            return
        rows = (
            self.client.table("ideas")
            .select("id")
            .eq("user_id", user_id)
            .eq("id", idea_id)
            .limit(1)
            .execute()
        )
        if _row_one(rows) is not None:
            return
        raise ValueError("Idea not found or not owned by user.")

    def _require_owned_idea_version(
        self, *, user_id: str, idea_version_id: str | None
    ) -> None:
        if idea_version_id is None:
            return
        rows = (
            self.client.table("idea_versions")
            .select("id")
            .eq("user_id", user_id)
            .eq("id", idea_version_id)
            .limit(1)
            .execute()
        )
        if _row_one(rows) is not None:
            return
        raise ValueError("Idea version not found or not owned by user.")

    def _require_owned_evidence_artifact(
        self, *, user_id: str, artifact_id: str | None
    ) -> None:
        if artifact_id is None:
            return
        rows = (
            self.client.table("evidence_artifacts")
            .select("id")
            .eq("user_id", user_id)
            .eq("id", artifact_id)
            .limit(1)
            .execute()
        )
        if _row_one(rows) is not None:
            return
        raise ValueError("Evidence artifact not found or not owned by user.")

    def _context_packet_owned_by_user(self, *, user_id: str, packet_id: str) -> bool:
        rows = (
            self.client.table("context_packets")
            .select("id")
            .eq("user_id", user_id)
            .eq("id", packet_id)
            .limit(1)
            .execute()
        )
        return _row_one(rows) is not None

    def create_route_receipt(
        self,
        *,
        user_id: str | None,
        receipt: dict[str, Any],
        conversation_id: str | None = None,
        run_id: str | None = None,
        message_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "run_id": run_id,
            "message_id": message_id,
            "task": receipt["task"],
            "tier": receipt["tier"],
            "model": receipt.get("model"),
            "fallback_model": receipt.get("fallback_model"),
            "mode": receipt["mode"],
            "schema_name": receipt.get("schema_name"),
            "latency_ms": receipt.get("latency_ms", 0),
            "outcome": receipt["outcome"],
            "failure_mode": receipt.get("failure_mode"),
            "fallback_used": bool(receipt.get("fallback_used")),
            "token_usage": receipt.get("token_usage"),
            "context_packet_ids": receipt.get("context_packet_ids") or [],
            "metadata": metadata or {},
            "created_at": receipt.get("created_at") or _now_iso(),
        }
        created = self.client.table("route_receipts").insert(payload).execute()
        return dict(_row_one(created) or {})

    def health_check(self) -> dict[str, Any]:
        started = time.perf_counter()
        self.client.table("profiles").select("id").limit(1).execute()
        return {
            "status": "ready",
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }

    def get_backtest_run(self, *, user_id: str, run_id: str) -> BacktestRun | None:
        rows = (
            self.client.table("backtest_runs")
            .select("*")
            .eq("user_id", user_id)
            .eq("id", run_id)
            .limit(1)
            .execute()
        )
        row = _row_one(rows)
        return BacktestRun.model_validate(row) if row else None

    def get_latest_completed_run_for_conversation(
        self, *, user_id: str, conversation_id: str
    ) -> BacktestRun | None:
        rows = (
            self.client.table("backtest_runs")
            .select("*")
            .eq("user_id", user_id)
            .eq("conversation_id", conversation_id)
            .eq("status", "completed")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        row = _row_one(rows)
        return BacktestRun.model_validate(row) if row else None

    def count_completed_runs(self, *, user_id: str) -> int:
        rows = (
            self.client.table("backtest_runs")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("status", "completed")
            .execute()
        )
        return int(rows.count or 0)

    def touch_conversation_title(
        self,
        *,
        user_id: str,
        conversation_id: str,
        title: str,
        title_source: str,
        last_message_preview: str,
    ) -> None:
        self.client.table("conversations").update(
            {
                "title": title,
                "title_source": title_source,
                "last_message_preview": last_message_preview,
                "updated_at": _now_iso(),
            }
        ).eq("id", conversation_id).eq("user_id", user_id).execute()

    def list_history_rows(
        self,
        *,
        user_id: str,
        limit: int | None,
        archived: bool = False,
        deleted: bool = False,
    ) -> dict[str, list[dict[str, Any]]]:
        query_runs = (
            self.client.table("backtest_runs")
            .select("id,conversation_id,conversation_result_card,created_at")
            .eq("user_id", user_id)
        )
        query_chats = (
            self.client.table("conversations")
            .select("id,title,last_message_preview,pinned,updated_at,deleted_at,archived")
            .eq("user_id", user_id)
            .eq("archived", archived)
        )
        query_strategies = (
            self.client.table("strategies")
            .select("id,name,symbols,pinned,updated_at,deleted_at")
            .eq("user_id", user_id)
        )
        query_collections = (
            self.client.table("collections")
            .select("id,name,pinned,updated_at,deleted_at")
            .eq("user_id", user_id)
        )

        if deleted:
            # We don't soft-delete backtest_runs usually, but if we did:
            # query_runs = query_runs.not_.is_("deleted_at", "null")
            query_chats = query_chats.not_.is_("deleted_at", "null")
            query_strategies = query_strategies.not_.is_("deleted_at", "null")
            query_collections = query_collections.not_.is_("deleted_at", "null")
        else:
            query_chats = query_chats.is_("deleted_at", "null")
            query_strategies = query_strategies.is_("deleted_at", "null")
            query_collections = query_collections.is_("deleted_at", "null")

        ordered_runs = query_runs.order("created_at", desc=True)
        ordered_chats = query_chats.order("updated_at", desc=True)
        ordered_strategies = query_strategies.order("updated_at", desc=True)
        ordered_collections = query_collections.order("updated_at", desc=True)

        if limit is None:
            runs = self._fetch_all_rows(lambda start, end: ordered_runs.range(start, end))
            chats = self._fetch_all_rows(
                lambda start, end: ordered_chats.range(start, end)
            )
            strategies = self._fetch_all_rows(
                lambda start, end: ordered_strategies.range(start, end)
            )
            collections = self._fetch_all_rows(
                lambda start, end: ordered_collections.range(start, end)
            )
        else:
            runs = ordered_runs.limit(limit).execute().data or []
            chats = ordered_chats.limit(limit).execute().data or []
            strategies = ordered_strategies.limit(limit).execute().data or []
            collections = ordered_collections.limit(limit).execute().data or []
        run_parent_conversations = self._fetch_history_run_conversation_states(
            user_id=user_id,
            runs=runs,
        )
        chat_message_states = self._fetch_history_conversation_message_states(
            user_id=user_id,
            conversations=chats,
        )
        runs = _filter_history_runs_by_conversation_state(
            runs,
            run_parent_conversations,
            archived=archived,
            deleted=deleted,
        )
        chats = _filter_history_conversations_by_message_state(
            chats,
            chat_message_states,
        )

        return {
            "runs": runs,
            "conversations": chats,
            "strategies": strategies,
            "collections": collections,
        }

    def _fetch_history_run_conversation_states(
        self,
        *,
        user_id: str,
        runs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        conversation_ids = sorted(
            {
                str(run["conversation_id"])
                for run in runs
                if run.get("conversation_id") is not None
            }
        )
        if not conversation_ids:
            return []
        return (
            self.client.table("conversations")
            .select("id,archived,deleted_at")
            .eq("user_id", user_id)
            .in_("id", conversation_ids)
            .execute()
            .data
            or []
        )

    def _fetch_history_conversation_message_states(
        self,
        *,
        user_id: str,
        conversations: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        conversation_ids = sorted(
            {
                str(conversation["id"])
                for conversation in conversations
                if conversation.get("id") is not None
            }
        )
        if not conversation_ids:
            return []
        query = (
            self.client.table("messages")
            .select("conversation_id")
            .eq("user_id", user_id)
            .in_("conversation_id", conversation_ids)
        )
        return self._fetch_all_rows(lambda start, end: query.range(start, end))

    def search_rows(
        self, *, user_id: str, query: str, limit: int | None
    ) -> dict[str, list[dict[str, Any]]]:
        normalized_query = query.strip().lower()
        conversations_query = (
            self.client.table("conversations")
            .select("id,title,last_message_preview,updated_at,deleted_at,pinned")
            .eq("user_id", user_id)
            .is_("deleted_at", "null")
            .order("updated_at", desc=True)
        )
        strategies_query = (
            self.client.table("strategies")
            .select("id,name,symbols,template,updated_at,deleted_at,pinned")
            .eq("user_id", user_id)
            .is_("deleted_at", "null")
            .order("updated_at", desc=True)
        )
        collections_query = (
            self.client.table("collections")
            .select("id,name,updated_at,deleted_at,pinned")
            .eq("user_id", user_id)
            .is_("deleted_at", "null")
            .order("updated_at", desc=True)
        )
        runs_query = (
            self.client.table("backtest_runs")
            .select(
                "id,conversation_id,conversation_result_card,created_at,status,"
                "asset_class,benchmark_symbol"
            )
            .eq("user_id", user_id)
            .eq("status", "completed")
            .order("created_at", desc=True)
        )
        ideas_query = (
            self.client.table("ideas")
            .select(
                "id,title,summary,lifecycle,active_version_id,"
                "source_conversation_id,updated_at"
            )
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
        )
        evidence_query = (
            self.client.table("evidence_artifacts")
            .select(
                "id,title,digest,lifecycle,artifact_type,payload,source_run_id,"
                "source_conversation_id,updated_at"
            )
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
        )
        decisions_query = (
            self.client.table("decision_notes")
            .select(
                "id,decision_state,note,evidence_artifact_id,"
                "source_conversation_id,updated_at"
            )
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
        )

        if limit is None:
            conversations_raw = self._fetch_all_rows(
                lambda start, end: conversations_query.range(start, end)
            )
            strategies_raw = self._fetch_all_rows(
                lambda start, end: strategies_query.range(start, end)
            )
            collections_raw = self._fetch_all_rows(
                lambda start, end: collections_query.range(start, end)
            )
            runs_raw = self._fetch_all_rows(
                lambda start, end: runs_query.range(start, end)
            )
            ideas_raw = self._fetch_all_rows(
                lambda start, end: ideas_query.range(start, end)
            )
            evidence_raw = self._fetch_all_rows(
                lambda start, end: evidence_query.range(start, end)
            )
            decisions_raw = self._fetch_all_rows(
                lambda start, end: decisions_query.range(start, end)
            )
        else:
            conversations_raw = conversations_query.limit(limit).execute().data or []
            strategies_raw = strategies_query.limit(limit).execute().data or []
            collections_raw = collections_query.limit(limit).execute().data or []
            runs_raw = runs_query.limit(limit).execute().data or []
            ideas_raw = ideas_query.limit(limit).execute().data or []
            evidence_raw = evidence_query.limit(limit).execute().data or []
            decisions_raw = decisions_query.limit(limit).execute().data or []

        conversations = [
            row
            for row in conversations_raw
            if normalized_query
            in (f"{row.get('title', '')} {row.get('last_message_preview') or ''}").lower()
        ]
        strategies = [
            row
            for row in strategies_raw
            if normalized_query
            in (
                f"{row.get('name', '')} {' '.join(row.get('symbols') or [])} {row.get('template') or ''}"
            ).lower()
        ]
        collections = [
            row
            for row in collections_raw
            if normalized_query in str(row.get("name", "")).lower()
        ]
        runs = [
            row
            for row in runs_raw
            if normalized_query
            in (
                f"{(row.get('conversation_result_card') or {}).get('title', '')} "
                f"{' '.join((row.get('conversation_result_card') or {}).get('symbols') or [])} "
                f"{(row.get('conversation_result_card') or {}).get('strategy_label', '')} "
                f"{row.get('benchmark_symbol') or ''}"
            ).lower()
        ]
        ideas = [
            row
            for row in ideas_raw
            if normalized_query
            in f"{row.get('title', '')} {row.get('summary') or ''}".lower()
        ]
        evidence = [
            row
            for row in evidence_raw
            if normalized_query
            in (
                f"{row.get('title', '')} {row.get('digest') or ''} "
                f"{' '.join(((row.get('payload') or {}).get('result_card') or {}).get('symbols') or [])}"
            ).lower()
        ]
        evidence_by_id = {str(row.get("id")): row for row in evidence_raw}
        decisions = []
        for row in decisions_raw:
            artifact = evidence_by_id.get(str(row.get("evidence_artifact_id"))) or {}
            haystack = (
                f"{row.get('decision_state', '')} {row.get('note') or ''} "
                f"{artifact.get('title', '')} {artifact.get('digest', '')}"
            )
            if normalized_query in haystack.lower():
                decisions.append(
                    {
                        **row,
                        "artifact_title": artifact.get("title"),
                        "artifact_digest": artifact.get("digest"),
                    }
                )
        return {
            "conversations": conversations,
            "strategies": strategies,
            "collections": collections,
            "runs": runs,
            "ideas": ideas,
            "evidence": evidence,
            "decisions": decisions,
        }

    def create_strategy(self, *, user_id: str, payload: dict[str, Any]) -> Strategy:
        self._require_owned_conversation(
            user_id=user_id,
            conversation_id=payload.get("conversation_id"),
        )
        created = (
            self.client.table("strategies")
            .insert({"user_id": user_id, **payload})
            .execute()
        )
        return Strategy.model_validate(_row_one(created))

    def list_strategies(
        self, *, user_id: str, limit: int | None, deleted: bool = False
    ) -> list[Strategy]:
        query = self.client.table("strategies").select("*").eq("user_id", user_id)
        if deleted:
            query = query.not_.is_("deleted_at", "null")
        else:
            query = query.is_("deleted_at", "null")

        ordered = query.order("pinned", desc=True).order("updated_at", desc=True)
        if limit is None:
            rows_data = self._fetch_all_rows(lambda start, end: ordered.range(start, end))
        else:
            rows_data = ordered.limit(limit).execute().data or []
        return [Strategy.model_validate(row) for row in rows_data]

    def get_strategy(self, *, user_id: str, strategy_id: str) -> Strategy | None:
        rows = (
            self.client.table("strategies")
            .select("*")
            .eq("user_id", user_id)
            .eq("id", strategy_id)
            .limit(1)
            .execute()
        )
        row = _row_one(rows)
        return Strategy.model_validate(row) if row else None

    def patch_strategy(
        self, *, user_id: str, strategy_id: str, patch: dict[str, Any]
    ) -> Strategy | None:
        patch["updated_at"] = _now_iso()
        self.client.table("strategies").update(patch).eq("id", strategy_id).eq(
            "user_id", user_id
        ).execute()
        return self.get_strategy(user_id=user_id, strategy_id=strategy_id)

    def soft_delete_strategy(self, *, user_id: str, strategy_id: str) -> bool:
        result = (
            self.client.table("strategies")
            .update({"deleted_at": _now_iso(), "updated_at": _now_iso()})
            .eq("id", strategy_id)
            .eq("user_id", user_id)
            .execute()
        )
        return bool(result.data)

    def create_collection(self, *, user_id: str, payload: dict[str, Any]) -> Collection:
        created = (
            self.client.table("collections")
            .insert({"user_id": user_id, **payload})
            .execute()
        )
        row = _row_one(created)
        if row is None:
            raise RuntimeError("Failed to create collection.")
        row["strategy_count"] = 0
        return Collection.model_validate(row)

    def list_collections(self, *, user_id: str, limit: int | None) -> list[Collection]:
        query = (
            self.client.table("collections")
            .select("*")
            .eq("user_id", user_id)
            .is_("deleted_at", "null")
            .order("pinned", desc=True)
            .order("updated_at", desc=True)
        )
        if limit is None:
            rows_data = self._fetch_all_rows(lambda start, end: query.range(start, end))
        else:
            rows_data = query.limit(limit).execute().data or []
        items: list[Collection] = []
        for row in rows_data:
            count = (
                self.client.table("collection_strategies")
                .select("id", count="exact")
                .eq("collection_id", row["id"])
                .eq("user_id", user_id)
                .execute()
                .count
                or 0
            )
            row["strategy_count"] = count
            items.append(Collection.model_validate(row))
        return items

    def get_collection(self, *, user_id: str, collection_id: str) -> Collection | None:
        rows = (
            self.client.table("collections")
            .select("*")
            .eq("user_id", user_id)
            .eq("id", collection_id)
            .limit(1)
            .execute()
        )
        row = _row_one(rows)
        if not row:
            return None
        count = (
            self.client.table("collection_strategies")
            .select("id", count="exact")
            .eq("collection_id", collection_id)
            .eq("user_id", user_id)
            .execute()
            .count
            or 0
        )
        row["strategy_count"] = count
        return Collection.model_validate(row)

    def patch_collection(
        self, *, user_id: str, collection_id: str, patch: dict[str, Any]
    ) -> Collection | None:
        patch["updated_at"] = _now_iso()
        self.client.table("collections").update(patch).eq("id", collection_id).eq(
            "user_id", user_id
        ).execute()
        return self.get_collection(user_id=user_id, collection_id=collection_id)

    def soft_delete_collection(self, *, user_id: str, collection_id: str) -> bool:
        result = (
            self.client.table("collections")
            .update({"deleted_at": _now_iso(), "updated_at": _now_iso()})
            .eq("id", collection_id)
            .eq("user_id", user_id)
            .execute()
        )
        return bool(result.data)

    def attach_strategies(
        self, *, user_id: str, collection_id: str, strategy_ids: list[str]
    ) -> Collection | None:
        collection = self.get_collection(user_id=user_id, collection_id=collection_id)
        if collection is None:
            return None

        if strategy_ids:
            valid_strategies = (
                self.client.table("strategies")
                .select("id")
                .eq("user_id", user_id)
                .in_("id", strategy_ids)
                .execute()
            )
            valid_ids = {row["id"] for row in (valid_strategies.data or [])}
            if len(valid_ids) != len(set(strategy_ids)):
                raise ValueError("One or more strategies not found or not owned by user.")

        rows = [
            {
                "user_id": user_id,
                "collection_id": collection_id,
                "strategy_id": strategy_id,
            }
            for strategy_id in strategy_ids
        ]
        if rows:
            self.client.table("collection_strategies").upsert(
                rows, on_conflict="collection_id,strategy_id"
            ).execute()
        return self.get_collection(user_id=user_id, collection_id=collection_id)

    def detach_strategy(
        self, *, user_id: str, collection_id: str, strategy_id: str
    ) -> bool:
        result = (
            self.client.table("collection_strategies")
            .delete()
            .eq("user_id", user_id)
            .eq("collection_id", collection_id)
            .eq("strategy_id", strategy_id)
            .execute()
        )
        return bool(result.data)

    def check_and_increment_usage(
        self, *, user_id: str, resource: str, period: str, limit_count: int
    ) -> None:
        now = datetime.now(timezone.utc)
        start, end = _align_period(now, period)
        start_iso = start.isoformat()
        end_iso = end.isoformat()
        with _USAGE_COUNTER_LOCK:
            for _ in range(5):
                rows = (
                    self.client.table("usage_counters")
                    .select("*")
                    .eq("user_id", user_id)
                    .eq("resource", resource)
                    .eq("period", period)
                    .eq("period_start", start_iso)
                    .limit(1)
                    .execute()
                )
                row = _row_one(rows)

                if row is None:
                    try:
                        self.client.table("usage_counters").insert(
                            {
                                "user_id": user_id,
                                "resource": resource,
                                "period": period,
                                "period_start": start_iso,
                                "period_end": end_iso,
                                "used_count": 0,
                                "limit_count": limit_count,
                                "created_at": _now_iso(),
                                "updated_at": _now_iso(),
                            }
                        ).execute()
                    except Exception:
                        pass
                    continue

                current_used = int(row.get("used_count", 0))
                if current_used >= limit_count:
                    raise QuotaExceededError(f"Quota exceeded for {resource} ({period})")

                updated = (
                    self.client.table("usage_counters")
                    .update(
                        {
                            "used_count": current_used + 1,
                            "limit_count": limit_count,
                            "updated_at": _now_iso(),
                        }
                    )
                    .eq("id", row["id"])
                    .eq("used_count", current_used)
                    .execute()
                )
                if updated.data:
                    return

            raise RuntimeError(
                f"Failed to increment usage counter for {resource} ({period})."
            )

    def get_auth_user_from_token(self, token: str) -> dict[str, Any]:
        response = self.client.auth.get_user(token)
        if not response or not response.user:
            raise RuntimeError("Invalid or missing user in token response.")
        return response.user.model_dump(mode="json")

    def get_or_create_profile_for_auth_user(self, auth_user: dict[str, Any]) -> User:
        user_id = auth_user["id"]
        email = str(auth_user.get("email") or "").strip()
        allowlist_role = self.private_alpha_role_for_email(email)
        is_admin = allowlist_role in {"admin", "developer"}
        # Try to get existing profile
        existing = self.get_user(user_id=user_id)
        if existing is not None:
            if is_admin and not existing.is_admin:
                return self.update_user(
                    user_id=user_id,
                    updates={"id": user_id, "is_admin": True},
                )
            return existing

        now = _now_iso()
        user_metadata = auth_user.get("user_metadata") or {}
        # Canonical defaults per requirements
        payload = {
            "id": user_id,
            "email": email,
            "username": user_metadata.get("username"),
            "display_name": user_metadata.get("display_name"),
            "language": "en",
            "locale": "en-US",
            "theme": "dark",
            "is_admin": is_admin,
            "onboarding": {
                "completed": False,
                "stage": "language_selection",
                "language_confirmed": False,
                "primary_goal": None,
            },
            "created_at": now,
            "updated_at": now,
        }

        created = self.client.table("profiles").insert(payload).execute()
        row = _row_one(created)
        if row is None:
            raise RuntimeError("Failed to create user profile.")
        return User.model_validate(row)

    @staticmethod
    def parse_iso(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def create_feedback(
        self,
        user_id: str,
        feedback_type: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Persists feedback to the Supabase database."""
        self.client.table("feedback").insert(
            {
                "id": self.new_id(),
                "user_id": user_id,
                "type": feedback_type,
                "message": message,
                "context": context,
                "created_at": _now_iso(),
            }
        ).execute()
