"""The one owner of user-facing reply punctuation at the point it becomes visible.

Argus never shows an em dash in user-facing copy, in any language
(.agent/rules/coding-standards.md, founder-locked 2026-08-04). Model-written
replies reach the user through two doors, the live SSE frames and the
persisted assistant message, and both pass through here. A rewrite is
recorded on the turn so a model that keeps writing em dashes stays visible.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any

from loguru import logger

EM_DASH = "—"
REPLY_REWRITES_METADATA_KEY = "reply_rewrites"

_CLOSING_PUNCTUATION = ".,;:!?"
# A dash set directly between two figures, no space on either side, is the
# model's range notation ("5%—10%", "$1,000—$2,000"); a comma would change
# the fact, so the range keeps a hyphen in every language.


def _is_figure_char(char: str) -> bool:
    """A digit, any currency sign (Unicode category Sc) or a percent-like
    sign; a figure may open or close on any of them ("$1,000", "1.000€",
    "5%")."""
    return (
        char.isdigit()
        or unicodedata.category(char) == "Sc"
        or unicodedata.name(char, "").endswith(("PERCENT SIGN", "PER MILLE SIGN"))
    )


@dataclass(frozen=True)
class VisibleReply:
    text: str | None
    em_dash_count: int


def rewrite_visible_reply(
    text: str | None,
    *,
    surface: str,
    trailing: str = "sentence",
    left_tail: str = "",
) -> VisibleReply:
    """Replace every em dash with the comma the copy rule asks for, or the
    hyphen of a numeric range.

    ``trailing`` says what a dash with nothing after it means: the end of a
    whole reply ("sentence") or the end of a streamed token ("clause") whose
    continuation arrives in the next frame. ``left_tail`` is text already
    shown before this piece, so a dash at the start of a stream chunk is
    joined to the word that preceded it exactly as the whole reply would be.
    """
    if not isinstance(text, str) or EM_DASH not in text:
        return VisibleReply(text=text, em_dash_count=0)
    count = text.count(EM_DASH)
    rewritten = _without_em_dashes(text, trailing=trailing, left_tail=left_tail)
    logger.info(
        "Visible reply em dash rewritten surface={} count={}",
        surface,
        count,
        surface=surface,
        em_dash_count=count,
    )
    return VisibleReply(text=rewritten, em_dash_count=count)


def _without_em_dashes(text: str, *, trailing: str, left_tail: str = "") -> str:
    # A run of dashes with nothing but spaces between them is one dash: the
    # blank between them is not the end of anything, so the stream and the
    # final reply read it the same.
    split = text.split(EM_DASH)
    pieces = [
        split[0],
        *(piece for piece in split[1:-1] if piece.strip(" ")),
        *split[1:][-1:],
    ]
    result = pieces[0]
    for piece in pieces[1:]:
        raw_left = result or left_tail
        if (
            raw_left
            and piece
            and _is_figure_char(raw_left[-1])
            and _is_figure_char(piece[0])
        ):
            result = f"{result}-{piece}"
            continue
        left = result.rstrip(" ")
        # What the dash follows: this piece's own text, or the text already
        # shown when the dash opens a stream chunk.
        preceding = left or left_tail.rstrip(" ")
        right = piece.lstrip(" ")
        if not preceding or preceding.endswith("\n"):
            result = f"{left}{right}"
        elif not right or right.startswith("\n"):
            closer = "," if trailing == "clause" and not right else "."
            if not preceding.endswith(tuple(_CLOSING_PUNCTUATION)):
                left = f"{left}{closer}"
            result = f"{left}{right}"
        elif (
            preceding.endswith(tuple(_CLOSING_PUNCTUATION))
            or right[0] in _CLOSING_PUNCTUATION
        ):
            result = f"{left} {right}"
        else:
            result = f"{left}, {right}"
    return result


# Characters a stream chunk may end on that only mean something once the
# next chunk arrives: a dash needs its right-hand word, a space before a dash
# would otherwise be shown before the comma that replaces it.
_BOUNDARY_CHARS = frozenset({EM_DASH, " "})


class ReplyRewrites:
    """Per-turn accumulator: token frames and the final text share one count.

    Chunks are rewritten as the whole reply would be: a chunk's trailing
    boundary characters are held for the next chunk, and a chunk that opens
    on a dash reads the text already shown as what the dash follows, so the
    live stream and the persisted reply are the same text.
    """

    def __init__(self, *, surface: str) -> None:
        self.surface = surface
        self.em_dash_count = 0
        self._carry = ""
        self._shown_tail = ""

    def token(self, content: str) -> str:
        text = f"{self._carry}{content}"
        held = 0
        while held < len(text) and text[-1 - held] in _BOUNDARY_CHARS:
            held += 1
        if held and held < len(text):
            self._carry, text = text[len(text) - held :], text[: len(text) - held]
        elif held:
            self._carry = text
            return ""
        else:
            self._carry = ""
        rewritten = rewrite_visible_reply(
            text,
            surface=f"{self.surface}:token",
            trailing="clause",
            left_tail=self._shown_tail,
        )
        self.em_dash_count += rewritten.em_dash_count
        shown = rewritten.text or ""
        self._shown_tail = f"{self._shown_tail}{shown}"[-32:]
        return shown

    def flush(self) -> str:
        """Show what a chunk held for a next chunk that never came."""
        held, self._carry = self._carry, ""
        if not held:
            return ""
        rewritten = rewrite_visible_reply(
            held,
            surface=f"{self.surface}:token",
            trailing="sentence",
            left_tail=self._shown_tail,
        )
        self.em_dash_count += rewritten.em_dash_count
        shown = rewritten.text or ""
        self._shown_tail = f"{self._shown_tail}{shown}"[-32:]
        return shown

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
