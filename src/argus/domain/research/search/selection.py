from __future__ import annotations

import os

from argus.domain.research.credentials import perplexity_api_key
from argus.domain.research.search.contracts import (
    SearchProvider,
    SearchUnavailableError,
)
from argus.domain.research.search.openrouter_web_search import (
    OpenRouterWebSearchProvider,
)
from argus.domain.research.search.perplexity_direct import PerplexityDirectProvider
from argus.llm.openrouter_key_policy import resolve_openrouter_api_key


def search_provider_for_config(*, provider_id: str) -> SearchProvider:
    """Resolve the configured adapter; unknown ids fail closed."""
    normalized = provider_id.strip().lower()
    if normalized == "perplexity_direct":
        return PerplexityDirectProvider(api_key=perplexity_api_key())
    if normalized == "openrouter_web_search":
        return OpenRouterWebSearchProvider(
            api_key=resolve_openrouter_api_key(),
            model=os.getenv("ARGUS_DISCOVERY_OPENROUTER_SEARCH_MODEL", ""),
        )
    raise SearchUnavailableError(
        reason="not_configured", detail=f"unknown_provider:{normalized}"
    )
