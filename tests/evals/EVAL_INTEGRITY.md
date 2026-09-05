# Eval integrity: #365 and #520

Verification date: 2026-09-05 UTC. Test-only lane; all changes are under
`tests/evals/`. No product source, frontend, model prompt, provider setting,
merge, or deployment changes. #364 remains separate.

## Branch and evidence boundary

- Branch: `codex/eval-integrity-365-520`.
- Original integration base: `77be94d68ae2217f43148883fc8c56348c4a40dc`.
- Integration re-fetched before handoff: the same SHA. No reconciliation or
  intervening semantic overlap; the checked tree is also the would-be merged tree.
- #365 was implemented and committed first as `6b434ddf`.
- Cost: **$0**. All provider responses in regression tests are mocked transport
  fixtures. No live evaluation, browser turns, or real backtests were run.

## What changed

#365 reads the existing runtime composer receipts before asking the prose judge.
A timeout followed by an empty fallback yields an unavailable measurement with
the observed localized recovery and receipt/cost evidence. It does not yield an
honesty failure or a quality pass. Successful fallback prose remains judged.
Missing/failed judge responses are likewise unavailable. Typed failures remain
visible and cannot be masked by expected-fail tags.

Outage-only results block the gate as `infrastructure_error` and are excluded
from quality-rate denominators. A category with no quality measurements reports
`pass_rate: null`. The detailed gate policy is in `README.md`.

#520 adds delivered-outcome assertions to every remaining fixture. Launch facts
must reach the launch payload, clarification facts must reach the clarification
contract, and answer/next-experiment cases must deliver their respective surface.
Expected launch values derive from the existing fixture fields rather than a
second copy. Confirmation refusals now continue through the real clarify stage;
four DCA cases measure the terminal unsupported recovery and await-user-reply
state. Other routing expectations are unchanged.

| Category | Total cases | Newly strengthened |
| --- | ---: | ---: |
| Action chip semantics | 15 | 15 |
| Asset discovery routing | 12 | 3 |
| Backtest metric correctness | 1 | 1 |
| Capability honesty | 6 | 6 |
| DCA capital semantics | 16 | 16 |
| Graceful recovery | 3 | 3 |
| Messy English | 5 | 5 |
| Messy Spanish | 3 | 3 |
| UI/user language mismatch | 1 | 1 |
| **Total** | **62** | **53** |

The two newer DCA cases explain the increase from the issue's original 51.

## Deterministic red/green proof

- #365: seven initial regression checks failed before implementation, including
  real composer retry code over fake transport (`TimeoutError`, then
  `empty_response`) and the scorecard denominator. The final availability suite
  has ten passing checks, including EN/es-419 recovery, a successful fallback
  judged for honesty, typed-failure coexistence, missing judge output, a judge
  timeout, and expected-fail masking.
- #520: `test_each_case_rejects_a_turn_that_delivers_nothing` retains every
  existing routing/draft assertion while erasing delivery. The test was replayed
  against `git archive` of the exact integration base's eval modules and fixtures:
  **53 failed**, because the base accepted those empty turns. The strengthened
  versions all pass by rejecting the mutations. This is deterministic fault
  injection, not a live model draw or a claim to reproduce each product defect.
- Additional checks remove DCA launch facts individually, prevent resurrection
  of cleared proposals, and use real offline clarification for all four DCA
  refusals, both initially and after a follow-up. The follow-up variants first
  caught reversed stage ordering and passed after correction.
- Full documented mocked harness plus the new availability/delivery checks,
  outcome projection, prose evidence, and #498 regressions: **240 passed**.
- Ruff and modularity budget: passed. No product or no-touch path changed.
- Independent read-only Codex review returned **no unresolved findings** after
  the follow-up ordering correction; reviewer verified **122 passing checks**.

The runnable checks live beside this report and the free commands are in
`README.md`. This evidence establishes harness integrity. It does not certify
current provider availability, live prose quality, browser delivery, or #364.

## Rollback

Revert this PR's test-only commits. No schema migration, data repair, provider
rollback, or deployment action is required. Historical scorecards are unchanged;
new consumers must allow the infrastructure count and nullable quality rate.
