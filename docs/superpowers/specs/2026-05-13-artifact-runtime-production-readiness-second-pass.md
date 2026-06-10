# Artifact Runtime Production Readiness Second Pass

NOTE: Historical context. This document is retained as implementation evidence and is not the current execution source of truth.

**Date:** 2026-05-13
**Status:** Draft for user review
**Branch:** `codex/artifact-runtime-rebuild`
**Origin branch:** `codex/backtesting-chat-service-modularization`
**Reason for second pass:** Live browser QA contradicted the first-pass confidence. The app can still render cards and actions that are not backed by a canonical executable artifact, and several capability, retry, save, and follow-up behaviors remain below production readiness.
**Directional update:** 2026-05-15
**Milestone checkpoint:** [2026-05-15 Artifact Runtime Milestone Checkpoint](./2026-05-15-artifact-runtime-milestone-checkpoint.md)

## Executive Truth

The first pass moved in the right direction but did not finish the product problem.

The production problem is not "fix one RSI case," "add one more strategy mapping," or "hide a duplicate chip." The production problem is that Argus still allows four different things to drift apart:

1. The visible conversation artifact.
2. The persisted message metadata.
3. The executable launch payload.
4. The engine and provider capability truth.

This second pass exists to make those four things one coherent runtime contract.

The runtime contract must be based on a canonical investing-idea intent and rule representation, not on strategy-name branches. `buy_and_hold`, `dca_accumulation`, `indicator_threshold`, `signal_strategy`, and future labels such as sentiment strategies may remain useful for display, analytics, saved-strategy organization, and engine adapters. They are not the conversational contract. Normal user language should become structured intent, conditions, schedules, sizing, exits, provider requirements, and assumptions first; strategy family names are derived metadata at the edge.

The release standard is live browser QA. Automated tests are supporting evidence only. A test suite that passes while the browser shows duplicate action chips, raw `missing_rule_group`, stale retries, or false capability claims is not sufficient.

## Most Important Missing Question

The question that can prevent this from reaching production grade is:

**What is the smallest end-to-end production slice that proves the architecture, and in what order do we expand it without breaking live chat?**

Without this question, the spec can become a big-bang rewrite: artifact spine, provider catalogs, pandas-ta schemas, rule compiler, result intelligence, UI action cleanup, and localization all moving at once. That is how previous attempts created many changed files without product confidence.

The answer is sequential vertical slices:

1. Prove the artifact/action spine with existing buy-and-hold and current runnable indicator paths.
2. Remove duplicate action surfaces and enforce `Ready to run` validation.
3. Prove reload, retry, save, breakdown, and result follow-up on that spine.
4. Add the capability planner contract so creative language becomes truthful next moves instead of rigid yes/no validation.
5. Add provider-backed asset/catalog truth through the same capability interface.
6. Add schema-driven pandas-ta support family by family through the rule compiler.
7. Expand live browser QA only when the prior slice remains passing.

Each slice must leave the app usable in the browser. No slice is allowed to make the core happy path worse while waiting for a later slice to fix it.

## Five Recommended Next Moves

These are the next execution moves for the current branch. They are intentionally vertical and evidence-driven.

1. **Freeze the evaluation spine before more behavior changes.**
   - Convert the eight buckets and browser QA matrix into a small scenario manifest plus browser scripts.
   - Capture prompt/action, visible artifact state, final answer, persisted metadata expectations, reload behavior, and pass/fail.
   - Use this to prevent another "tests pass, browser fails" cycle.

2. **Close the artifact/action runtime contract.**
   - One active artifact owns one validated payload and one action set.
   - Card actions must be functional, scoped, idempotent where appropriate, and reload-safe.
   - Typed text that means "run it" should guide the user to the quota-bearing button; only card actions execute backtests.

3. **Replace strategy-template thinking with canonical intent/rule IR.**
   - The LLM extracts what the user wants in a flexible schema: universe, time window, entry/exit conditions, schedules, sizing, parameters, assumptions, and unsupported context.
   - The capability planner validates whether that intent can become an executable artifact, needs clarification, needs repair, remains draft-only, or should become an answer-only turn.
   - Strategy family names become derived display/compiler labels, not routing truth.

4. **Unify provider and capability truth.**
   - Composer search, chat interpretation, capability Q&A, artifact validation, and engine launch must use the same asset resolver, indicator registry, provider-mode contract, and rule compiler.
   - Recorded fixtures are provider-shaped snapshots through the same interfaces, not a mock brain.

5. **Run release-grade live browser QA and publish evidence.**
   - The branch is not complete until the browser matrix passes against the implemented runtime.
   - Evidence must include correct failures, not only happy paths.
   - Any raw internal code, stale artifact action, false capability claim, lost draft context, or detached result follow-up blocks completion.

## Definition Of Full Functionality For This Pass

Full functionality does not mean Argus pretends to support every possible trading idea. It means every feature Argus advertises as supported is complete across the full product path:

1. Natural language interpretation.
2. Deterministic capability validation.
3. Confirmation artifact.
4. Executable payload.
5. Engine execution.
6. Result artifact.
7. Follow-up explanation.
8. Reload hydration.
9. Action retry/save/breakdown lifecycle.
10. Live browser QA.

For indicators, this means every indicator marked `executable` must work end to end through that path. Indicators that do not meet that bar can still be searchable or draftable, but Argus must say so clearly and must not offer them as runnable.

## Macro Pattern Mandate

This pass must unlock reusable product capability, not patch individual phrases.

The implementation should build macro patterns:

- artifact-centered action lifecycle,
- provider-backed asset capability,
- schema-driven indicator capability,
- normalized rule grammar,
- deterministic execution validation,
- result fact-bank follow-up,
- fixture-backed mock parity,
- card-scoped UI actions.

Every bug fix must answer: which reusable product pattern failed?

Examples:

- Bad: special-case `"starts rising"` into a 50/200 crossover.
- Good: classify `"starts rising"` as incomplete momentum semantics and route it through rule-definition clarification.
- Bad: add a regex that turns `"simplify to RSI"` into NVDA RSI only for that prompt.
- Good: plan an artifact edit that applies a new indicator family while preserving asset/date context through the artifact-edit pipeline.
- Bad: hardcode `Apple -> AAPL` in chat.
- Good: resolve Apple through the provider-backed asset catalog used by chat and composer search.
- Bad: add another composer chip condition to hide one duplicate button.
- Good: enforce the invariant that active artifact actions render only inside the artifact card.

If a proposed fix does not improve a reusable macro pattern, it should not be accepted in this production pass.

## Capability Planner Loophole

The current plan has one dangerous loophole: capability validation can become a rigid yes/no gate.

That would still fail the product philosophy. Argus should not merely reject creative user language. It should translate creative language into the nearest truthful executable plan, ask only the questions that change execution, and preserve unsupported parts as draft context when needed.

The missing layer is a capability planner.

The planner sits after LLM interpretation and before confirmation artifacts. It does not replace the LLM, the rule compiler, or the guardrails. It coordinates them.

Inputs:

- latest user message,
- structured LLM interpretation,
- canonical investing-idea intent and rule IR,
- active artifact, if any,
- provider-backed asset candidates,
- schema-driven indicator definitions,
- rule grammar and executable patterns,
- provider data-window availability,
- latest run or failed-action context when relevant.

Outputs:

- understood intent,
- normalized IR edit or replacement,
- relationship to active artifact (`new_idea`, `edit_existing`, `answer_question`, `retry_failed_action`, `result_follow_up`),
- resolved assets or ranked asset candidates,
- indicator and rule candidates,
- default parameters applied,
- user-specified parameter overrides,
- missing semantics that truly affect execution,
- executable status,
- draft/search-only status when applicable,
- repair options,
- user-facing explanation,
- artifact edit or executable launch payload.

The planner should produce one of these outcomes:

- `ready_to_confirm`: the idea has enough validated structure to show a ready confirmation card.
- `needs_clarification`: the user must choose between materially different executable meanings.
- `needs_repair`: the idea is clear but blocked by data window, warmup, provider availability, or a stale artifact.
- `draft_only`: Argus understands the idea but cannot execute it yet.
- `answer_only`: the user asked a capability, assumption, result, education, or casual-chat question.
- `unsupported_with_alternatives`: the idea cannot run, but Argus can preserve it and offer executable alternatives.

This is how the system remains flexible:

- The LLM remains the natural-language brain.
- The canonical IR captures user intent without collapsing it into a legacy strategy template.
- The planner turns ambiguous language into structured next moves.
- The capability registry tells the truth.
- The rule compiler only compiles complete executable rules.
- Artifacts store the visible, durable contract.

Planner rules:

- Do not guess entry or exit semantics when the choice materially changes the test.
- Do not ask for fields already available from the active artifact unless the user changed them.
- Do not show `Ready to run` until the planner has a validated launch payload.
- Do not collapse creative language into one default template unless the user phrase clearly implies that template.
- Preserve unsupported parts as draft notes instead of discarding them.
- Offer executable completions, not generic "try again" language.
- Treat strategy family names as derived labels or compiler macros, not as the primary routing contract.

Examples:

- "SPY when it starts rising" -> `needs_clarification` with executable definitions: percent move, close above moving average, moving average crossover, or RSI momentum.
- "Tesla after big drops... RSI 20/60" -> `ready_to_confirm` if RSI thresholds compile and data window is feasible.
- "Bitcoin MACD bullish and volume jumps" -> `ready_to_confirm` only if MACD and volume confirmation are both executable; otherwise `draft_only` or `unsupported_with_alternatives` with the runnable subset clearly named.
- "Actually make it Nvidia" -> `patch_existing` preserving strategy, date range, defaults, and assumptions.
- "Try again" after a failed run -> `retry_failed_action` or `needs_repair`, not `new_idea`.

Without this planner, the implementation will likely break in one of two ways:

- too permissive: polished cards claim capabilities the engine cannot execute,
- too rigid: Argus blocks creative language with excessive clarifications and loses conversational flow.

## Supersession Note

This spec supersedes any prior plan or QA note that marks the artifact runtime work as broadly passing when live browser QA shows otherwise.

In particular, any evidence doc that says result actions, retry, trust polish, or unsupported/capability handling are passing must be treated as stale unless it is backed by a fresh browser run on this second-pass implementation.

## Anti-Patterns To Avoid

The implementation must actively avoid these patterns:

- **Big-bang rewrite:** touching artifact runtime, indicator engine, asset providers, UI layout, and result intelligence in one unverified sweep.
- **Template creep:** adding one more hardcoded strategy template whenever a user phrase fails.
- **Prompt as source of truth:** updating LLM copy to claim capability that the engine/provider registry cannot execute.
- **Display-first artifacts:** rendering a polished card before executable payload validation succeeds.
- **Frontend reconstruction:** rebuilding strategy/run context from visible text, card labels, or local component state.
- **Mock divergence:** making mock mode pass with shortcuts that production resolver/provider paths do not use.
- **Catch-all modules:** hiding multiple concerns in `utils`, `helpers`, large stage files, or bloated React components.
- **Test normalization:** changing tests to accept broken browser behavior instead of using tests to guard the canonical contract.
- **Silent degradation:** allowing reload to change wording, action state, result context, or saved state.
- **Scope laundering:** using "production readiness" to quietly add excluded product scope such as shorting, leverage, arbitrary formulas, or mixed-asset execution.

## Canonical Decision Filters

Every implementation decision in this pass must satisfy these filters before code is written.

### Product Filter

Does this help a normal person speak an investing idea, understand what Argus can test, run it safely, and continue the conversation with confidence?

If not, it waits.

### Architecture Filter

Does this preserve the LangGraph runtime as the single active chat brain, keep FastAPI routers thin, and keep Supabase product records as durable truth?

If not, stop and consult the user.

### API Contract Filter

Is every executable artifact represented through documented structured payloads and additive metadata, without breaking existing clients?

If not, update the implementation design or stop and consult the user before changing canon.

### Data Model Filter

Can completed results and saved strategies be reproduced from canonical run/config state, not frontend prose?

If not, the design is not production ready.

### Design Filter

Does the UI reduce doubt? Does it make the current artifact and available actions obvious without duplicated surfaces?

If not, simplify the surface.

### Runtime Filter

Normal user language remains LLM-first. Deterministic code validates facts, artifacts, provider availability, capability truth, and execution readiness after interpretation.

No regex NLU gates, no parallel orchestrators, no hidden second state machine.

