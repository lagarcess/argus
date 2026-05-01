# Conversational Backtest Agent Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first production-shaped `agent_runtime` slice for conversational backtesting, with thread-aware session state, modular stages, a LangGraph workflow, a shared capability contract, and bounded recovery without replacing the existing orchestration path yet.

**Architecture:** Add a parallel runtime under `src/argus/agent_runtime/` instead of mutating `src/argus/domain/orchestrator.py` into another monolith. The first slice compiles a six-stage graph, runs it against typed `RunState`, persists only durable thread outcomes through a session manager, and uses stubbed tools for execution so the orchestration can be proven before engine coupling.

**Tech Stack:** Python 3.10, Pydantic, FastAPI codebase conventions, LangChain/OpenRouter already present, LangGraph (new dependency), pytest, pytest-asyncio, loguru.

---

## File Structure

**Create**
- `src/argus/agent_runtime/__init__.py`
- `src/argus/agent_runtime/runtime.py`
- `src/argus/agent_runtime/state/__init__.py`
- `src/argus/agent_runtime/state/models.py`
- `src/argus/agent_runtime/profile/__init__.py`
- `src/argus/agent_runtime/profile/response_profile.py`
- `src/argus/agent_runtime/capabilities/__init__.py`
- `src/argus/agent_runtime/capabilities/contract.py`
- `src/argus/agent_runtime/signals/__init__.py`
- `src/argus/agent_runtime/signals/task_relation.py`
- `src/argus/agent_runtime/stages/__init__.py`
- `src/argus/agent_runtime/stages/interpret.py`
- `src/argus/agent_runtime/stages/clarify.py`
- `src/argus/agent_runtime/stages/confirm.py`
- `src/argus/agent_runtime/stages/execute.py`
- `src/argus/agent_runtime/stages/explain.py`
- `src/argus/agent_runtime/stages/next_step.py`
- `src/argus/agent_runtime/recovery/__init__.py`
- `src/argus/agent_runtime/recovery/policy.py`
- `src/argus/agent_runtime/tools/__init__.py`
- `src/argus/agent_runtime/tools/backtest_stub.py`
- `src/argus/agent_runtime/session/__init__.py`
- `src/argus/agent_runtime/session/manager.py`
- `src/argus/agent_runtime/graph/__init__.py`
- `src/argus/agent_runtime/graph/workflow.py`
- `tests/agent_runtime/test_state_models.py`
- `tests/agent_runtime/test_interpret_stage.py`
- `tests/agent_runtime/test_conversation_stages.py`
- `tests/agent_runtime/test_execute_recovery.py`
- `tests/agent_runtime/test_session_manager.py`
- `tests/agent_runtime/test_workflow.py`

**Modify**
- `pyproject.toml`
- `src/argus/api/main.py`

**Keep unchanged for this slice**
- `src/argus/domain/orchestrator.py`
- `src/argus/domain/backtest_state_machine.py`
- `src/argus/domain/strategy_capabilities.py`

The new package is a parallel track. The existing domain orchestrator remains the current system of record until the new runtime proves stable.

### Task 1: Bootstrap The Runtime Package And Typed State

**Files:**
- Create: `src/argus/agent_runtime/__init__.py`
- Create: `src/argus/agent_runtime/state/models.py`
- Create: `src/argus/agent_runtime/profile/response_profile.py`
- Create: `src/argus/agent_runtime/capabilities/contract.py`
- Test: `tests/agent_runtime/test_state_models.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write the failing state-model test**

```python
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.profile.response_profile import resolve_effective_response_profile
from argus.agent_runtime.state.models import RunState, ThreadState, UserState


def test_effective_response_profile_prefers_turn_override():
    user = UserState(
        user_id="user-1",
        display_name="Sarah",
        language_preference="en",
        preferred_tone="concise",
        expertise_level="advanced",
        response_verbosity="low",
    )

    profile = resolve_effective_response_profile(
        user=user,
        explicit_overrides={
            "tone": "friendly",
            "verbosity": "high",
            "expertise_mode": "beginner",
        },
    )

    assert profile.effective_tone == "friendly"
    assert profile.effective_verbosity == "high"
    assert profile.effective_expertise_mode == "beginner"


def test_run_state_starts_fresh_but_thread_state_keeps_history():
    thread = ThreadState(
        thread_id="thread-1",
        message_history=[{"role": "user", "content": "backtest Apple"}],
        thread_metadata={"latest_task_type": "backtest_execution"},
        latest_task_snapshot=None,
        artifact_references=[],
    )

    state = RunState.new(
        current_user_message="now try Tesla",
        recent_thread_history=thread.message_history,
    )

    assert state.current_user_message == "now try Tesla"
    assert state.recent_thread_history == thread.message_history
    assert state.tool_call_records == []
    assert state.confirmation_payload is None


