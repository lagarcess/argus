# Issue #344 terminal-initialism citation evidence

## Audit identity

- Branch: `codex/issue-344-grounded-discovery-retry`
- Exact executable and acceptance SHA: `9f153cbb0268bd2092d51adf3c919b998c0c332b`
- Current integration SHA: `b36e7396c28c84d8acafdb86d2b81535dd0c6942`
- Latest one-way reconciliation merge SHA: `eb7e9db6778d82896b70e70b14bec0dfabd2884d`
- Date: 2026-08-03
- Browser: Playwright Chromium with explicit `PLAYWRIGHT_MCP_HEADLESS=true`, one named session, and one active page per capture
- Runtime: local Next.js and FastAPI against an isolated disposable Supabase project; real OpenRouter search/voice and Alpaca asset resolution
- Search: `openrouter_web_search` with `x-ai/grok-4.3`

No provider credential, password, bearer token, cookie, user id, conversation id, raw transcript export, or raw database row is preserved here.

## Review finding and repair

The exact-head Codex review found that a terminal geographic initialism could still look like a company-name prefix. For example, `Acme operates in the U.S. Supported Corp completed an IPO.[citation]` attached both sentences to the later citation.

The exact example reproduced as a red adapter test. The repair now treats uppercase dotted initials as a company-name prefix only when the dotted token begins the current claim. It preserves `U.S. Bancorp`, separates terminal `in the U.S.`, and retains the earlier corporate-suffix and lowercase-brand boundaries. All 29 discovery adapter cases passed.

Mocked tests prove these parser branches only. They are not the live or browser acceptance evidence.

## Exact-head live turn evaluation

The five issue #344 complete-turn cases were rerun at exact SHA `9f153cbb` because the repair changes discovery-provider semantics.

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

Both accepted journeys used the configured real OpenRouter search path and provider-backed Alpaca asset resolution at exact SHA `9f153cbb`.

| Locale | User turn | Result | Evidence |
|---|---|---|---|
| English | `Find trending cryptocurrencies right now.` | Resolver-verified `ONDO/USD` and `DOGE/USD` with three sources and typed Backtest actions; 0 console errors | `english-trending-crypto-grounded.png` |
| `es-419` | `Busca acciones farmacéuticas actuales de Estados Unidos que coticen en bolsa.` | Resolver-verified `REGN` and `VRTX` with four sources and localized Simular actions; 0 console errors | `spanish-pharma-grounded.png` |

## Retention disposition

- `528cce13` remains historical authority for its exact-head 43/43 broad live evaluation, original bilingual grounded-search matrix, retryable recovery, and labeled failure probes.
- `427b374f` remains authority for corrected non-retryable English/Spanish authorization voice and neighboring recovery guidance.
- `dca757bd` remains authority for the dotted-corporate-suffix repair and its exact-head acceptance, but it does not cover the later terminal-initialism collision.
- `9f153cbb` is current authority for claim-initial dotted-prefix detection, the five affected live issue #344 turns, and bilingual working-provider grounding after the final exact-head Codex finding.
- No artifact claims hosted/default Perplexity health, hosted deployment health, tester exposure, or release promotion.

## Artifact hashes

| Artifact | SHA-256 |
|---|---|
| `live-eval-scorecard.json` | `4e73a593758b11ef27d9b236f32858e419c8293dcfa453d87a137073df386dbd` |
| `english-trending-crypto-grounded.png` | `94db80d51f6309383d9acafac39a385589d1b778c5e815540e707072610c775e` |
| `spanish-pharma-grounded.png` | `627b1ee477a4e6af305f53c70dfbb0644e26966bb14e7f9c323e6dde817c8b80` |

## Lock declaration

This report is the acceptance baseline for executable SHA `9f153cbb0268bd2092d51adf3c919b998c0c332b`. A later evidence-only commit may carry this pack if exact-final-head deterministic verification confirms the executable tree is unchanged. It does not authorize merge, deploy, tester exposure, hosted configuration changes, issue closure, or release promotion. Founder approval remains required.
