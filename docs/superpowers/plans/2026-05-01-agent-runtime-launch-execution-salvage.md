# Agent Runtime Launch Execution Salvage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the runtime stub with real launch-bounded execution for `buy_and_hold`, `dca_accumulation`, and `indicator_threshold`, then cut `/api/v1/chat/stream` over to the new runtime without breaking the existing result card experience.

**Architecture:** Add a new `engine_launch` boundary under `src/argus/domain/` that accepts a normalized adapter request and returns a normalized execution envelope. The conversational runtime will keep first-class strategy types, map them into the adapter contract, and use the richer envelope for both result-card mapping and explanation while preserving graceful conversational fallback on unsupported or failed execution.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, existing `argus.agent_runtime` package, existing `argus.domain.engine` logic, selected salvage from `archive-v0.1`, pytest, current web result-card contract.

---

## File Structure

**Create**
- `src/argus/domain/engine_launch/__init__.py`
- `src/argus/domain/engine_launch/models.py`
- `src/argus/domain/engine_launch/sizing.py`
- `src/argus/domain/engine_launch/cadence.py`
- `src/argus/domain/engine_launch/strategies.py`
- `src/argus/domain/engine_launch/results.py`
- `src/argus/domain/engine_launch/adapter.py`
- `src/argus/agent_runtime/tools/real_backtest.py`
- `tests/agent_runtime/test_real_backtest_tool.py`
- `tests/domain/test_engine_launch.py`
- `tests/api/test_chat_runtime_cutover.py`

**Modify**
- `src/argus/agent_runtime/state/models.py`
- `src/argus/agent_runtime/stages/confirm.py`
- `src/argus/agent_runtime/stages/execute.py`
- `src/argus/agent_runtime/stages/explain.py`
- `src/argus/agent_runtime/runtime.py`
- `src/argus/api/main.py`
- `src/argus/domain/engine.py`
- `tests/agent_runtime/test_execute_recovery.py`
- `tests/agent_runtime/test_workflow.py`

**Reference only**
- `archive-v0.1/src/argus/engine.py`
- `archive-v0.1/src/argus/analysis/indicators.py`
- `archive-v0.1/src/argus/market/data_provider.py`

**Keep unchanged for this slice**
- `src/argus/agent_runtime/stages/interpret.py`
- `src/argus/agent_runtime/stages/clarify.py`
- `src/argus/agent_runtime/session/manager.py`
- `web/**` unless the preserved result-card contract proves incomplete during API verification

This slice is execution-focused. It should salvage engine capability into a new boundary, not reopen extraction or session design unless a launch-critical gap is uncovered.

### Task 1: Define The Launch Adapter Contract

**Files:**
- Create: `src/argus/domain/engine_launch/models.py`
- Modify: `src/argus/agent_runtime/state/models.py`
- Test: `tests/domain/test_engine_launch.py`

- [ ] **Step 1: Write the failing launch-model tests**

```python
from argus.domain.engine_launch.models import (
    LaunchBacktestRequest,
    LaunchExecutionEnvelope,
)


def test_launch_request_supports_three_strategy_types() -> None:
    request = LaunchBacktestRequest(
        strategy_type="buy_and_hold",
        symbol="TSLA",
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_rule=None,
        exit_rule=None,
        sizing_mode="capital_amount",
        capital_amount=10000.0,
        position_size=None,
        cadence=None,
        parameters={},
        risk_rules=[],
        benchmark_symbol="SPY",
    )

    assert request.strategy_type == "buy_and_hold"
    assert request.cadence is None


def test_launch_envelope_carries_card_and_explanation_fields() -> None:
    envelope = LaunchExecutionEnvelope(
        execution_status="succeeded",
        resolved_strategy={"strategy_type": "buy_and_hold", "symbol": "TSLA"},
        resolved_parameters={"timeframe": "1D"},
        metrics={"total_return_pct": 12.5},
        benchmark_metrics={"total_return_pct": 9.2},
        assumptions=["Starting capital: $10,000."],
        caveats=["Daily bars only."],
        artifact_references=[],
        provider_metadata={"provider": "alpaca"},
    )

    assert envelope.execution_status == "succeeded"
    assert envelope.metrics["total_return_pct"] == 12.5
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
poetry run pytest tests/domain/test_engine_launch.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'argus.domain.engine_launch'
```