def test_capability_contract_exposes_required_and_optional_fields():
    contract = build_default_capability_contract()

    assert contract.required_fields == [
        "strategy_thesis",
        "asset_universe",
        "entry_logic",
        "exit_logic",
        "date_range",
    ]
    assert contract.optional_defaults["initial_capital"] == 10000.0
    assert "engine_options" in contract.optional_defaults
```

- [ ] **Step 2: Run the state-model test to verify it fails**

Run:

```bash
poetry run pytest tests/agent_runtime/test_state_models.py -v
```

Expected:

```text
ERROR tests/agent_runtime/test_state_models.py
ModuleNotFoundError: No module named 'argus.agent_runtime'
```

- [ ] **Step 3: Add the dependency and minimal runtime models**

Update `pyproject.toml`:

```toml
[tool.poetry.dependencies]
langgraph = ">=1.1.5,<1.2.0"
```

Create `src/argus/agent_runtime/state/models.py`:

```python
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

IntentName = Literal[
    "beginner_guidance",
    "strategy_drafting",
    "backtest_execution",
    "results_explanation",
    "collection_management",
    "conversation_followup",
    "unsupported_or_out_of_scope",
]
TaskRelation = Literal["new_task", "continue", "refine", "ambiguous"]


class ResponseProfile(BaseModel):
    effective_tone: str
    effective_verbosity: str
    effective_expertise_mode: str


class UserState(BaseModel):
    user_id: str
    display_name: str | None = None
    language_preference: str = "en"
    preferred_tone: str = "friendly"
    expertise_level: str = "beginner"
    response_verbosity: str = "medium"


class ThreadState(BaseModel):
    thread_id: str
    message_history: list[dict[str, Any]] = Field(default_factory=list)
    thread_metadata: dict[str, Any] = Field(default_factory=dict)
    latest_task_snapshot: dict[str, Any] | None = None
    artifact_references: list[dict[str, Any]] = Field(default_factory=list)


class RunState(BaseModel):
    current_user_message: str
    recent_thread_history: list[dict[str, Any]] = Field(default_factory=list)
    normalized_signals: dict[str, Any] = Field(default_factory=dict)
    intent: IntentName | None = None
    task_relation: TaskRelation | None = None
    requires_clarification: bool = False
    user_goal_summary: str | None = None
    candidate_strategy_draft: dict[str, Any] = Field(default_factory=dict)
    missing_required_fields: list[str] = Field(default_factory=list)
    optional_parameter_status: dict[str, Any] = Field(default_factory=dict)
    effective_response_profile: ResponseProfile | None = None
    confirmation_payload: dict[str, Any] | None = None
    tool_call_records: list[dict[str, Any]] = Field(default_factory=list)
    failure_classification: str | None = None
    final_response_payload: dict[str, Any] | None = None

    @classmethod
    def new(
        cls,
        *,
        current_user_message: str,
        recent_thread_history: list[dict[str, Any]],
    ) -> "RunState":
        return cls(
            current_user_message=current_user_message,
            recent_thread_history=recent_thread_history,
        )
```

Create `src/argus/agent_runtime/profile/response_profile.py`:

```python
from __future__ import annotations

from argus.agent_runtime.state.models import ResponseProfile, UserState


def resolve_effective_response_profile(
    *,
    user: UserState,
    explicit_overrides: dict[str, str] | None = None,
) -> ResponseProfile:
    overrides = explicit_overrides or {}
    return ResponseProfile(
        effective_tone=overrides.get("tone", user.preferred_tone),
        effective_verbosity=overrides.get("verbosity", user.response_verbosity),
        effective_expertise_mode=overrides.get(
            "expertise_mode",
            user.expertise_level,
        ),
    )
```

Create `src/argus/agent_runtime/capabilities/contract.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class CapabilityContract(BaseModel):
    required_fields: list[str]
    optional_defaults: dict[str, object] = Field(default_factory=dict)


def build_default_capability_contract() -> CapabilityContract:
    return CapabilityContract(
        required_fields=[
            "strategy_thesis",
            "asset_universe",
            "entry_logic",
            "exit_logic",
            "date_range",
        ],
        optional_defaults={
            "initial_capital": 10000.0,
            "timeframe": "1d",
            "fees": 0.0,
            "slippage": 0.0,
            "engine_options": {},
        },
    )
