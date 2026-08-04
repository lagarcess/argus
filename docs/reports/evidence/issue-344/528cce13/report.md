# Argus issue #344 exact-head acceptance report

## Audit identity

- Branch: `codex/issue-344-grounded-discovery-retry`
- Exact SHA: `528cce136a7fc19660131637d7b4b6ca7dc145db`
- Original and current integration SHA at audit start: `6533377c1a08539136a622a7d53eee20d0efd845`
- Date: 2026-08-02
- Persona: one disposable authenticated account, exercised in English and `es-419`
- Environment: local Next.js frontend and FastAPI backend with isolated disposable Supabase project `argus-qa-344-4`; real OpenRouter and Alpaca APIs
- Working search provider/model: `openrouter_web_search` with `x-ai/grok-4.3`
- Failure probes: an explicit invalid Perplexity credential for authorization failure, an explicit invalid OpenRouter model for a retryable Spanish provider failure, and a naturally occurring retryable OpenRouter search failure during the English escalation
- No provider credential, bearer token, cookie, user id, conversation id, or raw database row is preserved in this report.

## Acceptance boundary

Mocked and deterministic tests prove the code path only. The acceptance claim below rests on a clean exact-head 43/43 live eval plus bilingual real-API browser QA on the same committed SHA.

## Live eval

- Command: `ARGUS_RUN_LIVE_EVALS=1 ARGUS_EVAL_ENV_FILE=.env ARGUS_MARKET_DATA_PROVIDER_MODE=live_provider poetry run pytest tests/evals/test_measurement_eval_live.py -q`
- Result: `43/43 passed` in 15m37s on exact SHA `528cce136a7fc19660131637d7b4b6ca7dc145db`
- Authoritative scorecard: `scorecard.json` (the committed copy of `temp/argus_eval_scorecards/argus-eval-scorecard-20260802T181257Z.json`)
- All four issue #344 cases passed with `semantic_turn_act=asset_discovery`, `relationship=category`, the expected equity or crypto hint, and `needs_current_facts=true`.

## Bilingual browser matrix

| ID | Journey | Locale | Result | Evidence |
|---|---|---|---|---|
| EN-01 | Recent IPO equity discovery | English | Four resolver-verified candidates and five current sources | `english-current-ipo.png` |
| EN-02 | Trending crypto discovery | English | Resolver-verified `ONDO/USD` and two current sources | `english-current-crypto.png` |
| EN-03 | General pharmaceutical discovery | English | Five general-knowledge candidates, the non-current marker, and the current-search action | `english-general-pharma.png` |
| EN-04 | General-to-current escalation and Retry | English | The asset-aware inferred user turn first hit a real temporary failure; Retry kept one copy of that turn and recovered to two verified candidates and four current sources | `english-transient-retry-visible.png`, `english-escalation-retry-grounded.png` |
| EN-05 | Unauthorized provider | English | Localized honest unavailable response with no Retry control | `english-auth-unavailable-no-retry.png` |
| ES-01 | Unauthorized provider | `es-419` | Localized unavailable response with no Reintentar control | `spanish-auth-unavailable-no-retry.png` |
| ES-02 | General pharmaceutical discovery | `es-419` | Five general-knowledge candidates, localized non-current marker, and localized current-search action | `spanish-general-pharma.png` |
| ES-03 | General-to-current escalation | `es-419` | The semantic user turn `Buscar acciones actuales para esta categoría: acciones farmacéuticas` returned five verified candidates and five current sources | `spanish-escalation-grounded.png` |
| ES-04 | Provider failure and same-request recovery | `es-419` | Invalid configured search model rendered Reintentar; restoring the working provider and clicking the same control kept one original request and returned five verified candidates with five sources | `spanish-provider-retry-visible.png`, `spanish-provider-retry-grounded.png` |

One additional Spanish escalation attempt naturally failed and its first Retry completed as a verified-empty search; `spanish-transient-retry-visible.png` preserves that diagnostic path. It is excluded from the successful escalation and recovery claims above.

## Observed contract truth

- Authorization failures persisted `discovery_unavailable`, `retryable=false`; neither locale rendered Retry.
- Temporary provider failures persisted `discovery_search_failed`, `retryable=true`; both locales rendered Retry or Reintentar.
- The English escalation Retry and Spanish IPO Retry each retained exactly one visible copy of the original request and returned grounded candidates after provider recovery.
- Both escalation actions sent natural, asset-aware user turns back through the real interpreter and API.
- Candidate rows remained backend-owned, resolver-verified, and source-corroborated before display.
- A clean final `es-419` reload recorded zero console errors, zero failed requests, and zero HTTP error responses. `/me`, the conversation list, and persisted-message hydration all returned HTTP 200.

