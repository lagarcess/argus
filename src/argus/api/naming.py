from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from argus.llm.openrouter import (
    invoke_openrouter_json_schema_sync,
    log_openrouter_failure,
)

STARTER_PROMPTS = {
    "en": [
        "Test Apple against SPY over the last 12 months.",
        "Try Bitcoin this year so far.",
        "Test weekly Nvidia buys over the last year.",
        "Show me a simple first idea.",
    ],
    "es-419": [
        "Compara Apple con SPY durante los últimos 12 meses.",
        "Prueba Bitcoin en lo que va del año.",
        "Prueba compras semanales de Nvidia durante el último año.",
        "Muéstrame una primera idea simple.",
    ],
}


class NameSuggestion(BaseModel):
    name: str


def resolve_language(language: str | None) -> Literal["en", "es-419"]:
    if (language or "en").lower().startswith("es"):
        return "es-419"
    return "en"


def get_starter_prompts(language: str | None = None) -> list[str]:
    return STARTER_PROMPTS[resolve_language(language)]


# A phone header shows roughly this much before it truncates, so the narrow
# budget is a generation rule rather than a clip applied after the fact.
NARROW_TITLE_MAX_WORDS = 3
WIDE_TITLE_MAX_WORDS = 6


def title_word_budget(viewport: str | None) -> int:
    return NARROW_TITLE_MAX_WORDS if viewport == "narrow" else WIDE_TITLE_MAX_WORDS


def constrain_to_word_budget(candidate: str, budget: int) -> str:
    """Hold a generated title to the budget the prompt asked for.

    A prompt is a request, not a guarantee. The contract says the backend owns
    the short form so a narrow header shows a title composed short rather than
    one the client clips, and that only holds if something here enforces it.

    Trimming is structural on purpose: taking the first words and dropping
    trailing punctuation, with no notion of which words matter. Anything
    smarter would need to know the language, and choosing behaviour by language
    is what this codebase does not do.
    """

    words = candidate.split()
    if budget <= 0 or len(words) <= budget:
        return candidate.strip()
    kept = " ".join(words[:budget])
    # A cut mid-phrase can leave a dangling comma or dash that reads as damage.
    return kept.rstrip(" ,;:-–—/&").strip()


def suggest_entity_name(
    *,
    entity_type: Literal["conversation"],
    context: str,
    language: str | None,
    viewport: str | None = None,
) -> str | None:
    try:
        resolved = resolve_language(language)
        budget = title_word_budget(viewport)
        response = invoke_openrouter_json_schema_sync(
            task="name_suggestion",
            schema_model=NameSuggestion,
            schema_name="name_suggestion",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Generate a concise user-facing name for Argus Alpha. "
                        f"Max {budget} words. "
                        "No punctuation-only output. "
                        f"Entity type: {entity_type}. Language: {resolved}."
                    ),
                },
                {"role": "user", "content": context},
            ],
        )
        if response is None:
            return None
        candidate = constrain_to_word_budget(response.name.strip(), budget)
        return candidate if candidate else None
    except Exception as exc:
        log_openrouter_failure(
            task="name_suggestion",
            model_name=None,
            exc=exc,
            message="Name suggestion failed",
        )
        return None
