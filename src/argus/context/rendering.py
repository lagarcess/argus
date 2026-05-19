from __future__ import annotations

from typing import Any


def context_packet_fact_summary(context_packets: list[dict[str, Any]]) -> dict[str, str]:
    summaries: list[str] = []
    limitations: list[str] = []
    packet_ids: list[str] = []
    for packet in context_packets:
        if not isinstance(packet, dict):
            continue
        packet_id = str(packet.get("id") or "").strip()
        if packet_id:
            packet_ids.append(packet_id)
        provider = str(packet.get("provider") or "").strip()
        packet_type = str(packet.get("packet_type") or "").strip()
        for fact in _packet_facts(packet):
            label = str(fact.get("label") or "").strip()
            value = fact.get("value")
            if label:
                summaries.append(f"{provider}/{packet_type}: {label} = {value}")
        for limitation in packet.get("limitations") or []:
            text = str(limitation).strip()
            if text and text not in limitations:
                limitations.append(text)
    result: dict[str, str] = {}
    if packet_ids:
        result["context_packet_ids"] = ", ".join(packet_ids)
    if summaries:
        result["context_packet_facts"] = "; ".join(summaries[:8])
    if limitations:
        result["context_packet_limitations"] = "; ".join(limitations[:6])
    return result


def _packet_facts(packet: dict[str, Any]) -> list[dict[str, Any]]:
    facts = packet.get("facts")
    if not isinstance(facts, list):
        return []
    return [fact for fact in facts if isinstance(fact, dict)]
