# Category discovery payload routing (#344), live eval at 9586a78d

Measured 2026-08-15, twice on the exact fix commit, per the lane's
measurement contract. Compare against the merged promotion candidate
scorecard (46 passed / 14 failed at `c2dbddd7`), not the fingerprint's
`last_measured`.

| run | result | cost |
|---|---|---|
| baseline `c2dbddd7` (merged candidate) | 46 passed / 14 failed | $1.31 |
| **run 1, `9586a78d`** | **49 passed / 11 failed** | $1.26 |
| **run 2, `9586a78d`** | **49 passed / 11 failed** | $0.98 |

## The five target cases

| case | baseline | run 1 | run 2 |
|---|---|---|---|
| asset_discovery_trending_crypto_exact_issue_344 | FAIL | PASS | PASS |
| asset_discovery_recent_ipo_exact_issue_344 | FAIL | FAIL* | PASS |
| asset_discovery_old_pharma_escalation_exact_issue_344 | FAIL | PASS | PASS |
| asset_discovery_semantic_pharma_escalation_issue_344 | FAIL | PASS | PASS |
| asset_discovery_spanish_generated_pharma_escalation_issue_344 | FAIL | PASS | PASS |

*Run 1's recent-IPO failure is prose-judge honesty only: every typed check
(act, payload, needs_current_facts, stage outcome) passed in BOTH runs, so
the routing target held 10/10 across the two runs. The judge saw the one
voiced framing sentence ("stocks that have completed their initial public
offerings in early August 2026") without the sidecar rows and sources the
interface renders, and called the dated claim unsupported. At baseline this
case never reached discovery voicing at all: it was diverted to grounded
research, whose full ticker-table answer the judge passed while every typed
check failed. The judge's blindness to the discovery sidecar on
single-sentence voiced framings is a pre-existing gap this fix makes
reachable, not a regression of working behavior.

## What was actually broken

The scorecard's `educational_question` outcomes were not (only) the
interpreter's answer. A stage-level instrumented probe showed the
interpreter emitting a perfect typed discovery response and the case still
failing: the rail classifier typed "recently IPO'ed" as `screening`,
`_dispatch` diverted the turn into grounded research, and
`research_grounded.research_decision()` rebuilt the decision with a
hardcoded `semantic_turn_act="educational_question"` and no payload. Two
failure modes alternate by serving day: (A) the model omits the payload;
(B) the model is perfect and the diversion erases the identity. Wording
the model out of (A) cannot fix (B), which is why #514's prompt-guidance
wins flipped after merge.

The fix routes on the typed payload, not the act label, at every layer:
the schema describes the payload as an act-independent read; a coherent
payload deterministically promotes the act (`discovery_payload_act_promoted`);
a refused payload is cleared (`discovery_payload_dropped_unroutable`);
survey classifier kinds no longer divert a typed discovery turn; remaining
diversions carry the typed decision instead of relabeling it; and a focused
second read recovers an omitted payload on payloadless knowledge-shaped
turns (`discovery_payload_recovered_by_focused_read`).

## Cases that moved against the baseline

Zero shared failures: every case that failed in both runs also failed at
the baseline. Three cases flipped in exactly one of the two runs, all with
same-SHA re-probe evidence recorded below:

- `action_chip_change_asset_remove_aapl_issue_188` (baseline PASS, runs
  FAIL/FAIL): a 3x same-SHA re-probe scored PASS/FAIL/FAIL, and its five
  action-chip siblings fail identically at baseline and in both runs while
  a sixth (`no_active_ref_remove_aapl`) flipped the other way, failing at
  baseline and run 1 and passing run 2. The whole family sits on a
  serving-day decision boundary; no changed surface is mechanically
  reachable from an action-chip turn (chip edits carry draft evidence,
  which vetoes payload promotion and the focused read, and they never
  enter the research rail).
- `compound_benchmark_start_date_preserves_confirmation_issue_339`
  (baseline PASS, run 1 PASS, run 2 FAIL): start-month extraction misread
  (2026-03-02 for 2026-04-01). A 3x same-SHA re-probe scored
  PASS/PASS/PASS, so the same commit's record is 4 pass / 1 fail.
- `dca_capital_semantics_spanish_seed_and_contribution_issue_455`
  (baseline PASS, run 1 PASS, run 2 FAIL): Spanish DCA money-role misread,
  the tail the DCA lane documented as flakiest. A 3x same-SHA re-probe
  scored FAIL/PASS/PASS: the case flips in both directions at one commit
  (same-SHA record 3 pass / 2 fail).

None of the three flips reproduces deterministically at this commit, and
each also passed at least one full run here, so all three read as
serving-day boundary variance, not effects of this change.

## Baseline-vs-head distribution for the action-chip flip

Because `action_chip_change_asset_remove_aapl_issue_188` failed both full
runs here while passing at the baseline scorecard, it was settled by
comparison rather than head-only re-probes: 20 interleaved attempts in one
session (2026-08-15, same live provider modes, alternating one baseline
attempt and one head attempt per round), each in a frozen worktree of its
commit.

| side | pass rate | rounds 1-10 |
|---|---|---|
| baseline `c2dbddd7` | 2/10 | F P F F F F F F F P |
| head `9586a78d` | 5/10 | P F P P F F F P F P |

Every failure on both sides carries the identical signature
(`intent: conversation_followup` instead of `backtest_execution`, AAPL
retained). The baseline is not materially better; in this session it is
worse, and its full-run PASS reads as a favorable draw from an unstable
case. The case sits on a serving boundary at both commits, so this change
neither caused the instability nor resolves it, and PR #510's fix for
this specific case is itself boundary-dependent at the merged tree.

## Provenance

- Fix commit and both runs: `9586a78d` (`fix(discovery): route discovery
  from the typed payload, not the act label`), branch
  `claude/category-discovery-semantic-act-282414`, base `f2036eee`.
- Both scorecards carry full schema-2 provenance (live provider modes,
  clean worktree, calendar probe, fixture hash) and sit beside this file.
- Pre-run targeted probes at the same commit: the five target cases 5/5
  and the three discovery negatives 3/3 (direct backtest, post-result
  what-next, capability question), so promotion does not overreach.
