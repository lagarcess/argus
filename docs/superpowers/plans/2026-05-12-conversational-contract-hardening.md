# Conversational Contract Hardening Implementation Plan

NOTE: Historical context. This document is retained as implementation evidence and is not the current execution source of truth.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden Argus's existing draft -> refine -> confirm -> run -> result loop so normal follow-ups patch the current conversational artifact, structured action chips behave as structured operations, and execution never skips required confirmation.

**Architecture:** Keep LangGraph as the only active conversational runtime. Normal text still reaches the structured LLM interpreter first, while structured action chips enter the runtime as explicit product operations instead of being downgraded to fragile text. Deterministic code only validates state transitions, preserves known fields, enforces confirmation boundaries, and creates state-aware recovery copy when the model is unavailable.

**Tech Stack:** Python, FastAPI, Pydantic v2, LangGraph checkpointers, pytest, Next.js/React, Bun tests, canonical data-only SSE.

---

## 2026-05-12 Implementation Amendment: Pending-Strategy Refinement Only

This branch is currently implementing one production-readiness gap from the
larger hardening plan: **Pending-strategy refinement**. Browser verification is
not marked complete until the live `/chat` flow proves the acceptance cases.

Active scope:

- Set the global drafted-strategy default `initial_capital` to `$1,000`.
- Keep `StrategySummary.capital_amount` semantics intact for explicit
  user-provided strategy amounts, especially DCA recurring contributions.
- Do not write default starting capital into `StrategySummary.capital_amount`.
- Expose `pending_strategy` on final SSE payloads while pending, ready for
  confirmation, or awaiting approval.
- Persist `pending_strategy` on assistant messages and recover it from recent
  metadata when the LangGraph checkpoint is unavailable.
- Treat `Change asset`, `Change dates`, and `Adjust assumptions` as structured
  refinement affordances attached to the active pending draft.
- Keep `Run backtest` confirmation-only; it must not execute from
  `await_user_reply`.
- Render selected action chips as action transcript items instead of normal
  typed user bubbles.

Still out of scope for this implementation pass: result breakdown depth, stale
result-card cleanup, quotas, Spanish expansion, fees, unequal allocations, new
strategy types, custom indicators, and RAG/vector memory.

---

## Source Of Truth Read Before Planning

- `AGENTS.md`
- `docs/PRODUCT.md`
- `docs/ARCHITECTURE.md`
- `docs/API_CONTRACT.md`
- `docs/DATA_MODEL.md`
- `.agent/designs/argus/DESIGN.md`
- `docs/CONVERSATIONAL_RUNTIME.md`
- `temp/docs/argus_runtime_qa_issue_log.md`

## Browser Evidence This Plan Addresses

The browser snapshots from `/chat` confirm the same macro failure across several user paths:

1. A pending AAPL buy-and-hold card exists, but `actually make it NVDA` collapses to model-unavailable recovery instead of preserving the draft and retrying the asset patch.
2. Clicking `Change asset` is rendered as a user message and still depends on the interpretation model.
3. A missing capital answer (`ten k`) can lead to a confirmation card in one run, but can also jump straight to result execution in another run.
4. `try again` does not reliably anchor to the last stable pending draft or last failed action.
5. Result follow-up can answer assumptions from run context, but breakdown/explanation prose repeats card metrics instead of adding interpretation.

## Macro Pattern

Argus is not consistently treating each user turn as a state transition against one active conversational artifact. The fix is not a phrase-specific map for "NVDA", "ten k", or "try again". The fix is to enforce a small transition contract:

- `start_draft`
- `patch_draft`
- `answer_missing_field`
- `ask_about_draft`
- `confirm_draft`
- `ask_about_result`
- `recover_last_turn`

These are conceptual operations. The implementation should continue using existing runtime names where possible: `semantic_turn_act`, `task_relation`, `pending_strategy_summary`, `confirmed_strategy_summary`, `latest_backtest_result_reference`, and structured `ChatActionPayload`.

## Non-Goals

- Do not add quota tracking.
- Do not expand Spanish/localization behavior.
- Do not add moving-average crossover execution, custom scripting, unequal allocations, fees, or new backtest engine breadth.
- Do not add a second orchestrator, second intent taxonomy, regex NLU layer, or frontend-invented strategy state.
- Do not add embeddings, pgvector, RAG, or semantic memory.

## Canon Compatibility

This plan enforces existing canon instead of replacing it:

- **Conversation is the product:** follow-ups patch the current draft/result instead of restarting.
- **The model proposes, Argus validates, the user confirms, the engine executes:** confirmation becomes a hard runtime boundary.
- **LLM-first interpretation:** normal natural-language text still reaches the structured interpreter before routing.
- **Deterministic guardrails after interpretation:** deterministic code validates field preservation, action-chip state, confirmation eligibility, and recovery boundaries.
- **One active chat brain:** all changes stay inside LangGraph runtime services and tests.
- **Frontend renders, it does not invent:** frontend continues rendering backend cards/actions/events.

## File Structure

Create:

- `tests/agent_runtime/test_conversational_contract_hardening.py` - regression tests for pending field preservation, confirmation gating, structured action semantics, and model-unavailable recovery.
- `tests/test_chat_action_contract.py` - API-level tests proving action chips carry structured context through `/api/v1/chat/stream`.

Modify:

