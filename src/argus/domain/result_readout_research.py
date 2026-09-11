"""The one research configuration for model-written text about a completed run.

The Breakdown and every answer in the conversation after a result call the same
model with the same tool limits, so a change to either reaches both.
"""

from __future__ import annotations

from argus.domain.research.config import ResearchConfigSpec
from argus.domain.research.perplexity_agent import StructuredAgentLimits

RESULT_RESEARCH_MODEL = "openai/gpt-5.6-luna"
RESULT_RESEARCH_LIMITS = StructuredAgentLimits(
    max_tool_calls=4,
    parallel_tool_calls=False,
    web_search_max_tokens=8000,
    web_search_max_tokens_per_page=2000,
    web_search_max_results=4,
    fetch_url_max_urls=2,
    fetch_url_total_budget_tokens=8000,
)


def result_research_spec(
    language: str, *, timeout_seconds: float = 75.0
) -> ResearchConfigSpec:
    return ResearchConfigSpec(
        shape="balanced",
        models=(RESULT_RESEARCH_MODEL,),
        max_steps=3,
        max_output_tokens=2200,
        tools=("web_search", "fetch_url"),
        timeout_seconds=timeout_seconds,
        language=language.split("-", 1)[0],
    )