- [ ] **Step 3: Add the normalized launch models**

Create `src/argus/domain/engine_launch/models.py`:

```python
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


LaunchStrategyType = Literal["buy_and_hold", "dca_accumulation", "indicator_threshold"]
SizingMode = Literal["capital_amount", "position_size"]
Cadence = Literal["daily", "weekly", "monthly", "quarterly"]
ExecutionStatus = Literal[
    "succeeded",
    "blocked_unsupported",
    "blocked_invalid_input",
    "failed_upstream",
    "failed_internal",
]


class DateRange(BaseModel):
    start: str
    end: str


class LaunchBacktestRequest(BaseModel):
    strategy_type: LaunchStrategyType
    symbol: str
    timeframe: str
    date_range: DateRange
    entry_rule: dict[str, Any] | None = None
    exit_rule: dict[str, Any] | None = None
    sizing_mode: SizingMode
    capital_amount: float | None = None
    position_size: float | None = None
    cadence: Cadence | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    risk_rules: list[dict[str, Any]] = Field(default_factory=list)
    benchmark_symbol: str

    @model_validator(mode="after")
    def validate_sizing_and_cadence(self) -> "LaunchBacktestRequest":
        if self.sizing_mode == "capital_amount" and self.capital_amount is None:
            raise ValueError("capital_amount_required")
        if self.sizing_mode == "position_size" and self.position_size is None:
            raise ValueError("position_size_required")
        if self.strategy_type == "dca_accumulation" and self.cadence is None:
            raise ValueError("cadence_required")
        if self.strategy_type != "dca_accumulation" and self.cadence is not None:
            raise ValueError("cadence_not_applicable")
        return self


class LaunchExecutionEnvelope(BaseModel):
    execution_status: ExecutionStatus
    resolved_strategy: dict[str, Any]
    resolved_parameters: dict[str, Any]
    metrics: dict[str, Any]
    benchmark_metrics: dict[str, Any]
    assumptions: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    artifact_references: list[dict[str, Any]] = Field(default_factory=list)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
    failure_category: str | None = None
    failure_reason: str | None = None
```

- [ ] **Step 4: Expose a launch result payload in runtime state**

Update `src/argus/agent_runtime/state/models.py`:

```python
class FinalResponsePayload(BaseModel):
    result_card: dict[str, Any] | None = None
    explanation_context: dict[str, Any] | None = None
```

Use this payload for the richer execution result that the API can serialize without exposing the full engine envelope directly.

- [ ] **Step 5: Run the targeted model test to verify it passes**

Run:

```bash
poetry run pytest tests/domain/test_engine_launch.py -v
```

Expected:

```text
tests/domain/test_engine_launch.py ... PASSED
```

- [ ] **Step 6: Commit**

```bash
git add src/argus/domain/engine_launch/models.py src/argus/agent_runtime/state/models.py tests/domain/test_engine_launch.py
git commit -m "feat(engine-launch): add launch adapter models"
```

### Task 2: Build Buy-And-Hold Execution First

**Files:**
- Create: `src/argus/domain/engine_launch/__init__.py`
- Create: `src/argus/domain/engine_launch/sizing.py`
- Create: `src/argus/domain/engine_launch/results.py`
- Create: `src/argus/domain/engine_launch/adapter.py`
- Modify: `src/argus/domain/engine.py`
- Test: `tests/domain/test_engine_launch.py`

- [ ] **Step 1: Write the failing buy-and-hold execution test**

```python
from argus.domain.engine_launch.adapter import run_launch_backtest
from argus.domain.engine_launch.models import LaunchBacktestRequest


def test_run_launch_backtest_executes_buy_and_hold() -> None:
    request = LaunchBacktestRequest(
        strategy_type="buy_and_hold",
        symbol="TSLA",
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_rule=None,
        exit_rule=None,
        sizing_mode="capital_amount",
        capital_amount=10000.0,
        position_size=None,
        cadence=None,
        parameters={},
        risk_rules=[],
        benchmark_symbol="SPY",
    )

    envelope = run_launch_backtest(request)

    assert envelope.execution_status == "succeeded"
    assert envelope.resolved_strategy["strategy_type"] == "buy_and_hold"
    assert "total_return_pct" in envelope.metrics
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
poetry run pytest tests/domain/test_engine_launch.py::test_run_launch_backtest_executes_buy_and_hold -v
```

