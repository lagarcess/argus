from __future__ import annotations

import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from argus.api.schemas import (
    BacktestRun,
    Collection,
    Conversation,
    Message,
    OnboardingState,
    Strategy,
    User,
)
from argus.domain.store import utcnow
from supabase import Client, create_client


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


@dataclass
class SupabaseGateway:
    client: Client
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
        return cls(client=create_client(url, key))

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
            "collection_strategies",
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
            response = self.client.auth.sign_up(
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

    def login(self, email: str, password: str) -> dict[str, Any]:
        try:
            response = self.client.auth.sign_in_with_password(
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
        result = (
            self.client.table("conversations")
            .update({"deleted_at": _now_iso(), "updated_at": _now_iso()})
            .eq("id", conversation_id)
            .eq("user_id", user_id)
            .execute()
        )
        return bool(result.data)

    def list_messages(
        self, *, user_id: str, conversation_id: str, limit: int | None
    ) -> list[Message]:
        query = (
            self.client.table("messages")
            .select("id,conversation_id,role,content,created_at")
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
            "metadata": metadata,
            "created_at": _now_iso(),
        }
        created = self.client.table("messages").insert(payload).execute()
        return Message.model_validate(_row_one(created))

    def create_backtest_run(self, *, user_id: str, run: BacktestRun) -> BacktestRun:
        payload = run.model_dump(mode="json")
        payload["user_id"] = user_id
        created = self.client.table("backtest_runs").insert(payload).execute()
        return BacktestRun.model_validate(_row_one(created))

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
        self, *, user_id: str, limit: int | None, deleted: bool = False
    ) -> dict[str, list[dict[str, Any]]]:
        query_runs = (
            self.client.table("backtest_runs")
            .select("id,conversation_result_card,created_at")
            .eq("user_id", user_id)
        )
        query_chats = (
            self.client.table("conversations")
            .select("id,title,last_message_preview,pinned,updated_at,deleted_at")
            .eq("user_id", user_id)
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
            chats = self._fetch_all_rows(lambda start, end: ordered_chats.range(start, end))
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

        return {
            "runs": runs,
            "conversations": chats,
            "strategies": strategies,
            "collections": collections,
        }

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
            .select("id,conversation_result_card,created_at,status")
            .eq("user_id", user_id)
            .eq("status", "completed")
            .order("created_at", desc=True)
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
            runs_raw = self._fetch_all_rows(lambda start, end: runs_query.range(start, end))
        else:
            conversations_raw = conversations_query.limit(limit).execute().data or []
            strategies_raw = strategies_query.limit(limit).execute().data or []
            collections_raw = collections_query.limit(limit).execute().data or []
            runs_raw = runs_query.limit(limit).execute().data or []

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
            in str((row.get("conversation_result_card") or {}).get("title", "")).lower()
        ]
        return {
            "conversations": conversations,
            "strategies": strategies,
            "collections": collections,
            "runs": runs,
        }

    def create_strategy(self, *, user_id: str, payload: dict[str, Any]) -> Strategy:
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
        # Try to get existing profile
        existing = self.get_user(user_id=user_id)
        if existing is not None:
            return existing

        now = _now_iso()
        user_metadata = auth_user.get("user_metadata") or {}
        # Canonical defaults per requirements
        payload = {
            "id": user_id,
            "email": auth_user.get("email"),
            "username": user_metadata.get("username"),
            "display_name": user_metadata.get("display_name"),
            "language": "en",
            "locale": "en-US",
            "theme": "dark",
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
