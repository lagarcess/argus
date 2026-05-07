# Agent Runtime Phase 1 Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Do not dispatch subagents unless the user explicitly requests parallel agent work. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop all pre-LLM message interception and structural message rewriting in the Argus agent runtime while preserving approval, edit-action, social, and educational behavior through the structured interpreter contract.

**Architecture:** Phase 1 keeps the current synchronous LangGraph runtime and legacy fallback path, but moves the first-pass decision to `OpenRouterStructuredInterpreter` whenever it is available. Deterministic code may validate facts and completeness after the LLM, but it must not modify or intercept the user's message before the interpreter sees it.

**Tech Stack:** Python 3.10, FastAPI, Pydantic v2, LangGraph `StateGraph`, LangChain/OpenRouter structured output, pytest, Ruff/pre-commit, Bun/Next.js lint.

---

## Source Of Truth

- Primary: `temp/argus_runtime_sot.md`
- Supporting: `docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md`
- Mandatory Argus context also reviewed before planning: `docs/PRODUCT.md`, `docs/DATA_MODEL.md`, `.agent/designs/argus/DESIGN.md`

## Pre-Execution Gate

- Current checked-out branch is `fix/argus-runtime-sot`.
- The user confirmed this is the intended branch for the remediation.
- Before implementation starts, confirm the working tree state:

```bash
git status --short
git branch --show-current
```

Expected:
- Working tree state is understood before editing.
- Active branch is `fix/argus-runtime-sot`.

## Phase 1 File Map

- Modify: `src/argus/agent_runtime/runtime.py`
  - Preserve only whitespace normalization before workflow input.
  - Remove structural strategy/date clause rewriting.
  - Remove post-hoc response quality replacement.
  - Stop constructing or storing `strategy_frame`.
- Modify: `src/argus/agent_runtime/stages/interpret.py`
  - Call the structured interpreter before any legacy fallback logic.
  - Remove pre-LLM approval, confirmation edit, and social opener gates.
  - Route approvals from the LLM's `semantic_turn_act`.
  - Derive pending needs only from `pending_strategy_summary`.
- Modify: `src/argus/agent_runtime/llm_interpreter.py`
  - Add `semantic_turn_act` to the LLM response schema.
  - Expand the system prompt to own approval, confirmation edit, social, education, and response-quality behavior.
  - Copy `semantic_turn_act` into the runtime interpretation.
- Modify: `src/argus/agent_runtime/state/models.py`
  - Remove `TaskSnapshot.strategy_frame`.
  - Remove now-unused `StrategyFrame` only if no remaining import needs it.
- Modify: `tests/agent_runtime/test_interpret_stage.py`
  - Rewrite regex-intercept tests to use mock structured interpreters.
  - Keep test intent, but assert LLM-first routing.
- Modify: `tests/agent_runtime/test_workflow.py`
  - Strengthen raw-message test coverage.
  - Rewrite quality-gate tests to assert prompt/schema responsibility instead of post-hoc text repair.
- Modify: `tests/agent_runtime/test_conversation_stages.py`
  - Rename and adapt strategy-frame expectations to pending-summary-derived needs.
- Modify: `tests/agent_runtime/test_llm_interpreter.py`
  - Add schema and prompt-contract coverage for `semantic_turn_act` and natural response rules.

---

### Task 1: Write Failing Tests For Raw Message Preservation

**Files:**
- Modify: `tests/agent_runtime/test_workflow.py`

- [ ] **Step 1: Add a raw-message regression test**

Add a test near `test_build_workflow_input_preserves_natural_date_phrasing`:

```python
def test_build_workflow_input_does_not_rewrite_strategy_logic_or_dates() -> None:
    message = (
        "  Backtest Tesla when RSI drops below 30 and exit above 55 "
        "over the last year  "
    )

    state = build_workflow_input(
        session_manager=InMemorySessionManager(),
        user=UserState(user_id="u1", expertise_level="advanced"),
        thread_id="thread-raw-strategy-message",
        message=message,
    )

    assert (
        state["run_state"].current_user_message
        == "Backtest Tesla when RSI drops below 30 and exit above 55 over the last year"
    )
```

- [ ] **Step 2: Run the targeted test and confirm it fails**

