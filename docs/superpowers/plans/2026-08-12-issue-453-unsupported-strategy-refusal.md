# Issue #453 Cause-aware Strategy Refusal Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task by task.

**Goal:** Make the guest chat distinguish supported DCA, invalid starting-capital bounds, true unsupported strategy logic, and incomplete extraction without exposing untyped interpreter text or acknowledging an invalid value.

**Architecture:** Keep the structured LLM as the language interpreter, then fail closed through existing typed runtime boundaries. A focused interpretation repair gets one chance when a bare unsupported verdict contradicts current strategy evidence or a pending numeric answer. The confirmation stage remains the canonical engine-envelope validator. Clarification metadata carries typed bounds, while backend and web display projections ignore generic `raw_value` subjects. The unsupported admission boundary always discards the primary interpreter's prose so the cause-aware clarification pass owns the visible answer.

**Tech Stack:** Python 3.10, Pydantic, LangGraph runtime stages, pytest, TypeScript, React/Next.js, i18next, Bun test, Playwright.

---

### Task 1: Capture the four untouched-base regressions

**Files:**

- Modify: `tests/agent_runtime/test_llm_interpreter_artifact_capability_repairs.py`
- Modify: `tests/agent_runtime/test_options_semantic_admission.py`
- Modify: `tests/agent_runtime/test_validation_failure_copy.py`
- Modify: `tests/agent_runtime/test_conversation_stages.py`
- Modify: `web/__tests__/chat-recovery-display.test.ts`

**Step 1: Add the supported DCA contradiction regression**

Add a mocked structured-model trajectory for the Spanish starter
`¿Y si hubiera comprado Coca-Cola cada mes durante cinco años?` where the
primary model returns a bare unsupported verdict and the focused extraction
returns `dca_accumulation`, `KO`, monthly cadence, and a five-year historical
window. Assert the readied response is a supported DCA clarification for only
the recurring amount, with no unsupported constraint or refusal prose.

**Step 2: Add the pending `$500` repair regression**

Model a pending buy-and-hold strategy for NFLX whose requested field is
`capital_amount`. Make the primary model return the production-shaped bare
unsupported verdict with `user_goal_summary="User wants to invest $500"` and
the Spanish acknowledgment. Make focused extraction return the typed amount.
Assert the ready response carries `500`, drops the acknowledgment, and continues
through the supported strategy route.

**Step 3: Change the unsupported admission prose regression**

Update the existing admission test so a still-unsupported strategy retains its
typed constraint but `stage_patch.assistant_response` is absent. This proves the
dedicated clarification stage, not an unvalidated primary acknowledgment, owns
the visible recovery.

**Step 4: Add the bounds recovery regression**

Build a complete buy-and-hold NFLX draft with `$500` starting capital. Run
`confirm_stage`, then the degraded `clarify_stage`. Assert there is no
confirmation artifact, the cause is `unsupported_starting_capital`, typed bounds
equal `MIN_STARTING_CAPITAL` and `MAX_STARTING_CAPITAL`, and the fallback names
the `$1,000` minimum without saying the strategy is unsupported.

**Step 5: Reverse the raw-subject expectations**

Backend and web tests must assert that `User wants to invest $500`, `MACD golden
cross`, `BTC_USDT`, and other generic raw strings never become sentence
subjects. Keep dedicated typed time-granularity behavior unchanged. Assert both
English and es-419 output use the generic typed capability or incomplete-rule
copy.

**Step 6: Run the new tests and record RED evidence**

Run:

```bash
poetry run pytest --no-cov tests/agent_runtime/test_llm_interpreter_artifact_capability_repairs.py tests/agent_runtime/test_options_semantic_admission.py tests/agent_runtime/test_validation_failure_copy.py tests/agent_runtime/test_conversation_stages.py -q -k 'issue_453 or unsupported_request_turn_act_contradiction or raw_value'
bun test web/__tests__/chat-recovery-display.test.ts
```

Expected: failures separately expose the unsupported DCA route, preserved
acknowledgment, missing typed bounds/correct copy, and raw-value interpolation.
Record command, base SHA, failing assertions, and classification under
`docs/reports/evidence/453/baseline.md` using `apply_patch`.

### Task 2: Repair bare unsupported verdicts through the existing LLM boundary

**Files:**

- Modify: `src/argus/agent_runtime/interpreter/focused_extraction.py`
- Modify: `src/argus/agent_runtime/llm_interpreter.py`
- Test: `tests/agent_runtime/test_llm_interpreter_artifact_capability_repairs.py`

**Step 1: Define the narrow repair predicate**

