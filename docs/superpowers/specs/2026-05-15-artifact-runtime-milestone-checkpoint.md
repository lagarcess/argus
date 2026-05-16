# Artifact Runtime Milestone Checkpoint

**Date:** 2026-05-15
**Branch:** `codex/artifact-runtime-rebuild`
**Parent spec:** [2026-05-13 Artifact Runtime Production Readiness Second Pass](./2026-05-13-artifact-runtime-production-readiness-second-pass.md)
**Purpose:** Milestone state for branching other app work from this runtime checkpoint and later merging back without losing the truth of what is fully proven, partially proven, or still pending.

## Executive State

This checkpoint is not "production ready" yet, but it is a materially stronger artifact-runtime baseline than the earlier broken state.

The main improvement is that Argus now has a clearer artifact spine:

- normal language reaches the LLM-first interpreter,
- capability and launch validation decide what can execute,
- visible cards own their own action payloads,
- quota-bearing execution happens through card actions,
- completed results become immutable facts,
- result actions operate on concrete run ids,
- refinement forks a new draft from the prior snapshot instead of mutating completed evidence.

The remaining release risk is not a single bug. It is proof coverage: the full live browser QA matrix still needs to be completed across non-deterministic human prompts, reloads, action clicks, and correct failures.

## Decision Rules For Future Branches

When merging other work back into this branch, preserve these rules:

- Do not create a second chat orchestrator.
- Do not bypass the LLM-first interpreter with phrase/regex routing.
- Do not let frontend prose invent strategy, result, or action context.
- Do not let a visible `Run backtest` button depend on reinterpretation.
- Do not mutate completed result artifacts when refining.
- Do not mark a card `Ready to run` unless the launch payload is validated.
- Do not execute quota-bearing backtests from typed natural language approval; guide the user to the card action.
- Do not advertise indicators or strategies as executable unless they have registry, compiler, launch, engine, result, and browser evidence.

## Fully Completed Or Proved

### Artifact Lifecycle Contract

Status: fully proved for the covered paths.

What should pass:

- One active confirmation artifact owns one visible card state.
- Older confirmations become superseded or terminal history.
- Cancel creates a durable non-runnable tombstone.
- Reload does not reactivate cancelled or superseded cards.
- Result refinement forks a new active draft from immutable run facts.

Evidence:

- Browser QA showed cancelled confirmation cards hydrate as `Draft canceled`, without runnable actions or noisy cancel transcripts.
- Browser DOM showed a completed `AAPL Buy and Hold` result, `Refine strategy`, the user refinement, a new `AAPL recurring buys` artifact, and a separate completed `DCA Accumulation` result.
- Tests:
  - `poetry run pytest tests/test_chat_runtime_reload_guardrails.py::test_refine_strategy_action_uses_latest_result_context_after_reload tests/test_chat_runtime_reload_guardrails.py::test_refine_strategy_text_reply_uses_persisted_refinement_context_after_reload tests/test_chat_runtime_reload_guardrails.py::test_refine_strategy_action_uses_card_run_before_runtime_memory -q --tb=short`
  - `poetry run pytest tests/test_chat_runtime_reload_guardrails.py::test_cancel_confirmation_action_persists_invisible_artifact_tombstone tests/test_chat_runtime_reload_guardrails.py::test_canceled_confirmation_does_not_recover_older_card -q --tb=short`

### Result Card Core Actions

Status: fully proved for `Run backtest`, `Show a breakdown`, `Save strategy`, and `Refine strategy`.

What should pass:

- `Run backtest` executes from the card payload.
- `Show a breakdown` adds one breakdown response and does not duplicate the result card.
- `Save strategy` shows a clear saved state and is idempotent.
- `Refine strategy` prompts for the desired change using the result run snapshot.
- Result actions remain sane after reload.

Evidence:

- Browser-clicked result lifecycle showed one result card, one breakdown, visible saved state, and a refine prompt that did not lose run context.
- Frontend tests:
  - `cd web && bun test __tests__/alpha-frontend.test.ts __tests__/chat-artifact-history.test.ts`
  - Result: `53 pass`.

### Result Follow-Up Grounding

Status: fully proved for covered result questions.

What should pass:

- `What exactly did you test?` answers from run facts.
- Max drawdown questions answer from run facts.
- False premises are corrected when the result outperformed.
- Follow-ups after reload still use the latest result.
- Answers do not merely repeat card metrics; they explain what the metric means.

Evidence:

- Browser QA on NVDA and TSLA result follow-ups showed latest run facts, benchmark, gap, max drawdown, and caveat after reload.
- Tests:
  - `poetry run pytest tests/agent_runtime/test_interpret_stage.py::test_underperformance_followup_corrects_false_premise_when_run_outperformed tests/agent_runtime/test_result_followups.py::test_result_followup_replaces_llm_answer_that_contradicts_positive_delta -q --tb=short`

