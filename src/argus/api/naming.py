from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from argus.llm.openrouter import (
    invoke_openrouter_json_schema_sync,
    log_openrouter_failure,
)

SUPPORTED_GOALS = {
    "learn_basics",
    "test_stock_idea",
    "build_passive_strategy",
    "explore_crypto",
    "surprise_me",
}

STARTER_PROMPTS = {
    "learn_basics": [
        "How do I start investing?",
        "Explain a market term simply",
        "What does buying every month mean?",
        "How do I test an idea?",
    ],
    "test_stock_idea": [
        "Buy Apple after big drops",
        "Hold Tesla for a year",
        "Compare Nvidia with Apple",
        "Test Microsoft when it starts rising",
    ],
    "build_passive_strategy": [
        "Buy SPY every month",
        "Compare a fund with a stock",
        "Test a simple long-term idea",
        "Start with a low-maintenance idea",
    ],
    "explore_crypto": [
        "Backtest Bitcoin halvings",
        "Hold Bitcoin for a year",
        "Compare Ethereum and Bitcoin",
        "Buy Bitcoin after big drops",
    ],
    "surprise_me": [
        "Show me something interesting",
        "Show me a simple first idea",
        "Test a familiar stock",
        "Compare two familiar assets",
    ],
}


class NameSuggestion(BaseModel):
    name: str


def resolve_language(language: str | None) -> Literal["en", "es-419"]:
    if (language or "en").lower().startswith("es"):
        return "es-419"
    return "en"


def get_starter_prompts(primary_goal: str | None) -> list[str]:
    goal = primary_goal if primary_goal in STARTER_PROMPTS else "surprise_me"
    return STARTER_PROMPTS[goal]


def suggest_entity_name(
    *,
    entity_type: Literal["conversation", "strategy", "collection"],
    context: str,
    language: str | None,
) -> str | None:
    try:
        resolved = resolve_language(language)
        response = invoke_openrouter_json_schema_sync(
            task="name_suggestion",
            schema_model=NameSuggestion,
            schema_name="name_suggestion",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Generate a concise user-facing name for Argus Alpha. "
                        "Max 6 words. No punctuation-only output. "
                        f"Entity type: {entity_type}. Language: {resolved}."
                    ),
                },
                {"role": "user", "content": context},
            ],
        )
        if response is None:
            return None
        candidate = response.name.strip()
        return candidate if candidate else None
    except Exception as exc:
        log_openrouter_failure(
            task="name_suggestion",
            model_name=None,
            exc=exc,
            message="Name suggestion failed",
        )
        return None
