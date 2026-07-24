from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any

import httpx

from argus.api.schemas import Conversation, Language
from argus.domain.guest_workspaces import GuestWorkspace
from argus.domain.usage_limits import QuotaExceededError


def _row_one(result: Any) -> dict[str, Any] | None:
    data = getattr(result, "data", None)
    if not data:
        return None
    if isinstance(data, list):
        return data[0] if data else None
    return data


class GuestAccountPersistenceMixin:
    """Supabase operations owned by the guest account and allowance spine."""

    def get_auth_user_from_token(self, token: str) -> dict[str, Any]:
        response = self.client.auth.get_user(token)
        if not response or not response.user:
            raise RuntimeError("Invalid or missing user in token response.")
        return response.user.model_dump(mode="json")

    def private_alpha_email_disabled(self, email: str) -> bool:
        rows = (
            self.client.table("private_alpha_allowlist")
            .select("disabled_at")
            .eq("email", email.strip().lower())
            .limit(1)
            .execute()
        )
        row = _row_one(rows)
        return bool(row and row.get("disabled_at") is not None)

    def sign_in_anonymously(
        self,
        *,
        captcha_token: str,
        language: Language,
    ) -> dict[str, Any]:
        try:
            auth_client = self.auth_client or self.client
            response = auth_client.auth.sign_in_anonymously(
                {
                    "options": {
                        "captcha_token": captcha_token,
                        "data": {"language": language},
                    }
                }
            )
            if not response.user or not response.session:
                raise RuntimeError("Anonymous sign-in returned no session.")
            return response.model_dump(mode="json")
        except Exception as exc:
            raise RuntimeError("Anonymous sign-in failed.") from exc

    def delete_auth_user(self, user_id: str) -> None:
        self.client.auth.admin.delete_user(user_id)

    def delete_anonymous_auth_user(self, user_id: str) -> bool:
        response = self.client.auth.admin.get_user_by_id(user_id)
        auth_user = getattr(response, "user", None)
        if auth_user is None:
            raise RuntimeError("Auth user revalidation returned no user.")
        if hasattr(auth_user, "model_dump"):
            auth_user = auth_user.model_dump(mode="json")
        is_anonymous = (
            auth_user.get("is_anonymous")
            if isinstance(auth_user, dict)
            else getattr(auth_user, "is_anonymous", None)
        )
        if is_anonymous is not True:
            return False
        self.delete_auth_user(user_id)
        return True

    def resolve_permanent_auth_user_id(self, email: str) -> str | None:
        normalized = email.strip().lower()
        profile = _row_one(
            self.client.table("profiles")
            .select("id,email")
            .eq("email", normalized)
            .limit(1)
            .execute()
        )
        if not profile:
            return None
        user_id = str(profile.get("id") or "")
        if not user_id:
            return None
        response = self.client.auth.admin.get_user_by_id(user_id)
        auth_user = getattr(response, "user", None)
        if auth_user is None:
            return None
        if hasattr(auth_user, "model_dump"):
            auth_user = auth_user.model_dump(mode="json")
        if not isinstance(auth_user, dict):
            return None
        auth_email = str(auth_user.get("email") or "").strip().lower()
        if auth_user.get("is_anonymous") is True or auth_email != normalized:
            return None
        return user_id

    def create_guest_workspace_handoff(
        self,
        *,
        source_user_id: str,
        destination_user_id: str,
        source_conversation_id: str,
        pending_action: dict[str, Any] | None,
        created_at: datetime,
    ) -> dict[str, Any]:
        workspace = _row_one(
            self.client.table("guest_workspaces")
            .select("user_id,conversation_id,status,expires_at")
            .eq("user_id", source_user_id)
            .eq("conversation_id", source_conversation_id)
            .eq("status", "active")
            .gt("expires_at", created_at.isoformat())
            .limit(1)
            .execute()
        )
        if not workspace:
            raise RuntimeError("Guest workspace is not available for handoff.")

        opaque_secret = secrets.token_urlsafe(32)
        secret_hash = hashlib.sha256(opaque_secret.encode("utf-8")).hexdigest()
        expires_at = created_at + timedelta(minutes=10)
        (
            self.client.table("guest_workspace_handoffs")
            .update({"status": "revoked"})
            .eq("source_user_id", source_user_id)
            .eq("status", "pending")
            .execute()
        )
        created = (
            self.client.table("guest_workspace_handoffs")
            .insert(
                {
                    "source_user_id": source_user_id,
                    "destination_user_id": destination_user_id,
                    "source_conversation_id": source_conversation_id,
                    "secret_hash": secret_hash,
                    "pending_action": pending_action,
                    "created_at": created_at.isoformat(),
                    "expires_at": expires_at.isoformat(),
                }
            )
            .execute()
        )
        row = _row_one(created)
        if row is None:
            raise RuntimeError("Guest handoff was not created.")
        return {
            "id": str(row["id"]),
            "expires_at": row["expires_at"],
            "opaque_secret": opaque_secret,
        }

    def claim_guest_workspace_handoff(
        self,
        *,
        handoff_id: str,
        opaque_secret: str,
        destination_user_id: str,
    ) -> dict[str, Any]:
        secret_hash = hashlib.sha256(opaque_secret.encode("utf-8")).hexdigest()
        try:
            result = self.client.rpc(
                "claim_guest_workspace_handoff",
                {
                    "p_handoff_id": handoff_id,
                    "p_secret_hash": secret_hash,
                    "p_destination_user_id": destination_user_id,
                },
            ).execute()
        except Exception as exc:
            detail = str(exc)
            known_codes = (
                "guest_handoff_consumed",
                "guest_handoff_expired",
                "guest_handoff_wrong_destination",
                "guest_handoff_source_not_anonymous",
                "guest_handoff_workspace_unavailable",
                "guest_handoff_unsafe_product_graph",
                "guest_handoff_invalid",
            )
            code = next((value for value in known_codes if value in detail), None)
            raise RuntimeError(code or "guest_handoff_invalid") from None
        row = _row_one(result)
        if row is None:
            raise RuntimeError("guest_handoff_invalid")
        return dict(row)

    def mark_guest_identity_linked(self, user_id: str, *, at: datetime) -> None:
        (
            self.client.table("guest_workspaces")
            .update(
                {
                    "status": "claimed",
                    "claimed_by": user_id,
                    "claimed_at": at.isoformat(),
                    "updated_at": at.isoformat(),
                }
            )
            .eq("user_id", user_id)
            .eq("status", "active")
            .execute()
        )

    def link_anonymous_identity(
        self,
        *,
        access_token: str,
        refresh_token: str,
        email: str,
        password: str,
    ) -> dict[str, Any]:
        auth_client = self.auth_client or self.client
        auth_url = str(auth_client.supabase_url).rstrip("/")
        auth_key = str(auth_client.supabase_key)
        headers = {
            "apikey": auth_key,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=15, follow_redirects=False) as client:
                updated = client.put(
                    f"{auth_url}/auth/v1/user",
                    headers=headers,
                    json={"email": email, "password": password},
                )
                if not updated.is_success:
                    raise RuntimeError("Provider rejected anonymous identity linking.")
                refreshed = client.post(
                    f"{auth_url}/auth/v1/token?grant_type=refresh_token",
                    headers={"apikey": auth_key, "Content-Type": "application/json"},
                    json={"refresh_token": refresh_token},
                )
                if not refreshed.is_success:
                    raise RuntimeError("Provider could not refresh the linked identity.")
                payload = refreshed.json()
        except Exception as exc:
            raise RuntimeError("Anonymous identity linking failed.") from exc

        auth_user = payload.get("user")
        session_access_token = payload.get("access_token")
        session_refresh_token = payload.get("refresh_token")
        if (
            not isinstance(auth_user, dict)
            or auth_user.get("is_anonymous") is not False
            or str(auth_user.get("email") or "").strip().lower() != email.strip().lower()
            or not isinstance(session_access_token, str)
            or not session_access_token
            or not isinstance(session_refresh_token, str)
            or not session_refresh_token
        ):
            raise RuntimeError("Provider returned an invalid linked identity.")
        return {
            "user": auth_user,
            "session": {
                "access_token": session_access_token,
                "refresh_token": session_refresh_token,
                "expires_in": payload.get("expires_in"),
            },
        }

    def get_active_guest_workspace(
        self,
        *,
        user_id: str,
        at: datetime,
    ) -> GuestWorkspace | None:
        rows = (
            self.client.table("guest_workspaces")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "active")
            .gt("expires_at", at.isoformat())
            .limit(1)
            .execute()
        )
        row = _row_one(rows)
        return GuestWorkspace.model_validate(row) if row else None

    def create_guest_workspace(
        self,
        *,
        user_id: str,
        created_at: datetime,
    ) -> GuestWorkspace:
        payload = {
            "user_id": user_id,
            "status": "active",
            "created_at": created_at.isoformat(),
            "expires_at": (created_at + timedelta(days=7)).isoformat(),
            "updated_at": created_at.isoformat(),
        }
        created = self.client.table("guest_workspaces").insert(payload).execute()
        row = _row_one(created)
        if row is None:
            raise RuntimeError("Failed to create guest workspace.")
        return GuestWorkspace.model_validate(row)

    def bind_guest_conversation(
        self,
        *,
        user_id: str,
        conversation_id: str,
    ) -> GuestWorkspace:
        result = self.client.rpc(
            "bind_guest_conversation",
            {
                "p_user_id": user_id,
                "p_conversation_id": conversation_id,
            },
        ).execute()
        row = _row_one(result)
        if row is None:
            raise RuntimeError("Failed to bind guest conversation.")
        return GuestWorkspace.model_validate(row)

    def replace_empty_guest_conversation(
        self,
        *,
        user_id: str,
        title: str,
        title_source: str,
        language: str,
    ) -> Conversation:
        result = self.client.rpc(
            "replace_empty_guest_conversation",
            {
                "p_user_id": user_id,
                "p_title": title,
                "p_title_source": title_source,
                "p_language": language,
            },
        ).execute()
        row = _row_one(result)
        if row is None:
            raise RuntimeError("Failed to replace guest conversation.")
        return Conversation.model_validate(row)

    def replace_guest_conversation(
        self,
        *,
        user_id: str,
        title: str,
        title_source: str,
        language: str,
    ) -> Conversation:
        result = self.client.rpc(
            "replace_guest_conversation",
            {
                "p_user_id": user_id,
                "p_title": title,
                "p_title_source": title_source,
                "p_language": language,
            },
        ).execute()
        row = _row_one(result)
        if row is None:
            raise RuntimeError("Failed to replace guest conversation.")
        return Conversation.model_validate(row)

    def claim_expired_guest_workspaces(
        self,
        *,
        limit: int,
        dry_run: bool,
    ) -> list[dict[str, object]]:
        result = self.client.rpc(
            "claim_expired_guest_workspaces",
            {
                "p_limit": limit,
                "p_dry_run": dry_run,
            },
        ).execute()
        data = result.data or []
        if isinstance(data, dict):
            return [dict(data)]
        return [dict(row) for row in data]

    def check_allowance_windows(
        self,
        *,
        user_id: str,
        resource: str,
        windows: list[dict[str, object]],
    ) -> None:
        for window in windows:
            period = str(window["period"])
            period_start = window.get("period_start")
            query = (
                self.client.table("usage_counters")
                .select("used_count")
                .eq("user_id", user_id)
                .eq("resource", resource)
                .eq("period", period)
            )
            if period_start is not None:
                value = (
                    period_start.isoformat()
                    if hasattr(period_start, "isoformat")
                    else str(period_start)
                )
                query = query.eq("period_start", value)
            rows = query.limit(1).execute()
            row = _row_one(rows)
            if int((row or {}).get("used_count", 0)) >= int(window["limit"]):
                raise QuotaExceededError(f"Quota exceeded for {resource} ({period})")

    def create_feedback_settling_usage(
        self,
        *,
        user_id: str,
        feedback_type: str,
        message: str,
        context: dict[str, Any] | None,
        allowance_limits: list[dict[str, object]],
    ) -> dict[str, Any]:
        serialized: list[dict[str, object]] = []
        for window in allowance_limits:
            item = dict(window)
            for key in ("period_start", "period_end"):
                value = item.get(key)
                if hasattr(value, "isoformat"):
                    item[key] = value.isoformat()  # type: ignore[union-attr]
            serialized.append(item)
        result = self.client.rpc(
            "create_feedback_settling_usage",
            {
                "p_feedback_id": self.new_id(),
                "p_user_id": user_id,
                "p_feedback_type": feedback_type,
                "p_message": message,
                "p_context": context or {},
                "p_usage_resource": "feedback",
                "p_usage_limits": serialized,
            },
        ).execute()
        row = _row_one(result)
        if not isinstance(row, dict):
            raise RuntimeError("Feedback settlement returned no decision.")
        return row
