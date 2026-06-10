# Agent Runtime Phase 3 and 4 NLU Collapse Implementation Plan

NOTE: Historical context. This document is retained as implementation evidence and is not the current execution source of truth.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse Argus runtime interpretation so the LLM is the only intent and extraction layer, with deterministic code limited to fact validation and graph routing.

**Architecture:** `interpret.py` becomes a thin orchestration stage: call the structured interpreter, validate facts, compute missing executable fields, and emit a `StageResult`. Regex field extraction and intent heuristics are deleted. `clarify.py` keeps deterministic response-intent metadata, but the user-facing clarifying question comes from one LLM call.

**Tech Stack:** Python, Pydantic, LangChain OpenRouter structured output, LangGraph `StateGraph`, pytest, Bun lint.

---

## Source Of Truth Reviewed

- `docs/PRODUCT.md`: conversation is the product, simple trusted backtests are the core happy path.
- `docs/ARCHITECTURE.md`: LLM owns intent, task relation, semantic turn act, and strategy field extraction; deterministic code validates facts only.
- `docs/API_CONTRACT.md`: chat SSE contract and backtest input constraints stay unchanged.
- `docs/DATA_MODEL.md`: no persistence schema changes are required for Phase 3 and 4.
- `.agent/designs/argus/DESIGN.md`: chat-first progressive disclosure; no raw slot strings.
- `temp/argus_runtime_sot.md`: Phases 3 and 4 require deleting regex NLU, canonical symbol resolution through `resolve_asset()`, and dynamic clarification.

## Scope Guardrails

- Work only on branch `fix/argus-runtime-sot`.
- Do not touch Phase 5 streaming/checkpointer work except the minimal graph route cleanup needed for `semantic_turn_act` driven routing.
- Do not clean up `compose.py` robotic strings.
- Do not add regex for intent, social turns, educational turns, approvals, strategy extraction, dates, symbols, cadence, or refinement.
- Keep deterministic validation to: canonical asset resolution, asset class parity, unsupported engine facts, date window limits, and missing required executable fields.

## File Structure

- Modify `tests/agent_runtime/test_interpret_stage.py`: rewrite around a mock structured interpreter. Remove assertions that depend on regex fallback.
- Modify `tests/agent_runtime/test_llm_interpreter.py`: assert prompt ownership for symbols, dates, DCA cadence, social, educational, approval, and refinement turns.
- Modify `tests/agent_runtime/test_conversation_stages.py`: update clarify tests to use a fake clarification generator and assert prompt context rather than hardcoded strings.
- Delete or repurpose `tests/agent_runtime/test_strategy_extractor.py`: regex extractor no longer exists.
- Modify `src/argus/agent_runtime/extraction/structured.py`: keep only post-LLM unsupported/fact validation helpers.
- Modify `src/argus/agent_runtime/extraction/__init__.py`: export only kept validation helpers.
- Modify `src/argus/agent_runtime/signals/task_relation.py`: retire deterministic turn-signal parsing; keep only a compatibility no-op.
- Modify `src/argus/agent_runtime/signals/__init__.py`: expose only the compatibility no-op during migration.
- Modify `src/argus/agent_runtime/llm_interpreter.py`: expand prompt, canonicalize symbols through `resolve_asset()`, remove local regex decisions that override model task relation.
- Modify `src/argus/agent_runtime/stages/interpret.py`: reduce to models, LLM call orchestration, fact validation, missing field calculation, and semantic outcome mapping.
- Modify `src/argus/agent_runtime/stages/clarify.py`: replace hardcoded prompt selection with a single LLM-backed clarification generator.
- Create `src/argus/agent_runtime/llm_clarifier.py`: concrete OpenRouter clarification generator.
- Modify `src/argus/agent_runtime/graph/workflow.py`: inject clarification generator and route from stage outcome rather than a pre-set route field.
- Modify `src/argus/agent_runtime/runtime.py` only if needed to pass the concrete clarifier into `build_workflow()`.

---

## Task 1: Migrate Interpret Tests To LLM-First Routing

**Files:**
- Modify: `tests/agent_runtime/test_interpret_stage.py`
- Delete/repurpose: `tests/agent_runtime/test_strategy_extractor.py`

- [ ] **Step 1: Replace regex-era imports and test helpers**

Remove:

```python
from argus.agent_runtime.signals.task_relation import extract_signals
```

Keep and extend this helper shape:

```python
class RecordingInterpreter:
    def __init__(self, response: StructuredInterpretation | None) -> None:
        self.response = response
        self.requests = []
        self.last_status = "unused"

    def __call__(self, request):
        self.requests.append(request)
        self.last_status = "used"
        return self.response
```

