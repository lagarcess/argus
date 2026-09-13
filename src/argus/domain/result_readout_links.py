"""Bound Breakdown hyperlinks to the sources returned with that draft."""

from __future__ import annotations

import re
from collections.abc import Sequence
from urllib.parse import urlsplit

from markdown_it import MarkdownIt
from markdown_it.common.utils import UNESCAPE_ALL_RE, unescapeAll
from markdown_it.rules_inline import autolink, link
from markdown_it.rules_inline.backticks import backtick
from markdown_it.rules_inline.state_inline import StateInline

from argus.domain.research.contracts import ResearchSource

_BARE_LINK = re.compile(
    r"(?:https?://|www\.)[^\s<>`]+|[\w.+-]+@[\w.-]+\.[a-z]{2,}", re.IGNORECASE
)
_MARKDOWN_PUNCTUATION = re.compile(r"([\\`*_{}\[\]<>()!])")


def _words(text: str) -> str:
    return _MARKDOWN_PUNCTUATION.sub(r"\\\1", text)


def _literal_url(text: str) -> str:
    # Inline code preserves the visible URL without GFM turning it back into a link.
    return f"`{text}`"


def _unlinked_label(label: str) -> str:
    pieces: list[str] = []
    cursor = 0
    for match in _BARE_LINK.finditer(label):
        pieces.extend(
            (_words(label[cursor : match.start()]), _literal_url(match.group()))
        )
        cursor = match.end()
    pieces.append(_words(label[cursor:]))
    return "".join(pieces)


def _visible_text_offsets(value: str) -> tuple[str, list[tuple[int, int]]]:
    """Decode CommonMark text while retaining each character's original span."""
    characters: list[str] = []
    offsets: list[tuple[int, int]] = []
    cursor = 0
    for match in UNESCAPE_ALL_RE.finditer(value):
        characters.extend(value[cursor : match.start()])
        offsets.extend((index, index + 1) for index in range(cursor, match.start()))
        decoded = unescapeAll(match.group())
        characters.extend(decoded)
        offsets.extend((match.start(), match.end()) for _ in decoded)
        cursor = match.end()
    characters.extend(value[cursor:])
    offsets.extend((index, index + 1) for index in range(cursor, len(value)))
    return "".join(characters), offsets


def returned_source_links(text: str, sources: Sequence[ResearchSource]) -> str:
    """Preserve named citations, title returned bare URLs, and unlink other URLs."""
    parser = MarkdownIt("commonmark", {"html": False})
    allowed = {parser.normalizeLink(source.url): source for source in sources}

    def named_link(url: str, source: ResearchSource) -> str:
        title = source.title.strip() or urlsplit(source.url).hostname or source.url
        return f"[{_words(title)}](<{url}>)"

    def plain_urls(value: str) -> str:
        # GFM autolinks decoded text, including entities and escaped punctuation.
        # Map replacements back to source spans so unrelated literal markup does
        # not become active Markdown merely because its entities were decoded.
        visible, offsets = _visible_text_offsets(value)
        pieces: list[str] = []
        cursor = 0
        for match in _BARE_LINK.finditer(visible):
            url = match.group()
            while url and (
                url[-1] in ".,;:!?"
                or (
                    url[-1] in ")]"
                    and url.count(url[-1]) > url.count({")": "(", "]": "["}[url[-1]])
                )
            ):
                url = url[:-1]
            normalized = parser.normalizeLink(url)
            source = allowed.get(normalized)
            start = offsets[match.start()][0]
            end = offsets[match.start() + len(url) - 1][1]
            pieces.extend(
                (
                    value[cursor:start],
                    named_link(normalized, source) if source else _literal_url(url),
                )
            )
            cursor = end
        pieces.append(value[cursor:])
        return "".join(pieces)

    # The block parser owns reference definitions and code blocks. Keep those
    # spans intact while using the inline parser's grammar for link destinations.
    env: dict = {}
    blocks = parser.parse(text, env)
    line_offsets = [0]
    for line in text.splitlines(keepends=True):
        line_offsets.append(line_offsets[-1] + len(line))
    spans: list[tuple[int, int, str]] = []
    for block in blocks:
        if block.type in {"fence", "code_block"} and block.map:
            start, end = (line_offsets[index] for index in block.map)
            spans.append((start, end, text[start:end]))
    for reference in env.get("references", {}).values():
        start, end = (line_offsets[index] for index in reference["map"])
        spans.append((start, end, text[start:end]))

    def capture(rule):
        def wrapped(state: StateInline, silent: bool) -> bool:
            start, token_start = state.pos, len(state.tokens)
            matched = rule(state, silent)
            if not matched or silent:
                return matched
            tokens = state.tokens[token_start:]
            opening = next((token for token in tokens if token.type == "link_open"), None)
            original = text[start : state.pos]
            if opening is not None:
                url = opening.attrGet("href") or ""
                label = "".join(
                    token.content
                    for token in tokens[tokens.index(opening) + 1 :]
                    if not token.nesting
                )
                source = allowed.get(url)
                if source is None:
                    original = _unlinked_label(label)
                elif opening.markup == "autolink" or _BARE_LINK.fullmatch(label):
                    original = named_link(url, source)
                spans.append((start, state.pos, original))
            elif any(token.type == "code_inline" for token in tokens):
                spans.append((start, state.pos, original))
            return True

        return wrapped

    parser.inline.ruler.at("link", capture(link))
    parser.inline.ruler.at("autolink", capture(autolink))
    parser.inline.ruler.at("backticks", capture(backtick))
    parser.inline.parse(text, parser, env, [])

    pieces: list[str] = []
    cursor = 0
    # Outer links/code blocks take precedence over spans inside their labels/body.
    for start, end, replacement in sorted(spans, key=lambda span: (span[0], -span[1])):
        if start < cursor:
            continue
        pieces.extend((plain_urls(text[cursor:start]), replacement))
        cursor = end
    pieces.append(plain_urls(text[cursor:]))
    return "".join(pieces)