Permit focused extraction for a constraint-free `unsupported_request` only when
the current turn has material execution evidence. For pending strategy context,
require both a pending requested field and current-turn evidence. Keep the
focused LLM responsible for deciding whether the turn is actually a testable
strategy; add no localized phrase or regex strategy classifier.

**Step 2: Prevent premature shape acceptance**

Make `_structured_interpretation_has_required_shape` reject a bare unsupported
response when it is answering an active pending execution need with material
current-turn evidence. This forces the existing focused repair before admission
can manufacture an unsupported-strategy constraint from a model summary.

**Step 3: Verify the focused repair tests GREEN**

Run:

```bash
poetry run pytest --no-cov tests/agent_runtime/test_llm_interpreter_artifact_capability_repairs.py -q -k 'issue_453 or supported_strategy_capability'
```

Expected: the Coca-Cola turn becomes DCA, the pending `$500` answer remains a
typed capital update, and existing true capability-conflict tests stay green.

### Task 3: Make admission and launch validation cause-safe

**Files:**

- Modify: `src/argus/agent_runtime/interpreter/unsupported_admission.py`
- Modify: `src/argus/agent_runtime/stages/launch_validation_recovery.py`
- Modify: `src/argus/agent_runtime/stages/confirm.py` only if cause-specific raw fact selection is required
- Test: `tests/agent_runtime/test_options_semantic_admission.py`
- Test: `tests/agent_runtime/test_conversation_stages.py`

**Step 1: Suppress unvalidated interpreter prose**

At the unsupported admission boundary, always set `assistant_response` to
`None`, matching recognized non-executable and future-performance admission.
The later clarification stage still carries the typed constraint and runnable
choices.

**Step 2: Add canonical typed capital bounds**

Add numeric `minimum` and `maximum` facts to the
`unsupported_starting_capital` constraint, deriving both from
`MIN_STARTING_CAPITAL` and `MAX_STARTING_CAPITAL`. Do not restate magic values.
Preserve DCA's positive-contribution floor exemption.

**Step 3: Verify admission and confirm-stage tests GREEN**

Run:

```bash
poetry run pytest --no-cov tests/agent_runtime/test_options_semantic_admission.py tests/agent_runtime/test_conversation_stages.py -q -k 'issue_453 or unsupported_request_turn_act_contradiction'
```

Expected: no acknowledgment survives a blocked verdict; `$500` buy-and-hold
reaches launch validation and returns typed canonical bounds without a card.

### Task 4: Project cause-aware recovery without raw subjects

**Files:**

- Modify: `src/argus/agent_runtime/clarification_contract.py`
- Modify: `src/argus/agent_runtime/llm_clarifier.py`
- Modify: `web/lib/chat-recovery-display.ts`
- Modify: `web/public/locales/en/common.json`
- Modify: `web/public/locales/es-419/common.json`
- Test: `tests/agent_runtime/test_validation_failure_copy.py`
- Test: `tests/agent_runtime/test_conversation_stages.py`
- Test: `web/__tests__/chat-recovery-display.test.ts`

**Step 1: Remove generic raw subjects in backend fallback**

For generic unsupported recovery, ignore `_unsupported_raw_value` and refer to
the typed rule category only. Preserve the dedicated typed timeframe and
future-performance branches. Keep uncategorized extraction on the existing
"What rule should I test?" path.

**Step 2: Carry typed bounds through clarification metadata**

Project numeric `minimum` and `maximum` from the capital constraint into the
typed clarification payload. The clarifier prompt must state that
`unsupported_starting_capital` is a validation bound, not a strategy capability
limit, and must ask for a value in range.

**Step 3: Remove the raw locale variants and add bounds copy**

Delete only:

- `chat.clarification.unsupported_recovery_with_raw_value`
- `chat.clarification.unsupported_recovery_with_raw_value_for_asset`

Add matching English and es-419 capital-bound copy derived from the typed
minimum and maximum. Use no em dash. Reconcile locale edits as a union with the
parallel research lane.

**Step 4: Make the web projection fail closed**

The generic unsupported renderer selects only generic or per-asset keys and
never branches on `rawValue`. The capital-bound reason code uses only typed
numeric limits. Time-granularity remains the sole relevant branch that may show
its dedicated typed value.

**Step 5: Verify backend and web copy tests GREEN**

Run:

```bash
poetry run pytest --no-cov tests/agent_runtime/test_validation_failure_copy.py tests/agent_runtime/test_conversation_stages.py -q -k 'issue_453 or raw_value or starting_capital'
bun test web/__tests__/chat-recovery-display.test.ts
```

Expected: neither language contains model English or generic raw text; both name
the `$1,000` floor for the bounds case; locale parity passes.

### Task 5: Update the contract and durable deterministic evidence

**Files:**