Add a helper so every interpret test explicitly uses a mock interpreter:

```python
def run_interpret_with_llm(
    *,
    message: str,
    response: StructuredInterpretation,
    user: UserState | None = None,
    snapshot: TaskSnapshot | None = None,
    history: list[dict[str, str]] | None = None,
):
    interpreter = RecordingInterpreter(response)
    state = RunState.new(
        current_user_message=message,
        recent_thread_history=history or [],
    )
    result = interpret_stage(
        state=state,
        user=user or UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=snapshot,
        structured_interpreter=interpreter,
    )
    return result, interpreter
```

- [ ] **Step 2: Add raw-message and one-call tests**

Add:

```python
def test_interpret_passes_raw_message_to_llm_without_regex_normalization() -> None:
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User is checking the product.",
        assistant_response="I can help turn an investing idea into a supported backtest.",
        semantic_turn_act="educational_question",
    )

    result, interpreter = run_interpret_with_llm(
        message="  Actually make that weekly instead.  ",
        response=response,
    )

    assert len(interpreter.requests) == 1
    assert interpreter.requests[0].current_user_message == "  Actually make that weekly instead.  "
    assert result.outcome == "ready_to_respond"
```

- [ ] **Step 3: Rewrite social and educational tests to assert LLM response ownership**

Use mock responses like:

```python
StructuredInterpretation(
    intent="conversation_followup",
    task_relation="continue",
    requires_clarification=False,
    user_goal_summary="User greeted Argus.",
    assistant_response="Hi. Tell me the investing idea you want to test.",
    confidence=0.94,
    semantic_turn_act="educational_question",
)
```

Assert:

```python
assert result.outcome == "ready_to_respond"
assert result.patch["assistant_response"] == response.assistant_response
assert result.decision.reason_codes[0] == "llm_interpreter_used"
assert "beginner_language_detected" not in result.decision.reason_codes
```

- [ ] **Step 4: Rewrite approval tests around `semantic_turn_act`**

Use the existing pending strategy fixtures. Assert an executable pending strategy routes to `approved_for_execution` only when:

```python
semantic_turn_act="approval"
```

Also add the negative case:

```python
def test_interpret_does_not_approve_when_llm_does_not_mark_approval() -> None:
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        asset_universe=["TSLA"],
        date_range="past year",
    )
    snapshot = TaskSnapshot(pending_strategy_summary=pending)
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asked a follow-up.",
        candidate_strategy_draft=pending,
        assistant_response="I can explain the assumptions first.",
        semantic_turn_act="result_followup",
    )

    result, _ = run_interpret_with_llm(
        message="Can you explain the assumptions?",
        response=response,
        snapshot=snapshot,
    )

    assert result.outcome == "ready_to_respond"
    assert result.outcome != "approved_for_execution"
```

- [ ] **Step 5: Rewrite extraction tests as LLM-first interpretation tests**

Delete `tests/agent_runtime/test_strategy_extractor.py` or replace its three cases with interpret-stage tests whose `StructuredInterpretation.candidate_strategy_draft` already contains extracted fields.

Example replacement:

```python
def test_interpret_uses_llm_extracted_sell_synonym_and_date_range() -> None:
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User supplied an RSI strategy.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing="Backtest Tesla and sell when RSI is above 70 over the last 2 years",
            strategy_type="indicator_threshold",
            strategy_thesis="Backtest Tesla RSI exit rule.",
            asset_universe=["TSLA"],
            entry_logic="RSI drops below 30",
            exit_logic="RSI rises above 70",
            date_range="last 2 years",
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(
        message="Backtest Tesla and sell when RSI is above 70 over the last 2 years",
        response=response,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["TSLA"]
    assert strategy.exit_logic == "RSI rises above 70"
    assert strategy.date_range == "last 2 years"
```

- [ ] **Step 6: Run targeted failing tests**

Run:

```bash
poetry run pytest tests\agent_runtime\test_interpret_stage.py tests\agent_runtime\test_strategy_extractor.py -q --no-cov
```

Expected before implementation: failures from removed assumptions and not-yet-collapsed runtime.

---

## Task 2: Purge Regex Extraction And Signal NLU

**Files:**
- Modify: `src/argus/agent_runtime/extraction/structured.py`
- Modify: `src/argus/agent_runtime/extraction/__init__.py`
- Modify: `src/argus/agent_runtime/signals/task_relation.py`
- Modify: `src/argus/agent_runtime/signals/__init__.py`

