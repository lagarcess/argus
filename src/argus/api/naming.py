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
    "en": {
        "learn_basics": [
            "How do I start testing an investing idea?",
            "Explain why people compare a stock to SPY.",
            "What does buying every month mean?",
            "How do I read a simple backtest?",
        ],
        "test_stock_idea": [
            "Test buying Apple this year so far.",
            "Hold Tesla over the last 12 months.",
            "Compare Nvidia with Apple over the last 6 months.",
            "Test buying Microsoft over the last 6 months.",
        ],
        "build_passive_strategy": [
            "Buy SPY every month over the last year.",
            "Compare SPY with Apple over the last 12 months.",
            "Test a simple buy-and-hold idea this year so far.",
            "Try weekly Nvidia buys over the last year.",
        ],
        "explore_crypto": [
            "Hold Bitcoin this year so far.",
            "Compare Ethereum and Bitcoin over the last 12 months.",
            "Test buying Solana over the last 6 months.",
            "Test a simple Bitcoin buy-and-hold over the last year.",
        ],
        "surprise_me": [
            "Test Apple against SPY over the last 12 months.",
            "Try Bitcoin this year so far.",
            "Test weekly Nvidia buys over the last year.",
            "Show me a simple first idea.",
        ],
    },
    "es-419": {
        "learn_basics": [
            "¿Cómo empiezo a probar una idea de inversión?",
            "Explícame por qué se compara una acción con SPY.",
            "¿Qué significa comprar todos los meses?",
            "¿Cómo leo un backtest simple?",
        ],
        "test_stock_idea": [
            "Prueba comprar Apple en lo que va del año.",
            "Mantén Tesla durante los últimos 12 meses.",
            "Compara Nvidia con Apple durante los últimos 6 meses.",
            "Prueba comprar Microsoft durante los últimos 6 meses.",
        ],
        "build_passive_strategy": [
            "Compra SPY cada mes durante el último año.",
            "Compara SPY con Apple durante los últimos 12 meses.",
            "Prueba una idea simple de comprar y mantener este año.",
            "Prueba compras semanales de Nvidia durante el último año.",
        ],
        "explore_crypto": [
            "Mantén Bitcoin en lo que va del año.",
            "Compara Ethereum y Bitcoin durante los últimos 12 meses.",
            "Prueba comprar Solana durante los últimos 6 meses.",
            "Prueba una idea simple de comprar y mantener Bitcoin durante el último año.",
        ],
        "surprise_me": [
            "Compara Apple con SPY durante los últimos 12 meses.",
            "Prueba Bitcoin en lo que va del año.",
            "Prueba compras semanales de Nvidia durante el último año.",
            "Muéstrame una primera idea simple.",
        ],
    },
}


class NameSuggestion(BaseModel):
    name: str


def resolve_language(language: str | None) -> Literal["en", "es-419"]:
    if (language or "en").lower().startswith("es"):
        return "es-419"
    return "en"


def get_starter_prompts(
    primary_goal: str | None,
    language: str | None = None,
) -> list[str]:
    resolved = resolve_language(language)
    prompts_by_goal = STARTER_PROMPTS[resolved]
    goal = primary_goal if primary_goal in prompts_by_goal else "surprise_me"
    return prompts_by_goal[goal]


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
