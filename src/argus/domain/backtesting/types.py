from typing import Literal

from pydantic import BaseModel

CoverageAdjustmentReason = Literal[
    "none",
    "calendar_alignment",
    "provider_coverage_adjustment",
]


class CoverageLimitedBy(BaseModel):
    """The series whose own first bar is a later effective start."""

    symbol: str
    first_available: str
