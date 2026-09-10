# Third registry live measurement

**Not accepted: 49 passed, 19 failed, zero infrastructure errors, zero skipped.**
The complete 68-case run measured clean candidate
`72aa04a06d00a76421414e778d67fc2cf3ccd0f2`, after restoring private cost attribution
and moving backtest card facts out of public sharing. The fingerprint remains
unchanged. This failed measurement cannot establish behavioral parity or clear
the lane.

- [Unmodified scorecard](live-measurement-third.json).
- [Case, check, intent and cost comparison](verification/72aa04a0/measurement-analysis/README.md).
- [Input and output provenance](verification/72aa04a0/measurement-analysis/provenance.json).
- [Exact-head bilingual card evidence](browser/72aa04a0/README.md).
- [Public boundary](verification/72aa04a0/public-boundary.json) and
  [99 passing import/checkpoint checks](verification/72aa04a0/lane-c.log).

The scorecard was copied byte for byte, SHA-256
`f617272f3fe31aef21085a509339fbbdb010032396988b4806694f7750baded8`.
Earlier measurements and grades remain unchanged. The comparison records
18 pass-to-fail transitions against fingerprint 411 and 16 against 565.
Different source and observation contracts prevent treating every transition
as an isolated causal estimate; they do not justify erasing a failure.

The announced estimate was $3–$5. Accounted reported or estimated charges total
**$2.737909816178**: OpenRouter $2.068219816178, Search $0.015, and four distinct
Research Agent invoices totaling $0.65469. The Agent invoices have tariff
mismatches and remain unvalidated. Additional unreported charges are unknown.
The 24 unpriced OpenRouter records include 15 local zero-latency rejection
records; they are not 24 extra provider requests. Duplicate Agent invoice logs
were excluded.

All four canonical intents occur. The run has 34 zero-call cases and 34
single-call cases. It provides no live composition or repeated-call proof;
the seven historical labels were not all exercised by the old scorecards.
The deterministic catalog and compatibility tests provide separate structural
evidence, not a substitute for successful live behavior.

## Backend and scope at the measured head

GitHub backend run [34436516669](https://github.com/lagarcess/argus/actions/runs/34436516669)
reports **7,214 passed, 584 skipped, one failure**, the interpreter fingerprint.
Guest release gates, frontend checks and ownership passed.
The explicitly dispatched [agent runtime sweep](https://github.com/lagarcess/argus/actions/runs/34436830809)
and [local smoke](https://github.com/lagarcess/argus/actions/runs/34436836154)
also passed at this exact SHA. The public paths still match integration
`34866139861a5f06a3572edb2533bc42733371e8`; the dispatcher and editable-input
handler remain protected. PR #575 is non-draft and has an unresolved measured
fingerprint review thread.

Supabase Preview separately reports remote migration versions absent from the
local directory after the founder-directed removal of duplicate public
migrations. No removed migration was restored and no hosted preview was reset.

## Free diagnosis after measurement

The retained selected-call arguments have already passed schema validation;
they are not raw provider JSON. Unretained focused/audit replies must not be
invented when explaining a failure.

- A [controlled declared-call reproduction](verification/72aa04a0/capital-edit-controls/declared.json)
  preserves the recorded capital input of 2,000, but an existing date-only
  result patch offers 1,000. This happens with both a no-op audit and a correct
  typed capital edit. Inheriting the result window exposes the partial patch.
- [Baseline controls](verification/72aa04a0/baseline-controls/provenance.json)
  reproduce the next-experiment renderer defect on integration. The retained
  budget-ceiling state also behaves identically downstream; its original
  primary response is unavailable. These controls do not regrade either case.
- The selection observer omitted delivered uncited candidate reasons and the
  UI's general-knowledge marker. Correcting observation must preserve absent
  source evidence, currentness checks and the original judge criteria.
- Fresh pharma retrievals lack fact-period proof under the current survey
  selector. Crypto candidates failed identity/history eligibility. IPO
  retrieval returned unavailable. These failures remain failures; neither a
  tool-name requirement nor a freshness waiver follows from them.

Repairs and any later measurement must carry their own verification. This is
failed-gate evidence at the measured SHA, not a terminal audit.
