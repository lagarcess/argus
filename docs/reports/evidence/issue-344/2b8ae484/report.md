# Argus issue #344 exact-code-head acceptance report

## Audit identity

- Branch: `codex/issue-344-grounded-discovery-retry`
- Exact code SHA: `2b8ae484d98fdc178bdce09bc765fbce3c10259f`
- Original integration base: `6533377c1a08539136a622a7d53eee20d0efd845`
- Current integration SHA: `4a8872f5069f43e478579d59ba0d0907af1016a8`
- Latest one-way integration merge SHA: `9d1433bc7b594709429df0cbfc57b559cb16835f`
- Date: 2026-08-03
- Persona: one disposable authenticated account, exercised in English and `es-419`
- Environment: local Next.js frontend and FastAPI backend with isolated disposable Supabase project `argus-qa-344-final`; real OpenRouter and Alpaca APIs
- Working search provider/model: `openrouter_web_search` with `x-ai/grok-4.3`
- Failure probes: an explicit invalid OpenRouter model for retryable provider failure and an explicit invalid Perplexity credential for non-retryable authorization failure
- No provider credential, bearer token, cookie, user id, conversation id, transcript body, or raw database row is preserved in this report.

## Acceptance boundary

Mocked and deterministic tests prove the code path only. The issue #344 claim below rests on real-interpreter live cases and bilingual real-API browser QA on the exact code SHA above.

The full live suite finished 43/44. All four issue #344 cases passed. The sole failure repeated the unrelated issue #244 comparison-classification variance seen on the prior head. This evidence supports the bounded issue #344 behavior; it does not claim a clean full-suite promotion gate.

## Live eval

Command:

```text
ARGUS_RUN_LIVE_EVALS=1 ARGUS_EVAL_ENV_FILE=.env ARGUS_MARKET_DATA_PROVIDER_MODE=live_provider poetry run pytest tests/evals/test_measurement_eval_live.py -q
```

| Result | Issue #344 cases | Other failure | Evidence |
|---:|---:|---|---|
| 43/44 in about 20m15s | 4/4 passed | Issue #244 comparison anchor returned `relationship=category` instead of `comparison` | `live-eval-red.json` |

The failing case is `asset_discovery_comparison_anchor_english_issue_244`. It is retained as a review risk, not converted into an expected failure and not hidden behind the mocked suite. A second paid rerun was not spent because the same unrelated case had already failed on the prior code head and the issue #344 cases were stable.

## Bilingual real-API browser matrix

| ID | Journey | Locale | Result | Evidence |
|---|---|---|---|---|
| EN-01 | Exact recent-IPO prompt | English | Honest verified-empty response; no invented ticker | `english-ipo-verified-empty.png` |
| EN-02 | Explicit 2025 IPO prompt | English | Honest verified-empty response after a named candidate could not be provider-verified | `english-ipo-2025-verified-empty.png` |
| EN-03 | Exact trending-crypto prompt | English | Resolver-verified `BNB/USD` with three current sources | `english-crypto-grounded.png` |
| ES-01 | Current pharmaceutical search | `es-419` | Localized verified-empty response; no invented ticker | `spanish-pharma-verified-empty.png` |
| ES-02 | Trending-crypto discovery | `es-419` | Resolver-verified `BNB/USD` and `AAVE/USD` with five current sources | `spanish-crypto-grounded.png` |
| ES-03 | Retryable provider failure | `es-419` | Localized unavailable response with visible `Reintentar` | `spanish-transient-retry-visible.png` |
| ES-04 | Same-request retry recovery | `es-419` | The Retry control replayed the single original request and completed with a truthful verified-empty result after the provider recovered | `spanish-retry-recovered-verified-empty.png` |
| ES-05 | Unauthorized provider | `es-419` | Localized unavailable response with no misleading `Reintentar` control | `spanish-authorization-no-retry.png` |

The browser snapshots reported zero console errors. Development-only warnings were present. Provider variance is visible rather than hidden: successful discovery can truthfully end with grounded candidates or a verified-empty result after resolver validation.

## Durable state observations

The isolated database contained only aggregate test evidence at audit end:

- 7 conversations
- 8 user messages and 8 assistant messages
- 7 completed and 1 `recoverable_failed` turn lifecycles

The failed lifecycle is the transient provider probe; its retry produced a completed response without duplicating the original user request.

## Deterministic exact-code-head evidence

