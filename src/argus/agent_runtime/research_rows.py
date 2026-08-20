"""Runnable rows and verified peers for research answers.

Every candidate passes the resolver, asset-class, and coverage gates before it
becomes tappable; provider name pairs are untrusted input, never output. Rows
ride the existing typed Try-next surface: a tap sends a fully specified ask
through the ordinary interpretation and confirmation lifecycle, so nothing
here executes anything.

Naming is one vocabulary everywhere: a short display name plus the
resolver-verified ticker as a typed part the client renders as a badge. Row
copy states the window it actually asks for, never a vague "against
history".
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Iterable

from loguru import logger

from argus.agent_runtime.asset_identity import (
    asset_label_parts,
    label_from_parts,
)
from argus.agent_runtime.next_experiments import (
    NEXT_EXPERIMENTS_ROW_CAP,
    NEXT_EXPERIMENTS_VERSION,
)
from argus.domain.research.contracts import MAX_PEER_PAIRS, ResearchNamePair

_PEER_VERIFY_BUDGET_SECONDS = 2.0
_MAX_VERIFIED_PEERS = 4
# A label_key is required by the row parser; this one is deliberately absent
# from the catalogs so the backend-localized label renders as supplied.
_DYNAMIC_LABEL_KEY = "chat.next_experiments.labels.research_dynamic"


def verified_peers(
    name_pairs: Iterable[ResearchNamePair],
    *,
    exclude: set[str],
    probe: Callable[[str], bool] | None = None,
    scan_limit: int = MAX_PEER_PAIRS,
) -> list[dict[str, str]]:
    """Resolver, asset-class, and coverage gates over provider name pairs.

    The resolver owns identity and display name; a name the catalog cannot
    resolve never becomes tappable, whatever the provider claimed.

    ``scan_limit`` bounds how many candidates are examined, not how many
    survive. A market survey lists whatever moved, so its first names are
    often micro caps the catalog cannot trade; scanning further is what lets
    the answer still end on a name the user can actually test.
    """
    peers: list[dict[str, str]] = []
    seen = {symbol.upper() for symbol in exclude}
    for pair in list(name_pairs)[: max(scan_limit, 1)]:
        candidate = pair.symbol.strip().upper()
        if not candidate or candidate in seen:
            continue
        resolved = _resolve_bounded(candidate, probe=probe)
        if resolved is None:
            continue
        symbol = resolved["symbol"]
        if symbol in seen or resolved["asset_class"] != "equity":
            continue
        seen.add(candidate)
        seen.add(symbol)
        peers.append(resolved)
        if len(peers) >= _MAX_VERIFIED_PEERS:
            break
    return peers


def _resolve_bounded(
    candidate: str, *, probe: Callable[[str], bool] | None
) -> dict[str, str] | None:
    """Answer-paints-first: peer verification runs under a hard budget and
    degrades to fewer rows when the provider is slow."""

    def _verify() -> dict[str, str] | None:
        if probe is not None:
            return (
                {"symbol": candidate, "name": candidate, "asset_class": "equity"}
                if probe(candidate)
                else None
            )
        from argus.domain import market_data

        resolved = market_data.resolve_asset(candidate)
        if resolved is None:
            return None
        if resolved.canonical_symbol.upper() != candidate:
            return None
        symbol = resolved.canonical_symbol.upper()
        # A peer row is an offer. The resolver says the catalog lists it; the
        # tradable-history owner says a tap will actually get bars, which is
        # the same gate discovery applies before offering a candidate.
        if not market_data.tradable_history(symbol, resolved.asset_class).is_tradable:
            logger.info(
                "Peer dropped: catalog lists it but there is no tradable history",
                symbol=symbol,
            )
            return None
        return {
            "symbol": symbol,
            "name": resolved.name or symbol,
            "asset_class": resolved.asset_class,
        }

    executor = ThreadPoolExecutor(max_workers=1)
    try:
        return executor.submit(_verify).result(timeout=_PEER_VERIFY_BUDGET_SECONDS)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Peer verification skipped", candidate=candidate, error=str(exc))
        return None
    finally:
        executor.shutdown(wait=False, cancel_futures=False)


# The prebaked ask is a three-year buy and hold when the assets have three
# years to give. A row that names a window the asset cannot cover is a
# promise the run must quietly break, so the window comes from the coverage
# Argus resolves, never from the template alone.
TEST_WINDOW_YEARS = 3
_COVERAGE_PROBE_BUDGET_SECONDS = 2.0
# A listing that starts within this margin of the window is a full window in
# every sense a reader cares about; exchange calendars are not to the day.
_COVERAGE_SLACK_DAYS = 21


@dataclass(frozen=True)
class RowWindow:
    """What a row may honestly say about the period it will run."""

    full_years: int | None
    start: date | None

    @property
    def is_full(self) -> bool:
        return self.full_years is not None


def _earliest_available(symbol: str, asset_class: str) -> date | None:
    """First date the provider actually has bars for, inside the window.

    The long lookback stays here because a row's window needs the true start,
    not just whether history exists; the short existence question belongs to
    the tradable-history owner and is asked first so an unofferable symbol
    never reaches the expensive probe.
    """
    from datetime import timedelta

    from argus.domain.market_data import tradable_history
    from argus.domain.market_data.provider import fetch_price_series

    if not tradable_history(symbol, asset_class).is_tradable:
        return None
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=365 * TEST_WINDOW_YEARS)
    series = fetch_price_series(symbol, asset_class, start, end, "1d")
    index = getattr(series, "index", None)
    if index is None or len(index) == 0:
        return None
    return date.fromisoformat(str(index[0])[:10])


def row_window(
    assets: list[dict[str, str]],
    *,
    probe: Callable[[str, str], date | None] | None = None,
) -> RowWindow:
    """The window every asset in a row can actually cover.

    The shortest history wins, because a versus row runs them together. When
    coverage cannot be established inside the budget, the row says nothing
    about a window rather than naming one that will be adjusted.
    """
    from datetime import timedelta

    resolver = probe or _earliest_available
    end = datetime.now(timezone.utc).date()
    requested_start = end - timedelta(days=365 * TEST_WINDOW_YEARS)
    latest_start: date | None = None
    for asset in assets:
        try:
            executor = ThreadPoolExecutor(max_workers=1)
            try:
                earliest = executor.submit(
                    resolver, asset["symbol"], asset.get("asset_class") or "equity"
                ).result(timeout=_COVERAGE_PROBE_BUDGET_SECONDS)
            finally:
                executor.shutdown(wait=False, cancel_futures=False)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "Row coverage probe skipped",
                symbol=asset.get("symbol"),
                error=str(exc),
            )
            return RowWindow(full_years=None, start=None)
        if earliest is None:
            return RowWindow(full_years=None, start=None)
        if latest_start is None or earliest > latest_start:
            latest_start = earliest
    if latest_start is None:
        return RowWindow(full_years=None, start=None)
    if (latest_start - requested_start).days <= _COVERAGE_SLACK_DAYS:
        return RowWindow(full_years=TEST_WINDOW_YEARS, start=latest_start)
    return RowWindow(full_years=None, start=latest_start)


def _identity_parts(subjects: list[dict[str, str]]) -> list[dict[str, str]]:
    return asset_label_parts(subjects)


def research_next_experiment_rows(
    *,
    subjects: list[dict[str, str]],
    peers: list[dict[str, str]],
    language: str,
    coverage_probe: Callable[[str, str], date | None] | None = None,
) -> dict[str, Any] | None:
    """Compose up to three prebaked runnable rows for a research answer."""
    spanish = language == "es-419"
    rows: list[dict[str, Any]] = []
    testable = [s for s in subjects if s.get("asset_class") in ("equity", "crypto")]
    if not testable:
        return None
    anchor = testable[0]
    if len(testable) >= 2:
        group = testable[: min(len(testable), 5)]
        symbols = ", ".join(s["symbol"] for s in group)
        window = row_window(group, probe=coverage_probe)
        rows.append(
            _row(
                kind="research_test_versus",
                parts=[
                    *_versus_parts(group[:1], group[1:], spanish),
                    *_window_parts(window, spanish),
                ],
                send_text=_send_text(symbols, spanish, window),
            )
        )
    else:
        single_window = row_window([anchor], probe=coverage_probe)
        rows.append(
            _row(
                kind="research_test_single",
                parts=[
                    {"type": "text", "value": "Probar " if spanish else "Test "},
                    *_identity_parts([anchor]),
                    *_window_parts(single_window, spanish),
                ],
                send_text=_send_text(anchor["symbol"], spanish, single_window),
            )
        )
        if peers:
            first_peers = peers[: min(len(peers), 4)]
            symbols = ", ".join([anchor["symbol"], *(p["symbol"] for p in first_peers)])
            versus_window = row_window([anchor, *first_peers], probe=coverage_probe)
            rows.append(
                _row(
                    kind="research_test_versus",
                    parts=[
                        *_versus_parts([anchor], first_peers, spanish),
                        *_window_parts(versus_window, spanish),
                    ],
                    send_text=_send_text(symbols, spanish, versus_window),
                )
            )
    return {
        "version": NEXT_EXPERIMENTS_VERSION,
        "rows": rows[:NEXT_EXPERIMENTS_ROW_CAP],
    }


def _versus_parts(
    anchors: list[dict[str, str]],
    others: list[dict[str, str]],
    spanish: bool,
) -> list[dict[str, str]]:
    parts: list[dict[str, str]] = [
        {"type": "text", "value": "Probar " if spanish else "Test "},
        *_identity_parts(anchors),
    ]
    for index, other in enumerate(others):
        if index == 0:
            separator = " frente a " if spanish else " vs "
        elif index == len(others) - 1:
            separator = " y " if spanish else " and "
        else:
            separator = ", "
        parts.append({"type": "text", "value": separator})
        parts.extend(_identity_parts([other]))
    return parts


_MONTHS_EN = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_MONTHS_ES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def _window_phrase(window: RowWindow, spanish: bool) -> str:
    """What the row may say about its period, in the reader's language."""
    if window.is_full:
        return (
            f" en los últimos {TEST_WINDOW_YEARS} años"
            if spanish
            else f" over the last {TEST_WINDOW_YEARS} years"
        )
    if window.start is not None:
        if spanish:
            return f" desde {_MONTHS_ES[window.start.month - 1]} de {window.start.year}"
        return f" since {_MONTHS_EN[window.start.month - 1]} {window.start.year}"
    # Coverage unknown: say nothing rather than name a window that moves.
    return ""


