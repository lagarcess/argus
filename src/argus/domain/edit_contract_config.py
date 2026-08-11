"""Feature gate for the in-place confirmation-card editing surface.

Default off. Three review rounds found real defects in the run-consumption
guard that protects non-turn card writes, so the surface ships dark and
the guard finishes as its own lane; the founder flips the flag at
promotion only once that lane closes. Everything conversational, the
compound edit contract, disclosure, scoped widening, and the accepted
value envelope, is turn-based and unaffected by this flag.
"""

from __future__ import annotations

import os

_TRUE_VALUES = {"1", "true", "yes", "on"}


def in_place_card_edits_enabled() -> bool:
    """Default-off kill switch; the founder flips it at promotion."""
    return (
        os.getenv("ARGUS_IN_PLACE_CARD_EDITS_ENABLED", "").strip().lower() in _TRUE_VALUES
    )
