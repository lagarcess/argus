# Issue #408: native capability dimensions

## Decision

Rename the guest funnel's `capability_category` to `product_capability`.
Keep the research rail's `capability_class`, which already belongs to the
persisted research sidecar and cost-ledger contract. The full definitions and
historical-query migration are in [API_CONTRACT.md section 17.1](../../../API_CONTRACT.md#native-analytics-dimensions).

- **Product capability:** what product activity a guest event concerns
  (`chat`, `simulation`, `decision`, `history`, `account`, `feedback`).
- **Research capability class:** what research work happened (`fast_quote`,
  `balanced_lookup`, `thorough_research`, `screening`, `peer_expansion`). It is
  independent of execution `shape`: screening can run balanced or thorough.

Merging these dimensions would mix unrelated meanings. Renaming the product
dimension removes the category/class collision without migrating durable
research messages, cache keys, or ledger readers. New guest events emit only
`product_capability`; old events retain their original property. The six saved
PostHog insights in project 372988 were inspected on 2026-09-03: none references
either old capability name. There are no saved actions to migrate.

## Root cause and implementation

The research class was absent from the native-property allowlist. Tracing the
current code also found that research settlement wrote the cost ledger only:
there was no research PostHog emitter. A projection-only change would still
leave native filters empty.

All guest producers now use the renamed field. Research settlement emits one
bounded event from its existing sidecar, with a native `capability_class` and
`event_action`/`status` describing the outcome. A degraded sidecar emits
`failed`/`degraded`. The class is bounded by the existing research type, cache
status is bounded, and no sidecar content, cost, provider data, or raw identity
is copied. Capture works independently of ledger availability and schedules
network I/O off the streaming event loop.

## Live native-filter evidence

This is a **synthetic ingestion/filter proof**, not production traffic, a
deployment, or proof that outage #535 is repaired. No LLM, market-data provider,
or Supabase write was used.

- Source commit: `d9eccbd7f7eab7c165b0f904b1ef4e8395da0560`, clean at capture.
- Project: 372988, US Cloud.
- Capture environment: `validation_issue_408_d9eccbd7f7ea_20260903T001225Z`.
- [Probe](probe-native-filters.py) sent four events through the real settlement
  and capture path: a balanced research failure and completion for one
  synthetic actor, a screening completion control, and a guest chat limit.
- [Capture receipts](native-capture.json) contain the emitted properties and
  source digests, without the ingestion credential.
- [Native funnel query and result](native-funnel.json): `capability_class =
  balanced_lookup`, then `event_action = failed` / `completed`, matched **1 → 1**.
- [Native event-property filters](native-filters.json): failed balanced lookup
  **1**, screening **1**, thorough research **0**, `product_capability = chat`
  **1**. The negative control demonstrates selectivity. These are ordinary
  event-property filters, not SQL or nested-JSON expressions.

An initial relative-window query returned no result. Subsequent queries with
the explicit capture-day window returned the counts above; no sample was
resent. The query artifacts include links to reopen them in PostHog.

## Verification and limits

[Verification record](verification.json): baseline focused tests 60 passed;
the initial regressions failed 31 cases for absent research capture and the
missing renamed property. Final focused verification passed 124 tests, including
all five research classes, hit/miss/bypass, degraded outcomes, exact outgoing
payload keys, private-data exclusion, and nonblocking capture. The independent
Codex reviewer found no actionable issues and ran 109 focused checks.

The full local suite passed 5,692 tests with 29 failures and 532 skips (87%
coverage). Every failed test was rerun on original integration commit
`c7802b37f39772a1216514e37fb6ff2b63142181` using the same interpreter and
environment; all 29 failed there as well. This is not a fully green local suite.
Runtime/test/script lint and modularity budgets pass. Repository-wide lint
also sees three errors in an unrelated archived `judge-replay.py`; the same
errors were reproduced from the base file. No unrelated files were changed.

Original and refreshed integration SHAs match at `c7802b37f39772a1216514e37fb6ff2b63142181`.
No reconciliation merge or semantic overlap is present. Source evidence is
retained across the documentation-only evidence commit; final PR verification
checks its recorded source digests again.

Background failures that never create a research sidecar retain their job
lifecycle failure records and are outside this settlement event's coverage.
Billing reconciliation and provider failure classification remain owned by
#535. `src/argus/llm/openrouter.py` and its receipt vocabulary are untouched;
the naming decision requires no #484 producer changes. No #484 PR was open at
the coordination check. No merge or deployment was performed.
