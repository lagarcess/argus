from __future__ import annotations

# Model-tier environment variable names consumed by openrouter.py's candidate
# resolution. Keys are OpenRouterModelTier values; kept as plain strings here
# so this module stays import-cycle-free.
TIER_PRIMARY_ENV: dict[str, tuple[str, ...]] = {
    "utility": ("ARGUS_UTILITY_MODEL",),
    "chat": ("ARGUS_CHAT_MODEL",),
    "structured": ("ARGUS_STRUCTURED_MODEL",),
    "context": ("ARGUS_CONTEXT_MODEL",),
}

TIER_FALLBACK_ENV: dict[str, tuple[str, ...]] = {
    "utility": ("ARGUS_UTILITY_FALLBACK_MODEL",),
    "chat": ("ARGUS_CHAT_FALLBACK_MODEL",),
    "structured": ("ARGUS_STRUCTURED_FALLBACK_MODEL",),
    "context": ("ARGUS_CONTEXT_FALLBACK_MODEL",),
}