## Non-Negotiable Invariants

### Invariant 1: Ready Means Executable

Argus must not show `Ready to run` unless the persisted confirmation artifact already contains a deterministic, validated executable launch payload.

Validation must include:

- Asset resolution.
- Same-asset-class enforcement.
- Date and provider data-window feasibility.
- Supported timeframe.
- Starting capital and sizing semantics.
- Indicator/rule support.
- Indicator warmup/data sufficiency.
- Rule group completeness.
- Benchmark default.
- Durable action payload with artifact id.

No visible card may be "ready" because the UI can display a friendly summary. It is ready only when the engine launch payload is already valid.

### Invariant 2: One Artifact Owns One Action Set

If an active confirmation or result card is visible, actions render only inside that card.

The composer may show starter prompts or non-artifact suggestions only when no active card action set is visible. It must not duplicate `Run backtest`, `Change dates`, `Change asset`, `Adjust assumptions`, `Cancel`, `Show breakdown`, `Save strategy`, or `Refine strategy` above the text input.

Decision: card-scoped actions win.

Reasoning:

- Product: actions sit next to the thing they affect.
- Architecture: one artifact owns one action set.
- API: actions carry artifact/run ids from backend metadata.
- Data model: reload hydrates the same artifact actions.
- Design: fewer action surfaces, less doubt.
- Simplicity: no duplicate live-state and hydrated-state chip systems.

### Invariant 3: Browser Truth Beats Test Truth

Implementation is incomplete until the live browser can run messy human flows end to end:

Prompt -> draft or clarification -> confirmation card -> action -> result card -> follow-up -> reload -> action/follow-up still works.

### Invariant 4: Capability Claims Come From Runtime Truth

Argus must not claim an asset, indicator, condition, or strategy is executable unless the provider/catalog/registry/engine contract says it is executable.

The LLM may explain and draft unsupported ideas, but deterministic capability truth decides what can run.

### Invariant 5: Raw Internal Codes Never Reach Users

Errors like `missing_rule_group`, `indicator_data_insufficient`, `unsupported_indicator`, and provider plumbing must be converted into natural recovery language with the next executable move.

## Browser QA Failures This Pass Must Fix

The following failures were observed in live browser QA and are the release gate for the second pass.

### Failure A: Duplicate Confirmation Actions

Observed:

- Confirmation action buttons appeared inside the card and again as composer-level chips.
- After reload, the duplicate composer chips disappeared, proving two action systems were competing.

Required:

- Active artifact actions render once, inside the card.
- Composer suggestions render only when there is no active artifact action set.
- Reload must not change action placement.

### Failure B: Ready Card Can Fail Execution

Observed:

- `What if I bought Tesla after big drops?`
- User clarified with RSI thresholds.
- One browser run showed a card labeled as `signal_strategy` with visible RSI rules and then failed with `missing_rule_group`.
- A nearby phrasing produced a runnable RSI threshold card.

Required:

- Strategy type and rule payload must be normalized before confirmation.
- RSI threshold display must be backed by executable `rule_spec`.
- `signal_strategy` cannot be used as a loose label for any rule-like idea unless it has a complete entry and exit rule group.

### Failure C: Vague Momentum Invented A 50/200 Crossover

Observed:

- `Test buying SPY when it starts rising.`
- Argus asked only for time period.
- User answered `last month`.
- Argus invented `50-day SMA crosses above 200-day SMA`, marked it ready, then failed with `indicator_data_insufficient`.

Required:

- "Starts rising" is ambiguous. Argus should clarify the executable definition, such as:
  - price up by a percentage,
  - close above a moving average,
  - moving average crossover,
  - RSI momentum threshold.
- If a long warmup rule is chosen for a short window, the confirmation card must not show `Ready to run`; it should explain the data-window issue and offer an executable range or shorter-period alternative.

### Failure D: Natural Retry Lost The Failed Action

Observed:

- After `indicator_data_insufficient`, user typed `try again`.
- Argus replied: "I'm here. Tell me the investing idea you want to test."

Required:

- Failed actions are durable artifacts with action type, launch payload, failure category, user-safe explanation, and retry options.
- `try again`, `run the same one`, and `no, same one` bind to the latest failed action unless the user explicitly changes the idea.

### Failure E: Unsupported MACD Was Overstated

Observed:

- User asked for Bitcoin when MACD turns bullish and volume jumps.
- Argus claimed it could run MACD crossover-only.
- The executable registry did not support MACD as a complete runnable indicator at that time.
- Follow-up looped on confirmation.

Required:

- Capability answers must come from the executable registry and rule compiler.
- Draft/searchable indicators must be distinguished from executable indicators.
- If MACD is not fully implemented, Argus can preserve the idea and offer runnable alternatives.
- If MACD is implemented in this pass, it must have parameter schema, output selectors, warmup, tests, engine execution, confirmation display, and live browser QA.

### Failure F: Simple Buy-And-Hold Fell Into Offline Recovery

Observed:

- `Test buying and holding Apple over the past year.`
- Argus replied: "I could not process that turn. Your message is saved; please try again in one sentence."

Required:

- Normal simple strategy prompts must not depend on brittle fallback.
- If the structured LLM call fails, the user-facing recovery must preserve the idea and explain that Argus kept the message, not force the user to compress a valid request.
- The runtime should never allow offline recovery copy to become the common path for simple prompts.

### Failure G: Result Follow-Up Is Too Shallow

Observed:

- `why did it underperform spy so badly?` used metrics but gave shallow attribution.
- `why did this result happen?` after reload used facts but remained template-like.

Required:

- Result follow-up must answer from the latest run fact bank and provide useful interpretation.
- It must distinguish:
  - "what happened" from metrics,
  - "why might this have happened" as non-causal interpretation,
  - "what to try next" as executable follow-up options.

### Failure H: Save Strategy Has No Clear State

Observed:

- Clicking `Save strategy` appeared to do nothing visible.

Required:

- Save must be idempotent.
- The result card must visibly change to saved state.
- Reload must preserve saved state.
- Save should not add redundant transcript noise.

## Production Architecture Direction

### Canonical Investing-Idea Intent And Rule IR

Argus must not scale by adding one conversational branch per strategy name. That path is brittle, English-centric, hard to evaluate, and incompatible with future breadth such as sentiment strategies, macro data, news events, or multilingual prompts.

The scalable product shape is:

1. Natural language.
2. Structured LLM interpretation.
3. Canonical investing-idea intent and rule IR.
4. Capability planner outcome.
5. Validated artifact.
6. Engine launch payload.
7. Result fact bank.

The canonical IR should describe what the user wants, not which legacy template the user happened to trigger.

Minimum IR responsibilities:

- `universe`: resolved assets, unresolved candidates, asset class, provider candidates, and same-asset-class constraints.
- `time_window`: user language, normalized dates, bars/timeframe, provider data-window feasibility, and warmup requirements.
- `capital_and_sizing`: starting capital, contribution schedule, allocation method, recurring amount, and any future sizing constraints.
- `entry_logic`: one or more entry condition groups.
- `exit_logic`: one or more exit condition groups, hold-through-end semantics, or missing exit semantics.
- `signals`: price, volume, indicator, provider-derived, or future external-signal references such as sentiment.
- `parameters`: inferred defaults and user-provided overrides with provenance.
- `assumptions`: benchmark, fees, slippage, long-only, allocation, bars, and provider mode.
- `unsupported_context`: parts of the user's idea Argus understands but cannot execute yet.
- `confidence_and_open_questions`: what is clear, what materially changes execution, and what must be clarified.

Strategy families remain useful, but only as derived labels or compiler macros:

- Buy-and-hold is entry at period start plus hold-through-end exit semantics.
- Recurring buy/DCA is scheduled entry logic with contribution sizing.
- RSI threshold is an indicator-threshold rule over an oscillator output.
- Moving-average crossover is an indicator-vs-indicator crossover rule.
- Sentiment strategies, when added, should become external-signal conditions with provider requirements, not a parallel chat runtime.

This keeps the LLM flexible while keeping execution honest. The LLM proposes the IR. Deterministic capability, provider, rule, and engine-launch layers decide what can run.

Non-negotiable rule:

No new user-facing strategy breadth should require a new conversational hardcoded mapping unless it introduces a genuinely new engine primitive. New breadth should usually be added through registry schemas, rule compiler support, provider adapters, or artifact/action lifecycle support.

### Artifact Spine

Add or consolidate a canonical artifact layer with small focused modules. Do not create one giant runtime script.

Artifacts:

- `strategy_draft`
- `confirmation`
- `backtest_result`
- `failed_action`
- `saved_strategy_state`

Each artifact needs:

- `artifact_id`
- `artifact_type`
- `artifact_status`
- `conversation_id`
- `supersedes_artifact_id`
- canonical payload
- visible presentation snapshot
- action list
- validation state
- reload hydration shape

### Executable Confirmation Artifact

A confirmation artifact must contain:

- normalized strategy summary,
- display card payload,
- executable launch payload,
- validation result,
- capability context,
- card actions,
- artifact id.

If executable launch payload is missing or invalid, the artifact is not `ready_to_run`.

### Action Ownership

The backend owns the action list as artifact metadata. The frontend renders it.

Frontend rules:

- Card actions are rendered inside the card.
- Composer artifact chips are removed.
- Composer non-artifact suggestions are hidden while an active artifact card has actions.
- Historical/superseded cards are visually muted and cannot execute.
- Reload must render the same action state from persisted metadata.

Backend rules:

- Every mutating action must include artifact id or run id.
- Stale artifact actions are rejected with natural recovery language.
- A visible active artifact action must not call the LLM to reinterpret the action.

### Capability Plane

Create one capability source that both chat and product UI can query.

It should answer:

- What asset classes can run?
- Which assets are available?
- Which strategy families are executable?
- Which indicators are searchable only?
- Which indicators are draftable but not executable?
- Which indicators are executable?
- Which rule operators are executable?
- Which combinations are executable?
- What defaults and parameter bounds apply?

Mock mode must use the same interfaces as production with fixture-backed providers. It must not use a separate hardcoded brain.

### Production Testability And Provider Modes

Mock mode is a major danger if it means "special behavior for development."

Production-grade testability requires provider modes that preserve the same runtime contract:

1. `live_provider`
   - Calls real configured providers.
   - Used for production and live verification.
   - Alpaca credentials are expected to come from environment variables.
   - Kraken public market-data endpoints do not require API keys.

2. `recorded_provider_fixture`
   - Uses versioned provider snapshots captured from `live_provider` through the same provider catalog interface.
   - Used for deterministic browser QA, CI, and local development.
   - Fixture records include provider source, refresh date, asset class, supported timeframes, data-window limits, provider asset payloads, and enough OHLCV data to run representative tests.
   - Fixture snapshots are generated from provider catalogs, not manually selected as the source of truth.

3. `synthetic_unit_fixture`
   - Used only for narrow unit tests of compilers, validators, and UI states.
   - Must be clearly marked as non-release evidence.
   - Cannot be used as proof that a real asset/indicator/provider path works.

The release branch should treat `recorded_provider_fixture` as the default testable mode, not a mock brain.

Required parity rules:

- All modes use the same asset resolver interface.
- All modes use the same indicator registry interface.
- All modes use the same planner, validator, rule compiler, engine-launch adapter, and artifact shapes.
- Environment flags may change the provider implementation, but not the capability semantics.
- Fixture data must be generated from provider-shaped records, not hand-authored shortcuts.
- Capability Q&A must not say an asset or indicator is executable unless the same mode can produce the corresponding executable plan and engine launch payload.

Required release evidence:

- A fixture manifest listing provider, snapshot date, source endpoint, covered asset classes, sampled symbols, covered timeframes, and covered indicator/rule families.
- A parity test proving mock/fixture mode and live-provider mode expose the same capability schema shape.
- Browser QA using recorded fixtures for deterministic results.
- At least one live-provider smoke path before production release using configured Alpaca environment variables and Kraken public endpoints.
- Clear labeling in logs/metadata of which provider mode produced each run.

What the user can do to help:

- Keep valid Alpaca environment variables available in the local/dev environment.
- Decide whether deterministic recorded-fixture QA is acceptable as the daily release gate, with live-provider smoke as a separate release check.
- Review the live browser QA evidence and tell us whether observed "correct failures" match product expectations.

What the agent can do without waiting:

- Audit current mock paths and identify every branch that bypasses production resolver, indicator, planner, compiler, or artifact logic.
- Create the provider-mode contract and fixture manifest format.
- Use official provider docs to implement live Alpaca asset validation and Kraken public asset/pair validation.
- Build recorded fixture adapters by snapshotting provider payloads through the same provider interfaces.
- Add parity tests that fail when mock mode gains private shortcuts.
- Run browser QA in recorded fixture mode and document the provider mode in the QA evidence.
- Run live-provider smoke tests when network access is available.

### Runtime Backbone Model

This update should unlock the system Argus has been building, not bypass it.

The production loop should be:

1. **LLM brain**
   - Understands messy natural language.
   - Extracts candidate assets, indicators, parameters, operators, time ranges, and user intent.
   - Does not decide executable truth by itself.

2. **Capability tools**
   - Resolve asset availability.
   - Resolve indicator support.
   - Resolve parameter schemas and defaults.
   - Resolve rule grammar and executable templates.
   - Expose the same truth to chat, composer search, and capability Q&A.

3. **Deterministic hands**
   - Convert structured interpretation into canonical artifact payloads.
   - Compile rule specs.
   - Build engine launch requests.
   - Execute backtests.

4. **Guardrails**
   - Validate provider data availability, same-asset-class rules, max symbol counts, indicator parameters, warmup bars, output selectors, and execution readiness.
   - Block unsupported execution before a card says `Ready to run`.

5. **State management**
   - Persist artifact metadata and run facts.
   - Hydrate the same artifact after reload.
   - Bind edits, retries, saves, and follow-ups to visible artifacts.

This is the required shape for production readiness. Any implementation that bypasses one of these layers with a one-off phrase rule or local hardcoded shortcut is drift.

### Strategy Labels Are Edge Metadata

The runtime may still expose familiar labels because users, cards, saved strategies, analytics, and engine adapters benefit from understandable names. Those labels must not become the route map for natural language.

Allowed uses of strategy labels:

- Card title and saved strategy organization.
- Analytics and usage reporting.
- Engine-launch macro selection after a valid IR has been produced.
- Backward-compatible API fields where existing clients expect a strategy type.

Disallowed uses:

- Deciding user intent before LLM interpretation.
- Adding one hardcoded chat branch per new strategy phrase.
- Treating `signal_strategy` as a catch-all for incomplete rules.
- Losing richer IR fields because a template label was selected.
- Claiming a label is executable when the underlying IR cannot compile.

Backward-compatible migration rule:

Existing `strategy_type` fields may remain during this pass, but they must be derived from or attached to the canonical IR. If the IR and `strategy_type` disagree, the IR/capability/compiler truth wins and the artifact must not be marked ready until the disagreement is repaired.

### Model Routing And Cost Discipline

Model selection is part of the runtime contract, not an implementation accident.
The goal is low-cost development without hiding production reliability risks.

Required routing shape:

1. `AGENT_MODEL`
   - Primary conversational model.
   - Used for normal chat, education, clarification, and flexible prose where a
     weaker answer can be recovered conversationally.

2. `AGENT_FALLBACK_MODEL`
   - Secondary model in the configured low-cost chain.
   - Tried only when the primary model fails, times out, or returns an
     incomplete artifact.

3. `AGENT_STRUCTURED_MODEL`
   - Optional explicit override for durable artifact extraction.
   - Must not be silently filled with an expensive model.
   - Should be set only when live QA proves the low-cost configured chain cannot
     produce complete strategy/run artifacts reliably enough.

Structured artifact calls use OpenRouter JSON-schema responses directly. For
artifact extraction, Argus should disable reasoning with
`reasoning: {"effort": "none"}` because the product needs complete JSON content,
not billable hidden reasoning. If a provider rejects that setting, the client may
retry without the reasoning setting and then continue through the configured
model chain. A model response that is valid JSON but missing the usable strategy
or artifact body is a failed candidate, not a successful interpretation.

Model changes are not allowed by vibes or one-off probes. Before changing
`AGENT_MODEL`, `AGENT_FALLBACK_MODEL`, or `AGENT_STRUCTURED_MODEL`, Argus needs a
repeatable benchmark matrix that scores each candidate by task:

- **Interpretation/artifact extraction:** preserves assets, periods, indicators,
  parameters, user overrides, refinement continuity, unsupported constraints, and
  approval/retry intent.
- **Conversational composition:** answers product and investing questions without
  duplicating prior assistant text, overstating execution support, or flattening
  the user's branch into generic advice.
- **Result readout and breakdown:** uses stored run facts, cites assumptions,
  avoids invented metrics, and explains actionable next experiments.
- **Operational behavior:** latency, timeout rate, invalid JSON rate, incomplete
  artifact rate, and cost per task.

Only a candidate that wins the relevant task benchmark and survives live browser
QA should be promoted into environment defaults.

## Indicator And Strategy Support Direction

The product must support creative user strategy ideas without hand-authoring one rigid strategy per phrase.

The right backbone is canonical intent/rule IR plus a schema-driven pandas-ta indicator provider.

pandas-ta support means Argus can compute or discover an indicator. Executable strategy support means Argus can also map user language into a validated rule using that indicator, with clear parameters, outputs, defaults, and entry/exit semantics.

This distinction should unlock flexibility rather than restrict it:

- If pandas-ta can expose an indicator, Argus can list/search/explain it.
- If Argus can infer or declare its parameter schema and outputs, Argus can draft with it safely.
- If Argus can bind those outputs into rule grammar and validate the data window, Argus can execute it.
- If user phrasing is incomplete, Argus asks a precise clarification instead of guessing.

This same direction applies beyond indicators:

- Sentiment strategies should be modeled as external-signal conditions with provider/data-source requirements.
- Event or macro strategies should be modeled as provider-backed signal conditions with clear timestamps and lookback rules.
- Multi-language prompts should produce the same IR as equivalent English prompts.
- New strategy breadth should change schemas, providers, compiler support, or guardrails, not add another conversational shortcut.

### Capability Tiers

Every indicator belongs to exactly one tier:

1. `searchable`
   - User can find it.
   - Argus can explain it.
   - Argus must not imply it can run.

2. `draftable`
   - Argus can preserve the idea in the conversation.
   - Argus can explain what would be needed.
   - Argus can offer executable simplifications.

3. `executable`
   - Indicator has parameter schema.
   - Indicator has default values and valid ranges.
   - Indicator has output selector mapping.
   - Indicator has warmup rules.
   - Indicator has required data columns.
   - Indicator works through the rule compiler.
   - Indicator appears in capability Q&A as runnable.
   - Indicator passes engine tests and live browser QA.

### Production Rule

Argus may expose the full pandas-ta catalog for search and education, but it must not claim full executable support for the entire pandas-ta catalog until each indicator has an executable spec and browser-proven path.

### Schema-Driven pandas-ta Provider

Build the indicator provider around schemas, not static one-off lists.

The provider should maintain an `IndicatorDefinition` concept with:

- canonical key,
- label,
- category,
- aliases,
- provider source (`pandas_ta_classic` or native),
- callable name,
- parameter schema,
- default parameters,
- valid ranges when known,
- required OHLCV columns,
- warmup estimate,
- output schema,
- semantic output roles,
- supported rule roles,
- support tier.

Parameter schema should be inferred from pandas-ta signatures where possible and overridden by explicit Argus specs where needed.

Examples:

- `sma`: `length`, output role `line`.
- `ema`: `length`, output role `line`.
- `rsi`: `length`, output role `oscillator`, default threshold semantics.
- `macd`: `fast`, `slow`, `signal`, output roles `macd`, `signal`, `histogram`.
- `bbands`: `length`, `std`, output roles `lower`, `middle`, `upper`, `bandwidth`, `percent`.
- `stoch`: `k`, `d`, `smooth_k`, output roles `k`, `d`.
- `vwap`: required columns include `high`, `low`, `close`, `volume`; output role `line`.
- `atr`: output role `volatility`; not a default entry trigger without user semantics.

Argus should prefer provider defaults when they are sensible and stable, but it must expose overrides through natural language:

- "SMA 7"
- "RSI 21"
- "MACD 8 21 5"
- "Bollinger Bands 20 and 2 standard deviations"

If the user omits parameters, defaults are allowed, but the confirmation card must show them.

### Output Roles And Rule Semantics

Indicators are not all identical from a strategy semantics perspective. They can all be represented through schemas, but the schema must describe how their outputs may be used.

Examples:

- Single-line indicators can compare price versus the line or line versus threshold.
- Oscillators can use threshold semantics, such as oversold/overbought.
- Multi-output indicators can compare one output to another, such as MACD crossing signal or Stoch K crossing D.
- Band indicators can compare price to lower/middle/upper bands.
- Volatility indicators like ATR may need a second semantic, such as "ATR above its moving average" or "ATR-based exit," before they are executable.

This is how Argus preserves creative natural language without pretending vague rules are complete.

### Executable Rule Patterns For This Update

This pass should make the following rule patterns production-grade:

- Indicator threshold:
  - Example: RSI <= 30, MFI >= 80.
- Price versus indicator:
  - Example: close crosses above EMA 200, close below VWAP.
- Indicator versus indicator:
  - Example: SMA 50 crosses above SMA 200, MACD crosses signal.
- Indicator band rules:
  - Example: close crosses below lower Bollinger Band, exit at middle band.
- Volume confirmation:
  - Example: volume above volume SMA.
- Simple condition groups:
  - Entry when A AND B.
  - Exit when C OR D.

### Executable Indicator Decision Table

Before implementation, create a decision table for these common families. Each row must be classified as `executable_this_pass`, `draftable_this_pass`, or `searchable_only`, with the reason and required browser QA prompt.

- Trend: SMA, EMA.
- Momentum: RSI, MACD, Stochastic, ROC or momentum.
- Volatility bands: Bollinger Bands.
- Volume: VWAP, OBV, volume SMA.
- Volatility/risk context: ATR.
- Money flow / trend strength: MFI, ADX.

Any family classified as `executable_this_pass` must have full functionality: parameter schema, defaults, bounds, warmup, output selectors, aliases, engine tests, confirmation display, result follow-up support, and live browser QA.

Any family that cannot be made reliable without architectural drift must remain draftable or searchable only, and the product must say so.

### Rule Compiler Requirements

The rule compiler must be generic enough to avoid one-off strategy patches:

- It consumes a normalized `rule_spec`.
- It resolves price, volume, and indicator series.
- It resolves multi-output indicator fields through output roles.
- It applies inferred or declared indicator defaults.
- It supports `lt`, `lte`, `gt`, `gte`, `cross_above`, `cross_below`.
- It supports `all` and `any`.
- It validates warmup and data-window feasibility before confirmation.
- It returns boolean entry/exit series for the existing long-only execution engine.
- It does not implement arbitrary user code or formulas.

## Asset Resolution Direction

Hardcoded asset mappings are not production truth.

Assets need the same provider-backed architecture as indicators.

Different market data providers overlap and complement each other:

- Alpaca is primary for equities and may cover crypto.
- Kraken complements crypto and owns currency-pair/forex-like coverage.
- Some symbols may exist in more than one provider.
- Some assets may be searchable but not executable for a requested timeframe or provider window.

Provider source APIs:

- Alpaca `/v2/assets` and single-asset lookup provide securities/crypto asset validation, including status and tradability fields.
- Kraken public `/public/Assets` and `/public/AssetPairs` provide asset and tradable-pair catalogs.
- Kraken public `/public/OHLC` provides OHLC data with the documented latest-720-candle limit.

Production behavior:

- Asset resolution uses provider catalog truth.
- Cached provider snapshots may exist in the database or local cache, but the resolver interface remains the source the app calls.
- Mock mode uses fixture-backed provider catalog through the same resolver interface.
- The LLM may supply candidate text, but deterministic resolver owns canonical symbol, asset class, and availability.
- Composer `@` search and chat resolution must share the same resolver/capability layer.

### Provider-Aware Asset Catalog

Build asset resolution around an `AssetProviderCatalog` concept.

Each asset record should include:

- canonical symbol,
- display symbol,
- provider symbol,
- asset class,
- provider source,
- provider priority,
- name,
- aliases,
- tradability / data availability,
- supported timeframes,
- provider data-window limits,
- last catalog refresh,
- confidence/source metadata.

When providers overlap, resolver behavior should be deterministic:

- Prefer the provider that owns the requested asset class and execution path.
- Preserve alternate provider candidates for fallback and diagnostics.
- Do not merge different asset classes just because display symbols look similar.
- Resolve ambiguous names through provider candidates and ask a clarification only when the outcome changes execution.

