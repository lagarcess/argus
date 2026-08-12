"""Static contract proof for the private access-welcome delivery migration."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _normalized_sql() -> str:
    migrations = sorted(
        (ROOT / "supabase" / "migrations").glob("*_add_access_welcome_deliveries.sql")
    )
    assert len(migrations) == 1
    return re.sub(r"\s+", " ", migrations[0].read_text()).strip().lower()


def test_access_welcome_delivery_migration_is_private_and_once_only() -> None:
    sql = _normalized_sql()
    assert "create table public.private_alpha_access_welcome_deliveries" in sql
    assert "recipient_email text primary key" in sql
    assert "content_version = 'private-alpha-access-welcome/v1'" in sql
    assert "enable row level security" in sql
    assert "from public, anon, authenticated, service_role" in sql
    assert "grant select, insert" in sql
    assert "create policy" not in sql


def test_access_welcome_delivery_migration_guards_direct_activation() -> None:
    sql = _normalized_sql()
    assert "complete_private_alpha_access_welcome" in sql
    assert "security invoker" in sql
    assert "require_private_alpha_access_welcome_delivery" in sql
    assert "new.role = 'user'" in sql
    assert "new.disabled_at is null" in sql
