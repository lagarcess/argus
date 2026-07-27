from __future__ import annotations

import os

from argus.domain.discovery_search.contracts import (
    SearchProvider,
    SearchUnavailableError,
)
from argus.domain.discovery_search.openrouter_web_search import (
    OpenRouterWebSearchProvider,
)
from argus.domain.discovery_search.perplexity_direct import PerplexityDirectProvider


def search_provider_for_config(*, provider_id: str) -> SearchProvider:
    """Resolve the configured adapter; unknown ids fail closed."""
    normalized = provider_id.strip().lower()
    if normalized == "perplexity_direct":
        return PerplexityDirectProvider(
            api_key=os.getenv("PERPLEXITY_API_KEY", ""),
        )
    if normalized == "openrouter_web_search":
        return OpenRouterWebSearchProvider(
            api_key=os.getenv("OPENROUTER_API_KEY", ""),
            model=os.getenv("ARGUS_DISCOVERY_OPENROUTER_SEARCH_MODEL", ""),
        )
    raise SearchUnavailableError(
        reason="not_configured", detail=f"unknown_provider:{normalized}"
    )
