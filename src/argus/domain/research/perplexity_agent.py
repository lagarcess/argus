"""Perplexity Agent API client for finance_search research.

One HTTP boundary with an injectable transport so tests stay hermetic. The
parser is deterministic: it walks the typed ``output`` items the Agent API
documents, never user language. Provider identity is scrubbed at parse time
because route receipts and the cost ledger own provenance, not prose.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from loguru import logger

from argus.domain.research.config import ResearchConfigSpec
from argus.domain.research.contracts import (
    MAX_ANSWER_CHARS,
    MAX_PACKET_TICKERS,
    MAX_PEER_PAIRS,
    MAX_SOURCES,
    MAX_URL_CHARS,
    PROVIDER_HOSTS,
    BackgroundPoll,
    ResearchNamePair,
    ResearchPacket,
    ResearchSource,
    ResearchUnavailableError,
    ResearchUsage,
)

PERPLEXITY_AGENT_URL = "https://api.perplexity.ai/v1/agent"
# Published tool pricing: $5 per 1,000 finance_search invocations. Token costs
# bill separately; the ledger records this floor as provider_reported.
DOCUMENTED_FINANCE_SEARCH_COST_USD = 0.005

_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "incomplete"}


class PerplexityAgentClient:
    def __init__(
        self,
        api_key: str,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_key = api_key.strip()
        self._transport = transport

    def run_research(self, prompt: str, spec: ResearchConfigSpec) -> ResearchPacket:
        payload = self._request_body(prompt, spec)
        started = time.monotonic()
        response = self._post(payload, timeout_seconds=spec.timeout_seconds)
        latency_ms = int((time.monotonic() - started) * 1000)
        packet = _packet_from_response(response, latency_ms=latency_ms)
        if not packet.answer_markdown:
            raise ResearchUnavailableError("empty_answer")
        return packet

    def submit_background(self, prompt: str, spec: ResearchConfigSpec) -> str:
        payload = self._request_body(prompt, spec)
        payload["background"] = True
        response = self._post(payload, timeout_seconds=spec.timeout_seconds)
        background_id = str(response.get("id") or "").strip()
        if not background_id:
            raise ResearchUnavailableError("malformed_response", "missing id")
        return background_id

    def poll_background(
        self, background_id: str, *, timeout_seconds: float = 30.0
    ) -> BackgroundPoll:
        started = time.monotonic()
        response = self._get(
            f"{PERPLEXITY_AGENT_URL}/{background_id}", timeout_seconds=timeout_seconds
        )
        status = str(response.get("status") or "").strip() or "in_progress"
        if status not in _TERMINAL_STATUSES:
            return BackgroundPoll(
                status="in_progress" if status != "queued" else "queued"
            )
        if status != "completed":
            error = response.get("error")
            detail = json.dumps(error)[:500] if error else None
            return BackgroundPoll(status=status, failure_detail=detail)  # type: ignore[arg-type]
        latency_ms = int((time.monotonic() - started) * 1000)
        packet = _packet_from_response(response, latency_ms=latency_ms)
        return BackgroundPoll(status="completed", packet=packet)

    def _request_body(self, prompt: str, spec: ResearchConfigSpec) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": spec.model,
            "input": prompt,
            "tools": [{"type": tool} for tool in spec.tools],
            "max_steps": spec.max_steps,
            "max_output_tokens": spec.max_output_tokens,
        }
        if spec.reasoning_effort is not None:
            body["reasoning"] = {"effort": spec.reasoning_effort}
        return body

    def _post(self, payload: dict[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
        return self._send("POST", PERPLEXITY_AGENT_URL, payload, timeout_seconds)

    def _get(self, url: str, *, timeout_seconds: float) -> dict[str, Any]:
        return self._send("GET", url, None, timeout_seconds)

    def _send(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        if not self._api_key:
            raise ResearchUnavailableError("not_configured")
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(
                transport=self._transport, timeout=timeout_seconds
            ) as client:
                response = client.request(method, url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise ResearchUnavailableError("timeout", str(exc)) from exc
        except httpx.HTTPError as exc:
            raise ResearchUnavailableError("transport", str(exc)) from exc
        if response.status_code in (401, 403):
            raise ResearchUnavailableError(
                "not_configured", f"http {response.status_code}"
            )
        if response.status_code >= 400:
            logger.warning(
                "Research provider returned an error status",
                status=response.status_code,
            )
            raise ResearchUnavailableError("http_error", f"http {response.status_code}")
        try:
            document = response.json()
        except ValueError as exc:
            raise ResearchUnavailableError("malformed_response", str(exc)) from exc
        if not isinstance(document, dict):
            raise ResearchUnavailableError("malformed_response", "non-object body")
        return document


def _packet_from_response(document: dict[str, Any], *, latency_ms: int) -> ResearchPacket:
    output = document.get("output")
    if not isinstance(output, list):
        raise ResearchUnavailableError("malformed_response", "missing output list")
    text_blocks: list[str] = []
    categories: list[str] = []
    tickers: list[str] = []
    sources: list[ResearchSource] = []
    pairs: list[ResearchNamePair] = []
    invocations = 0
    for item in output:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == "finance_results":
            for value in item.get("categories") or []:
                if isinstance(value, str) and value not in categories:
                    categories.append(value)
            for value in item.get("tickers") or []:
                if isinstance(value, str) and value not in tickers:
                    tickers.append(value)
            for result in item.get("results") or []:
                if not isinstance(result, dict):
                    continue
                category = result.get("category")
                if isinstance(category, str) and category not in categories:
                    categories.append(category)
                for url in result.get("sources") or []:
                    _append_public_source(sources, {"url": url})
                if category == "tickers_lookup":
                    pairs.extend(_pairs_from_lookup(str(result.get("content") or "")))
                elif category == "etf_holdings":
                    pairs.extend(_pairs_from_holdings(str(result.get("content") or "")))
        elif item_type == "search_results":
            # Web search citations live in their own output items: title,
            # url, and the publisher's own date. This is the channel the
            # sector and comparison shapes fill.
            for result in item.get("results") or []:
                if isinstance(result, dict):
                    _append_public_source(sources, result)
        elif item_type == "message":
            for chunk in item.get("content") or []:
                if not isinstance(chunk, dict) or chunk.get("type") != "output_text":
                    continue
                text = chunk.get("text")
                if isinstance(text, str) and text.strip():
                    text_blocks.append(text)
                # Some models carry their citations as annotations on the
                # same chunk instead of as search_results items.
                for annotation in chunk.get("annotations") or []:
                    if isinstance(annotation, dict):
                        _append_public_source(sources, annotation)
    usage = document.get("usage")
    if isinstance(usage, dict):
        details = usage.get("tool_calls_details")
        if isinstance(details, dict):
            finance = details.get("finance_search")
            if isinstance(finance, dict):
                try:
                    invocations = int(finance.get("invocation") or 0)
                except (TypeError, ValueError):
                    invocations = 0
    answer = _sanitize_answer("\n\n".join(text_blocks))
    seen: set[str] = set()
    unique_pairs = []
    for pair in pairs:
        key = pair.symbol.upper()
        if key in seen:
            continue
        seen.add(key)
        unique_pairs.append(pair)
    return ResearchPacket(
        answer_markdown=answer[:MAX_ANSWER_CHARS],
        categories=tuple(categories[:12]),
        tickers=tuple(tickers[:MAX_PACKET_TICKERS]),
        sources=tuple(sources[:MAX_SOURCES]),
        name_pairs=tuple(unique_pairs[:MAX_PEER_PAIRS]),
        usage=ResearchUsage(
            invocations=invocations,
            model=str(document.get("model") or ""),
            latency_ms=latency_ms,
            cost_usd=round(invocations * DOCUMENTED_FINANCE_SEARCH_COST_USD, 6),
        ),
        background_id=str(document.get("id") or "") or None,
    )


# Ticker-shaped cell: 1-5 uppercase letters, optionally a class suffix. Cells
# are read only from markdown table rows, which are machine-generated
# structure, never prose, and every symbol still passes the resolver before
# anything becomes tappable.
_TICKER_CELL = re.compile(r"^[A-Z]{1,5}(?:[.\-][A-Z]{1,2})?$")
_TICKER_HEADERS = frozenset({"TICKER", "SYMBOL", "ETF"})


def symbols_from_answer_tables(markdown: str) -> list[str]:
    """Symbols named in the answer's own tables, in the order shown.

    A market survey often reports its assets only in tables, with no typed
    ticker list attached. Reading those cells is the same deterministic
    markdown walk the lookup and holdings parsers already do.
    """
    symbols: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        for cell in stripped.strip("|").split("|"):
            candidate = cell.strip().strip("*` ").upper()
            if not candidate or candidate in _TICKER_HEADERS:
                continue
            if _TICKER_CELL.fullmatch(candidate) and candidate not in symbols:
                symbols.append(candidate)
    return symbols


def _append_public_source(sources: list[ResearchSource], entry: Any) -> None:
    """One citation, bounded and scrubbed.

    Accepts either channel's shape: a search result, an annotation, or a
    bare finance URL. Provider-identity hosts never survive, so Argus never
    cites the tool that answered it.
    """
    if not isinstance(entry, dict):
        return
    raw_url = entry.get("url") or entry.get("link") or entry.get("uri")
    if not isinstance(raw_url, str):
        return
    candidate = raw_url.strip()
    if not candidate.startswith("https://") or len(candidate) > MAX_URL_CHARS:
        return
    host = urlparse(candidate).netloc.lower()
    if any(host == p or host.endswith(f".{p}") for p in PROVIDER_HOSTS):
        return
    if any(source.url == candidate for source in sources):
        return
    title = entry.get("title") or entry.get("name") or ""
    published = entry.get("date") or entry.get("last_updated") or None
    sources.append(
        ResearchSource(
            url=candidate,
            title=str(title)[:200].strip(),
            source_date=str(published)[:10] if published else None,
        )
    )


def _pairs_from_holdings(content: str) -> list[ResearchNamePair]:
    """Parse the provider's ``etf_holdings`` markdown table.

    Machine-generated fixed format: a header row naming ``symbol`` and
    ``name`` columns, then one holding per row, top weights first. Row order
    is preserved so the heaviest constituents become the offerable pairs;
    the resolver still gates every one before anything is tappable, which is
    what grounds exposure vehicles whose tickers collide.
    """
    pairs: list[ResearchNamePair] = []
    symbol_index: int | None = None
    name_index: int | None = None
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        lowered = [cell.lower() for cell in cells]
        if symbol_index is None:
            if "symbol" in lowered and "name" in lowered:
                symbol_index = lowered.index("symbol")
                name_index = lowered.index("name")
            continue
        if name_index is None or len(cells) <= max(symbol_index, name_index):
            continue
        ticker = cells[symbol_index].strip("*").upper()
        if not ticker or set(ticker) <= {"-", " ", ":"}:
            continue
        if not re.fullmatch(r"[A-Z0-9.\-/]{1,12}", ticker):
            continue
        display = cells[name_index] or ticker
        pairs.append(ResearchNamePair(symbol=ticker, name=display.title()))
    return pairs


def _pairs_from_lookup(content: str) -> list[ResearchNamePair]:
    """Parse the provider's ``tickers_lookup`` markdown table.

    This walks a machine-generated fixed format (query | ticker | name rows),
    never user language. Unparseable rows are dropped, not guessed.
    """
    pairs: list[ResearchNamePair] = []
    for line in content.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        query, ticker, name = cells[0], cells[1], cells[2]
        if not ticker or ticker.upper() in ("TICKER", "NOT_FOUND"):
            continue
        if set(ticker) <= {"-", " ", ":"}:
            continue
        if not re.fullmatch(r"[A-Z0-9.\-/]{1,12}", ticker.strip("*").upper()):
            continue
        display = name or query
        if not display:
            continue
        pairs.append(
            ResearchNamePair(name=display[:120], symbol=ticker.strip("*").upper())
        )
    return pairs


_LINK_PATTERN = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)\)")


def strip_mechanism_narration(text: str) -> str:
    """Drop any sentence that names a provider tool.

    The Voice Boundary forbids raw internal names in assistant prose, and
    spec section 2 forbids handing the user a capability list; an answer
    explaining that "the requested finance_search tool was not available"
    breaks both at once. Tool names come from the configurations themselves,
    so a newly configured tool is covered without editing this function.
    Whole sentences go, because a sentence about a mechanism has nothing
    left to say once the mechanism is removed. Degradation is still told to
    the reader, from the typed signal on the packet.
    """
    if not _PROVIDER_VOCABULARY.search(text):
        return text
    kept: list[str] = []
    for block in text.split("\n"):
        sentences = re.split(r"(?<=[.!?])\s+", block)
        surviving = [
            sentence
            for sentence in sentences
            if not _PROVIDER_VOCABULARY.search(sentence)
        ]
        if sentences and not surviving:
            continue
        kept.append(" ".join(surviving).strip())
    return "\n".join(kept).strip()


def _provider_vocabulary_pattern() -> re.Pattern[str]:
    """Provider vocabulary, derived from the tools this rail declares.

    The declared names are the seed; their families are the reach. The leak
    that prompted this guard named ``finance_quotes`` and
    ``finance_company_profile``, which are the same provider vocabulary as
    the declared ``finance_search`` without being declared themselves.
    Matching the family prefix covers those, and covers whatever the
    provider names next, without a hand-maintained list. Snake_case
    identifiers do not occur in ordinary finance prose, so the reach is
    wide without being greedy.
    """
    from argus.domain.research.config import declared_tool_names

    tools = sorted(declared_tool_names())
    prefixes = sorted({tool.split("_", 1)[0] for tool in tools if "_" in tool})
    alternatives = [re.escape(tool) for tool in tools]
    alternatives += [rf"{re.escape(prefix)}_[a-z][a-z0-9_]*" for prefix in prefixes]
    if not alternatives:
        return re.compile(r"(?!x)x")
    return re.compile(r"\b(?:" + "|".join(alternatives) + r")\b")


_PROVIDER_VOCABULARY = _provider_vocabulary_pattern()


def _sanitize_answer(text: str) -> str:
    """Presentation-only cleanup: provider-host links become plain text and
    typographic dashes normalize to house style (digit ranges keep a hyphen)."""

    def _replace_link(match: re.Match[str]) -> str:
        host = urlparse(match.group(2)).netloc.lower()
        if any(host == p or host.endswith(f".{p}") for p in PROVIDER_HOSTS):
            return match.group(1)
        return match.group(0)

    cleaned = _LINK_PATTERN.sub(_replace_link, text)
    cleaned = re.sub(r"https?://(?:[a-z0-9-]+\.)*perplexity\.ai\S*", "", cleaned)
    # A lone dash table cell is an empty-value marker, not punctuation.
    cleaned = re.sub(r"\|\s*[—–]\s*(?=\|)", "| - ", cleaned)
    cleaned = re.sub(r"(?<=\d)\s*[—–]\s*(?=\d)", "-", cleaned)
    cleaned = re.sub(r"\s*[—–]\s*", ", ", cleaned)
    return strip_mechanism_narration(cleaned).strip()
