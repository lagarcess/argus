# Grounded Discovery Retry Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to execute this plan.

**Goal:** Repair issue #344 so current-fact discovery distinguishes permanent configuration/auth failures from transient failures, Retry succeeds after transient recovery, and general-to-current escalation sends asset-aware English and Spanish user intent.

**Architecture:** Keep the LLM interpreter as the only owner of discovery intent. Add one typed provider-failure reason at the shared HTTP boundary, map only permanent availability failures to non-retryable recovery in the existing discovery composer, and derive escalation language from the existing resolver-validated sidecar in a pure frontend helper. Do not add provider fallback, phrase routing, persistence, endpoints, or a second runtime.

**Tech Stack:** Python 3.10, FastAPI domain/runtime modules, Pydantic, pytest/pytest-asyncio, TypeScript, React/Next.js, i18next catalogs, Bun tests, Playwright, GitHub Actions.

## Global Constraints

- Work only on `codex/issue-344-grounded-discovery-retry`, originally based on `origin/codex/private-alpha-next` at `6533377c1a08539136a622a7d53eee20d0efd845`.
- Treat `docs/superpowers/specs/2026-08-02-grounded-discovery-retry-reliability.md` as the locked lane contract.
- Never add regex/phrase routing, a provider fallback chain, a category registry, new persistence/RLS, quota changes, or a second chat runtime.
- Never edit the canonical-linked `.env` or `web/.env.local`; use process-local variables for acceptance.
- Mocked and regression checks prove code paths only. The exact-head live interpreter eval and bilingual real-API browser QA are mandatory acceptance evidence before review.
- Perform the mandatory Argus review on the exact accepted head before pushing or opening the PR. Any review fix invalidates affected evidence and requires proportional reruns before another final review.
- Stop before merge, deploy, hosted configuration changes, tester exposure, or issue closure.

---

### Task 1: Type permanent provider authorization failures

**Files:**
- Modify: `tests/domain/test_discovery_search_adapters.py`
- Modify: `src/argus/domain/discovery_search/contracts.py`
- Modify: `src/argus/domain/discovery_search/http_post.py`

- [ ] **Step 1: Write failing adapter tests**

Add parameterized provider-adapter coverage proving HTTP 401 and 403 raise `SearchUnavailableError(reason="authentication_failed")`, while 429 and 5xx remain `reason="http_error"`. Keep the existing timeout, malformed response, and single-attempt assertions.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```bash
poetry run pytest tests/domain/test_discovery_search_adapters.py -q --no-cov
```

Expected: new 401/403 cases fail because `post_json` currently emits `http_error` for every HTTP status.

- [ ] **Step 3: Add the smallest shared-boundary implementation**

Extend `SearchUnavailableReason` and `_ALLOWED_UNAVAILABLE_REASONS` with `authentication_failed`. In `post_json`, classify only status 401/403 as that reason; preserve `http_error` for all other HTTP failures. Do not inspect response prose, retry automatically, or expose credentials.

- [ ] **Step 4: Run the focused tests and confirm GREEN**

Run the same pytest command and require all adapter tests to pass.

- [ ] **Step 5: Commit the provider classification**

```bash
git add src/argus/domain/discovery_search/contracts.py src/argus/domain/discovery_search/http_post.py tests/domain/test_discovery_search_adapters.py
git commit -m "fix(discovery): classify provider authorization failures"
```

### Task 2: Make Retry truthful and recoverable

**Files:**
- Modify: `tests/agent_runtime/discovery/test_discovery_composer.py`
- Modify: `src/argus/agent_runtime/discovery/composer.py`

- [ ] **Step 1: Write failing composer tests**

Add tests for these typed outcomes:

1. `not_configured` -> `discovery_unavailable`, `retryable=false`, `search_attempted=false`.
2. `authentication_failed` -> `discovery_unavailable`, `retryable=false`, `search_attempted=true`.
3. `timeout` and `http_error` -> `discovery_search_failed`, `retryable=true`.
4. A sequenced provider fails once with a transient error, then returns a usable packet when the identical discovery request is replayed; the second result contains validated discovery candidates and no recovery object.

- [ ] **Step 2: Run the focused tests and confirm RED**

```bash
OPENROUTER_API_KEY= PERPLEXITY_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/agent_runtime/discovery/test_discovery_composer.py -q --no-cov
```

