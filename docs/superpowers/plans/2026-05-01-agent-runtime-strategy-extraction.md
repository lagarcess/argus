# Agent Runtime Strategy Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bounded natural-language strategy extraction slice inside `Interpret` so the new agent runtime can understand ordinary strategy phrasing without forcing keyword-perfect input.

**Architecture:** Introduce a dedicated extraction submodule that returns typed `raw + normalized` field values, field status bands, ambiguity payloads, and unsupported constraints. `Interpret` will consume that extraction result, validate it against the capability contract, and route either to confirmation or low-friction clarification without changing the public chat path yet.

**Tech Stack:** Python 3.13, Pydantic, existing `argus.agent_runtime` package, pytest, FastAPI codebase conventions, LangGraph runtime already present.

---

## File Structure

**Create**
- `src/argus/agent_runtime/extraction/__init__.py`
- `src/argus/agent_runtime/extraction/structured.py`
- `tests/agent_runtime/test_strategy_extractor.py`

**Modify**
- `src/argus/agent_runtime/state/models.py`
- `src/argus/agent_runtime/capabilities/contract.py`
- `src/argus/agent_runtime/stages/interpret.py`
- `src/argus/agent_runtime/stages/clarify.py`
- `tests/agent_runtime/test_state_models.py`
- `tests/agent_runtime/test_interpret_stage.py`
- `tests/agent_runtime/test_conversation_stages.py`

**Keep unchanged for this slice**
- `src/argus/agent_runtime/stages/confirm.py`
- `src/argus/agent_runtime/stages/execute.py`
- `src/argus/agent_runtime/graph/workflow.py`
- `src/argus/api/main.py`

This slice improves understanding inside the existing runtime. It does not change the internal API seam or switch over the public chat flow.

### Task 1: Add Extraction Models And Capability Contract Extensions

**Files:**
- Modify: `src/argus/agent_runtime/state/models.py`
- Modify: `src/argus/agent_runtime/capabilities/contract.py`
- Test: `tests/agent_runtime/test_state_models.py`

- [ ] **Step 1: Write the failing state-model test**

```python
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.state.models import (
    AmbiguousField,
    ExtractedFieldValue,
    FieldExtractionStatus,
    UnsupportedConstraint,
)


def test_extraction_models_capture_raw_normalized_and_status() -> None:
    extracted = ExtractedFieldValue(
        raw_value="sell when RSI > 70",
        normalized_value="exit when RSI rises above 70",
        status="resolved",
    )
    ambiguous = AmbiguousField(
        field_name="exit_logic",
        raw_value="sell if RSI is not above 70",
        candidate_normalized_value="exit when RSI rises above 70",
        reason_code="negation_or_conditional_reversal",
    )
    unsupported = UnsupportedConstraint(
        category="unsupported_time_granularity",
        raw_value="sell at market open",
        explanation="Market-open execution timing is not supported in this runtime slice.",
        simplification_options=[
            {
                "label": "Retry with daily bars",
                "replacement_values": {"timeframe": "1D"},
            }
        ],
    )

    assert extracted.status == "resolved"
    assert ambiguous.reason_code == "negation_or_conditional_reversal"
    assert unsupported.simplification_options[0]["label"] == "Retry with daily bars"


def test_capability_contract_exposes_simplification_templates() -> None:
    contract = build_default_capability_contract()

    options = contract.get_simplification_options("unsupported_time_granularity")

    assert options[0]["label"] == "Retry with daily bars"
    assert options[0]["replacement_values"]["timeframe"] == "1D"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
poetry run pytest tests/agent_runtime/test_state_models.py::test_extraction_models_capture_raw_normalized_and_status -v
```

Expected:

```text
ImportError: cannot import name 'ExtractedFieldValue'
```

- [ ] **Step 3: Add the extraction models to runtime state**

Update `src/argus/agent_runtime/state/models.py`:

```python
FieldExtractionStatus = Literal["resolved", "missing", "ambiguous", "unsupported"]


class ExtractedFieldValue(BaseModel):
    raw_value: str | None = None
    normalized_value: str | None = None
    status: FieldExtractionStatus


class AmbiguousField(BaseModel):
    field_name: str
    raw_value: str
    candidate_normalized_value: str
    reason_code: str


class UnsupportedConstraint(BaseModel):
    category: str
    raw_value: str
    explanation: str
    simplification_options: list[dict[str, Any]] = Field(default_factory=list)
```

