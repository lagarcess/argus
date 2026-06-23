from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from argus.api.schemas import (
    BacktestRun,
    DecisionNote,
    DecisionState,
    EvidenceArtifact,
    Idea,
    IdeaVersion,
)

_MARKDOWN_HEADING_PREFIX_RE = re.compile(r"(?m)^\s{0,3}#{1,6}\s+")
_MARKDOWN_BULLET_PREFIX_RE = re.compile(r"(?m)^\s*[-*]\s+")
_MARKDOWN_EMPHASIS_RE = re.compile(r"[*`]+")
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class CapturedEvidence:
    idea: Idea
    idea_version: IdeaVersion
    evidence_artifact: EvidenceArtifact


def build_backtest_evidence_capture(
    *,
    run: BacktestRun,
    idea_id: str,
    idea_version_id: str,
    evidence_artifact_id: str,
    now: datetime,
) -> CapturedEvidence:
    title = _title_from_run(run)
    digest = evidence_digest_from_run(run)
    idea = Idea(
        id=idea_id,
        source_conversation_id=run.conversation_id,
        title=title,
        summary=digest,
        lifecycle="captured",
        active_version_id=idea_version_id,
        created_at=now,
        updated_at=now,
    )
    idea_version = IdeaVersion(
        id=idea_version_id,
        idea_id=idea_id,
        source_conversation_id=run.conversation_id,
        source_run_id=run.id,
        version_number=1,
        canonical_spec=_canonical_spec_from_run(run),
        strategy_snapshot=dict(run.config_snapshot),
        title=title,
        summary=digest,
        lifecycle="captured",
        created_at=now,
    )
    evidence_artifact = EvidenceArtifact(
        id=evidence_artifact_id,
        idea_id=idea_id,
        idea_version_id=idea_version_id,
        source_conversation_id=run.conversation_id,
        source_run_id=run.id,
        artifact_type="backtest",
        lifecycle="captured",
        title=title,
        digest=digest,
        payload=_payload_from_run(run, digest=digest),
        created_at=now,
        updated_at=now,
    )
    return CapturedEvidence(
        idea=idea,
        idea_version=idea_version,
        evidence_artifact=evidence_artifact,
    )


def build_decision_note(
    *,
    evidence_artifact: EvidenceArtifact,
    decision_id: str,
    decision_state: DecisionState,
    note: str | None,
    now: datetime,
) -> DecisionNote:
    return DecisionNote(
        id=decision_id,
        idea_id=evidence_artifact.idea_id,
        idea_version_id=evidence_artifact.idea_version_id,
        evidence_artifact_id=evidence_artifact.id,
        source_conversation_id=evidence_artifact.source_conversation_id,
        decision_state=decision_state,
        note=note,
        created_at=now,
        updated_at=now,
    )


def attach_decision_to_result_card(
    card: dict[str, Any],
    *,
    decision_id: str,
    decision_state: DecisionState,
) -> dict[str, Any]:
    return {
        **card,
        "decision_note_id": decision_id,
        "decision_state": decision_state,
        "evidence_lifecycle": "decided",
    }


def evidence_digest_from_run(run: BacktestRun) -> str:
    card = (
        run.conversation_result_card
        if isinstance(run.conversation_result_card, dict)
        else {}
    )
    quick_take = _safe_preview_text(card.get("quick_take"))
    if quick_take is not None:
        return quick_take
    row_text = " ".join(
        str(row.get("value") or "")
        for row in card.get("rows", [])
        if isinstance(row, dict)
    ).strip()
    symbols = ", ".join(run.symbols)
    benchmark = run.benchmark_symbol
    if row_text:
        return f"{symbols} backtest versus {benchmark}. {row_text}"
    return f"{symbols} backtest versus {benchmark}."


def evidence_preview_from_artifact(artifact: EvidenceArtifact) -> dict[str, Any]:
    return evidence_preview_from_payload(
        digest=artifact.digest,
        title=artifact.title,
        payload=artifact.payload,
    )


