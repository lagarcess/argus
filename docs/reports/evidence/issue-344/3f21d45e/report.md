# Issue #344 lowercase-brand citation evidence

## Audit identity

- Branch: `codex/issue-344-grounded-discovery-retry`
- Exact executable and acceptance SHA: `3f21d45e8c8e436f4723c1f10c918e273684ecf8`
- Original integration base: `6533377c1a08539136a622a7d53eee20d0efd845`
- Current integration SHA: `b36e7396c28c84d8acafdb86d2b81535dd0c6942`
- Latest one-way reconciliation merge SHA: `eb7e9db6778d82896b70e70b14bec0dfabd2884d`
- Date: 2026-08-03 (`America/Santo_Domingo`)
- Browser: Playwright Chromium launched with explicit `headless: true`; no visible browser window was opened
- Runtime: local Next.js and FastAPI against the isolated disposable `argus-qa` Supabase project; real OpenRouter search/voice and provider-backed asset resolution
- Search: `openrouter_web_search` with `x-ai/grok-4.3`

No provider credential, password, bearer token, cookie, user id, conversation id, raw transcript export, or raw database row is preserved here.

## Final cloud-review finding and repair

Exact-head Codex review found that a content-less citation following an all-lowercase brand could retain an unsupported preceding company. For example, `Unsupported Inc. adidas completed an IPO.[citation]` recovered the entire combined string because the earlier boundary logic recognized lower-camel and dotted brands but not all-lowercase styling.

The first regression reproduced that failure for `adidas` and `bp`. The initial metadata-based repair was then rejected by mandatory bounded review because case-insensitive matching also split normal continuations such as `Example Inc. today announced an IPO.` when the title started with `Today`.

The final repair uses exact case-sensitive style agreement between the claim's leading lowercase token and the citation title's leading token. It separates `adidas`/`adidas` and `bp`/`bp`, while preserving `today`/`Today` and `company`/`Company`. Mandatory re-review returned READY with no findings. When source-title styling does not agree, the parser fails closed by retaining context rather than inventing a boundary.

Mocked and hermetic tests prove these parser branches only. They do not prove the live provider or browser acceptance claims.

## Exact-code-head deterministic gates

- Hermetic runtime, spine, and discovery adapters: 1,616 passed
- Non-live eval suite: 92 passed, 1 live test skipped by design
- Provider contracts and adapters: 56 passed
- Focused adapter matrix: 38 passed
- Ruff, modularity, environment topology, and diff checks: passed
- `llm_interpreter.py`: 5,353 lines against the composed-tree limit of 5,354
- Mandatory bounded review: initial repair NOT READY with one confirmed false-positive finding; corrected repair READY with no findings

## Exact-code-head live turn evaluation

The five affected issue #344 complete-turn cases were rerun at executable SHA `3f21d45e` because this repair changes discovery citation semantics.

- Result: 5 passed, 0 failed, 0 skipped, 0 expected failures, 0 unexpected passes
- Durable scorecard: `live-eval-scorecard.json`
- Passed cases:
  - `asset_discovery_recent_ipo_exact_issue_344`
  - `asset_discovery_trending_crypto_exact_issue_344`
  - `asset_discovery_old_pharma_escalation_exact_issue_344`
  - `asset_discovery_semantic_pharma_escalation_issue_344`
  - `asset_discovery_spanish_generated_pharma_escalation_issue_344`

## Bilingual headless grounded-browser acceptance

Both accepted journeys ran at executable SHA `3f21d45e` with explicit Chromium `headless: true`, the configured real OpenRouter search path, and provider-backed asset resolution.

| Locale | User turn | Result | Evidence |
|---|---|---|---|
| English | `Search current sources for publicly traded pharmaceutical companies comparable to PFE, MRK, and ABBV.` | Resolver-verified actions including `Backtest JNJ`, five visible sources, and zero post-auth/turn browser errors | `english-pharma-comparison-grounded.png` |
| `es-419` | `Busca en fuentes actuales empresas farmacéuticas que coticen en bolsa comparables con PFE, MRK y ABBV.` | Localized resolver-verified actions including `Simular JNJ`, five visible sources, and zero post-auth/turn browser errors | `spanish-pharma-grounded.png` |

Both screenshots were visually inspected after capture. The English result exposed JNJ, AMGN, GILD, and REGN actions; the Spanish result exposed JNJ and NVS actions. The accepted matrix used two fresh temporary guest contexts.

The isolated loopback visitor already had two earlier discovery counters from prior exact-head QA. Before this matrix, only that loopback visitor's `chat_messages` and `discovery_searches` rows were removed from disposable local `argus-qa`; no hosted or user data was touched.

## Retention disposition

- `528cce13` remains historical authority for its exact-head 43/43 broad live evaluation, original bilingual grounded-search matrix, retryable recovery, and labeled failure probes.
- `603c9b9e` remains historical authority for the deterministic non-retryable recovery and English/Spanish conjunction repair at that head.
- `3f21d45e` is current authority for exact-style lowercase-brand boundaries and the inherited final discovery semantics, supported by the affected five-case live evaluation and bilingual working-provider browser matrix.
- The citation repair invalidated reliance on older heads for the changed boundary. The affected complete-turn and browser surfaces were rerun; no fresh 43-case broad live burn was needed for unchanged interpreter categories.
- No artifact claims hosted/default Perplexity health, hosted deployment health, tester exposure, or release promotion.

## Artifact hashes

| Artifact | SHA-256 |
|---|---|
| `live-eval-scorecard.json` | `85e0b660e1f6e888dbd2c9fbdade8dab9dbcedd039ab0fc75081e00d3884295a` |
| `english-pharma-comparison-grounded.png` | `19f24090f9e05bb9d824916c660df324e64f912185da962c21350e5fdd61753e` |
| `spanish-pharma-grounded.png` | `2fc0c78c4308a9a166be3a99d6fec2cfe119c1682e97264a721a06656c501a84` |

## Lock declaration

This report is the acceptance baseline for executable SHA `3f21d45e8c8e436f4723c1f10c918e273684ecf8`. A later evidence-only commit may carry this pack after exact-final-head deterministic verification confirms the executable tree is unchanged. It does not authorize merge, deploy, tester exposure, hosted configuration changes, issue closure, or release promotion. Founder approval remains required.
