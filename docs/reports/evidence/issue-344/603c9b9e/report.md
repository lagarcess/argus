# Issue #344 final reviewed recovery evidence

## Audit identity

- Branch: `codex/issue-344-grounded-discovery-retry`
- Exact executable and acceptance SHA: `603c9b9e03719b8aba6bfa823ebf0bebff32ec72`
- Original integration base: `6533377c1a08539136a622a7d53eee20d0efd845`
- Current integration SHA: `b36e7396c28c84d8acafdb86d2b81535dd0c6942`
- Latest one-way reconciliation merge SHA: `eb7e9db6778d82896b70e70b14bec0dfabd2884d`
- Date: 2026-08-03 (`America/Santo_Domingo`)
- Browser: Playwright Chromium launched with explicit `headless: true`; no visible browser window was opened
- Runtime: local Next.js and FastAPI against an isolated disposable Supabase project; real OpenRouter search/voice and provider-backed asset resolution
- Search: `openrouter_web_search` with `x-ai/grok-4.3`

No provider credential, password, bearer token, cookie, user id, conversation id, raw transcript export, or raw database row is preserved here.

## Final review findings and repairs

Two independently reported findings were validated and fixed.

1. A non-retryable `discovery_unavailable` recovery could still pass through the LLM composer, allowing stochastic wording to contradict the typed recovery metadata. The path now skips the LLM and uses canonical localized English or `es-419` copy while preserving the typed recovery action.
2. Citation markers joined only by the exact connectors `and` or Spanish `y`, with optional punctuation, could be split into separate claims. The parser now keeps those connectors in the shared citation group while still starting a new claim when substantive text appears.

Both repairs were first reproduced with focused regression tests. Mandatory bounded review of the full repair and the updated eval trajectory returned READY with no findings.

Mocked and hermetic tests prove these code paths only. They do not prove the live provider or browser acceptance claims.

## Exact-code-head deterministic gates

- Hermetic runtime, spine, and discovery adapters: 1,612 passed
- Non-live eval suite: 92 passed, 1 live test skipped by design
- Provider contracts and adapters: 52 passed
- Ruff, modularity, environment topology, and diff checks: passed
- `llm_interpreter.py`: 5,353 lines against the composed-tree limit of 5,354
- Mandatory bounded review: READY with no findings

## Exact-code-head live turn evaluation

The five affected issue #344 complete-turn cases were rerun at executable SHA `603c9b9e` because the repairs touch discovery composition and citation semantics.

- Result: 5 passed, 0 failed, 0 skipped, 0 expected failures, 0 unexpected passes
- Durable scorecard: `live-eval-scorecard.json`
- Passed cases:
  - `asset_discovery_recent_ipo_exact_issue_344`
  - `asset_discovery_trending_crypto_exact_issue_344`
  - `asset_discovery_old_pharma_escalation_exact_issue_344`
  - `asset_discovery_semantic_pharma_escalation_issue_344`
  - `asset_discovery_spanish_generated_pharma_escalation_issue_344`

## Bilingual headless grounded-browser acceptance

Both accepted journeys ran at executable SHA `603c9b9e` with explicit Chromium `headless: true`, the configured real OpenRouter search path, and provider-backed asset resolution.

| Locale | User turn | Result | Evidence |
|---|---|---|---|
| English | `Search current sources for publicly traded pharmaceutical companies comparable to PFE, MRK, and ABBV.` | Resolver-verified `JNJ`, five visible sources, and a typed Backtest action | `english-pharma-comparison-grounded.png` |
| `es-419` | `Busca en fuentes actuales empresas farmacéuticas que coticen en bolsa comparables con PFE, MRK y ABBV.` | Resolver-verified candidates including `JNJ`, five visible sources, and localized Simular actions | `spanish-pharma-grounded.png` |

Both accepted turns emitted zero browser errors after guest authentication and during the turn. Both screenshots were visually inspected after capture.

Earlier attempts that returned an honest verified-empty state or general-knowledge prose with zero sources were rejected from acceptance. Only the final source-backed matrix above is claimed.

## Retention disposition

- `528cce13` remains historical authority for its exact-head 43/43 broad live evaluation, original bilingual grounded-search matrix, retryable recovery, and labeled failure probes.
- `ff0ea0a1` remains historical authority for direct, whitespace-separated, and punctuation-separated adjacent citation grouping and its earlier exact-head browser evidence.
- `603c9b9e` is current authority for deterministic non-retryable unavailable recovery, English/Spanish conjunction citation grouping, the affected five-case live evaluation, and the final headless bilingual working-provider browser matrix.
- The latest changes invalidate reliance on the older heads for the two repaired semantics, but do not require burning the unchanged 43-case broad matrix again; the affected five complete-turn cases and bilingual browser surface were rerun at `603c9b9e`.
- No artifact claims hosted/default Perplexity health, hosted deployment health, tester exposure, or release promotion.

## Artifact hashes

| Artifact | SHA-256 |
|---|---|
| `live-eval-scorecard.json` | `8ac6c03f5947d002979878fc4c1bcf850a849221856e8b23afbd438862e128e2` |
| `english-pharma-comparison-grounded.png` | `5bba4fe04a86135bc08a0fb7b6771f66d045c81f2cfe18c53660a3ef969bf352` |
| `spanish-pharma-grounded.png` | `7e40090c5ae02fa6bf68749b7bdf8089215afa54fcb3f1aa0396587bdae86823` |

## Lock declaration

This report is the acceptance baseline for executable SHA `603c9b9e03719b8aba6bfa823ebf0bebff32ec72`. A later evidence-only commit may carry this pack after exact-final-head deterministic verification confirms the executable tree is unchanged. It does not authorize merge, deploy, tester exposure, hosted configuration changes, issue closure, or release promotion. Founder approval remains required.
