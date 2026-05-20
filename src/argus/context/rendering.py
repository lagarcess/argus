from __future__ import annotations

from typing import Any


def context_packet_fact_summary(
    context_packets: list[dict[str, Any]],
    *,
    symbols: list[str] | None = None,
) -> dict[str, str]:
    summaries: list[str] = []
    has_limitations = False
    packet_ids: list[str] = []
    symbol_filter = _normalized_symbols(symbols)
    for packet in context_packets:
        if not isinstance(packet, dict):
            continue
        packet_id = str(packet.get("id") or "").strip()
        if packet_id:
            packet_ids.append(packet_id)
        packet_type = str(packet.get("packet_type") or "").strip()
        for fact in _packet_facts(packet):
            summary = _safe_fact_summary(
                packet_type=packet_type,
                fact=fact,
                symbol_filter=symbol_filter,
            )
            if summary:
                summaries.append(summary)
        for limitation in packet.get("limitations") or []:
            text = str(limitation).strip()
            if text:
                has_limitations = True
    result: dict[str, str] = {}
    if packet_ids:
        result["context_packet_ids"] = ", ".join(packet_ids)
    if summaries:
        result["context_packet_facts"] = "; ".join(summaries[:4])
    if has_limitations:
        result["context_packet_limitations"] = (
            "Context is backdrop only; it cannot change the simulated trades, "
            "metrics, or benchmark, and it should not be treated as causal proof."
        )
    return result


def _packet_facts(packet: dict[str, Any]) -> list[dict[str, Any]]:
    facts = packet.get("facts")
    if not isinstance(facts, list):
        return []
    return [fact for fact in facts if isinstance(fact, dict)]


def _safe_fact_summary(
    *,
    packet_type: str,
    fact: dict[str, Any],
    symbol_filter: set[str],
) -> str:
    if packet_type == "macro":
        return _safe_macro_fact_summary(fact)
    if packet_type == "news":
        label = str(fact.get("label") or "").strip()
        return f"Recent headline: {label}" if label else ""
    if packet_type == "corporate_actions":
        value = fact.get("value")
        if not isinstance(value, dict):
            return ""
        symbol = str(value.get("symbol") or "").strip()
        action_type = str(value.get("type") or "").strip().replace("_", " ")
        event_date = str(value.get("event_date") or "").strip()
        parts = [item for item in (symbol, action_type, event_date) if item]
        return "Corporate action context: " + " ".join(parts) if parts else ""
    if packet_type == "market_movers":
        value = fact.get("value")
        if not isinstance(value, dict):
            return ""
        symbol = str(value.get("symbol") or "").strip()
        if not _matches_symbol_filter(symbol, symbol_filter):
            return ""
        percent_change = value.get("percent_change")
        if symbol and percent_change not in (None, ""):
            return f"Short-lived market move: {symbol} changed {percent_change}%"
        return f"Short-lived market move: {symbol}" if symbol else ""
    if packet_type == "most_actives":
        value = fact.get("value")
        if not isinstance(value, dict):
            return ""
        symbol = str(value.get("symbol") or "").strip()
        if not _matches_symbol_filter(symbol, symbol_filter):
            return ""
        rank_by = str(value.get("rank_by") or "").strip()
        if symbol and rank_by:
            return f"Short-lived market activity: {symbol} was active by {rank_by}"
        return f"Short-lived market activity: {symbol}" if symbol else ""
    label = str(fact.get("label") or "").strip()
    return label


def _normalized_symbols(symbols: list[str] | None) -> set[str]:
    if not isinstance(symbols, list):
        return set()
    return {str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()}


def _matches_symbol_filter(symbol: str, symbol_filter: set[str]) -> bool:
    if not symbol_filter:
        return False
    return symbol.strip().upper() in symbol_filter


def _safe_macro_fact_summary(fact: dict[str, Any]) -> str:
    label = str(fact.get("label") or "").strip()
    value = fact.get("value")
    series_id = label.split(" ", 1)[0].upper() if label else ""
    series_label = _macro_series_label(series_id)
    if "change from previous observation" in label:
        return f"{series_label} changed by {value} from the previous observation"
    if "latest observation" in label:
        return f"{series_label} latest observation was {value}"
    return f"{series_label}: {value}" if series_label and value not in (None, "") else ""


def _macro_series_label(series_id: str) -> str:
    labels = {
        "FEDFUNDS": "Fed funds rate",
        "DGS10": "10-year Treasury yield",
        "DGS2": "2-year Treasury yield",
        "T10Y2Y": "10-year minus 2-year Treasury spread",
        "CPIAUCSL": "consumer inflation",
        "CPILFESL": "core consumer inflation",
        "UNRATE": "unemployment rate",
        "PAYEMS": "nonfarm payrolls",
        "INDPRO": "industrial production",
        "USREC": "recession indicator",
    }
    return labels.get(series_id, series_id.replace("_", " ").lower())