Run:

```bash
poetry run pytest tests/agent_runtime/test_workflow.py::test_build_workflow_input_does_not_rewrite_strategy_logic_or_dates -q
```

Expected before implementation:
- FAIL because `_normalize_message_for_runtime_slice()` rewrites `when` to `enter when`, rewrites `and exit`, or moves the trailing date clause.

---

### Task 2: Write Failing Tests For LLM-First Routing Gates

**Files:**
- Modify: `tests/agent_runtime/test_interpret_stage.py`

- [ ] **Step 1: Add a recording mock interpreter helper**

Add near the top of the file after `ResolvedAssetStub`:

```python
class RecordingInterpreter:
    def __init__(self, response: StructuredInterpretation) -> None:
        self.response = response
        self.requests = []
        self.last_status = "unused"

    def __call__(self, request):
        self.requests.append(request)
        self.last_status = "used"
        return self.response
```

- [ ] **Step 2: Add approval routing test that proves the interpreter is called**

```python
def test_interpret_approval_uses_structured_interpreter_not_regex_gate() -> None:
    user = UserState(user_id="u1", expertise_level="advanced")
    pending_strategy = StrategySummary(
        raw_user_phrasing="Buy and hold Tesla over the past year.",
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Tesla over the past year.",
        asset_universe=["TSLA"],
        date_range="past year",
    )
    snapshot = TaskSnapshot(
        latest_task_type="backtest_execution",
        completed=False,
        pending_strategy_summary=pending_strategy,
    )
    interpreter = RecordingInterpreter(
        StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User approved the pending backtest.",
            candidate_strategy_draft=pending_strategy,
            assistant_response="I will run the backtest now.",
            confidence=0.96,
            semantic_turn_act="approval",
        )
    )
    state = RunState.new(
        current_user_message="Run backtest",
        recent_thread_history=[
            {"role": "user", "content": "Buy and hold Tesla over the past year."},
            {"role": "assistant", "content": "Please confirm this backtest."},
        ],
    )

    result = interpret_stage(
        state=state,
        user=user,
        latest_task_snapshot=snapshot,
        structured_interpreter=interpreter,
    )

    assert len(interpreter.requests) == 1
    assert interpreter.requests[0].current_user_message == "Run backtest"
    assert result.outcome == "approved_for_execution"
    assert result.patch["confirmation_payload"]["strategy"]["asset_universe"] == ["TSLA"]
    assert result.decision.semantic_turn_act == "approval"
```

Expected before implementation:
- FAIL because `_approval_stage_result_if_applicable()` returns before the interpreter is called, and/or `StructuredInterpretation` does not accept or propagate `semantic_turn_act`.

- [ ] **Step 3: Add social opener routing test that proves the interpreter is called**

```python
def test_interpret_social_opener_uses_structured_interpreter_response() -> None:
    user = UserState(user_id="u1", expertise_level="beginner")
    interpreter = RecordingInterpreter(
        StructuredInterpretation(
            intent="conversation_followup",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User greeted Argus.",
            assistant_response="Hi. Tell me an investing idea you want to test.",
            confidence=0.94,
        )
    )
    state = RunState.new(current_user_message="hello", recent_thread_history=[])

    result = interpret_stage(
        state=state,
        user=user,
        latest_task_snapshot=None,
        structured_interpreter=interpreter,
    )

    assert len(interpreter.requests) == 1
    assert result.outcome == "ready_to_respond"
    assert result.patch["assistant_response"] == (
        "Hi. Tell me an investing idea you want to test."
    )
    assert result.decision.reason_codes[0] == "llm_interpreter_used"
```

Expected before implementation:
- FAIL because `_social_opener_stage_result_if_applicable()` returns before the interpreter is called.

- [ ] **Step 4: Add confirmation edit routing test that proves the interpreter is called**

