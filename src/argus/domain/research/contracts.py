"""Typed contracts for the research rail.

Frozen models keep provider output immutable once parsed; sanitization happens
at parse time so every downstream consumer sees the same bounded shape.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

from babel.numbers import list_currencies
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

QuestionShape = Literal["fast", "balanced", "thorough"]
# What a row's value measures. Declared by the provider under the strict
# schema, never inferred from the shape of its unit.
RowKind = Literal["currency", "percent", "multiple", "count"]

# The currency codes a currency row may name: the CLDR data Babel ships and
# keeps current (XCG arrived there with the 2025 release), not a copied
# snapshot of ISO 4217 that goes stale the next time the standard moves.
CURRENCY_CODES = frozenset(list_currencies())

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
MAX_PACKET_ROWS = 64

# Perplexity-owned hosts never appear in user-facing output: route receipts and
# the cost ledger own provider provenance, not prose or sidecars.
PROVIDER_HOSTS = ("perplexity.ai",)

# The provider-side name of the strict response schema every research answer
# is requested in. It identifies the schema in the provider's cache, so a
# schema change must travel with a new recorded probe under it.
TYPED_RETRIEVAL_SCHEMA_NAME = "argus_typed_retrieval"


# Operating rule 4 of the grounded-finance board: retrieval produces typed
# rows, never prose. The strict request schema the provider fills is derived
# from these two models, so the shape the model writes and the shape Argus
# reads share one owner. Class and attribute docstrings are the schema
# descriptions the provider reads: they steer Perplexity, not the
# interpreter, and are frozen by the recorded probe in tests/research rather
# than by the interpreter fingerprint.
class RetrievedRow(BaseModel):
    """One figure read from a retrieved page: whose it is, what it is, its number, what the number measures, its date and its citation."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    subject: str
    """The entity the figure describes, as the source names it: Apple, Banco Popular, Netflix."""
    symbol: str | None
    """The exchange ticker of the security the figure describes, or null."""
    label: str
    """What the figure is, in a few words: closing share price, one-year certificate rate, revenue growth FY2025."""
    value: float = Field(strict=True, allow_inf_nan=False)
    """The figure as a plain number: 8.25 for 8.25 percent, 1250000 for 1,250,000."""
    kind: RowKind
    """What the value measures: currency for a money amount, percent for a percentage, multiple for a ratio such as a P/E, count for a number of units such as shares."""
    unit: str
    """The unit of value: the ISO 4217 code of a money amount such as USD or DOP, % for a percentage, x for a multiple, the thing counted for a count."""
    as_of: str | None
    """The date the source gives for this figure as YYYY-MM-DD, or null when it gives none."""
    source_url: str | None
    """The URL cited for this figure, or null when no citation was supplied. Figures without a citation are published with a source limitation."""

    @field_validator("unit")
    @classmethod
    def _stripped(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def _currency_unit_is_a_code(self) -> "RetrievedRow":
        # A money amount names a currency that exists, by its ISO 4217 code,
        # held against maintained currency data rather than a copied list.
        if self.kind == "currency" and self.unit not in CURRENCY_CODES:
            raise ValueError("a currency row names its unit by ISO 4217 code")
        return self


class ResearchNamePair(BaseModel):
    """A (name, symbol) pair the provider surfaced. Untrusted until it passes
    Argus's own resolver, asset-class, and coverage gates."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    name: str
    """The entity's name as supplied by the answer or retrieved tool result."""
    symbol: str
    """The exchange symbol supplied for that named entity."""


class TypedRetrieval(BaseModel):
    """A grounded answer: prose for the reader, plus every figure it states as a cited row."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    answer_markdown: str
    """The answer for the reader in markdown: no links, no list of sources, no mention of tools, providers or models."""
    rows: list[RetrievedRow]
    """Every figure answer_markdown states, one row each, with the retrieved page it was read from."""
    name_pairs: list[ResearchNamePair] = Field(default_factory=list)
    """The assets answer_markdown names, each with its name and exchange symbol; an empty list when the answer names no assets."""


def typed_retrieval_json_schema() -> dict[str, Any]:
    """The strict request schema, derived from the model the parser validates.

    Provider strict mode requires every object to close additional
    properties, every property to be required and every definition to be
    inline; Pydantic's schema carries titles, defaults and ``$defs`` instead.
    """
    schema = TypedRetrieval.model_json_schema()
    definitions = schema.pop("$defs", {})
    return _strict_schema(schema, definitions)


def typed_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": TYPED_RETRIEVAL_SCHEMA_NAME,
            "strict": True,
            "schema": typed_retrieval_json_schema(),
        },
    }


def _strict_schema(node: Any, definitions: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        if "$ref" in node:
            name = str(node["$ref"]).rsplit("/", 1)[-1]
            return _strict_schema(definitions[name], definitions)
        strict = {
            key: _strict_schema(value, definitions)
            for key, value in node.items()
            if key not in ("title", "default")
        }
        if strict.get("type") == "object" and isinstance(strict.get("properties"), dict):
            strict["additionalProperties"] = False
            strict["required"] = list(strict["properties"])
        return strict
    if isinstance(node, list):
        return [_strict_schema(item, definitions) for item in node]
    return node


class ResearchUnavailableError(Exception):
    """Raised when the research provider cannot serve a request.

    ``usage`` carries the invoice of a response that was read far enough to
    establish one before being rejected. Argus paid for that response, so the
    turn that discards it still records its spend.
    """

    def __init__(
        self,
        reason: str,
        detail: str | None = None,
        *,
        usage: ResearchUsage | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail
        self.usage = usage


class ResearchPricingError(Exception):
    """An invoice cannot be reconciled; this says nothing about the answer."""

    def __init__(
        self,
        reason: str,
        detail: str,
        *,
        reported: Decimal | None = None,
        expected_min: Decimal | None = None,
        expected_max: Decimal | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail
        self.reported = reported
        self.expected_min = expected_min
        self.expected_max = expected_max


class ResearchUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    # Compatibility name for persisted/public evidence: finance_search only.
    # Grounding checks use the explicit per-tool fields below so web or URL
    # retrieval is not mistaken for model-only synthesis.
    # Counts come from the provider's invoice. None means the invoice did not
    # establish a count; it is never spelled as zero. Argus-built packets
    # that ran no provider call keep the default zero.
    invocations: int | None = Field(default=0, ge=0)
    finance_search_invocations: int | None = Field(default=0, ge=0)
    web_search_invocations: int | None = Field(default=0, ge=0)
    fetch_url_invocations: int | None = Field(default=0, ge=0)
    model: str = ""
    latency_ms: int = Field(default=0, ge=0)
    cost_usd: float | None = Field(default=None, ge=0.0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cache_creation_input_tokens: int | None = Field(default=None, ge=0)
    cache_read_input_tokens: int | None = Field(default=None, ge=0)


def combined_research_usage(usages: Sequence[ResearchUsage]) -> ResearchUsage:
    """The spend of every provider response one turn read, as one usage.

    A turn that called the provider twice paid twice, whichever response it
    published and whether or not it published any: counts, latency and cost
    add up. A count or cost the invoices did not all establish is unknown for
    the turn as a whole, never the part of it that was known, because half a
    total understates the spend as confidently as a wrong one.
    """
    if not usages:
        return ResearchUsage()
    if len(usages) == 1:
        return usages[0]

    def _summed(field: str) -> int | None:
        values = [getattr(usage, field) for usage in usages]
        if any(value is None for value in values):
            return None
        return sum(values)

    costs = [usage.cost_usd for usage in usages]
    models = [usage.model for usage in usages if usage.model]
    return ResearchUsage(
        invocations=_summed("invocations"),
        finance_search_invocations=_summed("finance_search_invocations"),
        web_search_invocations=_summed("web_search_invocations"),
        fetch_url_invocations=_summed("fetch_url_invocations"),
        model=models[-1] if models else "",
        latency_ms=sum(usage.latency_ms for usage in usages),
        cost_usd=None if any(cost is None for cost in costs) else sum(costs),
        input_tokens=_summed("input_tokens"),
        output_tokens=_summed("output_tokens"),
        cache_creation_input_tokens=_summed("cache_creation_input_tokens"),
        cache_read_input_tokens=_summed("cache_read_input_tokens"),
    )


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
    # Figures the answer states that carry a citation, as the model wrote it:
    # the page URL, or null for a figure read from the provider's own finance
    # data, whose evidence is the tool result and whose provider host is
    # scrubbed at parse time.
    rows: tuple[RetrievedRow, ...] = ()
    # True when the answer arrived in the typed retrieval shape. Prose under a
    # typed request is still delivered, and recorded as prose.
    typed_answer: bool = False
    # Figures the model wrote with no citation at all. Published beside the
    # cited rows; the turn names them under the answer as figures it could
    # not tie to a source, from their own typed subject and label.
    unsourced_rows: tuple[RetrievedRow, ...] = ()
    # Tool result items in the provider's output, by item type and in order.
    # This is the retrieval record; the invoice's tool counts are billing.
    tool_results: tuple[str, ...] = ()
    usage: ResearchUsage = Field(default_factory=ResearchUsage)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    background_id: str | None = None

    @property
    def published_rows(self) -> tuple[RetrievedRow, ...]:
        """All figures the answer publishes, with their original identities and citations."""
        return (*self.rows, *self.unsourced_rows)

    @property
    def candidate_name_pairs(self) -> tuple[ResearchNamePair, ...]:
        """Every typed candidate identity, retaining conflicting names for validation."""
        identities = dict.fromkeys(
            (symbol.strip().upper(), name)
            for symbol, name in (
                *((pair.symbol, pair.name) for pair in self.name_pairs),
                *((row.symbol, row.subject) for row in self.published_rows if row.symbol),
            )
            if symbol.strip()
        )
        return tuple(
            ResearchNamePair(symbol=symbol, name=name) for symbol, name in identities
        )


class BackgroundPoll(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal[
        "queued", "in_progress", "completed", "failed", "cancelled", "incomplete"
    ]
    packet: ResearchPacket | None = None
    failure_detail: str | None = None
    # Why a completed run's answer could not be read, and the invoice it was
    # billed at. The packet is gone; the spend it cost is not.
    failure_reason: str | None = None
    usage: ResearchUsage | None = None

    @property
    def terminal(self) -> bool:
        return self.status not in ("queued", "in_progress")
