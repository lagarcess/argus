# Artifact-Centered Runtime Rebuild Scope

NOTE: Historical context. This document is retained as implementation evidence and is not the current execution source of truth.

**Date:** 2026-05-13  
**Status:** Draft scope for user review  
**Branch context:** `codex/backtesting-chat-service-modularization`  
**Primary evidence:** Live browser QA of the seven chat/runtime segments plus screenshots 1, 2, 4, and 5.

## TL;DR

This update is not an indicator patch. It is a production-readiness rebuild of Argus's conversation artifact spine, with broader indicator execution as one downstream capability.

The highest-priority problem from live browser QA is that Argus can show visible drafts, cards, results, and actions, but the runtime does not consistently treat those artifacts as canonical truth across refinement, execution, reload, retry, follow-up, save, and copy flows.

The rebuild should make Argus artifact-centered:

- Strategy drafts are durable.
- Confirmation cards are executable artifacts.
- Result cards are canonical fact sources.
- Visible actions operate on artifact IDs.
- Reload preserves meaning.
- Follow-up answers use actual run facts.
- Indicator strategies compile into executable signal rules instead of one-off templates.

## Canon Drift Stop Rule

The canon docs govern this update:

- `docs/PRODUCT.md`
- `docs/ARCHITECTURE.md`
- `docs/API_CONTRACT.md`
- `docs/DATA_MODEL.md`
- `.agent/designs/argus/DESIGN.md`

If any task requires changing Argus's product philosophy, chat-first direction, active runtime ownership, persistence boundary, SSE contract, data authority, same-asset execution rule, or design-system trust principles, implementation must stop and consult the user before proceeding.

This update should reinforce the canon. It must not quietly replace it.

## Priority Order

1. **Conversation Artifact Spine**
   - Preserve the active draft across edits.
   - Keep visible confirmation/result context authoritative.
   - Stop reinterpreting visible cards from scratch.
   - Prevent reload from changing assistant meaning or action state.

2. **Result Intelligence**
   - Result follow-ups must answer from canonical run facts.
   - Questions like "why did it underperform?", "what was max drawdown?", "what exactly did you test?", and "what should I try next?" must use the latest run artifact.

3. **Action Reliability**
   - `Run backtest`, `Show breakdown`, `Save strategy`, `Refine strategy`, and retry flows must operate from structured artifact/run context.
   - A visible valid action should not fail because the interpreter lacks context.
   - Saved state must survive reload.

4. **Recovery**
   - "Try again" and "run the same one" should bind to the latest failed action or visible draft/result.
   - Recovery must continue the thread, not restart from blank.

5. **Executable Strategy Expansion**
   - Replace one-off RSI handling with a registry-backed signal compiler.
   - Support trading-rule indicators through thresholds, crossovers, price-vs-indicator, indicator-vs-indicator, and simple `AND` / `OR`.

6. **Trust Polish**
   - Copy controls must copy the correct assistant content and show feedback.
   - Streaming/status/action controls should not make the user doubt whether a response is complete.

## Live Browser QA Evidence

### 1. Pending-Strategy Refinement

Observed:

- Apple did not reliably resolve to AAPL.
- Once NVDA existed, refinement preserved NVDA and date changes.
- "What assumptions are you using?" regenerated a card instead of answering from the visible card.
- Reload changed earlier assistant wording.

Required behavior:

- Active draft remains alive across edits.
- Assumption questions answer from the active draft/confirmation artifact.
- Reload preserves exact persisted assistant meaning and card state.

### 2. Unsupported Request Recovery

Observed:

- MA crossover recovery was directionally good but wording changed after reload.
- RSI simplification preserved NVDA.
- RSI(14) over two weeks produced a `Ready to run` card, then failed with literal `unsupported_indicator`.

Required behavior:

- Unsupported ideas are understood, preserved, and explained.
- Cards must not say `Ready to run` unless deterministic validation passes.
- Indicator validation must include warmup/data sufficiency.

### 3. Confirmation Action Reliability

Observed:

- Ticker-based TSLA card survived reload and ran.
- Natural-language "Tesla" often asked for clarification instead of resolving TSLA.

Required behavior:

- Asset resolver should use the same provider/catalog truth available to composer search.
- Confirmation actions execute from confirmation artifact IDs, not fresh natural-language interpretation.