Examples:

- "Apple" -> provider-backed AAPL equity candidate.
- "Bitcoin" -> BTC crypto candidate, with provider availability chosen by date/timeframe.
- "ETH/BTC" -> crypto pair/currency-pair-like candidate only if provider execution supports it.
- "Meta" -> META equity, not a hardcoded special case.

Allowed local fixtures:

- tests,
- storybook/mock UI,
- offline development,
- deterministic mock provider snapshots.

Disallowed:

- product runtime logic that silently resolves assets through unrelated hardcoded maps while claiming production capability.

## Conversation Runtime Direction

### LLM-First, Artifact-Grounded

Normal text still goes to the structured LLM interpreter first.

After interpretation, deterministic code may:

- select the active artifact,
- patch the artifact,
- validate the artifact,
- reject stale actions,
- answer deterministic capability questions from the registry,
- retrieve result fact banks,
- create user-safe failure recovery.

### Clarification Discipline

Argus should ask questions only when the answer changes executable behavior.

Good clarification:

- "When you say starts rising, should I define that as close above a moving average, a percentage gain, or an RSI threshold?"

Bad clarification:

- Asking whether "simply held it" means buy-and-hold.
- Asking for asset again when visible/pending artifact has one.
- Asking for time period after the user already provided one.

### Fallback Discipline

Offline or LLM failure recovery must not sound like a system crash.

Bad:

- "I could not process that turn. Your message is saved; please try again in one sentence."

Better:

- "I kept your message, but I could not finish structuring it. I understood this as an Apple buy-and-hold test over the past year. Want me to draft that, or should I adjust anything first?"

Fallback recovery should be conservative, but never dump raw scaffolding or make a valid user request feel wrong.

## Result Intelligence Direction

Result follow-ups must use canonical run facts.

Supported follow-up classes:

- What exactly did you test?
- What was max drawdown?
- Did it beat the benchmark?
- Why did it underperform/outperform?
- What assumptions are you using?
- What changed after reload?
- What should I try next?

Answer requirements:

- Use run id, symbols, strategy, date range, benchmark, metrics, assumptions.
- Correct false premises.
- Explain that causal attribution is limited.
- Suggest only executable next tests unless clearly labeling draft/future ideas.
- Never invent metrics outside stored results.

## Result Action Direction

### Show Breakdown

- Adds one breakdown response.
- Does not duplicate result card.
- Consumes `Show breakdown` for that result after a successful breakdown response so the same card cannot append duplicate breakdowns.
- Uses result fact bank.
- Survives reload.

### Save Strategy

- Uses concrete run id.
- Saves from canonical completed run state.
- Is idempotent.
- Updates card state to saved.
- Shows clear feedback.
- Does not append noisy transcript messages.
- Survives reload.

### Refine Strategy

- Starts from the result artifact and prior config snapshot.
- Creates a new draft/confirmation artifact from the completed run snapshot.
- Applies the user's refinement to that new draft while preserving unchanged
  run context such as asset class, asset, benchmark, date range, and
  assumptions.
- Does not mutate the completed run.
- Does not save over an existing saved strategy until the user explicitly saves
  the refined result.
- If the refinement is executable, shows a new confirmation card. If it is
  unsupported or underspecified, preserves the idea as draft context and asks
  only for the missing execution semantics.

## UX Decision: Card-Scoped Actions Only

This is the chosen behavior for the snapshot issue.

### Rule

Card actions live inside cards. Composer-level artifact chips are removed.

### Composer Behavior

The composer can show:

- starter suggestions when the thread is empty,
- general non-artifact suggestions when no active artifact action set exists,
- plain text input always.

The composer cannot show duplicate artifact actions while an active card already owns them.

### Visual Behavior

Cards become the user's visible contract:

- Confirmation cards own `Run backtest`, `Change dates`, `Change asset`, `Adjust assumptions`, `Cancel`.
- Result cards own `Show breakdown`, `Save strategy`, `Refine strategy`.
- Superseded cards are muted and action-disabled.
- Active cards show a concise status such as `Ready to run`, `Updated`, `Running`, `Completed`, `Saved`, or `Needs change`.

## Clean Code Requirements

This pass must reduce drift, not add another layer of hidden coupling.

Argus remains a modular monolith. That means one deployable codebase with clear internal ownership boundaries, not a pile of cross-cutting helper files. A module should be understandable by its public interface before reading its internals.

### Separation Of Concerns Gate

Before implementing or reviewing any change, apply this gate:

- If a file parses LLM output, validates engine capability, renders UI, and persists records, it has too many jobs.
- If a file needs knowledge of provider quirks, card rendering, and LangGraph state transitions at the same time, the boundary is wrong.
- If a test must know internal details from three layers to assert one behavior, the implementation is probably too coupled.
- If a fix requires adding another branch to an already-large stage/component instead of moving logic behind a clear interface, stop and split the responsibility.

The goal is not abstraction for its own sake. The goal is fast debugging: when a browser QA failure happens, the owner module should be obvious.

### Module Responsibility Rules

Each module should own one concern:

- Capability modules answer "what can Argus do?"
- Provider modules answer "what data/assets/indicators exist and under what limits?"
- Rule modules answer "can this normalized rule become entry/exit signals?"
- Engine-launch modules answer "can this artifact become an executable engine request?"
- Planner modules answer "what is the next truthful product move for this interpreted idea?"
- Runtime modules answer "which conversational artifact is active and how should the next turn move?"
- API chat modules answer "how do artifacts, messages, runs, and actions persist and recover?"
- Frontend chat modules answer "how does the canonical artifact render and behave?"

Cross-layer communication should happen through typed payloads and small public helpers, not by importing another layer's internal assumptions.

### Required Module Boundaries

Backend:

- `domain/capabilities/`
  - product capability registry, strategy families, indicator tiers, rule operators.
- `domain/market_data/`
  - provider-backed asset resolution and fixture-backed mock providers.
- `domain/indicators/`
  - executable specs, pandas-ta adapters, output selectors, defaults, bounds, aliases.
- `domain/backtesting/rules/`
  - rule models, validation, series resolution, compiler.
- `domain/engine_launch/`
  - converts canonical artifact launch payloads into engine configs.
- `agent_runtime/planning/`
  - capability planner outcomes, artifact edit proposals, clarification/repair options, and retry/result-follow-up routing.
- `agent_runtime/`
  - LLM interpretation, artifact selection, artifact editing, result/retry binding.
- `api/chat/`
  - persistence, recovery, action endpoints, saved/breakdown behavior.

Frontend:

- `web/components/chat/artifacts/`
  - artifact-specific hydration/render helpers if the main chat component begins to grow again.
- `web/components/chat/actions/`
  - card-scoped action rendering and action dispatch helpers.
- `web/components/chat/StrategyConfirmationCard.tsx`
  - render confirmation artifact and card-scoped actions.
- `web/components/chat/StrategyResultCard.tsx`
  - render result artifact and card-scoped actions.
- `web/components/chat/ChatInterface.tsx`
  - composition shell for streaming, hydration orchestration, composer placement, and message list coordination only.
- `web/components/chat/composer/`
  - composer text input and non-artifact suggestions.

`ChatInterface.tsx` must not become the owner of card action semantics, artifact validation, result save state, and message hydration all at once. If it starts accumulating those roles, split before adding more behavior.

### Prohibited Shapes

- One giant runtime helper.
- A second orchestrator.
- Regex NLU before the LLM.
- Frontend reconstructing strategies from visible text.
- Tests that normalize broken behavior.
- Mock-only code paths that bypass production resolver contracts.
- User-facing raw error codes.
- "Temporary" cross-layer imports that make a file know about unrelated runtime, provider, persistence, and UI details.
- New modules named generically enough to hide multiple concerns, such as `utils`, `helpers`, or `runtime_helpers`, unless their public surface is narrow and obvious.

## Canon Docs Policy

This pass should not rewrite canon docs unless absolutely required.

Allowed documentation work:

- New spec documents under `docs/superpowers/specs/`.
- New QA evidence under `docs/superpowers/qa/`.
- Minimal additive clarifications to `docs/API_CONTRACT.md` or `docs/CONVERSATIONAL_RUNTIME.md` only if implementation introduces a real structured field or lifecycle state.

Stop and consult the user before changing:

- product scope,
- architecture ownership,
- data model table shape,
- API breaking shapes,
- supported asset-class rules,
- the LangGraph runtime ownership model,
- Alpha exclusions such as shorting, leverage, arbitrary formulas, mixed-asset backtests, or real trading.

## Implementation Workstreams

Implementation must proceed as vertical slices, not broad layers. A vertical slice means browser-visible functionality works end to end before the next expansion begins.

The eight workstreams below are governed by the five recommended next moves:

- Move 1, freeze the evaluation spine, guards every workstream.
- Move 2, close artifact/action runtime, owns Workstreams 1, 2, 3, 6, 7, and 8.
- Move 3, replace strategy-template thinking with canonical IR, owns Workstreams 4, 5, and 6.
- Move 4, unify provider and capability truth, owns Workstreams 4 and 5.
- Move 5, run release-grade live browser QA, is the exit gate for every workstream.

No workstream is complete until its browser gate is represented in the evaluation spine and has fresh evidence.

### Slice 0: First-Pass Drift Audit

Goal: decide what to keep, rework, or remove from the current branch before adding more behavior.

Required output:

- A short audit note with file-level keep/rework/remove decisions.
- A list of stale tests or QA claims that must not be trusted.
- Confirmation that no work proceeds from the first-pass "passing" assumption.

Browser gate:

- Existing simple buy-and-hold still reaches a result before deeper refactors continue.

### Slice 1: Artifact Spine And Card-Scoped Actions

Goal: one visible artifact owns one validated payload and one action set.

Required output:

- Confirmation artifacts carry validated launch payloads.
- Result artifacts carry run fact references.
- Failed-action artifacts carry retry context.
- Composer artifact chips are removed.

Browser gate:

- No duplicate card/composer action chips.
- `Ready to run` never appears without executable payload validation.
- Reload preserves card-scoped actions.

### Slice 2: Core Conversation Continuity

Goal: drafts, assumptions, retry, and result follow-ups work on the artifact spine.

Required output:

- Draft edits bind to active draft/confirmation artifacts.
- Assumption questions answer from visible card.
- Retry binds to latest failed action.
- Result follow-ups use latest run fact bank.
- Save and breakdown actions are idempotent and visible.

Browser gate:

- QA 1, QA 2, QA 6, QA 7, QA 8, and QA 9 pass.

### Slice 3: Capability Planner, Capability Plane, And Provider Catalogs

Goal: interpreted user ideas flow through a planner that can produce truthful next moves, while chat, composer search, provider fixtures, assets, indicators, and capability Q&A use the same truth interfaces.

Required output:

- Capability planner input/output models and outcome taxonomy.
- Planner support for new ideas, artifact edits, capability questions, retries, result follow-ups, clarification, repair, draft-only ideas, and unsupported-with-alternatives.
- Provider-aware asset catalog and fixture-backed mock provider path.
- Schema-driven indicator catalog and support tiers.
- Capability answer helpers that the LLM can consume but does not own.
- Provider-mode manifest for recorded fixtures.
- Parity tests proving fixture modes do not bypass production contracts.

Browser gate:

- QA 13 and QA 14 pass.
- Capability answers match actual runnable paths.
- Ambiguous prompts produce useful next moves instead of false ready cards or generic rejection.

### Slice 4: Schema-Driven Rule Engine Expansion

Goal: broaden strategy expressiveness through the rule compiler, not rigid templates.

Required output:

- Indicator decision table.
- Executable indicator schemas for the selected families.
- Rule compiler support for thresholds, crossovers, price-vs-indicator, indicator-vs-indicator, bands, volume confirmation, and simple groups.
- Clear draft/search-only behavior for incomplete indicators.

Browser gate:

- QA 3, QA 4, QA 5, QA 11, and representative indicator-family prompts pass.

### Slice 5: Trust Polish And Localization Smoke

Goal: user confidence polish after the runtime truth is stable.

Required output:

- Copy/feedback controls scoped and delayed until final messages.
- No scroll yank.
- Status and answer surfaces do not compete.
- Spanish smoke remains on the same artifact path.

Browser gate:

- QA 10 and QA 12 pass on desktop and a mobile-sized viewport.

