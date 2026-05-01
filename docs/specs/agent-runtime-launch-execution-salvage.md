# Agent Runtime Launch Execution Salvage

Date: 2026-05-01
Status: Approved for planning
Scope: Production-ready launch execution slice for the conversational runtime

## 1. Scope And Purpose

This spec defines the minimum real execution capability needed to make the new conversational runtime the launch-ready product path.

In scope:

- real execution for:
  - `buy_and_hold`
  - `dca_accumulation`
  - `indicator_threshold`
- `single symbol only`
- normalized execution adapter boundary
- result-card-compatible payload
- explanation-compatible payload
- selective salvage from current engine and `archive-v0.1`
- unsupported behavior enforced at the adapter boundary
- explicit strategy-type confirmation support
- wiring the new runtime into the actual chat flow end to end

Out of scope:

- broad engine capability audit
- full migration map
- multi-symbol execution upgrades
- crossover strategies
- price-plus-indicator strategies
- advanced risk rules

This slice is intentionally narrow, but it is not a throwaway demo path. It is the production-ready launch cut that turns the new runtime into the real product flow.

## 2. Launch Execution Target

This slice should deliver a production-ready end-to-end path for three first-class strategy types:

- `buy_and_hold`
- `dca_accumulation`
- `indicator_threshold`

Launch constraints:

- `single symbol only`
- unsupported strategy types should be rejected before confirmation whenever the runtime can determine that early
- the adapter boundary remains the final execution truth layer
- `/api/v1/chat/stream` should be replaced with the new runtime path
- the existing useful UI, especially the result card, should be preserved where it already works well

### 2.1 Strategy Representation

The runtime should reason in first-class strategy types for product clarity.

The execution layer should normalize those into a shared internal shape such as:

- `strategy_type`
- `symbol`
- `timeframe`
- `date_range`
- `entry_rule`
- `exit_rule`
- `sizing_mode`
- `position_size`
- `capital_amount`
- `cadence`
- `parameters`
- `risk_rules`

Rules:

- exactly one sizing path is active at a time
- if the user does not specify sizing, a default capital amount may be applied and must be disclosed in confirmation
- non-launch `risk_rules` should route to unsupported handling, not partial execution

### 2.2 Cadence Support

`cadence` should stay top-level and nullable. It is a first-class execution concept, not a generic parameter bag.

Launch cadence set:

- `daily`
- `weekly`
- `monthly`
- `quarterly`

For launch strategy types:

- `buy_and_hold`: `cadence = null`
- `indicator_threshold`: `cadence = null`
- `dca_accumulation`: `cadence = daily | weekly | monthly | quarterly`

### 2.3 Confirmation Behavior

Confirmation should explicitly state the resolved strategy type, for example:

- `buy-and-hold`
- `DCA accumulation`
- `indicator threshold`

That makes misclassification easier to catch before execution.

### 2.4 UI And Result Contract Stance

Use a split contract:

- `frontend result card`
  preserve the current UI shape first, as long as it remains clean and useful

- `backend execution envelope`
  richer normalized payload for explanation, persistence, and failure handling

If the agent needs more explanation context than the current card exposes, add backend-only fields rather than bloating the visible card.

## 3. Adapter Contract And Failure Model

The execution adapter should be the single boundary between the conversational runtime and real backtest execution.

Its job is not just to run code. It must:

- accept a normalized, confirmed strategy
- enforce launch capability truth
- return a result envelope that supports both the result card and the agent explanation
- normalize failures into the runtime taxonomy

### 3.1 Adapter Input Contract

The adapter should accept a launch-bounded normalized request built from the confirmed runtime strategy.

Minimum input shape:

- `strategy_type`
- `symbol`
- `timeframe`
- `date_range`
- `entry_rule`
- `exit_rule`
- `sizing_mode`
- `position_size`
- `capital_amount`
- `cadence`
- `parameters`
- `risk_rules`
- `benchmark_symbol`

Rules:

- `buy_and_hold`
  - requires `symbol`, `date_range`
  - sizing resolved through `sizing_mode`
  - `entry_rule` and `exit_rule` may be normalized as start/end hold semantics

- `dca_accumulation`
  - requires `symbol`, `date_range`, `cadence`
  - sizing resolved through `sizing_mode`
  - execution means periodic accumulation on the chosen cadence

- `indicator_threshold`
  - requires `symbol`, `date_range`, `entry_rule`, `exit_rule`
  - sizing resolved through `sizing_mode`

Any request outside those supported launch forms should be rejected at the adapter boundary with normalized unsupported failure output.

### 3.2 Adapter Success Envelope

On success, the adapter should return a normalized execution result envelope.

Minimum success fields:

- `execution_status`
- `resolved_strategy`
- `resolved_parameters`
- `metrics`
- `benchmark_metrics`
- `assumptions`
- `caveats`
- `artifact_references`
- `provider_metadata`

This envelope serves three consumers:

- the result-card mapper
- the agent explanation stage
- persistence and thread memory

The frontend should not receive this whole object directly unless needed. The backend can map it into the cleaner existing result-card shape.

### 3.3 Failure Model

Failures must be normalized into the runtime taxonomy already in use:

- `parameter_validation_error`
- `missing_required_input`
- `unsupported_capability`
- `tool_execution_error`
- `upstream_dependency_error`
- `ambiguous_user_intent`
- `internal_system_error`

The adapter should also return structured failure detail:

- `execution_status`
- `failure_category`
- `failure_reason`

Suggested launch-ready `execution_status` values:

- `succeeded`
- `blocked_unsupported`
- `blocked_invalid_input`
- `failed_upstream`
- `failed_internal`

This keeps the runtime conversationally coherent when real execution replaces the stub.