### 4. Natural Retry Recovery

Observed:

- After failed RSI execution, "Can you try again?" did not retry.
- "No, run the same one" drifted back to the unsupported MA idea.

Required behavior:

- Latest failed action/result becomes a durable failed artifact.
- Retry language maps to the failed artifact unless the user explicitly changes it.

### 5. Result Follow-Up Depth

Observed:

- "Why did it underperform?" repeated the readout.
- "What was max drawdown?" said unavailable while the card showed drawdown.
- After reload, result follow-up context degraded.

Required behavior:

- Latest run fact bank is injected into follow-up interpretation/explanation.
- Result answers use canonical metrics, config snapshot, benchmark, assumptions, and chart/trade facts.

### 6. Result Card Actions

Observed:

- Fresh `Show breakdown` worked.
- After follow-ups/reload, actions became inconsistent.
- `Save strategy` posted a message but result card still looked unsaved after reload.

Required behavior:

- Result actions remain attached to the result artifact.
- Save is idempotent and visibly mutates saved state.
- Breakdown does not duplicate result cards.

### 7. Trust Polish

Observed:

- Copy control copied the user prompt instead of assistant answer.
- No visible copy confirmation.

Required behavior:

- Copy controls are scoped to the exact assistant message/card.
- Copy success/failure is visible and accessible.

## Screenshot Regression Batch

Screenshots 1, 2, 4, and 5 belong in this same update:

- NVDA MA crossover to RSI simplification to insufficient warmup failure.
- MSFT duplicated/repeated readout and poor result follow-up.
- Visible context/action mismatch around breakdown and latest result.
- Repeated clarification despite visible conversation context.

Screenshot 3, ETH/BTC comparison, remains a targeted repro item. It may belong here if it proves to be artifact/context loss, or it may become a separate crypto comparison/same-asset validation issue.

## Architecture Direction

### Artifact Model

Argus should treat chat as a sequence of durable artifacts:

- `strategy_draft`
- `confirmation`
- `backtest_run`
- `result_review`
- `failed_action`
- `saved_strategy`

Each artifact needs:

- Stable ID.
- Conversation ID.
- Type.
- Status.
- Canonical payload.
- Visible presentation snapshot.
- Available actions.
- Supersession rules.
- Reload hydration behavior.

### Runtime Rule

Normal user text remains LLM-first.

Deterministic code owns:

- Artifact selection.
- Artifact patching.
- Capability validation.
- Asset/provider validation.
- Same-asset-class enforcement.
- Indicator registry validation.
- Warmup/data validation.
- Action authorization.
- Result fact retrieval.
- SSE shape and persistence.

The LLM should interpret and explain, but it must not invent executable capability, result metrics, or hidden card context.

### State Rule

`TaskSnapshot` should continue storing only non-derivable runtime state, but the runtime must consistently carry artifact references:

- Active draft reference.
- Active confirmation reference.
- Latest completed result reference.
- Latest failed action reference.
- Saved strategy reference when applicable.

Message metadata and `backtest_runs.config_snapshot` remain the durable reload fallback. LangGraph checkpoint remains the runtime memory source when present.

## Engine Direction

Indicator expansion is a subsystem, not the headline.

Build a generic signal rule compiler over the existing long-only engine path:

- Input: normalized `rule_spec`.
- Output: `entries` and `exits` boolean series.
- Execution: existing vectorbt `from_signals` path.
- Validation: indicator params, output columns, data availability, warmup bars, same asset class, timeframe limits.

Supported v1 rule patterns:

- Thresholds: RSI below 30, MFI above 80.
- Crossovers: SMA 50 crosses above SMA 200, MACD crosses signal.
- Price vs indicator: close above EMA 200, close below VWAP.
- Indicator vs indicator: Stoch K crosses D.
- Volume confirmation: volume above volume SMA.
- Simple groups: entry when A AND B; exit when C OR D.

Explicitly out of scope for this rebuild:

- Shorting.
- Leverage/margin.
- Pair trading/spreads.
- Portfolio ranking/rotation.
- Multi-timeframe rules.
- Stop loss, trailing stop, take profit, partial exits.
- Arbitrary formulas or user code.
- Reviving archive-v0.1 builder UI.