```python
def test_interpret_confirmation_edit_uses_structured_interpreter_not_chip_gate() -> None:
    user = UserState(user_id="u1", expertise_level="advanced")
    pending_strategy = StrategySummary(
        raw_user_phrasing="Backtest GOOGL RSI over the past year.",
        strategy_type="rsi_threshold",
        strategy_thesis="Backtest GOOGL RSI over the past year.",
        asset_universe=["GOOGL"],
        date_range="past year",
        entry_logic="RSI drops below 30",
        exit_logic="RSI rises above 55",
    )
    snapshot = TaskSnapshot(
        latest_task_type="backtest_execution",
        completed=False,
        pending_strategy_summary=pending_strategy,
    )
    interpreter = RecordingInterpreter(
        StructuredInterpretation(
            intent="strategy_drafting",
            task_relation="refine",
            requires_clarification=True,
            user_goal_summary="User wants to change the pending date range.",
            candidate_strategy_draft=pending_strategy,
            missing_required_fields=["date_range"],
            assistant_response="What time period should I test instead?",
            confidence=0.93,
            semantic_turn_act="refine_current_idea",
        )
    )
    state = RunState.new(
        current_user_message="Change the date range",
        recent_thread_history=[
            {"role": "user", "content": "Backtest GOOGL RSI over the past year."},
            {"role": "assistant", "content": "Please confirm this backtest."},
        ],
    )

    result = interpret_stage(
        state=state,
        user=user,
        latest_task_snapshot=snapshot,
        structured_interpreter=interpreter,
    )

    assert len(interpreter.requests) == 1
    assert result.outcome == "needs_clarification"
    assert result.decision.task_relation == "refine"
    assert result.decision.semantic_turn_act == "refine_current_idea"
    assert "confirmation_action_chip" not in result.decision.reason_codes
```

Expected before implementation:
- FAIL because `_confirmation_edit_action_stage_result_if_applicable()` returns before the interpreter is called.

- [ ] **Step 5: Run the targeted tests and confirm they fail**

Run:

```bash
poetry run pytest tests/agent_runtime/test_interpret_stage.py::test_interpret_approval_uses_structured_interpreter_not_regex_gate tests/agent_runtime/test_interpret_stage.py::test_interpret_social_opener_uses_structured_interpreter_response tests/agent_runtime/test_interpret_stage.py::test_interpret_confirmation_edit_uses_structured_interpreter_not_chip_gate -q
```

Expected before implementation:
- FAIL for the exact reasons above.

---

### Task 3: Add LLM Semantic Turn Act To The Structured Contract

**Files:**
- Modify: `src/argus/agent_runtime/stages/interpret.py`
- Modify: `src/argus/agent_runtime/llm_interpreter.py`
- Modify: `tests/agent_runtime/test_llm_interpreter.py`

- [ ] **Step 1: Extend `StructuredInterpretation`**

In `src/argus/agent_runtime/stages/interpret.py`, add:

```python
semantic_turn_act: SemanticTurnAct | None = None
```

to the `StructuredInterpretation` model.

- [ ] **Step 2: Extend `LLMInterpretationResponse`**

In `src/argus/agent_runtime/llm_interpreter.py`, add:

```python
semantic_turn_act: Literal[
    "new_idea",
    "answer_pending_need",
    "refine_current_idea",
    "educational_question",
    "result_followup",
    "approval",
    "unsupported_request",
] | None = None
```

to `LLMInterpretationResponse`.

- [ ] **Step 3: Copy the field into runtime interpretation**

In `_to_runtime_interpretation()`, include:

```python
semantic_turn_act=response.semantic_turn_act,
```

when constructing `StructuredInterpretation`.

- [ ] **Step 4: Add prompt/schema regression coverage**

Add to `tests/agent_runtime/test_llm_interpreter.py`:

```python
def test_llm_interpreter_preserves_semantic_turn_act_from_response() -> None:
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="continue",
        user_goal_summary="User approved the pending strategy.",
        semantic_turn_act="approval",
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="yes run it",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert result.semantic_turn_act == "approval"
```

- [ ] **Step 5: Run targeted schema tests**

Run:

```bash
poetry run pytest tests/agent_runtime/test_llm_interpreter.py::test_llm_interpreter_preserves_semantic_turn_act_from_response -q
```

Expected after implementation:
- PASS.

---

### Task 4: Remove Runtime Message Rewriting And Response Quality Gate

**Files:**
- Modify: `src/argus/agent_runtime/runtime.py`
- Modify: `tests/agent_runtime/test_workflow.py`