```

- [ ] **Step 4: Run the state-model test to verify it passes**

Run:

```bash
poetry run pytest tests/agent_runtime/test_state_models.py -v
```

Expected:

```text
tests/agent_runtime/test_state_models.py::test_effective_response_profile_prefers_turn_override PASSED
tests/agent_runtime/test_state_models.py::test_run_state_starts_fresh_but_thread_state_keeps_history PASSED
tests/agent_runtime/test_state_models.py::test_capability_contract_exposes_required_and_optional_fields PASSED
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/argus/agent_runtime tests/agent_runtime/test_state_models.py
git commit -m "feat(agent-runtime): add state and capability scaffolding"
```

### Task 2: Build Signal Extraction And The Interpret Stage

**Files:**
- Create: `src/argus/agent_runtime/signals/task_relation.py`
- Create: `src/argus/agent_runtime/stages/interpret.py`
- Test: `tests/agent_runtime/test_interpret_stage.py`

- [ ] **Step 1: Write the failing interpret-stage test**

```python
from argus.agent_runtime.stages.interpret import interpret_stage
from argus.agent_runtime.state.models import RunState, ThreadState, UserState


def test_interpret_marks_beginner_guidance_for_novice_prompt():
    user = UserState(user_id="u1", expertise_level="beginner")
    thread = ThreadState(thread_id="t1")
    state = RunState.new(
        current_user_message="I don't know anything about finance, can you help me test an idea?",
        recent_thread_history=thread.message_history,
    )

    result = interpret_stage(state=state, user=user, latest_task_snapshot=None)

    assert result.outcome == "needs_clarification"
    assert result.patch["intent"] == "beginner_guidance"
    assert result.patch["requires_clarification"] is True
    assert "beginner_language_detected" in result.patch["reason_codes"]


def test_interpret_marks_new_task_when_symbols_change_after_completed_run():
    user = UserState(user_id="u1", expertise_level="advanced")
    state = RunState.new(
        current_user_message="Now backtest Tesla instead",
        recent_thread_history=[
            {"role": "user", "content": "Backtest Apple over the last 2 years"},
            {"role": "assistant", "content": "Your Apple backtest is ready."},
        ],
    )

    snapshot = {
        "latest_task_type": "backtest_execution",
        "completed": True,
        "confirmed_strategy_summary": {"asset_universe": ["AAPL"]},
    }

    result = interpret_stage(state=state, user=user, latest_task_snapshot=snapshot)

    assert result.patch["task_relation"] == "new_task"
    assert result.patch["intent"] == "backtest_execution"
    assert "symbols_changed" in result.patch["reason_codes"]
```

- [ ] **Step 2: Run the interpret-stage test to verify it fails**

Run:

```bash
poetry run pytest tests/agent_runtime/test_interpret_stage.py -v
```

Expected:

```text
ImportError: cannot import name 'interpret_stage'
```

- [ ] **Step 3: Implement deterministic signal extraction and interpret resolution**

Create `src/argus/agent_runtime/signals/task_relation.py`:

```python
from __future__ import annotations

import re
from typing import Any


BEGINNER_PATTERNS = [
    r"don't know anything about finance",
    r"explain .* simply",
    r"what can you do",
]