Expected:

```text
ImportError: cannot import name 'run_launch_backtest'
```

- [ ] **Step 3: Add sizing resolution and result-envelope helpers**

Create `src/argus/domain/engine_launch/sizing.py`:

```python
from __future__ import annotations

from argus.domain.engine_launch.models import LaunchBacktestRequest


def resolve_starting_capital(request: LaunchBacktestRequest) -> float:
    if request.sizing_mode == "capital_amount":
        return float(request.capital_amount)
    return float(request.position_size)
```

Create `src/argus/domain/engine_launch/results.py`:

```python
from __future__ import annotations

from typing import Any

from argus.domain.engine_launch.models import LaunchExecutionEnvelope


def build_success_envelope(
    *,
    resolved_strategy: dict[str, Any],
    resolved_parameters: dict[str, Any],
    metrics: dict[str, Any],
    benchmark_metrics: dict[str, Any],
    assumptions: list[str],
    caveats: list[str],
    provider_metadata: dict[str, Any],
) -> LaunchExecutionEnvelope:
    return LaunchExecutionEnvelope(
        execution_status="succeeded",
        resolved_strategy=resolved_strategy,
        resolved_parameters=resolved_parameters,
        metrics=metrics,
        benchmark_metrics=benchmark_metrics,
        assumptions=assumptions,
        caveats=caveats,
        provider_metadata=provider_metadata,
    )
```

- [ ] **Step 4: Implement buy-and-hold on top of current engine capabilities**

Create `src/argus/domain/engine_launch/adapter.py`:

```python
from __future__ import annotations

from argus.domain.engine import build_result_card, compute_alpha_metrics
from argus.domain.engine import normalize_backtest_config, validate_backtest_config
from argus.domain.engine_launch.models import LaunchBacktestRequest, LaunchExecutionEnvelope
from argus.domain.engine_launch.results import build_success_envelope
from argus.domain.engine_launch.sizing import resolve_starting_capital


def run_launch_backtest(request: LaunchBacktestRequest) -> LaunchExecutionEnvelope:
    config = normalize_backtest_config(
        {
            "template": "buy_and_hold",
            "symbols": [request.symbol],
            "timeframe": request.timeframe,
            "start_date": request.date_range.start,
            "end_date": request.date_range.end,
            "starting_capital": resolve_starting_capital(request),
            "benchmark_symbol": request.benchmark_symbol,
            "parameters": {},
        }
    )
    validate_backtest_config(config)
    metrics = compute_alpha_metrics(config)
    return build_success_envelope(
        resolved_strategy={"strategy_type": "buy_and_hold", "symbol": request.symbol},
        resolved_parameters={"timeframe": request.timeframe},
        metrics=metrics["aggregate"]["performance"],
        benchmark_metrics={
            "benchmark_symbol": request.benchmark_symbol,
            "benchmark_return_pct": metrics["aggregate"]["performance"]["benchmark_return_pct"],
        },
        assumptions=[
            f"Starting capital: ${resolve_starting_capital(request):,.0f}.",
            "Daily or supported intraday bars only.",
        ],
        caveats=[],
        provider_metadata={"provider": "alpaca"},
    )
```

Create `src/argus/domain/engine_launch/__init__.py`:

```python
from argus.domain.engine_launch.adapter import run_launch_backtest

__all__ = ["run_launch_backtest"]
```

- [ ] **Step 5: Run the targeted buy-and-hold test to verify it passes**

Run:

```bash
poetry run pytest tests/domain/test_engine_launch.py::test_run_launch_backtest_executes_buy_and_hold -v
```

Expected:

```text
tests/domain/test_engine_launch.py::test_run_launch_backtest_executes_buy_and_hold PASSED
```

- [ ] **Step 6: Commit**

