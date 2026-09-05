# Spanish discovery hint: consumer trace

- Candidate: `e3b98690b238bb292e161a9a25554cd9cfdbc19d`
- Inspected checkout: `236e78b0b28268825878ee28e96708f8abf4d0d4`; `git diff e3b98690 -- src web tests` is empty.
- Case: `asset_discovery_spanish_generated_pharma_escalation_issue_344`
- Method: source trace and existing deterministic unit checks. No new live eval, provider measurement, production mutation, or browser session.
- Verdict: accept the case-specific interpretation-hint difference. The null does not become the asset class used by the named calendar or research-row consumers.

## What the retained measurement says

The failing check reads `interpret_patch.asset_discovery.asset_class_hint`, via `measurement_eval_harness.py` lines 1008 and 1110. Baseline is `equity`; candidate is null. `AssetDiscoveryRequest` explicitly permits null at `stages/interpret_types.py:93`. Both observations are `answer_only`, with only `ready_to_respond`, and deliver LLY, JNJ, ABBV, MRK, and PFE. Neither turn enters confirmation or launches a test. The empty strategy draft's separate null `asset_class` is not the class on those discovery rows.

The retained rendered-context excerpt records row names and symbols but omits row asset classes. It is not an empirical capture of that field. The provenance of row class is established by the code below. The native candidate score remains failed and is not rewritten.

## Source to consumer

All source locations below refer to the candidate SHA.

| Boundary | Owning code | Effect of the null request hint |
| --- | --- | --- |
| Discovery routing | `src/argus/agent_runtime/research_answer.py:85`, `research_find.py:98`, `discovery/composer.py:40` | The typed request reaches the discovery operation. Both research-rail modes use the same discovery validator. |
| Search request | `src/argus/agent_runtime/discovery/composer.py:518` | Null and `equity` both select `publicly traded companies`. The category text remains the same. |
| Resolve each candidate | `src/argus/agent_runtime/discovery/validation.py:99` and `:179` | Both the history-prefetch pass and acceptance pass call `resolve(symbol_guess)`. The production caller supplies `market_data.resolve_asset`, not the interpreter hint. |
| Tradability | `src/argus/agent_runtime/discovery/validation.py:110`, `:187`, `:227`; `discovery/composer.py:485` | History probes receive `resolved.asset_class`. Empty resolver classes are excluded from prefetch; acceptance rejects classes outside equity, crypto, and currency pair. The hint is never passed as the history class. |
| Row construction | `src/argus/agent_runtime/discovery/validation.py:260`; `discovery/contracts.py:37`; `discovery/composer.py:885` | `ValidatedCandidate.asset_class` is a required non-null Literal. The sidecar copies `item.asset_class`, not `request.asset_class_hint`. |
| Research peers from discovery | `src/argus/agent_runtime/research_find.py:118` | Peers copy the already validated candidate class. The legacy `or "equity"` at line 139 is not exercised by these rows. This case has no anchors, so the anchor-subject branch is empty. |
| Other research subjects and peers | `src/argus/agent_runtime/research_answer.py:228`; `research_rows.py:64`, `:93`, `:102`, `:111` | Subjects and peer candidates resolve independently. Class filtering and tradability use resolver results. `row_window` at line 171 receives typed asset dictionaries; it has no request-hint argument. |
| Browser selection | `web/lib/chat-discovery-sidecar.ts:20`, `:96`; `web/components/chat/ChatMessage.tsx:527` | The parser rejects rows without a recognized class. A tap copies `candidate.asset_class` into the action and mention, then follows ordinary interpretation and confirmation. |
| Strategy grounding | `src/argus/agent_runtime/llm_interpreter.py:5157` | `_validate_capability_boundaries` resolves strategy symbols or uses their provider-verified context. Lines 5211 through 5226 derive the strategy class from those assets. It does not read the discovery request hint. |
| Confirmation calendar | `src/argus/agent_runtime/stages/confirm.py:441`, `:649`; `src/argus/domain/market_data/capabilities.py:185` | `_strategy_asset_class` accepts only the three supported classes. If absent, lines 445 through 447 return before `latest_complete_data_adjustment`. A verified equity strategy supplies `equity` at line 467 and takes the equity calendar branch. |
| Retest calendar | `src/argus/domain/retest_setup.py:220`, `:239`, `:154` | The other calendar caller derives class from the stored run/resolved strategy. Its constructor rejects missing or unsupported classes before returning a setup. Discovery request hints do not enter this path. |

## The hint has a narrower real role

`discovery/validation.py::_resolution_matches_request` uses the hint to corroborate ambiguous identities. Named companies must corroborate the resolver's company name. Pair-named assets require an explicit matching hint; a missing hint rejects those rows. For bare symbols, a missing hint allows the independently resolved identity to stand. This is a real validation input, so this finding does not establish that the hint is universally cosmetic or that every missing hint is safe.

For this pharmaceutical-company request, null and equity produce the same search universe, both measured turns deliver the same five company symbols, and every accepted row obtains its own resolver class before the named consumers. There is no dataflow from this null to the `today` or `today minus one` fallback in `capabilities.py`.

## Verification and limits

Existing checks cover provider-owned discovery class and corroboration, selection identity, research filtering and coverage, strategy-class grounding, and the equity daily endpoint. All 35 passed in 1.70 seconds with synthetic providers. Results and the exact command are recorded in `spanish-equity-hint-unit-tests.log` and the release manifest.

An initial unit-check invocation used invalid asset provider mode `static_fixture`; it returned 33 passed and two failures at resolver-dependent checks. `assets.py::_asset_provider_mode` rejects that value. The corrected invocation uses the repository's `synthetic_unit_fixture` mode for both providers. This was an operator setup error, not a measured product regression; both logs are retained. No code or fixture was changed between invocations.

This closes the requested code-path question. It does not replace the founder-required production browser checks after an authorized deployment.
