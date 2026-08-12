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
# Parsing must retain enough citations for question-aware publisher selection
# after retrieval. The public drawer still exposes at most MAX_SOURCES.
MAX_PACKET_SOURCES = 64
MAX_PEER_PAIRS = 12
# Survey answers name many assets and lead with whatever moved most, which is
# often untradable here; the packet keeps enough of them that the resolver can
# still find one the user can test.
MAX_PACKET_TICKERS = 32
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

    # Compatibility name for persisted/public evidence: finance_search only.
    # Grounding checks use the explicit per-tool fields below so web or URL
    # retrieval is not mistaken for model-only synthesis.
    invocations: int = Field(default=0, ge=0)
    finance_search_invocations: int = Field(default=0, ge=0)
    web_search_invocations: int = Field(default=0, ge=0)
    fetch_url_invocations: int = Field(default=0, ge=0)
    model: str = ""
    latency_ms: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cache_creation_input_tokens: int | None = Field(default=None, ge=0)
    cache_read_input_tokens: int | None = Field(default=None, ge=0)


class ResearchNamePair(BaseModel):
    """A (name, symbol) pair the provider surfaced. Untrusted until it passes
    Argus's own resolver, asset-class, and coverage gates."""

    model_config = ConfigDict(frozen=True)

    name: str
    symbol: str


class ResearchSource(BaseModel):
    """One citation the packet actually returned.

    Web search citations arrive in their own output items and, for some
    models, as annotations on the answer chunk. Both are the same evidence
    and both land here; provider-identity URLs never do.
    """

    model_config = ConfigDict(frozen=True)

    url: str
    title: str = ""
    source_date: str | None = None


class ResearchPacket(BaseModel):
    model_config = ConfigDict(frozen=True)

    answer_markdown: str
    categories: tuple[str, ...] = ()
    tickers: tuple[str, ...] = ()
    sources: tuple[ResearchSource, ...] = ()
    name_pairs: tuple[ResearchNamePair, ...] = ()
    usage: ResearchUsage = Field(default_factory=ResearchUsage)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
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