```bash
git add src/argus/domain/engine_launch/__init__.py src/argus/domain/engine_launch/sizing.py src/argus/domain/engine_launch/results.py src/argus/domain/engine_launch/adapter.py tests/domain/test_engine_launch.py
git commit -m "feat(engine-launch): add buy and hold execution path"
```

### Task 3: Add DCA Cadence Execution

**Files:**
- Create: `src/argus/domain/engine_launch/cadence.py`
- Modify: `src/argus/domain/engine_launch/adapter.py`
- Modify: `src/argus/domain/engine.py`
- Test: `tests/domain/test_engine_launch.py`

- [ ] **Step 1: Write the failing DCA execution test**

```python
from argus.domain.engine_launch.adapter import run_launch_backtest
from argus.domain.engine_launch.models import LaunchBacktestRequest


def test_run_launch_backtest_executes_dca_accumulation() -> None:
    request = LaunchBacktestRequest(
        strategy_type="dca_accumulation",
        symbol="TSLA",
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_rule=None,
        exit_rule=None,
        sizing_mode="capital_amount",
        capital_amount=500.0,
        position_size=None,
        cadence="monthly",
        parameters={},
        risk_rules=[],
        benchmark_symbol="SPY",
    )

    envelope = run_launch_backtest(request)

    assert envelope.execution_status == "succeeded"
    assert envelope.resolved_strategy["strategy_type"] == "dca_accumulation"
    assert envelope.resolved_parameters["cadence"] == "monthly"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
poetry run pytest tests/domain/test_engine_launch.py::test_run_launch_backtest_executes_dca_accumulation -v
```

Expected:

```text
AssertionError: resolved strategy type does not match
```

- [ ] **Step 3: Add cadence normalization**

Create `src/argus/domain/engine_launch/cadence.py`:

```python
from __future__ import annotations

from argus.domain.engine_launch.models import Cadence


def resolve_dca_cadence(value: Cadence | None) -> str:
    return (value or "weekly").lower()
```

- [ ] **Step 4: Route DCA requests through the current engine**

Update `src/argus/domain/engine_launch/adapter.py`:

```python
from argus.domain.engine_launch.cadence import resolve_dca_cadence


def run_launch_backtest(request: LaunchBacktestRequest) -> LaunchExecutionEnvelope:
    if request.strategy_type == "dca_accumulation":
        config = normalize_backtest_config(
            {
                "template": "dca_accumulation",
                "symbols": [request.symbol],
                "timeframe": request.timeframe,
                "start_date": request.date_range.start,
                "end_date": request.date_range.end,
                "starting_capital": resolve_starting_capital(request),
                "benchmark_symbol": request.benchmark_symbol,
                "parameters": {"dca_cadence": resolve_dca_cadence(request.cadence)},
            }
        )
        validate_backtest_config(config)
        metrics = compute_alpha_metrics(config)
        return build_success_envelope(
            resolved_strategy={"strategy_type": "dca_accumulation", "symbol": request.symbol},
            resolved_parameters={
                "timeframe": request.timeframe,
                "cadence": resolve_dca_cadence(request.cadence),
            },
            metrics=metrics["aggregate"]["performance"],
            benchmark_metrics={
                "benchmark_symbol": request.benchmark_symbol,
                "benchmark_return_pct": metrics["aggregate"]["performance"]["benchmark_return_pct"],
            },
            assumptions=[
                f"Recurring allocation: ${resolve_starting_capital(request):,.0f}.",
                f"Cadence: {resolve_dca_cadence(request.cadence)}.",
            ],
            caveats=[],
            provider_metadata={"provider": "alpaca"},
        )
```

Also update `src/argus/domain/engine.py` so `_build_signals()` supports `quarterly` alongside the already-added daily, weekly, and monthly cadence branches:

```python
        elif cadence == "quarterly":
            quarters = index.to_series().dt.to_period("Q")
            entries = quarters != quarters.shift(1)
```

- [ ] **Step 5: Run the DCA test to verify it passes**

Run:

```bash
poetry run pytest tests/domain/test_engine_launch.py::test_run_launch_backtest_executes_dca_accumulation -v
```

Expected:

```text
tests/domain/test_engine_launch.py::test_run_launch_backtest_executes_dca_accumulation PASSED
```

- [ ] **Step 6: Commit**

