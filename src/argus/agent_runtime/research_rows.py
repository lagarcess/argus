"""Runnable rows and verified peers for research answers.

Every candidate passes the resolver, asset-class, and coverage gates before it
becomes tappable; provider name pairs are untrusted input, never output. Rows
ride the existing typed Try-next surface: a tap sends a fully specified ask
through the ordinary interpretation and confirmation lifecycle, so nothing
here executes anything. Naming everywhere is ``<Name> [ticker]`` in plain
language.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Iterable

from loguru import logger

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
) -> list[dict[str, str]]:
    """Resolver, asset-class, and coverage gates over provider name pairs.

    The resolver owns identity and display name; a name the catalog cannot
    resolve never becomes tappable, whatever the provider claimed.
    """
    peers: list[dict[str, str]] = []
    seen = {symbol.upper() for symbol in exclude}
    for pair in list(name_pairs)[:MAX_PEER_PAIRS]:
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
        return {
            "symbol": resolved.canonical_symbol.upper(),
            "name": resolved.name or resolved.canonical_symbol.upper(),
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


def _named(subject: dict[str, str]) -> str:
    return f"{subject['name']} [{subject['symbol']}]"


def research_next_experiment_rows(
    *,
    subjects: list[dict[str, str]],
    peers: list[dict[str, str]],
    language: str,
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
        names = _join_names([_named(s) for s in group], spanish)
        symbols = ", ".join(s["symbol"] for s in group)
        rows.append(
            _row(
                kind="research_test_versus",
                label=(
                    f"Probar {names} entre sí"
                    if spanish
                    else f"Test {names} against each other"
                ),
                send_text=(
                    f"Prueba comprar y mantener {symbols} durante los últimos tres años"
                    if spanish
                    else f"Test buying and holding {symbols} over the last three years"
                ),
            )
        )
    else:
        rows.append(
            _row(
                kind="research_test_single",
                label=(
                    f"Probar {_named(anchor)} con datos históricos"
                    if spanish
                    else f"Test {_named(anchor)} against history"
                ),
                send_text=(
                    f"Prueba comprar y mantener {anchor['symbol']} durante los últimos tres años"
                    if spanish
                    else f"Test buying and holding {anchor['symbol']} over the last three years"
                ),
            )
        )
        if peers:
            first_peers = peers[: min(len(peers), 4)]
            names = _join_names([_named(p) for p in first_peers], spanish)
            symbols = ", ".join([anchor["symbol"], *(p["symbol"] for p in first_peers)])
            rows.append(
                _row(
                    kind="research_test_versus",
                    label=(
                        f"Probar {_named(anchor)} frente a {names}"
                        if spanish
                        else f"Test {_named(anchor)} against {names}"
                    ),
                    send_text=(
                        f"Prueba comprar y mantener {symbols} durante los últimos tres años"
                        if spanish
                        else f"Test buying and holding {symbols} over the last three years"
                    ),
                )
            )
    return {
        "version": NEXT_EXPERIMENTS_VERSION,
        "rows": rows[:NEXT_EXPERIMENTS_ROW_CAP],
    }


def _join_names(names: list[str], spanish: bool) -> str:
    if len(names) == 1:
        return names[0]
    conjunction = " y " if spanish else " and "
    return ", ".join(names[:-1]) + conjunction + names[-1]


def _row(*, kind: str, label: str, send_text: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "label": label,
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
