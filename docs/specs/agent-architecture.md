# Conversational Backtest Agent Architecture

**Status:** Proposed  
**Date:** 2026-04-29  
**Scope:** Conversational backtest agent runtime for Argus

## 1. Purpose

Argus should behave like a conversational product first and a backtesting system second.
The core value is not exposing infrastructure to the user. The core value is helping a user move from idea to understanding through a guided conversation that can educate, clarify, execute, explain, and organize outcomes without feeling brittle or rigid.

This document defines a new agent runtime architecture for the conversational backtest flow.
It is intentionally a clean runtime slice, not a patch over the current orchestration shape.

## 2. Design Goals

- Make backtesting feel like a seamless conversation.
- Preserve user intent while allowing tool-driven task completion.
- Support multiple independent chat threads per user.
- Prevent state leakage between separate tasks in the same thread.
- Require explicit confirmation before execution.
- Support beginner guidance as a first-class mode.
- Keep execution and conversation aligned through a shared capability contract.
- Keep the architecture flexible enough to add, remove, or reorder stages later.

## 3. High-Level Architecture

The runtime is split into four layers:

1. **Session manager**
   Owns user scope, chat thread scope, context loading, and persistence write-back.

2. **LangGraph orchestration layer**
   Owns the staged workflow, transitions, stop conditions, and retry policy.

3. **Stage module layer**
   Implements each stage as an isolated, testable Python module with a standard interface.

4. **Tool and capability layer**
   Provides tool adapters and a shared configuration contract for supported operations, defaults, and validation.

## 4. Multi-Chat Runtime Model

The architecture must support multiple independent chats per user.

### 4.1 User scope

User scope stores durable user-level information shared across chats:

- `user_id`
- `display_name`
- `language_preference`
- `preferred_tone`
- `expertise_level`
- `response_verbosity`

These are defaults, not constraints. Explicit turn-level user instructions always win over stored preferences.

### 4.2 Thread scope

A chat thread is the canonical container for one conversation stream.
Each user can have many threads.

Thread scope stores:

- thread id
- message history
- thread metadata
- latest completed task snapshot
- latest backtest result reference
- latest collection action reference

Task continuity is decided only within the current thread. Cross-thread carryover is not default behavior.

### 4.3 Graph run scope

Each incoming user message inside a thread starts a fresh graph run.

The graph run receives:

- the current user message
- recent thread history
- selected thread metadata
- user preferences
- relevant artifact references

The graph run does **not** inherit transient execution artifacts such as:

- tool outputs from prior runs
- missing-field trackers
- confirmation flags
- retry counters
- temporary failure state

This is the primary anti-leakage rule.

## 5. State Model

The runtime uses three state shapes.

### 5.1 `UserState`

Durable across all chats for a user.

Fields:

- `user_id`
- `display_name`
- `language_preference`
- `preferred_tone`
- `expertise_level`
- `response_verbosity`

### 5.2 `ThreadState`

Durable within one chat thread.

Fields:

- `thread_id`
- `message_history`
- `thread_metadata`
- `latest_task_snapshot`
- `artifact_references`

### 5.3 `RunState`

Fresh per graph run and disposable after the run completes.

Fields:

- `current_user_message`
- `recent_thread_history`
- `normalized_signals`
- `intent`
- `task_relation`
- `requires_clarification`
- `user_goal_summary`
- `candidate_strategy_draft`
- `missing_required_fields`
- `optional_parameter_status`
- `effective_response_profile`
- `confirmation_payload`
- `tool_call_records`
- `failure_classification`
- `final_response_payload`

Only durable outcomes are written back to `ThreadState`.

## 6. Six-Stage Workflow

The initial workflow is graph-defined, not hardcoded into one monolithic runtime.

`Interpret -> Clarify -> Confirm -> Execute -> Explain -> Next step`

These six stages are the initial policy only.
The runtime must allow the workflow to change by editing graph wiring or swapping stage modules.

### 6.1 `Interpret`

Responsibilities:

- classify intent
- determine task relation
- extract deterministic signals
- resolve the effective response profile for the turn
- decide whether clarification is required

Must not:

- call execution tools
- confirm a strategy
- invent missing strategy details

### 6.2 `Clarify`

Responsibilities:

- ask the minimum next question
- gather required fields first
- offer optional parameters as opt-in
- support beginner guidance and idea shaping

Must not:

- ask large multi-part interrogations
- overwhelm the user with engine jargon
- execute a backtest
- hide assumptions as if approved

### 6.3 `Confirm`

Responsibilities:

- restate the strategy in plain language
- include required inputs
- include optional parameters with either user-specified values or defaults
- make assumptions explicit
- request approval before execution

Must not:

- execute before approval
- hide defaults
- rewrite the strategy during confirmation

### 6.4 `Execute`

Responsibilities:

- call tools
- capture structured observations
- classify failures
- perform bounded recovery within policy

Must not:

- silently alter the user thesis
- silently alter symbols
- silently alter entry logic
- silently alter exit logic
- silently alter date range
- retry indefinitely

### 6.5 `Explain`

Responsibilities:

- translate results into plain language
- adapt depth to the effective response profile
- explain assumptions and caveats
- connect results back to the user thesis

Must not:

- fabricate unsupported explanations
- bury important assumptions
- force depth the user did not request

### 6.6 `Next step`

Responsibilities:

- offer a small, relevant set of follow-up actions
- keep the conversation moving
- propose refine, compare, save, add to collection, or learn-more actions

Must not:

- dump a long menu
- ask unnecessary questions
- start a new execution implicitly

## 7. Intent Model

The initial first-class intent set is:

- `beginner_guidance`
- `strategy_drafting`
- `backtest_execution`
- `results_explanation`
- `collection_management`
- `conversation_followup`
- `unsupported_or_out_of_scope`

`beginner_guidance` is intentionally first-class.
A novice or curious user is not just "missing fields." They require a different conversation strategy.

## 8. Interpret Contract

`Interpret` must return a typed decision object rather than free-form text.

Fields:

- `intent`
- `task_relation`
  - `new_task`
  - `continue`
  - `refine`
  - `ambiguous`
- `requires_clarification`
- `user_goal_summary`
- `candidate_strategy_draft`
- `missing_required_fields`
- `optional_parameter_opportunity`
- `confidence`
- `reason_codes`
- `effective_response_profile`
- `user_preference_overridden_for_turn`

### 8.1 Response profile precedence

The effective response profile is resolved in this order:

1. explicit turn-level user instruction
2. user-level preference default
3. system fallback default

Initial fields:

- `effective_tone`
- `effective_verbosity`
- `effective_expertise_mode`

Examples:

- "Explain it like I'm 5" overrides advanced expertise defaults for this turn.
- "Walk me through each step in detail" overrides concise defaults for this turn.

### 8.2 Ambiguous vs under-specified

- `ambiguous` means the system cannot safely decide whether the message starts a new task, continues a prior task, or refines one.
- `under_specified` is not a task relation. It is a condition where the user's goal is understandable but the strategy details are incomplete.

`ambiguous` should trigger disambiguation.
`under_specified` should trigger guided drafting or beginner guidance.

## 9. Task-Relation Decision Model

The runtime should not rely on pure rules or pure LLM judgment.

It uses a pragmatic two-layer system:

1. **Signal extraction first**
   Deterministic preprocessing extracts concrete conversation signals.

2. **Resolution second**
   - obvious cases resolve in code
   - gray cases are sent to the LLM using narrow structured output
   - unresolved low-confidence cases trigger clarification

This avoids brittle FSM-only behavior and unreliable open-ended reasoning.

Example reason codes:

- `explicit_new_request`
- `references_prior_result`
- `pending_confirmation_exists`
- `symbols_changed`
- `strategy_logic_changed`
- `beginner_language_detected`
- `request_is_under_specified`

## 10. Execution Readiness Gate

Before entering `Confirm`, the agent must have the minimum required execution inputs.

Required fields:

- `strategy_thesis`
- `asset_universe`
- `entry_logic`
- `exit_logic`
- `date_range`

Optional fields are handled separately and disclosed during confirmation with user-selected values or defaults.

Initial optional fields:

- `initial_capital`
- `timeframe`
- `fees`
- `slippage`
- `engine_options`

The system must support future optional knobs without rewriting the workflow.

## 11. Shared Capability Contract

Defaults and supported knobs should not live in ad hoc stage logic.

A shared configuration contract sits between the conversation layer and the execution layer.

It defines:

- supported intents or tool families
- required execution fields
- optional parameters
- default values
- allowed ranges
- validation rules
- plain-language labels and descriptions
- unsupported combinations
- versioning

Both conversation stages and execution must read from the same contract so that the agent never promises behavior the engine cannot support.

## 12. Tool Layer

Tools are the agent's hands.
They should be narrow, typed, and observable.

Initial tool families:

- backtest tools
- education tools
- collection tools
- thread/context tools

Each tool should return a normalized result envelope:

- `success`
- `payload`
- `error_type`
- `error_message`
- `retryable`
- `capability_context`

Structured observations are required so recovery can be machine-usable.

## 13. Disciplined ReAct

The runtime should use a bounded, stage-scoped form of ReAct.

Pattern:

1. `Reason`
   What is the stage trying to achieve?

2. `Act`
   Call only a stage-legal tool.

3. `Observe`
   Receive structured output.

4. `Decide`
   Continue, retry within policy, or exit back to conversation.

This is not a free-form autonomous agent loop.
The runtime, not the LLM, owns tool availability, stage legality, retry policy, and stop conditions.

## 14. Recovery Framework

Recovery must be observation-driven and intent-preserving.

Initial failure taxonomy:

- `parameter_validation_error`
- `missing_required_input`
- `unsupported_capability`
- `tool_execution_error`
- `upstream_dependency_error`
- `ambiguous_user_intent`
- `internal_system_error`

### 14.1 Recovery principles

- `capability-aware`
  Retry only within declared support boundaries.

- `intent-preserving`
  Never silently change thesis, symbols, entry logic, exit logic, or date range.

- `observation-driven`
  React to classified failures, not improvisation.

- `transparent`
  If recovery changes the path materially, tell the user.

- `bounded`
  Retries must stop at a small fixed limit.

### 14.2 Recovery policy by class

- `parameter_validation_error`
  Retry only if the correction is mechanical and intent-preserving.

- `missing_required_input`
  Do not blind retry. Return to conversation.

- `unsupported_capability`
  Do not push deeper into unsupported paths. Offer a conversational plan B.

- `tool_execution_error`
  Retry only if the tool marks it retryable and the action is unchanged.

- `upstream_dependency_error`
  Allow bounded transient retries, then surface clearly.

- `ambiguous_user_intent`
  Do not execute. Ask the user.

- `internal_system_error`
  Fail gracefully and stop quickly.

## 15. Memory And Persistence

For v1, memory should stay explicit and simple.

### 15.1 Memory layers

- `User memory`
  Durable across all chats. Stores profile and preference facts.

- `Thread memory`
  Durable within one chat. Stores message history, metadata, compact task snapshots, and artifact references.

- `Artifact memory`
  Durable references to outputs such as backtest result ids, strategy draft ids, and collection ids.

The graph run itself is not persisted memory.

### 15.2 Write-back rules

After a run completes, write back only durable outcomes:

- appended user and assistant messages
- updated thread timestamps
- latest task snapshot
- artifact references
- confirmed preference updates
- optional lightweight analytics/debug summaries

Do not persist:

- temporary missing-field trackers
- retry counters
- transient tool observations
- unapproved confirmation payloads
- transient failure internals as live thread state

### 15.3 Task snapshot

Each thread should persist a compact latest task snapshot:

- latest task type
- whether the last task completed
- latest confirmed strategy summary
- latest backtest result reference
- latest collection action reference
- last unresolved follow-up, if any

This is a retrieval aid, not a mutable execution object.

### 15.4 Context assembly

Each run should receive a context package assembled from:

- recent raw messages
- latest task snapshot
- relevant artifact summaries
- user preferences

This is better than dumping the full thread into every run.

## 16. Implementation Shape

This architecture should be implemented as a new runtime slice.

Recommended package structure:

- `src/argus/agent_runtime/`
- `src/argus/agent_runtime/session/`
- `src/argus/agent_runtime/state/`
- `src/argus/agent_runtime/graph/`
- `src/argus/agent_runtime/stages/`
- `src/argus/agent_runtime/signals/`
- `src/argus/agent_runtime/capabilities/`
- `src/argus/agent_runtime/tools/`
- `src/argus/agent_runtime/recovery/`
- `src/argus/agent_runtime/profile/`

### 16.1 Stage module interface

Each stage module should expose a small contract such as:

- `run(state, deps) -> StageResult`

Rules:

- no hidden mutation of shared state
- explicit returned patches/results
- dependencies injected from a runtime container

### 16.2 Graph routing

The graph should route on typed stage outcomes rather than parsing strings.

Example outcome categories:

- `needs_clarification`
- `ready_for_confirmation`
- `approved_for_execution`
- `execution_succeeded`
- `execution_failed_recoverably`
- `execution_failed_terminally`
- `ready_to_respond`
- `end_run`

## 17. First Implementation Slice

The first implementation should prove the architecture before deep engine integration.

Build:

- multi-chat-aware session manager
- typed state models
- LangGraph with the six stages wired
- fully implemented `Interpret`, `Clarify`, `Confirm`, and `Next step`
- `Execute` against a stubbed backtest tool adapter
- `Explain` against stubbed result payloads
- shared capability contract for required and optional fields
- failure taxonomy and bounded retry scaffold
- anti-leakage tests

## 18. Testing Strategy

Minimum test layers:

- `unit tests`
  - signal extraction
  - effective response profile resolution
  - capability defaults
  - failure classification
  - stage logic

- `graph tests`
  - no execute before approval
  - clarification routes correctly
  - retry bounds are respected
  - unsupported capability exits to conversation

- `session tests`
  - multi-chat isolation
  - fresh `RunState` per user message
  - preserved thread history
  - no carryover of confirmation or tool scratch state

- `integration tests`
  - beginner asks a vague question
  - user drafts and confirms a strategy
  - user asks to explain results
  - user starts a new task in the same thread
  - user starts a separate thread with no leakage

## 19. Migration Guidance

This should begin as a parallel architecture track, not an immediate rewrite of all orchestration paths.

Recommended stance:

- create a clean runtime entry boundary
- validate the new conversational backtest slice end to end
- keep the first scope narrow
- retire older orchestration paths only after the new runtime proves stable

## 20. Canonical Docs Impact

This design conflicts with the spirit or detail level of parts of the current canonical docs, especially where those docs describe the product as a broader, already-stabilized full system rather than an agent-runtime-first conversational architecture.

Recommended documentation approach:

1. **Revise, do not silently ignore**
   If this architecture is the new intended direction, the canonical docs must be updated. The code should not drift away from them again.

2. **Update in priority order**
   - `docs/PRODUCT.md`
     Reframe the product around conversation as the primary value and backtesting as supporting infrastructure.
   - `docs/ARCHITECTURE.md`
     Replace thin-orchestration language with explicit agent-runtime, stage, graph, capability, and multi-chat session boundaries.
   - `docs/API_CONTRACT.md`
     Revise only after the runtime entry points and interaction model are decided.
   - `docs/DATA_MODEL.md`
     Add user, thread, run-adjacent persistence boundaries, task snapshots, and artifact references.
   - design docs
     Align UX and conversation guidance with the staged runtime.

3. **Treat this spec as the pivot document**
   This file should act as the bridge document for the rewrite of canonical docs. Do not try to rewrite every canonical doc before the architecture decision is accepted.

4. **Avoid full-product overclaiming**
   The canonical docs should distinguish between:
   - stable alpha product truths
   - proposed runtime architecture
   - deferred product surfaces or capabilities

5. **Sequence the revision work**
   First approve this agent architecture.
   Then update `PRODUCT.md` and `ARCHITECTURE.md`.
   Then update `DATA_MODEL.md` and `API_CONTRACT.md` to match the new boundaries.

This keeps the documentation authoritative again instead of aspirational in one direction and implemented in another.