- [ ] **Step 4: Extend the capability contract with simplification templates**

Update `src/argus/agent_runtime/capabilities/contract.py`:

```python
class SimplificationOption(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: str
    replacement_values: dict[str, Any] = Field(default_factory=dict)


class CapabilityContract(BaseModel):
    model_config = ConfigDict(frozen=True)

    # existing fields...
    simplification_templates: dict[str, tuple[SimplificationOption, ...]] = Field(
        default_factory=dict
    )

    def get_simplification_options(self, category: str) -> list[dict[str, Any]]:
        return [
            option.model_dump(mode="python")
            for option in self.simplification_templates.get(category, ())
        ]
```

Add to `build_default_capability_contract()`:

```python
        simplification_templates={
            "unsupported_time_granularity": (
                SimplificationOption(
                    label="Retry with daily bars",
                    replacement_values={"timeframe": "1D"},
                ),
            ),
            "unsupported_asset_mix": (
                SimplificationOption(
                    label="Split into separate equity and crypto runs",
                    replacement_values={"split_runs": True},
                ),
            ),
            "unsupported_strategy_logic": (
                SimplificationOption(
                    label="Simplify to RSI-only logic",
                    replacement_values={"simplify_logic": "rsi_only"},
                ),
            ),
        },
```

- [ ] **Step 5: Run the targeted model test to verify it passes**

Run:

```bash
poetry run pytest tests/agent_runtime/test_state_models.py -v
```

Expected:

```text
tests/agent_runtime/test_state_models.py ... PASSED
```

- [ ] **Step 6: Commit**

```bash
git add src/argus/agent_runtime/state/models.py src/argus/agent_runtime/capabilities/contract.py tests/agent_runtime/test_state_models.py
git commit -m "feat(agent-runtime): add extraction state models"
```

### Task 2: Add The Structured Strategy Extractor Module

**Files:**
- Create: `src/argus/agent_runtime/extraction/__init__.py`
- Create: `src/argus/agent_runtime/extraction/structured.py`
- Test: `tests/agent_runtime/test_strategy_extractor.py`

- [ ] **Step 1: Write the failing extractor tests**

```python
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.extraction.structured import extract_strategy_fields


def test_extractor_understands_sell_synonym_and_normalizes_exit_logic() -> None:
    result = extract_strategy_fields(
        message="Backtest Tesla and sell when RSI is above 70 over the last 2 years",
        contract=build_default_capability_contract(),
    )

    assert result.exit_logic.raw_value == "sell when RSI is above 70"
    assert result.exit_logic.normalized_value == "exit when RSI rises above 70"
    assert result.exit_logic.status == "resolved"
    assert result.asset_universe.normalized_value == "TSLA"
    assert result.date_range.normalized_value == "last 2 years"


def test_extractor_marks_negation_flip_as_ambiguous() -> None:
    result = extract_strategy_fields(
        message="Backtest Tesla and sell when RSI is not above 70",
        contract=build_default_capability_contract(),
    )

    assert result.exit_logic.status == "ambiguous"
    assert result.ambiguous_fields[0].field_name == "exit_logic"
    assert result.ambiguous_fields[0].reason_code == "negation_or_conditional_reversal"


def test_extractor_detects_unsupported_time_granularity() -> None:
    result = extract_strategy_fields(
        message="Backtest Tesla and sell at market open when RSI is above 70",
        contract=build_default_capability_contract(),
    )

    assert result.unsupported_constraints[0].category == "unsupported_time_granularity"
    assert result.unsupported_constraints[0].simplification_options[0]["label"] == "Retry with daily bars"
```

- [ ] **Step 2: Run the extractor tests to verify they fail**

Run:

```bash
poetry run pytest tests/agent_runtime/test_strategy_extractor.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'argus.agent_runtime.extraction'
```

- [ ] **Step 3: Create the typed extractor contract and result model**

