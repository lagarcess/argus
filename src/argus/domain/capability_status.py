from __future__ import annotations

from typing import Literal

# Shared, typed capability status used by the strategy and indicator registries and by
# the canonical capability_registry derivations. Kept in its own low-level module so
# strategy_capabilities.py, indicators.py, and capability_registry.py can all import it
# without an import cycle.
#
#   executable -> reachable end-to-end by a supported, user-facing path
#   draft      -> partially built / computes, but not yet a supported user-facing path
#   future     -> recognised but not yet computable / built
CapabilityStatus = Literal["executable", "draft", "future"]
