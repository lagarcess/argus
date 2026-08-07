"""Typed contracts for the research rail.

Frozen models keep provider output immutable once parsed; sanitization happens
at parse time so every downstream consumer sees the same bounded shape.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

QuestionShape = Literal["fast", "balanced", "thorough"]
CapabilityClass = Literal[
    "fast_quote",
    "balanced_lookup",
    "thorough_research",
    "screening",
    "peer_expansion",
]

MAX_ANSWER_CHARS = 20_000
MAX_SOURCES = 5
MAX_PEER_PAIRS = 12
MAX_URL_CHARS = 512

# Perplexity-owned hosts never appear in user-facing output: route receipts and
# the cost ledger own provider provenance, not prose or sidecars.
PROVIDER_HOSTS = ("perplexity.ai",)


class ResearchUnavailableError(Exception):
    """Raised when the research provider cannot serve a request."""

    def __init__(self, reason: str, detail: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


class ResearchUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    invocations: int = 0
    model: str = ""
    latency_ms: int = 0
    cost_usd: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None


class ResearchNamePair(BaseModel):
    """A (name, symbol) pair the provider surfaced. Untrusted until it passes
    Argus's own resolver, asset-class, and coverage gates."""

    model_config = ConfigDict(frozen=True)

    name: str
    symbol: str


class ResearchPacket(BaseModel):
    model_config = ConfigDict(frozen=True)

    answer_markdown: str
    categories: tuple[str, ...] = ()
    tickers: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    name_pairs: tuple[ResearchNamePair, ...] = ()
    usage: ResearchUsage = Field(default_factory=ResearchUsage)
    retrieved_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    background_id: str | None = None


class BackgroundPoll(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal[
        "queued", "in_progress", "completed", "failed", "cancelled", "incomplete"
    ]
    packet: ResearchPacket | None = None
    failure_detail: str | None = None

    @property
    def terminal(self) -> bool:
        return self.status not in ("queued", "in_progress")
