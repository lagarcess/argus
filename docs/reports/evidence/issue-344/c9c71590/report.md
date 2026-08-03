# Argus issue #344 final citation-boundary acceptance evidence

## Audit identity

- Branch: `codex/issue-344-grounded-discovery-retry`
- Exact code and acceptance SHA: `c9c71590596a322a0f91602734feb085bc4588e6`
- Original integration base: `6533377c1a08539136a622a7d53eee20d0efd845`
- Current integration SHA: `7568eff3c064de4df8837021dff02fe639b8d409`
- Latest one-way integration merge SHA: `77b3c70c49824662b48c5d782240e6d64717f839`
- Date: 2026-08-03
- Persona: one disposable authenticated account, exercised in English and `es-419`
- Environment: local Next.js frontend and FastAPI backend with isolated disposable Supabase project `argus-qa-344-c9`; real OpenRouter and Alpaca APIs
- Browser mode: one named Playwright Chromium session with explicit `headless: true`, a fixed viewport, and one reused page
- Working search provider/model: `openrouter_web_search` with `x-ai/grok-4.3`
- Failure probes: an explicit invalid OpenRouter model for retryable provider failure and an explicit invalid Perplexity credential for non-retryable authorization failure
- No provider credential, bearer token, cookie, password, user id, conversation id, transcript export, or raw database row is preserved here.

## Why this run exists

Independent review found that the first corporate-abbreviation repair could merge an unrelated sentence ending in `Corp.` or `Inc.` into the adjacent cited sentence. Commit `c9c71590` now treats a recognized abbreviation period as internal only when the following claim text continues in lowercase. The targeted regression went red before the implementation and green after it; the existing `Example Inc. recently...` and `Acme S.A. completed...` cases remain green.

Because this changes discovery citation semantics, the prior `f640d480` acceptance pack is superseded. This directory contains a fresh live scorecard and headless bilingual real-API browser evidence from the exact code head.

## Exact-head live evaluation

Command:

```text
ARGUS_RUN_LIVE_EVALS=1 ARGUS_EVAL_ENV_FILE=.env ARGUS_MARKET_DATA_PROVIDER_MODE=live_provider poetry run pytest tests/evals/test_measurement_eval_live.py -q
```

Result: `1 passed` in 1711.30 seconds. `live-eval-scorecard.json` reports 44 passed, 0 failed, 0 skipped, 0 expected failures, and 0 unexpected passes. All four issue #344 cases passed:

- `asset_discovery_recent_ipo_exact_issue_344`
- `asset_discovery_trending_crypto_exact_issue_344`
- `asset_discovery_old_pharma_escalation_exact_issue_344`
- `asset_discovery_semantic_pharma_escalation_issue_344`

This is live provider evidence. Mocked and hermetic suites are code-path regression evidence only.

## Bilingual headless real-API browser matrix

| ID | Journey | Locale | Result | Evidence |
|---|---|---|---|---|
| EN-01 | General pharmaceutical discovery | English | Five resolver-backed general-knowledge candidates, explicit non-current marker, and generated current-search action | `english-general-pharma.png` |
| EN-02 | Generated current-search escalation | English | The generated natural-language action re-entered the interpreter and returned five grounded candidates with three sources; corporate abbreviations remained attached to their cited claims | `english-escalation-grounded.png` |
| EN-03 | Retryable provider failure | English | The trending-crypto request displayed `Retry` after an injected invalid search model | `english-transient-retry-visible.png` |
| EN-04 | Same-request recovery | English | `Retry` replayed the one original request after provider recovery and completed with a truthful verified-empty result | `english-retry-recovered-verified-empty.png` |
| EN-05 | Unauthorized provider | English | The generated current-search action reached an honest unavailable response with no misleading `Retry` control | `english-authorization-no-retry.png` |
| ES-01 | General pharmaceutical discovery | `es-419` | Five resolver-backed general-knowledge candidates, localized non-current marker, and localized current-search action | `spanish-general-pharma.png` |
| ES-02 | Generated current-search escalation | `es-419` | The localized natural-language action re-entered the interpreter and ultimately returned three grounded candidates with five sources; corporate abbreviations remained attached to cited claims | `spanish-escalation-grounded.png` |
| ES-03 | Retryable provider failure | `es-419` | The trending-crypto request displayed `Reintentar` after the injected invalid search model | `spanish-transient-retry-visible.png` |
| ES-04 | Same-request recovery | `es-419` | `Reintentar` replayed the one original request after provider recovery and completed with a truthful verified-empty result | `spanish-retry-recovered-verified-empty.png` |
| ES-05 | Unauthorized provider | `es-419` | A direct current-search request reached a localized unavailable response with no misleading `Reintentar` control | `spanish-authorization-no-retry.png` |

