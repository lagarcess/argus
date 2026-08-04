# Argus issue #344 citation-fix acceptance evidence

## Audit identity

- Branch: `codex/issue-344-grounded-discovery-retry`
- Exact code and acceptance SHA: `f640d480a949a65983d99bfe3e09a03dc7345162`
- Original integration base: `6533377c1a08539136a622a7d53eee20d0efd845`
- Integration SHA at acceptance capture: `4a8872f5069f43e478579d59ba0d0907af1016a8`
- Current integration SHA: `7568eff3c064de4df8837021dff02fe639b8d409`
- Latest one-way integration merge SHA: `77b3c70c49824662b48c5d782240e6d64717f839`
- Date: 2026-08-03
- Persona: one disposable authenticated account, exercised in English and `es-419`
- Environment: local Next.js frontend and FastAPI backend with isolated disposable Supabase project `argus-qa-344-abbrev`; real OpenRouter and Alpaca APIs
- Working search provider/model: `openrouter_web_search` with `x-ai/grok-4.3`
- Failure probes: an explicit invalid OpenRouter model for retryable provider failure and an explicit invalid Perplexity credential for non-retryable authorization failure
- No provider credential, bearer token, cookie, password, user id, conversation id, transcript export, or raw database row is preserved here.

## Why this run exists

The final `@codex` review at `faa3c06e` found that citation claim segmentation treated periods in corporate abbreviations such as `Inc.` and `S.A.` as sentence boundaries. That could discard the first clause and its citation even when the claim was supported. Commit `f640d480` preserves recognized corporate abbreviations while retaining the prior same-line wrong-source guard.

Because this repair changes discovery citation semantics, the earlier `528cce13` live evidence is superseded rather than merely retained. This directory contains the fresh exact-code-head live scorecard and bilingual browser acceptance evidence required by the issue contract.

## Exact-head live evaluation

Command:

```text
ARGUS_RUN_LIVE_EVALS=1 ARGUS_EVAL_ENV_FILE=.env ARGUS_MARKET_DATA_PROVIDER_MODE=live_provider poetry run pytest tests/evals/test_measurement_eval_live.py -q
```

Result: `1 passed` in 1119.99 seconds. The durable scorecard `live-eval-scorecard.json` reports 44 passed, 0 failed, 0 skipped, 0 expected failures, and 0 unexpected passes. All four issue #344 cases passed:

- `asset_discovery_recent_ipo_exact_issue_344`
- `asset_discovery_trending_crypto_exact_issue_344`
- `asset_discovery_old_pharma_escalation_exact_issue_344`
- `asset_discovery_semantic_pharma_escalation_issue_344`

This is live provider evidence. Mocked and hermetic suites are recorded separately as code-path regression evidence only.

## Locked bilingual real-API browser matrix

| ID | Journey | Locale | Result | Evidence |
|---|---|---|---|---|
| EN-01 | General pharmaceutical discovery | English | Five resolver-backed general-knowledge candidates, explicit non-current marker, and generated current-search action | `english-general-pharma.png` |
| EN-02 | Generated current-search escalation | English | The generated action ran through the ordinary composer and returned grounded, resolver-verified candidates with cited sources; names include corporate abbreviations | `english-escalation-grounded.png` |
| EN-03 | Retryable provider failure | English | The trending-crypto request displayed `Retry` after an injected invalid search model | `english-transient-retry-visible.png` |
| EN-04 | Same-request recovery | English | `Retry` replayed the single original request after provider recovery and completed with a truthful verified-empty result | `english-retry-recovered-verified-empty.png` |
| EN-05 | Unauthorized provider | English | Honest unavailable response with no misleading `Retry` control | `english-authorization-no-retry.png` |
| ES-01 | General pharmaceutical discovery | `es-419` | Five resolver-backed general-knowledge candidates, localized non-current marker, and localized current-search action | `spanish-general-pharma.png` |
| ES-02 | Generated current-search escalation | `es-419` | The localized generated action ran through the ordinary composer and returned grounded, resolver-verified candidates with cited sources; names include corporate abbreviations | `spanish-escalation-grounded.png` |
| ES-03 | Retryable provider failure | `es-419` | The trending-crypto request displayed `Reintentar` after the injected invalid search model | `spanish-transient-retry-visible.png` |
| ES-04 | Same-request recovery | `es-419` | `Reintentar` replayed the single original request after provider recovery and reached an honest asset-resolution terminal response without another retry control | `spanish-retry-recovered-honest-terminal.png` |
| ES-05 | Unauthorized provider | `es-419` | Localized unavailable response with no misleading `Reintentar` control | `spanish-authorization-no-retry.png` |

