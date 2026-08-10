"""Fail-closed target resolution for destructive operations scripts."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping
from urllib.parse import urlsplit


class DestructiveDatabaseTargetError(ValueError):
    """Raised before a destructive job can construct a database gateway."""


@dataclass(frozen=True)
class DestructiveDatabaseTarget:
    database_host: str
    supabase_host: str
    supabase_url: str = field(repr=False)


def resolve_destructive_database_target(
    environ: Mapping[str, str] | None = None,
) -> DestructiveDatabaseTarget:
    """Resolve only process-provided coordinates and validate their hosts."""

    source = os.environ if environ is None else environ
    database_url = str(source.get("DATABASE_URL") or "").strip()
    if not database_url:
        raise DestructiveDatabaseTargetError(
            "DATABASE_URL must be set explicitly in the process environment; "
            "dotenv discovery is disabled for destructive jobs."
        )
    database_host = _validated_host(
        database_url,
        name="DATABASE_URL",
        schemes={"postgres", "postgresql"},
    )

    supabase_url = str(
        source.get("SUPABASE_URL") or source.get("SUPABASE_PROJECT_URL") or ""
    ).strip()
    if not supabase_url:
        raise DestructiveDatabaseTargetError(
            "SUPABASE_URL or SUPABASE_PROJECT_URL must be set explicitly in the "
            "process environment for a destructive job."
        )
    supabase_host = _validated_host(
        supabase_url,
        name="SUPABASE_URL",
        schemes={"http", "https"},
    )

    if not str(source.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip():
        raise DestructiveDatabaseTargetError(
            "SUPABASE_SERVICE_ROLE_KEY must be set explicitly in the process "
            "environment for a destructive job."
        )

    return DestructiveDatabaseTarget(
        database_host=database_host,
        supabase_host=supabase_host,
        supabase_url=supabase_url,
    )


def pin_destructive_database_target(target: DestructiveDatabaseTarget) -> None:
    """Make the validated Supabase URL the exact value consumed downstream."""

    os.environ["SUPABASE_URL"] = target.supabase_url


def announce_destructive_database_target(target: DestructiveDatabaseTarget) -> None:
    """Print non-secret target evidence before gateway construction or queries."""

    print(
        "destructive database target: "
        f"database_host={target.database_host} "
        f"supabase_host={target.supabase_host}",
        flush=True,
    )


def _validated_host(url: str, *, name: str, schemes: set[str]) -> str:
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        # Accessing port catches malformed values such as `:not-a-port`.
        _ = parsed.port
    except ValueError as exc:
        raise DestructiveDatabaseTargetError(
            f"{name} must be an absolute URL with a valid host and port."
        ) from exc
    if parsed.scheme.lower() not in schemes or not host:
        expected = " or ".join(f"{scheme}://" for scheme in sorted(schemes))
        raise DestructiveDatabaseTargetError(
            f"{name} must use {expected} and include a host."
        )
    return host.lower()