Expected: permanent-failure cases fail because the composer currently marks every provider failure retryable; the transient replay test should document the existing stateless retry path and pass only when the fixture advances correctly.

- [ ] **Step 3: Implement typed recovery mapping**

In the existing `SearchUnavailableError` handler, map `not_configured` and `authentication_failed` to non-retryable `discovery_unavailable`; map timeout, generic HTTP, and malformed response failures to retryable `discovery_search_failed`. Preserve the current `fallback_code`, accurate `search_attempted`, single-attempt behavior, and localized recovery voice.

- [ ] **Step 4: Run the focused tests and confirm GREEN**

Run the same hermetic composer command and require all tests to pass.

- [ ] **Step 5: Commit the recovery repair**

```bash
git add src/argus/agent_runtime/discovery/composer.py tests/agent_runtime/discovery/test_discovery_composer.py
git commit -m "fix(chat): make discovery retry availability truthful"
```

### Task 3: Make current-search escalation asset-aware and bilingual

**Files:**
- Create: `web/lib/chat-discovery-escalation.ts`
- Create: `web/__tests__/chat-discovery-escalation.test.ts`
- Modify: `web/components/chat/ChatMessage.tsx`
- Modify: `web/public/locales/en/common.json`
- Modify: `web/public/locales/es-419/common.json`

- [ ] **Step 1: Write failing behavior and locale tests**

Create a pure helper test that supplies valid discovery sidecars and asserts:

- uniform equity candidates select the stock noun,
- uniform crypto candidates select the cryptocurrency noun,
- uniform currency-pair candidates select the currency-pair noun,
- mixed or empty candidates select the generic asset noun,
- category, peer, and comparison relationships select their matching message template,
- interpolation with the checked-in English and es-419 catalogs yields semantic ordinary turns, including `Search for current stocks in the pharmaceutical sector` and its Spanish equivalent.

Also assert that every new asset-noun/template key exists in both catalogs.

- [ ] **Step 2: Run the focused frontend tests and confirm RED**

```bash
cd web && bun test __tests__/chat-discovery-escalation.test.ts
```

Expected: the helper and new locale keys do not exist yet.

- [ ] **Step 3: Implement the pure copy-plan helper**

Add a helper that derives only from `DiscoverySidecar.relationship`, `query_summary`, and resolver-validated `candidates[].asset_class`. Return a translation key plus variables; do not compare translated labels or add backend state. Mixed/empty classes must use the generic asset key.

- [ ] **Step 4: Wire the existing escalation row**

Use the helper in `ChatMessage.tsx` to build the natural-language `select_response_option` label/payload. Preserve `onAction`, ordinary interpreter re-entry, allowance gating, and all existing discovery rows.

- [ ] **Step 5: Add English and es-419 parity**

Add asset-noun keys for equities, crypto, currency pairs, and generic assets plus relationship templates that accept `{{assetKind}}` and `{{query}}`. Keep concise beginner-facing grammar in both languages.

- [ ] **Step 6: Run focused frontend tests and confirm GREEN**

```bash
cd web && bun test __tests__/chat-discovery-escalation.test.ts __tests__/discovery-sidecar.test.ts __tests__/chat-next-move-rows.test.ts __tests__/chat-retry-actions.test.ts
```

- [ ] **Step 7: Commit the bilingual escalation change**

```bash
git add web/lib/chat-discovery-escalation.ts web/__tests__/chat-discovery-escalation.test.ts web/components/chat/ChatMessage.tsx web/public/locales/en/common.json web/public/locales/es-419/common.json
git commit -m "fix(chat): send asset-aware discovery escalation"
```

### Task 4: Lock the exact interpreter and recovery contracts

**Files:**
- Modify: `tests/evals/measurement_eval_harness.py`
- Modify: `tests/evals/test_measurement_eval_harness.py`
- Modify: `tests/evals/measurement_cases/asset_discovery_routing.yaml`
- Modify: `docs/API_CONTRACT.md`
- Modify: `docs/superpowers/specs/2026-07-25-grounded-discovery-search-v1-design.md`

- [ ] **Step 1: Write a failing eval-comparator test**

Add a harness unit test where expected `needs_current_facts=true` and actual is false. Require the comparator to report a field-specific failure. Verify old cases that omit the expectation remain backward compatible.

