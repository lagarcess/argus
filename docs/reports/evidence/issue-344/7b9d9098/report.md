# Issue #344 citation-boundary review evidence

## Audit identity

- Branch: `codex/issue-344-grounded-discovery-retry`
- Exact executable and acceptance SHA: `7b9d90981eff5e102b7eff607c23ab945e667db4`
- Current integration SHA: `be15c73e7e42c23f66cb89838fb371878b79936e`
- One-way reconciliation merge SHA: `3efa726ed7abb72659c75f17e629682a1a334f89`
- Date: 2026-08-03
- Browser: Playwright Chromium with explicit `headless: true`, one named session and one active page per capture
- Runtime: local Next.js and FastAPI against an isolated disposable Supabase project; real OpenRouter search/voice and Alpaca asset resolution
- Search: `openrouter_web_search` with `x-ai/grok-4.3`

No provider credential, password, bearer token, cookie, user id, conversation id, raw transcript export, or raw database row is preserved here.

## Review findings and repair

The exact-head Codex review at `8fac5544` found two content-less citation boundaries that the existing tests did not cover:

1. A dotted company prefix such as `U.S. Bancorp` could be truncated to `Bancorp`.
2. A lowercase-styled company name such as `eBay`, `iRobot`, or `monday.com` could inherit an unrelated preceding claim ending in `Inc.`.

Both findings reproduced as red adapter tests. The repair uses structural token shape rather than company-name phrasebooks: uppercase dotted initials remain attached to the following company name, while mixed-case or domain-style lowercase name starts create a new claim after a corporate suffix. All 24 adapter tests passed after the change, including the four new regressions.

Mocked tests prove these exact parser branches only. They are not the live or browser acceptance evidence.

## Exact-head live turn evaluation

The five issue #344 complete turn cases were rerun at exact SHA `7b9d9098` because the repair changes discovery-provider semantics.

- Result: 5 passed, 0 failed, 0 skipped, 0 expected failures, 0 unexpected passes
- Durable scorecard: `live-eval-scorecard.json`
- Passed cases:
  - `asset_discovery_recent_ipo_exact_issue_344`
  - `asset_discovery_trending_crypto_exact_issue_344`
  - `asset_discovery_old_pharma_escalation_exact_issue_344`
  - `asset_discovery_semantic_pharma_escalation_issue_344`
  - `asset_discovery_spanish_generated_pharma_escalation_issue_344`

The interpreter-focused run used the honest unavailable recovery path, so it proves live full-turn routing and voice, not working search-provider grounding. Working-provider proof is the browser evidence below.

## Bilingual headless grounded-browser acceptance

Both accepted journeys used the configured real OpenRouter search path and provider-backed asset resolution at exact SHA `7b9d9098`.

| Locale | User turn | Result | Evidence |
|---|---|---|---|
| English | `Find trending cryptocurrencies right now.` | Resolver-verified `BLESS/USD` with two sources and a typed Backtest action; 0 console errors | `english-trending-crypto-grounded.png` |
| `es-419` | `Busca acciones farmacéuticas actuales.` | Resolver-verified `JNJ` and `MRK` with four sources and localized Simular actions; 0 console errors | `spanish-pharma-grounded.png` |

An English recent-IPO attempt and a Spanish trending-crypto attempt completed as honest verified-empty diagnostics. They are excluded from the grounded-success claim above. No retry or repeated request was needed for either accepted journey.

## Retention disposition

- `528cce13` remains historical authority for its exact-head 43/43 broad live evaluation, original bilingual grounded-search matrix, retryable recovery, and labeled failure probes.
- `427b374f` remains authority for the corrected non-retryable English/Spanish authorization voice and neighboring recovery-code guidance. The citation repair runs only after a provider returns citations, so it cannot affect the missing/unauthorized pre-search path; the exact-current-head five-case live run also retained the voice contract.
- `7b9d9098` is current authority for content-less citation segmentation, the five affected live issue #344 turns, and bilingual working-provider grounding after the final Codex findings.
- The earlier broad and first-click evidence remains useful for unchanged Retry and generated-action UI behavior, but it no longer vouches for current citation parsing.
- No artifact claims hosted/default Perplexity health, hosted deployment health, tester exposure, or release promotion.

## Artifact hashes

| Artifact | SHA-256 |
|---|---|
| `live-eval-scorecard.json` | `c719e6eeccfd1c84977b42d3b4f52f6d897097cacd036e92795edebf943bd01a` |
| `english-trending-crypto-grounded.png` | `458dd417135f1193235a286bfba3e5e059dc536937e18c8fba9b05fb765b9ded` |
| `spanish-pharma-grounded.png` | `f6ee7e1a77f0c1c98500f5121ff0d9b841aaac6d4acb1c6d4b9567a7cab9cb28` |

## Lock declaration

This report is the acceptance baseline for executable SHA `7b9d90981eff5e102b7eff607c23ab945e667db4`. A later evidence-only commit may carry this pack if exact-final-head deterministic verification confirms the executable tree is unchanged. It does not authorize merge, deploy, tester exposure, hosted configuration changes, issue closure, or release promotion. Founder approval remains required.
