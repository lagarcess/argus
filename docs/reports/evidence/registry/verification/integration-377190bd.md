# Registry reconciliation with research spend integration

The original integration base is
`9e8b59b23f29d432ec7603c42f7362137b1ee21f`. The first reconciliation merged
`743dfda3da9b467d32023ac32e900dad5a392500` as
`3c4f5aab93f1928d999a20fc34c4b0a6bcecf5a8`.

Integration then advanced through PR #571 to
`377190bd2911959e14ad9d92f2f4dba3edeb8453`. A normal, one-way merge brought it
into the worker as `6cfe4d58e78f7c59ab7cef0aa2fcd824a3c9aa5f`. No rebase,
integration push, hosted migration, or deployment was performed.

## Semantic overlap and resolution

The incoming work changes research parsing, discarded-response spend, cache-hit
billing, and background failure accounting. Shared owners are
`research_grounded.py`, `research_answer.py`, `research_evidence.py`,
`research_jobs.py`, and the API contract. Research contracts and the provider
parser also affect the registry adapter indirectly. There are no incoming
frontend, migration, environment-variable, or pinned-state-class changes.

The grounded-result merge keeps both owners' behavior: integration's turn-total
spend and withheld-result handling, plus the registry's declared-operation
query, explicit survey and typed-figure requirements, cache identity, and
data-class settings. A withheld result avoids unnecessary candidate resolution.

The new billed background failure path initially lost the registry's call
identity. A recorded-provider test executed two declared thorough calls under
one request, produced two billed parser failures, and observed both ledger call
IDs as null. The fix derives that identity from the existing `ToolJobBinding`.
The same test now retains distinct call correlations, both invoices, and two
matching unavailable cards with no answer.

## Verification and evidence disposition

Free checks on the combined working tree during reconciliation:

- 514 research tests passed, including the incoming discarded-spend suite.
- Four joint-path tests passed: billed parser failures, retry-total versus
  cached-packet usage, and repeated thorough failure correlations.
- Modularity budgets passed.
- An independent local review of the completed declaration, research-return,
  card-judge projection, and reconciliation deltas was clean; its focused
  command passed 204 tests. The still-active backtest preparation and receipt
  scope changes were excluded from that review.

These working-tree checks precede the final repair commit and do not claim an
exact-head terminal gate. Final deterministic checks, live comparison, CI, and
the GitHub Codex round remain required.

Both earlier live scorecards remain unchanged historical failed-gate evidence.
Their research billing and failure results do not establish the combined
behavior. Integration alone does not invalidate backtest, import, or fixture
browser evidence; the new interpreter repairs still owe their own measurement.
