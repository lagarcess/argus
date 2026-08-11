"""One credential seam for the one Perplexity provider layer.

Both API paths — the direct Search API (``research.search``) and the Agent
API (``research.perplexity_agent``) — authenticate through this function, so
key sourcing can never drift between them.
"""

from __future__ import annotations

import os


def perplexity_api_key() -> str:
    """The configured key, stripped; empty string means not configured."""
    return os.getenv("PERPLEXITY_API_KEY", "").strip()