def evidence_preview_from_payload(
    *,
    digest: object,
    title: object = None,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        provenance = {}
    result_card = payload.get("result_card")
    if not isinstance(result_card, dict):
        result_card = {}
    preview: dict[str, Any] = {
        "digest": _safe_text(digest) or _safe_text(title),
        "symbols": _safe_text_list(
            provenance.get("symbols") or result_card.get("symbols")
        ),
        "benchmark_symbol": _safe_text(
            provenance.get("benchmark_symbol") or result_card.get("benchmark_symbol")
        ),
        "assumptions": _safe_text_list(
            payload.get("assumptions") or result_card.get("assumptions")
        ),
        "metrics_summary": _metrics_summary(payload.get("metrics")),
    }
    quick_take = _safe_preview_text(
        payload.get("quick_take") or result_card.get("quick_take")
    )
    if quick_take is not None:
        preview["quick_take"] = quick_take
    breakdown = _safe_breakdown(
        payload.get("breakdown") or result_card.get("breakdown")
    )
    if breakdown is not None:
        preview["breakdown"] = breakdown
    return {
        key: value
        for key, value in preview.items()
        if value is not None and value != [] and value != {}
    }


def _title_from_run(run: BacktestRun) -> str:
    card = (
        run.conversation_result_card
        if isinstance(run.conversation_result_card, dict)
        else {}
    )
    title = card.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return f"{', '.join(run.symbols)} Backtest"


def _canonical_spec_from_run(run: BacktestRun) -> dict[str, Any]:
    return {
        "asset_class": run.asset_class,
        "symbols": list(run.symbols),
        "allocation_method": run.allocation_method,
        "benchmark_symbol": run.benchmark_symbol,
        "config_snapshot": dict(run.config_snapshot),
    }


def _payload_from_run(run: BacktestRun, *, digest: str) -> dict[str, Any]:
    card = (
        run.conversation_result_card
        if isinstance(run.conversation_result_card, dict)
        else {}
    )
    safe_card = {
        key: card.get(key)
        for key in (
            "title",
            "symbols",
            "strategy_label",
            "asset_class",
            "date_range",
            "status_label",
            "rows",
            "benchmark_note",
            "assumptions",
            "quick_take",
            "breakdown",
        )
        if key in card
    }
    quick_take = _safe_preview_text(card.get("quick_take"))
    breakdown = _safe_breakdown(card.get("breakdown"))
    assumptions = _safe_text_list(card.get("assumptions"))
    if assumptions:
        safe_card["assumptions"] = assumptions
    if quick_take is not None:
        safe_card["quick_take"] = quick_take
    if breakdown is not None:
        safe_card["breakdown"] = breakdown
    return {
        "artifact_type": "backtest",
        "digest": digest,
        "source": {
            "run_id": run.id,
            "conversation_id": run.conversation_id,
            "strategy_id": run.strategy_id,
        },
        "assumptions": assumptions,
        "metrics": run.metrics,
        "quick_take": quick_take,
        "breakdown": breakdown,
        "result_card": safe_card,
        "chart_summary": _chart_summary(run.chart),
        "provenance": {
            "asset_class": run.asset_class,
            "symbols": list(run.symbols),
            "benchmark_symbol": run.benchmark_symbol,
            "created_at": run.created_at.isoformat(),
        },
    }


def _chart_summary(chart: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(chart, dict):
        return None
    series = chart.get("series")
    return {
        "kind": chart.get("kind"),
        "points": len(series) if isinstance(series, list) else 0,
        "currency": chart.get("currency"),
        "value_summary": chart.get("value_summary"),
    }


def _safe_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _safe_preview_text(value: object) -> str | None:
    normalized = _safe_text(value)
    if normalized is None:
        return None
    normalized = _MARKDOWN_HEADING_PREFIX_RE.sub("", normalized)
    normalized = _MARKDOWN_BULLET_PREFIX_RE.sub("", normalized)
    normalized = _MARKDOWN_EMPHASIS_RE.sub("", normalized)
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip()
    return normalized or None


def _safe_text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    safe_values: list[str] = []
    for item in value:
        normalized = _safe_preview_text(item)
        if normalized is not None:
            safe_values.append(normalized)
    return safe_values


def _safe_breakdown(value: object) -> object | None:
    if isinstance(value, str):
        return _safe_preview_text(value)
    if isinstance(value, dict):
        safe: dict[str, object] = {}
        for key, raw in value.items():
            if not isinstance(key, str) or key.endswith("_id"):
                continue
            if isinstance(raw, str):
                normalized = _safe_preview_text(raw)
                if normalized is not None:
                    safe[key] = normalized
            elif isinstance(raw, list):
                values = _safe_text_list(raw)
                if values:
                    safe[key] = values
        return safe or None
    return None


def _metrics_summary(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    performance = value.get("aggregate")
    if isinstance(performance, dict):
        performance = performance.get("performance")
    if not isinstance(performance, dict):
        return {}
    summary: dict[str, object] = {}
    for key in (
        "total_return_pct",
        "benchmark_return_pct",
        "delta_vs_benchmark_pct",
        "max_drawdown_pct",
        "sharpe_ratio",
    ):
        metric = performance.get(key)
        if isinstance(metric, int | float | str) and metric != "":
            summary[key] = metric
    return summary
