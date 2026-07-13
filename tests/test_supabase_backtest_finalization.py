from types import SimpleNamespace
from typing import Any

import pytest
from argus.api.schemas import BacktestRun
from argus.domain.backtest_finalization import PreparedBacktestFinalization
from argus.domain.evidence import build_backtest_evidence_capture
from argus.domain.store import utcnow
from argus.domain.supabase_backtest_finalization import finalize_backtest


class _RecordingRpcClient:
    def __init__(self, *, return_row: bool = True) -> None:
        self.return_row = return_row
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def rpc(self, function_name: str, params: dict[str, Any]):
        self.calls.append((function_name, params))
        return _RecordingRpcRequest(params, return_row=self.return_row)


class _RecordingRpcRequest:
    def __init__(self, params: dict[str, Any], *, return_row: bool) -> None:
        self.params = params
        self.return_row = return_row

    def execute(self) -> SimpleNamespace:
        if not self.return_row:
            return SimpleNamespace(data=[])
        return SimpleNamespace(
            data=[
                {
                    "run": self.params["p_run"],
                    "idea": self.params["p_idea"],
                    "idea_version": self.params["p_idea_version"],
                    "evidence_artifact": self.params["p_evidence_artifact"],
                }
            ]
        )


class _FailingRpcClient:
    def rpc(self, function_name: str, params: dict[str, Any]):
        raise ConnectionError("rpc unavailable")


def _prepared_finalization() -> PreparedBacktestFinalization:
    now = utcnow()
    run = BacktestRun(
        id="run-1",
        conversation_id="conversation-1",
        status="completed",
        asset_class="equity",
        symbols=["AAPL"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={"aggregate": {"performance": {"total_return_pct": 12.4}}},
        config_snapshot={"template": "buy_and_hold", "symbols": ["AAPL"]},
        conversation_result_card={
            "title": "AAPL buy and hold",
            "rows": [
                {
                    "key": "total_return_pct",
                    "label": "Total Return",
                    "value": "+12.4%",
                }
            ],
            "assumptions": ["Benchmark: SPY"],
        },
        created_at=now,
        chart=None,
        trades=[],
    )
    captured = build_backtest_evidence_capture(
        run=run,
        idea_id="idea-1",
        idea_version_id="version-1",
        evidence_artifact_id="artifact-1",
        now=now,
    )
    return PreparedBacktestFinalization(
        user_id="user-1",
        execution_identity="backtest_job:job-1",
        run=run,
        captured=captured,
    )


def test_finalize_backtest_uses_existing_rpc_contract() -> None:
    finalization = _prepared_finalization()
    client = _RecordingRpcClient()

    finalized = finalize_backtest(client, finalization=finalization)

    assert [name for name, _params in client.calls] == ["finalize_backtest_completion"]
    params = client.calls[0][1]
    assert params["p_user_id"] == finalization.user_id
    assert params["p_execution_identity"] == finalization.execution_identity
    assert params["p_run"] == finalization.run.model_dump(mode="json")
    assert params["p_idea"] == finalization.captured.idea.model_dump(mode="json")
    assert params["p_idea_version"] == finalization.captured.idea_version.model_dump(
        mode="json"
    )
    assert params["p_evidence_artifact"] == (
        finalization.captured.evidence_artifact.model_dump(mode="json")
    )
    assert finalized.identity.run_id == finalization.run.id
    assert finalized.identity.evidence_artifact_id == (
        finalization.captured.evidence_artifact.id
    )


def test_finalize_backtest_rejects_missing_durable_state() -> None:
    client = _RecordingRpcClient(return_row=False)

    with pytest.raises(
        RuntimeError,
        match="Backtest finalization did not return durable artifact state",
    ):
        finalize_backtest(client, finalization=_prepared_finalization())


def test_finalize_backtest_propagates_rpc_failure() -> None:
    with pytest.raises(ConnectionError, match="rpc unavailable"):
        finalize_backtest(
            _FailingRpcClient(),
            finalization=_prepared_finalization(),
        )