### Workstream 1: Audit And Revert First-Pass Drift

Goal: identify which current changes serve the second-pass invariant and which are patch-shaped.

Actions:

- Review all modified files against this spec.
- Keep useful tested pieces only if they support canonical artifacts.
- Remove duplicate composer artifact action logic.
- Mark stale QA claims as superseded.
- Re-check PR 80/81 protected SSE and hydration boundaries.

Exit criteria:

- A short audit note lists keep/remove/rework decisions.
- No implementation proceeds from stale "passing" assumptions.
- Any deterministic phrase/strategy mapping that predates LLM-first interpretation is classified as keep only if it is an engine macro or compatibility adapter, not a conversational router.

### Workstream 2: Canonical Artifact Contract

Goal: one artifact object owns visible card state, executable payload, action state, and reload hydration.

Actions:

- Define confirmation/result/failed-action artifact shapes.
- Persist active artifact metadata with messages.
- Store executable launch payload before showing `Ready to run`.
- Validate launch payload before confirmation display.
- Reject or clarify invalid cards before they become actionable.

Exit criteria:

- A card cannot render `Ready to run` without a validated launch payload.
- Reload produces the same card and action state.

### Workstream 3: Action Lifecycle And UI Ownership

Goal: remove duplicate action surfaces and stale action ambiguity.

Actions:

- Remove composer-level artifact chips.
- Render card actions from backend artifact metadata.
- Disable superseded card actions.
- Add natural recovery when stale actions are clicked.
- Ensure action state after reload matches pre-reload state.

Exit criteria:

- No duplicate action chips in browser.
- Card-scoped actions work before and after reload.

### Workstream 4: Capability Planner And Provider Truth

Goal: one capability planner and capability plane power LLM context, canonical IR, UI answers, provider modes, fixture-backed QA, and validation.

Actions:

- Define canonical investing-idea intent and rule IR models or explicit adapter boundaries for the current pass.
- Define planner input and output models.
- Implement outcome taxonomy: `ready_to_confirm`, `needs_clarification`, `needs_repair`, `draft_only`, `answer_only`, `unsupported_with_alternatives`.
- Route planner outputs into artifact creation, artifact editing, retry recovery, result follow-ups, and capability answers.
- Ensure planner decisions are based on capability/provider/compiler truth, not prompt copy.
- Inventory current provider asset resolution.
- Define provider-backed asset catalog records and resolver priority rules.
- Replace product runtime hardcoded maps with provider/fixture resolver interface.
- Define provider modes: `live_provider`, `recorded_provider_fixture`, and `synthetic_unit_fixture`.
- Add fixture manifest shape and provider-mode metadata.
- Define schema-driven pandas-ta indicator definitions and support tiers.
- Create capability answer helpers for assets, indicators, operators, rule patterns, and strategy families.
- Feed capability summaries into the LLM prompt without making prompt text the source of truth.
- Ensure recorded fixture mode uses provider-shaped records through the same interface.
- Add parity tests that fail if fixture mode gains private resolver, indicator, planner, compiler, or artifact shortcuts.

Exit criteria:

- Creative but incomplete prompts produce planner outcomes that preserve intent and offer precise next moves.
- Capability Q&A answers are deterministic and match actual executable registry.
- Recorded fixture mode does not hide production resolver gaps.
- Composer search and chat resolution return consistent assets/indicators.
- Strategy family/type values are derived from the IR and compiler/capability result, not selected by conversational shortcuts.

### Workstream 5: Indicator And Rule Engine Completion

Goal: make the advertised indicator/rule patterns actually executable end to end through canonical IR and generic compiler support.

Actions:

- Inventory pandas-ta availability and current engine adapters.
- Implement schema inference for pandas-ta indicators where signatures are stable.
- Define explicit Argus overrides for defaults, bounds, warmup, required columns, and output roles where inference is insufficient.
- Classify the indicator catalog into searchable, draftable, and executable tiers.
- Implement parameter schemas, defaults, bounds, warmup, output selectors, aliases, and semantic output roles.
- Compile generic rule specs into entry/exit signals.
- Validate data sufficiency before confirmation.
- Support threshold, crossover, price-vs-indicator, indicator-vs-indicator, volume confirmation, and simple groups.
- Keep draft-only indicators honest.

Exit criteria:

- Every indicator claimed as executable has engine tests and live browser QA.
- Every unsupported indicator is preserved and explained without fake execution promises.
- Every executable indicator can use defaults or user-provided parameter overrides.
- A new executable rule pattern is added by extending schemas/compiler support, not by adding a chat phrase branch.

### Workstream 6: Conversation Continuity And Recovery

Goal: natural edits, assumptions, retry, and reload bind to active artifacts.

Actions:

- Bind "actually make it X", "use last 6 months", "what assumptions", "try again", "run the same one" to active artifact context after LLM interpretation.
- Store failed-action artifacts with retryable launch payload and user-safe failure.
- Improve LLM failure fallback so valid prompts do not become "try again in one sentence."

Exit criteria:

- Pending draft refinement passes messy browser scripts.
- Natural retry binds to latest failed action.
- Assumption answers come from visible card.

### Workstream 7: Result Intelligence And Actions

Goal: completed runs become durable conversational facts.

Actions:

- Build result fact bank from immutable run records.
- Inject result facts into follow-up answers.
- Make Show Breakdown fact-grounded and non-duplicative.
- Make Save Strategy idempotent and visibly persisted.
- Keep Refine Strategy grounded in result config snapshot.

Exit criteria:

- Result follow-ups after reload answer from latest run.
- Save and breakdown actions are stable and clear.

### Workstream 8: Trust Polish

Goal: UI behavior never makes the user doubt completion or action state.

Actions:

- Hide feedback/copy controls while latest assistant response is streaming.
- Scope copy to exact assistant message/card content.
- Show copy success/failure feedback.
- Prevent scroll yank while the user reads older content; use `Jump to latest`.
- Remove competing status and answer surfaces.

Exit criteria:

- Trust polish live QA passes on desktop and mobile-sized viewport.

## Live Browser QA Matrix

This matrix is the release gate.

### QA 1: Simple Buy And Hold Human Language

Prompt:

`i just wanna know if microsoft beat spy last year if i simply held it`

Expected:

- Argus recognizes buy-and-hold without unnecessary clarification.
- It resolves Microsoft to MSFT.
- It drafts or confirms past-year MSFT vs SPY.
- Run succeeds.
- Follow-up `why did it underperform/outperform?` uses result facts with interpretation, not just metric repetition.

### QA 2: Draft Continuity

Prompts:

1. `Test buying and holding Apple over the past year.`
2. `Actually make it Nvidia.`
3. `Use the last 6 months instead.`
4. `What assumptions are you using?`

Expected:

- Apple resolves or clarifies through provider resolver.
- Nvidia edit preserves strategy.
- Date edit preserves NVDA.
- Assumptions answer from visible card.
- Reload preserves card and actions.

### QA 3: Ambiguous Dip To RSI

Prompts:

1. `What if I bought Tesla after big drops?`
2. `technical thing like RSI, buy when it gets to 20 or lower, sell when 60 or higher, past 3 months`

Expected:

- Argus asks useful clarification for "big drops."
- RSI thresholds become an executable indicator rule.
- Card says `Ready to run` only with valid launch payload.
- Run succeeds or explains data insufficiency before showing ready.

### QA 4: Vague Momentum

Prompts:

1. `Test buying SPY when it starts rising.`
2. `last month`

Expected:

- Argus does not invent 50/200 SMA crossover.
- It asks how to define "starts rising."
- If the user chooses a long-window crossover with one-month range, Argus explains warmup/window issue before ready state.

### QA 5: Unsupported Compound Indicator

Prompts:

1. `could you test bitcoin when macd turns bullish and volume jumps, maybe over the last 6 months?`
2. `ok run the macd crossover only`

Expected:

- Argus states exact executable truth.
- If MACD is executable, it drafts a valid rule with defaults and exit semantics.
- If MACD is not executable, it preserves the idea and offers executable alternatives.
- It never claims a draft-only indicator can run.

### QA 6: Confirmation Action Reliability

Steps:

1. Create a simple confirmation card.
2. Reload before running.
3. Click `Run backtest`.

Expected:

- One action surface inside the card.
- Action survives reload.
- Run uses artifact payload, not reinterpretation.

### QA 7: Natural Retry Recovery

Steps:

1. Trigger a controlled recoverable failure, such as data-window insufficiency.
2. Type `try again`.
3. Type `no, run the same one`.

Expected:

- Argus binds to latest failed action.
- It either retries with same valid payload or offers precise executable adjustment.
- It does not ask for asset again.

### QA 8: Result Follow-Up Depth

Steps:

1. Run a completed backtest.
2. Ask:
   - `Why did it underperform the benchmark?`
   - `What was the max drawdown?`
   - `What exactly did you test?`
   - `What should I try next?`
3. Reload.
4. Ask: `Why did this result happen?`

Expected:

- Answers use latest run facts.
- False premises are corrected.
- Interpretation is useful and caveated.
- Reload does not lose result context.

### QA 9: Result Card Actions

Steps:

1. Run a backtest.
2. Click `Show a breakdown`.
3. Click `Save strategy`.
4. Reload.

Expected:

- Breakdown does not duplicate result card.
- Save visibly changes state.
- Save is idempotent.
- Reload preserves saved state.

### QA 10: Trust Polish

Steps:

1. Send a prompt that streams.
2. Scroll during streaming.
3. Hover latest assistant message.
4. Copy from message menu.

Expected:

- Status and assistant answer do not compete.
- Page does not yank unexpectedly.
- Feedback/copy controls wait until response is final.
- Copy has visible feedback.

### QA 11: Crypto Comparison And Same-Asset Validation

Prompt:

`Compare Ethereum and Bitcoin over the last year.`

Expected:

- Argus handles same-asset crypto comparison if supported by the current engine path, or explains the supported comparison flow.
- It does not confuse comparison with mixed-asset validation.
- It preserves ETH/BTC context after reload.

### QA 12: Spanish Smoke

Prompt:

`Prueba comprar y mantener Nvidia durante los ultimos seis meses.`

Expected:

- Static UI remains localized where applicable.
- AI response mirrors Spanish preference or user language context.
- Card values and dates remain understandable.
- Run path remains the same canonical artifact path.

### QA 13: Capability Truth Q&A

Prompts:

1. `what indicators can I use here?`
2. `do you support MACD, Bollinger Bands, VWAP, and ATR?`
3. `can I change the RSI period to 21?`

Expected:

- Argus distinguishes searchable, draftable, and executable indicators.
- Argus answers from the capability registry, not stale prompt copy.
- Argus explains parameter defaults and user overrides.
- Argus does not claim every pandas-ta indicator is executable unless full functionality exists.

### QA 14: Provider-Aware Asset Resolution

Prompts:

1. `test Apple over the last year`
2. `compare bitcoin and ethereum over six months`
3. `test euro dollar over the last week`

Expected:

- Asset resolution uses provider-backed candidates.
- Equity, crypto, and currency-pair assets resolve through the shared resolver path.
- Provider overlap is deterministic and visible in assumptions only when useful.
- Provider data-window limits produce natural recovery before `Ready to run`.

## Test Suite Role

Automated tests should protect the architecture, not replace browser truth.

Required test classes:

- Unit tests for capability planner outcomes.
- Unit tests for capability registry.
- Unit tests for asset resolver fixture/production interface parity.
- Unit tests for provider-mode manifest validation.
- Unit tests for indicator specs.
- Unit tests for rule compiler.
- Engine integration tests for selected indicators and rule patterns.
- Runtime tests for artifact selection, patching, stale action rejection, retry binding.
- API contract tests for message metadata and action payloads.
- Frontend tests for no duplicate artifact actions, card-scoped actions, saved state, copy scoping.
- PR 80/81 SSE and hydration guardrails.

But final acceptance requires live browser QA matrix passing.

## Lightweight Evaluation Spine

Argus needs an evaluation spine that embraces non-determinism without letting the runtime become untestable.

The goal is not a large evaluation platform. The goal is a small, durable harness that makes the eight buckets repeatedly testable and prevents regressions from hiding behind green unit tests.

### Evaluation Artifacts

Create a small scenario manifest for the current release slice.

Each scenario should include:

- `id`
- `bucket`
- `purpose`
- `natural_prompt_variants`
- `conversation_steps`
- expected artifact type and status
- expected visible card state
- expected action availability
- expected persisted metadata fields
- reload expectations
- expected result fact usage when relevant
- forbidden outcomes
- optional LLM-judge rubric for answer quality

The manifest should be intentionally small at first. It should cover the browser QA matrix and the known red/yellow regressions before adding breadth.

### Evaluation Layers

Use three complementary layers:

1. **Code-scored contract checks**
   - Artifact exists.
   - Artifact id is stable.
   - Launch payload exists before `Ready to run`.
   - Actions include artifact/run ids.
   - Result fact bank exists after completion.
   - Reload preserves active artifact/result context.

2. **Browser trajectory checks**
   - The app reaches the expected visual state.
   - Card actions are clickable and scoped.
   - Composer actions do not duplicate card actions.
   - Raw internal codes are absent.
   - Reload behavior matches the pre-reload artifact state.

3. **LLM-as-judge checks**
   - Used only for answer quality after hard runtime checks pass.
   - Scores whether the answer is grounded in visible/run facts, truthful about capability, helpful, concise, and non-overclaiming.
   - Must not override deterministic failures. A beautiful answer attached to a stale artifact is still a failure.

### Probabilistic Mindset

Non-deterministic prompts should be grouped by intended semantic target, not exact text.

Example group:

- "what if I bought Tesla after a big drop?"
- "suppose I wait for TSLA to get hammered then buy"
- "can we test buying Tesla on dips?"

Correct behavior is not identical wording. Correct behavior is a high probability of converging to the same truthful next move: clarify dip semantics or draft a supported rule if the user supplies one.

### Release Scoring

For this pass, use a simple release score:

- `must_pass`: hard runtime invariants and browser QA scripts.
- `should_pass`: natural variants that should usually converge to the same planner outcome.
- `watch`: educational or exploratory answers judged for quality but not release-blocking unless they overclaim executable support.

A `must_pass` failure blocks completion. A `should_pass` failure requires a documented decision: fix now, downgrade to watch with reason, or add it to the next pass. A `watch` failure is recorded as product learning unless it violates capability truth.

### Eval Scope Guardrail

The eval spine must not become a second product runtime. It observes the runtime, seeds scenarios, inspects artifacts/actions/results, and optionally judges answer quality. It does not add interpretation rules, hidden mock behavior, or special browser-only shortcuts.

## Expected End State

If this pass is implemented correctly, the system status should be:

### Conversation Runtime

- Users can describe realistic investing ideas in natural language.
- A capability planner turns interpreted ideas into truthful next moves instead of rigid acceptance or rejection.
- Argus asks only clarifications that change executable behavior.
- Draft edits preserve prior context unless the user explicitly changes it.
- The active artifact remains coherent through edit, confirmation, run, result, follow-up, reload, retry, and save.
- LLM failures degrade gracefully without blaming the user or dumping internal scaffolding.

### Strategy Execution

- Buy-and-hold and recurring buy flows remain stable.
- Indicator strategies are no longer limited to brittle one-off RSI paths.
- Schema-backed indicators can use defaults or user-supplied parameters.
- Rule specs can express thresholds, crossovers, price-vs-indicator, indicator-vs-indicator, bands, volume confirmation, and simple AND/OR groups where supported.
- Unsupported or underspecified strategies are preserved as ideas and clarified or simplified without pretending they can run.

### Capability Truth

- Asset resolution, indicator support, rule support, and provider data windows are deterministic.
- Recorded fixture mode uses the same interfaces as production through provider-shaped fixtures.
- Synthetic fixtures are limited to narrow unit tests and are not accepted as release evidence.
- Capability answers match the engine/provider registry.
- The composer search and chat interpreter resolve assets/indicators consistently.

### UI And Artifact Actions

- Card actions live inside cards only.
- The composer does not duplicate active artifact actions.
- Superseded cards are visible history but not executable.
- Save/breakdown/refine actions are scoped to a concrete result artifact.
- Saved state survives reload.
- Raw error codes never appear as assistant answers.

### Codebase Health

- Major responsibilities live in focused modules.
- `ChatInterface.tsx`, runtime stage files, and provider modules do not become catch-all files.
- Cross-layer communication uses typed payloads.
- Tests protect boundaries without normalizing broken live behavior.
- Strategy labels are edge metadata derived from canonical IR, not the primary product brain.
- New strategy breadth plugs into IR, provider schemas, capability planner, compiler support, or artifact lifecycle rather than chat phrase branches.

### Release Evidence

- A QA evidence document lists every live browser script, prompt/action, visible card state, final answer, reload behavior, and pass/fail.
- Any failed browser script blocks completion.
- The final status is a matrix, not a narrative claim.

## Release-Grade Runtime Contract Checklist

The branch is close to production readiness only when this checklist is complete with fresh evidence.

## Fresh Evidence Ledger

This ledger is intentionally narrow. It records current proof without upgrading
the whole branch to "complete" until every release-gate scenario has browser
evidence.

### Automated Contract Evidence

- `poetry run pytest tests/agent_runtime/test_llm_interpreter.py tests/agent_runtime/test_interpret_stage.py tests/agent_runtime/test_conversation_stages.py tests/agent_runtime/test_runtime_semantic_boundaries.py -q --tb=short`
  - Result: 117 passed.
  - Covers: LLM-first interpretation boundaries, structured interpretation
    recovery, semantic integrity, staged conversation behavior, explicit
    supported rule repair, and prevention of vague momentum invention.
- `poetry run pytest tests/evals/test_chat_runtime_eval_manifest.py tests/test_chat_backtest_state_machine.py tests/test_chat_runtime_reload_guardrails.py tests/agent_runtime/test_conversational_contract_hardening.py tests/agent_runtime/test_confirmation_artifacts.py tests/agent_runtime/test_execute_launch_payload.py tests/agent_runtime/test_execute_recovery.py tests/agent_runtime/test_result_followups.py tests/agent_runtime/test_workflow.py -q --tb=short`
  - Result: 121 passed.
  - Covers: eight-bucket eval manifest, card-owned actions, launch payload
    identity, stale action rejection, reload guardrails, failed-action recovery,
    result follow-ups, save/breakdown/refine contracts, and workflow integration.
- `poetry run pytest tests/test_chat_runtime_reload_guardrails.py::test_newer_confirmation_metadata_overrides_stale_result_checkpoint_for_text_turn tests/test_chat_runtime_reload_guardrails.py::test_visible_confirmation_metadata_fallback_carries_text_turn_context tests/test_chat_runtime_reload_guardrails.py::test_stale_confirmation_action_id_does_not_execute tests/agent_runtime/test_conversational_contract_hardening.py::test_natural_language_approval_executes_only_after_confirmation_card -q --tb=short`
  - Result: 4 passed.
  - Covers: the live-discovered stale checkpoint bug where an older result
    could override a newer visible confirmation card during text turns.
- `poetry run ruff check src/argus/api/routers/agent.py src/argus/domain/backtesting/rules/intent_normalizer.py src/argus/agent_runtime/stages/execute.py src/argus/agent_runtime/strategy_contract.py src/argus/agent_runtime/stages/interpret_actions.py src/argus/agent_runtime/signal_rule_repair.py tests/test_chat_runtime_reload_guardrails.py tests/agent_runtime/test_llm_interpreter.py tests/agent_runtime/test_execute_launch_payload.py tests/agent_runtime/test_execute_recovery.py`
  - Result: all checks passed.
- `cd web && bun run lint components/chat/ChatInput.tsx components/chat/ChatInterface.tsx components/chat/StrategyConfirmationCard.tsx components/chat/StrategyResultCard.tsx`
  - Result: passed.
- `cd web && bun test __tests__/chat-composer-model.test.ts __tests__/alpha-frontend.test.ts`
  - Result: 48 passed.
  - Covers: composer model, structured cards, card-scoped actions, result
    presentation, and frontend guardrail string checks.
- `poetry run pytest tests/agent_runtime/test_interpret_stage.py::test_supported_indicator_simplification_preserves_user_threshold_overrides tests/agent_runtime/test_interpret_stage.py::test_active_artifact_rule_answer_repairs_and_preserves_prior_asset tests/agent_runtime/test_llm_interpreter.py::test_llm_interpreter_maps_indicator_threshold_fields_to_strategy_parameters tests/agent_runtime/test_llm_interpreter.py::test_llm_interpreter_promotes_typed_indicator_values_from_extra_parameters tests/agent_runtime/test_llm_interpreter.py::test_llm_interpreter_merges_refinement_with_pending_strategy -q --tb=short`
  - Result: 5 passed.
  - Covers: active-artifact rule repair, preservation of prior asset/date
    context when the LLM underfills an artifact edit, indicator threshold
    promotion, and refinement merging.
- `poetry run pytest tests/agent_runtime/test_interpret_stage.py::test_result_refinement_reply_forks_latest_result_into_new_draft tests/test_chat_runtime_reload_guardrails.py::test_refine_strategy_action_uses_latest_result_context_after_reload tests/test_chat_runtime_reload_guardrails.py::test_refine_strategy_text_reply_uses_persisted_refinement_context_after_reload tests/test_chat_runtime_reload_guardrails.py::test_refine_strategy_action_uses_card_run_before_runtime_memory -q --tb=short`
  - Result: 4 passed.
  - Covers: result-refinement forks a new artifact from immutable run facts,
    persisted refinement context survives runtime reset/reload, free-text
    refinement replies keep prior asset/date context, and result-card action ids
    outrank stale runtime memory.
- `poetry run pytest tests/agent_runtime/test_conversational_contract_hardening.py::test_refine_strategy_result_action_prompts_for_change_without_llm tests/test_chat_runtime_reload_guardrails.py::test_cancel_confirmation_action_persists_invisible_artifact_tombstone tests/test_chat_runtime_reload_guardrails.py::test_canceled_confirmation_does_not_recover_older_card -q --tb=short`
  - Result: 3 passed.
  - Covers: result-card refine action prompts without a model round-trip,
    cancel persists a terminal artifact tombstone, and cancelled confirmations do
    not resurrect older cards after reload.
- `poetry run pytest tests/domain/test_engine_launch.py::test_launch_request_limits_cadence_to_dca tests/domain/test_engine_launch.py::test_dca_adapter_supports_quarterly_cadence tests/domain/test_engine_launch.py::test_build_signals_supports_quarterly_dca_cadence tests/test_openrouter_policy.py::test_explicit_model_interpreter_plans_result_refinement_before_accepting_prose tests/agent_runtime/test_interpret_stage.py::test_result_refinement_reply_forks_latest_result_into_new_draft tests/test_engine_signals.py::test_dca_accumulation_signals_biweekly tests/test_slot_normalizer.py::test_normalizes_locale_cadence_values -q --tb=short`
  - Result: 7 passed.
  - Covers: explicit-model interpreter symmetry, result-refinement fork
    planning, biweekly recurring-buy execution, calendar-quarter recurring-buy
    execution, and cadence capability normalization without a validation shim.
- `poetry run ruff check tests/domain/test_engine_launch.py src/argus/domain/cadences.py src/argus/domain/engine_launch/cadence.py src/argus/domain/engine_launch/models.py src/argus/domain/engine_launch/adapter.py src/argus/domain/strategy_capabilities.py src/argus/domain/backtesting/signals.py src/argus/agent_runtime/llm_interpreter.py tests/test_openrouter_policy.py tests/agent_runtime/test_interpret_stage.py tests/test_engine_signals.py tests/test_slot_normalizer.py`
  - Result: all checks passed.
  - Covers: the shared cadence registry, launch model, engine signal builder,
    strategy capability surface, and interpreter acceptance-gate refactor.
- `cd web && bun test __tests__/chat-artifact-history.test.ts`
  - Result: 12 passed.
  - Covers: confirmation action tombstones, reload-safe cancelled card state,
    terminal artifact status preservation, stale-action recovery immunity, and
    transient edit/cancel priority.
- `cd web && bun run lint -- components/chat/ChatInterface.tsx components/chat/artifact-history.ts __tests__/chat-artifact-history.test.ts`
  - Result: passed.
  - Covers: frontend artifact-history extraction and card state normalization.
