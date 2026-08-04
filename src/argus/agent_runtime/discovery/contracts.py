from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DISCOVERY_SIDECAR_SCHEMA_VERSION = "argus_discovery/v1"

MAX_RAW_CANDIDATES = 8
MAX_UNVERIFIED_NAMES = 3
MAX_CANDIDATE_NAME_CHARS = 120
MAX_REASON_CHARS = 200
MAX_SYMBOL_GUESS_CHARS = 12


class ExtractedCandidate(BaseModel):
    """One untrusted candidate named by the extraction call."""

    name: str = ""
    symbol_guess: str = ""
    reason_text: str = ""
    source_indices: list[int] = Field(default_factory=list)


class DiscoveryExtraction(BaseModel):
    """Structured extraction output over untrusted search snippets."""

    candidates: list[ExtractedCandidate] = Field(default_factory=list)

    def __init__(self, **data: object) -> None:
        candidates = data.get("candidates")
        if isinstance(candidates, list):
            data["candidates"] = candidates[:MAX_RAW_CANDIDATES]
        super().__init__(**data)


class ValidatedCandidate(BaseModel):
    """A provider-resolved, bounded candidate eligible for selection."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    name: str
    asset_class: Literal["equity", "crypto", "currency_pair"]
    reason_text: str
    source_indices: tuple[int, ...] = ()
