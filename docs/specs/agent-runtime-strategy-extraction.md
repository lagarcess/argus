# Agent Runtime Strategy Extraction

**Status:** Proposed  
**Date:** 2026-05-01  
**Scope:** Natural language strategy extraction inside `Interpret` for the Argus conversational backtest agent

## 1. Purpose

The first agent runtime slice proved the orchestration shape: session management, staged workflow, bounded recovery, confirmation-first execution, and an internal API seam.

The next problem is language brittleness.

Today the runtime can guide a backtest conversation, but it is still too strict about how users phrase strategy ideas. A normal person should be able to say:

- `buy when RSI drops below 30`
- `sell when RSI goes above 70`
- `close it if volume dries up`
- `test Tesla over the last two years`

Argus should understand those ideas without forcing keyword-perfect phrasing, while still staying disciplined, capability-aware, and transparent.

This document defines the next runtime slice: a bounded natural language strategy extractor used by the `Interpret` stage.

It does not change the main chat path yet. It improves how the new runtime understands strategy requests.

## 2. Design Goals

- Reduce conversational brittleness in `Interpret`.
- Let normal users express strategies in natural language.
- Preserve trust by never silently dropping unsupported intent.
- Preserve transparency by separating raw user phrasing from normalized Argus semantics.
- Keep clarification targeted and low-friction.
- Keep the architecture bounded and easier to change than regex-heavy parsing.

## 3. Scope

### 3.1 In scope

- one structured extraction call inside `Interpret`
- extraction of required strategy fields
- `raw + normalized` field outputs
- per-field status bands
- detection of unsupported constraints
- material-meaning-change rules
- grouped clarification payloads for ambiguous fields
- capability-contract simplification options for unsupported constraints

### 3.2 Out of scope

- rewiring the public chat path
- replacing the stubbed backtest execution tool
- multi-model routing
- fast-model / heavy-model escalation
- adaptive per-user extraction behavior
- thread-level learning from prior corrections

Those can be added later if V1 extraction proves insufficient.

## 4. Runtime Boundary

This slice stays inside the current runtime architecture. It does not add a new graph stage.

The runtime split becomes:

- `signals`
  Deterministic cues for task relation, explicit overrides, prior-result references, and beginner hints.

- `extractor`
  One bounded structured extraction pass for strategy fields and unsupported constraints.

- `Interpret`
  The decision point that combines signals, extracted fields, field statuses, capability validation, and clarification policy.

This keeps the architecture simpler than a new pre-`Interpret` stage and avoids collapsing strategy understanding into the signal layer.

## 5. V1 Extraction Approach

V1 uses:

- one structured extraction call
- deterministic post-validation against the capability contract
- no numeric model self-confidence
- no second model pass for support mapping
- no synonym-regex sprawl as the primary strategy

The extractor may use natural language understanding to propose structured fields, but the runtime remains the source of truth for whether those fields are acceptable, ambiguous, missing, or unsupported.

## 6. Extractor Contract

The extractor returns a typed contract used by `Interpret`.

### 6.1 Required extracted fields

- `strategy_thesis`
- `asset_universe`
- `entry_logic`
- `exit_logic`
- `date_range`

### 6.2 Per-field representation

Each strategy field returns both:

- `raw_value`
- `normalized_value`

This preserves what the user actually said while still giving Argus a normalized internal representation to validate and confirm.

### 6.3 Field status bands

Each strategy field gets one of:

- `resolved`
- `missing`
- `ambiguous`
- `unsupported`

These status bands are the V1 decision primitive. They are preferred over numeric confidence because they answer the product question directly:

- can Argus proceed,
- should it clarify,
- or must it block and revise?

### 6.4 Additional contract outputs

- `field_status`
- `reason_codes`
- `unsupported_constraints`

The extractor does not return arbitrary numeric confidence in V1.

## 7. Supporting Models

This slice should introduce dedicated typed models for extraction.

### 7.1 `ExtractedFieldValue`

Fields:

- `raw_value`
- `normalized_value`
- `status`

### 7.2 `AmbiguousField`

Fields:

- `field_name`
- `raw_value`
- `candidate_normalized_value`
- `reason_code`

### 7.3 `UnsupportedConstraint`

Fields:

- `category`
- `raw_value`
- `explanation`
- `simplification_options`

These models should live close to the runtime state and stage contracts, not inside frontend-specific code or execution adapters.

## 8. Unsupported Constraint Handling

The extractor must never silently ignore unsupported intent.

### 8.1 V1 unsupported categories

- `unsupported_time_granularity`
- `unsupported_order_semantics`
- `unsupported_asset_mix`
- `unsupported_position_logic`
- `unsupported_strategy_logic`
- `unsupported_data_dependency`

### 8.2 Category intent

- `unsupported_time_granularity`
  For requests such as market-open or intraday semantics the current execution path cannot represent.

