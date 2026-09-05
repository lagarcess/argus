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
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

import httpx
from loguru import logger

from argus.domain.research.billing import (
    UnpricedResearchSpend,
    UnpricedSpendRecorder,
    record_unpriced_spend,
    unpriced_spend,
)
from argus.domain.research.config import ResearchConfigSpec
from argus.domain.research.contracts import (
    MAX_ANSWER_CHARS,
    MAX_PACKET_SOURCES,
    MAX_PACKET_TICKERS,
    MAX_PEER_PAIRS,
    MAX_URL_CHARS,
    PROVIDER_HOSTS,
    BackgroundPoll,
    ResearchNamePair,
    ResearchPacket,
    ResearchPricingError,
    ResearchSource,
    ResearchUnavailableError,
    ResearchUsage,
)
from argus.domain.research.pricing import validated_research_cost_usd

PERPLEXITY_AGENT_URL = "https://api.perplexity.ai/v1/agent"

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
        self._reported_unpriced_ids: set[str] = set()

    def run_research(self, prompt: str, spec: ResearchConfigSpec) -> ResearchPacket:
        payload = self._request_body(prompt, spec)
        started = time.monotonic()
        response = self._post(payload, timeout_seconds=spec.timeout_seconds)
        latency_ms = int((time.monotonic() - started) * 1000)
        packet = _packet_from_response(
            response, latency_ms=latency_ms, on_unpriced=self._record_unpriced
        )
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
        packet = _packet_from_response(
            response, latency_ms=latency_ms, on_unpriced=self._record_unpriced
        )
        return BackgroundPoll(status="completed", packet=packet)

    def _record_unpriced(self, spend: UnpricedResearchSpend) -> None:
        response_id = spend.provider_response_id
        if response_id and response_id in self._reported_unpriced_ids:
            return
        record_unpriced_spend(spend)
        if response_id:
            self._reported_unpriced_ids.add(response_id)

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


def _packet_from_response(
    document: dict[str, Any],
    *,
    latency_ms: int,
    on_unpriced: UnpricedSpendRecorder = record_unpriced_spend,
) -> ResearchPacket:
    output = document.get("output")
    if not isinstance(output, list):
        raise ResearchUnavailableError("malformed_response", "missing output list")
    text_blocks: list[str] = []
    parsed = _ParsedToolResults()
    for item in output:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if not isinstance(item_type, str):
            continue
        reader = _TOOL_RESULT_READERS.get(item_type)
        if reader is not None:
            # Reading a tool result is what records it as retrieval evidence;
            # the two facts share one owner and cannot drift.
            parsed.tool_results.append(item_type)
            reader(item, parsed)
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
                        _append_public_source(parsed.sources, annotation)
    usage = _usage_from_response(document, latency_ms=latency_ms, on_unpriced=on_unpriced)
    answer = _sanitize_answer("\n\n".join(text_blocks))
    if not answer:
        raise ResearchUnavailableError("empty_answer")
    seen: set[str] = set()
    unique_pairs = []
    for pair in parsed.pairs:
        key = pair.symbol.upper()
        if key in seen:
            continue
        seen.add(key)
        unique_pairs.append(pair)
    return ResearchPacket(
        answer_markdown=answer[:MAX_ANSWER_CHARS],
        categories=tuple(parsed.categories[:12]),
        tickers=tuple(parsed.tickers[:MAX_PACKET_TICKERS]),
        sources=tuple(parsed.sources[:MAX_PACKET_SOURCES]),
        name_pairs=tuple(unique_pairs[:MAX_PEER_PAIRS]),
        tool_results=tuple(parsed.tool_results),
        usage=usage,
        background_id=str(document.get("id") or "") or None,
    )


@dataclass
class _ParsedToolResults:
    """Everything the tool result items of one response contribute."""

    categories: list[str] = field(default_factory=list)
    tickers: list[str] = field(default_factory=list)
    sources: list[ResearchSource] = field(default_factory=list)
    pairs: list[ResearchNamePair] = field(default_factory=list)
    tool_results: list[str] = field(default_factory=list)


