from argus.domain.discovery_search.config import (
    DEFAULT_PROVIDER_ID,
    DiscoverySearchConfig,
    discovery_search_config,
)
from argus.domain.discovery_search.contracts import (
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
