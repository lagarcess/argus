# Issue #344 dotted-suffix citation evidence

## Audit identity

- Branch: `codex/issue-344-grounded-discovery-retry`
- Exact executable and acceptance SHA: `dca757bdcde82500cec85ed0c6df4cbb2880d4c1`
- Current integration SHA: `be15c73e7e42c23f66cb89838fb371878b79936e`
- One-way reconciliation merge SHA: `3efa726ed7abb72659c75f17e629682a1a334f89`
- Date: 2026-08-03
- Browser: Playwright Chromium with explicit `PLAYWRIGHT_MCP_HEADLESS=true`, one named session, and one active page per capture
- Runtime: local Next.js and FastAPI against an isolated disposable Supabase project; real OpenRouter search/voice and Alpaca asset resolution
- Search: `openrouter_web_search` with `x-ai/grok-4.3`

No provider credential, password, bearer token, cookie, user id, conversation id, raw transcript export, or raw database row is preserved here.

## Review finding and repair

The mandatory independent review found that dotted corporate suffixes such as `S.A.`, `N.V.`, `L.P.`, and `C.V.` could be mistaken for the `U.S.` name prefix added by the prior repair. In content such as `Unsupported S.A. Supported Corp completed an IPO.[citation]`, that collision attached the unsupported company to the later citation.

Four parametrized regressions reproduced the defect before implementation. The smallest repair excludes the existing corporate-abbreviation set from the dotted-name-prefix exception. All 28 discovery adapter cases then passed, including the preserved `U.S. Bancorp`, lowercase-styled brand, corporate-abbreviation, and new suffix-boundary cases.

Mocked tests prove these parser branches only. They are not the live or browser acceptance evidence.

## Exact-head live turn evaluation

The five issue #344 complete-turn cases were rerun at exact SHA `dca757bd` because the repair changes discovery-provider semantics.

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

Both accepted journeys used the configured real OpenRouter search path and provider-backed Alpaca asset resolution at exact SHA `dca757bd`.

| Locale | User turn | Result | Evidence |
|---|---|---|---|
| English | `Find trending cryptocurrencies right now.` | Resolver-verified `BNB/USD` with four sources and a typed Backtest action; 0 console errors | `english-trending-crypto-grounded.png` |
| `es-419` | `Busca acciones farmacéuticas actuales de Estados Unidos que coticen en bolsa.` | Resolver-verified `JNJ`, `ABBV`, and `PFE` with five sources and localized Simular actions; 0 console errors | `spanish-pharma-grounded.png` |

Before the accepted Spanish journey, the broader prompt `Busca acciones farmacéuticas actuales.` completed as an honest verified-empty result because the live provider returned names outside the Alpaca catalog. It is excluded from the grounded-success claim. The accepted journey is a more specific US-listed request, not a replay of the same failed turn.

## Retention disposition

- `528cce13` remains historical authority for its exact-head 43/43 broad live evaluation, original bilingual grounded-search matrix, retryable recovery, and labeled failure probes.
- `427b374f` remains authority for corrected non-retryable English/Spanish authorization voice and neighboring recovery guidance.
- `7b9d9098` remains authority for the first citation-boundary repair and its exact-head bilingual grounded evidence, but it does not cover the later dotted-suffix collision.
- `dca757bd` is current authority for dotted corporate suffix separation, the five affected live issue #344 turns, and bilingual working-provider grounding after the mandatory review finding.
- No artifact claims hosted/default Perplexity health, hosted deployment health, tester exposure, or release promotion.

## Artifact hashes

| Artifact | SHA-256 |
|---|---|
| `live-eval-scorecard.json` | `6a5b0b9e06e497966deace27610cabf9c00b9d15aff1c11054afa8336023fb3b` |
| `english-trending-crypto-grounded.png` | `da22ddb2a3809c8339d45c26971129f0ae6d845bbe40e9bc46ea115b7ac3cbae` |
| `spanish-pharma-grounded.png` | `534321778d8f6721f336381b4256a809e264b1be6a48b44f75e1deebaabd30f9` |

## Lock declaration

This report is the acceptance baseline for executable SHA `dca757bdcde82500cec85ed0c6df4cbb2880d4c1`. A later evidence-only commit may carry this pack if exact-final-head deterministic verification confirms the executable tree is unchanged. It does not authorize merge, deploy, tester exposure, hosted configuration changes, issue closure, or release promotion. Founder approval remains required.
