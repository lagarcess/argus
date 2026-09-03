# Issue #411 follow-up: discovery regression and browser evidence

Historical handoff at `83a38d15`. See the [reconciled branch report](2026-09-03-issue-411-reconciled.md)
for the actual integration merge and fresh research capture; its research
acceptance no longer depends on the temporary tree described below.

The discovery regression is fixed. The correct recovery remains
`discovery_unavailable`. Both META build requests reached runnable cards with
zero `knowledge_route` receipts. A genuine research answer reached the browser
when this lane was combined with current integration, which contains the
separate research-pricing fix. No branch was merged, pushed, or deployed.

The original [production impact assessment](2026-09-03-issue-411-live-impact.md)
still stands: a real explicit-build turn paid an unnecessary 1,250 ms /
$0.00156590 classifier hop. This follow-up is candidate acceptance, not a claim
that production has received #411.

## Why `discovery_unavailable` is correct

The reported test supplies a successful primary interpretation with
`semantic_turn_act="asset_discovery"`, a coherent NVDA peer request, a prior
result, and `result_followup_focus="general"`. My ownership guard let that
last hint veto discovery. The turn fell through to generic result composition,
whose unavailable model produced the misleading `interpreter_unavailable`.

An explicit discovery act owns this turn. The shared guard now gives it
precedence over the composition hint; artifact targets, result acts, factual
result keys, execution evidence, and other stronger owners remain protected.
The original recovery assertion is unchanged and now runs with the research
rail both off and on. This is typed precedence after interpretation, consistent
with AGENTS.md's LLM-first and single-chat-brain rules. It adds no classifier,
language rule, or intent taxonomy.

## Browser evidence

The app was driven through Playwright CLI against local mock auth and memory
persistence, with real OpenRouter, Alpaca, and Perplexity calls. Both research
rail flags were enabled. `ARGUS_GROUNDED_DISCOVERY_ENABLED=false` in the local
API deliberately exercised the real disabled-discovery recovery. No Turnstile
setting, sitekey, timeout, or production setting changed.

The run began headed, then switched to HeadlessChrome immediately when the
founder requested it. The Spanish card and discovery screenshots were captured
after headless reload; the successful research capture was entirely headless.

| Check | What appeared | Evidence |
| --- | --- | --- |
| English build | `test META buy and hold`, followed by dates/capital, reached META Buy and Hold, $10,000, Jan 3 2023–Dec 31 2024, with an enabled Run backtest button | [Card](evidence/411/browser/build-en.png), [transcript](evidence/411/browser/build-en.txt), [card SSE](evidence/411/browser/03-build-en-card.sse) |
| Spanish build | `Prueba META con una estrategia de comprar y mantener`, followed by dates/capital, reached Comprar y mantener, Listo para ejecutar, and Ejecutar backtest | [Card and prompt](evidence/411/browser/build-es.png), [persisted messages](evidence/411/browser/es-messages.json) |
| Discovery after a result | One real META simulation completed; `Find companies similar to Nvidia` then rendered discovery-unavailable guidance | [Recovery screen](evidence/411/browser/discovery-unavailable.png), [prior result](evidence/411/browser/backtest-result.png), [persisted recovery code](evidence/411/browser/en-discovery-messages.json) |
| Genuine research | The Microsoft business-model question returned a substantive answer, a balanced research sidecar, and a Microsoft investor-relations source on the combined tree | [Answer](evidence/411/browser/combined/research-answer-top.png), [sources drawer](evidence/411/browser/combined/research-sources.png), [SSE](evidence/411/browser/combined/research-answer.sse) |

[The evidence index](evidence/411/browser/browser-evidence.json) joins each of
nine API turns to its request/message IDs and route receipts. All **43**
captured OpenRouter receipt entries contain **zero `knowledge_route` calls**.
Build cards contain no research sidecar. Existing extraction, repair, and
composition calls remain; this does not claim that each turn uses only one
model call or that its total latency fell by exactly 1,250 ms.

The browser discovery turn proves recovery after a real result, including
hydration. The deterministic test pins the exact conflicting
`result_followup_focus="general"` combination; the browser capture does not
claim the real model emitted that same optional hint.

