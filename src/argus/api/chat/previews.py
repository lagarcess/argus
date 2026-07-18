from __future__ import annotations

from collections.abc import Iterable
from typing import Any

try:
    from markdown_it import MarkdownIt
    from markdown_it.token import Token
except Exception:  # pragma: no cover - parser is optional runtime polish.
    MarkdownIt = None  # type: ignore[assignment]
    Token = object  # type: ignore[misc,assignment]


def plain_text_preview(content: str, max_length: int = 180) -> str | None:
    """Return deterministic sidebar preview text without markdown control marks."""

    if MarkdownIt is not None:
        preview = _preview_from_markdown(content)
    else:
        preview = _compact_text(content)
    if not preview:
        return None
    return preview[:max_length]


def is_degraded_clarification_compatibility_text(
    *,
    role: str,
    metadata: dict[str, Any] | None,
) -> bool:
    """Identify stored fallback copy that is display transport, not model history."""

    if role != "assistant" or not isinstance(metadata, dict):
        return False
    clarification = metadata.get("clarification")
    if not isinstance(clarification, dict):
        return False
    return clarification.get("prompt_source") != "llm_generated"


def _preview_from_markdown(content: str) -> str:
    parser = MarkdownIt("commonmark")
    tokens = parser.parse(content)
    return _compact_preview_tokens(_token_text(tokens))


def _token_text(tokens: Iterable[Token]) -> Iterable[str]:
    for token in tokens:
        if token.type in {"text", "code_inline"} and token.content:
            yield token.content
        elif token.type in {"softbreak", "hardbreak"}:
            yield " "
        if token.children:
            yield from _token_text(token.children)


def _compact_text(content: str) -> str:
    return " ".join(content.split())


def _compact_preview_tokens(values: Iterable[str]) -> str:
    """Join parsed markdown text for sidebar display without inferring intent."""

    pieces = [str(value) for value in values if str(value)]
    preview = ""
    for piece in pieces:
        text = _compact_text(piece)
        if not text:
            continue
        if not preview:
            preview = text
        elif text[0] in ".,;:!?)]}":
            preview += text
        elif preview[-1:] in "([{":
            preview += text
        else:
            preview += f" {text}"
    return preview
