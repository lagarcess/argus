"""Research rail flag and the three documented finance_search configurations.

The configuration ladder is locked by the research-to-test-rail spec section 3
from Perplexity's recommended configurations. One deviation is evidence-based:
the documentation's fast row says ``max_steps=1``, but a live probe on
2026-08-07 showed the first step is consumed by the finance skill load, so
``max_steps=1`` returns "I can't retrieve live market data" with zero tool
invocations even for an equity control. ``max_steps=2`` grounds correctly with
one invocation. Probe evidence: docs/reports/evidence/research-rail/probes/.
"""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, ConfigDict

from argus.domain.research.contracts import CapabilityClass, QuestionShape

TRUE_VALUES = {"1", "true", "yes", "on"}


def research_rail_enabled() -> bool:
    """Default-off kill switch; the founder flips it at promotion."""
    return os.getenv("ARGUS_RESEARCH_RAIL_ENABLED", "").strip().lower() in TRUE_VALUES


class ResearchConfigSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    shape: QuestionShape
    model: str
    max_steps: int
    max_output_tokens: int
    tools: tuple[str, ...]
    reasoning_effort: Literal["low", "medium", "high"] | None = None
    background: bool = False
    timeout_seconds: float = 45.0


RESEARCH_CONFIG_SPECS: dict[QuestionShape, ResearchConfigSpec] = {
    "fast": ResearchConfigSpec(
        shape="fast",
        model="openai/gpt-5.6-sol",
        # Documented as 1; probed to need 2 (skill load consumes a step).
        max_steps=2,
        max_output_tokens=1024,
        tools=("finance_search",),
        timeout_seconds=30.0,
    ),
    "balanced": ResearchConfigSpec(
        shape="balanced",
        model="openai/gpt-5.6-sol",
        max_steps=5,
        max_output_tokens=2048,
        tools=("web_search", "finance_search", "fetch_url"),
        reasoning_effort="low",
        timeout_seconds=75.0,
    ),
    "thorough": ResearchConfigSpec(
        shape="thorough",
        model="anthropic/claude-opus-4-7",
        max_steps=10,
        max_output_tokens=4096,
        tools=("web_search", "finance_search", "fetch_url"),
        background=True,
        timeout_seconds=30.0,
    ),
}

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
