"""The Supabase Admin API calls account deletion makes.

Placeholders and the final auth-user delete go through the Admin API only,
never through SQL on auth.users.
"""

from __future__ import annotations

from typing import Any, Protocol

# Long enough to outlive the product; GoTrue takes a Go duration.
PLACEHOLDER_BAN = "876000h"
PLACEHOLDER_DOMAIN = "cuadrao.invalid"


def placeholder_email(token: str) -> str:
    return f"exmiembro+{token}@{PLACEHOLDER_DOMAIN}"


class AuthAdmin(Protocol):
    def create_placeholder(self, *, user_id: str, email: str) -> None:
        """Create a banned, confirmed, passwordless user with that id.
        Must succeed, or report the id already exists, without side effects."""
        ...

    def user_exists(self, user_id: str) -> bool: ...

    def identity_providers(self, user_id: str) -> set[str]: ...

    def delete_user(self, user_id: str) -> None:
        """Delete the auth user. Deleting a user that is already gone is a no-op."""
        ...


class SupabaseAuthAdmin:
    def __init__(self, client: Any) -> None:
        self._admin = client.auth.admin

    def create_placeholder(self, *, user_id: str, email: str) -> None:
        self._admin.create_user(
            {
                "id": user_id,
                "email": email,
                "email_confirm": True,
                "ban_duration": PLACEHOLDER_BAN,
                "app_metadata": {"placeholder": True},
            }
        )

    def _get(self, user_id: str) -> Any | None:
        try:
            response = self._admin.get_user_by_id(user_id)
        except Exception as exc:  # GoTrue answers 404 as an AuthApiError
            if getattr(exc, "status", None) == 404 or "not found" in str(exc).lower():
                return None
            raise
        return getattr(response, "user", None)

    def user_exists(self, user_id: str) -> bool:
        return self._get(user_id) is not None

    def identity_providers(self, user_id: str) -> set[str]:
        user = self._get(user_id)
        if user is None:
            return set()
        return {
            str(identity.provider)
            for identity in (getattr(user, "identities", None) or [])
            if getattr(identity, "provider", None)
        }

    def delete_user(self, user_id: str) -> None:
        if self._get(user_id) is None:
            return
        self._admin.delete_user(user_id)