- `poetry run pytest tests/test_openrouter_policy.py::test_explicit_model_interpreter_plans_result_refinement_before_accepting_prose tests/agent_runtime/test_interpret_stage.py::test_result_refinement_reply_forks_latest_result_into_new_draft tests/agent_runtime/test_conversational_contract_hardening.py::test_refine_strategy_result_action_prompts_for_change_without_llm tests/agent_runtime/test_interpret_stage.py::test_capability_question_answer_uses_indicator_registry_not_llm_copy -q --tb=short`
  - Result: 4 passed.
  - Covers: explicit-model interpreter symmetry, result-refinement fork
    planning, result-card refine action handoff, and capability Q&A grounded in
    the executable indicator registry instead of stale LLM copy.
- `poetry run ruff check src/argus/agent_runtime/capabilities/answers.py src/argus/agent_runtime/stages/interpret.py src/argus/agent_runtime/stages/interpret_types.py src/argus/agent_runtime/llm_interpreter.py src/argus/agent_runtime/llm_interpreter_types.py tests/agent_runtime/test_interpret_stage.py`
  - Result: all checks passed.
  - Covers: capability answer module integration, structured schema fields, and
    the LLM-to-runtime capability focus handoff.
- `poetry run pytest tests/agent_runtime/test_interpret_stage.py::test_underperformance_followup_corrects_false_premise_when_run_outperformed tests/agent_runtime/test_result_followups.py::test_result_followup_replaces_llm_answer_that_contradicts_positive_delta -q --tb=short`
  - Result: 2 passed.
  - Covers: result follow-ups correct false underperformance premises from run
    facts instead of accepting contradictory LLM prose.

- `poetry run pytest tests/domain/test_indicator_registry.py tests/domain/test_engine_launch.py::test_indicator_threshold_adapter_returns_envelope_card_and_context tests/domain/test_engine_launch.py::test_adapter_accepts_registry_bounded_indicator_threshold_shape tests/domain/test_engine_launch.py::test_adapter_uses_indicator_period_from_threshold_rules tests/domain/test_engine_launch.py::test_adapter_maps_common_crossover_payload_to_rule_spec tests/domain/test_engine_launch.py::test_build_signals_preserves_rule_template_branches_after_rsi -q --tb=short`
  - Result: 12 passed.
  - Covers: executable indicator defaults/overrides, draft-only catalog status
    for indicators without execution specs, registry-bounded threshold launch,
    rule-spec launch validation, and generic rule-template execution branches.
- `poetry run pytest tests/agent_runtime/test_interpret_stage.py::test_interpret_passes_raw_message_to_llm_without_regex_normalization tests/agent_runtime/test_interpret_stage.py::test_pending_date_answer_uses_structured_interpreter_before_updating_draft -q --tb=short`
  - Result: 2 passed.
  - Covers: normal user text reaches the structured interpreter before draft
    updates and is not pre-normalized through regex or phrase gates.
- `poetry run pytest tests/agent_runtime/test_strategy_contract.py::test_extracted_fields_do_not_force_unknown_strategy_contract tests/agent_runtime/test_strategy_contract.py::test_extracted_fields_do_not_accept_unknown_rule_spec_as_signal_strategy tests/agent_runtime/test_strategy_contract.py::test_extracted_fields_resolve_indicator_threshold_from_registry -q --tb=short`
  - Result: 3 passed.
  - Covers: strategy family names are not accepted as the conversational contract
    for unknown future families such as sentiment, unknown rule specs do not
    become executable signal strategies, and executable labels are derived only
    from registry-backed fields.
- `poetry run pytest tests/agent_runtime/test_llm_interpreter.py::test_signal_rule_plan_draft_only_routes_to_unsupported_recovery tests/agent_runtime/test_llm_interpreter.py::test_focused_strategy_extraction_prompt_preserves_draft_only_strategy_fields tests/agent_runtime/test_llm_interpreter.py::test_unsupported_free_text_strategy_response_needs_context_repair tests/agent_runtime/test_conversation_stages.py::test_clarifier_system_prompt_guides_unsupported_recovery_context tests/agent_runtime/test_conversation_stages.py::test_clarify_unsupported_recovery_uses_generator_over_prefilled_copy -q --tb=short`
  - Result: 5 passed.
  - Covers: unsupported and draft-only ideas preserve asset, period, and rule
    context, avoid fake execution claims, and route through recovery copy grounded
    in capability constraints instead of stale prefilled prose.
- `poetry run pytest tests/agent_runtime/test_execute_recovery.py::test_execute_recovers_visible_dca_confirmation_when_market_data_is_unavailable tests/agent_runtime/test_execute_recovery.py::test_workflow_rebuilds_failed_action_retry_as_confirmation tests/agent_runtime/test_interpret_stage.py::test_retry_failed_action_rebuilds_confirmation_instead_of_auto_running tests/test_chat_runtime_reload_guardrails.py::test_retry_after_reload_carries_latest_failed_action_reference tests/test_chat_runtime_reload_guardrails.py::test_failed_action_fallback_is_superseded_by_newer_completed_result -q --tb=short`
  - Result: 5 passed.
  - Covers: failed actions persist retryable launch payloads, natural retry
    rebuilds a confirmation instead of auto-running quota-bearing work, reload
    recovers the failed-action reference, and newer completed results supersede
    stale failures.
- `poetry run pytest tests/section3/test_market_data_provider.py::test_live_provider_mode_fails_closed_when_provider_catalog_unavailable tests/section3/test_market_data_provider.py::test_synthetic_unit_fixture_is_explicitly_opted_in tests/section3/test_market_data_provider.py::test_recorded_provider_fixture_uses_provider_shaped_payloads tests/agent_runtime/test_llm_interpreter.py::test_llm_interpreter_validates_asset_class_with_alpaca_resolver -q --tb=short`
  - Result: 4 passed.
  - Covers: provider modes share resolver shapes, live mode fails closed when the
    provider catalog is unavailable, recorded fixtures use provider-shaped
    payloads, synthetic fixtures are opt-in only, and LLM asset candidates still
    pass through deterministic provider validation.
- `cd web && bun test __tests__/alpha-frontend.test.ts __tests__/chat-artifact-history.test.ts`
  - Result: 53 passed.
  - Covers: card-scoped action rendering, duplicated composer-action prevention,
    artifact hydration, saved-state feedback, copy feedback, jump-to-latest
    behavior, final-only feedback controls, status hiding after assistant tokens
    begin, and cancelled/superseded confirmation history.
- `cd web && bun run lint -- components/chat/ChatInterface.tsx components/chat/ChatMessage.tsx __tests__/alpha-frontend.test.ts`
  - Result: passed.
  - Covers: the trust-polish frontend changes and artifact-history integration.

### Direct Runtime Evidence

- Stream prompt:
  `Test Nvidia over the past year when the 50-day moving average crosses above the 200-day moving average.`
  - Result: `await_approval`.
  - Confirmation card: `NVDA signal strategy`, `Ready to run`, asset `NVDA`,
    period `past year`, entry `50-day SMA crosses above 200-day SMA`, exit
    `50-day SMA crosses below 200-day SMA`.
  - Payload: executable `rule_spec` present for entry and exit; launch validation
    marked the card ready to run.
- Stream prompt after a visible confirmation card:
  `yes run it`
  - Result: no quota-bearing execution.
  - Assistant answer: directs the user to use the visible `Run backtest` card
    action.
  - Card identity stayed stable rather than rotating a new draft.
- Direct streaming runtime probe:
  - Prompt: `Backtest buy and hold Apple over the past year.`
  - Action: sent the exact persisted `Run backtest` confirmation action.
  - Result: completed `AAPL Buy and Hold` run with result actions.
  - Action: sent the exact persisted `Refine strategy` result action.
  - Reply: `i want to do recurrent biweekly buys of 500 bucks instead`.
  - Result: new `AAPL recurring buys` confirmation card, `Ready to run`, with
    `Cadence: Biweekly` and `Contribution: $500`; no prose-only fake update.

### Live Browser Evidence

2026-05-15 update: the in-app Browser path is usable for visual inspection,
card-scoped clicks, sidebar/history hydration, screenshots, and reload proof
after rebooting the local servers and reconnecting the browser session. In the
current Codex browser session, free-text entry into the contenteditable composer
is still blocked by the browser clipboard bridge, so free-text setup evidence is
split between API-seeded runtime turns and browser-hydrated/card-clicked visual
verification. Do not treat API-seeded setup as a replacement for the final live
browser free-text matrix.

- Correct failure discovered and fixed:
  - In a long mixed QA thread, a visible TSLA `Run backtest` card action was
    rejected as stale even though it was the newest visible card.
  - Root cause: stale latest-result checkpoint state could outrank newer visible
    confirmation metadata for text turns.
  - Fix: persisted confirmation metadata now outranks stale result checkpoint
    fallback for plain text turns; stale action ids still reject.
- Fresh golden card/action/result flow:
  - Prompt: `could you check if holding Tesla for about a year would have beaten SPY?`
  - Visible card after reload: `TSLA buy and hold`, `Ready to run`, one visible
    card-scoped `Run backtest`, no duplicate composer-level action chips.
  - Natural text after the card: `yes run it`.
  - Result: no backtest executed; assistant directed the user to the visible
    card action.
  - Action: clicked the visible browser `Run backtest` button.
  - Result card: `TSLA Buy and Hold`, `Simulation Complete`, result actions
    visible, no raw `missing_rule_group`, and no duplicate result card.
  - Result answer: TSLA returned `+29.3%` versus SPY `+26.7%`, with a `+2.6 pts`
    gap and explicit assumptions.
- Reload continuity:
  - Reload after the ready card preserved the same card and one card-scoped run
    action.
  - Reload after the completed result showed zero active `Run backtest` buttons
    and preserved the result card/actions.
  - Follow-up after result, `what exactly did you test?`, answered from latest
    run facts: TSLA, buy-and-hold, exact dates, SPY benchmark, return, benchmark
    return, gap, and assumptions.
- Composer discovery:
  - `@` discovery showed both assets and indicators, including `SMA`, `RSI`,
    runnable `MACD`, and draft-only `ATR`.
  - This proves the regression where inline search returned assets only is fixed
    for the current capability surface.
- Fresh browser-typed continuity/result flow:
  - Prompt: `Test buying and holding Apple over the past year.`
  - Visible card: `AAPL buy and hold`, `Ready to run`, period `past year`.
  - Prompt: `Actually make it Nvidia.`
  - Visible card: `NVDA buy and hold`, same period preserved.
  - Prompt: `Use the last 6 months instead.`
  - Visible card: `NVDA buy and hold`, period updated to `past 6 months`.
  - Prompt: `What assumptions are you using?`
  - Assistant answered from the visible draft assumptions: `$1,000`, `1D bars`,
    no fees/slippage, `Benchmark: SPY`.
  - Prompt: `yes run it`
  - Assistant did not execute; it directed the user to the visible
    `Run backtest` button.
  - Browser action: clicked card-scoped `Run backtest`.
  - Result card: `NVDA Buy and Hold`, `Simulation Complete`, return `+21.9%`,
    SPY `+11.4%`, gap `+10.4 pts`, max drawdown `-15.7%`.
  - Follow-up: `What exactly did you test?` answered from latest run facts.
  - Follow-up regression found: `What was the max drawdown?` initially answered
    with the generic performance fallback because interpreter focus drift plus a
    structured-composer validation failure suppressed the risk fact.
  - Fix: result follow-up fallback now produces fact-complete general answers and
    performance fallbacks include the core risk fact. Rechecked in browser:
    `What was the max drawdown?` answered with `The max drawdown was -15.7%`.
  - Result actions: `Show a breakdown` added one breakdown message without
    duplicating the result card; `Save strategy` changed the card state to
    disabled `Saved`; `Refine strategy` produced a follow-up prompt asking what
    to change.
- Reload: preserved result card, saved state, result actions, breakdown, and
  post-reload follow-up context. `Why did this result happen after reload?`
  answered from the latest run facts and included return, benchmark, gap, max
  drawdown, and caveat.
- Fresh active-artifact repair QA:
  - Prompt: `What if I bought Tesla after big drops?`
  - Follow-up: `technical thing like RSI, buy when it gets to 20 or lower, sell when 60 or higher, past 3 months`
  - Result: the active TSLA draft was preserved, the vague dip idea was refined
    into an executable RSI rule, user thresholds were preserved as RSI(14)
    `<= 20` entry and `>= 60` exit, and the card became `Ready to run`.
  - Card action: `Run backtest` executed from the confirmation payload and
    produced a result card instead of `missing_rule_group`.
  - Result truth: return `0.0%` because no entry trade fired; the result facts
    explicitly stated the strategy stayed in cash, which is the correct
    historical outcome rather than a market-flat inference.