- `src/argus/agent_runtime/state/models.py` - add structured action context to `RunState`, keep it JSON-safe, and expose it through `RunState.new()`.
- `src/argus/agent_runtime/stages/interpret_types.py` - pass selected thread metadata into `InterpretationRequest` so approval gating can know the prior stage without reading prose.
- `src/argus/agent_runtime/runtime.py` - accept and propagate `action_context` from API payloads into graph input.
- `src/argus/agent_runtime/graph/workflow.py` - pass selected thread metadata into interpretation, preserve latest pending snapshots across controlled action turns, and keep existing graph routes.
- `src/argus/agent_runtime/stages/interpret.py` - add structured action handling, contextual draft merge, approval gating, and state-aware model-unavailable recovery.
- `src/argus/agent_runtime/llm_interpreter.py` - remove duplicate or insufficient prior-strategy merge behavior once the runtime-level merge is authoritative.
- `src/argus/api/routers/agent.py` - pass `payload.action` as structured context to the runtime; keep router thin.
- `src/argus/api/chat_service.py` - keep user-visible action labels, but stop treating action labels as the only runtime signal.
- `docs/API_CONTRACT.md` - clarify structured action semantics, confirmation boundary, missing-field patching, and recovery behavior.
- `docs/CONVERSATIONAL_RUNTIME.md` - document the conversational artifact transition contract.
- `docs/ARCHITECTURE.md` - fix stale chat route wording and clarify that structured actions are product operations entering LangGraph.

Do not modify, except where listed in the amendment above:

- `src/argus/domain/engine.py`
- `src/argus/domain/engine_launch/**`
- `src/argus/domain/market_data/**`
- Supabase migrations
- collection UI or strategy surfaces outside result save behavior

---

### Task 1: Add Contract Regression Tests For Pending Draft Transitions

**Files:**
- Create: `tests/agent_runtime/test_conversational_contract_hardening.py`

- [x] **Step 1: Write failing tests for missing-field answers and natural-language approval gating**

Create `tests/agent_runtime/test_conversational_contract_hardening.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from argus.agent_runtime.stages.interpret import StructuredInterpretation, interpret_stage
from argus.agent_runtime.state.models import RunState, StrategySummary, TaskSnapshot, UserState


@dataclass(frozen=True)
class ResolvedAssetStub:
    canonical_symbol: str
    asset_class: str
    name: str = ""
    raw_symbol: str = ""


class RecordingInterpreter:
    def __init__(self, response: StructuredInterpretation | None) -> None:
        self.response = response
        self.requests: list[Any] = []

    def __call__(self, request: Any) -> StructuredInterpretation | None:
        self.requests.append(request)
        return self.response


def _interpret(
    *,
    message: str,
    response: StructuredInterpretation | None,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any] | None = None,
    action_context: dict[str, Any] | None = None,
):
    interpreter = RecordingInterpreter(response)
    state = RunState.new(
        current_user_message=message,
        recent_thread_history=[],
        action_context=action_context,
    )
    result = interpret_stage(
        state=state,
        user=UserState(user_id="user-1"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata or {},
        structured_interpreter=interpreter,
    )
    return result, interpreter


def test_answer_pending_need_preserves_prior_strategy_fields(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range="past year",
        capital_amount=None,
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User supplied the missing capital amount.",
        candidate_strategy_draft=StrategySummary(
            capital_amount=10000,
            sizing_mode="notional",
        ),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = _interpret(
        message="ten thousand",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={"last_stage_outcome": "await_user_reply"},
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.asset_class == "equity"
    assert strategy.date_range == "past year"
    assert strategy.capital_amount == 10000


def test_natural_language_approval_does_not_execute_from_missing_field_state(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range="past year",
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="The user supplied capital, not approval.",
        candidate_strategy_draft=StrategySummary(capital_amount=10000),
        semantic_turn_act="approval",
    )

    result, _ = _interpret(
        message="ten thousand",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={"last_stage_outcome": "await_user_reply"},
    )

    assert result.outcome == "ready_for_confirmation"
    assert "confirmation_payload" not in result.patch


def test_natural_language_approval_executes_only_after_confirmation_card(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range="past year",
        capital_amount=10000,
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User approved the visible confirmation.",
        candidate_strategy_draft=pending,
        semantic_turn_act="approval",
    )

    result, _ = _interpret(
        message="yes, run it",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
    )

    assert result.outcome == "approved_for_execution"
    assert result.patch["confirmation_payload"]["strategy"]["asset_universe"] == ["AAPL"]
```

- [x] **Step 2: Run tests and verify they fail**

Run:

```bash
poetry run pytest tests/agent_runtime/test_conversational_contract_hardening.py -q --no-cov
```

Expected: FAIL because `RunState.new()` and `interpret_stage()` do not yet accept `action_context` / `selected_thread_metadata`, and pending-field answers do not merge prior state for `answer_pending_need`.

- [x] **Step 3: Commit failing tests**

```bash
git add tests/agent_runtime/test_conversational_contract_hardening.py
git commit -m "test(agent): capture conversational contract regressions"
```

---

### Task 2: Thread Structured Action Context Through The Runtime

**Files:**
- Modify: `src/argus/agent_runtime/state/models.py`
- Modify: `src/argus/agent_runtime/stages/interpret_types.py`
- Modify: `src/argus/agent_runtime/runtime.py`
- Modify: `src/argus/agent_runtime/graph/workflow.py`
- Modify: `src/argus/api/routers/agent.py`
- Test: `tests/agent_runtime/test_conversational_contract_hardening.py`

- [x] **Step 1: Add structured action context models**

In `src/argus/agent_runtime/state/models.py`, add after `ArtifactReference`:

```python
StructuredActionType = Literal[
    "run_backtest",
    "change_dates",
    "change_asset",
    "adjust_assumptions",
    "cancel_confirmation",
    "show_breakdown",
    "refine_strategy",
    "save_strategy",
]


class StructuredActionContext(BaseModel):
    type: StructuredActionType
    label: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    presentation: Literal["confirmation", "result"] | None = None
```

