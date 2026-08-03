# Argus issue #344 exact-code-head acceptance report

## Audit identity

- Branch: `codex/issue-344-grounded-discovery-retry`
- Exact code SHA: `2a758d2ce84c7b058f3c5d87a0f1e313cf770eba`
- Original integration base: `6533377c1a08539136a622a7d53eee20d0efd845`
- Reconciled integration SHA: `26ab31b211302e480379e609d901d7e040c9c859`
- Integration merge SHA: `f63e4a2244ef46f8fc8f5559ac6cb0c9ee3ccf89`
- Date: 2026-08-03
- Persona: one disposable authenticated account, exercised in English and `es-419`
- Environment: local Next.js frontend and FastAPI backend with isolated disposable Supabase project `argus-qa-344-final`; real OpenRouter and Alpaca APIs
- Working search provider/model: `openrouter_web_search` with `x-ai/grok-4.3`
- Failure probes: an explicit invalid Perplexity credential for authorization failure and an explicit invalid OpenRouter model for retryable provider failure
- No provider credential, bearer token, cookie, user id, conversation id, transcript body, or raw database row is preserved in this report.

## Acceptance boundary

Mocked and deterministic tests prove the code path only. The issue #344 claim below rests on real-interpreter live cases and bilingual real-API browser QA on the exact code SHA above.

The broad live suite did not finish fully green. Both permitted exact-head runs passed all four issue #344 cases, but each had one different unrelated model-classification failure. This evidence supports the bounded issue #344 behavior; it does not claim a clean full-suite promotion gate.

## Live eval

Command for both runs:

```text
ARGUS_RUN_LIVE_EVALS=1 ARGUS_EVAL_ENV_FILE=.env ARGUS_MARKET_DATA_PROVIDER_MODE=live_provider poetry run pytest tests/evals/test_measurement_eval_live.py -q
```

| Run | Result | Issue #344 cases | Other failure | Evidence |
|---|---:|---:|---|---|
| First | 43/44 in 19m31s | 4/4 passed | Issue #336 messy-English Apple opening omitted `AAPL` and requested `asset_universe` instead of `date_range` | `live-eval-first-red.json` |
| Permitted rerun | 43/44 in 17m11s | 4/4 passed | Issue #244 comparison anchor returned `relationship=category` instead of `comparison` | `live-eval-rerun-red.json` |

The two failures are different and outside the code changed by the citation repair. They are retained as review risks, not converted into expected failures and not hidden behind the mocked suite.

## Bilingual real-API browser matrix

| ID | Journey | Locale | Result | Evidence |
|---|---|---|---|---|
| EN-01 | Current 2025 IPO discovery | English | Resolver-verified `MDLN` with four current sources | `english-current-ipo-grounded.png` |
| EN-02 | Trending crypto discovery | English | Resolver-verified `BNB/USD` with three current sources | `english-current-crypto-grounded.png` |
| EN-03 | General pharmaceutical discovery | English | Five general-knowledge candidates, non-current marker, and current-search action | `english-general-pharma.png` |
| EN-04 | General-to-current escalation | English | Four verified current candidates with five sources | `english-escalation-grounded.png` |
| EN-05 | Unauthorized provider | English | Honest unavailable response with no Retry control | `english-auth-unavailable-no-retry.png` |
| ES-01 | Unauthorized provider | `es-419` | Localized unavailable response with no Reintentar control | `spanish-auth-unavailable-no-retry.png` |
| ES-02 | General pharmaceutical discovery | `es-419` | Five general-knowledge candidates, localized non-current marker, and localized current-search action | `spanish-general-pharma.png` |
| ES-03 | General-to-current escalation | `es-419` | Four verified current candidates with five sources | `spanish-escalation-grounded.png` |
| ES-04 | Provider failure and same-request recovery | `es-419` | Invalid model rendered Reintentar; after provider recovery the same control retained one original request and returned three verified candidates with five sources | `spanish-provider-retry-pharma-visible.png`, `spanish-provider-retry-pharma-grounded.png` |

Three provider-variance diagnostics are also retained:

- The first English crypto search completed honestly with no verified candidates before the next exact prompt returned grounded `BNB/USD`: `english-current-crypto-verified-empty.png`.
- The first Spanish retry journey displayed Reintentar and then completed as verified-empty after provider recovery: `spanish-provider-retry-visible.png`, `spanish-provider-retry-verified-empty.png`.

They are excluded from the successful grounded and successful-retry claims above.

## Durable state observations

The isolated database contained only aggregate test evidence at audit end:

- 15 user messages and 15 assistant messages
- 7 discovery sidecars containing 23 resolver-verified candidates and 22 sources
- 2 retryable `discovery_search_failed` records
- 2 non-retryable `discovery_unavailable` records
- 4 non-retryable `discovery_no_verified_candidates` records, including the diagnostic paths above
- 13 completed and 2 `recoverable_failed` turn lifecycles
- 84 route receipts
- 97 cost-ledger entries totaling `$0.62846436`

