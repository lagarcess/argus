"""The ``route_receipts.tier`` check, rendered from the runtime's tier owner.

``OpenRouterModelTier`` is the one owner of every tier a route receipt carries.
The migration that installs the active check is pinned to this rendering, and
the real-Postgres suite compares the applied check with the same owner, so a
tier added to the runtime without a migration fails CI.
"""

from __future__ import annotations

from typing import get_args

from argus.llm.openrouter_tasks import OpenRouterModelTier

TIER_CHECK_CONSTRAINT_NAME = "route_receipts_tier_check"


def render_tier_check_constraint() -> str:
    """The DDL that replaces the tier check with exactly the runtime's tiers."""
    tiers = ", ".join(f"'{tier}'" for tier in get_args(OpenRouterModelTier))
    return f"""alter table public.route_receipts
  drop constraint {TIER_CHECK_CONSTRAINT_NAME},
  add constraint {TIER_CHECK_CONSTRAINT_NAME}
    check (tier in ({tiers}));"""
