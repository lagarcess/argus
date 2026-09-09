# Initial registry live gate

Candidate: `3c4f5aab93f1928d999a20fc34c4b0a6bcecf5a8`.
Integration base: `9e8b59b23f29d432ec7603c42f7362137b1ee21f`.
Reconciled integration: `743dfda3da9b467d32023ac32e900dad5a392500`.
The reconciliation commit is the candidate above. The intervening integration
change adds future conversation-sharing documentation; it changes no runtime,
API/card contract, UI state, migration, environment setting, or affected test.

The full live gate completed in 1,742.81 seconds: **43 passed, 25 failed**, no
infrastructure errors or skipped cases. All 68 original case IDs are retained.
This is a failed candidate, not accepted prompt evidence or a readiness claim.
The measured fingerprint deliberately still points at its previous scorecard.

- Raw result: `live-measurement-initial.json`.
- Comparison against both previous scorecards: `baseline-comparison-initial.json`.
- Current fresh-process probes: `verification/lane-c-3c4f5aab.json`.
- Schema/compatibility demonstration: `verification/intent-contract-3c4f5aab.json`.
- Bilingual fixture-browser evidence: `browser/3c4f5aab/README.md`.

## What the measurement demonstrated

The primary model used all four canonical intents: 46 calculate, 13 explain,
two follow_up, and seven cannot. It selected zero calls in 43 cases, one in 24,
and two in one. These are primary interpretation observations; the completed
runtime stage can update the effective task intent. The separate synthetic
declaration proof covers two distinct tools and one tool called twice.

The failed backtest cases exposed a structural input mismatch. A persisted
`StrategySummary` was used as the declared input, although interpretation owns
richer temporal, capital-role, cost, and rule facts. Those facts fell into
untyped extras, and the new call path bypassed existing preparation. Dates,
starting amounts, modeled costs, unsupported limits, and recovery were lost.
The correction must retain one typed backtest-input owner and the existing
preparation path, rather than adding field-by-field repairs.

The harness also changed its observation point: it inspected primary intent
before declared dispatch where the former harness observed the research stage's
completed decision. Six failures are intent-only; two more combine intent with
other failures. Original canonical expectations and actual stage precedence
must be restored. A Spanish DCA case also exposed an internal confirmation
handoff being counted as a new behavioral milestone. Raw execution traces and
all financial, clarification, approval, delivery, and prose checks are retained.

## Spend and limits

The announced estimate was $1.50–$3 for this complete pass, not a cap.
OpenRouter receipts report **$1.57375615144** across 280 priced receipts. Another
16 receipts have no cost or token data: 11 timeouts, three contract violations,
one result-followup timeout, and one validation failure. Their billing is
unknown, not assumed zero.

The research provider separately reported **$0.20487** for one response whose
components disagree with the repository's pinned price table. The existing
invoice observer recorded the anomaly without withholding its grounded answer;
these are provider-reported, independently unvalidated amounts. The sanitized
billing record is `verification/research-billing-initial.json`. Five fresh
discovery retrievals additionally have an estimated $0.025 search fee at the
repository's declared per-request rate. Thus about **$1.80 is accounted for or
estimated**, with the missing receipt costs still unknown. The scorecard's
OpenRouter sum is not presented as the complete bill.

No additional provider calls are part of the initial diagnosis. A corrected
clean candidate needs another announced full pass because its typed input schema
and strategy instructions change broadly. This document is diagnostic evidence;
the terminal CI/review audit remains pending.
