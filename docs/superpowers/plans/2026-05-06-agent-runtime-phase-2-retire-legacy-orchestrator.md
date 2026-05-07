# Agent Runtime Phase 2 Retire Legacy Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Do not dispatch subagents unless the user explicitly requests parallel agent work. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the parallel legacy NLU/orchestrator path so Argus chat turns use one intent taxonomy and one LLM-first runtime classification path.

**Architecture:** Phase 2 keeps the current synchronous LangGraph `run_agent_turn(...)` path and removes the old `domain/orchestrator.py` chat classifier plus `BacktestConversationState` state machine wiring. Explicit onboarding control tokens stay in `api/main.py` as API/UI control handling, not natural-language intent routing. The agent runtime and `OpenRouterStructuredInterpreter` remain the only intent classification path for chat turns.

**Tech Stack:** Python 3.10, FastAPI, Pydantic v2, LangGraph `StateGraph`, LangChain/OpenRouter structured output, pytest, Bun/Next.js lint.

---

## Source Of Truth

- Primary: `temp/argus_runtime_sot.md`
- Required project docs reviewed before planning: `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md`, `docs/DATA_MODEL.md`, `.agent/designs/argus/DESIGN.md`
- Existing Phase 1 plan reference: `docs/superpowers/plans/2026-05-06-agent-runtime-phase-1-remediation.md`

## Scope Guardrails

- Stay strictly in Phase 2.
- Do not edit `compose.py`, `_contextual_response_stage_result_if_applicable`, or downstream robotic UI/stage copy unless a Phase 2 test cannot pass without removing legacy orchestrator wiring.
- Do not add regex, natural-language string matching, or hardcoded natural-language early returns to route chat execution.
- Onboarding sentinel handling such as `__ONBOARDING_GOAL__:` is allowed only as an explicit UI control-token parser in `api/main.py`; it must not classify normal user language.
- Do not delete failing tests outright. Rewrite legacy tests to assert the LangGraph/runtime path with mock interpreters.
- Leave unrelated working tree changes untouched. Current pre-plan audit shows untracked `diff.txt`; do not modify it.

## Pre-Execution Gate

- [ ] **Step 1: Confirm branch and working tree before editing**

Run:

```bash
git branch --show-current
git status --short
```

Expected:

```text
fix/argus-runtime-sot
```

The working tree may include unrelated files. Do not revert or edit unrelated files.

- [ ] **Step 2: Sync branch only after approval**

Run after approval, before code edits:

```bash
git fetch origin main
git rebase origin/main
```

Expected:

```text
Current branch fix/argus-runtime-sot is up to date.
```

If the rebase reports conflicts, stop and resolve only files required for Phase 2. Do not discard user changes.

## Current Audit Summary

- `src/argus/api/main.py` imports `BacktestConversationState` and `parse_onboarding_goal`, defines a legacy `orchestrate_chat_turn(...)` wrapper, and still contains `_latest_backtest_state(...)`, `_state_has_params(...)`, and `_latest_completed_run_id(...)`.
- `src/argus/domain/orchestrator.py` still contains the old `ChatTurnIntent` schema, `classify_chat_turn_intent(...)`, deterministic symbol/template extraction, `orchestrate_chat_turn(...)`, and `assistant_message_for_chat_turn(...)`.
- `src/argus/domain/backtest_state_machine.py` exists only for legacy orchestration and tests after live call sites are removed.
- Tests still importing legacy APIs:
  - `tests/test_openrouter_policy.py`
  - `tests/test_conversational_ux.py`
  - `tests/test_alpha_orchestration_regression.py`
  - `tests/test_backtest_state_machine.py`
- `src/argus/domain/strategy_capabilities.py` duplicates some capability metadata, but it remains live engine/normalizer support through `src/argus/domain/engine.py` and `src/argus/domain/slot_normalizer.py`. Do not delete it in Phase 2.

## Phase 2 File Map

