# Issue #344 non-retryable recovery acceptance evidence

## Audit identity

- Branch: `codex/issue-344-grounded-discovery-retry`
- Exact executable and acceptance SHA: `427b374f5349bc7c7741d3fa298806a76bcce3e6`
- Recovery-voice fix SHA: `cdef53286b626c0d8534e2639fcdc5be7a3b8035`
- Review follow-up SHA: `427b374f5349bc7c7741d3fa298806a76bcce3e6`
- Original integration base: `6533377c1a08539136a622a7d53eee20d0efd845`
- Previous reconciled integration SHA: `dc407d549b38de1c107f7556bfe9dc6d65a12ecb`
- Current integration SHA: `be15c73e7e42c23f66cb89838fb371878b79936e`
- Current one-way reconciliation merge SHA: `3efa726ed7abb72659c75f17e629682a1a334f89`
- Date: 2026-08-03
- Browser: Playwright Chromium with explicit `headless: true`, one named session, one browser, one context, and one page
- Runtime: local Next.js and FastAPI against an isolated disposable Supabase project; real OpenRouter voice and interpreter calls
- Engineered failure probe: an explicit invalid Perplexity credential forced the non-retryable authorization path

No provider credential, password, bearer token, cookie, user id, conversation id, raw transcript export, or raw database row is preserved here.

## Acceptance boundary

Mocked and deterministic tests prove the code path only. They do not prove the live language or browser claim. Acceptance for this repair rests on the exact-head five-case live turn evaluation plus the bilingual headless browser journeys below.

The engineered invalid credential proves failure classification and recovery presentation only. It is not evidence that the provider's working path or hosted credentials are healthy.

## Integration overlap disposition

Integration advanced from `dc407d54` to `be15c73e` through PR #358. The incoming work changed the shared `llm_interpreter.py` owner, interpreter helpers, and measurement harness, so the overlap was treated as semantic even though Git merged without a conflict.

The incoming compound-edit planning logic does not change discovery recovery ownership, but the shared interpreter and harness changes invalidated the affected interpreter acceptance claim. The five issue #344 live cases and both browser journeys were therefore rerun after the one-way merge. The composed-tree modularity check passed with `llm_interpreter.py` at 5,353/5,354 lines.

## Live red-to-green evidence

The first attempted design made non-retryable copy deterministic in English. On exact SHA `2a91b582`, the affected live run correctly failed the Spanish case:

- Result: 4 passed, 1 failed
- Failure: `asset_discovery_spanish_generated_pharma_escalation_issue_344`
- Failed criterion: `prose_judge:spanish_language_integrity`
- Durable diagnostic: `live-eval-spanish-first-red.json`

That failure prevented acceptance. The implementation was corrected to retain LLM-owned localized voice while passing the typed `retryable=false` constraint and a strict no-retry, no-temporal-promise prompt.

After the current integration merge and mandatory-review follow-up, the same five complete turn paths were rerun at exact SHA `427b374f`:

- Result: 5 passed, 0 failed, 0 skipped, 0 expected failures, 0 unexpected passes
- Durable scorecard: `live-eval-scorecard.json`
- Passed cases:
  - `asset_discovery_recent_ipo_exact_issue_344`
  - `asset_discovery_trending_crypto_exact_issue_344`
  - `asset_discovery_old_pharma_escalation_exact_issue_344`
  - `asset_discovery_semantic_pharma_escalation_issue_344`
  - `asset_discovery_spanish_generated_pharma_escalation_issue_344`

This is live full-turn interpreter/composer evidence, not a mocked substitute. Search was intentionally unavailable in this bounded probe, so the result proves honest non-retryable recovery voice; it does not prove grounded provider success.

## Bilingual headless browser acceptance

Both journeys ran from clean conversations at exact SHA `427b374f` with the invalid Perplexity authorization probe. Chromium remained headless for the entire run and did not open or focus a visible browser window.

| Locale | User turn | Observed response contract | Result | Evidence |
|---|---|---|---|---|
| English | `Find current pharmaceutical stocks.` | Says discovery is unavailable for this request; asks for a specific symbol or company; no retry action, future promise, or temporal qualifier | Pass; 0 console errors | `english-authorization-no-retry.png` |
| `es-419` | `Busca acciones farmacéuticas actuales.` | Says backed discovery is unavailable for this request; asks for a specific symbol or company; no Reintentar action, future promise, or temporal qualifier | Pass; 0 console errors | `spanish-authorization-no-retry.png` |

The absence of a Retry/Reintentar control matches the typed contract `discovery_unavailable`, `retryable=false`; the UI did not infer recovery from prose.

## Retention disposition

- `528cce13` remains historical authority for its exact-head 43/43 broad live evaluation, bilingual grounded-search matrix, retryable failure recovery, and failure probes.
- `528cce13` no longer vouches for the revised non-retryable recovery voice because the interpreter/composer presentation changed afterward.
- `b2d5b1a0` remains authority for the reconciled Spanish first-click grounded-search journey and its five then-current affected live cases. The new integration changes did not touch search adapters, discovery candidate verification, Retry mechanics, or that generated-action UI path.
- `3efa726e` is superseded for current recovery-voice acceptance because mandatory review found that its generic non-retryable instruction could misvoice missing-target and no-verified-candidate outcomes.
- `427b374f` is the current authority for the non-retryable English and Spanish unavailable voice, code-specific neighboring recovery guidance, the affected five-case live turn path after the latest integration reconciliation, and the no-Retry browser presentation.
- No fresh broad 43-case live burn was needed: the repair and integration overlap affected discovery interpreter/composer semantics, so only the five issue #344 cases were rerun. Unchanged grounded-search and broad browser evidence is retained rather than overstated.
- No evidence pack claims hosted provider health, hosted deployment health, tester exposure, or release readiness beyond this PR lane.

## Artifact hashes

| Artifact | SHA-256 |
|---|---|
| `english-authorization-no-retry.png` | `5a6fd7132d520197a8d2b190b6d87e1efebc5121a4288c2e0bb773a8c4cce54d` |
| `spanish-authorization-no-retry.png` | `ef43b45dab3af5582e2bcb7e32ebb14223994130031873e623df6d47cea6b34a` |
| `live-eval-scorecard.json` | `58373fadd37ca8b964e6a16aafb9c382aa0c060ab080b765bdb5831edde89443` |
| `live-eval-spanish-first-red.json` | `df5b0fd8017963fca63c3e9cc0482193645d7124e12ce4cf164c484a6258e4fe` |

## Lock declaration

This report is the acceptance baseline for executable SHA `427b374f5349bc7c7741d3fa298806a76bcce3e6`. A later evidence-only commit may carry this pack if exact-final-head deterministic verification confirms that the executable tree is unchanged. It does not authorize merge, deploy, tester exposure, hosted configuration changes, issue closure, or release promotion. Founder approval remains required.