Create `src/argus/agent_runtime/extraction/structured.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, Field

from argus.agent_runtime.capabilities.contract import CapabilityContract
from argus.agent_runtime.state.models import (
    AmbiguousField,
    ExtractedFieldValue,
    UnsupportedConstraint,
)


class StrategyExtractionResult(BaseModel):
    strategy_thesis: ExtractedFieldValue
    asset_universe: ExtractedFieldValue
    entry_logic: ExtractedFieldValue
    exit_logic: ExtractedFieldValue
    date_range: ExtractedFieldValue
    ambiguous_fields: list[AmbiguousField] = Field(default_factory=list)
    unsupported_constraints: list[UnsupportedConstraint] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Implement the first bounded extractor**

Continue `src/argus/agent_runtime/extraction/structured.py`:

```python
def extract_strategy_fields(
    *,
    message: str,
    contract: CapabilityContract,
) -> StrategyExtractionResult:
    return StrategyExtractionResult(
        strategy_thesis=extract_strategy_thesis(message),
        asset_universe=extract_asset_universe(message),
        entry_logic=extract_entry_logic(message),
        exit_logic=extract_exit_logic(message, contract=contract),
        date_range=extract_date_range(message),
        ambiguous_fields=detect_ambiguous_fields(message),
        unsupported_constraints=detect_unsupported_constraints(
            message=message,
            contract=contract,
        ),
        reason_codes=collect_reason_codes(message),
    )
```

Add the concrete helpers in the same file for V1:

```python
def extract_exit_logic(message: str, *, contract: CapabilityContract) -> ExtractedFieldValue:
    if "not above" in message.lower():
        return ExtractedFieldValue(
            raw_value="sell when RSI is not above 70",
            normalized_value="exit when RSI rises above 70",
            status="ambiguous",
        )
    if "sell when rsi is above 70" in message.lower():
        return ExtractedFieldValue(
            raw_value="sell when RSI is above 70",
            normalized_value="exit when RSI rises above 70",
            status="resolved",
        )
    return ExtractedFieldValue(status="missing")
```

The implementation should stay bounded:

- parse ordinary phrases like `buy`, `sell`, `close`, and plain date-range wording
- detect unsupported timing words like `market open`
- use contract simplification templates rather than hardcoding response text into stage logic
- never silently mark a field `resolved` if a meaning-change rule is triggered

- [ ] **Step 5: Export the extractor**

Create `src/argus/agent_runtime/extraction/__init__.py`:

```python
from argus.agent_runtime.extraction.structured import (
    StrategyExtractionResult,
    extract_strategy_fields,
)

__all__ = [
    "StrategyExtractionResult",
    "extract_strategy_fields",
]
```

- [ ] **Step 6: Run the extractor tests to verify they pass**

Run:

```bash
poetry run pytest tests/agent_runtime/test_strategy_extractor.py -v
```

Expected:

```text
tests/agent_runtime/test_strategy_extractor.py ... PASSED
```

- [ ] **Step 7: Commit**

```bash
git add src/argus/agent_runtime/extraction/__init__.py src/argus/agent_runtime/extraction/structured.py tests/agent_runtime/test_strategy_extractor.py
git commit -m "feat(agent-runtime): add structured strategy extractor"
```

### Task 3: Integrate Extraction Into Interpret

**Files:**
- Modify: `src/argus/agent_runtime/stages/interpret.py`
- Modify: `tests/agent_runtime/test_interpret_stage.py`

- [ ] **Step 1: Write the failing interpret tests**

```python
from argus.agent_runtime.stages.interpret import interpret_stage
from argus.agent_runtime.state.models import RunState, UserState