def _window_parts(window: RowWindow, spanish: bool) -> list[dict[str, str]]:
    phrase = _window_phrase(window, spanish)
    return [{"type": "text", "value": phrase}] if phrase else []


def _send_text(symbols: str, spanish: bool, window: RowWindow) -> str:
    # The sent text is a prompt the interpreter parses, not display copy, so
    # it carries the same window the label promises: a row that says one
    # period and runs another is the defect this replaced.
    if window.is_full:
        if spanish:
            return f"Prueba comprar y mantener {symbols} durante los últimos tres años"
        return f"Test buying and holding {symbols} over the last three years"
    if window.start is not None:
        start = window.start.isoformat()
        if spanish:
            return f"Prueba comprar y mantener {symbols} desde {start} hasta hoy"
        return f"Test buying and holding {symbols} from {start} until today"
    if spanish:
        return f"Prueba comprar y mantener {symbols} en su historial disponible"
    return f"Test buying and holding {symbols} over its available history"


def _row(*, kind: str, parts: list[dict[str, str]], send_text: str) -> dict[str, Any]:
    # `label` stays the plain sentence: aria labels, analytics, and any client
    # that does not render parts must read exactly what the badge row shows.
    return {
        "kind": kind,
        "label": label_from_parts(parts),
        "label_parts": parts,
        "label_key": _DYNAMIC_LABEL_KEY,
        "send_text": send_text,
    }


def honest_no_next_line(language: str) -> str:
    if language == "es-419":
        return (
            "Ninguno de estos activos se puede probar directamente en Argus "
            "todavía, así que no hay una prueba de un toque para ofrecer aquí."
        )
    return (
        "None of these can be tested directly in Argus yet, so there is no "
        "one-tap test to offer here."
    )