## Archive-v0.1 Salvage Policy

Use archive-v0.1 only as reference material.

Salvage concepts:

- Criteria arrays.
- `indicator_a` / `indicator_b` comparisons.
- `cross_above`, `cross_below`, `gt`, `lt`.
- Dynamic pandas-ta resolution ideas.
- Indicator metadata categories.
- Builder tests as examples of user strategy flexibility.

Do not copy:

- Monolithic `ArgusEngine`.
- Pattern/harmonic detours.
- Execution Forge / slippage realism scope.
- Old API payloads wholesale.
- Old frontend builder UX.
- Dormant brittle tests unless rewritten around current canon.

## Implementation Shape

Keep the modular monolith clean. Do not create another oversized script.

Recommended subsystem boundaries:

- `domain/indicators/*`
  - Registry, specs, aliases, output selectors, warmup rules.

- `domain/backtesting/rules/*`
  - Rule models, series references, operators, condition groups, validation.

- `domain/backtesting/signals.py`
  - Thin compatibility wrapper that delegates signal strategy compilation.

- `domain/engine_launch/*`
  - Launch request normalization and envelope building.

- `agent_runtime/*`
  - LLM interpretation, artifact patching, action routing, and result fact injection.

- `api/chat/*`
  - Persistence, recovery, action handling, result breakdown/save behavior.

- `web/components/chat/*`
  - Hydration, card/action rendering, copy controls, saved state.

## Public Contract Changes

Add or extend structured metadata with:

- `artifact_id`
- `artifact_type`
- `artifact_status`
- `active_artifact_id`
- `supersedes_artifact_id`
- `rule_spec`
- `validation_state`
- `saved_strategy_id`
- `failed_action`
- `result_fact_bank`

Extend strategy execution payloads to support:

- `strategy_type: "signal_strategy"`
- `entry_rule_group`
- `exit_rule_group`
- `indicator_parameters`
- `assumptions`
- `validation_warnings`

Keep backward compatibility for:

- `buy_and_hold`
- `dca_accumulation`
- existing `indicator_threshold` payloads, mapped into `signal_strategy`.

## Acceptance Criteria

The update is not complete until live browser QA proves:

- Draft edits preserve the active strategy.
- "What assumptions?" answers from the visible draft/card.
- Unsupported ideas are preserved and recovered with executable alternatives.
- No card says `Ready to run` if the engine cannot execute it.
- `Run backtest` works after reload when a valid card is visible.
- Retry binds to the latest failed action.
- Result follow-ups answer from canonical metrics.
- `Show breakdown` does not duplicate result cards.
- `Save strategy` visibly persists saved state after reload.
- Copy copies the correct assistant content and shows feedback.
- Assistant message text does not morph after reload.
- PR 80/81 SSE and hydration guardrails remain passing.

## Test Strategy

Backend:

- Indicator registry unit tests.
- Rule compiler unit tests.
- Engine integration tests with synthetic OHLCV.
- Warmup/data sufficiency tests.
- Artifact selection and recovery tests.
- Result fact-bank follow-up tests.
- Save/breakdown idempotency tests.
- PR 80/81 stream/reload guardrail tests.

Frontend:

- Hydrated confirmation card actions.
- Hydrated result card actions.
- Saved-state rendering.
- Copy scoping.
- No action clearing from historical result cards.
- Reload equivalence.

Browser QA:

- Re-run the seven validated scripts.
- Re-run screenshots 1, 2, 4, and 5 scenarios.
- Add targeted ETH/BTC comparison repro for screenshot 3.
- Validate no console errors and no silent action failures.

## Verification Note

Current backend tests may require a stable `NUMBA_CACHE_DIR` because vectorbt import can fail under Python 3.14 with a Numba cache locator error. Implementation work should fix or standardize this before relying on engine test results.

## Non-Negotiables

- Do not restore a legacy orchestrator.
- Do not add regex NLU gates before the LLM.
- Do not weaken PR 80/81 tests to make regressions pass.
- Do not move chat hydration casually out of the protected flow.
- Do not copy archive-v0.1 code wholesale.
- Do not let visible UI state and backend artifact state disagree.
- Do not claim support for indicators or strategies until deterministic validation proves execution is possible.