- Modify: `src/argus/domain/orchestrator.py`
  - Retain only starter prompts and AI entity-name suggestion.
  - Remove `classify_chat_turn_intent(...)`, `ChatTurnIntent`, `BacktestParamsUpdate` imports, deterministic extraction helpers, `orchestrate_chat_turn(...)`, and `assistant_message_for_chat_turn(...)`.
- Delete: `src/argus/domain/backtest_state_machine.py`
  - No live runtime path should import it after `api/main.py` and tests are migrated.
- Modify: `src/argus/api/main.py`
  - Remove `BacktestConversationState` import and legacy state helpers.
  - Remove the `orchestrate_chat_turn(...)` wrapper.
  - Stop importing `parse_onboarding_goal` and private `_resolve_language` from `domain/orchestrator.py`.
  - Add local API helpers for explicit onboarding control tokens and language resolution.
  - Preserve existing endpoints and the `run_agent_turn(...)` chat path.
- Modify: `tests/test_openrouter_policy.py`
  - Replace legacy chat-composer classifier coverage with a runtime/interpreter bounded-profile test.
- Modify: `tests/test_conversational_ux.py`
  - Rewrite to assert assistant copy comes from mock runtime interpreter output.
- Modify: `tests/test_alpha_orchestration_regression.py`
  - Rewrite the Spanish multi-turn persistence regression to use `run_agent_turn(...)` plus a mock interpreter.
- Modify: `tests/test_backtest_state_machine.py`
  - Rewrite state-machine tests into runtime interpret-stage routing tests.
- Add: `tests/test_phase2_runtime_sot.py`
  - Static guard tests for retired legacy classifier/state-machine wiring.

---

### Task 1: Rewrite Tests To Describe Phase 2 Behavior

**Files:**
- Modify: `tests/test_openrouter_policy.py`
- Modify: `tests/test_conversational_ux.py`
- Modify: `tests/test_alpha_orchestration_regression.py`
- Modify: `tests/test_backtest_state_machine.py`
- Add: `tests/test_phase2_runtime_sot.py`

- [ ] **Step 1: Replace legacy OpenRouter classifier test**

In `tests/test_openrouter_policy.py`, remove this import:

```python
from argus.domain.orchestrator import ChatTurnIntent, classify_chat_turn_intent
```

Add these imports:

```python
from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.runtime import run_agent_turn
from argus.agent_runtime.session.manager import InMemorySessionManager
```

Replace `test_legacy_chat_composer_uses_bounded_profile` with:

```python
def test_agent_runtime_turn_uses_interpretation_profile_without_legacy_composer(
    monkeypatch,
) -> None:
    FakeChatOpenRouter.calls.clear()
    FakeChatOpenRouter.structured_response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="new_task",
        user_goal_summary="User asked what Argus can do.",
        assistant_response="Argus can help shape and test investing ideas.",
        semantic_turn_act="educational_question",
    )
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(openrouter, "ChatOpenRouter", FakeChatOpenRouter)

    contract = build_default_capability_contract()
    workflow = build_workflow(
        structured_interpreter=OpenRouterStructuredInterpreter(
            contract=contract,
            model_name="custom/model",
        )
    )
    result = run_agent_turn(
        workflow=workflow,
        session_manager=InMemorySessionManager(),
        user=UserState(user_id="u1"),
        thread_id="thread-policy",
        message="what can you do?",
    )

    assert result["assistant_response"] == (
        "Argus can help shape and test investing ideas."
    )
    assert FakeChatOpenRouter.calls == [
        {"model": "custom/model", "temperature": 0, "max_tokens": 1200}
    ]
```

Run:

```bash
pytest tests/test_openrouter_policy.py -q
```

Expected before implementation:

```text
FAILED
```

Failure should be from stale imports or still-present legacy API expectations.

- [ ] **Step 2: Rewrite conversational UX tests against mock runtime interpreter**

Replace `tests/test_conversational_ux.py` with:

```python
from __future__ import annotations

from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.runtime import run_agent_turn
from argus.agent_runtime.session.manager import InMemorySessionManager
from argus.agent_runtime.stages.interpret import (
    InterpretationRequest,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import UserState


def _workflow_with_interpretation(response: StructuredInterpretation):
    def interpreter(_request: InterpretationRequest) -> StructuredInterpretation:
        return response

    return build_workflow(structured_interpreter=interpreter)


def test_conversational_ux_response_comes_from_runtime_interpreter() -> None:
    workflow = _workflow_with_interpretation(
        StructuredInterpretation(
            intent="conversation_followup",
            task_relation="new_task",
            user_goal_summary="User asks what Argus can do.",
            assistant_response=(
                "Argus can help you shape an investing idea, check what details "
                "are missing, and run a historical simulation when it is ready."
            ),
            confidence=0.92,
            semantic_turn_act="educational_question",
        )
    )

    result = run_agent_turn(
        workflow=workflow,
        session_manager=InMemorySessionManager(),
        user=UserState(user_id="u1", language_preference="en"),
        thread_id="thread-ux",
        message="help",
    )

    assert result["stage_outcome"] == "ready_to_respond"
    assert "shape an investing idea" in result["assistant_response"]


def test_conversational_ux_low_confidence_runtime_response_is_preserved() -> None:
    workflow = _workflow_with_interpretation(
        StructuredInterpretation(
            intent="conversation_followup",
            task_relation="new_task",
            user_goal_summary="User asks for guidance.",
            assistant_response=(
                "I can start by explaining the idea in plain language, then we "
                "can turn it into a supported backtest."
            ),
            confidence=0.1,
            semantic_turn_act="educational_question",
        )
    )

    result = run_agent_turn(
        workflow=workflow,
        session_manager=InMemorySessionManager(),
        user=UserState(user_id="u1", language_preference="en"),
        thread_id="thread-ux-low-confidence",
        message="help",
    )

    assert result["stage_outcome"] == "ready_to_respond"
    assert "supported backtest" in result["assistant_response"]


def test_legacy_template_fallback_is_not_available() -> None:
    import argus.domain.orchestrator as orchestrator_module

    assert not hasattr(orchestrator_module, "assistant_message_for_chat_turn")
    assert not hasattr(orchestrator_module, "ChatTurnIntent")
```

Run:

```bash
pytest tests/test_conversational_ux.py -q
```

Expected before implementation:

```text
FAILED
```

The final test should fail until the legacy orchestrator API is removed.

- [ ] **Step 3: Rewrite Spanish multi-turn regression to use `run_agent_turn(...)`**

Replace `tests/test_alpha_orchestration_regression.py` with:

```python
from __future__ import annotations

from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.runtime import run_agent_turn
from argus.agent_runtime.session.manager import InMemorySessionManager
from argus.agent_runtime.stages.interpret import (
    InterpretationRequest,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import StrategySummary, UserState


def test_spanish_multiturn_strategy_context_uses_agent_runtime() -> None:
    responses = iter(
        [
            StructuredInterpretation(
                intent="strategy_drafting",
                task_relation="new_task",
                requires_clarification=True,
                user_goal_summary="El usuario quiere probar un backtest.",
                candidate_strategy_draft=StrategySummary(
                    raw_user_phrasing="quiero probar un backtest",
                    strategy_thesis="El usuario quiere preparar un backtest.",
                ),
                missing_required_fields=["strategy_type", "asset_universe"],
                semantic_turn_act="new_idea",
            ),
            StructuredInterpretation(
                intent="strategy_drafting",
                task_relation="refine",
                requires_clarification=True,
                user_goal_summary="El usuario eligio una regla RSI.",
                candidate_strategy_draft=StrategySummary(
                    raw_user_phrasing=(
                        "quiero probar una reversion a la media con RSI"
                    ),
                    strategy_type="indicator_threshold",
                    strategy_thesis="Comprar cuando RSI indica sobreventa.",
                    entry_logic="RSI drops below 30",
                    exit_logic="RSI rises above 55",
                ),
                missing_required_fields=["asset_universe", "date_range"],
                semantic_turn_act="answer_pending_need",
            ),
            StructuredInterpretation(
                intent="backtest_execution",
                task_relation="refine",
                requires_clarification=False,
                user_goal_summary="El usuario completo activo, capital y periodo.",
                candidate_strategy_draft=StrategySummary(
                    raw_user_phrasing=(
                        "Quiero GOOG, con capital de 10mil, 1 anio hacia atras "
                        "desde hoy"
                    ),
                    strategy_type="indicator_threshold",
                    strategy_thesis="Comprar GOOG cuando RSI indica sobreventa.",
                    asset_universe=["GOOG"],
                    asset_class="equity",
                    entry_logic="RSI drops below 30",
                    exit_logic="RSI rises above 55",
                    date_range="last year",
                    sizing_mode="capital_amount",
                    capital_amount=10000,
                ),
                semantic_turn_act="answer_pending_need",
            ),
        ]
    )
    seen_requests: list[InterpretationRequest] = []

    def interpreter(request: InterpretationRequest) -> StructuredInterpretation:
        seen_requests.append(request)
        return next(responses)

    workflow = build_workflow(structured_interpreter=interpreter)
    manager = InMemorySessionManager()
    user = UserState(user_id="u1", language_preference="es-419")
    thread_id = "thread-spanish-context"

    first = run_agent_turn(
        workflow=workflow,
        session_manager=manager,
        user=user,
        thread_id=thread_id,
        message="quiero probar un backtest",
    )
    second = run_agent_turn(
        workflow=workflow,
        session_manager=manager,
        user=user,
        thread_id=thread_id,
        message="quiero probar una reversion a la media con RSI",
    )
    third = run_agent_turn(
        workflow=workflow,
        session_manager=manager,
        user=user,
        thread_id=thread_id,
        message="Quiero GOOG, con capital de 10mil, 1 anio hacia atras desde hoy",
    )

    assert first["stage_outcome"] == "await_user_reply"
    assert second["stage_outcome"] == "await_user_reply"
    assert third["stage_outcome"] == "await_approval"
    assert third["confirmation_payload"]["strategy"]["asset_universe"] == ["GOOG"]
    assert third["confirmation_payload"]["strategy"]["strategy_type"] == (
        "indicator_threshold"
    )
    assert seen_requests[1].latest_task_snapshot is not None
    assert seen_requests[2].latest_task_snapshot is not None
    assert len(seen_requests[2].recent_thread_history) >= 2
```

Run:

```bash
pytest tests/test_alpha_orchestration_regression.py -q
```

Expected before implementation:

```text
PASSED
```

This test can pass before code deletion because it targets the correct runtime path. Keep it as the migration replacement for legacy `orchestrate_chat_turn(...)`.

- [ ] **Step 4: Rewrite state-machine tests into runtime interpret-stage tests**

Replace `tests/test_backtest_state_machine.py` with:

```python
from __future__ import annotations

from argus.agent_runtime.stages.interpret import (
    InterpretationRequest,
    StructuredInterpretation,
    interpret_stage,
)
from argus.agent_runtime.state.models import (
    RunState,
    StrategySummary,
    TaskSnapshot,
    UserState,
)


def _interpret_with(response: StructuredInterpretation):
    def interpreter(_request: InterpretationRequest) -> StructuredInterpretation:
        return response

    return interpreter


def test_partial_strategy_from_mock_interpreter_waits_for_missing_fields() -> None:
    result = interpret_stage(
        state=RunState.new(
            current_user_message="test RSI on Apple",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=None,
        structured_interpreter=_interpret_with(
            StructuredInterpretation(
                intent="strategy_drafting",
                task_relation="new_task",
                requires_clarification=True,
                user_goal_summary="User wants an RSI idea but no period yet.",
                candidate_strategy_draft=StrategySummary(
                    strategy_type="indicator_threshold",
                    strategy_thesis="Buy Apple when RSI is oversold.",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    entry_logic="RSI drops below 30",
                    exit_logic="RSI rises above 55",
                ),
                missing_required_fields=["date_range"],
                semantic_turn_act="new_idea",
            )
        ),
    )

    assert result.outcome == "needs_clarification"
    assert result.decision is not None
    assert result.decision.candidate_strategy_draft.asset_universe == ["AAPL"]
    assert result.decision.missing_required_fields == ["date_range"]


def test_ready_strategy_from_mock_interpreter_reaches_confirmation() -> None:
    result = interpret_stage(
        state=RunState.new(
            current_user_message="test RSI on Apple last year",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=None,
        structured_interpreter=_interpret_with(
            StructuredInterpretation(
                intent="backtest_execution",
                task_relation="new_task",
                requires_clarification=False,
                user_goal_summary="User supplied an executable RSI idea.",
                candidate_strategy_draft=StrategySummary(
                    strategy_type="indicator_threshold",
                    strategy_thesis="Buy Apple when RSI is oversold.",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    date_range="last year",
                    entry_logic="RSI drops below 30",
                    exit_logic="RSI rises above 55",
                ),
                semantic_turn_act="new_idea",
            )
        ),
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision is not None
    assert result.decision.semantic_turn_act == "new_idea"


def test_approval_uses_llm_semantic_turn_act_not_state_machine_confirmation() -> None:
    pending = StrategySummary(
        strategy_type="indicator_threshold",
        strategy_thesis="Buy Apple when RSI is oversold.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range="last year",
        entry_logic="RSI drops below 30",
        exit_logic="RSI rises above 55",
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="yes run it",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=TaskSnapshot(
            latest_task_type="backtest_execution",
            completed=False,
            pending_strategy_summary=pending,
        ),
        structured_interpreter=_interpret_with(
            StructuredInterpretation(
                intent="backtest_execution",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="User approved the pending strategy.",
                semantic_turn_act="approval",
            )
        ),
    )

    assert result.outcome == "approved_for_execution"
    assert result.patch["confirmation_payload"]["strategy"] == pending.model_dump(
        mode="python"
    )
```

Run:

```bash
pytest tests/test_backtest_state_machine.py -q
```

Expected before implementation:

```text
PASSED
```

This validates the replacement behavior before deleting the legacy state-machine module.

- [ ] **Step 5: Add static Phase 2 guard tests**

Create `tests/test_phase2_runtime_sot.py`:

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_domain_orchestrator_retains_only_non_routing_helpers() -> None:
    source = _source("src/argus/domain/orchestrator.py")

    banned_symbols = [
        "classify_chat_turn_intent",
        "ChatTurnIntent",
        "BacktestParamsUpdate",
        "orchestrate_chat_turn",
        "assistant_message_for_chat_turn",
        "COMMON_NAMES",
        "NON_SYMBOLS",
        "_extract_symbols_from_text",
        "_extract_deterministic_intent",
        "_extract_strategy_intent",
    ]
    for symbol in banned_symbols:
        assert symbol not in source

    assert "def get_starter_prompts" in source
    assert "def suggest_entity_name" in source


def test_api_main_has_no_legacy_orchestrator_wiring() -> None:
    source = _source("src/argus/api/main.py")

    banned_fragments = [
        "BacktestConversationState",
        "from argus.domain.backtest_state_machine",
        "orchestrate_chat_turn",
        "_latest_backtest_state",
        "_state_has_params",
        "_latest_completed_run_id",
        "parse_onboarding_goal",
        "from argus.domain.orchestrator import _resolve_language",
    ]
    for fragment in banned_fragments:
        assert fragment not in source


def test_backtest_state_machine_module_is_retired() -> None:
    assert not (ROOT / "src/argus/domain/backtest_state_machine.py").exists()