- [ ] **Step 1: Replace structural normalization with whitespace-only normalization**

In `build_workflow_input()`, replace:

```python
normalized_message = _normalize_message_for_runtime_slice(message)
```

with:

```python
normalized_message = " ".join(message.strip().split())
```

- [ ] **Step 2: Delete structural normalization helpers**

Delete these functions from `runtime.py`:

```python
_normalize_message_for_runtime_slice()
_normalize_single_unit_date_ranges()
_move_trailing_date_clause_ahead_of_strategy_logic()
_normalize_entry_clause()
_normalize_exit_clause()
```

Also remove `import re` if no longer used.

- [ ] **Step 3: Remove post-hoc response quality replacement**

In `run_agent_turn()`, replace:

```python
result = _apply_response_quality_gate(
    result=_compose_runtime_response(workflow.invoke(initial_state)),
    message=message,
)
```

with:

```python
result = _compose_runtime_response(workflow.invoke(initial_state))
```

Delete these functions from `runtime.py`:

```python
_apply_response_quality_gate()
_replacement_for_low_quality_text()
_contains_backend_scaffolding()
_assistant_text_is_too_thin()
_scaffolding_recovery_prompt()
_educational_recovery_response()
```

- [ ] **Step 4: Rewrite quality-gate tests**

Replace `test_workflow_quality_gate_repairs_thin_educational_llm_response` with a test that proves Phase 1 no longer repairs text after the graph:

```python
def test_runtime_preserves_llm_response_without_posthoc_quality_gate() -> None:
    def thin_interpreter(_request: InterpretationRequest) -> StructuredInterpretation:
        return StructuredInterpretation(
            intent="conversation_followup",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User asked what a backtest is.",
            assistant_response="Backtest.",
            confidence=0.9,
            semantic_turn_act="educational_question",
        )

    workflow = build_workflow(structured_interpreter=thin_interpreter)
    manager = InMemorySessionManager()

    result = run_agent_turn(
        workflow=workflow,
        session_manager=manager,
        user=UserState(user_id="u1", expertise_level="beginner"),
        thread_id="thread-thin-education",
        message="what is a backtest?",
    )

    assert result["stage_outcome"] == "ready_to_respond"
    assert result["assistant_response"] == "Backtest."
```

Replace `test_workflow_quality_gate_repairs_raw_backend_scaffolding_prompt` with a prompt-contract test in `tests/agent_runtime/test_llm_interpreter.py`:

```python
def test_llm_system_prompt_forbids_scaffolding_and_internal_field_names() -> None:
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )

    prompt = interpreter._system_prompt().lower()

    assert "asset_universe" in prompt
    assert "capital_amount" in prompt
    assert "requested_field" in prompt
    assert "not specified" in prompt
    assert "do not expose" in prompt or "never expose" in prompt
```

- [ ] **Step 5: Run targeted runtime tests**

Run:

```bash
poetry run pytest tests/agent_runtime/test_workflow.py::test_build_workflow_input_does_not_rewrite_strategy_logic_or_dates tests/agent_runtime/test_workflow.py::test_runtime_preserves_llm_response_without_posthoc_quality_gate -q
```

Expected after implementation:
- PASS.

---

### Task 5: Remove Pre-LLM Gates From `interpret_stage`

**Files:**
- Modify: `src/argus/agent_runtime/stages/interpret.py`

- [ ] **Step 1: Move structured interpretation to the top of `interpret_stage()`**

Change `interpret_stage()` so this call happens before legacy fallback logic:

```python
structured_result = _structured_stage_result(
    state=state,
    user=user,
    latest_task_snapshot=snapshot,
    structured_interpreter=structured_interpreter,
    capability_contract=capability_contract,
)
if structured_result is not None:
    return structured_result
```

This must be the first routing decision after snapshot normalization.

- [ ] **Step 2: Delete the three pre-LLM gate calls**

Remove these calls from the top of `interpret_stage()`:

```python
_approval_stage_result_if_applicable(...)
_confirmation_edit_action_stage_result_if_applicable(...)
_social_opener_stage_result_if_applicable(...)
```

- [ ] **Step 3: Delete gate helper functions that exist only for pre-LLM interception**

Delete:

