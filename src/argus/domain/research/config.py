"""Research rail flag and the three documented finance_search configurations.

The configuration ladder is locked by the research-to-test-rail spec section 3
from Perplexity's recommended configurations. One deviation is evidence-based:
the documentation's fast row says ``max_steps=1``, but a live probe on
2026-08-07 showed the first step is consumed by the finance skill load, so
``max_steps=1`` returns "I can't retrieve live market data" with zero tool
invocations even for an equity control. ``max_steps=2`` grounds correctly with
one invocation. Probe evidence: docs/reports/evidence/377/probes/.

The retrieval parameters (grounded-finance board, "Retrieval parameters") ride
the same spec: a model fallback chain, the strict typed-output schema, the
response language, the web search context size, a recency filter derived from
the question's data class, and the asking user's declared country as the user
location. They are configuration per question shape, derived by
:func:`retrieval_spec`; nothing here routes.
"""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from argus.domain.calculations.answer_request import (
    ANSWER_CALCULATION_INSTRUCTIONS,
    calculation_kinds_clause,
)
from argus.domain.research.cache import DataClass, data_class_for
from argus.domain.research.contracts import CapabilityClass, QuestionShape

TRUE_VALUES = {"1", "true", "yes", "on"}

RecencyFilter = Literal["hour", "day", "week", "month", "year"]
SearchContextSize = Literal["low", "medium", "high"]

# Provider limits on the Agents API: a fallback chain of at most five models
# and a domain filter of at most twenty entries.
MAX_FALLBACK_MODELS = 5
MAX_SOURCE_DOMAINS = 20

# The two models the pricing validator can reconcile, so a fallback never
# turns into an unpriced invoice. Each tier lists the other as its fallback:
# a provider hiccup on the primary is served by the second model rather than
# by nothing. The invoice names the model that served, so a fallback is
# visible on every receipt.
PRIMARY_MODEL = "openai/gpt-5.6-sol"
THOROUGH_MODEL = "anthropic/claude-opus-4-7"

# System-level contract for every typed retrieval call. This text steers
# Perplexity, not the interpreter; it is frozen by the recorded probe in
# tests/research, not by the interpreter fingerprint.
_ANSWER_OPENING = (
    "Answer the reader's money question the way a trusted expert would, as fully "
    "as the best search answer. Open answer_markdown with the direct answer in one "
    "or two sentences. Then, where it helps the reader, add short sections under "
    "### headings, a table when comparing options, the formula when math explains "
    "the answer, one worked example, and steps the reader can check. Write for a "
    "curious non-expert. Every factual claim comes from a page retrieved in this "
    "response and every current figure is retrieved with its as-of date, never "
    "answered from memory; when a figure cannot be found, say that it could not be "
    "found and answer the rest. List in source_urls every retrieved page the "
    "answer relies on; the reader sees those pages in the sources panel, so write "
    "no links and no list of sources, and never mention tools, "
    "providers or models. Reply in the requested JSON shape. Every figure "
    "answer_markdown states in digits appears once in rows, with the URL of the "
    "retrieved page it was read from. A figure a page publishes, such as a "
    "product's price, a rate, a fee or local inflation, is retrieved and cited, "
    "never asked of the reader; when the reader named no exact product, retrieve "
    "typical examples and say which. Lay out the options with their math and "
    "trade-offs and let the reader decide: never say which product to choose, what "
    "to do or prefer, or a rule of thumb such as rebalancing once a year, and never "
    "state a forecast as fact. "
)
# A choice that turns on a future figure nobody can cite is answered with the
# recent past. Scenario answers never carry it: a forward-valuation question
# keeps decision 10's computed scenarios.
HISTORY_NOT_FORECAST_INSTRUCTION = (
    "When a choice turns on a future figure nobody can cite, such as an exchange "
    "rate or a price, do not project it; show what the recent past did with cited "
    "figures, computed by Argus and labeled as history, not a forecast. "
)
_ANSWER_REST = (
    "Write dates as dates, not in words. follow_up_questions "
    "holds two to four short questions, in the reader's language, that this reader "
    "is likely to ask next and Argus can answer. When the question asks for a "
    "figure that arithmetic on specific figures answers, such as what a fund's fees cost "
    "over ten years, fill calculations from the retrieved figures and assumptions "
    "you state, or leave the figures only the reader knows null so Argus offers "
    "them; never answer such a question with prose and follow-up questions alone. "
    "When a calculation needs a "
    "figure only the reader knows, leave that input null and write answer_markdown "
    "without that calculation's results: Argus offers the reader the calculation "
    "with that figure left to enter. When the reader leaves out a detail the math "
    "needs, such as how often interest compounds, assume the likeliest one, say "
    "plainly what you assumed, and fill a calculation for each option the reader "
    "weighs. When the answer turns on a figure only the reader knows, such as their "
    "own balance or rate, fill calculations anyway with that figure left null so "
    "Argus offers it, even when nothing else is computed. When the request is not a "
    "money question, or "
    "asks Argus to place a trade, move money or act on an account, set declined to "
    "true, retrieve nothing, and write answer_markdown as one or two plain sentences "
    "saying Argus does not do that and what it can help with instead, with no "
    "figures, no calculations and no follow-up questions. "
    + ANSWER_CALCULATION_INSTRUCTIONS
    + calculation_kinds_clause()
)
RETRIEVAL_INSTRUCTIONS = _ANSWER_OPENING + HISTORY_NOT_FORECAST_INSTRUCTION + _ANSWER_REST