### Confirmation Action Reliability

Status: fully proved for covered card-owned run paths.

What should pass:

- A visible `Run backtest` action executes from the visible card payload.
- Reload before running does not make the visible card unusable.
- Typed "yes run it" does not execute a quota-bearing backtest.
- Stale runtime memory cannot outrank the card action payload.

Evidence:

- Browser QA showed typed `yes run it` responded by directing the user to the card button.
- Browser-clicked `Run backtest` produced result cards instead of model reinterpretation failures.
- Tests:
  - `poetry run pytest tests/test_chat_runtime_reload_guardrails.py::test_refine_strategy_action_uses_card_run_before_runtime_memory -q --tb=short`

### Capability Truth Foundation

Status: fully proved for the current supported surface.

What should pass:

- Capability answers come from registry/provider/compiler truth, not stale LLM prose.
- Unsupported or draft-only ideas preserve context and offer executable alternatives.
- Executable indicators support defaults and user overrides.
- Unknown future strategy families are not forced into old labels.

Evidence:

- Browser `@` discovery showed assets and indicators, including supported and draft-only capability status.
- Runtime tests prove unknown rule specs do not become executable signal strategies.
- Tests:
  - `poetry run pytest tests/agent_runtime/test_strategy_contract.py::test_extracted_fields_do_not_force_unknown_strategy_contract tests/agent_runtime/test_strategy_contract.py::test_extracted_fields_do_not_accept_unknown_rule_spec_as_signal_strategy tests/agent_runtime/test_strategy_contract.py::test_extracted_fields_resolve_indicator_threshold_from_registry -q --tb=short`
  - `poetry run pytest tests/domain/test_indicator_registry.py tests/domain/test_engine_launch.py::test_indicator_threshold_adapter_returns_envelope_card_and_context tests/domain/test_engine_launch.py::test_adapter_accepts_registry_bounded_indicator_threshold_shape tests/domain/test_engine_launch.py::test_adapter_uses_indicator_period_from_threshold_rules tests/domain/test_engine_launch.py::test_adapter_maps_common_crossover_payload_to_rule_spec tests/domain/test_engine_launch.py::test_build_signals_preserves_rule_template_branches_after_rsi -q --tb=short`

### Lightweight Evaluation Spine

Status: fully scaffolded, not yet a full evaluator platform.

What should pass:

- The scenario manifest covers the eight workstreams.
- The manifest covers the live browser QA matrix.
- Must-pass scenarios define hard checks separate from LLM-judge quality checks.

Evidence:

- `tests/evals/chat_runtime_scenarios.json`
- `poetry run pytest tests/evals/test_chat_runtime_eval_manifest.py -q --tb=short`
- Result: `3 passed`.

## Partially Completed

### Draft Continuity

Status: partially proved.

What currently works:

- Asset edits preserve prior strategy/date context.
- Date edits preserve prior asset/strategy context.
- Result refinement preserves prior result context and forks a new draft.
- Assumption questions can answer from visible artifact context.

What still needs proof:

- Full live browser matrix for asset/date/assumption edits across varied human phrasing.
- Reload proof for every edit state, including mid-edit states and stale-action recovery.
- Spanish variants of the same continuity patterns.

### Natural Retry Recovery

Status: automated coverage exists; live browser proof still pending.

What currently works in tests:

- Failed action payloads persist retry context.
- Natural retry rebuilds a confirmation instead of auto-running quota-bearing work.
- Reload can recover the failed-action reference.
- Newer completed results supersede stale failed-action context.

What still needs proof:

- A clean live browser failed-action scenario.
- Reload after failure.
- User phrases like "try again" and "no, run the same one" recovering without asking for assets again.

### Trust Polish

Status: partially implemented, insufficient browser proof.

What currently works in code/tests:

- Stream status hides once assistant tokens exist.
- Feedback/copy controls are guarded by final answer state.
- Composer-level artifact actions are hidden when a card owns actions.

What still needs proof:

- Desktop and mobile live scroll behavior.
- Copy success/failure feedback in the browser.
- No scroll yanking during streaming.
- Controls do not appear before answer completion.

### Browser QA Evidence

Status: strong partial evidence, not full release evidence.

What currently exists:

- Live DOM inspection.
- Browser reload proof.
- Browser card clicks.
- API-seeded setup for flows where Codex browser text entry was blocked.

What still needs proof:

- Full prompt-by-prompt live browser matrix without relying on API seeding.
- Screenshots or transcripts for every must-pass scenario.
- Correct failures recorded as passing when they preserve capability truth.

