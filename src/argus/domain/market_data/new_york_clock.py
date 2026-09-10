"""The one clock every reading of the user's "today" derives from.

Argus keeps the New York calendar the US markets keep, never the host's: a UTC
host is already on the next date after 20:00 ET.
"""

from __future__ import annotations

from datetime import date, datetime

from argus.domain.market_data.capabilities import EASTERN


def new_york_now() -> datetime:
    """The current instant on the New York clock."""
    return datetime.now(EASTERN)


def new_york_today() -> date:
    """Today by the New York calendar."""
    return new_york_now().date()