# The same contract, without the history line, for a question whose answer is
# computed (decision 10): the answer returns its calculation with every input's
# source, and Argus computes the scenario figures itself. Frozen by its own recording under
# docs/reports/evidence/grounded-math/probes.
SCENARIO_RETRIEVAL_INSTRUCTIONS = (
    _ANSWER_OPENING
    + _ANSWER_REST
    + (
        "This question is answered by a calculation: fill calculations with "
        "valuation_scenarios unless another listed kind fits the question better, "
        "with the current price from market_data and every other input from a page "
        "or a stated assumption. Never compute the answer, scenario values, ranges "
        "or future figures yourself, and never present one number as the future."
    )
)


def research_rail_enabled() -> bool:
    """Default-off kill switch; the founder flips it at promotion."""
    return os.getenv("ARGUS_RESEARCH_RAIL_ENABLED", "").strip().lower() in TRUE_VALUES


class RetrievalLocation(BaseModel):
    """Where the reader is, in the provider's own shape."""

    model_config = ConfigDict(frozen=True)

    country: str
    region: str | None = None
    city: str | None = None

    @field_validator("country")
    @classmethod
    def _iso_alpha_2(cls, value: str) -> str:
        code = value.strip().upper()
        if len(code) != 2 or not code.isalpha():
            raise ValueError("country must be an ISO 3166-1 alpha-2 code")
        return code


class ResearchConfigSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    shape: QuestionShape
    # Tried in order until one serves; the invoice names the one that did.
    models: tuple[str, ...]
    max_steps: int
    max_output_tokens: int
    tools: tuple[str, ...]
    reasoning_effort: Literal["low", "medium", "high"] | None = None
    background: bool = False
    timeout_seconds: float = 45.0
    search_context_size: SearchContextSize | None = None
    # Request the strict typed shape (answer plus cited rows) instead of prose.
    typed_output: bool = True
    # The provider-facing contract sent with a typed request.
    instructions: str = RETRIEVAL_INSTRUCTIONS
    # Per-call retrieval facts, derived from the question by retrieval_spec().
    language: str | None = None
    location: RetrievalLocation | None = None
    recency: RecencyFilter | None = None
    source_domains: tuple[str, ...] = ()

    @property
    def model(self) -> str:
        return self.models[0]

    @field_validator("models")
    @classmethod
    def _bounded_chain(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        chain = tuple(model.strip() for model in value if model.strip())
        if not 1 <= len(chain) <= MAX_FALLBACK_MODELS:
            raise ValueError(f"models must name 1 to {MAX_FALLBACK_MODELS} models")
        return chain

    @field_validator("source_domains")
    @classmethod
    def _bounded_domains(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return normalized_source_domains(value)


def normalized_source_domains(domains: tuple[str, ...]) -> tuple[str, ...]:
    """Lower-cased registrable hosts, unique, within the provider's ceiling."""
    seen: list[str] = []
    for raw in domains:
        host = raw.strip().lower()
        host = host.removeprefix("https://").removeprefix("http://").split("/", 1)[0]
        if host and host not in seen:
            seen.append(host)
    if len(seen) > MAX_SOURCE_DOMAINS:
        raise ValueError(f"a domain filter holds at most {MAX_SOURCE_DOMAINS} domains")
    return tuple(seen)


RESEARCH_CONFIG_SPECS: dict[QuestionShape, ResearchConfigSpec] = {
    "fast": ResearchConfigSpec(
        shape="fast",
        models=(PRIMARY_MODEL, THOROUGH_MODEL),
        # Documented as 1; probed 2026-08-07 to need 2 (the skill load consumes
        # a step) and 2026-09-10 to need 4 when the ticker is not already
        # resolved: a lookup and then the quote, or the answer is "could not
        # be retrieved" (docs/reports/evidence/open-the-gates/probes/
        # nike-unresolved-fast-*.json). A step budget is room, never a rule;
        # the model stops when it has the figure.
        max_steps=4,
        max_output_tokens=1024,
        tools=("finance_search",),
        timeout_seconds=30.0,
    ),
    "balanced": ResearchConfigSpec(
        shape="balanced",
        models=(PRIMARY_MODEL, THOROUGH_MODEL),
        max_steps=5,
        max_output_tokens=2048,
        tools=("web_search", "finance_search", "fetch_url"),
        reasoning_effort="low",
        # A scenario answer (forecasts, targets and multiples, the arithmetic
        # written out) took 122s on this configuration and timed out at 75s
        # on every forward-looking question in the decision 10 after picture
        # (docs/reports/evidence/decision-10/probes/scenario-balanced-180s.json).
        # The ceiling is room, never a rule; a quick answer still returns quickly.
        timeout_seconds=150.0,
        search_context_size="medium",
    ),
    "thorough": ResearchConfigSpec(
        shape="thorough",
        models=(THOROUGH_MODEL, PRIMARY_MODEL),
        max_steps=10,
        max_output_tokens=4096,
        tools=("web_search", "finance_search", "fetch_url"),
        background=True,
        timeout_seconds=30.0,
        search_context_size="high",
    ),
}

# How old a web page may be, by the section 7 data class of the question.
# The class already says how fast the answer goes stale, which is the same
# fact a recency filter asks for, so freshness has one owner: a closed
# window is closed_ohlcv and is never filtered to the past week, and a
# current survey is movers and never cites a year-old page as today's move.
RECENCY_BY_DATA_CLASS: dict[DataClass, RecencyFilter | None] = {
    "quotes": "week",
    "movers": "week",
    "analyst_estimates": "month",
    "fundamentals": None,
    "peers_constituents": None,
    "closed_ohlcv": None,
    "filings_transcripts": None,
}


def iso_language(language_tag: str | None) -> str:
    """ISO 639-1 code from a BCP 47 tag: es-419 to es, en to en."""
    return str(language_tag or "en").split("-", 1)[0].strip().lower() or "en"


def retrieval_spec(
    shape: QuestionShape,
    *,
    question_kind: str | None,
    country: str | None,
    closed_period: bool = False,
    language_tag: str | None = "en",
    scenario: bool = False,
) -> ResearchConfigSpec:
    """The documented configuration for a shape, with this question's
    retrieval parameters: response language, the asking user's declared
    country as the location, recency by data class, and the scenario contract
    when the answer is computed from published inputs.

    ``country`` has no default: every caller says whose question it builds,
    and a user without a country sends no location."""
    return RESEARCH_CONFIG_SPECS[shape].model_copy(
        update={
            "language": iso_language(language_tag),
            "location": RetrievalLocation(country=country) if country else None,
            "recency": RECENCY_BY_DATA_CLASS[
                data_class_for(
                    question_kind=question_kind,
                    closed_period=closed_period,
                    scenario=scenario,
                )
            ],
            "instructions": (
                SCENARIO_RETRIEVAL_INSTRUCTIONS if scenario else RETRIEVAL_INSTRUCTIONS
            ),
        }
    )


# Chat must never hang: thorough runs go through background mode and the job
# lifecycle. The poller gives up after this deadline and fails the job honestly.
DEFAULT_BACKGROUND_DEADLINE_SECONDS = 600.0
BACKGROUND_POLL_INTERVAL_SECONDS = 5.0


def background_deadline_seconds() -> float:
    raw = os.getenv("ARGUS_RESEARCH_BACKGROUND_DEADLINE_SECONDS", "")
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_BACKGROUND_DEADLINE_SECONDS
    if value <= 0:
        return DEFAULT_BACKGROUND_DEADLINE_SECONDS
    return value


def capability_class_for_shape(
    shape: QuestionShape, *, screening: bool
) -> CapabilityClass:
    """The class describes the work, not the config tier it ran on.

    A market survey is screening whether it grounded on the balanced tier or
    the thorough one; metering reads the class, so it must not change when a
    shape is retuned."""
    if screening:
        return "screening"
    if shape == "fast":
        return "fast_quote"
    if shape == "balanced":
        return "balanced_lookup"
    return "thorough_research"


def declared_tool_names() -> frozenset[str]:
    """Every provider tool this rail is configured to use.

    Derived from the configurations themselves so a tool added there is
    covered the day it is configured, rather than the day someone remembers
    to extend a hand-written list.
    """
    return frozenset(
        tool for spec in RESEARCH_CONFIG_SPECS.values() for tool in spec.tools
    )
