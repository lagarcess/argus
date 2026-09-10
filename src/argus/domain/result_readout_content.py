"""Creation-time readout transport. Legacy prose can never acquire this stamp."""

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

ReadoutSurface = Literal["quick_take", "breakdown"]
READOUT_METADATA_KEYS = (
    "result_readout_content",
    "result_readout_source",
    "result_readout_fallback_used",
    "result_readout_failure_mode",
)


class ResultReadoutContent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["result_readout/v1"]
    surface: ReadoutSurface
    language: Literal["en", "es-419"]
    text: str | None

    @field_validator("text")
    @classmethod
    def complete_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("readout text must be complete or null")
        return value


def validated_readout(value: Any) -> dict[str, Any] | None:
    try:
        return ResultReadoutContent.model_validate(value).model_dump()
    except (ValidationError, TypeError):
        return None


def readout_metadata(
    *,
    surface: ReadoutSurface,
    text: str | None,
    language: str,
    source: str,
    fallback_used: bool,
    failure_mode: str | None = None,
) -> dict[str, Any]:
    """Stamp a completed composition, never a historical read or raw draft."""
    normalized_language = language.lower().replace("_", "-").split("-")[0]
    accepted = text.strip() if isinstance(text, str) and not fallback_used else None
    content = validated_readout(
        {
            "schema_version": "result_readout/v1",
            "surface": surface,
            "language": "es-419" if normalized_language == "es" else normalized_language,
            "text": accepted or None,
        }
    )
    fallback_used = fallback_used or content is None or not accepted
    return {
        "result_readout_content": content,
        "result_readout_source": source,
        "result_readout_fallback_used": fallback_used,
        "result_readout_failure_mode": failure_mode,
    }


def readout_metadata_from_stage(
    patch: Mapping[str, Any], *, language: str
) -> dict[str, Any]:
    return readout_metadata(
        surface="quick_take",
        text=patch.get("assistant_response"),
        language=language,
        source=patch.get("assistant_response_source") or "deterministic_fallback",
        fallback_used=patch.get("assistant_response_fallback_used") is not False,
        failure_mode=patch.get("assistant_response_failure_mode"),
    )


def stored_readout_metadata(card: Any) -> dict[str, Any]:
    """Derive transport copies from the run's creation-time card metadata."""
    if not isinstance(card, Mapping):
        return {}
    content = validated_readout(card.get("result_readout_content"))
    if content is None:
        return {}
    return {
        **{key: card[key] for key in READOUT_METADATA_KEYS if key in card},
        "result_readout_content": content,
    }