Add to `RunState`:

```python
    structured_action: StructuredActionContext | None = None
```

Update `RunState.new()` signature:

```python
        action_context: StructuredActionContext | dict[str, Any] | None = None,
```

Inside `RunState.new()`, include:

```python
        structured_action = (
            StructuredActionContext.model_validate(action_context)
            if action_context is not None
            else None
        )
```

and pass `structured_action=structured_action` into the returned `RunState`.

- [x] **Step 2: Add selected metadata to interpretation requests**

In `src/argus/agent_runtime/stages/interpret_types.py`, change `InterpretationRequest` to:

```python
class InterpretationRequest(BaseModel):
    current_user_message: str
    recent_thread_history: list[Any] = Field(default_factory=list)
    latest_task_snapshot: TaskSnapshot | None = None
    selected_thread_metadata: dict[str, Any] = Field(default_factory=dict)
    user: UserState
```

- [x] **Step 3: Propagate action context through runtime input**

In `src/argus/agent_runtime/runtime.py`, add `action_context` to `build_workflow_input()`, `stream_agent_turn_events()`, and `run_agent_turn()`:

```python
    action_context: dict[str, Any] | None = None,
```

Pass it into `RunState.new()`:

```python
    run_state = RunState.new(
        current_user_message=normalized_message,
        recent_thread_history=_bounded_recent_thread_history(
            list(recent_thread_history or [])
        ),
        context_hints=list(context_hints or []),
        action_context=action_context,
    )
```

Pass it from `stream_agent_turn_events()` into `build_workflow_input()`, and from `run_agent_turn()` into `stream_agent_turn_events()`.

- [x] **Step 4: Pass selected metadata into interpret stage**

In `src/argus/agent_runtime/graph/workflow.py`, update `_interpret_node_async()`:

```python
        await interpret_stage_async(
            state=_run_state(state),
            user=_user(state),
            latest_task_snapshot=state.get("latest_task_snapshot"),
            selected_thread_metadata=state.get("selected_thread_metadata", {}),
            structured_interpreter=structured_interpreter,
        ),
```

- [x] **Step 5: Pass API action context to the runtime**

In `src/argus/api/routers/agent.py`, before `stream_agent_turn_events(...)`, build:

```python
        action_context = (
            payload.action.model_dump(mode="python")
            if payload.action is not None
            else None
        )
```

Then pass:

```python
                action_context=action_context,
```

into `stream_agent_turn_events(...)`.

- [x] **Step 6: Run focused tests and verify signature plumbing**

Run:

```bash
poetry run pytest tests/agent_runtime/test_conversational_contract_hardening.py -q --no-cov
```

Expected: tests still fail on behavior, but no longer fail on unexpected keyword arguments or missing `structured_action`.

- [x] **Step 7: Commit runtime plumbing**

```bash
git add src/argus/agent_runtime/state/models.py src/argus/agent_runtime/stages/interpret_types.py src/argus/agent_runtime/runtime.py src/argus/agent_runtime/graph/workflow.py src/argus/api/routers/agent.py
git commit -m "feat(agent): thread structured chat actions through runtime"
```

---

### Task 3: Add Structured Action Semantics For Confirmation Chips

**Files:**
- Modify: `tests/agent_runtime/test_conversational_contract_hardening.py`
- Modify: `src/argus/agent_runtime/stages/interpret.py`
- Test: `tests/agent_runtime/test_conversational_contract_hardening.py`

- [x] **Step 1: Add failing tests for `run_backtest` and `change_asset` chips**

Append to `tests/agent_runtime/test_conversational_contract_hardening.py`:

```python
def test_run_backtest_action_approves_pending_confirmation_without_llm(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range="past year",
        capital_amount=10000,
    )

    result, interpreter = _interpret(
        message="run backtest",
        response=None,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        action_context={
            "type": "run_backtest",
            "label": "Run backtest",
            "presentation": "confirmation",
            "payload": {},
        },
    )

    assert interpreter.requests == []
    assert result.outcome == "approved_for_execution"
    assert result.patch["confirmation_payload"]["strategy"]["asset_universe"] == ["AAPL"]


def test_change_asset_action_prompts_for_replacement_without_llm() -> None:
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range="past year",
        capital_amount=10000,
    )

    result, interpreter = _interpret(
        message="change asset",
        response=None,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        action_context={
            "type": "change_asset",
            "label": "Change asset",
            "presentation": "confirmation",
            "payload": {},
        },
    )

    assert interpreter.requests == []
    assert result.outcome == "await_user_reply"
    assert result.patch["requested_field"] == "asset_universe"
    assert result.patch["missing_required_fields"] == ["asset_universe"]
    assert "asset" in result.patch["assistant_prompt"].lower()
    assert result.patch["candidate_strategy_draft"]["asset_universe"] == ["AAPL"]
```

- [x] **Step 2: Run tests and verify action behavior fails**

Run:

```bash
poetry run pytest tests/agent_runtime/test_conversational_contract_hardening.py::test_run_backtest_action_approves_pending_confirmation_without_llm tests/agent_runtime/test_conversational_contract_hardening.py::test_change_asset_action_prompts_for_replacement_without_llm -q --no-cov
```

Expected: FAIL because structured action context is not handled before interpreter invocation.

- [x] **Step 3: Implement structured action handling in `interpret.py`**

In `src/argus/agent_runtime/stages/interpret.py`, add near the top:

```python
CONFIRMATION_EDIT_ACTION_FIELDS = {
    "change_asset": ("asset_universe", "What asset should I use instead?"),
    "change_dates": ("date_range", "What date range should I use instead?"),
    "adjust_assumptions": (
        "assumption",
        "Which assumption do you want to adjust: starting capital, timeframe, fees, or slippage?",
    ),
}
```

Update `interpret_stage()` and `interpret_stage_async()` signatures:

```python
    selected_thread_metadata: dict[str, Any] | None = None,
```

Pass the value through the synchronous wrapper.

Inside `interpret_stage_async()`, after `snapshot = normalize_task_snapshot(...)` and before checking `structured_interpreter is None`, add:

```python
    structured_action_result = _structured_action_stage_result_if_applicable(
        state=state,
        snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata or {},
        user=user,
    )
    if structured_action_result is not None:
        return structured_action_result
```

Add these helpers:

```python
def _structured_action_stage_result_if_applicable(
    *,
    state: RunState,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
    user: UserState,
) -> StageResult | None:
    del user
    action = state.structured_action
    if action is None or action.presentation != "confirmation":
        return None
    if snapshot is None or snapshot.pending_strategy_summary is None:
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "assistant_prompt": (
                    "I do not have an active confirmation to change. "
                    "Describe the investing idea again and I will prepare a fresh draft."
                ),
                "requested_field": None,
                "missing_required_fields": [],
            },
        )

    pending = snapshot.pending_strategy_summary.model_copy(deep=True)
    action_type = action.type
    if action_type == "run_backtest":
        if not _prior_stage_was_await_approval(selected_thread_metadata):
            return StageResult(
                outcome="ready_for_confirmation",
                stage_patch={
                    "candidate_strategy_draft": pending.model_dump(mode="python"),
                    "assistant_prompt": None,
                },
            )
        approved = _canonicalized_strategy(pending)
        if not strategy_can_be_approved(approved):
            return StageResult(
                outcome="needs_clarification",
                stage_patch={
                    "candidate_strategy_draft": approved.model_dump(mode="python"),
                    "missing_required_fields": _pending_needs(snapshot),
                },
            )
        return StageResult(
            outcome="approved_for_execution",
            stage_patch={
                "candidate_strategy_draft": approved.model_dump(mode="python"),
                "confirmation_payload": {
                    "strategy": approved.model_dump(mode="python"),
                    "optional_parameters": {},
                },
            },
        )

    if action_type in CONFIRMATION_EDIT_ACTION_FIELDS:
        requested_field, prompt = CONFIRMATION_EDIT_ACTION_FIELDS[action_type]
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "candidate_strategy_draft": pending.model_dump(mode="python"),
                "assistant_prompt": prompt,
                "requested_field": requested_field,
                "missing_required_fields": [requested_field],
                "response_intent": {
                    "kind": "clarification",
                    "semantic_needs": [_semantic_need_for_action(action_type)],
                    "requested_fields": [requested_field],
                    "facts": {
                        "strategy": pending.model_dump(mode="python"),
                        "current_user_message": state.current_user_message,
                        "structured_action": action.model_dump(mode="python"),
                    },
                    "options": [],
                },
            },
        )

    if action_type == "cancel_confirmation":
        return StageResult(
            outcome="ready_to_respond",
            stage_patch={
                "candidate_strategy_draft": StrategySummary().model_dump(mode="python"),
                "assistant_response": "No problem. I will leave that draft unrun.",
            },
        )
    return None


def _prior_stage_was_await_approval(metadata: dict[str, Any]) -> bool:
    return str(metadata.get("last_stage_outcome") or "") == "await_approval"


def _semantic_need_for_action(action_type: str) -> str:
    mapping = {
        "change_asset": "asset_target",
        "change_dates": "period",
        "adjust_assumptions": "assumption",
    }
    return mapping[action_type]
```

- [x] **Step 4: Run action tests**

Run:

```bash
poetry run pytest tests/agent_runtime/test_conversational_contract_hardening.py::test_run_backtest_action_approves_pending_confirmation_without_llm tests/agent_runtime/test_conversational_contract_hardening.py::test_change_asset_action_prompts_for_replacement_without_llm -q --no-cov
```

Expected: PASS.

- [x] **Step 5: Commit structured action semantics**

```bash
git add tests/agent_runtime/test_conversational_contract_hardening.py src/argus/agent_runtime/stages/interpret.py
git commit -m "feat(agent): handle confirmation actions as structured operations"
```

---

### Task 4: Centralize Contextual Draft Merging

**Files:**
- Modify: `src/argus/agent_runtime/stages/interpret.py`
- Modify: `src/argus/agent_runtime/llm_interpreter.py`
- Test: `tests/agent_runtime/test_conversational_contract_hardening.py`

- [x] **Step 1: Add a failing test for partial asset refinement**

Append:

```python
def test_refine_current_idea_preserves_prior_date_and_capital(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range="past year",
        capital_amount=10000,
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary="User changed the asset to Nvidia.",
        candidate_strategy_draft=StrategySummary(asset_universe=["NVDA"]),
        semantic_turn_act="refine_current_idea",
    )

    result, _ = _interpret(
        message="actually make it NVDA",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["NVDA"]
    assert strategy.asset_class == "equity"
    assert strategy.date_range == "past year"
    assert strategy.capital_amount == 10000
```

- [x] **Step 2: Run merge tests and verify failures**

Run:

```bash
poetry run pytest tests/agent_runtime/test_conversational_contract_hardening.py::test_answer_pending_need_preserves_prior_strategy_fields tests/agent_runtime/test_conversational_contract_hardening.py::test_refine_current_idea_preserves_prior_date_and_capital -q --no-cov
```