```python
_approval_stage_result_if_applicable()
_confirmation_edit_action_stage_result_if_applicable()
_confirmation_edit_action()
_social_opener_stage_result_if_applicable()
```

Do not add replacement regex, string-matching, or early-return gates.

- [ ] **Step 4: Add LLM-driven approval handling inside `_structured_stage_result()`**

After constructing `decision`, before symbol-only and fragment response logic, add logic equivalent to:

```python
if (
    interpretation.semantic_turn_act == "approval"
    and latest_task_snapshot is not None
    and latest_task_snapshot.pending_strategy_summary is not None
    and strategy_can_be_approved(latest_task_snapshot.pending_strategy_summary)
):
    approved_strategy = latest_task_snapshot.pending_strategy_summary
    return StageResult(
        outcome="approved_for_execution",
        decision=decision.model_copy(
            update={
                "intent": "backtest_execution",
                "task_relation": "continue",
                "requires_clarification": False,
                "candidate_strategy_draft": approved_strategy,
                "missing_required_fields": [],
                "semantic_turn_act": "approval",
            }
        ),
        stage_patch={
            "confirmation_payload": {
                "strategy": approved_strategy.model_dump(mode="python"),
                "optional_parameters": {},
            },
        },
    )
```

If the pending strategy is incomplete, do not approve. Let deterministic completeness checks produce clarification.

- [ ] **Step 5: Ensure LLM semantic turn act is copied into `InterpretDecision`**

In the main `InterpretDecision` built by `_structured_stage_result()`, set:

```python
semantic_turn_act=interpretation.semantic_turn_act,
```

- [ ] **Step 6: Run targeted routing tests**

Run:

```bash
poetry run pytest tests/agent_runtime/test_interpret_stage.py::test_interpret_approval_uses_structured_interpreter_not_regex_gate tests/agent_runtime/test_interpret_stage.py::test_interpret_social_opener_uses_structured_interpreter_response tests/agent_runtime/test_interpret_stage.py::test_interpret_confirmation_edit_uses_structured_interpreter_not_chip_gate -q
```

Expected after implementation:
- PASS.

---

### Task 6: Remove `strategy_frame` From TaskSnapshot Storage

**Files:**
- Modify: `src/argus/agent_runtime/state/models.py`
- Modify: `src/argus/agent_runtime/runtime.py`
- Modify: `src/argus/agent_runtime/stages/interpret.py`
- Modify: `tests/agent_runtime/test_conversation_stages.py`

- [ ] **Step 1: Remove the `TaskSnapshot.strategy_frame` field**

In `TaskSnapshot`, delete:

```python
strategy_frame: StrategyFrame | None = None
```

If `StrategyFrame` has no remaining references, delete the `StrategyFrame` class too.

- [ ] **Step 2: Stop constructing `StrategyFrame` in runtime snapshot persistence**

In `_build_task_snapshot()`, delete the local `strategy_frame = ...` block and remove:

```python
strategy_frame=strategy_frame,
```

from the `TaskSnapshot(...)` constructor.

Remove `StrategyFrame` from the `runtime.py` imports.

- [ ] **Step 3: Derive pending needs only from `pending_strategy_summary`**

Replace `_pending_needs()` in `interpret.py` with a pure derivation:

```python
def _pending_needs(snapshot: TaskSnapshot | None) -> list[str]:
    if snapshot is None or snapshot.pending_strategy_summary is None:
        return []
    needs: list[str] = []
    strategy = snapshot.pending_strategy_summary
    if not strategy.asset_universe:
        needs.append("asset_target")
    if strategy.strategy_type == "dca_accumulation" and strategy.capital_amount is None:
        needs.append("sizing_amount")
    if strategy.date_range is None:
        needs.append("period")
    if executable_strategy_type(strategy) == "indicator_threshold":
        if not strategy.entry_logic or not strategy.exit_logic:
            needs.append("rule_definition")
    return list(dict.fromkeys(needs))
```

Do not read `snapshot.pending_needs` or any deleted `snapshot.strategy_frame`.

- [ ] **Step 4: Update test naming and expectations**

In `tests/agent_runtime/test_conversation_stages.py`, rename:

```python
test_buy_and_hold_without_asset_uses_strategy_frame_needs
```