```

Run:

```bash
pytest tests/test_phase2_runtime_sot.py -q
```

Expected before implementation:

```text
FAILED
```

Failure should identify the remaining legacy symbols.

---

### Task 2: Slim `domain/orchestrator.py` To Non-Routing Helpers

**Files:**
- Modify: `src/argus/domain/orchestrator.py`

- [ ] **Step 1: Replace `domain/orchestrator.py` with non-routing helper content**

Replace the file with:

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from argus.llm.openrouter import (
    build_openrouter_model,
    log_openrouter_failure,
    resolve_openrouter_model,
)

SUPPORTED_GOALS = {
    "learn_basics",
    "test_stock_idea",
    "build_passive_strategy",
    "explore_crypto",
    "surprise_me",
}

STARTER_PROMPTS = {
    "learn_basics": [
        "How do I start investing?",
        "Explain a market term simply",
        "What does buying every month mean?",
        "How do I test an idea?",
    ],
    "test_stock_idea": [
        "Buy Apple after big drops",
        "Hold Tesla for a year",
        "Compare Nvidia with Apple",
        "Test Microsoft when it starts rising",
    ],
    "build_passive_strategy": [
        "Buy SPY every month",
        "Compare a fund with a stock",
        "Test a simple long-term idea",
        "Start with a low-maintenance idea",
    ],
    "explore_crypto": [
        "Backtest Bitcoin halvings",
        "Hold Bitcoin for a year",
        "Compare Ethereum and Bitcoin",
        "Buy Bitcoin after big drops",
    ],
    "surprise_me": [
        "Show me something interesting",
        "Show me a simple first idea",
        "Test a familiar stock",
        "Compare two familiar assets",
    ],
}


class NameSuggestion(BaseModel):
    name: str


def _resolve_language(language: str | None) -> Literal["en", "es-419"]:
    if (language or "en").lower().startswith("es"):
        return "es-419"
    return "en"


def get_starter_prompts(primary_goal: str | None) -> list[str]:
    goal = primary_goal if primary_goal in STARTER_PROMPTS else "surprise_me"
    return STARTER_PROMPTS[goal]


def suggest_entity_name(
    *,
    entity_type: Literal["conversation", "strategy", "collection"],
    context: str,
    language: str | None,
) -> str | None:
    primary_model = resolve_openrouter_model()
    model = build_openrouter_model("name_suggestion", model_name=primary_model)
    if model is None:
        return None

    try:
        structured = model.with_structured_output(NameSuggestion)
        resolved = _resolve_language(language)
        response = structured.invoke(
            [
                {
                    "role": "system",
                    "content": (
                        "Generate a concise user-facing name for Argus Alpha. "
                        "Max 6 words. No punctuation-only output. "
                        f"Entity type: {entity_type}. Language: {resolved}."
                    ),
                },
                {"role": "user", "content": context},
            ]
        )
        candidate = response.name.strip()
        return candidate if candidate else None
    except Exception as exc:
        log_openrouter_failure(
            task="name_suggestion",
            model_name=primary_model,
            exc=exc,
            message="Name suggestion failed",
        )
        return None
```

Run:

```bash
pytest tests/test_phase2_runtime_sot.py::test_domain_orchestrator_retains_only_non_routing_helpers -q
```

Expected:

```text
PASSED
```

---

### Task 3: Remove Legacy State-Machine Wiring From `api/main.py`

**Files:**
- Modify: `src/argus/api/main.py`

- [ ] **Step 1: Remove legacy imports and wrapper**

Remove:

```python
from argus.domain.backtest_state_machine import (
    BacktestConversationState,
)
```

Change:

```python
from argus.domain.orchestrator import (
    get_starter_prompts,
    parse_onboarding_goal,
    suggest_entity_name,
)
```

to:

```python
from argus.domain.orchestrator import get_starter_prompts, suggest_entity_name
```

Delete:

```python
def orchestrate_chat_turn(**kwargs: Any) -> Any:
    from argus.domain.orchestrator import orchestrate_chat_turn as legacy_orchestrator

    return legacy_orchestrator(**kwargs)
```

- [ ] **Step 2: Add local API-only onboarding helpers**

Add near the other module-level helpers, after `InternalAgentRuntimeTurnRequest`:

```python
SUPPORTED_ONBOARDING_GOALS = {
    "learn_basics",
    "test_stock_idea",
    "build_passive_strategy",
    "explore_crypto",
    "surprise_me",
}


def _resolve_language(language: str | None) -> str:
    if (language or "en").lower().startswith("es"):
        return "es-419"
    return "en"


def _parse_onboarding_control_message(message: str) -> str | None:
    if message == "__ONBOARDING_SKIP__":
        return "surprise_me"
    prefix = "__ONBOARDING_GOAL__:"
    if not message.startswith(prefix):
        return None
    goal = message.removeprefix(prefix)
    if goal in SUPPORTED_ONBOARDING_GOALS:
        return goal
    return None
```

