# Issue #344 Spanish first-attempt acceptance evidence

## Audit identity

- Branch: `codex/issue-344-grounded-discovery-retry`
- Exact executable and acceptance SHA: `f50a6ca08827f38df46627a2ba337651befa8d3c`
- Original integration base: `6533377c1a08539136a622a7d53eee20d0efd845`
- Current integration SHA: `7568eff3c064de4df8837021dff02fe639b8d409`
- Latest one-way integration merge SHA: `77b3c70c49824662b48c5d782240e6d64717f839`
- Date: 2026-08-03
- Browser: Playwright Chromium with explicit `headless: true`, one worker, one context, one reused page, and retries disabled
- Runtime: local Next.js and FastAPI against disposable Supabase project `argus-qa-344-f50`; real OpenRouter and Alpaca APIs
- Search: `openrouter_web_search` with `x-ai/grok-4.3`
- Cleanup: disposable identities removed, frontend/backend stopped, isolated Supabase containers removed, temporary QA directory sent to Trash, and canonical `.env` links restored

No provider credential, password, bearer token, cookie, user id, conversation id, raw transcript export, or raw database row is preserved in this directory.

## Why this run exists

Independent review accepted the citation-boundary repair but rejected promotion because the prior Spanish browser journey grounded only after the same generated-current action was repeated. Commit `f50a6ca0` clarifies the LLM-owned contract, in language-neutral terms, that requests for current or up-to-date candidates require current facts. It also locks the exact generated Spanish action into the live eval case set. No regex, localized phrase gate, typed-action bypass, or second runtime owner was added.

## Exact-head live evaluation

Command:

```text
ARGUS_RUN_LIVE_EVALS=1 ARGUS_EVAL_ENV_FILE=.env ARGUS_MARKET_DATA_PROVIDER_MODE=live_provider poetry run pytest tests/evals/test_measurement_eval_live.py -q
```

Result: the command completed in 1897.29 seconds with 44 passed cases and one unrelated failed case. All five issue #344 cases passed, including `asset_discovery_spanish_generated_pharma_escalation_issue_344`. Its typed outcome was:

- `intent=conversation_followup`
- `semantic_turn_act=asset_discovery`
- `relationship=category`
- `asset_class_hint=equity`
- `category_description=acciones farmacéuticas`
- `needs_current_facts=true`
- `stage_outcomes=[ready_to_respond]`

The lone failure was `messy_english_opening_apple_capital_missing_period_issue_336`: the live asset-mention path preserved `APPLE` as an ambiguous provider candidate instead of resolving `AAPL`, so it requested `asset_universe` rather than `date_range`. A single-case exact-head rerun reproduced that unrelated failure. Both the full scorecard and targeted retest are retained; this report does not call the full live suite green.

The earlier `c9c71590` full scorecard passed that issue #336 case. The focused asset-mention extraction prompt had the same 782 prompt-token count in the earlier pass and current failure, while its live output differed. This supports an inference of model/provider variance, not proof of independence. Mandatory review must decide whether the unrelated red case blocks PR readiness; it is not waived here.

## Headless Spanish real-API browser proof

The one-test journey started from zero conversations and used the disposable `es-419` account:

1. `busca acciones farmacéuticas` produced five resolver-backed general-knowledge candidates, the explicit non-current marker, and `Buscar resultados actuales`.
2. The row sent the exact ordinary user turn `Buscar acciones actuales para esta categoría: acciones farmacéuticas`.
3. On that first click, without a retry or repeated action, Argus returned a resolver-verified pharmaceutical candidate with three current sources.

Result: `1 passed (1.1m)`. Both screenshots were visually inspected. The initial failed harness attempt used the generated sentence as the row's accessible name; the actual accessible name is the localized title `Buscar resultados actuales`. That locator-only failure occurred before any escalation click, was corrected, and the database was reset to zero conversations before the accepted run.

| Journey | Result | Evidence |
|---|---|---|
| Spanish general pharmaceutical discovery | Five general-knowledge candidates, explicit non-current marker, generated current-search action | `spanish-general-pharma.png` |
| Spanish generated-current escalation | First click sent the exact localized action and returned one verified candidate with three sources | `spanish-first-click-grounded.png` |

## Retention disposition

- The `528cce13` evidence remains historical proof of the broad bilingual journey and failure probes, but it no longer vouches for current interpreter semantics.
- The `c9c71590` evidence remains authoritative for the unchanged citation-boundary browser matrix and its exact 44/44 scorecard, but its disclosed Spanish repeat-click limitation is superseded by this first-click proof.
- This `f50a6ca0` pack is authoritative for the changed interpreter wording, the exact Spanish generated action, and the first-click Spanish browser journey.
- The exact-head full live command is transparently red only on the unrelated issue #336 case described above. No mocked pass is used to replace that fact.
- An evidence-only commit may retain this pack after deterministic exact-final-head verification confirms the executable diff is unchanged.
- No merge, deploy, hosted configuration change, migration, issue closure, or tester exposure is authorized. Founder approval remains required.

## Artifact hashes

| Artifact | SHA-256 |
|---|---|
| `live-eval-scorecard.json` | `2d24a3b3eb05ba1bc1ce61f6077ace8f74125a663555d1630c0ede65e5e52117` |
| `issue-336-targeted-retest.json` | `665812b9e79c96fe41ae8f88b08511713b8a766db2e105e28ca182584ceec160` |
| `spanish-general-pharma.png` | `493341da305e32461b0e0ef01008b8e90f877d66164e0b5affc01e9a040b6ba4` |
| `spanish-first-click-grounded.png` | `f848fc4f503cdf6f64b549dbcf1189659eae63bfdb4cc0970262042da303bb34` |
