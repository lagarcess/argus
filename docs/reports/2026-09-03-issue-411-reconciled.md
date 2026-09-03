# Issue #411: reconciled branch and fresh research browser proof

The worker branch now includes integration `4e987de6` through merge commit
`5b0d5d6320fbd45bcb18dd36b1a65f3a028a4112`. A fresh headless browser turn on
that actual branch returned a sourced research answer. The temporary-tree
limitation in the earlier handoff no longer applies.

## Reconciliation

- Original integration base: `c7802b37f39772a1216514e37fb6ff2b63142181`.
- Current integration: `4e987de6e74c3d94df8355ac092d4995f7525529`.
- Incoming work: #536/#484 readable failure records, #537/#408 research
  analytics, and #538/#535 research pricing/delivery.
- Reconciliation was a normal one-way merge into the worker. No rebase or
  integration-branch update was performed.
- Both shared files merged automatically and were inspected semantically.
  `tests/research/conftest.py` retains `recorded_agent_response()` and the
  independent captured invoice. The removed `_agent_cost`, `_token_cost`, and
  production rate-table imports remain absent. #411's 13-line helper only
  injects a typed `research_query` into the test interpretation; it has no
  dependency on the removed fixture-pricing code.
- `docs/API_CONTRACT.md` retains primary-interpreter question ownership,
  provenance rules, pricing/answer independence, and the native analytics
  dimensions. None of the incoming contract additions was overwritten.
- Relative to current integration, the lane has no differences under
  `src/argus/domain/research/`, `src/argus/llm/`, or
  `src/argus/observability/`.

## Full requested suites

At clean reconciled commit `5b0d5d63`:

```text
poetry run pytest tests/agent_runtime/ tests/research/ -q --no-cov
2233 passed, 2 failed in 21.29s
```

The only failures are the two founder-identified integration failures:

- `test_detected_turn_language_reaches_discovery_composer`
- `test_knowledge_turn_with_resolved_asset_is_not_interrogated`

There is no third failure. The discovery precedence regression passes with
the research rail both off and on, preserving `discovery_unavailable`.
[Complete output](evidence/411/reconciled-5b0d5d63/runtime-research-full.txt).

## Research answer on the reconciled branch

Prompt: **How does Microsoft make money and what are its main businesses?**

The UI returned a substantive answer and a source drawer containing five
sources, including Microsoft's annual filing and investor-relations pages.
The final response is `ready_to_respond`, with `research.shape=balanced`,
`capability_class=balanced_lookup`, and no degraded sidecar.

- [Answer screenshot](evidence/411/reconciled-5b0d5d63/research-answer-top.png)
- [Sources screenshot](evidence/411/reconciled-5b0d5d63/research-sources.png)
- [Full visible transcript](evidence/411/reconciled-5b0d5d63/research-answer.txt)
- [Browser SSE](evidence/411/reconciled-5b0d5d63/research-answer.sse)
- [Route receipts and verification](evidence/411/reconciled-5b0d5d63/verification.json)

Request `fb3711de-f3f2-4ea6-a34c-495f8027ef8d` has two captured OpenRouter
receipts: asset extraction and the primary interpretation. There is **no
`knowledge_route` call**. The research provider sidecar reports two finance
tool invocations and 27,030 ms provider latency. Its cost is null because the
invoice is unreconciled; the already-landed #535 behavior preserves the answer
and emits pricing evidence rather than discarding it.

The browser was headless throughout this capture. Auth and persistence used
the approved local mock/memory recipe; interpretation, asset resolution, and
research used real providers. An observational wrapper copied the existing
API receipt objects and called the original persistor. No provider response,
routing result, or UI response was mocked. Turnstile and hosted settings were
unchanged. This is routing and answer-delivery evidence, not an independent
audit of every financial assertion or hosted ledger persistence.

## Retained evidence and remaining verification limits

The original [live impact assessment](2026-09-03-issue-411-live-impact.md),
[English card](evidence/411/browser/build-en.png),
[Spanish card](evidence/411/browser/build-es.png), and
[discovery recovery](evidence/411/browser/discovery-unavailable.png) remain
valid for their stated captures. The merge introduces no changes under
`src/argus/agent_runtime/` or `web/` relative to `35e5cea8`. Their screenshots
and receipts are retained; the new research capture replaces reliance on the
temporary combined-tree research capture.

The prior paid measurement scorecard remains 61 passed / 1 failed, with its
single documented retry passing. No model-facing text changed during this
reconciliation, and that scorecard is not rewritten as a clean full run.

The repository's broader `/verify` was also run:

- Full repository suite: **5,773 passed, 533 skipped, 20 failed; 87% coverage**.
  [Original terminal result](evidence/411/reconciled-5b0d5d63/full-verify-summary.txt).
- Fourteen failures were sandbox-denied local listener/sysctl operations.
  All fourteen passed on the permitted local retry.
  [Retry output](evidence/411/reconciled-5b0d5d63/sandbox-retest.txt).
- Apart from the two known routing-suite failures, the remaining four concern
  default-off saved memory, two stream timing/terminal assertions, and the
  OpenRouter raising-origin assertion. All four reproduce on a detached,
  untouched checkout of integration `4e987de6` with the same environment.
  [Baseline output](evidence/411/reconciled-5b0d5d63/integration-baseline.txt).
- CI's lint scope (`src tests workflows scripts`) and modularity pass.
  Broad `ruff check .` reports three existing import-style errors in
  `docs/reports/evidence/2026-08-24-main-promotion/judge-replay.py`, whose bytes
  match integration. They were not changed.
- The ownership command exits successfully with no matching branch policy;
  this is a skip, not an enforced ownership approval. Explicit scope and
  sibling-directory comparisons passed.

The original broad-suite failure output is retained; targeted retries are
not presented as a second clean full-suite run. Unrelated baseline tests and
lint findings were left unchanged. The headless browser and both QA servers
were stopped after capture.

The final handoff remains a PR for founder review. No PR merge, deployment,
flag activation, or production mutation is authorized by this evidence.
