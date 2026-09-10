# Model result readouts: implementation checkpoint

Status: **not ready to merge**. Implementation and free verification are being
prepared for review. Founder-approved live measurement, fresh provider-backed
browser results, the measured fingerprint, exact-head CI, and terminal Codex
review are still required. This is a progress record, not the terminal audit.

## Behavior

Quick take and Breakdown keep their existing frames, labels, order and result
card. New complete model text crosses the private-prose boundary only through
the closed, versioned `result_readout_content` envelope. Its creation language
must match the reader's workspace language. Older results, language mismatch,
invalid envelopes and failed compositions use the current templates. Reads do
not call a model or rewrite saved history.

Both composers receive the complete stored metrics tree and canonical execution
configuration. Chart data remains optional. The shared checker rejects false
figures using compatible units and rounding tolerance, contradictory benchmark
claims, and internal field/schema names. Required mentions and content caps are
removed. Model tiers remain chat for Quick take and context for Breakdown.

- [Every validator disposition](validator-disposition.md)
- [Measurement scope, costs and execution prerequisites](measurement-plan.md)
- [Founder DOCN comparison steps in English and Spanish](founder-comparison.md)
- [Provider-free browser evidence](browser/)

## Evidence boundaries

The local browser replay uses a genuine pre-lane META result/card and authored
new readout envelopes. All replay Breakdown rows are synthetic. It proves
language matching, legacy fallbacks, unchanged frames, reload and clipboard
behavior; it does not prove model quality or a fresh real backtest. The browser
report names its captured code and any later revalidation.

A read-only inspection of the saved DOCN/SPY run confirmed that full metrics
and a chart are persisted. A sanitized temporary snapshot was used only for
free payload sizing. The candidate request reached 48,835 bytes, so the earlier
8,000-byte/$1 targeted estimate is superseded by the revised measurement plan.
No saved user identifiers or private prose are published with that snapshot.

No paid model requests or new market-data simulations have run in this lane.
The prompt fingerprint intentionally remains unchanged until approved measured
evidence exists. Its expected failure must not be waived or relabeled green.

## Deterministic verification

Python 3.10.20, provider keys blanked, no live calls:

- 558 affected backend tests passed across generation, transport, persistence,
  job completion, reload, private-prose boundaries and runtime workflows.
- 254 frontend tests passed across 12 files, including both language directions,
  old results, invalid envelopes, visible text/copy parity and AST bypass probes.
- 23 targeted measurement and prompt-extractor tests passed. The unchanged
  prompt-freeze suite had its expected one failure and two passes.
- The prescribed mocked evaluation harness passed 257 tests earlier in this
  lane; this is mocked harness evidence, not a live scorecard.
- Changed Python Ruff checks and changed TypeScript ESLint passed.
- Modularity budgets and `git diff --check` passed. `git merge-tree` calculated
  `42d16ecf927946722a83b49a4410a23d7f814a7c`, identical to the implementation
  tree at `55e63bf7647eb8a6f87e152a05db3fb871a76594`; that would-be merged tree
  passed the budget check. Recheck current integration before readiness.
- Independent code review reproduced and closed unit confusion, generic
  benchmark-subject inversion, and compact-number parsing defects. Its final
  review of the latest correction was clean. This does not replace the final
  GitHub Codex review.

## Integration and parallel scope

Original integration base and latest fetched integration:
`d0884c3de81f8c53d454ac4f68f461d3b5dd77e3`.
No reconciliation merge is currently needed. The initial and repeated open-PR
overlap checks found no open PRs. Repeat that check and fetch before readiness;
decision 10 can still advance its parallel branch.

No decision-10-owned files, locale catalogs, environment files, `render.yaml`,
release contracts or branch protection were changed. AGENTS.md already assigns
the intended short/deep surface ownership and remains unchanged. The founder
retains merge and deployment authority.
