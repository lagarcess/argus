"""Language-neutral conversation preview transport."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ConversationPreview(BaseModel):
    """Reader facts; retained assistant artifact prose is never a preview."""

    kind: Literal[
        "text",
        "result",
        "confirmation",
        "assumptions",
        "breakdown",
        "empty",
        "unavailable",
    ]
    text: str | None = Field(default=None, max_length=500)
    symbols: list[str] = Field(default_factory=list, max_length=5)
    template: str | None = None

    @model_validator(mode="after")
    def artifact_previews_have_no_prose(self) -> ConversationPreview:
        if self.kind != "text" and self.text is not None:
            raise ValueError("Artifact previews cannot contain stored prose.")
        return self