All preserved journeys were visually inspected. The successful authorization probes reported zero browser console errors; development-only warnings were present. One earlier Spanish authorization attempt was interrupted by the browser connection and produced an abandoned lifecycle, so it is excluded from acceptance evidence. The probe was repeated cleanly and the successful no-Retry result is the preserved artifact.

## Durable state observations

The isolated database contained only aggregate test evidence at audit end:

- 7 conversations
- 11 user messages and 10 assistant messages
- 8 completed, 2 `recoverable_failed`, and 1 abandoned turn lifecycle

The two recoverable failures are the injected English and Spanish transient-provider probes. Their Retry actions reached completed terminal responses without duplicating the original visible user request. The single abandoned lifecycle is the explicitly excluded browser-interrupted authorization attempt above.

## Artifact hashes

| Artifact | SHA-256 |
|---|---|
| `english-authorization-no-retry.png` | `e4b40927ec17c3f3b5417893b40f63aafabce4585425423884f140de533ae330` |
| `english-escalation-grounded.png` | `3376942c6234ddc7ca796af58b61b711f5e380eeb482d2cd3df5a0b5ef54490b` |
| `english-general-pharma.png` | `2dcc3ea5d806d3e0a90c01433d861ef3f66e03bba8ac9c5e34c2347e28184b4d` |
| `english-retry-recovered-verified-empty.png` | `7a1664609dde3deaeba08298e18338fd10404b86714440e4bca76d0185e8153c` |
| `english-transient-retry-visible.png` | `7c5d86e098fdd1efe03eaa5b9e6ae51074dcbe40b97c3d59165c34d5bbafb1d8` |
| `live-eval-scorecard.json` | `bbb45c27c4d5c2f05ed39f03c4e0df451b9501c6fa670765db1ee4eba67bd7d8` |
| `spanish-authorization-no-retry.png` | `ed1f22ca62b9f51a31c2a49b90a72fa730bf2bddd0244f44bccd04af1ea4ca34` |
| `spanish-escalation-grounded.png` | `2af1a2fc80e7b6d9cc3e79cf9f7d47c627bebba573f1245070df479cbb3c6804` |
| `spanish-general-pharma.png` | `049b2916f73cc047342f9ed1ac57dea868576e79fc967e109b669fb6ff97d003` |
| `spanish-retry-recovered-honest-terminal.png` | `6c4ef8d97e0fa014cec1493f50e094aaf302287788a8438bd2d2c95d4cb61756` |
| `spanish-transient-retry-visible.png` | `c5b46fd36e89b8a2dbf743b88e58ca143a78b272da12ba178f9d3c4b2860dd3a` |

## Retention and authority

- This exact-head 44/44 live scorecard and bilingual real-API matrix supersede the earlier `528cce13` live evidence for acceptance authority.
- Integration advanced after capture with first-login Guest-claim profile creation plus documentation. The delta changes auth/profile initialization, not existing-profile locale reads, chat interpretation, discovery, search, citation, Retry, or the browser journeys exercised here. It therefore has no semantic overlap with issue #344 acceptance. The evidence is retained after the one-way merge and an exact-final-head hermetic rerun.
- A later commit that adds only this evidence may retain it after an exact-final-head hermetic rerun and a diff confirming no executable change.
- No merge, deploy, hosted configuration change, issue closure, migration, or tester exposure is authorized. Founder approval remains required.