to:

```python
test_buy_and_hold_without_asset_uses_pending_strategy_summary_needs
```

Keep the behavior assertion: the missing needs should come from the pending strategy summary, not a stored frame.

- [ ] **Step 5: Add stale pending-needs regression coverage**

Add to `tests/agent_runtime/test_interpret_stage.py`:

```python
def test_pending_needs_ignore_stale_snapshot_pending_needs() -> None:
    snapshot = TaskSnapshot(
        latest_task_type="backtest_execution",
        completed=False,
        pending_strategy_summary=StrategySummary(
            raw_user_phrasing="Buy and hold Tesla over the past year.",
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Tesla over the past year.",
            asset_universe=["TSLA"],
            date_range="past year",
        ),
        pending_needs=["sizing_amount"],
    )

    result = interpret_stage(
        state=RunState.new(current_user_message="500", recent_thread_history=[]),
        user=UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=snapshot,
        structured_interpreter=lambda _request: StructuredInterpretation(
            intent="conversation_followup",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User sent a fragment unrelated to required fields.",
            assistant_response="I still have the Tesla buy-and-hold idea ready.",
            confidence=0.8,
        ),
    )

    assert "capital_amount" not in result.decision.missing_required_fields
    assert result.outcome == "ready_to_respond"
```

- [ ] **Step 6: Run targeted state tests**

Run:

```bash
poetry run pytest tests/agent_runtime/test_conversation_stages.py::test_buy_and_hold_without_asset_uses_pending_strategy_summary_needs tests/agent_runtime/test_interpret_stage.py::test_pending_needs_ignore_stale_snapshot_pending_needs -q
```

Expected after implementation:
- PASS.

---

### Task 7: Expand The LLM System Prompt For Phase 1 Responsibilities

**Files:**
- Modify: `src/argus/agent_runtime/llm_interpreter.py`
- Modify: `tests/agent_runtime/test_llm_interpreter.py`

- [ ] **Step 1: Add explicit prompt instructions**

Extend `_system_prompt()` with concise instructions covering:

```text
Approval handling:
- If the user clearly approves a pending confirmation, set semantic_turn_act to approval, intent to backtest_execution, task_relation to continue, requires_clarification to false, and preserve the prior strategy.

Confirmation edit handling:
- If the user asks to change dates, assets, assumptions, timeframe, capital, or strategy details, set semantic_turn_act to refine_current_idea and ask only for the missing changed detail.

Social turns:
- Greetings or check-ins are conversation_followup, not strategy_drafting, unless the message includes a real investing idea.

Educational turns:
- Product or investing concept questions are educational_question or conversation_followup, and must use assistant_response without forcing a backtest.

Response quality:
- assistant_response must be natural user-facing prose.
- Never expose internal field names such as asset_universe, capital_amount, requested_field, or missing_required_fields.
- Never output raw JSON, "not specified", template placeholders, or scaffolding labels.
- Avoid responses under 10 words except deliberate short confirmations.
```

- [ ] **Step 2: Add prompt contract test**

Add to `tests/agent_runtime/test_llm_interpreter.py`:

```python
def test_llm_system_prompt_owns_phase_one_routing_and_quality_rules() -> None:
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )

    prompt = interpreter._system_prompt().lower()

    assert "semantic_turn_act" in prompt
    assert "approval" in prompt
    assert "refine_current_idea" in prompt
    assert "conversation_followup" in prompt
    assert "educational" in prompt
    assert "asset_universe" in prompt
    assert "capital_amount" in prompt
    assert "missing_required_fields" in prompt
    assert "not specified" in prompt
```

- [ ] **Step 3: Run targeted prompt tests**

Run:

```bash
poetry run pytest tests/agent_runtime/test_llm_interpreter.py::test_llm_system_prompt_owns_phase_one_routing_and_quality_rules tests/agent_runtime/test_llm_interpreter.py::test_llm_system_prompt_forbids_scaffolding_and_internal_field_names -q
```

Expected after implementation:
- PASS.

---

### Task 8: Phase 1 Self-Review And Full Verification Gate

**Files:**
- Review all modified files.

- [ ] **Step 1: Search for prohibited Phase 1 remnants**