```bash
git add src/argus/domain/engine_launch/cadence.py src/argus/domain/engine_launch/adapter.py src/argus/domain/engine.py tests/domain/test_engine_launch.py
git commit -m "feat(engine-launch): add dca accumulation execution"
```

### Task 4: Add Indicator-Threshold Execution And Unsupported Guards

**Files:**
- Create: `src/argus/domain/engine_launch/strategies.py`
- Modify: `src/argus/domain/engine_launch/adapter.py`
- Create: `src/argus/agent_runtime/tools/real_backtest.py`
- Test: `tests/domain/test_engine_launch.py`
- Test: `tests/agent_runtime/test_real_backtest_tool.py`

- [ ] **Step 1: Write the failing indicator-threshold tests**

```python
from argus.domain.engine_launch.adapter import run_launch_backtest
from argus.domain.engine_launch.models import LaunchBacktestRequest


def test_run_launch_backtest_executes_indicator_threshold() -> None:
    request = LaunchBacktestRequest(
        strategy_type="indicator_threshold",
        symbol="TSLA",
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_rule={"indicator": "rsi", "operator": "below", "threshold": 30},
        exit_rule={"indicator": "rsi", "operator": "above", "threshold": 55},
        sizing_mode="capital_amount",
        capital_amount=10000.0,
        position_size=None,
        cadence=None,
        parameters={},
        risk_rules=[],
        benchmark_symbol="SPY",
    )

    envelope = run_launch_backtest(request)

    assert envelope.execution_status == "succeeded"
    assert envelope.resolved_strategy["strategy_type"] == "indicator_threshold"


def test_run_launch_backtest_blocks_unsupported_risk_rules() -> None:
    request = LaunchBacktestRequest(
        strategy_type="buy_and_hold",
        symbol="TSLA",
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_rule=None,
        exit_rule=None,
        sizing_mode="capital_amount",
        capital_amount=10000.0,
        position_size=None,
        cadence=None,
        parameters={},
        risk_rules=[{"type": "stop_loss", "threshold_pct": 5}],
        benchmark_symbol="SPY",
    )

    envelope = run_launch_backtest(request)

    assert envelope.execution_status == "blocked_unsupported"
    assert envelope.failure_category == "unsupported_capability"
```

- [ ] **Step 2: Run the indicator-threshold tests to verify they fail**

Run:

```bash
poetry run pytest tests/domain/test_engine_launch.py::test_run_launch_backtest_executes_indicator_threshold tests/domain/test_engine_launch.py::test_run_launch_backtest_blocks_unsupported_risk_rules -v
```

Expected:

```text
AssertionError: indicator threshold path not implemented
```

- [ ] **Step 3: Add launch strategy normalization helpers**

Create `src/argus/domain/engine_launch/strategies.py`:

```python
from __future__ import annotations

from argus.domain.engine_launch.models import LaunchBacktestRequest


def normalize_template_name(request: LaunchBacktestRequest) -> str:
    if request.strategy_type == "buy_and_hold":
        return "buy_and_hold"
    if request.strategy_type == "dca_accumulation":
        return "dca_accumulation"
    return "rsi_mean_reversion"


def validate_launch_supported(request: LaunchBacktestRequest) -> None:
    if request.risk_rules:
        raise ValueError("unsupported_risk_rules")
    if request.strategy_type == "indicator_threshold":
        if not request.entry_rule or not request.exit_rule:
            raise ValueError("missing_threshold_rules")
```

- [ ] **Step 4: Implement threshold execution and the real runtime tool**

Update `src/argus/domain/engine_launch/adapter.py`:

```python
from argus.domain.engine_launch.strategies import normalize_template_name, validate_launch_supported


def run_launch_backtest(request: LaunchBacktestRequest) -> LaunchExecutionEnvelope:
    try:
        validate_launch_supported(request)
    except ValueError as exc:
        return LaunchExecutionEnvelope(
            execution_status="blocked_unsupported",
            resolved_strategy={"strategy_type": request.strategy_type, "symbol": request.symbol},
            resolved_parameters={},
            metrics={},
            benchmark_metrics={},
            failure_category="unsupported_capability",
            failure_reason=str(exc),
        )

    template = normalize_template_name(request)
    parameters = {}
    if request.strategy_type == "indicator_threshold":
        parameters = {
            "entry_rule": request.entry_rule,
            "exit_rule": request.exit_rule,
        }
```