This is an explicit UI control-token parser. Do not extend it to natural-language intent classification.

- [ ] **Step 3: Delete unused legacy state helpers**

Delete all of:

```python
def _latest_backtest_state(
    history: list[dict[str, Any]],
) -> BacktestConversationState:
    ...


def _state_has_params(state: BacktestConversationState) -> bool:
    ...


def _latest_completed_run_id(history: list[dict[str, Any]]) -> str | None:
    ...
```

- [ ] **Step 4: Replace onboarding helper calls**

Change:

```python
onboarding_goal = parse_onboarding_goal(request_message)
```

to:

```python
onboarding_goal = _parse_onboarding_control_message(request_message)
```

Delete both function-local imports:

```python
from argus.domain.orchestrator import _resolve_language
```

The existing calls to `_resolve_language(lang)` should then resolve to the local helper added in Step 2.

Run:

```bash
pytest tests/test_phase2_runtime_sot.py::test_api_main_has_no_legacy_orchestrator_wiring -q
```

Expected:

```text
PASSED
```

- [ ] **Step 5: Verify chat endpoint still routes through runtime**

Run:

```bash
pytest tests/agent_runtime/test_workflow.py::test_internal_agent_runtime_turn_endpoint_returns_confirmation_ready_result -q
```

Expected:

```text
PASSED
```

---

### Task 4: Retire `BacktestConversationState`

**Files:**
- Delete: `src/argus/domain/backtest_state_machine.py`

- [ ] **Step 1: Delete the legacy state-machine module**

Delete:

```text
src/argus/domain/backtest_state_machine.py
```

Run:

```bash
rg -n "BacktestConversationState|BacktestParamsUpdate|apply_backtest_turn|backtest_state_machine" src tests
```

Expected:

```text
No output.
```

- [ ] **Step 2: Verify static retirement guard**

Run:

```bash
pytest tests/test_phase2_runtime_sot.py::test_backtest_state_machine_module_is_retired -q
```

Expected:

```text
PASSED
```

---

### Task 5: Validate Capability Duplication Decision

**Files:**
- Read-only audit: `src/argus/domain/strategy_capabilities.py`
- Read-only audit: `src/argus/agent_runtime/capabilities/contract.py`
- Read-only audit: `src/argus/domain/engine.py`
- Read-only audit: `src/argus/domain/slot_normalizer.py`

- [ ] **Step 1: Confirm `strategy_capabilities.py` is not legacy NLU routing**

Run:

```bash
rg -n "STRATEGY_CAPABILITIES|CapabilityContract" src/argus/domain src/argus/agent_runtime tests
```

Expected:

```text
src/argus/domain/engine.py
src/argus/domain/slot_normalizer.py
src/argus/domain/strategy_capabilities.py
src/argus/agent_runtime/capabilities/contract.py
```

There will also be tests for both registries.

- [ ] **Step 2: Keep `strategy_capabilities.py` in Phase 2**

No code change. Reason: it is still used by the backtest engine and slot normalizer after legacy orchestrator removal. Consolidating it with `CapabilityContract` would be a separate engine/runtime registry refactor and is outside Phase 2 unless tests show it is only reachable through deleted legacy modules.

Run:

```bash
pytest tests/test_strategy_capabilities.py tests/test_slot_normalizer.py -q
```

Expected:

```text
PASSED
```

---

### Task 6: Run Targeted Regression Suite

**Files:**
- No code edits unless a targeted test fails from Phase 2 changes.

- [ ] **Step 1: Run migrated Phase 2 tests**

Run:

```bash
pytest tests/test_phase2_runtime_sot.py tests/test_openrouter_policy.py tests/test_conversational_ux.py tests/test_alpha_orchestration_regression.py tests/test_backtest_state_machine.py -q
```

Expected:

```text
PASSED
```

- [ ] **Step 2: Run runtime tests most likely to catch chat regressions**

Run:

```bash
pytest tests/agent_runtime/test_workflow.py tests/agent_runtime/test_llm_interpreter.py -q
```

Expected:

```text
PASSED
```

- [ ] **Step 3: Search for retired legacy symbols**

Run:

```bash
rg -n "classify_chat_turn_intent|ChatTurnIntent|BacktestConversationState|BacktestParamsUpdate|apply_backtest_turn|orchestrate_chat_turn|assistant_message_for_chat_turn|parse_onboarding_goal" src tests
```

Expected:

```text
No output.
```

If output appears only in this plan document, rerun with:

```bash
rg -n "classify_chat_turn_intent|ChatTurnIntent|BacktestConversationState|BacktestParamsUpdate|apply_backtest_turn|orchestrate_chat_turn|assistant_message_for_chat_turn|parse_onboarding_goal" src tests
```

The command intentionally scopes to `src tests`, so plan-document matches should not appear.

---

### Task 7: Full Verification Gate

**Files:**
- No code edits unless verification fails from Phase 2 changes.

- [ ] **Step 1: Run full backend test suite**

Run from repo root:

```bash
pytest
```

Expected:

```text
PASSED
```

- [ ] **Step 2: Run frontend lint**

Run from `web/`:

```bash
bun run lint
```

Expected:

```text
Passed with no errors.
```

If lint reports existing unrelated debt outside changed files, capture the output and do not widen Phase 2 without approval.

- [ ] **Step 3: Verify working tree scope**

Run:

```bash
git status --short
git diff -- src/argus/domain/orchestrator.py src/argus/api/main.py tests/test_openrouter_policy.py tests/test_conversational_ux.py tests/test_alpha_orchestration_regression.py tests/test_backtest_state_machine.py tests/test_phase2_runtime_sot.py
```

Expected changed files:

```text
src/argus/domain/orchestrator.py
src/argus/domain/backtest_state_machine.py
src/argus/api/main.py
tests/test_openrouter_policy.py
tests/test_conversational_ux.py
tests/test_alpha_orchestration_regression.py
tests/test_backtest_state_machine.py
tests/test_phase2_runtime_sot.py
docs/superpowers/plans/2026-05-06-agent-runtime-phase-2-retire-legacy-orchestrator.md
```

The pre-existing untracked `diff.txt` should remain untouched.

---

### Task 8: Commit Gate

**Files:**
- Stage only Phase 2 files.

- [ ] **Step 1: Stage Phase 2 changes only**

Run:

```bash
git add src/argus/domain/orchestrator.py src/argus/domain/backtest_state_machine.py src/argus/api/main.py tests/test_openrouter_policy.py tests/test_conversational_ux.py tests/test_alpha_orchestration_regression.py tests/test_backtest_state_machine.py tests/test_phase2_runtime_sot.py docs/superpowers/plans/2026-05-06-agent-runtime-phase-2-retire-legacy-orchestrator.md
```

Expected:

```text
No output.
```

- [ ] **Step 2: Commit only after `pytest` and `bun run lint` pass**

Run:

```bash
git commit -m "refactor(runtime): retire legacy orchestrator NLU"
```

Expected:

```text
[fix/argus-runtime-sot ...] refactor(runtime): retire legacy orchestrator NLU
```

Do not commit if either full verification command fails.

---

## Completion Criteria

- `classify_chat_turn_intent(...)` no longer exists.
- `ChatTurnIntent` no longer exists.
- `BacktestConversationState` no longer exists.
- `src/argus/domain/backtest_state_machine.py` is deleted.
- `api/main.py` does not import or wrap legacy orchestrator routing.
- Chat streaming endpoint still reaches `run_agent_turn(...)`.
- Migrated tests use mock interpreters and assert runtime/LLM-first behavior.
- No regex, natural-language string matching, or hardcoded chat-routing early returns are introduced.
- `pytest` passes.
- `bun run lint` passes from `web/`.
- Commit exists only after the verification gate passes.
