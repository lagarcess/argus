# Issue #344 reconciled-head acceptance evidence

## Audit identity

- Branch: `codex/issue-344-grounded-discovery-retry`
- Exact executable and acceptance SHA: `b2d5b1a000f29ae051959b089e479a3064661b05`
- Original integration base: `6533377c1a08539136a622a7d53eee20d0efd845`
- Current integration SHA: `dc407d549b38de1c107f7556bfe9dc6d65a12ecb`
- One-way reconciliation merge SHA: `b2d5b1a000f29ae051959b089e479a3064661b05`
- Date: 2026-08-03
- Browser: Playwright Chromium with explicit `headless: true`, one worker, one context, one page, and retries disabled
- Runtime: local Next.js and FastAPI against disposable Supabase project `argus-qa-344-b2d5`; real OpenRouter and Alpaca APIs
- Search: `openrouter_web_search` with `x-ai/grok-4.3`
- Cleanup: disposable identities removed, frontend/backend stopped, isolated Supabase containers removed, temporary QA directory sent to Trash, and canonical `.env` links restored

No provider credential, password, bearer token, cookie, user id, conversation id, raw transcript export, or raw database row is preserved here.

## Integration overlap disposition

Integration advanced from `7568eff3` to `dc407d54` through PR #359. The incoming work changed the shared interpreter owner and added relationship-precedence guidance to `AssetDiscoveryRequest.relationship`. This lane changes `AssetDiscoveryRequest.needs_current_facts` guidance, so the overlap was treated as semantic even though Git merged it without a conflict.

The guidance is compatible: PR #359 tells the LLM how to choose category, peer, or comparison; issue #344 tells it when a discovery answer requires current facts. The composed-tree modularity check passed after the merge: `llm_interpreter.py` is 5,354/5,354 lines and `interpret.py` is 3,233/3,234 lines.

Because the shared schema changed, prior interpreter evidence was invalidated. The five issue #344 live cases and Spanish first-click browser surface were rerun at the merge SHA. Unchanged citation segmentation, provider failure classification, Retry mechanics, English browser journeys, and broad frontend presentation retain their prior accepted evidence.

## Affected exact-head live evaluation

The live harness loaded the ordinary measurement cases, selected the five ids containing `issue_344`, ran each complete turn through the real interpreter/composer path, and wrote `affected-live-scorecard.json`.

Result: 5 passed, 0 failed, 0 skipped, 0 expected failures, and 0 unexpected passes. Every case produced `intent=conversation_followup`, `semantic_turn_act=asset_discovery`, and `needs_current_facts=true`:

- `asset_discovery_recent_ipo_exact_issue_344`
- `asset_discovery_trending_crypto_exact_issue_344`
- `asset_discovery_old_pharma_escalation_exact_issue_344`
- `asset_discovery_semantic_pharma_escalation_issue_344`
- `asset_discovery_spanish_generated_pharma_escalation_issue_344`

This is live provider evidence, not a mocked substitute. The configured search adapter was unavailable inside this interpreter-focused run, so its user-visible output was the honest unavailable path. Grounded search is proven separately by the real-API browser journey below.

## Reconciled-head Spanish browser proof

The one-test run started from zero conversations. It used the disposable `es-419` account and performed exactly one generated-current click:

1. `busca acciones farmacéuticas` returned five resolver-backed general-knowledge candidates, the explicit non-current marker, and `Buscar resultados actuales`.
2. Clicking once sent `Buscar acciones actuales para esta categoría: acciones farmacéuticas` as an ordinary natural-language turn.
3. The first click returned five grounded candidates with current-source chips and a `3 fuentes` source control.

Result: `1 passed (1.5m)`. Both screenshots were visually inspected. No retry, repeated action, typed-action bypass, visible Chromium window, or phrase gate was used.

| Journey | Result | Evidence |
|---|---|---|
| Spanish general pharmaceutical discovery | Five general-knowledge candidates, explicit non-current marker, generated current-search action | `spanish-general-pharma.png` |
| Spanish generated-current escalation | First click sent the exact localized action and returned five grounded candidates with three sources | `spanish-first-click-grounded.png` |

## Retention disposition

- `528cce13` remains historical broad bilingual and failure-probe evidence, not current interpreter authority.
- `c9c71590` remains authority for the unchanged citation-boundary and broad browser matrix, but not for the Spanish first-click reliability claim.
- `f50a6ca0` records the pre-reconciliation prompt fix, 44/45 full live result, unrelated issue #336 variance, and first successful Spanish first-click proof. Its interpreter authority is superseded by this reconciled pack.
- `b2d5b1a0` is the current authority for the five affected live interpreter cases and reconciled Spanish first-click journey.
- The unrelated issue #336 full-suite failure remains transparently retained in `f50a6ca0`; independent review ruled it outside this bounded PR because it belongs to the separate Apple asset-mention path and the earlier exact-head full suite passed it. No claim says that `f50a6ca0` full suite was green.
- An evidence-only commit may retain this pack after exact-final-head deterministic verification confirms the executable diff is unchanged.
- No merge, deploy, hosted configuration change, migration, issue closure, or tester exposure is authorized. Founder approval remains required.

## Artifact hashes

| Artifact | SHA-256 |
|---|---|
| `affected-live-scorecard.json` | `21d33d3ebf49eb7215ea6783feed7c9b19e55f4f49a9f239a4ee9097e2977e26` |
| `spanish-general-pharma.png` | `7c35380deedf13b58e3fe284d07adcf2913330109c9b0c3cb1cc78f6c132d65e` |
| `spanish-first-click-grounded.png` | `2c309d21eceeb552989ee69d9d38413f567197ce24e03661d19baf6c9cbdacee` |