def test_interpret_uses_extractor_for_sell_synonym() -> None:
    result = interpret_stage(
        state=RunState.new(
            current_user_message="Backtest Tesla and sell when RSI is above 70 over the last 2 years",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=None,
    )

    assert result.decision.candidate_strategy_draft.exit_logic == "exit when RSI rises above 70"
    assert result.decision.missing_required_fields == ["entry_logic"]


def test_interpret_blocks_confirmation_for_unsupported_constraint() -> None:
    result = interpret_stage(
        state=RunState.new(
            current_user_message="Backtest Tesla and sell at market open when RSI is above 70",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=None,
    )

    assert result.outcome == "needs_clarification"
    assert result.decision.requires_clarification is True
    assert "unsupported_time_granularity" in result.decision.reason_codes
```

- [ ] **Step 2: Run the interpret tests to verify they fail**

Run:

```bash
poetry run pytest tests/agent_runtime/test_interpret_stage.py -v
```

Expected:

```text
AssertionError: expected normalized exit logic not found
```

- [ ] **Step 3: Replace direct field parsing with extractor output**

Update `src/argus/agent_runtime/stages/interpret.py`:

```python
from argus.agent_runtime.extraction import extract_strategy_fields


def interpret_stage(...):
    capability_contract = build_default_capability_contract()
    extraction = extract_strategy_fields(
        message=state.current_user_message,
        contract=capability_contract,
    )
    candidate_strategy = build_candidate_strategy_from_extraction(extraction)
    missing_required_fields = [
        field_name
        for field_name in capability_contract.required_fields
        if extraction_field_status(extraction, field_name) == "missing"
    ]
```

- [ ] **Step 4: Add unsupported and ambiguous extraction handling**

Continue `src/argus/agent_runtime/stages/interpret.py`:

```python
    has_unsupported_constraints = bool(extraction.unsupported_constraints)
    has_ambiguous_fields = bool(extraction.ambiguous_fields)

    requires_clarification = (
        intent == "beginner_guidance"
        or task_relation == "ambiguous"
        or has_unsupported_constraints
        or has_ambiguous_fields
        or (
            should_track_execution_requirements(
                intent=intent,
                task_relation=task_relation,
                signals=signals,
            )
            and bool(missing_required_fields)
        )
    )
```

Update the interpret decision patch shape:

```python
            "field_status": build_field_status_payload(extraction),
            "ambiguous_fields": [
                item.model_dump(mode="python")
                for item in extraction.ambiguous_fields
            ],
            "unsupported_constraints": [
                item.model_dump(mode="python")
                for item in extraction.unsupported_constraints
            ],
```

- [ ] **Step 5: Run the interpret tests to verify they pass**

Run:

```bash
poetry run pytest tests/agent_runtime/test_interpret_stage.py -v
```

Expected:

```text
tests/agent_runtime/test_interpret_stage.py ... PASSED
```

- [ ] **Step 6: Commit**

```bash
git add src/argus/agent_runtime/stages/interpret.py tests/agent_runtime/test_interpret_stage.py
git commit -m "feat(agent-runtime): route interpret through strategy extraction"
```

### Task 4: Add Grouped Clarification And Simplification Responses

**Files:**
- Modify: `src/argus/agent_runtime/stages/clarify.py`
- Modify: `tests/agent_runtime/test_conversation_stages.py`

- [ ] **Step 1: Write the failing clarification tests**

```python
from argus.agent_runtime.stages.clarify import clarify_stage
from argus.agent_runtime.state.models import RunState
from argus.agent_runtime.capabilities.contract import build_default_capability_contract


def test_clarify_groups_multiple_ambiguous_fields() -> None:
    state = RunState.new(current_user_message="test", recent_thread_history=[])
    state.requires_clarification = True
    state.optional_parameter_status = {
        "ambiguous_fields": [
            {
                "field_name": "entry_logic",
                "raw_value": "buy if RSI is kind of weak",
                "candidate_normalized_value": "enter when RSI drops below 30",
                "reason_code": "semantic_category_shift",
            },
            {
                "field_name": "exit_logic",
                "raw_value": "sell if RSI is not above 70",
                "candidate_normalized_value": "exit when RSI rises above 70",
                "reason_code": "negation_or_conditional_reversal",
            },
        ]
    }

    result = clarify_stage(
        state=state,
        contract=build_default_capability_contract(),
    )

    assert result.outcome == "await_user_reply"
    assert "entry_logic" in result.patch["ambiguous_fields"][0]["field_name"]
    assert "exit_logic" in result.patch["ambiguous_fields"][1]["field_name"]


def test_clarify_surfaces_simplification_options_for_unsupported_constraints() -> None:
    state = RunState.new(current_user_message="test", recent_thread_history=[])
    state.requires_clarification = True
    state.optional_parameter_status = {
        "unsupported_constraints": [
            {
                "category": "unsupported_time_granularity",
                "raw_value": "market open",
                "explanation": "Market-open execution timing is not supported.",
                "simplification_options": [
                    {
                        "label": "Retry with daily bars",
                        "replacement_values": {"timeframe": "1D"},
                    }
                ],
            }
        ]
    }

    result = clarify_stage(
        state=state,
        contract=build_default_capability_contract(),
    )

    assert result.patch["simplification_options"][0]["label"] == "Retry with daily bars"
```

- [ ] **Step 2: Run the conversation-stage tests to verify they fail**

Run:

```bash
poetry run pytest tests/agent_runtime/test_conversation_stages.py -v
```

Expected:

```text
KeyError: 'ambiguous_fields'
```

- [ ] **Step 3: Add grouped ambiguity support to Clarify**

Update `src/argus/agent_runtime/stages/clarify.py`:

```python
def clarify_stage(*, state: RunState, contract: CapabilityContract) -> StageResult:
    ambiguous_fields = state.optional_parameter_status.get("ambiguous_fields", [])
    if len(ambiguous_fields) > 1:
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "assistant_prompt": build_grouped_ambiguity_prompt(ambiguous_fields),
                "ambiguous_fields": ambiguous_fields,
            },
        )
