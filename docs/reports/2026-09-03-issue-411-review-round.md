# PR #539: canonical strategy ownership review round

The P1 was live and reproducible. The fix is commit
`c2cf0b0ca53093043a9afeca08bb1e5b61182a13`. Both thin META requests reached
runnable cards in one headless browser turn, and a dated comparison still
returned a research answer.

## Finding verification and decision

GitHub returned exactly one unresolved inline thread from
`chatgpt-codex-connector`: [comment 3921070867](https://github.com/lagarcess/argus/pull/539#discussion_r3921070867),
at `interpreter/research_routing.py:20`. It was not outdated. Its
`original_commit_id`, reviewed commit, local HEAD, and PR head all equaled
`f6862e8ff50111c3d8a655aa303da4a81c467a74` before work began.
[Captured comment](evidence/411/review-c2cf0b0c/review-comment.json).

I constructed valid `StructuredInterpretation` objects describing “Test META
from 2020 through 2024”: META and a date window, a buy-and-hold strategy type
marked `default`, no capital or other execution evidence, and a contradictory
`market_stats` research query. I separately supplied `backtest_execution`,
`strategy_drafting`, and `new_idea` ownership. In all three cases, the canonical
strategy predicate returned true while `primary_research_query()` accepted the
query. This is a direct reachability reproduction, not an estimate of how
often the model emits that contradiction in production.

- [Inputs and before results](evidence/411/review-c2cf0b0c/reproduction-before.json)
- [Same inputs after the fix](evidence/411/review-c2cf0b0c/reproduction-after.json)
- [Twelve failing regression cases before the fix](evidence/411/review-c2cf0b0c/regression-before.txt)

The finding is accepted. The strategy-route predicate and its existing act
set moved unchanged into `interpreter/strategy_routing.py`. Asset resolution
re-exports the same function under its former name, so the interpret stage
and both research entries consume one implementation. Research's duplicate
strategy-act list was removed. Defaults remain excluded from execution-field
evidence for genuine questions; explicit strategy intent or acts independently
retain strategy ownership.

## Tests and the old comparison fixtures

The new tests cover both `LLMInterpretationResponse` and
`StructuredInterpretation`, both research entry points, and a genuine question
carrying an incidental default strategy type.

The first full run also exposed two old question fixtures that explicitly
declared strategy ownership while expecting research to override it. That
expectation depended on the secondary-classifier design. Their question
fixtures now carry question intent/acts and retain default draft baggage; the
new contradiction regressions preserve the rejected strategy-owned cases.
The assertions that genuine questions receive research remain intact.

- Final full `tests/agent_runtime/` and `tests/research/`: **2,246 passed,
  exactly 2 failed**. Only `test_detected_turn_language_reaches_discovery_composer`
  and `test_knowledge_turn_with_resolved_asset_is_not_interrogated` fail;
  neither was changed. [Full output](evidence/411/review-c2cf0b0c/full-runtime-research.txt).
- Focused routing and prompt-freeze checks: **42 passed**.
  [Output](evidence/411/review-c2cf0b0c/regression-and-freeze-after.txt).
- Required mocked measurement/session harness: **100 passed**.
  [Output](evidence/411/review-c2cf0b0c/mocked-harness.txt).
- CI lint scope and merged-tree modularity pass.
  [Modularity output](evidence/411/review-c2cf0b0c/modularity.txt).
- The observed prompt surface has **zero changed, added, or removed entries**.
  The fingerprint is unchanged, so Never-Violate 12 does not require a new
  model-text scorecard. [Fingerprint comparison](evidence/411/review-c2cf0b0c/prompt-surface.json).

## Fresh headless browser evidence

All three turns ran on clean code commit `c2cf0b0c`, with the approved local
mock-auth/memory recipe and real OpenRouter, Alpaca, and Perplexity providers.
Both rail flags were enabled. No Turnstile, provider response, UI response,
or interpretation was replaced. The existing observational wrapper copied
the API's receipt objects and called the original persistor.

| Prompt | Visible outcome | Evidence |
| --- | --- | --- |
| Test META from 2020 through 2024 | One-turn Buy and Hold card, $1,000 default capital, enabled Run backtest | [Screenshot](evidence/411/review-c2cf0b0c/build-en-thin.png), [transcript](evidence/411/review-c2cf0b0c/build-en-thin.txt), [SSE](evidence/411/review-c2cf0b0c/build-en-thin.sse) |
| Prueba META desde 2020 hasta 2024 | One-turn Comprar y mantener card, Listo para ejecutar, enabled Ejecutar backtest | [Screenshot](evidence/411/review-c2cf0b0c/build-es-thin.png), [transcript](evidence/411/review-c2cf0b0c/build-es-thin.txt), [SSE](evidence/411/review-c2cf0b0c/build-es-thin.sse) |
| Compare PLTR to LMT over the last 3 years | Research answer with comparison tables and Try next, no build clarification | [Screenshot](evidence/411/review-c2cf0b0c/research-comparison-top.png), [transcript](evidence/411/review-c2cf0b0c/research-comparison.txt), [SSE](evidence/411/review-c2cf0b0c/research-comparison.sse) |

The two thin requests added no strategy wording or capital. Both returned
`await_approval` with confirmation payloads and no research sidecar. The cards
disclosed adjustment to the shared provider window, July 27, 2020 through
December 31, 2024. The browser did not launch either backtest.

The comparison returned `ready_to_respond` with `research.shape=thorough`,
no confirmation/strategy payload, and no degraded sidecar. It used three
finance-tool invocations; the sidecar reports 37,139 ms and $0.19487. It exposes
no publisher sources. This proves routing and answer delivery, not an
independent audit of its financial figures.

Each turn has two OpenRouter receipts: asset extraction and primary
interpretation. All **six receipts contain zero `knowledge_route` calls**.
The [verification record](evidence/411/review-c2cf0b0c/verification.json)
joins request/message IDs, route receipts, terminal payloads, and screenshots.

## Scope and evidence validity

Integration remains `4e987de6e74c3d94df8355ac092d4995f7525529`, already included
through merge `5b0d5d63`; the original lane base remains `c7802b37`. The review
fix changes no sibling-owned research-domain, LLM-provider, or observability
files. No frontend or model-facing text changed.

The earlier thick-request screenshots are historical evidence, not proof of
these thin requests. The fresh captures above cover the changed ownership
boundary. Existing discovery precedence tests still pass in the full run.
The evidence publication commit adds reports/artifacts only; its product-code
bytes are revalidated against the captured commit before pushing. The browser
and both local QA servers were stopped after capture.

Hosted CI and follow-up review outcomes belong to the current PR head and are
recorded on the PR after publication. This report does not authorize a merge,
deployment, or production flag change.
