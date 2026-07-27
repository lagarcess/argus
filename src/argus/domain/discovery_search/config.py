from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict

TRUE_VALUES = frozenset(("1", "true", "yes", "on"))

DEFAULT_PROVIDER_ID = "perplexity_direct"
DEFAULT_TIMEOUT_SECONDS = 8.0
DEFAULT_MAX_CANDIDATES = 5
DEFAULT_HOURLY_LIMIT = 10
DEFAULT_DAILY_LIMIT = 25

# The visible-candidate ceiling matches the 5-symbol run cap.
MAX_CANDIDATE_CEILING = 5


class DiscoverySearchConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool
    provider_id: str
    timeout_seconds: float
    max_candidates: int
    hourly_limit: int
    daily_limit: int


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def _env_float(name: str, default: float, *, minimum: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > minimum else default


def _env_int(name: str, default: int, *, minimum: int, maximum: int | None = None) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if value < minimum:
        return minimum
    if maximum is not None and value > maximum:
        return maximum
    return value


def discovery_search_config() -> DiscoverySearchConfig:
    """Read the grounded-discovery runtime config snapshot from the environment."""
    return DiscoverySearchConfig(
        enabled=_env_flag("ARGUS_GROUNDED_DISCOVERY_ENABLED"),
        provider_id=(
            os.getenv("ARGUS_DISCOVERY_SEARCH_PROVIDER", "").strip().lower()
            or DEFAULT_PROVIDER_ID
        ),
        timeout_seconds=_env_float(
            "ARGUS_DISCOVERY_SEARCH_TIMEOUT_SECONDS",
            DEFAULT_TIMEOUT_SECONDS,
            minimum=0.0,
        ),
        max_candidates=_env_int(
            "ARGUS_DISCOVERY_MAX_CANDIDATES",
            DEFAULT_MAX_CANDIDATES,
            minimum=1,
            maximum=MAX_CANDIDATE_CEILING,
        ),
        hourly_limit=_env_int(
            "ARGUS_DISCOVERY_HOURLY_LIMIT", DEFAULT_HOURLY_LIMIT, minimum=0
        ),
        daily_limit=_env_int(
            "ARGUS_DISCOVERY_DAILY_LIMIT", DEFAULT_DAILY_LIMIT, minimum=0
        ),
    )
