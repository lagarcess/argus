from __future__ import annotations

from typing import Any, Protocol

from argus.api.schemas import BacktestRun, EvidenceArtifact, Idea, IdeaVersion
from argus.domain.backtest_finalization import (
    FinalizedBacktest,
    PreparedBacktestFinalization,
)
from argus.domain.evidence import CapturedEvidence


class _RpcResult(Protocol):
    data: Any


class _RpcRequest(Protocol):
    def execute(self) -> _RpcResult: ...


class _RpcClient(Protocol):
    def rpc(self, function_name: str, params: dict[str, Any]) -> _RpcRequest: ...


def finalize_backtest(
    client: _RpcClient,
    *,
    finalization: PreparedBacktestFinalization,
) -> FinalizedBacktest:
    captured = finalization.captured
    result = client.rpc(
        "finalize_backtest_completion",
        {
            "p_user_id": finalization.user_id,
            "p_execution_identity": finalization.execution_identity,
            "p_run": finalization.run.model_dump(mode="json"),
            "p_idea": captured.idea.model_dump(mode="json"),
            "p_idea_version": captured.idea_version.model_dump(mode="json"),
            "p_evidence_artifact": captured.evidence_artifact.model_dump(mode="json"),
        },
    ).execute()
    data = getattr(result, "data", None)
    if not data:
        row = None
    elif isinstance(data, list):
        row = data[0]
    else:
        row = data
    if row is None:
        raise RuntimeError("Backtest finalization did not return durable artifact state.")
    return FinalizedBacktest(
        run=BacktestRun.model_validate(row["run"]),
        captured=CapturedEvidence(
            idea=Idea.model_validate(row["idea"]),
            idea_version=IdeaVersion.model_validate(row["idea_version"]),
            evidence_artifact=EvidenceArtifact.model_validate(row["evidence_artifact"]),
        ),
    )
