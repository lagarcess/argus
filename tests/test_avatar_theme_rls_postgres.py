"""Real-Postgres proof for registered-only avatar-theme policies.

Set ``ARGUS_DISPOSABLE_DATABASE_URL`` only to an isolated Supabase Postgres
database with every checked-in migration applied; never point it at shared or
production data.
"""

from __future__ import annotations

import json
import os
from uuid import uuid4

import pytest

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()

pytestmark = pytest.mark.skipif(
    not DSN,
    reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured",
)

psycopg = pytest.importorskip("psycopg")


def _set_authenticated_claims(cursor, *, user_id: str, is_anonymous: bool) -> None:
    cursor.execute("set local role authenticated")
    cursor.execute(
        "select set_config('request.jwt.claims', %s, true)",
        (json.dumps({"sub": user_id, "role": "authenticated", "is_anonymous": is_anonymous}),),
    )


def test_avatar_theme_rls_blocks_cross_account_and_guest_access() -> None:
    owner_id, other_id, guest_id = (str(uuid4()) for _ in range(3))

    with psycopg.connect(DSN) as connection:
        try:
            with connection.cursor() as cursor:
                for user_id, label, anonymous in (
                    (owner_id, "owner", False),
                    (other_id, "other", False),
                    (guest_id, "guest", True),
                ):
                    email = None if anonymous else f"avatar-theme-{label}-{user_id}@example.test"
                    cursor.execute(
                        "insert into auth.users (id, email, is_anonymous) values (%s, %s, %s)",
                        (user_id, email, anonymous),
                    )
                    cursor.execute(
                        "insert into public.profiles (id, email, username, avatar_theme)"
                        " values (%s, %s, %s, %s)",
                        (user_id, email, f"avatar-theme-{label}-{user_id[:8]}", "ocean" if label == "owner" else "teal"),
                    )

                # Keep the guest session valid so its denial below comes from
                # the avatar-theme policy rather than the older session guard.
                cursor.execute(
                    "insert into public.guest_workspaces (user_id, expires_at)"
                    " values (%s, now() + interval '7 days')",
                    (guest_id,),
                )

                _set_authenticated_claims(cursor, user_id=owner_id, is_anonymous=False)
                cursor.execute(
                    "select avatar_theme from public.profiles where id = %s",
                    (owner_id,),
                )
                assert cursor.fetchone() == ("ocean",)
                cursor.execute(
                    "select avatar_theme from public.profiles where id = %s",
                    (other_id,),
                )
                assert cursor.fetchone() is None
                cursor.execute(
                    "update public.profiles set avatar_theme = 'plum' where id = %s"
                    " returning id",
                    (owner_id,),
                )
                owner_update = cursor.fetchone()
                assert owner_update is not None
                assert str(owner_update[0]) == owner_id
                cursor.execute(
                    "update public.profiles set avatar_theme = 'plum' where id = %s"
                    " returning id",
                    (other_id,),
                )
                assert cursor.fetchone() is None

                cursor.execute("reset role")
                cursor.execute(
                    "select avatar_theme from public.profiles where id = %s",
                    (other_id,),
                )
                assert cursor.fetchone() == ("teal",)

                _set_authenticated_claims(cursor, user_id=guest_id, is_anonymous=True)
                cursor.execute(
                    "select avatar_theme from public.profiles where id = %s",
                    (guest_id,),
                )
                assert cursor.fetchone() is None
                cursor.execute(
                    "update public.profiles set avatar_theme = 'gold' where id = %s"
                    " returning id",
                    (guest_id,),
                )
                assert cursor.fetchone() is None
        finally:
            connection.rollback()