- [ ] **Step 1: Replace `structured.py` with validation-only helpers**

Delete `StrategyExtractionResult`, `extract_strategy_fields()`, `extract_strategy_thesis()`, `extract_asset_universe()`, `extract_entry_logic()`, `extract_exit_logic()`, `extract_strategy_date_range()`, `detect_ambiguous_fields()`, `collect_reason_codes()`, `extract_raw_exit_phrase()`, and `normalize_logic_condition()`.

Keep a validation helper with this shape:

```python
from __future__ import annotations

from argus.agent_runtime.capabilities.contract import CapabilityContract
from argus.agent_runtime.state.models import StrategySummary, UnsupportedConstraint
from argus.domain.market_data import resolve_asset


def detect_unsupported_constraints(
    *,
    strategy: StrategySummary,
    contract: CapabilityContract,
) -> list[UnsupportedConstraint]:
    symbols = [symbol for symbol in strategy.asset_universe if symbol]
    asset_classes: dict[str, str] = {}
    unsupported: list[UnsupportedConstraint] = []

    for symbol in symbols:
        try:
            resolved = resolve_asset(symbol)
        except Exception:
            continue
        asset_classes[resolved.canonical_symbol] = resolved.asset_class

    if len(set(asset_classes.values())) > 1:
        unsupported.append(
            UnsupportedConstraint(
                category="unsupported_asset_mix",
                raw_value=", ".join(asset_classes),
                explanation=(
                    "Argus Alpha cannot run mixed asset classes in one simulation."
                ),
                simplification_options=contract.get_simplification_options(
                    "unsupported_asset_mix"
                ),
            )
        )

    return unsupported
```

Do not inspect raw user text here. Market-open or other unsupported natural language must arrive from the LLM as structured unsupported constraints.

- [ ] **Step 2: Update `extraction/__init__.py` exports**

Replace with:

```python
from argus.agent_runtime.extraction.structured import detect_unsupported_constraints

__all__ = ["detect_unsupported_constraints"]
```

- [ ] **Step 3: Collapse `task_relation.py` to profile overrides only**

Delete all intent and extraction patterns: beginner, backtest, new task, refinement, continuation, `SYMBOL_ALIASES`, date range patterns, `ExtractedSignals`, `extract_signals()`, `detect_symbols()`, `extract_date_range()`, and `explicit_strategy_logic_present()`.

Keep:

```python
from __future__ import annotations

import re

from argus.agent_runtime.state.models import ResponseProfileOverrides

TONE_OVERRIDE_PATTERNS: dict[str, tuple[str, ...]] = {...}
EXPERTISE_OVERRIDE_PATTERNS = (...)
VERBOSITY_OVERRIDE_PATTERNS = (...)


def _matches_any(message: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, message) for pattern in patterns)


def resolve_response_profile_overrides(message: str) -> ResponseProfileOverrides:
    lowered = " ".join(message.strip().lower().split())
    overrides = ResponseProfileOverrides()
    for tone, patterns in TONE_OVERRIDE_PATTERNS.items():
        if _matches_any(lowered, patterns):
            overrides.tone = tone
            break
    if _matches_any(lowered, EXPERTISE_OVERRIDE_PATTERNS):
        overrides.expertise_mode = "beginner"
    if _matches_any(lowered, VERBOSITY_OVERRIDE_PATTERNS):
        overrides.verbosity = "high"
    return overrides
```

This regex remains allowed because it changes response style only. It must not affect intent, task relation, extraction, semantic turn act, or route.

- [ ] **Step 4: Update `signals/__init__.py`**

Replace with:

```python
"""Response profile override helpers for runtime interpretation."""

from argus.agent_runtime.signals.task_relation import resolve_response_profile_overrides

__all__ = ["resolve_response_profile_overrides"]
```

- [ ] **Step 5: Run import checks**

Run:

```bash
poetry run pytest tests\agent_runtime\test_interpret_stage.py tests\agent_runtime\test_llm_interpreter.py -q --no-cov
```

Expected before Task 3: import failures in `interpret.py` and tests still referencing removed exports.

---

## Task 3: Expand LLM Interpreter Prompt And Canonical Symbol Validation

**Files:**
- Modify: `src/argus/agent_runtime/llm_interpreter.py`
- Modify: `tests/agent_runtime/test_llm_interpreter.py`

- [ ] **Step 1: Add prompt assertions first**

Add assertions to `test_llm_system_prompt_owns_phase_one_routing_and_quality_rules()` or a new test:

```python
def test_llm_system_prompt_owns_phase_three_extraction_rules() -> None:
    prompt = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )._system_prompt()

    assert "Extract symbols, company names, crypto assets, and currency pairs" in prompt
    assert "Do not rely on backend regex extraction" in prompt
    assert "date_range" in prompt
    assert "cadence" in prompt
    assert "semantic_turn_act is the routing source of truth" in prompt
    assert "social" in prompt.lower()
    assert "educational" in prompt.lower()
```

- [ ] **Step 2: Expand `_system_prompt()`**

Add a dedicated section:

```python
"NLU ownership: you are the only intent and extraction layer. "
"Extract symbols, company names, crypto assets, currency pairs, date ranges, "
"DCA cadence, recurring contribution amount, entry logic, exit logic, and "
"refinement targets from the user message and thread context. Do not rely on "
"backend regex extraction. If the user writes a company name like Tesla or "
"Bitcoin, put that text or the ticker in asset_universe; the deterministic "
"validator will canonicalize it with the market data resolver. "
"For natural periods, return date_range as a normalized string when exact dates "
"are not available, or as {'start': 'YYYY-MM-DD', 'end': 'YYYY-MM-DD'} when the "
"user provides exact dates. For recurring buys, extract cadence as daily, weekly, "
"monthly, or yearly and never invent capital_amount. "
```

Extend the existing semantic turn act instructions:

```python
"Use new_idea for a fresh testable idea, answer_pending_need when the user "
"answers the latest missing fact, refine_current_idea for changes like weekly "
"instead or keep everything else, educational_question for product or investing "
"concept questions, result_followup for questions about the latest completed run, "
"approval only for explicit approval of an executable pending strategy, and "
"unsupported_request when the user asks for unsupported capabilities. "
"Social turns are conversation_followup with assistant_response and no strategy "
"draft unless they also contain a real investing idea. "
```

- [ ] **Step 3: Canonicalize asset symbols through `resolve_asset()`**

Update `_validate_capability_boundaries()` so `asset_universe` is rewritten from resolver output:

```python
canonical_symbols: list[str] = []
for raw_symbol in strategy.asset_universe:
    try:
        resolved = resolve_asset(raw_symbol)
    except Exception:
        invalid_symbols.append(raw_symbol)
        continue
    canonical_symbols.append(resolved.canonical_symbol)
    asset_classes.add(resolved.asset_class)

strategy.asset_universe = list(dict.fromkeys(canonical_symbols))
```

Remove any fallback asset-class inference that bypasses `resolve_asset()`.

- [ ] **Step 4: Remove regex task-relation override in `_merge_prior_strategy()`**

Delete `_current_turn_starts_fresh_strategy()` and its call. Trust `response.task_relation` and `response.semantic_turn_act` from the LLM:

```python
if request.latest_task_snapshot is None or response.task_relation != "refine":
    return
```

If fresh-strategy/refinement behavior breaks, update the prompt and tests instead of adding a deterministic message classifier.

- [ ] **Step 5: Keep deterministic validation facts only**

Review remaining private helpers in `llm_interpreter.py`. Regex helpers may remain only when they validate engine support or data provenance after the LLM call, such as:

- `_text_contains_amount()`: prevents invented DCA contribution amounts.
- `_contains_unsupported_indicator_terms()`: validates unsupported indicator facts.
- `_indicator_rule_is_registry_executable()`: checks registry support.

They must not change `intent`, `task_relation`, or `semantic_turn_act`.

- [ ] **Step 6: Run focused tests**

Run:

```bash
poetry run pytest tests\agent_runtime\test_llm_interpreter.py -q --no-cov
```

Expected after implementation: prompt and canonical resolver tests pass.

---

## Task 4: Collapse `interpret.py` To LLM Orchestration Only

**Files:**
- Modify: `src/argus/agent_runtime/stages/interpret.py`
- Modify: `tests/agent_runtime/test_interpret_stage.py`

- [ ] **Step 1: Delete regex-era imports and model types**

Remove imports of:

```python
import re
from argus.agent_runtime.extraction import StrategyExtractionResult, extract_strategy_fields
from argus.agent_runtime.signals.task_relation import ExtractedSignals, extract_signals
from argus.domain.indicators import detect_executable_indicator_key, executable_indicator_spec
```

Keep imports for:

```python
from argus.agent_runtime.extraction import detect_unsupported_constraints
from argus.agent_runtime.signals.task_relation import resolve_response_profile_overrides
from argus.agent_runtime.profile.response_profile import resolve_effective_response_profile
from argus.agent_runtime.strategy_contract import strategy_can_be_approved
from argus.domain.market_data import resolve_asset
```

Delete arbitration classes and protocols unless another file still imports them:

```python
ArbitrationRequest
ArbitrationDecision
ArbitrationResolution
StructuredArbitrator
```

- [ ] **Step 2: Replace `interpret_stage()` with a required LLM path**

Target shape:

```python
def interpret_stage(
    *,
    state: RunState,
    user: UserState,
    latest_task_snapshot: TaskSnapshot | dict[str, Any] | None,
    structured_interpreter: StructuredInterpreter | None = None,
) -> StageResult:
    capability_contract = build_default_capability_contract()
    snapshot = normalize_task_snapshot(latest_task_snapshot)
    if structured_interpreter is None:
        return _offline_interpreter_unavailable_result(state=state, user=user)

    interpretation = structured_interpreter(
        InterpretationRequest(
            current_user_message=state.current_user_message,
            recent_thread_history=list(state.recent_thread_history),
            latest_task_snapshot=snapshot,
            user=user,
        )
    )
    if interpretation is None:
        return _offline_interpreter_unavailable_result(state=state, user=user)

    return _stage_result_from_interpretation(
        state=state,
        user=user,
        snapshot=snapshot,
        interpretation=interpretation,
        capability_contract=capability_contract,
    )
```

The offline result is the only allowed hardcoded natural language in this file:

```python
def _offline_interpreter_unavailable_result(*, state: RunState, user: UserState) -> StageResult:
    profile = resolve_effective_response_profile(user=user, explicit_overrides=None)
    decision = InterpretDecision(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="The LLM interpreter was unavailable for this turn.",
        candidate_strategy_draft=StrategySummary(),
        confidence=0.0,
        arbitration_mode="deterministic",
        reason_codes=["llm_interpreter_unavailable"],
        effective_response_profile=profile,
        semantic_turn_act=None,
    )
    return StageResult(
        outcome="ready_to_respond",
        decision=decision,
        stage_patch={
            "assistant_response": (
                "I could not reach the interpretation model for this turn. "
                "Your message is saved; please try again."
            )
        },
    )
```

- [ ] **Step 3: Implement `_stage_result_from_interpretation()`**

Target routing logic:

```python
def _stage_result_from_interpretation(
    *,
    state: RunState,
    user: UserState,
    snapshot: TaskSnapshot | None,
    interpretation: StructuredInterpretation,
    capability_contract: Any,
) -> StageResult:
    strategy = _canonicalized_strategy(interpretation.candidate_strategy_draft)
    unsupported = [
        *interpretation.unsupported_constraints,
        *detect_unsupported_constraints(strategy=strategy, contract=capability_contract),
    ]
    missing = _missing_fields_for_interpretation(
        interpretation=interpretation,
        strategy=strategy,
        contract=capability_contract,
    )
    response_overrides = resolve_response_profile_overrides(state.current_user_message)
    profile = resolve_effective_response_profile(
        user=user,
        explicit_overrides=response_overrides,
    )
    requires_clarification = bool(
        interpretation.requires_clarification
        or interpretation.ambiguous_fields
        or unsupported
        or missing
    )
    decision = InterpretDecision(
        intent=interpretation.intent,
        task_relation=interpretation.task_relation,
        requires_clarification=requires_clarification,
        user_goal_summary=interpretation.user_goal_summary,
        candidate_strategy_draft=strategy,
        missing_required_fields=missing,
        optional_parameter_opportunity=list(capability_contract.optional_defaults),
        confidence=interpretation.confidence,
        arbitration_mode="structured_arbitration",
        reason_codes=["llm_interpreter_used", *interpretation.reason_codes],
        effective_response_profile=profile,
        user_preference_overridden_for_turn=has_response_profile_overrides(response_overrides),
        normalized_signals={},
        field_status={},
        ambiguous_fields=interpretation.ambiguous_fields,
        unsupported_constraints=unsupported,
        semantic_turn_act=interpretation.semantic_turn_act,
    )
    approval = _approval_stage_result_if_applicable(
        decision=decision,
        snapshot=snapshot,
    )
    if approval is not None:
        return approval
    if interpretation.assistant_response and not _strategy_route_expected(decision):
        return StageResult(
            outcome="ready_to_respond",
            decision=decision,
            stage_patch={"assistant_response": interpretation.assistant_response},
        )
    if requires_clarification:
        return StageResult(outcome="needs_clarification", decision=decision)
    return StageResult(outcome="ready_for_confirmation", decision=decision)
```

- [ ] **Step 4: Implement canonical strategy validation without local dictionaries**

Use:

```python
def _canonicalized_strategy(strategy: StrategySummary) -> StrategySummary:
    updated = strategy.model_copy(deep=True)
    canonical_symbols: list[str] = []
    asset_classes: set[str] = set()
    invalid_symbols: list[str] = []

    for symbol in updated.asset_universe:
        try:
            resolved = resolve_asset(symbol)
        except Exception:
            invalid_symbols.append(symbol)
            continue
        canonical_symbols.append(resolved.canonical_symbol)
        asset_classes.add(resolved.asset_class)

    if canonical_symbols:
        updated.asset_universe = list(dict.fromkeys(canonical_symbols))
    if len(asset_classes) == 1:
        updated.asset_class = next(iter(asset_classes))
    elif len(asset_classes) > 1:
        updated.asset_class = "mixed"
    if invalid_symbols:
        updated.extra_parameters = {
            **updated.extra_parameters,
            "invalid_symbols": invalid_symbols,
        }
    return updated
```

Do not add `_known_symbol_asset_class()` or any replacement alias dictionary.

- [ ] **Step 5: Keep missing required fields deterministic**

Keep a small `missing_required_fields_for_strategy()` function that reads only `StrategySummary` and `CapabilityContract`. It must not take extraction output.

```python
def missing_required_fields_for_strategy(
    strategy: StrategySummary,
    *,
    contract: Any,
) -> list[str]:
    required = list(contract.required_fields)
    if strategy.strategy_type == "dca_accumulation" and strategy.capital_amount is None:
        required.append("capital_amount")
    if strategy.strategy_type == "buy_and_hold":
        required = ["asset_universe", "date_range"]
    missing: list[str] = []
    payload = strategy.model_dump(mode="python")
    for field_name in required:
        value = payload.get(field_name)
        if isinstance(value, list):
            if not value:
                missing.append(field_name)
        elif value is None or value == "":
            missing.append(field_name)
    return missing
```

- [ ] **Step 6: Delete regex orchestration helpers**

Delete helpers listed in `temp/argus_runtime_sot.md` Phase 4, including:

```text
_contextual_response_stage_result_if_applicable
build_candidate_strategy_from_extraction
_resolve_semantic_turn_act
_message_answers_pending_need
_message_refines_pending_strategy
_message_describes_strategy_family
_is_educational_turn
_direct_conversational_response
_social_opener_response
_symbol_only_guidance_response
_asset_explanation_response
_is_approval_message
_detect_strategy_type
_detect_cadence
_detect_capital_amount
_detect_risk_rules
_asset_class_for_symbols
_known_symbol_asset_class
resolve_intent
resolve_task_relation
build_user_goal_summary
resolve_confidence
resolve_gray_case_arbitration
```

- [ ] **Step 7: Run focused tests**

Run:

```bash
poetry run pytest tests\agent_runtime\test_interpret_stage.py -q --no-cov
```

Expected after implementation: interpret tests pass without importing or calling deleted regex NLU.

---

## Task 5: Make Graph Routing Read Stage Outcomes

**Files:**
- Modify: `src/argus/agent_runtime/graph/workflow.py`
- Modify: `tests/agent_runtime/test_workflow.py`

- [ ] **Step 1: Remove `route` from node output state**

In `_apply_stage_result()`, stop storing `transition.route`:

```python
workflow_state: WorkflowState = {
    **state,
    "run_state": run_state,
    "stage_outcome": WorkflowStageOutcome(result.outcome),
}
```

- [ ] **Step 2: Replace `_route_from_state()`**

Use:

```python
def _route_from_stage_outcome(state: WorkflowState) -> str:
    outcome = WorkflowStageOutcome(state["stage_outcome"])
    failure_classification = state.get("failure_classification")
    if outcome is WorkflowStageOutcome.NEEDS_CLARIFICATION:
        if failure_classification == "unsupported_capability":
            return WorkflowRoute.END.value
        return WorkflowRoute.CLARIFY.value
    if outcome is WorkflowStageOutcome.READY_FOR_CONFIRMATION:
        return WorkflowRoute.CONFIRM.value
    if outcome is WorkflowStageOutcome.APPROVED_FOR_EXECUTION:
        return WorkflowRoute.EXECUTE.value
    if outcome is WorkflowStageOutcome.EXECUTION_SUCCEEDED:
        return WorkflowRoute.EXPLAIN.value
    return WorkflowRoute.END.value
```

Wire all conditional edges to `_route_from_stage_outcome`.

- [ ] **Step 3: Keep Phase 5 out of this task**

Do not add checkpointers, `astream_events()`, or streaming changes in this phase.

- [ ] **Step 4: Run workflow tests**

Run:

```bash
poetry run pytest tests\agent_runtime\test_workflow.py -q --no-cov
```

Expected after implementation: workflow routes by stage outcome and no test depends on `state["route"]`.

---

## Task 6: Replace Hardcoded Clarify Prompts With One LLM Call

**Files:**
- Create: `src/argus/agent_runtime/llm_clarifier.py`
- Modify: `src/argus/agent_runtime/stages/clarify.py`
- Modify: `src/argus/agent_runtime/graph/workflow.py`
- Modify: `tests/agent_runtime/test_conversation_stages.py`

- [ ] **Step 1: Write failing clarify generator tests**

Add a fake generator:

```python
class RecordingClarifier:
    def __init__(self, question: str) -> None:
        self.question = question
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        return self.question
```

Update clarify tests to call:

```python
clarifier = RecordingClarifier("Which asset and period should I use?")
result = clarify_stage(
    state=state,
    contract=build_default_capability_contract(),
    clarification_generator=clarifier,
)

assert result.patch["assistant_prompt"] == "Which asset and period should I use?"
assert clarifier.requests[0].missing_required_fields == ["asset_universe", "date_range"]
assert "asset_universe" not in result.patch["assistant_prompt"]
```

- [ ] **Step 2: Create `llm_clarifier.py`**

Implement:

```python
from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field

from argus.agent_runtime.state.models import ConversationMessage, StrategySummary
from argus.llm.openrouter import build_openrouter_model, log_openrouter_failure


class ClarificationRequest(BaseModel):
    current_user_message: str
    recent_thread_history: list[ConversationMessage] = Field(default_factory=list)
    candidate_strategy_draft: StrategySummary = Field(default_factory=StrategySummary)
    missing_required_fields: list[str] = Field(default_factory=list)
    ambiguous_fields: list[dict[str, Any]] = Field(default_factory=list)
    unsupported_constraints: list[dict[str, Any]] = Field(default_factory=list)
    optional_parameter_choices: list[str] = Field(default_factory=list)
    response_intent: dict[str, Any] = Field(default_factory=dict)
    language: str = "en"


class ClarificationResponse(BaseModel):
    question: str


class OpenRouterClarificationGenerator:
    def __init__(self, *, model_name: str | None = None) -> None:
        self.model_name = (
            model_name or os.getenv("AGENT_MODEL") or "google/gemini-2.0-flash-001"
        )
        self.last_status: str | None = None

    def __call__(self, request: ClarificationRequest) -> str | None:
        model = build_openrouter_model("clarification", model_name=self.model_name)
        if model is None:
            self.last_status = "missing_api_key"
            return None
        try:
            structured = model.with_structured_output(ClarificationResponse)
            response = structured.invoke(self._messages(request))
        except Exception as exc:
            self.last_status = "failed"
            log_openrouter_failure(
                task="clarification",
                model_name=self.model_name,
                exc=exc,
                message="LLM clarification failed",
            )
            return None
        if not isinstance(response, ClarificationResponse):
            self.last_status = "invalid_response"
            return None
        self.last_status = "used"
        return response.question.strip() or None
```

The `_messages()` method must include a system prompt that says:

```python
"Generate exactly one concise, context-aware clarifying question. "
"Do not expose field names such as asset_universe, capital_amount, date_range, "
"requested_field, or missing_required_fields. Do not output JSON. "
"Use the user's language preference."
```

- [ ] **Step 3: Refactor `clarify_stage()`**

Change signature:

```python
def clarify_stage(
    *,
    state: RunState,
    contract: CapabilityContract,
    clarification_generator: StructuredClarificationGenerator | None = None,
) -> StageResult:
```

Build response intent and metadata deterministically, then call exactly one generator:

```python
assistant_prompt = _generate_clarifying_question(
    state=state,
    response_intent=response_intent,
    missing_required_fields=requested_fields,
    ambiguous_fields=ambiguous_fields,
    unsupported_constraints=unsupported_constraints,
    optional_parameter_choices=optional_parameter_choices,
    clarification_generator=clarification_generator,
)
```

If the generator returns `None`, return the allowed offline fallback:

```python
"I could not generate the clarifying question right now. Please try again."
```

- [ ] **Step 4: Delete hardcoded prompt helpers**

Delete:

```text
BEGINNER_GUIDANCE_PROMPT
AMBIGUOUS_TURN_PROMPT
_optional_parameter_opt_in_prompt
_ambiguous_fields_prompt
_semantic_missing_questions
_unsupported_constraint_prompt
_friendly_option_label
_choice_phrase
_optional_parameter_description
_ambiguous_turn_prompt
_grouped_required_fields_prompt
_required_field_prompt
```

