"""One asset-identity vocabulary for every runnable row.

Rows across the app used to name assets three different ways: legal listing
names with a bracketed ticker on research rows, ``TICKER · Legal Name`` on
discovery rows, and parenthesized tickers in prose. This module is the one
answer: a short display name a person would say, plus the resolver-verified
ticker carried as its own typed part so the client can render it as a badge
instead of punctuation.

Shortening is conservative and structural. It strips the legal-form suffixes
the exchange appends to every listing, never words that distinguish one
company from another, and it never invents a name: every word that survives
came from what the resolver returned, in the order it returned them. A share
class is distinguishing, so it is kept and re-attached after the boilerplate
in front of it is stripped. When stripping would leave nothing meaningful,
the resolver's name stands unchanged.
"""

from __future__ import annotations

import re
from typing import Any

# Trailing listing boilerplate, longest forms first so "Common Stock" goes
# before "Stock". Every entry is exchange bookkeeping, never a distinguishing
# word: "Class A" stays, because share classes are how GOOG and GOOGL differ.
_SUFFIX_PATTERNS: tuple[str, ...] = (
    r"common stock",
    r"ordinary shares",
    r"american depositary shares",
    r"depositary shares",
    r"units",
    r"incorporated",
    r"corporation",
    r"company",
    r"holdings",
    r"group",
    r"limited",
    r"inc\.?",
    r"corp\.?",
    r"co\.?",
    r"plc",
    r"ltd\.?",
    r"llc",
    r"lp",
    r"nv",
    r"sa",
    r"ag",
)

_TRAILING = re.compile(
    r"[\s,]*(?:" + "|".join(_SUFFIX_PATTERNS) + r")[\s,.]*$",
    flags=re.IGNORECASE,
)

_MIN_SHORT_NAME_CHARS = 2

# A share class is the one distinguishing thing that trails a listing name, so
# it survives shortening. It also sits behind the legal form it has to be
# lifted off before the boilerplate in front of it can be reached:
# "CrowdStrike Holdings, Inc. Class A" is otherwise stuck whole, next to a
# clean "Fortinet" in the same row.
# Only "Class X". A fund's "Series 1" is part of its name, not a share class,
# and lifting it changed "Invesco QQQ Trust, Series 1" for no reason.
_SHARE_CLASS = re.compile(
    r"\s*[,]?\s*(class\s+[a-z0-9]{1,2})\s*$",
    flags=re.IGNORECASE,
)


def short_display_name(name: str, *, symbol: str = "") -> str:
    """A name a person would say, derived from the resolver's own name."""
    candidate = " ".join(str(name or "").split())
    if not candidate:
        return symbol.strip().upper()
    candidate, share_class = _without_share_class(candidate)
    while True:
        trimmed = _TRAILING.sub("", candidate).strip(" ,.")
        if trimmed == candidate or len(trimmed) < _MIN_SHORT_NAME_CHARS:
            break
        candidate = trimmed
    candidate = _without_repeated_issuer_prefix(candidate)
    # "The Walt Disney Company" loses its suffix and keeps a dangling article;
    # spoken names drop it, and only when something substantial remains.
    if candidate.lower().startswith("the "):
        without_article = candidate[4:].strip()
        if len(without_article) >= _MIN_SHORT_NAME_CHARS:
            candidate = without_article
    if not candidate:
        return " ".join(str(name).split())
    return f"{candidate} {share_class}" if share_class else candidate


def _without_share_class(name: str) -> tuple[str, str]:
    """Split a trailing share class off, so it can be put back after the
    legal-form boilerplate in front of it is stripped. Nothing is dropped: an
    unmatched name comes back unchanged with an empty class."""
    match = _SHARE_CLASS.search(name)
    if match is None:
        return name, ""
    head = name[: match.start()].strip(" ,.")
    if len(head) < _MIN_SHORT_NAME_CHARS:
        return name, ""
    return head, " ".join(match.group(1).split())


def asset_label_parts(subjects: list[dict[str, str]]) -> list[dict[str, str]]:
    """Typed identity parts for one asset: short name text, then its ticker."""
    parts: list[dict[str, str]] = []
    for index, subject in enumerate(subjects):
        symbol = str(subject.get("symbol") or "").strip().upper()
        if index:
            parts.append({"type": "text", "value": " "})
        parts.append(
            {
                "type": "text",
                "value": short_display_name(
                    str(subject.get("name") or ""), symbol=symbol
                ),
            }
        )
        parts.append({"type": "ticker", "value": symbol})
    return parts


def label_from_parts(parts: list[dict[str, Any]]) -> str:
    """The plain-text form of a parts label.

    Kept as the row's ``label`` so older clients, aria labels, analytics, and
    every non-visual consumer read the same sentence the badge row shows.
    """
    rendered: list[str] = []
    for part in parts:
        value = str(part.get("value") or "")
        if not value:
            continue
        if part.get("type") == "ticker":
            rendered.append(f" ({value})")
        else:
            rendered.append(value)
    return "".join(rendered).replace("  ", " ").strip()


def _without_repeated_issuer_prefix(name: str) -> str:
    """Fund listings repeat their issuer: "First Trust Exchange-Traded Fund II
    First Trust NASDAQ Cybersecurity ETF". When the opening words reappear
    later, the second occurrence starts the name a person would say. The
    result is still a substring of what the resolver returned."""
    tokens = name.split()
    for width in range(min(4, len(tokens) // 2), 1, -1):
        prefix = tokens[:width]
        for start in range(width, len(tokens) - width + 1):
            if tokens[start : start + width] == prefix:
                return " ".join(tokens[start:])
    return name