## Typed and durable evidence

The isolated database contained:

- 14 user messages and 14 assistant messages across 8 conversations
- 8 discovery sidecars containing 1-5 candidates and 0-5 sources, 32 candidates and 21 sources in total
- 2 non-retryable `discovery_unavailable` records
- 3 retryable `discovery_search_failed` records
- 1 non-retryable `discovery_no_verified_candidates` record from the excluded verified-empty diagnostic
- 11 completed and 3 `recoverable_failed` turn lifecycles
- 84 route receipts
- 95 cost-ledger entries totaling `$0.43082035`
- 6 succeeded and 2 failed `openrouter_web_search` research entries, plus 3 failed unknown-provider authorization/availability entries

These aggregates intentionally exclude identifiers, transcript bodies, tokens, cookies, and provider credentials.

## Screenshot hashes

| Screenshot | SHA-256 |
|---|---|
| `english-auth-unavailable-no-retry.png` | `9cf64cf1fee13ac2547b5d2fbd76d37c76c258807b16a4bb67a58985a052b480` |
| `english-current-crypto.png` | `51e9bbc8e5cae9b6e073c6323cca5de858f44301c00bd501b7774c41d0181f5d` |
| `english-current-ipo.png` | `29712ea551eedcd8cf87dd09e7472edb79599f31d418484333714f8039dd568f` |
| `english-escalation-retry-grounded.png` | `ffa99cbdb1498a1083d767b59986997c2223cfe9e3f6d01b0e86f87a265f2173` |
| `english-general-pharma.png` | `289cc1ff0cfb13fb92ec1f8c848f6eba938c6e65ab87b72181a0ccb29261b1ef` |
| `english-transient-retry-visible.png` | `efd2a5086908372b584ed876714820fe2a95a88a8b2190bd9819579e42168f6b` |
| `spanish-auth-unavailable-no-retry.png` | `26548c3df3ef738274ce322e5d8caace6251a3234aaf232d867a06e28a839d83` |
| `spanish-escalation-grounded.png` | `06e164641335838eb02501e4f4d5ce9e92eaf8a4721e63a914eed81253ae6777` |
| `spanish-general-pharma.png` | `206fc3815e8ebc56f03f8b69b2ebb976b9db9ffac9b8fc3412c70434b12655f4` |
| `spanish-provider-retry-grounded.png` | `8bb9244c5ed732c26641d36eeb6acd4d2b317a4207be92c0786b6f361dc32089` |
| `spanish-provider-retry-visible.png` | `96c597dbba7b72bec8de2d054e84c6d3c5e95913c1e98c77856aae68466b63dc` |
| `spanish-transient-retry-visible.png` | `852b10d90c51b55299e00be0b1f024e62bf5c4a44de6411568b2caba36e207ea` |

The screenshots are sanitized, co-located with this report, and committed as durable evidence. Their hashes match the original captures from `output/playwright/issue-344-528cce13/`.

## Ambiguity and exclusions

- The default local Perplexity credential returned HTTP 401. This audit proves the new non-retryable classification with an explicit invalid credential and proves the configured OpenRouter path; it does not claim default or hosted Perplexity credential health.
- No hosted deployment, tester exposure, provider fallback chain, backtest job, real-money action, migration, shared environment mutation, or hosted data write occurred.
- A pre-existing Python 3.10/local-Supabase timestamp serialization edge caused the conversation list to return HTTP 500 after one lifecycle timestamp ended with a trimmed fractional digit. The newest disposable lifecycle row was advanced by one microsecond, after which the list and composer recovered. No repository code, shared environment, hosted data, or non-disposable stack was changed.
- Evidence from earlier SHAs remains diagnostic history. This report is the acceptance authority for `528cce136a7fc19660131637d7b4b6ca7dc145db`.

## Cleanup disposition

The browser, frontend, backend, and isolated Supabase stack were stopped after evidence capture. The disposable user, conversations, and database rows were deleted without backup, and the temporary stack directory was moved to Trash. Sanitized screenshots and this report remain. Canonical linked environment files were never detached or rewritten.

## Lock declaration

This report is the immutable local acceptance baseline for exact SHA `528cce136a7fc19660131637d7b4b6ca7dc145db`. It does not authorize merge, deploy, tester exposure, hosted configuration changes, or issue closure.
