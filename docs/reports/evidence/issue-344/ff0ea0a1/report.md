# Issue #344 adjacent-citation evidence

## Audit identity

- Branch: `codex/issue-344-grounded-discovery-retry`
- Exact executable and acceptance SHA: `ff0ea0a1e9eeee394b130187984d3ed6012b5a06`
- Original integration base: `6533377c1a08539136a622a7d53eee20d0efd845`
- Current integration SHA: `b36e7396c28c84d8acafdb86d2b81535dd0c6942`
- Latest one-way reconciliation merge SHA: `eb7e9db6778d82896b70e70b14bec0dfabd2884d`
- Date: 2026-08-03 (`America/Santo_Domingo`)
- Browser: Playwright Chromium launched with explicit `headless: true`; one isolated browser context and one page per locale
- Runtime: local Next.js and FastAPI against an isolated disposable Supabase project; real OpenRouter search/voice and provider-backed asset resolution
- Search: `openrouter_web_search` with `x-ai/grok-4.3`

No provider credential, password, bearer token, cookie, user id, conversation id, raw transcript export, or raw database row is preserved here.

## Review finding and repair

Exact-head Codex review found that consecutive content-less citation markers could lose their shared claim. Advancing the claim floor after the first marker left the second citation with an empty snippet. If sanitization then rejected the first citation, the surviving source could no longer ground the candidate. Mandatory review also found that punctuation-only separators such as `citation 1, citation 2` must remain in the same group.

Both cases reproduced as red adapter tests. The repair now groups consecutive citation markers until substantive alphanumeric claim text appears, and every citation in a group recovers context ending at the group's first marker. This preserves the shared claim for direct, whitespace-separated, and punctuation-separated markers, including when the first source is rejected. It still advances the claim floor when real text starts the next claim.

Mocked tests prove these parser branches only. They are not the live or browser acceptance evidence.

## Exact-head deterministic gates

- Discovery adapters and contracts: 49 passed
- Hermetic runtime, spine, and discovery adapters: 1,608 passed
- Non-live eval suite: 92 passed, 1 live test skipped by design
- Ruff, modularity, environment topology, and diff checks: passed
- Mandatory bounded review after the punctuation repair: READY with no findings

## Exact-head live turn evaluation

The five issue #344 complete-turn cases were rerun at exact SHA `ff0ea0a1` because this repair changes discovery-provider semantics.

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

Both accepted journeys used the configured real OpenRouter search path and provider-backed asset resolution at exact SHA `ff0ea0a1`.

| Locale | User turn | Result | Evidence |
|---|---|---|---|
| English | `Find trending cryptocurrencies right now.` | Resolver-verified `ONDO/USD` with three sources and a typed Backtest action | `english-trending-crypto-grounded.png` |
| `es-419` | `Busca acciones farmacéuticas actuales de Estados Unidos que coticen en bolsa.` | Resolver-verified `REGN` and `MRNA` with four sources and localized Simular actions | `spanish-pharma-grounded.png` |

The English page emitted five expected `401` responses before anonymous guest bootstrap completed and emitted zero console errors after authentication or during the accepted turn. The Spanish page likewise emitted zero console errors after guest bootstrap and during its accepted turn. Both screenshots were visually inspected after capture.

## Retention disposition

- `528cce13` remains historical authority for its exact-head 43/43 broad live evaluation, original bilingual grounded-search matrix, retryable recovery, and labeled failure probes.
- `427b374f` remains authority for corrected non-retryable English/Spanish authorization voice and neighboring recovery guidance.
- `dca757bd` remains authority for the dotted-corporate-suffix repair and its exact-head acceptance.
- `9f153cbb` remains authority for claim-initial dotted-prefix detection and the terminal-initialism repair.
- `ff0ea0a1` is current authority for adjacent citation grouping, the five affected live issue #344 turns, and bilingual working-provider grounding after the latest exact-head Codex finding.
- No artifact claims hosted/default Perplexity health, hosted deployment health, tester exposure, or release promotion.

## Artifact hashes

| Artifact | SHA-256 |
|---|---|
| `live-eval-scorecard.json` | `cdfa7276d1b63428c973a791546d9f46c0b5742f81ef4c24c92bd9c44f19ddd3` |
| `english-trending-crypto-grounded.png` | `e2f859beb7bef59f6960df4ad634260235549020a8567978dbc7ae7348926c3d` |
| `spanish-pharma-grounded.png` | `2ec16b58843a3c24475f24f1a6d0b785080c224170a2545e957b04f4d85f4efb` |

## Lock declaration

This report is the acceptance baseline for executable SHA `ff0ea0a1e9eeee394b130187984d3ed6012b5a06`. A later evidence-only commit may carry this pack if exact-final-head deterministic verification confirms the executable tree is unchanged. It does not authorize merge, deploy, tester exposure, hosted configuration changes, issue closure, or release promotion. Founder approval remains required.
