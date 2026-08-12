"""Question-aware selection for the public research sources drawer.

Provider parsing retains a bounded evidence pool. This module is the one
public selection step: it removes citations that cannot plausibly describe
the question's period, keeps one page per publisher, then applies the drawer
cap. Retrieval order is preserved among eligible publishers.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable
from urllib.parse import urlparse

from argus.domain.research.contracts import MAX_SOURCES, ResearchSource


def select_public_sources(
    sources: Iterable[ResearchSource],
    *,
    question_kind: str | None = None,
    period_start: date | None = None,
    question_as_of: date | None = None,
) -> tuple[ResearchSource, ...]:
    """Return period-plausible, publisher-unique sources for the drawer.

    A dated source published before the asked-for period cannot describe that
    period. A source with no publisher date remains eligible because a live
    page can plausibly be current. A non-empty but malformed date is not
    evidence of freshness and is therefore excluded when the question has a
    freshness bound.
    """
    effective_start = period_start
    if effective_start is None and question_kind == "market_pulse":
        effective_start = question_as_of

    selected: list[ResearchSource] = []
    seen_publishers: set[str] = set()
    seen_urls: set[str] = set()
    for source in sources:
        if source.url in seen_urls:
            continue
        if not _period_plausible(
            source,
            period_start=effective_start,
            question_as_of=question_as_of,
        ):
            continue
        publisher = _publisher_key(source.url)
        if not publisher or publisher in seen_publishers:
            continue
        seen_urls.add(source.url)
        seen_publishers.add(publisher)
        selected.append(source)
        if len(selected) >= MAX_SOURCES:
            break
    return tuple(selected)


def _period_plausible(
    source: ResearchSource,
    *,
    period_start: date | None,
    question_as_of: date | None,
) -> bool:
    if period_start is None:
        return True
    if source.source_date is None:
        return True
    try:
        published = date.fromisoformat(source.source_date[:10])
    except ValueError:
        return False
    if published < period_start:
        return False
    return question_as_of is None or published <= question_as_of


def _publisher_key(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    labels = host.removeprefix("www.").split(".")
    if len(labels) < 2:
        return host
    # Collapse outlet subdomains such as finance.yahoo.com and news.yahoo.com.
    # For common country-code forms, keep the publisher label as well as the
    # two-part suffix (reuters.co.uk rather than co.uk).
    if (
        len(labels) >= 3
        and len(labels[-1]) == 2
        and labels[-2] in {"ac", "co", "com", "gov", "net", "org"}
    ):
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])
