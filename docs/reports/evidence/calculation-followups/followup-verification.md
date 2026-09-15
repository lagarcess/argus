# Catalogue and general currency-risk follow-up

The founder resumed the stopped lane with two changes: derive advertised result
names from presentation, and generalize the proposed currency-risk judge rule.
The 93-case measurement remains paused.

## Shared ownership

`ToolCardBinding.result_projection` owns each result fact's name, factory,
placement and presence condition. The card renderer and model catalogue use
those same definitions. Factories receive the owned name, and projection enforces
it on the emitted fact. Metadata such as the requested historical date window
is no longer advertised as a renderable result. Conditional names are marked
`when present` in the generated catalogue.

All 13 calculations use this contract. Solver names derive from existing
unknown-field rules; scenario names derive from shared scenario labels; ranked
positions derive from the same maximum used by the items schema. The catalogue
never executes a calculation, sample, or provider to discover its fields.
Existing tools without a result projection retain their original presenter path.
The shared `presentation_reference_facts` helper preserves input/row/answer
precedence for answer substitution.

## Deterministic evidence

Before the fix, the new all-kind tests failed for time value, effective rate,
ranked comparison, valuation scenarios, and historical drawdown, plus the
specific requested-date regression. The shared projection closes these without
a second list of names maintained alongside the presenter.

The 14 new checks cover every kind, every solved field, both time-value
directions, optional loan/scenario inputs, ranked collections of 2 and 12,
scaled-amount variants, and historical decline/no-decline observations. Every
advertised result name must have an actual rendered witness; every unconditional
name must appear on every tested variant. Each available name is passed through
the real answer-template renderer. Historical cases use typed offline outcomes,
not a market provider.

Focused catalogue and API-startup checks: **24 passed**. Existing calculation and
legacy declaration checks: **232 passed**, including the frozen card fixtures.
The full backend suite: **8,790 passed, 605 skipped, seven failed**, with **89%
coverage**. The seven failures are the interpreter prompt fingerprint and six
frozen retrieval-request recordings; none has been refreshed without live
measurement. The complete frontend suite: **1,987 passed**. Ruff and merged-tree
modularity checks passed.

The full backend run excluded only the worktree's real dotenv file and blocked
external DNS, while permitting the local stub servers and process-inspection
tests. No provider keys, model calls or live backtests were used.

## Reconciliation

Original lane base: `0893c27e878f8b55c39afb467cba15ed0ed3cfee`.
The preceding reconciliation used `6ec3679750fb6fb4cded21443c1ab4635a4687b5`.
This follow-up first merged integration
`edeaffa9f6565e4750fa0685a050f10aefd6d718` in one direction, as merge
`d0eecbf417cff6e51d37b889f6581d437295adcb`.

There is semantic overlap with #633 in knowledge-answer admission, research
execution/recovery timing, and interpreter failure state. It does not add a new
API/data schema, migration, or deployment variable. The full merged-tree suite
reran the affected recovery, no-new-facts routing, calculation publication and
observer paths. Prior standalone runtime evidence is superseded by this merged
verification. There was no live measurement evidence to retain or invalidate.

Integration then advanced with #632. A second one-way merge,
`bebdf2c0a74f992750b7c868a5d4871617944931`, incorporates
`a4a183138aadf1cff8268d0ce169e444732116fe`. Its overlap is the public receipt
projection of calculation answers and user-written inputs, the shared card
fixture, and answer-sharing tests. The new result projections, catalogue,
reference helper, all-kind tests and judge proposal are unchanged by that merge.
Integration supplies its own public-receipt API/data contract and migration;
this lane adds no further schema or deployment variable. The full offline
backend and frontend suites above were rerun after this merge, as were Ruff and
merged-tree modularity. No paid acceptance evidence was repeated.

The limited Codex review of `0812951e8bbf8299ec39a468fe1211312b826757`
returned clean; all threads were resolved. The final integration-overlap review
and exact-head CI remain to be recorded in the terminal PR comment.

## Model text and remaining gate

The proposed judge now describes savings in A funding an expense in B, matching
the answer instruction. The rest of the approved-shape answer, field and judge
text remains unchanged and inactive until measurement go. The complete generated
catalogue is captured in [the exact-text proposal](model-text-proposal.md).
[The spending proposal](measurement-budget-proposal.md) bounds Agent eligibility
and sends, and states the remaining admission-guard work and billing limitation.

This document records deterministic verification, not the terminal review or a
readiness claim. Exact pushed head, CI, and limited Codex review disposition will
be recorded in the PR after that review completes. No merge or deployment is
part of this lane.