Expected: FAIL because the missing-field answer path produces a draft missing prior fields or routes to clarification instead of confirmation.

- [x] **Step 3: Add contextual merge helpers to `interpret.py`**

In `src/argus/agent_runtime/stages/interpret.py`, add:

```python
CONTEXTUAL_PATCH_TURN_ACTS = {
    "answer_pending_need",
    "refine_current_idea",
}


def _strategy_with_contextual_merge(
    *,
    strategy: StrategySummary,
    snapshot: TaskSnapshot | None,
    semantic_turn_act: str | None,
    task_relation: str,
) -> StrategySummary:
    if snapshot is None:
        return strategy
    if semantic_turn_act not in CONTEXTUAL_PATCH_TURN_ACTS and task_relation != "refine":
        return strategy
    prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    if prior is None:
        return strategy
    merged = prior.model_copy(deep=True)
    incoming = strategy.model_dump(mode="python")
    for key, value in incoming.items():
        if key in {"raw_user_phrasing", "strategy_thesis"}:
            continue
        if value in (None, "", [], {}):
            continue
        setattr(merged, key, value)
    if strategy.raw_user_phrasing:
        merged.raw_user_phrasing = strategy.raw_user_phrasing
    return merged
```

In `_stage_result_from_interpretation()`, replace the current strategy assignment with:

```python
    incoming_strategy = _strategy_with_contextual_merge(
        strategy=interpretation.candidate_strategy_draft,
        snapshot=snapshot,
        semantic_turn_act=interpretation.semantic_turn_act,
        task_relation=interpretation.task_relation,
    )
    strategy = (
        _canonicalized_strategy(incoming_strategy)
        if expects_strategy_route
        else incoming_strategy
    )
```

- [x] **Step 4: Remove duplicate merge responsibility from `llm_interpreter.py`**

In `src/argus/agent_runtime/llm_interpreter.py`, keep `_merge_prior_strategy()` as a compatibility function but remove merge authority from it. Runtime-level merge in `interpret.py` becomes the single authoritative merge path.

Use this narrower implementation if keeping the function:

```python
def _merge_prior_strategy(
    *,
    strategy: StrategySummary,
    request: InterpretationRequest,
    response: LLMInterpretationResponse,
) -> None:
    del strategy, request, response
    return None
```

Then rely on `interpret.py` for the authoritative merge.

- [x] **Step 5: Run contextual merge tests**

Run:

```bash
poetry run pytest tests/agent_runtime/test_conversational_contract_hardening.py::test_answer_pending_need_preserves_prior_strategy_fields tests/agent_runtime/test_conversational_contract_hardening.py::test_refine_current_idea_preserves_prior_date_and_capital -q --no-cov
```

Expected: PASS.

- [x] **Step 6: Run interpreter regression tests**

Run:

```bash
poetry run pytest tests/agent_runtime/test_interpret_stage.py tests/agent_runtime/test_llm_interpreter.py -q --no-cov
```

Expected: PASS. Update direct `_merge_prior_strategy()` assertions so the merge is verified through `interpret_stage`, not through the OpenRouter adapter internals.

- [x] **Step 7: Commit contextual merge**

```bash
git add src/argus/agent_runtime/stages/interpret.py src/argus/agent_runtime/llm_interpreter.py tests/agent_runtime/test_conversational_contract_hardening.py tests/agent_runtime/test_llm_interpreter.py
git commit -m "fix(agent): preserve pending draft fields across refinements"
```

---

### Task 5: Enforce Confirmation Boundary For Natural-Language Approval

**Files:**
- Modify: `src/argus/agent_runtime/stages/interpret.py`
- Modify: `tests/agent_runtime/test_interpret_stage.py`
- Test: `tests/agent_runtime/test_conversational_contract_hardening.py`

- [x] **Step 1: Update approval gate implementation**

In `src/argus/agent_runtime/stages/interpret.py`, update `_stage_result_from_interpretation()` to pass selected metadata into `_approval_stage_result_if_applicable()`:

```python
    approval_result = _approval_stage_result_if_applicable(
        decision=decision,
        snapshot=snapshot,
        state=state,
        selected_thread_metadata=selected_thread_metadata,
    )
```

Update `_approval_stage_result_if_applicable()` signature:

```python
def _approval_stage_result_if_applicable(
    *,
    decision: InterpretDecision,
    snapshot: TaskSnapshot | None,
    state: RunState,
    selected_thread_metadata: dict[str, Any],
) -> StageResult | None:
```

Add this guard immediately after checking `decision.semantic_turn_act`:

```python
    if not _prior_stage_was_await_approval(selected_thread_metadata):
        return None
```

Keep the existing `strategy_can_be_approved()` check.

- [x] **Step 2: Update existing approval tests to include prior stage metadata**

In `tests/agent_runtime/test_interpret_stage.py`, update approval tests that expect execution to pass:

```python
    result, _ = run_interpret_with_llm(
        message="Run backtest",
        response=response,
        snapshot=snapshot,
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        history=[
            {"role": "user", "content": "Buy and hold Tesla over the past year."},
            {"role": "assistant", "content": "Please confirm this backtest."},
        ],
    )
```

Update the helper `run_interpret_with_llm()` in that file to accept:

```python
    selected_thread_metadata: dict[str, Any] | None = None,
```

and pass it to `interpret_stage()`.

- [x] **Step 3: Run confirmation-boundary tests**

Run:

```bash
poetry run pytest tests/agent_runtime/test_conversational_contract_hardening.py::test_natural_language_approval_does_not_execute_from_missing_field_state tests/agent_runtime/test_conversational_contract_hardening.py::test_natural_language_approval_executes_only_after_confirmation_card tests/agent_runtime/test_interpret_stage.py::test_interpret_approval_uses_semantic_turn_act -q --no-cov
```

Expected: PASS.

- [x] **Step 4: Commit confirmation gate**

```bash
git add src/argus/agent_runtime/stages/interpret.py tests/agent_runtime/test_interpret_stage.py tests/agent_runtime/test_conversational_contract_hardening.py
git commit -m "fix(agent): require visible confirmation before execution"
```

---

### Task 6: Make Model-Unavailable Recovery Preserve The Active Artifact

**Files:**
- Modify: `tests/agent_runtime/test_conversational_contract_hardening.py`
- Modify: `src/argus/agent_runtime/stages/interpret.py`
- Test: `tests/agent_runtime/test_conversational_contract_hardening.py`

- [x] **Step 1: Add failing recovery test**

Append:

```python
def test_model_unavailable_recovery_mentions_active_pending_draft() -> None:
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range="past year",
        capital_amount=10000,
    )

    result, interpreter = _interpret(
        message="actually make it NVDA",
        response=None,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
    )

    assert len(interpreter.requests) == 1
    assert result.outcome == "ready_to_respond"
    assert "AAPL" in result.patch["assistant_response"]
    assert "draft" in result.patch["assistant_response"].lower()
    assert "try again" in result.patch["assistant_response"].lower()
    assert "interpretation model" not in result.patch["assistant_response"].lower()
```

- [x] **Step 2: Run recovery test and verify it fails**

Run:

```bash
poetry run pytest tests/agent_runtime/test_conversational_contract_hardening.py::test_model_unavailable_recovery_mentions_active_pending_draft -q --no-cov
```

Expected: FAIL because the current message says it could not reach the interpretation model and does not anchor to the active draft.

- [x] **Step 3: Implement state-aware recovery copy**

In `src/argus/agent_runtime/stages/interpret.py`, change `_offline_interpreter_unavailable_result()` signature:

```python
def _offline_interpreter_unavailable_result(
    *,
    user: UserState,
    snapshot: TaskSnapshot | None = None,
) -> StageResult:
```

Change the calls in `interpret_stage_async()`:

```python
        return _offline_interpreter_unavailable_result(user=user, snapshot=snapshot)
```

Add:

```python
def _offline_recovery_message(snapshot: TaskSnapshot | None) -> str:
    if snapshot is not None and snapshot.pending_strategy_summary is not None:
        strategy = snapshot.pending_strategy_summary
        assets = ", ".join(strategy.asset_universe) or "the current asset"
        strategy_label = (strategy.strategy_type or "strategy").replace("_", " ")
        return (
            f"I still have the {assets} {strategy_label} draft in this chat, "
            "but I could not process that last change. Try the change again in one sentence, "
            "or use the visible action chip to adjust the draft."
        )
    if snapshot is not None and snapshot.latest_backtest_result_reference is not None:
        return (
            "I still have the latest result in this chat, but I could not process that "
            "follow-up. Try the question again in one sentence."
        )
    return (
        "I could not process that turn. Your message is saved; please try again "
        "in one sentence."
    )
```

Use it in the returned stage patch:

```python
            "assistant_response": _offline_recovery_message(snapshot),
```

- [x] **Step 4: Run recovery tests**

Run:

```bash
poetry run pytest tests/agent_runtime/test_conversational_contract_hardening.py::test_model_unavailable_recovery_mentions_active_pending_draft -q --no-cov
```

Expected: PASS.

- [x] **Step 5: Commit recovery copy**

```bash
git add src/argus/agent_runtime/stages/interpret.py tests/agent_runtime/test_conversational_contract_hardening.py
git commit -m "fix(agent): anchor model recovery to active draft"
```

---

### Task 7: Verify API Action Contract End-To-End

**Files:**
- Create: `tests/test_chat_action_contract.py`
- Modify: `src/argus/api/routers/agent.py`
- Modify: `src/argus/api/chat_service.py`
- Test: `tests/test_chat_action_contract.py`

- [x] **Step 1: Write API test for `Change asset` chip preserving metadata context**

Create `tests/test_chat_action_contract.py`:

```python
from __future__ import annotations

import json
from typing import Any

from argus.api.main import app
from argus.api.message_store import create_message
from fastapi.testclient import TestClient


def _client() -> TestClient:
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    client.patch(
        "/api/v1/me",
        json={
            "onboarding": {
                "stage": "ready",
                "language_confirmed": True,
                "primary_goal": "test_stock_idea",
                "completed": False,
            }
        },
    )
    return client


def _stream_payloads(stream: str, event_type: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for part in stream.split("\n\n"):
        data_line = next(
            (line for line in part.splitlines() if line.startswith("data: ")),
            None,
        )
        if data_line is None:
            continue
        raw = data_line.removeprefix("data: ").strip()
        if raw == "[DONE]":
            continue
        event = json.loads(raw)
        if event.get("type") == event_type:
            payloads.append(event.get("payload", event))
    return payloads


def _conversation(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/v1/conversations", json={"language": "en"})
    assert response.status_code == 200
    return response.json()["conversation"]


def _user_id(client: TestClient) -> str:
    response = client.get("/api/v1/me")
    assert response.status_code == 200
    return str(response.json()["user"]["id"])


def test_change_asset_action_uses_structured_runtime_context() -> None:
    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="I read this as AAPL using a buy and hold approach.",
        metadata={
            "conversation_mode": "confirm",
            "agent_runtime_stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "strategy_thesis": "Buy and hold Apple.",
                    "asset_universe": ["AAPL"],
                    "asset_class": "equity",
                    "date_range": "past year",
                    "capital_amount": 10000,
                },
                "optional_parameters": {},
            },
            "confirmation_card": {
                "title": "AAPL buy and hold",
                "statusLabel": "Ready to run",
                "summary": "I read this as AAPL using a buy and hold approach.",
                "rows": [],
                "assumptions": ["Benchmark: SPY"],
                "actions": [
                    {
                        "id": "change-asset",
                        "type": "change_asset",
                        "label": "Change asset",
                        "presentation": "confirmation",
                        "payload": {},
                    }
                ],
            },
        },
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "change_asset",
                "label": "Change asset",
                "presentation": "confirmation",
                "payload": {},
            },
            "language": "en",
        },
    )

    assert response.status_code == 200
    final = _stream_payloads(response.text, "final")[0]
    text = final["assistant_response"] or final.get("assistant_prompt") or ""
    assert "asset" in text.lower()
    assert final["stage_outcome"] == "await_user_reply"
```