def _read_finance_results(item: dict[str, Any], parsed: _ParsedToolResults) -> None:
    for value in item.get("categories") or []:
        if isinstance(value, str) and value not in parsed.categories:
            parsed.categories.append(value)
    for value in item.get("tickers") or []:
        if isinstance(value, str) and value not in parsed.tickers:
            parsed.tickers.append(value)
    for result in item.get("results") or []:
        if not isinstance(result, dict):
            continue
        category = result.get("category")
        if isinstance(category, str) and category not in parsed.categories:
            parsed.categories.append(category)
        for url in result.get("sources") or []:
            _append_public_source(parsed.sources, {"url": url})
        if category == "tickers_lookup":
            parsed.pairs.extend(_pairs_from_lookup(str(result.get("content") or "")))
        elif category == "etf_holdings":
            parsed.pairs.extend(_pairs_from_holdings(str(result.get("content") or "")))


def _read_search_results(item: dict[str, Any], parsed: _ParsedToolResults) -> None:
    # Web search citations live in their own output items: title, url, and
    # the publisher's own date. This is the channel the sector and
    # comparison shapes fill.
    for result in item.get("results") or []:
        if isinstance(result, dict):
            _append_public_source(parsed.sources, result)


# The one owner of which output items are tool results. Recorded responses
# carry exactly one finance_results item per finance_search call and one
# search_results item per web search; a response that ran no tool carries
# neither. A kind read here is retrieval evidence whether or not the invoice
# arrived.
_TOOL_RESULT_READERS: dict[str, Callable[[dict[str, Any], _ParsedToolResults], None]] = {
    "finance_results": _read_finance_results,
    "search_results": _read_search_results,
}


def _usage_from_response(
    document: dict[str, Any],
    *,
    latency_ms: int,
    on_unpriced: UnpricedSpendRecorder = record_unpriced_spend,
) -> ResearchUsage:
    raw_model = document.get("model")
    model = raw_model.strip() if isinstance(raw_model, str) else ""
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_creation_input_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    # Unknown until the invoice establishes each count; a lost or malformed
    # invoice leaves them None, never zero.
    finance_search_invocations: int | None = None
    web_search_invocations: int | None = None
    fetch_url_invocations: int | None = None
    pricing_error: ResearchPricingError | None = None
    try:
        usage = document.get("usage")
        if not isinstance(usage, dict):
            raise ResearchPricingError("invalid_usage", "missing usage")
        details = usage.get("tool_calls_details")
        if details is None:
            details = {}
        if not isinstance(details, dict):
            raise ResearchPricingError(
                "invalid_usage", "invalid usage.tool_calls_details"
            )
        finance_search_invocations = _tool_invocation_count(details, "finance_search")
        web_search_invocations = _tool_invocation_count(
            details, "web_search", "search_web"
        )
        fetch_url_invocations = _tool_invocation_count(details, "fetch_url")
        if not model:
            raise ResearchPricingError("invalid_usage", "missing model")
        input_tokens = _required_nonnegative_int(
            usage, "input_tokens", path="usage.input_tokens"
        )
        output_tokens = _required_nonnegative_int(
            usage, "output_tokens", path="usage.output_tokens"
        )
        input_details = usage.get("input_tokens_details")
        if not isinstance(input_details, dict):
            raise ResearchPricingError(
                "invalid_usage", "invalid usage.input_tokens_details"
            )
        cache_creation_input_tokens = _required_nonnegative_int(
            input_details,
            "cache_creation_input_tokens",
            path="usage.input_tokens_details.cache_creation_input_tokens",
        )
        cache_read_input_tokens = _required_nonnegative_int(
            input_details,
            "cache_read_input_tokens",
            path="usage.input_tokens_details.cache_read_input_tokens",
        )
        cached_tokens = input_details.get("cached_tokens")
        if cached_tokens is not None and (
            isinstance(cached_tokens, bool)
            or not isinstance(cached_tokens, int)
            or cached_tokens != cache_read_input_tokens
        ):
            raise ResearchPricingError(
                "invalid_usage",
                "invalid usage.input_tokens_details.cached_tokens",
            )
        cost = usage.get("cost")
        if not isinstance(cost, dict) or cost.get("currency") != "USD":
            raise ResearchPricingError("invalid_pricing", "invalid usage.cost currency")
        provider_tool_costs_usd = _tool_cost_details(cost)
        cost_usd = validated_research_cost_usd(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_input_tokens=cache_creation_input_tokens,
            cache_read_input_tokens=cache_read_input_tokens,
            finance_search_invocations=finance_search_invocations,
            web_search_invocations=web_search_invocations,
            fetch_url_invocations=fetch_url_invocations,
            provider_input_cost_usd=_required_nonnegative_decimal(
                cost, "input_cost", path="usage.cost.input_cost"
            ),
            provider_output_cost_usd=_required_nonnegative_decimal(
                cost, "output_cost", path="usage.cost.output_cost"
            ),
            provider_cache_creation_cost_usd=_required_nonnegative_decimal(
                cost, "cache_creation_cost", path="usage.cost.cache_creation_cost"
            ),
            provider_cache_read_cost_usd=_required_nonnegative_decimal(
                cost, "cache_read_cost", path="usage.cost.cache_read_cost"
            ),
            provider_tool_calls_cost_usd=_optional_nonnegative_decimal(
                cost, "tool_calls_cost", path="usage.cost.tool_calls_cost"
            ),
            provider_tool_costs_usd=provider_tool_costs_usd,
            provider_total_cost_usd=_required_nonnegative_decimal(
                cost, "total_cost", path="usage.cost.total_cost"
            ),
        )
    except ResearchPricingError as exc:
        cost_usd = None
        pricing_error = exc
    parsed_usage = ResearchUsage(
        invocations=finance_search_invocations,
        finance_search_invocations=finance_search_invocations,
        web_search_invocations=web_search_invocations,
        fetch_url_invocations=fetch_url_invocations,
        model=model,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
    )

    if pricing_error is not None:
        on_unpriced(
            unpriced_spend(document=document, usage=parsed_usage, error=pricing_error)
        )
    return parsed_usage


