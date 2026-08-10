"""The direct Search path of the one Perplexity provider layer.

This package and ``research.perplexity_agent`` are the only two modules that
speak to Perplexity: direct Search here (source-backed result lists), the
Agent API there (finance_search grounding). One layer, two documented paths,
one credential seam (``research.credentials``). Nothing else in the codebase
may open its own Perplexity client.
"""

from argus.domain.research.search.config import (
    DEFAULT_PROVIDER_ID,
    DiscoverySearchConfig,
    discovery_search_config,
)
from argus.domain.research.search.contracts import (
    MAX_RESULTS,
    MAX_SNIPPET_CHARS,
    MAX_TITLE_CHARS,
    MAX_URL_CHARS,
    SearchProvider,
    SearchResult,
    SearchResultPacket,
    SearchUnavailableError,
    sanitize_search_result,
)

__all__ = [
    "DEFAULT_PROVIDER_ID",
    "DiscoverySearchConfig",
    "MAX_RESULTS",
    "MAX_SNIPPET_CHARS",
    "MAX_TITLE_CHARS",
    "MAX_URL_CHARS",
    "SearchProvider",
    "SearchResult",
    "SearchResultPacket",
    "SearchUnavailableError",
    "discovery_search_config",
    "sanitize_search_result",
]