An observer copied the API's existing persistence-bound receipt objects before
calling the original persistor. It did not replace interpretation, research,
HTTP responses, or routing. The [observer](evidence/411/browser/observe_local_api.py)
and environment manifests are included. Memory mode cannot persist a hosted
cost ledger; background title naming is outside these turn receipts.

## Findings retained, not hidden

- The English flow asked for dates twice, even after the first answer included
  dates. An explicit ISO-date reply completed the card. All three turns and
  their receipts are retained; this was not a clean one-clarification path.
- Standalone `35e5cea8` routed the Microsoft question to research but discarded
  its answer for `usage.cost.output_cost is outside the served-model rate table`.
  [Failed screen](evidence/411/browser/research-pricing-failure.png) and
  [diagnostic](evidence/411/browser/research-pricing-diagnostic.txt) are retained.
- Integration `4e987de6` includes #538/#535's pricing repair. In the temporary
  combined tree, the same question produced an answer and source. Its research
  cost remained **null**, with the disputed invoice recorded as unpriced in
  [diagnostic evidence](evidence/411/browser/combined/research-pricing-evidence.txt).
  Memory persistence also reported that the ledger write was unavailable.
  This is answer-delivery proof, not hosted billing acceptance.
- After the local API restart the mock profile reverted to English. The
  successful research request used the same Spanish text with an English app
  preference, and its answer was English. It is not Spanish research-language
  acceptance. Research factual quality was not independently audited here.

## Verification and integration

Fix commits: `35e5cea8e6ca3186694fd02696535caa905b118f` (runtime precedence)
and `fe40da62c6462bc9c8176cc1000bc0f9cbcb971b` (test helper compatibility).

The combined-suite check found that #538 imports `_classify` from a shared
research test module. This lane had removed that helper. It now delegates to
the canonical primary-query fixture, preserving the shared test interface
without restoring the removed secondary classifier.

- Full `tests/agent_runtime/ tests/research/`, final standalone candidate:
  **2,176 passed, 2 failed**. [Output](evidence/411/browser/full-runtime-research.txt).
- Same complete suites on the prospective combined tree, using the same
  linked environment: **2,233 passed, 2 failed**.
  [Output](evidence/411/browser/combined/full-runtime-research.txt).
- In both runs the only failures are the two founder-identified integration
  failures: `test_detected_turn_language_reaches_discovery_composer` and
  `test_knowledge_turn_with_resolved_asset_is_not_interrogated`. Neither test
  was changed. A combined-tree run without the linked environment had passed
  all 2,235 cases; it is not used to claim parity with the flag-on lane run.
- Mocked measurement/session harness: **100 passed**. Ruff and whitespace
  checks passed. [Merged-tree modularity](evidence/411/browser/combined/modularity.txt)
  passed with every watched path present.

Original integration base: `c7802b37f39772a1216514e37fb6ff2b63142181`.
Current fetched integration: `4e987de6e74c3d94df8355ac092d4995f7525529`.
Reconciliation merge: none. The temporary tree was computed with
`git merge-tree`, without updating a branch.

Browser captures used standalone `35e5cea8` and prospective combined tree
`66073a69403084688a725dfae9006af6f90a6459`. After the test-helper adapter,
the prospective tree is `5fc943f88ea1144c419bcc1767a8a0d1c4784146`.
All 1,349 materialized source/test/frontend blobs were checked against that
tree. Only the test-helper adapter changed after browser capture; runtime
and frontend bytes are unchanged, so browser evidence is retained.

Incoming integration changes have semantic overlap at research delivery and
the shared research tests. That is why the research browser check and full
combined suites were run. There are no incoming differences under
`src/argus/agent_runtime/` or `web/`; the build/discovery evidence is retained.
The lane itself has no edits under `src/argus/domain/research/`, `src/argus/llm/`,
or `src/argus/observability/`.

The browser and both local servers were stopped; ports 3200 and 8200 are
closed. This is a local review handoff. Research-answer acceptance depends on
including the already-landed pricing repair. Hosted CI, branch reconciliation,
and promotion remain outstanding; this report does not declare the standalone
branch ready to deploy.