```

- [ ] **Step 4: Add unsupported simplification routing to Clarify**

Continue `src/argus/agent_runtime/stages/clarify.py`:

```python
    unsupported_constraints = state.optional_parameter_status.get(
        "unsupported_constraints",
        [],
    )
    if unsupported_constraints:
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "assistant_prompt": build_unsupported_constraint_prompt(
                    unsupported_constraints
                ),
                "unsupported_constraints": unsupported_constraints,
                "simplification_options": flatten_simplification_options(
                    unsupported_constraints
                ),
            },
        )
```

- [ ] **Step 5: Run the conversation-stage tests to verify they pass**

Run:

```bash
poetry run pytest tests/agent_runtime/test_conversation_stages.py -v
```

Expected:

```text
tests/agent_runtime/test_conversation_stages.py ... PASSED
```

- [ ] **Step 6: Commit**

```bash
git add src/argus/agent_runtime/stages/clarify.py tests/agent_runtime/test_conversation_stages.py
git commit -m "feat(agent-runtime): add grouped extraction clarifications"
```

### Task 5: Full Slice Verification

**Files:**
- Verify: `tests/agent_runtime/test_state_models.py`
- Verify: `tests/agent_runtime/test_strategy_extractor.py`
- Verify: `tests/agent_runtime/test_interpret_stage.py`
- Verify: `tests/agent_runtime/test_conversation_stages.py`
- Verify: `tests/agent_runtime/test_execute_recovery.py`
- Verify: `tests/agent_runtime/test_session_manager.py`
- Verify: `tests/agent_runtime/test_workflow.py`

- [ ] **Step 1: Run the extraction-focused suite**

Run:

```bash
poetry run pytest tests/agent_runtime/test_state_models.py tests/agent_runtime/test_strategy_extractor.py tests/agent_runtime/test_interpret_stage.py tests/agent_runtime/test_conversation_stages.py -v
```

Expected:

```text
tests/agent_runtime/test_state_models.py ... PASSED
tests/agent_runtime/test_strategy_extractor.py ... PASSED
tests/agent_runtime/test_interpret_stage.py ... PASSED
tests/agent_runtime/test_conversation_stages.py ... PASSED
```

- [ ] **Step 2: Run the full agent-runtime regression suite**

Run:

```bash
poetry run pytest tests/agent_runtime -v
```

Expected:

```text
tests/agent_runtime/test_state_models.py ... PASSED
tests/agent_runtime/test_strategy_extractor.py ... PASSED
tests/agent_runtime/test_interpret_stage.py ... PASSED
tests/agent_runtime/test_conversation_stages.py ... PASSED
tests/agent_runtime/test_execute_recovery.py ... PASSED
tests/agent_runtime/test_session_manager.py ... PASSED
tests/agent_runtime/test_workflow.py ... PASSED
```

- [ ] **Step 3: Commit**

```bash
git add tests/agent_runtime/test_strategy_extractor.py tests/agent_runtime/test_interpret_stage.py tests/agent_runtime/test_conversation_stages.py tests/agent_runtime/test_state_models.py
git commit -m "test(agent-runtime): lock strategy extraction regression coverage"
```

## Self-Review Checklist

- Spec coverage:
  - dedicated extractor submodule: Task 2
  - `raw + normalized` field values: Tasks 1 and 2
  - field status bands: Tasks 1, 2, and 3
  - unsupported constraints and simplification options: Tasks 1, 2, and 4
  - material-meaning-change handling: Tasks 2 and 3
  - grouped ambiguity clarification payloads: Task 4
  - `Interpret` integration: Task 3
- Placeholder scan:
  - no `TBD`, `TODO`, or vague “handle later” steps remain
  - each task includes explicit files, code, commands, expected outcomes, and commits
- Type consistency:
  - `ExtractedFieldValue`, `AmbiguousField`, `UnsupportedConstraint`, and `StrategyExtractionResult` are defined before later tasks use them

## Notes

- This plan intentionally stops short of rewiring `/api/v1/chat/stream` to the new runtime.
- The first implementation can use a bounded extractor module and injected test doubles without introducing multi-model orchestration.
- If the extractor needs a runtime-injected callable later, add that only after the basic contract and clarification routing are proven stable.
