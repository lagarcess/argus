# Clara local verification

Verified 2026-09-20 in the standalone app environment. Runtime source commit:
`cb7402bb79f5229e0948f651a160ebed4a5be990`. The following evidence commit adds
only this record and screenshots; it does not change the verified runtime.
GitHub CI and the requested Codex PR review are recorded separately after they
finish.

## What works

Spanish-first money home with English available, an embedded conversation,
editable confirmation, backend-owned Decimal comparisons, dated source and
calculation drawers, durable saving, source-load jobs, and notices that open
the corresponding before/after results. Failed loads and failed rechecks retain
the last good data. The original saved answer and user-input receipt dates
remain immutable. Country-neutral contracts are exercised with DO/DOP,
DO/USD and an independent synthetic NZ/NZD provider dataset.

## Executed verification

| Check | Result |
| --- | --- |
| Fresh app `.venv`, pinned requirements | Installed without parent Argus dependencies |
| `.venv/bin/python -m pytest -c pytest.ini tests -q` | 95 passed; one third-party Starlette deprecation warning |
| `.venv/bin/python -m ruff check server tests` | Passed |
| `bun run build` | TypeScript and Vite passed |
| `bun run test:e2e` | 5 passed, actual loopback API and temporary SQLite |
| CLI baseline load | Exit 0, attempt succeeded, source state ready |
| CLI failed load | Exit 1, failed attempt, same last-good dataset retained |
| Codex in-app browser | Confirmed, calculated, saved, changed data, opened both before/after tabs, inspected receipts, switched language |

Browser cases cover Spanish and English at 1440px and Spanish at 390px.
They verify no comparison before confirmation, source drawer keyboard closure,
save/reload, silent same-winner changes, changed-winner notice, before/after
navigation, failed-load retention, no horizontal overflow, and no JavaScript
page exceptions. The fourth case rejects an edited example instead of guessing,
then edits and saves an NZ/NZD comparison and verifies locale persistence.
It also verifies that the pending money summary shares the edited confirmation
inputs, the localized country label retains its synthetic qualifier, and the
browser makes no non-loopback requests. The fifth case confirms the maximum
supported amount fits the 390px mobile view without clipping or changing values.

Screenshots use completed animations. They were visually inspected against the
accepted design concept:

- [Spanish comparison](es-1440-comparison.png)
- [English comparison](en-1440-comparison.png)
- [Spanish saved answer](es-1440-before-after.png)
- [English saved answer](en-1440-before-after.png)
- [Mobile comparison](es-390-comparison.png)
- [Mobile saved answer](es-390-before-after.png)
- [Edited New Zealand confirmation](en-nz-confirmation.png)
- [Maximum amount on mobile](es-390-maximum-amount.png)

## Independent review

Three bounded reviewers examined math/provenance/providers, durable state/API/
interpretation, and UI/copy/accessibility. The captain integrated their findings
and each reviewer closed its scoped follow-up without remaining findings.

Corrections proved by regressions include numeric overflow limits, sourced zero
fees, strict documented SB wire types, interrupted-load recovery, CLI result
attribution, immutable input dates, dated notice evidence, exact inflation
references from the original saved answer, failure visibility, and accessible
amounts. The first GitHub Codex review found two UI ownership defects: the pending
money summary ignored edited confirmation inputs, and browser-generated country
labels discarded the supplied synthetic qualifier. Both are corrected and covered
by browser regressions. Country labels are now localized server catalog data;
the existing comparison/source origin still owns whether data is simulated.

The captain owned architecture, interfaces, source research synthesis, branch
isolation, verification and PR delivery. Bounded workers owned the domain,
persistence/API, semantic interpreter and web surface. Design and implementation
reviews were independent. All workers/reviewers returned their output and stopped.

## Faked and unverified

All institutions, deposit rates, fees, inflation, fixture publication dates and
change scenarios are synthetic. Prepared conversations replay explicit recorded
interpretations. Arbitrary text requires optional model configuration; no live
model was called or evaluated. The real SB boundary parses documented raw fields
but refuses calculation readiness without verified maturity, publication date
and rate semantics. BCRD's schema and both live services remain unverified
without access. Real-data reuse permission is also unresolved.

The loader command is ready for a local scheduled runner; no system cron was
installed. The SQLite-backed demo is single-user and loopback-only. Hosted
authentication, multi-user ownership and production operation are not claimed.
No deployment, production access, parent environment writes or Supabase migration
execution occurred. The private target was published with only its two pilot
branches excluded from parent CI, and no parent workflow ran for that push.

Original source base: `708864ef76961df2767d7e09c2fbf5f9812179c7`.
Private PR base: `codex/money-placement-pilot` at
`442958c5` (plan plus branch-local CI isolation).
Implementation: `codex/money-placement-pilot-impl`.
Neither `main` nor `codex/private-alpha-next` is a PR target.