- [x] **Step 2: Run API action test**

Run:

```bash
poetry run pytest tests/test_chat_action_contract.py -q --no-cov
```

Expected: PASS after Tasks 2 and 3.

- [x] **Step 3: Ensure await-user-reply prompts surface as final assistant text**

In `src/argus/api/chat_service.py`, update `runtime_result_message()` so `assistant_prompt` is accepted for `await_user_reply` payloads:

```python
def runtime_result_message(runtime_result: dict[str, Any]) -> str | None:
    assistant_response = runtime_result.get("assistant_response")
    if isinstance(assistant_response, str) and assistant_response:
        return assistant_response
    assistant_prompt = runtime_result.get("assistant_prompt")
    if isinstance(assistant_prompt, str) and assistant_prompt:
        return assistant_prompt
    return None
```

- [x] **Step 4: Commit API action coverage**

```bash
git add tests/test_chat_action_contract.py src/argus/api/chat_service.py src/argus/api/routers/agent.py
git commit -m "test(api): verify structured chat action contract"
```

---

### Task 8: Tighten Result Explanation And Breakdown Without New Metrics

**Files:**
- Modify: `tests/test_openrouter_policy.py`
- Modify: `src/argus/agent_runtime/stages/explain.py`
- Modify: `src/argus/api/chat_service.py`
- Test: `tests/test_openrouter_policy.py`

- [x] **Step 1: Add regression test for concise breakdown prose**

In `tests/test_openrouter_policy.py`, add:

```python
def test_result_breakdown_is_concise_and_not_card_duplicate() -> None:
    from argus.api.chat_service import result_breakdown_message
    from argus.api.schemas import BacktestRun
    from argus.domain.store import utcnow

    run = BacktestRun(
        id="run-1",
        conversation_id="conversation-1",
        strategy_id=None,
        status="completed",
        asset_class="equity",
        symbols=["AAPL"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={
            "aggregate": {
                "performance": {
                    "total_return_pct": 39.5,
                    "benchmark_return_pct": 25.6,
                    "delta_vs_benchmark_pct": 13.9,
                    "max_drawdown_pct": -13.8,
                }
            },
            "by_symbol": {},
        },
        config_snapshot={
            "template": "buy_and_hold",
            "symbols": ["AAPL"],
            "timeframe": "1D",
            "benchmark_symbol": "SPY",
        },
        conversation_result_card={
            "title": "AAPL Buy and Hold",
            "rows": [
                {"key": "total_return_pct", "label": "Total Return (%)", "value": "+39.5%"},
                {"key": "max_drawdown", "label": "Max Drawdown", "value": "-13.8%"},
            ],
            "assumptions": ["Universe: AAPL.", "Benchmark: SPY."],
        },
        created_at=utcnow(),
        chart=None,
        trades=[],
    )

    text = result_breakdown_message(run)

    assert len(text.split()) <= 95
    assert "not a prediction" in text.lower()
    assert text.lower().count("total return") <= 1
```

- [x] **Step 2: Run breakdown test and verify it fails or passes narrowly**

Run:

```bash
poetry run pytest tests/test_openrouter_policy.py::test_result_breakdown_is_concise_and_not_card_duplicate -q --no-cov
```

Expected: FAIL before prose tightening because the current breakdown can restate card metrics in dense paragraph form.

- [x] **Step 3: Tighten deterministic breakdown fallback**

In `src/argus/api/chat_service.py`, update `result_breakdown_message()` fallback so it follows this shape:

```python
return (
    f"{symbols_text} finished {return_text} versus {benchmark_text}. "
    f"The main risk shown here was max drawdown of {drawdown_text}. "
    f"Assumptions: {assumption_text}. "
    "This is historical simulation evidence, not a prediction or trading recommendation."
)
```

Keep the existing LLM-backed path, but constrain its fallback and prompt to:

```python
"Keep the answer under 90 words. Do not restate every result-card metric. "
"Interpret what matters, name the main caveat, and use only supplied run data."
```

- [x] **Step 4: Run result explanation tests**

Run:

```bash
poetry run pytest tests/test_openrouter_policy.py tests/agent_runtime/test_conversation_stages.py -q --no-cov
```

Expected: PASS.

- [x] **Step 5: Commit result prose tightening**

```bash
git add src/argus/api/chat_service.py src/argus/agent_runtime/stages/explain.py tests/test_openrouter_policy.py
git commit -m "fix(chat): make result breakdowns interpretive and concise"
```

---

### Task 9: Clarify Canon Docs And API Contract