- Hermetic runtime/spine sweep: 1,473 passed with provider keys blank and `synthetic_unit_fixture`
- Mocked eval harness: 70 passed
- Discovery adapter plus modularity tests: 24 passed
- Focused frontend discovery, Retry, locale, and shared-shortcut tests: 81 passed
- Ruff and `git diff --check`: passed
- Modularity: `llm_interpreter.py` is 5,354 lines, exactly at its 5,354-line limit
- Composed diff versus current integration for `llm_interpreter.py`: 8 additions, 8 deletions; net zero

These checks remain code-path proof and do not replace the live evidence above.

## Integration overlap disposition

Current integration was merged one-way into the worker branch. The first intervening changes touched the broad interpreter owner and locale catalogs, plus unrelated shortcut UI, starting-capital runtime, conversation activity, and run-dossier surfaces. They did not touch the issue #344 discovery route, search adapters, citation extraction, migrations, or environment variables.

Because the shared interpreter owner and locale catalogs overlap semantically with this lane, the interpreter-facing live eval, focused discovery tests, and bilingual browser matrix were rerun. No paid backtest or hosted validation was required.

Integration advanced once more after acceptance capture. That final delta only refreshed Guest-to-account Recents after handoff and updated its tests and roadmap records. Its single `ChatInterface.tsx` line passes a pre-existing activity-refresh callback into Guest conversion; it does not alter the signed-in discovery path, interpreter, search, citation, Retry, locale catalog, API/data contract, migration, or environment. The `2b8ae484` live/browser evidence is therefore retained across merge `9d1433bc`; exact-final-head hermetic, frontend, and CI gates remain required.

## Evidence retention disposition

- `528cce13` remains committed under `docs/reports/evidence/issue-344/528cce13/` as historical evidence. It is **not retained as current acceptance authority** because later citation and interpreter semantics changed.
- `2a758d2c` remains committed under `docs/reports/evidence/issue-344/2a758d2c/` as historical evidence. It is **not retained as current acceptance authority** because independent review found a same-line multi-claim citation-attribution defect, and integration advanced afterward.
- Exact code SHA `2b8ae484` isolates a URL marker to the immediately adjacent claim, includes the one-way integration merge, and owns the live and browser evidence in this directory.
- A later commit that adds only this evidence directory may retain the `2b8ae484` live/browser proof after an exact-final-head hermetic rerun and a diff confirming that the later commit is documentation-only.

## Ambiguity and exclusions

- The broad live suite is not fully green: it ended 43/44 on an unrelated issue #244 classification case. No merge, issue-close, or promotion claim should treat this as 44/44.
- The default local Perplexity credential was not treated as healthy. The audit proves non-retryable authorization classification with an explicit invalid credential and proves the configured OpenRouter path.
- No hosted deployment, tester exposure, provider fallback chain, real backtest, real-money action, shared environment mutation, or hosted data write occurred.

## Artifact hashes

| Artifact | SHA-256 |
|---|---|
| `english-crypto-grounded.png` | `2bbe22a3e5aa072f0d427e29886c60469174d58a5ddbd2a60cfaadeb2416d97b` |
| `english-ipo-2025-verified-empty.png` | `cd895166b6726515d077849a2bdb4cd77e0a1bee3af3da9c4f512e7e8d72a633` |
| `english-ipo-verified-empty.png` | `768ec8c44fd87e95697b2bc52e586d69e797966429ef82f98996f3f6419c9009` |
| `live-eval-red.json` | `e3315fdfb151ffc9868ec709ed546991f6134d36d88320b45da2d8dcbe87fd7e` |
| `spanish-authorization-no-retry.png` | `c9e51c20045560564c2d57afe10cbb807d744c72cfbaa5af8410e0ff3b2bbabd` |
| `spanish-crypto-grounded.png` | `6a343ecf01d5fcce08c66e3825aecf74fd5827258847161c8de10dba11ea7d8a` |
| `spanish-pharma-verified-empty.png` | `de01b88c1fd928ec2be0f514c1a58ab025b69f869586b4637c2452ffb2aac03e` |
| `spanish-retry-recovered-verified-empty.png` | `d04f2a9878bbd93652520d375f69b4a9afc6ca65d5a7bc58a5b5e49f2701e03e` |
| `spanish-transient-retry-visible.png` | `25dd44a345fd248f53ce8e83e5ca77434507d87f2eb209f686181d47af9dae8d` |

## Cleanup and authority

The isolated browser, frontend, backend, and Supabase processes are disposable and must be stopped after evidence capture. This report does not authorize merge, deploy, tester exposure, hosted configuration changes, or issue closure. Founder approval remains required.
