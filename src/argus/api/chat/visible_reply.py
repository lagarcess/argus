"""Stream and final reply accounting using the shared punctuation owner."""

from typing import Any

from argus.domain.visible_reply import (
    EM_DASH as EM_DASH,
)
from argus.domain.visible_reply import (
    rewrite_visible_reply as rewrite_visible_reply,
)

REPLY_REWRITES_METADATA_KEY = "reply_rewrites"


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