**Files:**
- Modify: `docs/API_CONTRACT.md`
- Modify: `docs/CONVERSATIONAL_RUNTIME.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/superpowers/plans/2026-05-12-conversational-contract-hardening.md`

- [x] **Step 1: Update API contract action semantics**

In `docs/API_CONTRACT.md`, under `# 12. Chat Streaming Endpoint`, add:

```markdown
### Structured Action Semantics

`action` payloads are structured product operations, not plain user text.

- `run_backtest` is valid only when the latest runtime state or safe metadata fallback contains a pending strategy that has already been shown as a confirmation card.
- `change_asset`, `change_dates`, and `adjust_assumptions` patch the active pending strategy by asking for the replacement field while preserving all other known fields.
- Missing-field answers patch only the requested field and must preserve prior known fields from the pending strategy.
- A runnable draft produced after a missing-field answer must emit confirmation before execution.
- `show_breakdown` and `save_strategy` require canonical result run context.
```

- [x] **Step 2: Update conversational runtime docs**

In `docs/CONVERSATIONAL_RUNTIME.md`, after `## Runtime Contract`, add:

```markdown
## Conversational Artifact Contract

Each active chat turn is grounded in one conversational artifact:

- a pending strategy draft awaiting clarification or confirmation, or
- a completed result awaiting follow-up.

Every user turn must start a draft, patch the pending draft, answer a pending field, ask about the draft, confirm the draft, ask about the latest result, or recover the latest failed turn. Argus should not restart from blank state when a prior artifact clearly exists, and it must not execute a completed draft until the user has seen and approved the confirmation state.
```

- [x] **Step 3: Fix architecture route drift and structured action wording**

In `docs/ARCHITECTURE.md`, verify the runtime route is:

```markdown
HTTP POST /api/v1/chat/stream (SSE)
```

Add under the NLU ownership rule:

```markdown
Structured action chips are not natural-language NLU shortcuts. They enter LangGraph as explicit product operations attached to the current confirmation or result artifact. Normal user text still reaches the structured LLM interpreter before routing decisions.
```

- [x] **Step 4: Run docs drift search**

Run:

```bash
bad_route='conversations/[{]id[}]/''chat'
bad_action='action chips are plain'' text'
bad_confirmation='bypass ''confirmation'
bad_progress='fake ''progress'
rg -n "$bad_route|$bad_action|$bad_confirmation|$bad_progress" docs AGENTS.md
```

Expected: no stale chat runtime route remains, and no docs describe action chips as plain user text.

- [x] **Step 5: Commit docs**

```bash
git add docs/API_CONTRACT.md docs/CONVERSATIONAL_RUNTIME.md docs/ARCHITECTURE.md docs/superpowers/plans/2026-05-12-conversational-contract-hardening.md
git commit -m "docs(agent): clarify conversational action contract"
```

---

### Task 10: Run Full Focused Verification

**Files:**
- No new files.

- [x] **Step 1: Run backend focused runtime suite**

Run:

```bash
poetry run pytest tests/agent_runtime/test_conversational_contract_hardening.py tests/agent_runtime/test_interpret_stage.py tests/agent_runtime/test_workflow.py tests/test_chat_runtime_cutover.py tests/test_chat_runtime_reload_guardrails.py tests/test_chat_action_contract.py tests/test_chat_stream_contract.py -q --no-cov
```

Expected: PASS.

- [x] **Step 2: Run frontend tests**

Run:

```bash
cd web && bun test __tests__
```

Expected: PASS.

- [x] **Step 3: Run lint**

Run:

```bash
poetry run ruff check .
```

Expected: PASS.

- [ ] **Step 4: Manual browser verification**

Start the app:

```bash
poetry run fastapi dev src/argus/api/main.py
cd web && NEXT_PUBLIC_MOCK_AUTH=true bun run dev
```

Verify these flows at `http://localhost:3000/chat`:

1. `Test buying and holding AAPL over the past year` -> confirmation card.
2. `actually make it NVDA` -> confirmation remains buy-and-hold, date remains past year, asset becomes NVDA.
3. `ten thousand` after a missing-capital prompt -> confirmation card, not result execution.
4. `Run backtest` chip -> result execution from visible confirmation without model-unavailable failure.
5. `Change asset` chip -> asks for replacement asset and preserves other fields.
6. `what assumptions are you using?` after result -> answers from latest run context.
7. `Show a breakdown` -> concise interpretive response without duplicate result card.

Blocked on local frontend startup: `NEXT_PUBLIC_MOCK_AUTH=true bun run dev`
failed because macOS rejected the local `@next/swc-darwin-arm64` binary with
`mapping process and mapped file (non-platform) have different Team IDs`, and
no WASM fallback package was installed. Backend startup reached
`http://127.0.0.1:8000`; browser flow verification could not proceed because
`http://localhost:3000` never became available.

- [x] **Step 5: Commit final verification updates**

```bash
git status --short
git add .
git commit -m "test(agent): verify conversational contract hardening"
```

---

## Self-Review Checklist

- Spec coverage: Tasks 1-7 cover pending refinement, missing-field answer preservation, structured actions, confirmation gate, and recovery. Task 8 covers result follow-up prose quality. Task 9 covers canon/API contract drift. Task 10 covers verification.
- Placeholder scan: this plan intentionally avoids unspecified implementation steps; each task names files, code shape, commands, and expected outcomes.
- Type consistency: `StructuredActionContext`, `action_context`, `selected_thread_metadata`, `pending_strategy_summary`, and `last_stage_outcome` are used consistently across tests, runtime input, and interpreter gating.
- Scope check: the plan does not add new strategy capabilities, quota, localization expansion, RAG, or a second orchestrator.
