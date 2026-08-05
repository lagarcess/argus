# Argus issue #344 final-head browser acceptance supplement

## Audit identity

- Branch: `codex/issue-344-grounded-discovery-retry`
- Exact browser candidate SHA: `97f3c2a45c2c1aa1daa45d47fe653dbc43bdf6cc`
- Exact live-eval code SHA retained from the authoritative report: `2b8ae484d98fdc178bdce09bc765fbce3c10259f`
- Original integration base: `6533377c1a08539136a622a7d53eee20d0efd845`
- Current integration SHA: `4a8872f5069f43e478579d59ba0d0907af1016a8`
- Latest one-way integration merge SHA: `9d1433bc7b594709429df0cbfc57b559cb16835f`
- Date: 2026-08-03
- Persona: one disposable authenticated account, exercised in English and `es-419`
- Environment: local Next.js frontend and FastAPI backend with isolated disposable Supabase project `argus-qa-344-final`; real OpenRouter and Alpaca APIs
- Working search provider/model: `openrouter_web_search` with `x-ai/grok-4.3`
- Failure probes: an explicit invalid OpenRouter model for retryable provider failure and an explicit invalid Perplexity credential for non-retryable authorization failure
- No provider credential, bearer token, cookie, password, user id, conversation id, transcript export, or raw database row is preserved in this report.

## Why this supplement exists

Independent review correctly found that the `2b8ae484` report proved direct discovery and Spanish failure handling but did not preserve the locked general-knowledge-to-current escalation journey or the English failure ladder on the repaired lineage. This final-head browser run closes that acceptance gap. It changes no product code.

The 43/44 live scorecard in `../2b8ae484/live-eval-red.json` remains the live authority: all four issue #344 cases passed and the sole failure repeated unrelated issue #244 classification variance. Between `2b8ae484` and this browser candidate, merge `9d1433bc` changed only Guest-to-account Recents handoff plumbing and documentation; commit `97f3c2a4` added evidence only. Neither delta changes interpreter, discovery, search, citation, Retry, signed-in locale, API/data contract, migration, or environment semantics.

## Locked bilingual real-API browser matrix

| ID | Journey | Locale | Result | Evidence |
|---|---|---|---|---|
| EN-01 | General pharmaceutical discovery | English | Five resolver-backed general-knowledge candidates, explicit non-current marker, and generated current-search action | `english-general-pharma.png` |
| EN-02 | Generated current-search escalation | English | Action sent `Search for current stocks for this category: pharmaceutical stocks` through the ordinary composer; resolver-verified `MRK`, `PFE`, and `JNJ` returned with three sources | `english-escalation-grounded.png` |
| EN-03 | Unauthorized provider | English | Honest unavailable response with no Retry control | `english-authorization-no-retry.png` |
| EN-04 | Retryable provider failure | English | Exact trending-crypto request displayed Retry after an injected invalid search model | `english-transient-retry-visible.png` |
| EN-05 | Same-request recovery | English | The Retry control replayed the single original request after provider recovery and returned resolver-verified `BNB/USD` with three sources | `english-retry-grounded.png` |
| ES-01 | General pharmaceutical discovery | `es-419` | Five resolver-backed general-knowledge candidates, localized non-current marker, and localized current-search action | `spanish-general-pharma.png` |
| ES-02 | Generated current-search escalation | `es-419` | Action sent `Buscar acciones actuales para esta categoría: acciones farmacéuticas` through the ordinary composer; resolver-verified `VRTX`, `REGN`, and `PPH` returned with four sources | `spanish-escalation-grounded.png` |
| ES-03 | Retryable provider failure | `es-419` | Exact trending-crypto request displayed `Reintentar` after the injected invalid search model | `spanish-transient-retry-visible.png` |
| ES-04 | Same-request recovery | `es-419` | `Reintentar` replayed the single original request after provider recovery and completed with a truthful resolver-verified empty result | `spanish-retry-recovered-verified-empty.png` |
| ES-05 | Unauthorized provider | `es-419` | Localized unavailable response with no misleading `Reintentar` control | `spanish-authorization-no-retry.png` |

The escalation screenshots preserve both the original general-knowledge response and the generated localized user turn followed by its grounded result. The failure/recovery pairs preserve one original user request. Browser snapshots reported zero console errors; development-only warnings were present.

## Durable state observations

The isolated database contained only aggregate test evidence at audit end:

- 7 conversations
- 11 user messages and 11 assistant messages
- 9 completed and 2 `recoverable_failed` turn lifecycles

The two failed lifecycles are the injected English and Spanish transient-provider probes. Each Retry produced a completed response without duplicating its original user request.

## Artifact hashes

| Artifact | SHA-256 |
|---|---|
| `english-authorization-no-retry.png` | `8f779c42c5fe4d63d1b38d9ac662fc3b2d3092dc96d20f4a2b90e1563068d92c` |
| `english-escalation-grounded.png` | `f351a8f77de695249e3ddb6c0d37fb9ff84dfed5a8e3a8fb1dab682fe8a0ac6b` |
| `english-general-pharma.png` | `838cc7fbed40c865215cdbf2320c2eae035a95892f820fc9d6a5d0fab3a66afc` |
| `english-retry-grounded.png` | `b6abf4432c2c23114247429fe386e92eee60fb71fe6062cb2081be812f4117c4` |
| `english-transient-retry-visible.png` | `55400880881526631d0a86fc28fbe8f82444eb728d71e9c0ff853f7ef3cb72ff` |
| `spanish-authorization-no-retry.png` | `5e645b0520c1ccd61e01051ed622456e660e6cbaeb7c01f28d8aa63fe420e003` |
| `spanish-escalation-grounded.png` | `ca44c6f76298c11987e79115c17955dc4fb461d13f412db5feb2e5fae9bed971` |
| `spanish-general-pharma.png` | `e1b4156656536e902245b9e0a914d4bd3d84df1c09aa98bf89aa0eb0eb246493` |
| `spanish-retry-recovered-verified-empty.png` | `0084b86eea342e3974e094f69ea796373ec444d5ef838f901d11d2e48409d3d9` |
| `spanish-transient-retry-visible.png` | `d31d32fc21b5641ed52f5e06375e2c290b870c3a66ea69bc9be09a7cf8e38506` |

## Retention and authority

- The browser evidence in this directory is authoritative for the locked bilingual escalation and failure/recovery matrix at code head `97f3c2a4`.
- A later commit that adds only this supplement may retain this browser proof after an exact-final-head hermetic rerun and a diff confirming no executable change.
- The live-eval authority remains the disclosed 43/44 scorecard at `2b8ae484`; it is not represented as a fully green promotion gate.
- No merge, deploy, hosted configuration change, issue closure, migration, or tester exposure is authorized. Founder approval remains required.
