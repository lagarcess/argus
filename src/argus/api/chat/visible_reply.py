"""The one owner of user-facing reply punctuation at the point it becomes visible.

Argus never shows an em dash in user-facing copy, in any language
(.agent/rules/coding-standards.md, founder-locked 2026-08-04). Model-written
replies reach the user through two doors, the live SSE frames and the
persisted assistant message, and both pass through here. A rewrite is
recorded on the turn so a model that keeps writing em dashes stays visible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loguru import logger

EM_DASH = "—"
REPLY_REWRITES_METADATA_KEY = "reply_rewrites"

_CLOSING_PUNCTUATION = ".,;:!?"


@dataclass(frozen=True)
class VisibleReply:
    text: str | None
    em_dash_count: int


def rewrite_visible_reply(
    text: str | None, *, surface: str, trailing: str = "sentence"
) -> VisibleReply:
    """Replace every em dash with the comma the copy rule asks for.

    ``trailing`` says what a dash with nothing after it means: the end of a
    whole reply ("sentence") or the end of a streamed token ("clause") whose
    continuation arrives in the next frame.
    """
    if not isinstance(text, str) or EM_DASH not in text:
        return VisibleReply(text=text, em_dash_count=0)
    count = text.count(EM_DASH)
    rewritten = _without_em_dashes(text, trailing=trailing)
    logger.info(
        "Visible reply em dash rewritten surface={} count={}",
        surface,
        count,
        surface=surface,
        em_dash_count=count,
    )
    return VisibleReply(text=rewritten, em_dash_count=count)


def _without_em_dashes(text: str, *, trailing: str) -> str:
    pieces = text.split(EM_DASH)
    result = pieces[0]
    for piece in pieces[1:]:
        left = result.rstrip(" ")
        right = piece.lstrip(" ")
        if not left or left.endswith("\n"):
            result = f"{left}{right}"
        elif not right or right.startswith("\n"):
            closer = "," if trailing == "clause" and not right else "."
            if not left.endswith(tuple(_CLOSING_PUNCTUATION)):
                left = f"{left}{closer}"
            result = f"{left}{right}"
        elif (
            left.endswith(tuple(_CLOSING_PUNCTUATION)) or right[0] in _CLOSING_PUNCTUATION
        ):
            result = f"{left} {right}"
        else:
            result = f"{left}, {right}"
    return result


class ReplyRewrites:
    """Per-turn accumulator: token frames and the final text share one count."""

    def __init__(self, *, surface: str) -> None:
        self.surface = surface
        self.em_dash_count = 0

    def token(self, content: str) -> str:
        rewritten = rewrite_visible_reply(
            content, surface=f"{self.surface}:token", trailing="clause"
        )
        self.em_dash_count += rewritten.em_dash_count
        return rewritten.text or ""

    def text(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        rewritten = rewrite_visible_reply(value, surface=self.surface)
        self.em_dash_count += rewritten.em_dash_count
        return rewritten.text

    def finalize(
        self,
        *,
        runtime_result: dict[str, Any],
        metadata: dict[str, Any],
        assistant_text: str | None,
        persisted_text: str | None,
    ) -> tuple[str | None, str | None]:
        """Rewrite every visible copy of the reply and record the turn's count."""
        final_count = 0
        for key in ("assistant_response", "assistant_prompt"):
            value = runtime_result.get(key)
            if isinstance(value, str):
                rewritten = rewrite_visible_reply(value, surface=self.surface)
                runtime_result[key] = rewritten.text
                final_count = max(final_count, rewritten.em_dash_count)
        assistant = rewrite_visible_reply(assistant_text, surface=self.surface)
        persisted = rewrite_visible_reply(persisted_text, surface=self.surface)
        final_count = max(final_count, assistant.em_dash_count, persisted.em_dash_count)
        # Streamed tokens and the final text are the same reply; count it once.
        self.em_dash_count = max(self.em_dash_count, final_count)
        if self.em_dash_count:
            record = {"em_dash": self.em_dash_count}
            metadata[REPLY_REWRITES_METADATA_KEY] = record
            runtime_result[REPLY_REWRITES_METADATA_KEY] = dict(record)
        return assistant.text, persisted.text