### 3.4 Unsupported Enforcement

Unsupported behavior should be rejected in two layers:

- `runtime layer`
  reject unsupported strategy types or obvious out-of-scope requests before confirmation when possible

- `adapter layer`
  final enforcement of execution truth before engine execution

That avoids false promises while keeping the conversation helpful.

### 3.5 Graceful Chat Fallback

Because this path will back `/api/v1/chat/stream`, execution failure must not collapse the conversation.

Required fallback behaviors:

- `unsupported_capability`
  return to guided revision with supported alternatives

- `missing_required_input`
  return to clarification

- `upstream_dependency_error`
  explain the temporary issue and offer retry or wait framing

- `internal_system_error`
  fail gracefully with honest limits, not a broken stream

## 4. Salvage Strategy And Implementation Slice

This slice should salvage only the execution capability needed to launch the new chat runtime credibly. It should not become a general engine rewrite.

### 4.1 Salvage Rule

Source candidates:

- current engine logic in [engine.py](../../src/argus/domain/engine.py)
- selected execution, analysis, and market-data logic from `archive-v0.1`

Salvage policy:

- move useful logic into the new engine boundary
- do not preserve runtime dependence on archive modules
- do not revive old orchestration or old chat control flow
- prefer re-homing small, deep execution modules over copying broad subsystems

The product test is:
does this help Argus run the three launch strategy types truthfully, fast, and explainably?

### 4.2 What To Salvage First

Priority order:

1. `indicator and threshold execution primitives`
   Enough to run single-symbol `indicator_threshold` strategies cleanly.

2. `time-based accumulation primitives`
   Enough to run `dca_accumulation` on daily, weekly, monthly, and quarterly cadence.

3. `result shaping and analytics`
   Enough to power the existing result card and the explanation layer from the same envelope.

4. `buy-and-hold baseline path`
   This should be simple, explicit, and not depend on the threshold path.

### 4.3 What Not To Salvage Now

Do not expand this slice into:

- mixed-asset execution
- multi-symbol execution upgrades
- complex confluence strategies
- crossover support
- price-plus-indicator support
- advanced risk rules
- broad provider abstraction redesign

If code exists for those, note it, but do not let it widen the launch slice.

### 4.4 Implementation Seam

Recommended new boundary:

- `src/argus/agent_runtime/tools/real_backtest.py`
  adapter-facing runtime tool

- `src/argus/domain/engine_launch/`
  launch-bounded execution modules re-homed from current engine and archive logic

Possible module split:

- `strategies.py`
- `sizing.py`
- `cadence.py`
- `indicators.py`
- `results.py`
- `providers.py`

The goal is a few deep modules with simple interfaces, not a sprawl of wrappers.

### 4.5 First Implementation Slice

Build only what is needed to replace the stub and wire real execution into the current runtime:

- normalized adapter contract
- real execution path for:
  - `buy_and_hold`
  - `dca_accumulation`
  - `indicator_threshold`
- result-envelope mapper
- failure normalization into runtime taxonomy
- `/api/v1/chat/stream` cutover to the new runtime path
- reuse existing useful result-card UI behavior

### 4.6 Verification Standard

This slice is complete only if:

- a user can describe one of the three launch strategies conversationally
- Argus confirms the right strategy type
- Argus runs a real backtest
- the result card renders correctly
- the assistant explains the result and assumptions from the real envelope
- unsupported requests fall back conversationally instead of breaking the flow

## 5. Launch Implementation Plan Shape And Sequencing

This launch slice should be sequenced to preserve momentum and keep the system testable at every step.

### 5.1 Sequence

1. `adapter contract + engine_launch boundary`
   Define the normalized execution request and result interfaces and create the new launch-bounded engine package.

2. `buy_and_hold execution`
   Land the simplest real execution path first so the runtime can stop depending on a pure stub.

3. `dca_accumulation execution`
   Add cadence-aware periodic accumulation with the bounded launch cadence set.

4. `indicator_threshold execution`
   Add the real threshold-based path for single-symbol indicator strategies.

5. `result envelope + mapper`
   Produce the richer backend execution envelope and map it into the current useful result-card shape.

6. `runtime execution cutover`
   Replace the stubbed runtime tool with the real adapter and normalize failure handling.

7. `chat path cutover`
   Replace `/api/v1/chat/stream` orchestration with the new runtime.

8. `end-to-end launch verification`
   Verify the three supported strategy types through the real UI flow.

### 5.2 Why This Sequence

This sequence keeps the system useful after each step:

- the adapter boundary stabilizes first
- the simplest real execution path lands before the more expressive ones
- the result card and explanation contract are validated before full chat cutover
- chat cutover happens after execution truth exists

That reduces the chance of shipping a conversationally impressive path backed by fake execution.

### 5.3 Testing Shape

Minimum launch test layers:

- `unit tests`
  normalized strategy validation, sizing resolution, cadence resolution, indicator threshold normalization, failure mapping

- `engine integration tests`
  real execution for:
  - `buy_and_hold`
  - `dca_accumulation`
  - `indicator_threshold`

- `runtime tests`
  confirmation, unsupported rejection before confirm, adapter failure fallback, result-envelope explanation compatibility

- `API tests`
  `/api/v1/chat/stream` with the new runtime path

- `UI verification`
  result card still renders cleanly with preserved core shape

### 5.4 Launch Bar

The slice is launch-ready when all of these are true:

- the old stub is no longer the active execution path for supported launch strategies
- `/api/v1/chat/stream` is backed by the new runtime
- the three launch strategy types execute truthfully end to end
- result cards remain clean and understandable
- explanations are grounded in the same execution envelope
- unsupported requests degrade into conversational guidance instead of silent failure or broken streams