- [ ] **Step 2: Run the comparator test and confirm RED**

```bash
poetry run pytest tests/evals/test_measurement_eval_harness.py -q --no-cov
```

Expected: the new mismatch is not yet reported.

- [ ] **Step 3: Implement the optional typed assertion**

Teach `_compare_asset_discovery` to compare `needs_current_facts` when the expected case provides it. Do not infer it from prompt text or make it mandatory for unrelated historical cases.

- [ ] **Step 4: Add the exact #344 cases**

Add measurement cases for:

- `find me stocks that have recently IPO'ed`
- `find me cryptos that are trending`
- `Search current sources for: pharmaceutical sector`
- the repaired semantic escalation `Search for current stocks in the pharmaceutical sector`

Each expected output must retain `semantic_turn_act=asset_discovery`, the correct relationship/category and asset hint where the language supplies it, and `needs_current_facts=true`.

- [ ] **Step 5: Update contract truth**

In `docs/API_CONTRACT.md`, state that missing or unauthorized configured Search is `discovery_unavailable` and non-retryable, while transient timeout/HTTP failures are retryable `discovery_search_failed`. Add a dated #344 reconciliation note to the historical discovery v1 outage table without rewriting its original provider-selection decision.

- [ ] **Step 6: Run mocked eval/regression checks**

```bash
OPENROUTER_API_KEY= PERPLEXITY_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest \
  tests/evals/test_measurement_eval_harness.py \
  tests/evals/test_chat_runtime_eval_manifest.py \
  tests/evals/test_chat_runtime_trajectory_harness.py \
  -q --no-cov
```

These checks prove the comparator and deterministic path only; record them separately from live acceptance.

- [ ] **Step 7: Commit the contract and eval cases**

```bash
git add tests/evals/measurement_eval_harness.py tests/evals/test_measurement_eval_harness.py tests/evals/measurement_cases/asset_discovery_routing.yaml docs/API_CONTRACT.md docs/superpowers/specs/2026-07-25-grounded-discovery-search-v1-design.md
git commit -m "test(chat): lock grounded discovery issue cases"
```

### Task 5: Run deterministic candidate verification

**Files:**
- Verify only; no expected edits.

- [ ] **Step 1: Run focused backend coverage**

```bash
OPENROUTER_API_KEY= PERPLEXITY_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/domain/test_discovery_search_adapters.py tests/agent_runtime/discovery/test_discovery_composer.py tests/evals/test_measurement_eval_harness.py -q --no-cov
```

- [ ] **Step 2: Run the hermetic runtime regression sweep**

```bash
OPENROUTER_API_KEY= PERPLEXITY_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/agent_runtime tests/test_spine_guardrails.py -q --no-cov
```

- [ ] **Step 3: Run affected frontend verification**

```bash
cd web && bun test __tests__/chat-discovery-escalation.test.ts __tests__/discovery-sidecar.test.ts __tests__/chat-next-move-rows.test.ts __tests__/chat-retry-actions.test.ts
cd web && bun run lint
cd web && bun run typecheck
```

If the package has no `typecheck` script, use the repository-documented equivalent and record the substitution.

- [ ] **Step 4: Inspect the candidate diff for scope**

```bash
git status --short
git diff --check
git diff 6533377c1a08539136a622a7d53eee20d0efd845...HEAD --stat
git diff 6533377c1a08539136a622a7d53eee20d0efd845...HEAD
```

Remove any speculative machinery not justified by the accepted design.

### Task 6: Gather exact-head live interpreter evidence

**Files:**
- Verify only; preserve generated evidence only if the repository workflow explicitly tracks it.

- [ ] **Step 1: Read eval tier instructions and identify the exact case filter**

Read `tests/evals/README.md` in full. Confirm the sanctioned live command, the required environment, and whether the four #344 cases can be filtered without changing harness semantics.

- [ ] **Step 2: Commit any remaining tracked candidate changes**

The live run must use a clean exact head. Record:

```bash
git status --short
git rev-parse HEAD
```

- [ ] **Step 3: Run the sanctioned live eval once on exact head**

Use the repository-documented live command with the existing live structured interpreter model. If discovery composition is exercised, configure the already-supported `openrouter_web_search` provider only through process-local environment variables. Do not write linked env files and do not use the failing Perplexity credential as proof.