## Deterministic exact-code-head evidence

- Hermetic runtime/spine sweep: 1,471 passed with provider keys blank and `synthetic_unit_fixture`
- Mocked eval harness: 70 passed
- Discovery adapter plus modularity tests: 23 passed
- Ruff and `git diff --check`: passed
- Modularity: `llm_interpreter.py` is 5,354 lines, exactly at its 5,354-line limit
- Composed diff versus integration for `llm_interpreter.py`: 8 additions, 8 deletions; net zero

These checks remain code-path proof and do not replace the live evidence above.

## Evidence retention disposition

- `528cce13` remains committed under `docs/reports/evidence/issue-344/528cce13/` as historical acceptance evidence.
- It is **not retained as current acceptance authority**. The integration reconcile and the later citation-span repair touched discovery/interpreter semantics.
- Intermediate SHA `f63e4a22` is also not accepted: its live rerun reached 44/44, but real browser QA exposed that OpenRouter annotations point to citation markers rather than claim spans, causing valid candidates to be stripped.
- Exact code SHA `2a758d2c` binds URL-marker citations only to the immediately adjacent claim, passed the focused regression, and produced the live/browser evidence in this directory.
- A later commit that adds only this evidence directory may retain the `2a758d2c` live/browser proof after an exact-head hermetic rerun and a diff confirming no executable change.

## Ambiguity and exclusions

- The broad live suite is not fully green: two permitted runs ended 43/44 with different unrelated failures. No merge, issue-close, or promotion claim should treat this as 44/44.
- The default local Perplexity credential was not treated as healthy. The audit proves non-retryable authorization classification with an explicit invalid credential and proves the configured OpenRouter path.
- No hosted deployment, tester exposure, provider fallback chain, real backtest, real-money action, shared environment mutation, or hosted data write occurred.
- A pre-existing Python 3.10/local-Supabase timestamp serialization edge caused one conversation hydration failure. The newest disposable lifecycle timestamp was advanced by one microsecond, after which hydration returned cleanly. No repository code or shared environment changed.

## Artifact hashes

| Artifact | SHA-256 |
|---|---|
| `english-auth-unavailable-no-retry.png` | `8e3da2b37fafaf115c4629d918a2e292ca4fc40a74da8acb1cb6938fbcbd2527` |
| `english-current-crypto-grounded.png` | `f436e0718cb753b44a394f02891864cd875cc7b5e2525080feb060e1b747b717` |
| `english-current-crypto-verified-empty.png` | `826cce5f9b2ec7d22099892c90289624e75b080b8956f57bc05e3bbc94d17c06` |
| `english-current-ipo-grounded.png` | `3af9b17c52f7af7799242e0257ec2bd12cf0483b7f846f3b3f97a6b96804cdab` |
| `english-escalation-grounded.png` | `fb7b4e5a02c3cd7ab682151b2a4ad4f6b7987b40504e71d5e34651b9be389f8a` |
| `english-general-pharma.png` | `174ca274c63fc4209a9b0e1ebb4a993fd197f93fbe32080fe64832b9c0dad50a` |
| `live-eval-first-red.json` | `473d6876b256699e553aa4a6472d4998893222966f17800b5e8e624620f5db9c` |
| `live-eval-rerun-red.json` | `9413698bb8dfef5e0ead8df1b4e3e5644c6cc65ba212d60ab43d85117ec71d38` |
| `spanish-auth-unavailable-no-retry.png` | `cc0891678e9ef2b731b53f989ec95d2408b2f0a534bcc1fc47d3773b141006c7` |
| `spanish-escalation-grounded.png` | `37809ef368aa1da79de56c42990eb64585ac93bf91379660c4ccfcfa3a3de9bd` |
| `spanish-general-pharma.png` | `03941fcbf7607f72b9e49ed2c17c197d6a9b4c98bd0323274274d08b8b26bf86` |
| `spanish-provider-retry-pharma-grounded.png` | `71057b54d73700104e8f2f1f4a4ed18a0d88ae0908dafb447f2f94522c1c37e1` |
| `spanish-provider-retry-pharma-visible.png` | `95d2364a72790d492121189842d18850c09c20e986b5d4785f106256c2f8bfc5` |
| `spanish-provider-retry-verified-empty.png` | `74d809dc9f411e9a045ca07f177c418264d0d8548632e386f85f1d6a197bed61` |
| `spanish-provider-retry-visible.png` | `af42039bca816e6f590527d12fa46f55b2369156ef251b89a75dc6f7f90a0c54` |

## Cleanup and authority

The isolated browser, frontend, backend, and Supabase processes are disposable and must be stopped after evidence capture. This report does not authorize merge, deploy, tester exposure, hosted configuration changes, or issue closure. Founder approval remains required.