Create `src/argus/agent_runtime/tools/real_backtest.py`:

```python
from __future__ import annotations

from typing import Any

from argus.domain.engine_launch.adapter import run_launch_backtest
from argus.domain.engine_launch.models import LaunchBacktestRequest


class RealBacktestTool:
    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = LaunchBacktestRequest.model_validate(payload)
        return run_launch_backtest(request).model_dump(mode="python")
```

Write `tests/agent_runtime/test_real_backtest_tool.py`:

```python
from argus.agent_runtime.tools.real_backtest import RealBacktestTool


def test_real_backtest_tool_returns_launch_envelope() -> None:
    tool = RealBacktestTool()

    result = tool.run(
        {
            "strategy_type": "buy_and_hold",
            "symbol": "TSLA",
            "timeframe": "1D",
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
            "entry_rule": None,
            "exit_rule": None,
            "sizing_mode": "capital_amount",
            "capital_amount": 10000.0,
            "position_size": None,
            "cadence": None,
            "parameters": {},
            "risk_rules": [],
            "benchmark_symbol": "SPY",
        }
    )

    assert result["execution_status"] == "succeeded"
```

- [ ] **Step 5: Run the targeted engine-launch and tool tests to verify they pass**

Run:

```bash
poetry run pytest tests/domain/test_engine_launch.py tests/agent_runtime/test_real_backtest_tool.py -v
```

Expected:

```text
tests/domain/test_engine_launch.py ... PASSED
tests/agent_runtime/test_real_backtest_tool.py ... PASSED
```

- [ ] **Step 6: Commit**

```bash
git add src/argus/domain/engine_launch/strategies.py src/argus/domain/engine_launch/adapter.py src/argus/agent_runtime/tools/real_backtest.py tests/domain/test_engine_launch.py tests/agent_runtime/test_real_backtest_tool.py
git commit -m "feat(engine-launch): add threshold execution and runtime tool"
```

### Task 5: Replace The Stub In Execute And Explain

**Files:**
- Modify: `src/argus/agent_runtime/stages/confirm.py`
- Modify: `src/argus/agent_runtime/stages/execute.py`
- Modify: `src/argus/agent_runtime/stages/explain.py`
- Modify: `src/argus/agent_runtime/runtime.py`
- Modify: `tests/agent_runtime/test_execute_recovery.py`
- Modify: `tests/agent_runtime/test_workflow.py`

- [ ] **Step 1: Write the failing runtime execution tests**

```python
from argus.agent_runtime.tools.real_backtest import RealBacktestTool
from argus.agent_runtime.stages.execute import execute_stage
from argus.agent_runtime.state.models import ConfirmationPayload, RunState


def test_execute_stage_uses_real_backtest_tool_payload() -> None:
    state = RunState.new(current_user_message="Backtest Tesla", recent_thread_history=[])
    state.confirmation_payload = ConfirmationPayload(
        strategy_summary="Run buy-and-hold on TSLA.",
        required_fields={},
        optional_fields={},
    )
    state.candidate_strategy_draft = {
        "strategy_type": "buy_and_hold",
        "asset_universe": "TSLA",
        "date_range": "last 1 year",
    }

    result = execute_stage(state=state, backtest_tool=RealBacktestTool())

    assert result.outcome == "execution_succeeded"
    assert result.patch["final_response_payload"]["result_card"] is not None
```

- [ ] **Step 2: Run the runtime execution tests to verify they fail**

Run:

```bash
poetry run pytest tests/agent_runtime/test_execute_recovery.py tests/agent_runtime/test_workflow.py -v
```

Expected:

```text
AssertionError: final_response_payload missing result_card
```

- [ ] **Step 3: Teach confirm and execute about launch strategy types**

Update `src/argus/agent_runtime/stages/confirm.py` so the confirmation payload includes the explicit strategy type:

```python
confirmation_summary = (
    f"Argus is about to run this as a {strategy_type_label} strategy for {symbol}."
)
```

