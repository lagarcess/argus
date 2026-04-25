from __future__ import annotations

import os
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
    mock_user_email: str = "developer@argus.local"
    mock_user_password: str = "ArgusDevUser123!"
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

    def update_user(self, user_id: str, updates: dict[str, Any]) -> User:
        updates["updated_at"] = _now_iso()
        self.client.table("profiles").update(updates).eq("id", user_id).execute()
        loaded = (
            self.client.table("profiles").select("*").eq("id", user_id).single().execute()
        )
        return User.model_validate(_row_one(loaded))

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
        self, *, user_id: str, limit: int, archived: bool | None = None, deleted: bool = False
    ) -> list[Conversation]:
        query = self.client.table("conversations").select("*").eq("user_id", user_id)
        if deleted:
            query = query.not_.is_("deleted_at", "null")
        else:
            query = query.is_("deleted_at", "null")

        if archived is not None:
            query = query.eq("archived", archived)

        rows = (
            query.order("pinned", desc=True)
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [Conversation.model_validate(row) for row in (rows.data or [])]

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
        self, *, user_id: str, conversation_id: str, limit: int
    ) -> list[Message]:
        rows = (
            self.client.table("messages")
            .select("id,conversation_id,role,content,created_at")
            .eq("user_id", user_id)
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        return [Message.model_validate(row) for row in (rows.data or [])]

    def create_message(
        self, *, user_id: str, conversation_id: str, role: str, content: str
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
        self, *, user_id: str, limit: int, deleted: bool = False
    ) -> dict[str, list[dict[str, Any]]]:
        query_runs = self.client.table("backtest_runs").select("id,conversation_result_card,created_at").eq("user_id", user_id)
        query_chats = self.client.table("conversations").select("id,title,last_message_preview,pinned,updated_at,deleted_at").eq("user_id", user_id)
        query_strategies = self.client.table("strategies").select("id,name,symbols,pinned,updated_at,deleted_at").eq("user_id", user_id)
        query_collections = self.client.table("collections").select("id,name,pinned,updated_at,deleted_at").eq("user_id", user_id)

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

        runs = query_runs.order("created_at", desc=True).limit(limit).execute().data or []
        chats = query_chats.order("updated_at", desc=True).limit(limit).execute().data or []
        strategies = query_strategies.order("updated_at", desc=True).limit(limit).execute().data or []
        collections = query_collections.order("updated_at", desc=True).limit(limit).execute().data or []

        return {
            "runs": runs,
            "conversations": chats,
            "strategies": strategies,
            "collections": collections,
        }

    def search_rows(
        self, *, user_id: str, query: str, limit: int
    ) -> dict[str, list[dict[str, Any]]]:
        conversations = (
            self.client.table("conversations")
            .select("id,title,last_message_preview,updated_at,deleted_at")
            .eq("user_id", user_id)
            .is_("deleted_at", "null")
            .ilike("title", f"%{query}%")
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
        strategies = (
            self.client.table("strategies")
            .select("id,name,symbols,updated_at,deleted_at")
            .eq("user_id", user_id)
            .is_("deleted_at", "null")
            .ilike("name", f"%{query}%")
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
        collections = (
            self.client.table("collections")
            .select("id,name,updated_at,deleted_at")
            .eq("user_id", user_id)
            .is_("deleted_at", "null")
            .ilike("name", f"%{query}%")
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
        return {
            "conversations": conversations,
            "strategies": strategies,
            "collections": collections,
        }

    def create_feedback(
        self, *, user_id: str, feedback_type: str, message: str, context: dict[str, Any]
    ) -> None:
        self.client.table("feedback").insert(
            {
                "user_id": user_id,
                "type": feedback_type,
                "message": message,
                "context": context,
                "created_at": _now_iso(),
            }
        ).execute()

    def create_strategy(self, *, user_id: str, payload: dict[str, Any]) -> Strategy:
        created = (
            self.client.table("strategies")
            .insert({"user_id": user_id, **payload})
            .execute()
        )
        return Strategy.model_validate(_row_one(created))

    def list_strategies(
        self, *, user_id: str, limit: int, deleted: bool = False
    ) -> list[Strategy]:
        query = self.client.table("strategies").select("*").eq("user_id", user_id)
        if deleted:
            query = query.not_.is_("deleted_at", "null")
        else:
            query = query.is_("deleted_at", "null")

        rows = (
            query.order("pinned", desc=True)
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [Strategy.model_validate(row) for row in (rows.data or [])]

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

    def list_collections(self, *, user_id: str, limit: int) -> list[Collection]:
        rows = (
            self.client.table("collections")
            .select("*")
            .eq("user_id", user_id)
            .is_("deleted_at", "null")
            .order("pinned", desc=True)
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )
        items: list[Collection] = []
        for row in rows.data or []:
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

    def check_and_increment_usage(
        self, *, user_id: str, resource: str, period: str, limit_count: int
    ) -> None:
        now = datetime.now(timezone.utc)
        start, end = _align_period(now, period)
        start_iso = start.isoformat()
        end_iso = end.isoformat()

        rows = (
            self.client.table("usage_counters")
            .select("*")
            .eq("user_id", user_id)
            .eq("resource", resource)
            .eq("period", period)
            .eq("period_start", start_iso)
            .execute()
        )
        row = _row_one(rows)

        if row:
            if row["used_count"] >= limit_count:
                raise QuotaExceededError(f"Quota exceeded for {resource} ({period})")
            self.client.table("usage_counters").update(
                {"used_count": row["used_count"] + 1, "updated_at": _now_iso()}
            ).eq("id", row["id"]).execute()
        else:
            self.client.table("usage_counters").insert(
                {
                    "user_id": user_id,
                    "resource": resource,
                    "period": period,
                    "period_start": start_iso,
                    "period_end": end_iso,
                    "used_count": 1,
                    "limit_count": limit_count,
                    "created_at": _now_iso(),
                    "updated_at": _now_iso(),
                }
            ).execute()

    def detach_strategy(
        self, *, user_id: str, collection_id: str, strategy_id: str
    ) -> None:
        self.client.table("collection_strategies").delete().eq("user_id", user_id).eq(
            "collection_id", collection_id
        ).eq("strategy_id", strategy_id).execute()

    @staticmethod
    def parse_iso(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
