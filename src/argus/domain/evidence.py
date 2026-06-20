from __future__ import annotations

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
    provenance = artifact.payload.get("provenance")
    if not isinstance(provenance, dict):
        provenance = {}
    return {
        "digest": artifact.digest,
        "symbols": provenance.get("symbols") if isinstance(provenance, dict) else [],
        "benchmark_symbol": provenance.get("benchmark_symbol"),
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
        )
        if key in card
    }
    return {
        "artifact_type": "backtest",
        "digest": digest,
        "source": {
            "run_id": run.id,
            "conversation_id": run.conversation_id,
            "strategy_id": run.strategy_id,
        },
        "assumptions": list(card.get("assumptions") or []),
        "metrics": run.metrics,
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