- Modify: `docs/API_CONTRACT.md`
- Add: `docs/reports/evidence/453/baseline.md`
- Add: `docs/reports/evidence/453/verification.md`

**Step 1: Update the API contract**

Replace the generic unsupported example that treats `raw_value` as displayable.
Document that `raw_value` is opaque diagnostic or interpretation evidence, never
a generic display subject. Document typed capital bounds and cause routing.

**Step 2: Run focused backend verification**

Run:

```bash
poetry run pytest --no-cov tests/agent_runtime/test_llm_interpreter_artifact_capability_repairs.py tests/agent_runtime/test_options_semantic_admission.py tests/agent_runtime/test_validation_failure_copy.py tests/agent_runtime/test_conversation_stages.py -q
```

**Step 3: Run mocked interpreter evaluation**

Use the exact mocked command documented by `tests/evals/README.md`, scoped to
the interpreter-facing suite, with live providers disabled and
`ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture`.

**Step 4: Record evidence without generated secrets or environment files**

Write exact commands, results, base/head SHAs, and failure classifications to
the evidence markdown files with `apply_patch`. Do not write `.env` or
`web/.env.local`.

### Task 6: Capture bilingual guest browser proof

**Files:**

- Add: `docs/reports/evidence/453/browser/*`

**Step 1: Start the repository-supported local guest stack**

Use process-local environment values and repository scripts. Do not create or
edit an environment file. Keep market data on the synthetic unit fixture and do
not enable paid workflow execution.

**Step 2: Reproduce the four base behaviors in a controlled guest browser**

At the untouched base behavior or an equivalent controlled pre-fix response,
capture English and Spanish screenshots plus rendered-text receipts for:

1. raw model summary inside unsupported copy;
2. Coca-Cola monthly purchases refused as unsupported;
3. `$500` NFLX starting capital described as unsupported instead of bounded;
4. acknowledgment of `$500` before rejection.

**Step 3: Capture exact-head after proof**

On the final implementation head, repeat both languages through the guest path.
Show DCA reaches its amount clarification or confirmation, `$500` buy-and-hold
states the `$1,000` minimum, no raw summary appears, and no invalid
acknowledgment appears.

**Step 4: Commit durable artifacts**

Store screenshots and text receipts under
`docs/reports/evidence/453/browser/`, with a manifest naming locale, viewport,
scenario, base/head SHA, and whether the response was controlled or live.

### Task 7: Full verification and integration reconciliation

**Files:**

- Modify only files already owned by this plan, except conflict-resolution union additions

**Step 1: Run formatting and static checks**

Run the repository commands from `.agent/workflows/verify.md` for Python format,
Ruff, web lint/type checks, and locale validation.

**Step 2: Run full backend and web suites**

Run:

```bash
poetry run pytest tests/ -q
bun run test
```

Baseline-check every failure against
`8025672924d1c74eb80cc926c72b5d8574b613d7` before attributing it to this lane.

**Step 3: Fetch and compare integration**

Fetch `origin/codex/private-alpha-next`, record its SHA, and compare intervening
changes by runtime owner, contract, UI state, locale, and tests. If it advanced,
merge it one-way into this worker branch. Preserve locale changes as a union.

**Step 4: Run modularity against the would-be merged tree**

Run `scripts/check_modularity_budget.py` after reconciliation. Re-run the exact
affected acceptance surface if semantic overlap exists; otherwise retain
non-invalidated expensive/browser evidence and run normal exact-head gates.

**Step 5: Audit forbidden surfaces**

Assert no diff in `render.yaml`, `.env.example`, `.github/argus-env.sh`, the
release profile, `.env`, or `web/.env.local`.

### Task 8: Publish and exhaust review

**Files:**

- Add or modify the PR description and evidence links only

**Step 1: Commit atomically**

Keep the existing spec-only commit. Commit tests and implementation with
conventional messages that describe the user-visible refusal fix. Do not amend
or rebase after browser or review evidence.

**Step 2: Push and open the PR**

Push `codex/issue-453-unsupported-refusal` and open a ready PR against
`codex/private-alpha-next` with the required structured description, issue
link, original base, current integration SHA, and evidence links. Add relevant
existing labels.

**Step 3: Run CI and review loop**

Wait for terminal CI. Request the repository Codex review once per changed head.
Validate every finding, fix only actionable in-scope defects, rerun affected
tests, push, and request a latest-delta review. Stop when that review is clean
and unresolved-thread count is zero. Do not re-request on an unchanged head.

**Step 4: Record the terminal exact head and stop**

Report the PR URL, exact head SHA, original and current integration SHAs,
reconciliation merge SHA if any, overlap disposition, retained/invalidated
evidence, terminal CI state, clean review verdict, and unresolved-thread count.
Do not merge or deploy.