Update `src/argus/agent_runtime/stages/execute.py` to build a `LaunchBacktestRequest`-shaped payload:

```python
payload = {
    "strategy_type": candidate_strategy["strategy_type"],
    "symbol": candidate_strategy["asset_universe"],
    "timeframe": resolved_optional_fields.get("timeframe", "1D"),
    "date_range": normalized_date_range,
    "entry_rule": candidate_strategy.get("entry_rule"),
    "exit_rule": candidate_strategy.get("exit_rule"),
    "sizing_mode": resolved_sizing_mode,
    "capital_amount": resolved_capital_amount,
    "position_size": resolved_position_size,
    "cadence": candidate_strategy.get("cadence"),
    "parameters": candidate_strategy.get("parameters", {}),
    "risk_rules": candidate_strategy.get("risk_rules", []),
    "benchmark_symbol": resolved_benchmark_symbol,
}
```

- [ ] **Step 4: Map the real envelope into result-card and explanation payloads**

Update `src/argus/agent_runtime/stages/explain.py`:

```python
def explain_stage(*, state: RunState) -> StageResult:
    payload = state.final_response_payload
    explanation_context = payload.explanation_context or {}
    result_card = payload.result_card or {}
    assumptions = explanation_context.get("assumptions", [])
    caveats = explanation_context.get("caveats", [])
```

Update `src/argus/agent_runtime/runtime.py` so `_public_result()` keeps `final_response_payload`, and ensure the workflow output carries:

```python
{
    "result_card": mapped_result_card,
    "explanation_context": {
        "resolved_strategy": envelope["resolved_strategy"],
        "metrics": envelope["metrics"],
        "benchmark_metrics": envelope["benchmark_metrics"],
        "assumptions": envelope["assumptions"],
        "caveats": envelope["caveats"],
    },
}
```

- [ ] **Step 5: Run the runtime execution tests to verify they pass**

Run:

```bash
poetry run pytest tests/agent_runtime/test_execute_recovery.py tests/agent_runtime/test_workflow.py -v
```

Expected:

```text
tests/agent_runtime/test_execute_recovery.py ... PASSED
tests/agent_runtime/test_workflow.py ... PASSED
```

- [ ] **Step 6: Commit**

```bash
git add src/argus/agent_runtime/stages/confirm.py src/argus/agent_runtime/stages/execute.py src/argus/agent_runtime/stages/explain.py src/argus/agent_runtime/runtime.py tests/agent_runtime/test_execute_recovery.py tests/agent_runtime/test_workflow.py
git commit -m "feat(agent-runtime): replace stub execution with launch adapter"
```

### Task 6: Cut `/api/v1/chat/stream` Over To The New Runtime

**Files:**
- Modify: `src/argus/api/main.py`
- Test: `tests/api/test_chat_runtime_cutover.py`

- [ ] **Step 1: Write the failing chat cutover API tests**

```python
from fastapi.testclient import TestClient

from argus.api.main import app


def test_chat_stream_uses_agent_runtime_for_buy_and_hold() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "message": "Buy and hold Tesla over the last year.",
            "thread_id": "launch-thread-1",
        },
        headers={"Authorization": "Bearer mock-token"},
    )

    assert response.status_code == 200
    assert "buy-and-hold" in response.text.lower()


def test_chat_stream_falls_back_conversationally_on_unsupported_request() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "message": "Backtest Tesla with a 5% trailing stop.",
            "thread_id": "launch-thread-2",
        },
        headers={"Authorization": "Bearer mock-token"},
    )

    assert response.status_code == 200
    assert "supported" in response.text.lower()
```

- [ ] **Step 2: Run the API tests to verify they fail**

Run:

```bash
poetry run pytest tests/api/test_chat_runtime_cutover.py -v
```

Expected:

```text
AssertionError: response still comes from legacy orchestrator
```

- [ ] **Step 3: Route `/api/v1/chat/stream` through `run_agent_turn(...)`**

Update `src/argus/api/main.py` at the `/api/v1/chat/stream` handler:

```python
runtime_result = run_agent_turn(
    workflow=agent_runtime_workflow,
    session_manager=agent_runtime_session_manager,
    user=UserState(user_id=user.id),
    thread_id=payload.thread_id or f"chat-{user.id}",
    message=payload.message,
)
```