Run:

```bash
rg -n "_apply_response_quality_gate|_replacement_for_low_quality_text|_normalize_entry_clause|_normalize_exit_clause|_move_trailing_date_clause_ahead_of_strategy_logic|_confirmation_edit_action_stage_result_if_applicable|_social_opener_stage_result_if_applicable|strategy_frame" src\argus\agent_runtime tests\agent_runtime
```

Expected:
- No matches, except a test name only if it has not been renamed yet. Rename it before continuing.

- [ ] **Step 2: Search for risky new regex additions in touched runtime files**

Run:

```bash
git diff -- src\argus\agent_runtime\runtime.py src\argus\agent_runtime\stages\interpret.py src\argus\agent_runtime\llm_interpreter.py | rg -n "re\.|fullmatch|search|match|regex"
```

Expected:
- No new regex or string-matching logic added to `runtime.py` or `interpret.py`.
- Prompt text mentioning "regex" is acceptable only if it instructs the LLM/system not to rely on regex.

- [ ] **Step 3: Run targeted Phase 1 tests**

Run:

```bash
poetry run pytest tests/agent_runtime/test_interpret_stage.py tests/agent_runtime/test_workflow.py tests/agent_runtime/test_conversation_stages.py tests/agent_runtime/test_llm_interpreter.py -q
```

Expected:
- PASS.

- [ ] **Step 4: Run full backend suite**

Run:

```bash
poetry run pytest
```

Expected:
- PASS.

- [ ] **Step 5: Run Python hooks/lint**

Run:

```bash
poetry run pre-commit run --all-files
```

Expected:
- PASS.

If hooks modify files, inspect the diff and rerun the command.

- [ ] **Step 6: Run frontend lint and tests**

Run:

```bash
Set-Location web
bun run lint
bun test __tests__
Set-Location ..
```

Expected:
- PASS.

If `bun run lint` fails on unrelated pre-existing debt, do not commit. Capture the exact failures and decide whether to fix them within Phase 1 or pause for user direction, because the user protocol requires the gate to pass before the phase commit.

- [ ] **Step 7: Self-review the diff**

Run:

```bash
git diff --stat
git diff -- src\argus\agent_runtime\runtime.py src\argus\agent_runtime\stages\interpret.py src\argus\agent_runtime\llm_interpreter.py src\argus\agent_runtime\state\models.py tests\agent_runtime
```

Review checklist:
- The LLM sees `message.strip()` with collapsed whitespace only.
- No approval/social/edit gate can return before `_structured_stage_result()` when an interpreter is present.
- Approval execution is driven by `semantic_turn_act == "approval"`.
- `strategy_frame` is no longer stored or read.
- The quality gate is removed, and prompt/tests own response quality.
- No new regex, string-matching, or early-return gate was added to `interpret.py` or `runtime.py`.

- [ ] **Step 8: Commit Phase 1 only**

After all gates pass:

```bash
git add src\argus\agent_runtime\runtime.py src\argus\agent_runtime\stages\interpret.py src\argus\agent_runtime\llm_interpreter.py src\argus\agent_runtime\state\models.py tests\agent_runtime\test_interpret_stage.py tests\agent_runtime\test_workflow.py tests\agent_runtime\test_conversation_stages.py tests\agent_runtime\test_llm_interpreter.py
git commit -m "fix(agent-runtime): stop pre-llm message interception"
```

Expected:
- Conventional commit created for Phase 1.
- Do not begin Phase 2 until this commit exists and all verification gates pass.

---

## Phase 1 Completion Criteria

- The raw user message is passed to the interpreter unchanged except whitespace normalization.
- No runtime regex normalization rewrites strategy clauses before the LLM.
- Approval, social opener, and confirmation edit handling use the structured interpreter when available.
- `TaskSnapshot.strategy_frame` is gone.
- `_pending_needs()` reads only `pending_strategy_summary`.
- `_apply_response_quality_gate()` and hardcoded recovery strings are gone.
- Prompt/schema now make the LLM responsible for approval, social, educational, edit-action, and response-quality behavior.
- `pytest`, `pre-commit`, `bun run lint`, and `bun test __tests__` pass.
- Phase 1 is committed before Phase 2 begins.