### Broader Indicator And Strategy Support

Status: directionally aligned but not complete.

What currently works:

- Supported indicators are registry-backed.
- Defaults and user overrides can flow through executable indicator rules.
- Some SMA/EMA/RSI-style rule paths are executable.
- DCA cadence support includes biweekly and quarterly paths in the shared cadence surface.

What still needs proof:

- Full schema-driven pandas-ta expansion.
- Execution specs for every indicator advertised as executable.
- Clear draft-only behavior for indicators that are searchable but not executable.
- Non-template strategy IR that can grow into future sentiment and multi-signal strategies.

## Still Pending Before Release-Grade Completion

These are the high-signal pending items from the parent spec.

1. Full release-grade live browser QA matrix across the scenario manifest.
2. Change asset and adjust assumptions full browser proof.
3. Spanish smoke QA.
4. Mixed/provider asset resolution browser proof.
5. Natural retry recovery browser proof.
6. Trust polish desktop/mobile browser proof.
7. Production-grade evaluator beyond the manifest: trajectory checks, state verification, artifact/action checks, and LLM-judge answer quality.
8. Deeper modular cleanup of large runtime/interpreter files where responsibilities remain bundled.

## Non-Deterministic Live Browser QA Playbook

Use this playbook when continuing the checkpoint. The point is not to prove one exact phrase. The point is to sample realistic human behavior and verify the artifact contract survives.

### For Every Scenario Capture

- Prompt or action.
- Visible card state.
- Final assistant answer.
- Persisted artifact/action context if inspectable.
- What happens after reload.
- Whether the failure, if any, is correct and helpful.

### Must-Pass Human Variants

Use natural variants, not only template prompts:

- "i just wanna know if microsoft beat spy last year if i simply held it"
- "same thing but nvidia"
- "make the window six months"
- "what did you assume here?"
- "yes run it"
- "try again"
- "no, run the same one"
- "what if i bought tesla after big drops?"
- "use RSI below 20 and sell above 60"
- "what exactly did you test?"
- "why did this happen?"
- "what should i try next?"
- "do recurring buys every two weeks with 500 bucks instead"

### Required Browser Outcomes

- Argus keeps the active draft alive across edits.
- Argus does not overstate unsupported execution.
- Argus only runs a backtest from a card action.
- Argus can use latest result facts in follow-ups.
- Argus recovers from failure without asking for everything again.
- Result actions are card-owned, reload-safe, and non-duplicative.
- UI state does not make the user doubt whether the answer/action is complete.

### Correct Failures

These should count as pass cases when phrased clearly:

- Unsupported mixed asset classes.
- Unsupported indicator confluence without an execution spec.
- Provider/catalog unavailable in live mode.
- Date range unavailable for a provider/instrument.
- Missing required DCA contribution amount.
- Quota/paywall gate once billing exists.

## Merge-Back Checklist

Before merging another branch back into this checkpoint, verify:

- The parent spec link still represents the current runtime goal.
- `tests/evals/chat_runtime_scenarios.json` still covers all eight workstreams.
- New UI surfaces do not duplicate card actions.
- New backend behavior does not bypass the LLM-first interpreter.
- New strategy/indicator/provider work plugs into registry, compiler, launch, and artifact surfaces.
- Browser QA still passes the golden path: natural prompt -> confirmation card -> card run -> result card -> follow-up -> reload.
- Any failing must-pass scenario is either fixed or explicitly marked as a blocker.

## Quick Deterministic Gates For This Checkpoint

These are supporting evidence, not the release gate:

```bash
poetry run pytest tests/evals/test_chat_runtime_eval_manifest.py -q --tb=short
poetry run pytest tests/agent_runtime/test_interpret_stage.py::test_result_refinement_reply_forks_latest_result_into_new_draft tests/test_chat_runtime_reload_guardrails.py::test_refine_strategy_action_uses_latest_result_context_after_reload tests/test_chat_runtime_reload_guardrails.py::test_refine_strategy_text_reply_uses_persisted_refinement_context_after_reload tests/test_chat_runtime_reload_guardrails.py::test_refine_strategy_action_uses_card_run_before_runtime_memory -q --tb=short
cd web && bun test __tests__/alpha-frontend.test.ts __tests__/chat-artifact-history.test.ts
```

## Final Checkpoint Truth

This branch is a usable artifact-runtime checkpoint for parallel app work, but it should not be treated as final production readiness until the remaining browser QA matrix and evaluation harness are completed.

The product direction is correct when new features plug into the same spine:

natural language -> LLM interpretation -> capability validation -> artifact -> card-owned action -> engine/result facts -> follow-up/reload.

If a future change cannot fit that spine, stop and redesign before merging it back.