Keep helpers that compute structured metadata:

```text
_response_intent
_semantic_needs_from_required_fields
_semantic_needs_from_fields
_optional_parameter_choices
_ambiguous_fields
_unsupported_constraints
_simplification_options
_first_missing_required_field
```

- [ ] **Step 5: Inject clarifier through workflow**

Update `build_workflow()`:

```python
def build_workflow(
    *,
    contract: CapabilityContract | None = None,
    tool: Any | None = None,
    max_retries: int = 2,
    structured_interpreter: StructuredInterpreter | None = None,
    clarification_generator: StructuredClarificationGenerator | None = None,
):
```

Pass it into `clarify_stage()`.

- [ ] **Step 6: Run clarify and workflow tests**

Run:

```bash
poetry run pytest tests\agent_runtime\test_conversation_stages.py tests\agent_runtime\test_workflow.py -q --no-cov
```

Expected after implementation: no test asserts old hardcoded clarify prompt wording.

---

## Task 7: Structural Regression Guards

**Files:**
- Modify: `tests/agent_runtime/test_interpret_stage.py`
- Modify: `tests/agent_runtime/test_llm_interpreter.py`

- [ ] **Step 1: Add no-regex-NLU structural tests**

Add:

```python
def test_interpret_stage_has_no_regex_nlu_imports() -> None:
    source = Path("src/argus/agent_runtime/stages/interpret.py").read_text()
    forbidden = [
        "extract_signals(",
        "extract_strategy_fields(",
        "resolve_intent(",
        "resolve_task_relation(",
        "resolve_gray_case_arbitration(",
        "_direct_conversational_response(",
        "_is_educational_turn(",
        "_is_approval_message(",
    ]
    for token in forbidden:
        assert token not in source
```

Add:

```python
def test_symbol_alias_dictionaries_are_deleted() -> None:
    paths = [
        Path("src/argus/agent_runtime/signals/task_relation.py"),
        Path("src/argus/domain/orchestrator.py"),
        Path("src/argus/agent_runtime/stages/interpret.py"),
    ]
    source = "\n".join(path.read_text() for path in paths)
    for token in ["SYMBOL_ALIASES", "COMMON_NAMES", "NON_SYMBOLS"]:
        assert token not in source
```

- [ ] **Step 2: Add no-hardcoded-clarify structural test**

Add:

```python
def test_clarify_stage_does_not_contain_slot_prompt_strings() -> None:
    source = Path("src/argus/agent_runtime/stages/clarify.py").read_text().lower()
    forbidden = [
        "what should trigger the buy",
        "which asset should i test",
        "what time period should i test",
        "how much should each recurring purchase be",
        "should i keep working on the current idea",
    ]
    for phrase in forbidden:
        assert phrase not in source
```

- [ ] **Step 3: Run structural tests**

Run:

```bash
poetry run pytest tests\agent_runtime\test_interpret_stage.py tests\agent_runtime\test_conversation_stages.py -q --no-cov
```

---

## Task 8: Final Verification Gate

**Files:**
- No planned file edits.

- [ ] **Step 1: Run focused runtime suite**

Run:

```bash
poetry run pytest tests\agent_runtime -q --no-cov
```

Expected: all agent runtime tests pass.

- [ ] **Step 2: Run full backend suite**

Run:

```bash
poetry run pytest
```

Expected: pass. If unrelated failures appear, capture exact failing tests and do not claim full verification.

- [ ] **Step 3: Run frontend lint**

Run:

```bash
Push-Location web
bun run lint
Pop-Location
```

Expected: pass. If existing lint debt appears, capture the exact output and separate it from Phase 3/4 changes.

- [ ] **Step 4: Check collapse size**

Run:

```bash
(Get-Content src\argus\agent_runtime\stages\interpret.py).Count
```

Expected: close to 400 lines. A small overage is acceptable only if every remaining helper is orchestration or validation, not NLU.

- [ ] **Step 5: Final source grep**

Run:

```bash
rg -n "extract_strategy_fields|extract_signals|SYMBOL_ALIASES|COMMON_NAMES|NON_SYMBOLS|_direct_conversational_response|resolve_gray_case_arbitration|_is_educational_turn|_is_approval_message" src tests
```

Expected: no production references. Test references are allowed only in structural guards that assert absence.

---

## Approval Checkpoint

Stop here until approval is given. After approval, execute Task 1 through Task 8 in order. Do not implement Phase 5 streaming/checkpointer changes and do not modify `compose.py` voice strings during this pass.
