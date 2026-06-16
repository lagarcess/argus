from __future__ import annotations

from babel import Locale, UnknownLocaleError


def response_language_instruction(language: str | None) -> str:
    normalized = (language or "en").strip() or "en"
    try:
        locale = Locale.parse(normalized.replace("_", "-"), sep="-")
    except (TypeError, ValueError, UnknownLocaleError):
        return (
            "Answer in the user's preferred language when it is clear from their "
            "message; otherwise answer in English."
        )
    language_name = locale.get_display_name("en")
    return f"Answer in {language_name}."