Then map the runtime result into the existing streaming response shape:

```python
stream_payload = {
    "message": runtime_result.get("assistant_response") or runtime_result.get("assistant_prompt"),
    "result_card": (
        runtime_result.get("final_response_payload", {}).get("result_card")
        if runtime_result.get("final_response_payload")
        else None
    ),
}
```

Keep graceful fallback behavior by routing unsupported or missing-input outcomes to the assistant prompt instead of raising HTTP errors.

- [ ] **Step 4: Run the chat cutover tests to verify they pass**

Run:

```bash
poetry run pytest tests/api/test_chat_runtime_cutover.py -v
```

Expected:

```text
tests/api/test_chat_runtime_cutover.py ... PASSED
```

- [ ] **Step 5: Commit**

```bash
git add src/argus/api/main.py tests/api/test_chat_runtime_cutover.py
git commit -m "feat(api): route chat stream through agent runtime"
```

### Task 7: Full Launch Slice Verification

**Files:**
- Verify: `tests/domain/test_engine_launch.py`
- Verify: `tests/agent_runtime/test_real_backtest_tool.py`
- Verify: `tests/agent_runtime/test_execute_recovery.py`
- Verify: `tests/agent_runtime/test_workflow.py`
- Verify: `tests/api/test_chat_runtime_cutover.py`

- [ ] **Step 1: Run the engine-launch and runtime-focused suites**

Run:

```bash
poetry run pytest tests/domain/test_engine_launch.py tests/agent_runtime/test_real_backtest_tool.py tests/agent_runtime/test_execute_recovery.py tests/agent_runtime/test_workflow.py -v
```

Expected:

```text
tests/domain/test_engine_launch.py ... PASSED
tests/agent_runtime/test_real_backtest_tool.py ... PASSED
tests/agent_runtime/test_execute_recovery.py ... PASSED
tests/agent_runtime/test_workflow.py ... PASSED
```

- [ ] **Step 2: Run the end-to-end launch regression slice**

Run:

```bash
poetry run pytest tests/domain/test_engine_launch.py tests/agent_runtime tests/api/test_chat_runtime_cutover.py -v
```

Expected:

```text
tests/domain/test_engine_launch.py ... PASSED
tests/agent_runtime/... PASSED
tests/api/test_chat_runtime_cutover.py ... PASSED
```

- [ ] **Step 3: Commit**

```bash
git add tests/domain/test_engine_launch.py tests/agent_runtime/test_real_backtest_tool.py tests/agent_runtime/test_execute_recovery.py tests/agent_runtime/test_workflow.py tests/api/test_chat_runtime_cutover.py
git commit -m "test(agent-runtime): lock launch execution cutover coverage"
```

## Self-Review Checklist

- Spec coverage:
  - launch-bounded adapter contract: Task 1
  - three supported launch strategy types: Tasks 2, 3, and 4
  - top-level nullable cadence: Task 3
  - explicit strategy-type confirmation: Task 5
  - runtime-first unsupported rejection plus adapter enforcement: Tasks 4 and 5
  - split result-card/backend envelope contract: Tasks 1, 5, and 6
  - graceful `/api/v1/chat/stream` fallback: Task 6
  - real chat path cutover: Task 6
- Placeholder scan:
  - no `TBD`, `TODO`, or “handle later” steps remain
  - every task includes concrete files, commands, expected outcomes, and commit boundaries
- Type consistency:
  - `LaunchBacktestRequest`, `LaunchExecutionEnvelope`, `RealBacktestTool`, and `FinalResponsePayload` are defined before later tasks use them

## Notes

- This plan assumes implementation happens in `D:\Users\garce\git-repos\argus-clone\argus\.worktrees\agent-runtime-implementation`, because that worktree already contains the runtime slice and the extraction slice.
- Archive code is reference material only during implementation. Re-home useful logic into `src/argus/domain/engine_launch/`; do not introduce permanent imports from `archive-v0.1`.
- Because medium and long shell commands hang in this environment, the worker must stop before running pytest or broader verification commands and hand those exact commands back to the user.
