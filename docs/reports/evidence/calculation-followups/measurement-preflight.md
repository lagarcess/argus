# Approved measurement preflight

The founder approved $15 total, including $8 Agent and at most 16 Agent sends,
then gave go with latest integration merged first. No paid measurement has run.

Integration `350e3dca8f573f5dfd61f1f753d8ed16a2724c9e` was merged one-way as
`1cf517194a69125c21aae6b5b40f3835826db9c0`. Its changes are promotion-checklist
and release-evidence validation, including rejection of unmeasured cases. It
changes no runtime model-facing text. The approved answer instructions, schema
field descriptions and A/B judge additions are activated exactly as captured in
[model-text-proposal.md](model-text-proposal.md). The judge version is now 4;
the interpreter fingerprint and retrieval recordings remain unrefreshed.

## Budget enforcement

The sanctioned runner accepts `ARGUS_EVAL_BUDGET_REPORT`, installs a measurement-
only HTTP transport guard, and executes cases serially. The guard reads the
approved case allowlists from the budget document. It enforces one Agent
application request and one HTTP send per eligible case, at most 16 sends,
with shared thread-safe accounting and the approved provider pools. Provider
errors, unpriced invoices, uncertain outstanding calls, forbidden research,
retry denial and exhausted admission budget stop the entire run.

Raw Agent invoices are accounted before answer parsing. OpenRouter synchronous,
asynchronous and streamed usage is counted, including judges and retries.
Search uses its separately recorded documented per-request fee. JSONL events
are flushed to disk for admissions, invoices and stops. The serial runner
retains provenance and completed-case results after every case; interruption
writes an explicitly incomplete report and cannot reach the scorecard writer.
Production transport and retry behavior are unchanged. This is an admission
budget, not a guaranteed provider invoice ceiling.

A preflight also found that the shared test fixture overwrote live context-
packet and memory-fallback flags. It now preserves live settings, as the
provider-credential fixture already did. A red/green regression covers that
behavior. The prepared ignored environment matches all 26 release-owned model
and flag values, with live market/asset providers and memory-only product
persistence. Credentials were checked for presence without printing them.

## Free verification

- 24 transport/ledger tests passed, including retries, concurrent requests,
  cancellation, malformed answers with real invoice fixtures and streamed body
  replay.
- Two serial-runner tests passed for complete and interrupted runs.
- The complete mocked harness plus guard/runner checks passed 371 tests; an
  additional sanctioned-runner test passed, proving forbidden research never
  reaches transport or writes a scorecard.
- Full backend: **8,820 passed, 605 skipped, seven failed**. The failures are
  the six retrieval-request recordings and interpreter fingerprint pending live
  measurement. No other failures occurred.
- Ruff, diff whitespace and merged-tree modularity passed.

## Launch dependency

Preflight found PR #626 still open, absent from the fetched integration head.
The founder's preceding instruction and active board say its recovery-text
change lands before this measurement. The captain requested clarification on
whether the new go overrides that dependency. Until the dependency lands or
the founder explicitly waives it, paid calls remain paused. The next launch
must merge and verify then-current integration again, preserve the approved
spending limits, and record its exact clean measured head. No git stash was used.