- `unsupported_order_semantics`
  For order behavior such as market-open execution rules, stop-limit specifics, partial fills, and similar unsupported semantics.

- `unsupported_asset_mix`
  For mixed-asset runs that combine equity and crypto in one simulation.

- `unsupported_position_logic`
  For shorting, leverage, options-like semantics, or unsupported portfolio behavior.

- `unsupported_strategy_logic`
  For compound or confluence logic the engine cannot represent even if the user’s idea is understandable.

- `unsupported_data_dependency`
  For truly unavailable external inputs or unsupported non-indicator dependencies.

`unsupported_data_dependency` should not be used for ordinary technical indicators that are intended to be supported through `pandas-ta`.

### 8.3 Routing rule

If any unsupported constraint is present:

- do not enter `Confirm`
- route back to `Clarify`
- explain the unsupported part plainly
- provide at least one low-friction simplification option when available

Trust and clarity take priority over rushing into a broken confirmation flow.

## 9. Capability Contract Extensions

The capability contract should become the source of truth for simplification options.

It should expose:

- unsupported constraint categories
- simplification templates
- plain-language labels
- suggested replacement parameter values where applicable

Examples:

- `unsupported_time_granularity` -> `retry with daily bars`
- `unsupported_asset_mix` -> `split into separate equity and crypto runs`
- `unsupported_strategy_logic` -> `simplify to RSI-only logic`

This keeps the backend honest and lets the UI present one-click simplification actions without inventing unsupported alternatives.

## 10. Normalization Policy

The extractor may normalize natural language into Argus-supported semantics, but only within trust-preserving rules.

### 10.1 Allowed normalization

Example:

- `sell when RSI > 70` may normalize into supported `exit_logic`

This reduces friction and helps ordinary users speak naturally.

### 10.2 Disclosure rule

Normalization must always remain visible by the time Argus reaches `Confirm`.

`Confirm` must show the normalized strategy clearly so the user sees what Argus intends to run.

### 10.3 Material meaning change rule

If normalization materially changes the user’s meaning, the field becomes `ambiguous` and the flow returns to `Clarify`.

V1 meaning-change categories:

- `semantic_category_shift`
- `threshold_or_comparator_shift`
- `dropped_constraint`
- `scope_shift`
- `negation_or_conditional_reversal`

Examples:

- `sell` normalized into `trim`
- `above 70` normalized into `crosses above 70`
- `at market open` dropped from the normalized field
- `sell all` normalized into a partial exit
- `not above 70` normalized into `above 70`

The rule is strict:
Argus may simplify phrasing, but it may not silently reinterpret strategy intent.

## 11. Clarification Behavior

Clarification should stay as narrow as possible while still being conversational and low-friction.

### 11.1 Single ambiguous field

If one field is ambiguous:

- ask only about that field
- show the raw phrase
- show the candidate normalized interpretation
- explain why clarification is needed

### 11.2 Multiple ambiguous fields

If multiple fields are ambiguous:

- use a grouped clarification message
- clarify only the ambiguous fields
- do not restate the whole strategy unless the entire request is too unstable to trust

This is the V1 product decision because asking one field at a time is too slow and too rigid for normal users.

### 11.3 Backend clarification contract

For grouped ambiguity, the backend should return:

- one concise clarification prompt
- `ambiguous_fields`

Each `ambiguous_fields` item includes:

- `field_name`
- `raw_value`
- `candidate_normalized_value`
- `reason_code`

This preserves transparency while giving the frontend structured data for low-friction interaction.

## 12. Interaction With `Interpret`

`Interpret` should use the extractor output as input to its existing decision policy.

It should:

- combine deterministic signals and extracted strategy fields
- determine whether required fields are `resolved`, `missing`, `ambiguous`, or `unsupported`
- use field status rather than free-form confidence to decide the next action
- preserve `strategy_thesis` when the user’s request is recognizable but incomplete
- block `Confirm` when unsupported constraints are present
- route to grouped clarification when multiple fields are ambiguous

This keeps `Interpret` as the decision boundary rather than turning the extractor into a second orchestrator.

## 13. Product Behavior

This slice is successful if it improves the experience for a normal user trying to test an investing idea through conversation.

That means:

- users can say `buy`, `sell`, `close`, and similar natural language without keyword-perfect phrasing
- Argus remains explicit about what it understood
- unsupported requests are surfaced before confirmation, not silently ignored
- clarification remains targeted and low-friction
- confirmation remains trustworthy

The product standard is not “did the model extract something.”
The product standard is:

`Does this make it easier for a normal person to test an investing idea through conversation?`

## 14. V2 Notes

This V1 spec intentionally avoids over-engineering.

Future versions may add:

- context-adaptive extraction based on user corrections
- two-step extraction (`raw intent -> support mapping`) if single-pass extraction proves too lossy
- fast-model first, heavier-model escalation for especially complex requests
- richer ambiguity handling if grouped clarification is not enough

Those are valid future directions, but not part of this implementation slice.