- Fresh result-action API/browser-backed QA:
  - `Show a breakdown` added one breakdown response without duplicating the
    result card.
  - `Save strategy` returned and persisted a saved strategy id.
  - `Refine strategy` created a pending strategy from the completed run config
    and asked what to change, instead of losing the result.
- Fresh cancel/reload browser QA:
  - Prompt: `Backtest buy and hold Apple over the past year.`
  - Action: clicked the card-scoped `Cancel` action through the persisted action
    payload.
  - Reload behavior: the confirmation card hydrated as `Draft canceled`, had no
    runnable actions, and did not show a noisy cancel transcript.
  - Root cause fixed: frontend history normalization now lives in
    `artifact-history` and preserves terminal confirmation states instead of
    reactivating the latest card after reload.
- Fresh API-seeded + browser-clicked confirmation lifecycle QA:
  - API-seeded prompt: `Backtest buy and hold Apple over the past year.`
  - API-seeded card action: `Change dates`.
  - API-seeded reply: `July 3rd to August 13th in 2024`.
  - Browser-loaded visible card: `AAPL buy and hold`, `Ready to run`, period
    `July 3, 2024 - August 13, 2024`, with exactly one visible `Run backtest`
    button and one card-owned action set.
  - Browser action: clicked `Cancel`.
  - Browser result: card changed to `Draft canceled`, runnable action buttons
    disappeared, reload preserved the terminal state, and no user-visible cancel
    transcript was added.
- Fresh browser-clicked result-action lifecycle QA after extracting result
  action history into `artifact-history`:
  - API-seeded prompt: `Backtest buy and hold Apple over the last 90 days.`
  - Browser-loaded visible card: `Ready to run` with one `Run backtest`.
  - Browser action: clicked card-owned `Run backtest`.
  - Browser result: `Simulation Complete`, result actions visible, no raw
    `missing_rule_group`, and no duplicate result card.
  - Browser action: clicked `Show a breakdown`.
  - Browser result: one breakdown response appeared, result card count remained
    one, and `Show a breakdown` was consumed.
  - Browser action: clicked `Save strategy`.
  - Browser result: visible state changed to `Saved`; `Save strategy` was
    consumed.
  - Browser action: clicked `Refine strategy`.
  - Browser result: Argus asked what to change and did not say it lacked a
    completed result.
  - Reload result: completed result, saved state, breakdown, and refine prompt
    persisted without the prior missing-result error.
- Fresh result-refinement contract evidence:
  - Browser-observed failure: after `Refine strategy`, the reply `i want to do
    recurrent biweekly buys of 500 bucks instead` produced prose claiming the
    strategy was updated but did not create a new card.
  - Root cause: explicit-model structured interpretation accepted a prose-only
    response before running the same artifact-edit planning gate used by the
    default candidate path.
  - Fix: all structured interpretation paths now pass through the same runtime
    acceptance gate before returning to the graph.
  - Expected runtime behavior: completed result remains immutable; refinement
    forks a pending draft from the latest result snapshot; unchanged asset/date
    context is preserved; executable refinements create a new confirmation card.
  - Related capability truth: biweekly recurring buys are now a supported DCA
    cadence in the shared cadence registry and engine signal builder, not a
    one-off chat phrase.
  - Direct runtime proof: the same AAPL result-refinement sequence now returns
    a new `AAPL recurring buys` confirmation artifact, `Ready to run`, with
    rows for `Cadence: Biweekly` and `Contribution: $500`.
  - Browser-hydration proof: opening the persisted run thread from the sidebar
    shows the result refine prompt, the user refinement, and the new
    `AAPL recurring buys` confirmation card with card-owned actions. The old
    completed result remains above it as immutable evidence.
  - Live DOM proof after user stress testing: the visible conversation contains
    the original `AAPL Buy and Hold` completed result, the user action transcript
    `Refine strategy`, the refinement prompt, the free-text change
    `i want to do recurrent biweekly buys of 500 bucks instead`, the new
    `AAPL recurring buys` artifact with `Cadence: Biweekly` and
    `Contribution: $500`, and a separate completed `DCA Accumulation` result.
    This confirms refinement forks forward from the prior snapshot rather than
    editing the old completed result or saving over an existing strategy.

### Still Unproven Or Incomplete

- Full QA 1-14 browser matrix is not complete yet. Browser free-text `fill`
  and `type` still hit a Codex clipboard bridge issue in the current session, so
  this pass used API seeding for setup and real browser hydration, clicks, and
  reloads for card/action verification where needed.
- Trust polish needs desktop and mobile browser evidence for scroll behavior,
  final-only controls, and copy feedback.
- Natural retry recovery has automated coverage, but still needs a clean live
  failed-action scenario and reload proof.
- Capability Q&A now has focused runtime proof that indicator support answers
  come from the executable registry rather than stale LLM prose. Full
  schema-driven pandas-ta expansion remains intentionally gated by execution
  specs across advertised indicator/rule families.
- Result actions have fresh proof for breakdown, save, and refine; cancellation
  now has browser reload proof. Change-date has API-seeded/browser-hydrated proof.
  Change-asset and adjust-assumptions still need the full scripted browser
  matrix.
- Spanish smoke and mixed provider asset resolution still need browser evidence.

### Runtime Contract

- [x] Normal user text reaches LLM-first interpretation before deterministic routing.
- [x] Structured interpretation produces or patches canonical investing-idea IR.
- [x] Strategy type/family is derived edge metadata, not the chat routing source.
- [x] Capability planner outcome is persisted or traceable for the active artifact.
- [x] `Ready to run` requires validated executable payload.
- [x] Typed "run it" intent does not execute quota-bearing backtests; the card action does.

### Artifact Contract

- [x] One active artifact owns one visible card state.
- [x] One active artifact owns one action set.
- [x] Actions carry artifact/run ids.
- [x] Superseded artifacts remain visible history but cannot execute.
- [x] Reload hydrates the same artifact status and actions.
- [x] Failed actions preserve retry context and user-safe recovery.

### Capability Contract

- [x] Capability Q&A answers from registry/provider/compiler truth.
- [x] Composer search and chat resolution use the same asset/indicator capability interfaces.
- [x] Provider modes use the same resolver/registry/planner/compiler/artifact shapes.
- [x] Unsupported or draft-only ideas are preserved and explained without fake execution claims.
- [x] Indicators marked executable support defaults and user overrides.
- [x] Rule patterns marked executable compile and run through the engine.

### Result Contract

- [x] Completed runs create immutable result facts.
- [x] Follow-ups after result use latest run facts.
- [x] False premises are corrected.
- [x] Breakdown is fact-grounded and non-duplicative.
- [x] Save strategy is idempotent and persists visible saved state.
- [x] Refine strategy starts from prior result config and creates a new draft artifact.

### UI Contract

- [x] Card actions render inside cards only.
- [x] Composer does not duplicate active artifact actions.
- [x] Raw internal codes never appear to users.
- [x] Status and streamed answer do not compete visually.
- [x] Feedback/copy controls appear only when the answer is final.
- [x] Copy shows visible success/failure feedback.
- [x] Scroll does not yank while the user is reading older content.

### Evaluation Contract

- [x] Scenario manifest covers the eight buckets and the live browser QA matrix.
- [x] Hard contract checks run before LLM-judge answer scoring.
- [ ] Browser trajectory checks cover prompt/action/card/final/reload behavior.
- [ ] Correct failures are documented as pass cases when they preserve capability truth.
- [ ] Any `must_pass` scenario failure blocks completion.
- [ ] Final evidence is a matrix with links or notes for every QA script.

## Stop Conditions

Stop and consult the user if any implementation requires:

- changing product scope,
- adding a second orchestrator,
- moving away from LangGraph runtime ownership,
- changing persistence ownership away from Supabase,
- adding embeddings/vector memory,
- making all pandas-ta indicators appear executable without full specs,
- supporting shorting, leverage, mixed-asset execution, arbitrary formulas, or real trading,
- weakening tests to normalize broken browser behavior,
- expanding a module into an oversized catch-all file.

## Self Review 1: Canon Alignment

Result: pass after adding explicit stop conditions.

Checked against:

- `docs/PRODUCT.md`: keeps chat-first, trust-first, simple validation.
- `docs/ARCHITECTURE.md`: preserves LangGraph, thin FastAPI, Supabase persistence.
- `docs/API_CONTRACT.md`: uses additive metadata and reproducible run state.
- `docs/DATA_MODEL.md`: saves strategies from completed runs and keeps run config canonical.
- `.agent/designs/argus/DESIGN.md`: keeps card-scoped, low-clutter, conversation-first UX.

No canon doc change is required by this spec. Any future canon change must be minimal and user-approved.

## Self Review 2: Live QA Coverage

Result: pass after adding QA 4, QA 5, QA 11, and QA 12.

The spec covers:

- duplicate action chips,
- ready-but-not-executable cards,
- vague momentum invention,
- natural retry loss,
- unsupported MACD overstatement,
- simple buy-and-hold fallback failure,
- shallow result follow-ups,
- save state ambiguity,
- reload preservation,
- crypto comparison,
- localization smoke.

## Self Review 3: Drift And Modularity

Result: pass after adding separation-of-concerns gates, module responsibility rules, prohibited shapes, and module boundaries.

The spec rejects:

- patching by edge-case phrases,
- hardcoded mock-only resolver shortcuts,
- giant runtime scripts,
- second orchestrators,
- UI reconstruction from text,
- test changes that hide browser failures.
- generic helpers that hide provider/runtime/persistence/UI coupling,
- bloated chat components that own artifact semantics, hydration, card actions, composer suggestions, and stream state at once.

The spec requires focused modules, typed cross-layer payloads, and clean ownership boundaries before implementation.

## Self Review 4: Indicator Scope Honesty

Result: pass after adding capability tiers and the canonical IR rule.

The spec now frames pandas-ta as a schema-driven provider, not a hand-curated dead end. It allows broad search/education, schema-driven drafting, and broad execution where parameter schemas, output roles, rule semantics, validation, engine integration, and browser QA are complete.

This matches production readiness better than claiming breadth without execution truth.

It also prevents the current supported labels from becoming permanent product walls. `buy_and_hold`, recurring buy, RSI threshold, moving-average crossover, and future sentiment strategies are all represented through IR semantics first, with labels derived later.

## Self Review 5: Provider Backbone Coverage

Result: pass after adding runtime backbone, schema-driven pandas-ta provider, and provider-aware asset catalog sections.

The spec now covers:

- LLM as natural-language brain.
- Capability tools as deterministic truth providers.
- Engine/compiler as deterministic hands.
- Guardrails before `Ready to run`.
- Artifact state as reload/retry/follow-up memory.
- pandas-ta schemas, defaults, output roles, and parameter overrides.
- asset provider overlap and complement behavior across Alpaca, Kraken, and fixtures.

This closes the gap where the prior version could still be read as a narrow manually promoted indicator list or a hardcoded asset resolver cleanup.

## Self Review 6: Anti-Pattern And Sequencing Review

Result: pass after adding the missing-question section, anti-pattern list, vertical slices, five next moves, release-grade checklist, and expected end state.

The most important missing question was the production slice question: what is the smallest end-to-end slice that proves the architecture before expanding indicator and provider breadth?

The spec now prevents:

- a big-bang rewrite,
- an implementation that claims production readiness without a working happy path at each slice,
- expanding pandas-ta/provider scope before the artifact spine is truthful,
- treating strategy labels as the primary conversational contract,
- building a deterministic evaluation suite that ignores non-deterministic trajectories,
- ending without explicit expectations for runtime, strategy execution, capability truth, UI actions, codebase health, and release evidence.

## Self Review 7: Evaluation Spine Coverage

Result: pass after adding the lightweight evaluation spine and release-grade runtime contract checklist.

The spec now defines how deterministic checks, browser trajectory checks, and LLM-as-judge quality checks work together:

- deterministic checks own runtime truth,
- browser checks own product truth,
- LLM judges own answer quality only after runtime truth passes.

This avoids two failure modes:

- green unit tests that miss broken browser behavior,
- subjective browser impressions with no repeatable artifact/action assertions.

## Final Acceptance Statement

This second pass is complete only when the live browser QA matrix passes on the implemented branch and the UI no longer shows duplicate artifact actions, raw internal errors, unsupported capability overstatements, stale retries, or result follow-ups detached from the latest run.