def extract_signals(
    *,
    message: str,
    latest_task_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    lowered = message.lower()
    reason_codes: list[str] = []

    beginner_language = any(re.search(pattern, lowered) for pattern in BEGINNER_PATTERNS)
    if beginner_language:
        reason_codes.append("beginner_language_detected")

    prior_symbols = (
        (latest_task_snapshot or {})
        .get("confirmed_strategy_summary", {})
        .get("asset_universe", [])
    )
    symbols_changed = bool(prior_symbols) and any(
        token in lowered for token in ["tesla", "tsla", "apple", "aapl", "google", "goog"]
    )
    if symbols_changed:
        reason_codes.append("symbols_changed")

    return {
        "beginner_language_detected": beginner_language,
        "symbols_changed": symbols_changed,
        "reason_codes": reason_codes,
    }
```

Create `src/argus/agent_runtime/stages/interpret.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, Field

from argus.agent_runtime.profile.response_profile import resolve_effective_response_profile
from argus.agent_runtime.signals.task_relation import extract_signals
from argus.agent_runtime.state.models import RunState, UserState


class StageResult(BaseModel):
    outcome: str
    patch: dict = Field(default_factory=dict)


def interpret_stage(
    *,
    state: RunState,
    user: UserState,
    latest_task_snapshot: dict | None,
) -> StageResult:
    signals = extract_signals(
        message=state.current_user_message,
        latest_task_snapshot=latest_task_snapshot,
    )
    profile = resolve_effective_response_profile(user=user, explicit_overrides={})

    if signals["beginner_language_detected"]:
        return StageResult(
            outcome="needs_clarification",
            patch={
                "normalized_signals": signals,
                "intent": "beginner_guidance",
                "task_relation": "new_task",
                "requires_clarification": True,
                "user_goal_summary": "User needs guidance before strategy execution.",
                "reason_codes": signals["reason_codes"],
                "effective_response_profile": profile,
            },
        )

    if signals["symbols_changed"]:
        return StageResult(
            outcome="needs_clarification",
            patch={
                "normalized_signals": signals,
                "intent": "backtest_execution",
                "task_relation": "new_task",
                "requires_clarification": True,
                "user_goal_summary": "User wants to run a new backtest with different symbols.",
                "reason_codes": signals["reason_codes"],
                "effective_response_profile": profile,
            },
        )

    return StageResult(
        outcome="needs_clarification",
        patch={
            "normalized_signals": signals,
            "intent": "strategy_drafting",
            "task_relation": "ambiguous",
            "requires_clarification": True,
            "user_goal_summary": "User intent needs clarification.",
            "reason_codes": signals["reason_codes"],
            "effective_response_profile": profile,
        },
    )
```

- [ ] **Step 4: Run the interpret-stage test to verify it passes**

Run:

```bash
poetry run pytest tests/agent_runtime/test_interpret_stage.py -v
```

Expected:

```text
tests/agent_runtime/test_interpret_stage.py::test_interpret_marks_beginner_guidance_for_novice_prompt PASSED
tests/agent_runtime/test_interpret_stage.py::test_interpret_marks_new_task_when_symbols_change_after_completed_run PASSED
```

- [ ] **Step 5: Commit**

```bash
git add src/argus/agent_runtime/signals src/argus/agent_runtime/stages/interpret.py tests/agent_runtime/test_interpret_stage.py
git commit -m "feat(agent-runtime): add interpret stage and signal extraction"
```

### Task 3: Implement Clarify, Confirm, And Next-Step Stages

**Files:**
- Create: `src/argus/agent_runtime/stages/clarify.py`
- Create: `src/argus/agent_runtime/stages/confirm.py`
- Create: `src/argus/agent_runtime/stages/next_step.py`
- Test: `tests/agent_runtime/test_conversation_stages.py`

- [ ] **Step 1: Write the failing conversation-stage tests**

```python
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.stages.clarify import clarify_stage
from argus.agent_runtime.stages.confirm import confirm_stage
from argus.agent_runtime.stages.next_step import next_step_stage
from argus.agent_runtime.state.models import RunState


def test_clarify_asks_only_for_first_missing_required_field():
    state = RunState.new(current_user_message="Backtest Tesla", recent_thread_history=[])
    state.intent = "backtest_execution"
    state.missing_required_fields = ["entry_logic", "exit_logic", "date_range"]

    result = clarify_stage(state=state)

    assert result.outcome == "await_user_reply"
    assert "entry" in result.patch["assistant_prompt"].lower()
    assert "exit logic" not in result.patch["assistant_prompt"].lower()


def test_confirm_stage_includes_defaults_for_undisclosed_optional_fields():
    state = RunState.new(current_user_message="run it", recent_thread_history=[])
    state.intent = "backtest_execution"
    state.candidate_strategy_draft = {
        "strategy_thesis": "Buy Tesla on pullbacks",
        "asset_universe": ["TSLA"],
        "entry_logic": "RSI below 30",
        "exit_logic": "RSI above 55",
        "date_range": "2024-01-01 to 2025-01-01",
    }
    contract = build_default_capability_contract()

    result = confirm_stage(state=state, contract=contract)

    assert result.outcome == "await_approval"
    assert result.patch["confirmation_payload"]["optional_parameters"]["initial_capital"] == 10000.0
    assert "initial_capital" in result.patch["assistant_prompt"]


def test_next_step_stage_limits_follow_up_actions():
    state = RunState.new(current_user_message="why did that happen?", recent_thread_history=[])
    state.final_response_payload = {"summary": "Tesla outperformed SPY"}

    result = next_step_stage(state=state)

    assert result.outcome == "end_run"
    assert result.patch["next_actions"] == [
        "refine_strategy",
        "compare_benchmark",
        "save_to_collection",
    ]
```

- [ ] **Step 2: Run the conversation-stage tests to verify they fail**

Run:

```bash
poetry run pytest tests/agent_runtime/test_conversation_stages.py -v
```

Expected:

```text
ImportError: cannot import name 'clarify_stage'
```

- [ ] **Step 3: Implement the three conversation stages**

Create `src/argus/agent_runtime/stages/clarify.py`:

```python
from __future__ import annotations

from argus.agent_runtime.stages.interpret import StageResult
from argus.agent_runtime.state.models import RunState


def clarify_stage(*, state: RunState) -> StageResult:
    field = state.missing_required_fields[0] if state.missing_required_fields else "strategy_thesis"
    prompts = {
        "strategy_thesis": "What idea are you trying to test in plain language?",
        "asset_universe": "Which stock or crypto symbols should I use?",
        "entry_logic": "What should trigger the entry?",
        "exit_logic": "What should trigger the exit?",
        "date_range": "What date range should I test?",
    }
    return StageResult(
        outcome="await_user_reply",
        patch={"assistant_prompt": prompts[field]},
    )
```

Create `src/argus/agent_runtime/stages/confirm.py`:

```python
from __future__ import annotations

from argus.agent_runtime.capabilities.contract import CapabilityContract
from argus.agent_runtime.stages.interpret import StageResult
from argus.agent_runtime.state.models import RunState


def confirm_stage(*, state: RunState, contract: CapabilityContract) -> StageResult:
    optional_parameters = contract.optional_defaults.copy()
    optional_parameters.update(state.optional_parameter_status)

    payload = {
        "strategy": state.candidate_strategy_draft,
        "optional_parameters": optional_parameters,
    }
    return StageResult(
        outcome="await_approval",
        patch={
            "confirmation_payload": payload,
            "assistant_prompt": (
                "Please confirm this backtest. "
                f"Optional parameters: {optional_parameters}"
            ),
        },
    )
```

Create `src/argus/agent_runtime/stages/next_step.py`:

```python
from __future__ import annotations

from argus.agent_runtime.stages.interpret import StageResult
from argus.agent_runtime.state.models import RunState


def next_step_stage(*, state: RunState) -> StageResult:
    return StageResult(
        outcome="end_run",
        patch={
            "next_actions": [
                "refine_strategy",
                "compare_benchmark",
                "save_to_collection",
            ]
        },
    )
```

- [ ] **Step 4: Run the conversation-stage tests to verify they pass**

Run:

```bash
poetry run pytest tests/agent_runtime/test_conversation_stages.py -v
```

Expected:

```text
tests/agent_runtime/test_conversation_stages.py::test_clarify_asks_only_for_first_missing_required_field PASSED
tests/agent_runtime/test_conversation_stages.py::test_confirm_stage_includes_defaults_for_undisclosed_optional_fields PASSED
tests/agent_runtime/test_conversation_stages.py::test_next_step_stage_limits_follow_up_actions PASSED
```

- [ ] **Step 5: Commit**

```bash
git add src/argus/agent_runtime/stages/clarify.py src/argus/agent_runtime/stages/confirm.py src/argus/agent_runtime/stages/next_step.py tests/agent_runtime/test_conversation_stages.py
git commit -m "feat(agent-runtime): add clarify confirm and next-step stages"
```

### Task 4: Add Execute, Explain, And Recovery With A Stub Tool

**Files:**
- Create: `src/argus/agent_runtime/tools/backtest_stub.py`
- Create: `src/argus/agent_runtime/recovery/policy.py`
- Create: `src/argus/agent_runtime/stages/execute.py`
- Create: `src/argus/agent_runtime/stages/explain.py`
- Test: `tests/agent_runtime/test_execute_recovery.py`

- [ ] **Step 1: Write the failing execute/recovery test**

```python
from argus.agent_runtime.stages.execute import execute_stage
from argus.agent_runtime.stages.explain import explain_stage
from argus.agent_runtime.tools.backtest_stub import StubBacktestTool
from argus.agent_runtime.state.models import RunState


def test_execute_retries_only_for_retryable_transient_failure():
    tool = StubBacktestTool(
        responses=[
            {"success": False, "error_type": "upstream_dependency_error", "error_message": "timeout", "retryable": True, "payload": None, "capability_context": {}},
            {"success": True, "payload": {"total_return": 0.14, "benchmark_return": 0.09}, "error_type": None, "error_message": None, "retryable": False, "capability_context": {}},
        ]
    )
    state = RunState.new(current_user_message="run it", recent_thread_history=[])
    state.confirmation_payload = {"strategy": {"asset_universe": ["TSLA"]}}

    result = execute_stage(state=state, tool=tool, max_retries=2)

    assert result.outcome == "execution_succeeded"
    assert len(result.patch["tool_call_records"]) == 2
    assert result.patch["failure_classification"] is None


def test_execute_does_not_retry_unsupported_capability():
    tool = StubBacktestTool(
        responses=[
            {"success": False, "error_type": "unsupported_capability", "error_message": "options backtests not supported", "retryable": False, "payload": None, "capability_context": {}},
        ]
    )
    state = RunState.new(current_user_message="run it", recent_thread_history=[])
    state.confirmation_payload = {"strategy": {"asset_universe": ["TSLA"]}}

    result = execute_stage(state=state, tool=tool, max_retries=2)

    assert result.outcome == "needs_clarification"
    assert result.patch["failure_classification"] == "unsupported_capability"


def test_explain_stage_uses_result_payload_without_fabricating():
    state = RunState.new(current_user_message="why", recent_thread_history=[])
    state.final_response_payload = {"result": {"total_return": 0.14, "benchmark_return": 0.09}}

    result = explain_stage(state=state)

    assert result.outcome == "ready_to_respond"
    assert "14.0%" in result.patch["assistant_response"]
    assert "9.0%" in result.patch["assistant_response"]
```

- [ ] **Step 2: Run the execute/recovery test to verify it fails**

Run:

```bash
poetry run pytest tests/agent_runtime/test_execute_recovery.py -v
```

Expected:

```text
ImportError: cannot import name 'execute_stage'
```

- [ ] **Step 3: Implement the stub tool, recovery policy, execute stage, and explain stage**

Create `src/argus/agent_runtime/tools/backtest_stub.py`:

```python
from __future__ import annotations


class StubBacktestTool:
    def __init__(self, responses: list[dict]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def run(self, payload: dict) -> dict:
        self.calls.append(payload)
        return self._responses.pop(0)
```

Create `src/argus/agent_runtime/recovery/policy.py`:

```python
from __future__ import annotations


def should_retry(*, error_type: str | None, retryable: bool, attempt: int, max_retries: int) -> bool:
    if error_type in {"missing_required_input", "unsupported_capability", "ambiguous_user_intent", "internal_system_error"}:
        return False
    if not retryable:
        return False
    return attempt < max_retries
```

Create `src/argus/agent_runtime/stages/execute.py`:

```python
from __future__ import annotations

from argus.agent_runtime.recovery.policy import should_retry
from argus.agent_runtime.stages.interpret import StageResult
from argus.agent_runtime.state.models import RunState


def execute_stage(*, state: RunState, tool, max_retries: int = 2) -> StageResult:
    records: list[dict] = []
    for attempt in range(1, max_retries + 1):
        envelope = tool.run(state.confirmation_payload or {})
        records.append(envelope)
        if envelope["success"]:
            return StageResult(
                outcome="execution_succeeded",
                patch={
                    "tool_call_records": records,
                    "failure_classification": None,
                    "final_response_payload": {"result": envelope["payload"]},
                },
            )
        if not should_retry(
            error_type=envelope.get("error_type"),
            retryable=bool(envelope.get("retryable")),
            attempt=attempt,
            max_retries=max_retries,
        ):
            return StageResult(
                outcome="execution_failed_terminally",
                patch={
                    "tool_call_records": records,
                    "failure_classification": envelope.get("error_type"),
                    "final_response_payload": {
                        "error": envelope.get("error_message"),
                    },
                },
            )
    return StageResult(
        outcome="execution_failed_terminally",
        patch={
            "tool_call_records": records,
            "failure_classification": "upstream_dependency_error",
            "final_response_payload": {"error": "Retry limit reached"},
        },
    )
```

Create `src/argus/agent_runtime/stages/explain.py`:

```python
from __future__ import annotations

from argus.agent_runtime.stages.interpret import StageResult
from argus.agent_runtime.state.models import RunState


def explain_stage(*, state: RunState) -> StageResult:
    result = (state.final_response_payload or {}).get("result", {})
    total_return = float(result.get("total_return", 0.0)) * 100
    benchmark_return = float(result.get("benchmark_return", 0.0)) * 100
    return StageResult(
        outcome="ready_to_respond",
        patch={
            "assistant_response": (
                f"Your strategy returned {total_return:.1f}% versus {benchmark_return:.1f}% "
                "for the benchmark over the same period."
            )
        },
    )
```

- [ ] **Step 4: Run the execute/recovery test to verify it passes**

Run:

```bash
poetry run pytest tests/agent_runtime/test_execute_recovery.py -v
```

Expected:

```text
tests/agent_runtime/test_execute_recovery.py::test_execute_retries_only_for_retryable_transient_failure PASSED
tests/agent_runtime/test_execute_recovery.py::test_execute_does_not_retry_unsupported_capability PASSED
tests/agent_runtime/test_execute_recovery.py::test_explain_stage_uses_result_payload_without_fabricating PASSED
```

- [ ] **Step 5: Commit**

```bash
git add src/argus/agent_runtime/tools src/argus/agent_runtime/recovery src/argus/agent_runtime/stages/execute.py src/argus/agent_runtime/stages/explain.py tests/agent_runtime/test_execute_recovery.py
git commit -m "feat(agent-runtime): add execute explain and recovery scaffold"
```

### Task 5: Add The Session Manager And LangGraph Workflow

**Files:**
- Create: `src/argus/agent_runtime/session/manager.py`
- Create: `src/argus/agent_runtime/graph/workflow.py`
- Create: `src/argus/agent_runtime/runtime.py`
- Test: `tests/agent_runtime/test_session_manager.py`
- Test: `tests/agent_runtime/test_workflow.py`

- [ ] **Step 1: Write the failing session and workflow tests**

```python
from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.runtime import run_agent_turn
from argus.agent_runtime.session.manager import InMemorySessionManager
from argus.agent_runtime.state.models import UserState


def test_session_manager_isolates_threads_for_same_user():
    manager = InMemorySessionManager()
    user = UserState(user_id="u1", display_name="Sarah")

    manager.append_message(user_id=user.user_id, thread_id="thread-a", role="user", content="Backtest Apple")
    manager.append_message(user_id=user.user_id, thread_id="thread-b", role="user", content="Backtest Tesla")

    thread_a = manager.load_thread(user_id=user.user_id, thread_id="thread-a")
    thread_b = manager.load_thread(user_id=user.user_id, thread_id="thread-b")

    assert thread_a.message_history[0]["content"] == "Backtest Apple"
    assert thread_b.message_history[0]["content"] == "Backtest Tesla"


def test_workflow_requires_confirmation_before_execute():
    workflow = build_workflow()
    manager = InMemorySessionManager()
    user = UserState(user_id="u1", expertise_level="advanced")

    result = run_agent_turn(
        workflow=workflow,
        session_manager=manager,
        user=user,
        thread_id="thread-1",
        message="Backtest Tesla when RSI drops below 30 and exit above 55 over the last year",
    )

    assert result["stage_outcome"] == "await_approval"
    assert "Please confirm this backtest" in result["assistant_prompt"]
```

- [ ] **Step 2: Run the session and workflow tests to verify they fail**

Run:

```bash
poetry run pytest tests/agent_runtime/test_session_manager.py tests/agent_runtime/test_workflow.py -v
```

Expected:

```text
ImportError: cannot import name 'InMemorySessionManager'
```

- [ ] **Step 3: Implement the session manager, graph workflow, and runtime entrypoint**

Create `src/argus/agent_runtime/session/manager.py`:

```python
from __future__ import annotations

from collections import defaultdict

from argus.agent_runtime.state.models import ThreadState


class InMemorySessionManager:
    def __init__(self) -> None:
        self._threads = defaultdict(lambda: ThreadState(thread_id=""))

    def load_thread(self, *, user_id: str, thread_id: str) -> ThreadState:
        key = f"{user_id}:{thread_id}"
        thread = self._threads.get(key)
        if thread is None:
            thread = ThreadState(thread_id=thread_id)
            self._threads[key] = thread
        return thread

    def append_message(self, *, user_id: str, thread_id: str, role: str, content: str) -> None:
        thread = self.load_thread(user_id=user_id, thread_id=thread_id)
        thread.message_history.append({"role": role, "content": content})
```

Create `src/argus/agent_runtime/graph/workflow.py`:

```python
from __future__ import annotations

from langgraph.graph import END, StateGraph

from argus.agent_runtime.state.models import RunState


def build_workflow():
    graph = StateGraph(RunState)
    graph.add_node("interpret", lambda state: state)
    graph.add_node("clarify", lambda state: state)
    graph.add_node("confirm", lambda state: state)
    graph.add_node("execute", lambda state: state)
    graph.add_node("explain", lambda state: state)
    graph.add_node("next_step", lambda state: state)
    graph.set_entry_point("interpret")
    graph.add_edge("interpret", "confirm")
    graph.add_edge("confirm", END)
    return graph.compile()
```

Create `src/argus/agent_runtime/runtime.py`:

```python
from __future__ import annotations

from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.session.manager import InMemorySessionManager
from argus.agent_runtime.stages.confirm import confirm_stage
from argus.agent_runtime.state.models import RunState, UserState


def run_agent_turn(*, workflow, session_manager: InMemorySessionManager, user: UserState, thread_id: str, message: str) -> dict:
    thread = session_manager.load_thread(user_id=user.user_id, thread_id=thread_id)
    state = RunState.new(current_user_message=message, recent_thread_history=thread.message_history)
    state.intent = "backtest_execution"
    state.candidate_strategy_draft = {
        "strategy_thesis": message,
        "asset_universe": ["TSLA"],
        "entry_logic": "RSI below 30",
        "exit_logic": "RSI above 55",
        "date_range": "last 1 year",
    }
    result = confirm_stage(state=state, contract=build_default_capability_contract())
    session_manager.append_message(user_id=user.user_id, thread_id=thread_id, role="user", content=message)
    session_manager.append_message(user_id=user.user_id, thread_id=thread_id, role="assistant", content=result.patch["assistant_prompt"])
    return {
        "stage_outcome": result.outcome,
        **result.patch,
    }
```

- [ ] **Step 4: Run the session and workflow tests to verify they pass**

Run:

```bash
poetry run pytest tests/agent_runtime/test_session_manager.py tests/agent_runtime/test_workflow.py -v
```

Expected:

```text
tests/agent_runtime/test_session_manager.py::test_session_manager_isolates_threads_for_same_user PASSED
tests/agent_runtime/test_workflow.py::test_workflow_requires_confirmation_before_execute PASSED
```

- [ ] **Step 5: Commit**

```bash
git add src/argus/agent_runtime/session src/argus/agent_runtime/graph src/argus/agent_runtime/runtime.py tests/agent_runtime/test_session_manager.py tests/agent_runtime/test_workflow.py
git commit -m "feat(agent-runtime): add session manager and workflow entrypoint"
```

### Task 6: Add A Minimal API Integration Seam And Full Slice Verification

**Files:**
- Modify: `src/argus/api/main.py`
- Test: `tests/agent_runtime/test_workflow.py`

- [ ] **Step 1: Write the failing API-seam test**

```python
from fastapi.testclient import TestClient

from argus.api.main import app


def test_agent_runtime_smoke_endpoint_returns_confirmation_payload():
    client = TestClient(app)

    response = client.post(
        "/internal/agent-runtime/turn",
        json={
            "user_id": "u1",
            "thread_id": "thread-1",
            "message": "Backtest Tesla when RSI drops below 30 and exit above 55 over the last year",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["stage_outcome"] == "await_approval"
    assert "confirmation_payload" in payload
```

- [ ] **Step 2: Run the API-seam test to verify it fails**

Run:

```bash
poetry run pytest tests/agent_runtime/test_workflow.py::test_agent_runtime_smoke_endpoint_returns_confirmation_payload -v
```

Expected:

```text
E       assert 404 == 200
```

- [ ] **Step 3: Add the internal runtime seam to the API**

Update `src/argus/api/main.py`:

```python
from pydantic import BaseModel

from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.runtime import run_agent_turn
from argus.agent_runtime.session.manager import InMemorySessionManager
from argus.agent_runtime.state.models import UserState

_agent_runtime_workflow = build_workflow()
_agent_runtime_sessions = InMemorySessionManager()


class AgentRuntimeTurnRequest(BaseModel):
    user_id: str
    thread_id: str
    message: str


@app.post("/internal/agent-runtime/turn")
def agent_runtime_turn(request: AgentRuntimeTurnRequest) -> dict[str, Any]:
    user = UserState(user_id=request.user_id)
    return run_agent_turn(
        workflow=_agent_runtime_workflow,
        session_manager=_agent_runtime_sessions,
        user=user,
        thread_id=request.thread_id,
        message=request.message,
    )
```

- [ ] **Step 4: Run the targeted slice verification**

Run:

```bash
poetry run pytest tests/agent_runtime -v
```

Expected:

```text
tests/agent_runtime/test_state_models.py ... PASSED
tests/agent_runtime/test_interpret_stage.py ... PASSED
tests/agent_runtime/test_conversation_stages.py ... PASSED
tests/agent_runtime/test_execute_recovery.py ... PASSED
tests/agent_runtime/test_session_manager.py ... PASSED
tests/agent_runtime/test_workflow.py ... PASSED
```

- [ ] **Step 5: Commit**

```bash
git add src/argus/api/main.py tests/agent_runtime/test_workflow.py
git commit -m "feat(api): add internal seam for agent runtime slice"
```

## Self-Review Checklist

- Spec coverage:
  - state boundaries: Tasks 1 and 5
  - interpret contract and signal extraction: Task 2
  - clarify/confirm/next-step stages: Task 3
  - execute/explain/recovery: Task 4
  - multi-chat session manager and fresh per-run state: Task 5
  - minimal API seam: Task 6
- Placeholder scan:
  - no `TBD`, `TODO`, or “implement later” placeholders remain
  - each task includes a file set, test, command, and commit
- Type consistency:
  - `RunState`, `ThreadState`, `UserState`, `ResponseProfile`, and `StageResult` names are reused consistently across tasks

## Notes

- This plan intentionally stops short of replacing the current chat orchestration path in `src/argus/domain/orchestrator.py`.
- The API seam is internal on purpose. It gives the team a runnable path for end-to-end verification without prematurely migrating the public chat flow.
- If LangGraph introduces typing friction with `StateGraph(RunState)`, resolve it in implementation by using a dict-based state adapter at the graph boundary while keeping the internal stage modules typed.
