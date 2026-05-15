from __future__ import annotations

from argus.domain.cadences import SUPPORTED_DCA_CADENCES
from argus.domain.engine_launch.models import Cadence


def resolve_dca_cadence(value: Cadence | None) -> str:
    normalized = (value or "weekly").lower()
    if normalized not in SUPPORTED_DCA_CADENCES:
        raise ValueError("unsupported_dca_cadence")
    return normalized