Required observations for the exact issue prompts: `semantic_turn_act=asset_discovery`, expected relationship/category and supplied asset hint, and `needs_current_facts=true`.

- [ ] **Step 4: Enforce the stop condition**

If any exact prompt is typed differently, stop with the live typed output and route receipt. Do not add deterministic phrase logic or claim acceptance from mocked results.

### Task 7: Gather bilingual real-API browser evidence

**Files:**
- Verify only, except sanitized evidence artifacts allowed by the repository QA workflow.

- [ ] **Step 1: Use the Playwright skill and prepare an isolated real-API stack**

Read and follow the local Playwright skill. Recheck worktree env topology, start the real API and frontend with process-local provider overrides, and confirm the UI is not in mock API/auth mode. Never print secrets.

- [ ] **Step 2: Prove the English journeys**

On the exact live-eval SHA, capture sanitized evidence for:

- recent-IPO equity discovery,
- trending-crypto discovery,
- general-knowledge pharmaceutical candidates -> asset-aware current-search escalation,
- missing/unauthorized Search -> honest non-retryable recovery with no Retry,
- transient provider failure -> visible Retry -> same request succeeds after the configured provider becomes available.

- [ ] **Step 3: Prove es-419 parity**

Repeat the user-visible escalation, failure truth, and Retry recovery in es-419. Confirm the sent escalation is semantic Spanish natural language and still re-enters the real interpreter/API.

- [ ] **Step 4: Record exact evidence identity**

Record the exact Git SHA, API/frontend runtime modes, explicit provider id/model (never key values), locale, conversation identifiers safe for local QA, screenshots, typed recovery code/retryable flag, and final grounded sidecar/source state.

- [ ] **Step 5: Enforce the stop condition**

If the real-API/browser journeys cannot be completed without shared env mutation, hosted writes, or unavailable provider capability, stop and report. Mocked browser data cannot substitute for this gate.

### Task 8: Mandatory final review and proportional remediation

**Files:**
- Review the exact diff and evidence; modify only for validated findings.

- [ ] **Step 1: Use the Argus review contract**

Run the mandatory independent review against `6533377c1a08539136a622a7d53eee20d0efd845...HEAD`. Provide the locked spec, exact-head live evidence, bilingual browser evidence, test commands, no-touch surfaces, and issue #344 acceptance criteria.

- [ ] **Step 2: Resolve findings proportionally**

For each finding, confirm reachability and severity. Apply only the smallest safe fix. If a fix changes interpreter routing, recovery ownership, provider classification, escalation behavior, or user-visible copy, rerun the affected live/browser acceptance on the new exact head before a final review pass.

- [ ] **Step 3: Require a clean review disposition**

Do not open the PR while any validated blocking finding remains. Record the reviewed SHA and disposition.

### Task 9: Reconcile integration freshness and open the PR

**Files:**
- Verify repository state and create GitHub metadata only.

- [ ] **Step 1: Fetch integration and assess overlap**

```bash
git fetch origin codex/private-alpha-next
git rev-parse origin/codex/private-alpha-next
git log --oneline --left-right 6533377c1a08539136a622a7d53eee20d0efd845...origin/codex/private-alpha-next
```

Compare any intervening changes by runtime owner, contract, UI state owner, environment/provider selection, and affected tests. If integration advanced, merge it one-way into this worker branch; never rebase an evidenced/published head. Rerun only evidence invalidated by semantic overlap.

- [ ] **Step 2: Run final exact-head verification**

Use the superpowers verification and finishing skills. Require a clean worktree, `git diff --check`, focused green suites, accepted live/browser evidence applicable to the final SHA, and terminal CI readiness.

- [ ] **Step 3: Push the reviewed worker branch**

```bash
git push -u origin codex/issue-344-grounded-discovery-retry
```

- [ ] **Step 4: Open the ready PR**

Create one ready-for-review PR targeting `codex/private-alpha-next`, link issue #344, use the required Argus PR structure, attach sanitized exact-head acceptance evidence, and add relevant existing labels. Do not merge or close the issue.

- [ ] **Step 5: Report the READY lineage**

Report original integration base, current integration SHA, reconciliation merge SHA if any, semantic-overlap disposition, evidence retained/invalidated, exact PR head, CI state, PR URL, and the founder-owned next step.