All ten screenshots were visually inspected. Acceptance navigations reported zero console errors; development-only warnings were present.

### Disclosed live variance

The English escalation grounded on its first generated-current action. In the preserved Spanish escalation conversation, the first generated-current action returned another general-knowledge answer; repeating the identical generated-current action then grounded with five sources. Two later attempts to obtain a clean first-attempt Spanish escalation encountered retryable provider failures before producing general candidates. Those failed attempts are excluded from the matrix, but not hidden from this report.

The exact-head live interpreter suite independently passed both issue #344 escalation cases. The browser run therefore proves that the localized action re-enters the real interpreter and can reach grounded output, but it does not prove first-attempt Spanish reliability. Review and promotion should weigh this disclosed variance; mocked coverage is not used to erase it.

## Durable state observations

The isolated database contained only aggregate test evidence at audit end:

- 8 conversations
- 14 user messages and 14 assistant messages
- 10 completed and 4 `recoverable_failed` turn lifecycles

Two recoverable failures are the intentional English and Spanish invalid-model probes. Two are the disclosed unplanned Spanish provider failures during clean-escalation attempts. Retry recovery preserved one visible original user request in both intentional failure journeys.

## Artifact hashes

| Artifact | SHA-256 |
|---|---|
| `english-authorization-no-retry.png` | `a706d1230749a1a4b47f1885a7279265d8cd2c376bb466503ae9b911b0e01de1` |
| `english-escalation-grounded.png` | `38362cd7948e361d42747d72df58f14e0d525a8b4f3a0bb55dd0e265d98e842d` |
| `english-general-pharma.png` | `58bdfe72bc22cdd90277b0fe320666f2f32cea9b9545ec072ee7927f034c5696` |
| `english-retry-recovered-verified-empty.png` | `ddce7e733062f9229e5c298b92a7447bffe7a7ba1aca7aa7f1f955ae938d79ad` |
| `english-transient-retry-visible.png` | `de4f7ea47eb7e5344bd217a0ce278a2d26159d20de210f5d69a6dddc1ed87d22` |
| `live-eval-scorecard.json` | `5b50da1753e2a99e166b1114b3ef787a75c6e358a8f5bfe952678d129642547a` |
| `spanish-authorization-no-retry.png` | `90bd6210a07d6419d2d3d4716b5429a60cd6b11040a1378cfa76f4a599142f2e` |
| `spanish-escalation-grounded.png` | `ca766001979b040e7615d2d80863cb9bdae93c9fee5c9fdb85f410b86fe213d7` |
| `spanish-general-pharma.png` | `b499b6ac7a87320ef0fe3c7911de1c79f8888c2f881af1219f6805898434598f` |
| `spanish-retry-recovered-verified-empty.png` | `4aa3e4afad8a571d5844eb6eea3141338a0c38787675acb31db10731d4d129fc` |
| `spanish-transient-retry-visible.png` | `a680e38e3c884abc3bc937687ecfa516e64ee82f68dfc2341f9b7fe126034cee` |

## Retention and authority

- This exact-head 44/44 live scorecard supersedes the earlier live packs for citation-boundary acceptance authority.
- The browser artifacts are exact-code-head real-API evidence with the Spanish first-attempt limitation disclosed above.
- Integration changes after the earlier capture affect first-login Guest-claim profile initialization, not existing-profile locale reads, chat interpretation, discovery, search, citation, Retry, or these browser journeys.
- A later evidence-only commit may retain this pack after an exact-final-head hermetic rerun and executable-diff confirmation.
- No merge, deploy, hosted configuration change, issue closure, migration, or tester exposure is authorized. Founder approval remains required.