def _tool_invocation_count(details: dict[str, Any], *provider_keys: str) -> int:
    counts: list[int] = []
    for key in provider_keys:
        if key not in details:
            continue
        entry = details[key]
        if not isinstance(entry, dict):
            raise ResearchPricingError(
                "invalid_usage", f"invalid usage.tool_calls_details.{key}"
            )
        counts.append(
            _required_nonnegative_int(
                entry,
                "invocation",
                path=f"usage.tool_calls_details.{key}.invocation",
            )
        )
    if not counts:
        return 0
    if any(count != counts[0] for count in counts[1:]):
        joined = ", ".join(provider_keys)
        raise ResearchPricingError("invalid_usage", f"conflicting tool counts: {joined}")
    return counts[0]


def _required_nonnegative_int(values: dict[str, Any], key: str, *, path: str) -> int:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ResearchPricingError("invalid_usage", f"invalid {path}")
    return value


def _required_nonnegative_decimal(
    values: dict[str, Any], key: str, *, path: str
) -> Decimal:
    if key not in values:
        raise ResearchPricingError("invalid_pricing", f"invalid {path}")
    return _nonnegative_decimal(values[key], path=path)


def _optional_nonnegative_decimal(
    values: dict[str, Any], key: str, *, path: str
) -> Decimal:
    if key not in values:
        return Decimal(0)
    return _nonnegative_decimal(values[key], path=path)


def _nonnegative_decimal(value: Any, *, path: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ResearchPricingError("invalid_pricing", f"invalid {path}")
    parsed = Decimal(str(value))
    if not parsed.is_finite() or parsed < 0:
        raise ResearchPricingError("invalid_pricing", f"invalid {path}")
    return parsed


def _tool_cost_details(cost: dict[str, Any]) -> dict[str, Decimal]:
    details = cost.get("tool_calls_cost_details")
    if details is None:
        return {}
    if not isinstance(details, dict):
        raise ResearchPricingError(
            "invalid_pricing", "invalid usage.cost.tool_calls_cost_details"
        )
    normalized: dict[str, Decimal] = {}
    aliases = {
        "finance_search": "finance_search",
        "web_search": "web_search",
        "search_web": "web_search",
        "fetch_url": "fetch_url",
    }
    for provider_key, value in details.items():
        tool = aliases.get(provider_key)
        if tool is None:
            raise ResearchPricingError(
                "invalid_pricing",
                "unknown tool in usage.cost.tool_calls_cost_details",
            )
        parsed = _nonnegative_decimal(
            value, path=f"usage.cost.tool_calls_cost_details.{provider_key}"
        )
        previous = normalized.get(tool)
        if previous is not None and previous != parsed:
            raise ResearchPricingError(
                "invalid_pricing", f"conflicting tool costs: {tool}"
            )
        normalized[tool] = parsed
    return normalized


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
