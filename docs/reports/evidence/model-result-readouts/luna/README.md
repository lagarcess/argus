# Luna readouts: implementation and pending paid proof

Status: implemented and verified without paid calls. This is not a readiness
or quality approval. The fingerprint is held, no merge has occurred, and the
new twelve-draft check still needs the founder's explicit approval.

The measured source candidate is `4dc1afeebd9b7a3dda7ef0a9bafbaafff64c4d1e`.
`preflight.json` records six saved-run/language pairs, twelve frames and zero
HTTP attempts. Later evidence-only commits can be checked against the source
hashes in `preapproval-audit.json`. The former structured-tier check and its
approval request are cancelled; the old evidence remains historical.

## Locked paths

- Quick take: Luna through OpenRouter's new `readout` tier, no search, identical
  primary/fallback keys and a single distinct model candidate.
- Breakdown: Luna through the existing Perplexity Agent client, with only
  `web_search` and `fetch_url`. The new public structured method and supporting
  types add 147 lines and delete zero existing client lines. Existing research
  methods and the request builder are unchanged in this lane.
- Both frames keep the labeled run fact sheet, figure references, written
  language check and complete template fallback. The card owns numerical
  reporting; the prose interprets the historical experience.
- Breakdown web figures use separate dated citations. They never become run
  facts. The public envelope remains closed; only complete accepted text and
  its attached dated links cross it.
- Received Breakdown invoices use the shared research ledger writer, including
  rejected drafts and work completed after a browser disconnect. Existing
  unpriced-spend recording remains active.

## Approval estimate

For DOCN buy-and-hold, DOCN DCA with costs and SPY RSI, in English and Spanish,
generate Quick take and Breakdown once each: **12 drafts, one attempt each,
no new backtests**. Then render every outcome using the offline browser harness,
with a screenshot beside the unchanged run's source numbers. Rejected drafts
remain visible only as evidence diagnostics beside the user-facing template.

The free preflight calculates a **$1.4202192 planning estimate** from actual
request sizes, the full allowed retrieved text and prior generated text at
each step, plus output and tool allowances. It uses request bytes as tokens
and conservative published rates. It is not an observed bill.

The separate **$10.46352 conservative reservation** covers a full 1,050,000-token
model context for each of three Agent steps plus a final generation, 2,200
output tokens each time and four tool calls at the higher enabled tool price.
It is conditional on the provider honoring its documented limits; it is not an
absolute invoice guarantee. A requested **$11 allowance** covers that reservation.
The runner stops subsequent work if a returned invoice exceeds its reservation,
and unknown spend is retained rather than treated as zero.

The largest request, including 8,192 bytes reserved for the prior Quick take,
is 90,288 bytes. The 91,000-byte dispatch ceiling leaves all twelve tasks
eligible. No prerequisites remain except paid approval.

`prices.json` cites the official OpenRouter provider rates and exact context
size, Perplexity model/tool prices, and documented tool-limit fields. These are
estimate inputs only. Luna's **billed** input/output rate is deliberately not
invented in `research/pricing.py`. After approval, retain the first Agent raw
response, derive its rates from actual token/cost components, then add the rate
row and reconcile the retained invoices offline. This requires no extra draft.

## Checks and limits

| Check | Disposition and reason |
| --- | --- |
| Run fact key, value, unit and rounded visible quote | Kept: prevents a quoted number from resolving to a missing or different run value. |
| Numeric occurrence coverage and duplicate ownership | Kept: rejects uncited figures and overlapping run/source references. |
| Returned web URL, citation date, claim span and source figure unit/value | Added for the new source channel: every external figure must have a dated citation attached to its visible occurrence. |
| Beat/lag contradiction | Kept: catches a claim that reverses the stored benchmark result. |
| Internal field/schema names | Kept: prevents machine contract details leaking into visible prose. |
| Model-reported written language | Kept: mismatch rejects the entire draft; existing saved-language display rules remain. |
| Required metric mentions and three-figure allowance | Remain removed: honest richer prose may choose which facts illuminate the run. |
| Model-written citation links | Rejected: only code attaches links to validated returned URLs after complete validation. |

Reference structure does not prove arbitrary prose entailment. In particular,
a model can misdescribe a correctly referenced peak as ending equity, or
misattribute a sourced number to the backtest. The live review must catch these
as factual failures; a URL alone is not quality approval. Review all twelve
outcomes for numeric meaning, run/source attribution, supported causes, dates,
language, complementarity, no advice/forecasts and no em dashes. Do not mark
the lane ready if accepted prose contains a factual error.

## Free verification and handoff

`preapproval-audit.json` records the focused checks and the old-wiring audit.
The main combined backend set passed 640 tests, the mocked eval harness 257,
and the frontend readout/privacy guard 76. The new measurement harness passed
43 tests. New additive-client behavior and existing client/retrieval/ledger
paths passed their focused tests. The final nested-schema guard delta passed 374 focused tests. Nine prompt-surface coverage tests pass; the
frozen fingerprint comparison intentionally remains failed and unchanged.

`merged-modularity.json` and `.txt` record a passing check across 1,430 source
files in a computed tree with current integration
`4482aaa68f9d7c7d3945324c32c2ee1cfcb384be`. No branch was merged. Shared API/docs
and request-builder ownership are recorded in the audit; final reconciliation,
exact-head CI and final GitHub Codex review are still delivery gates.

Founder environment additions, in the existing local backend environment:

```dotenv
ARGUS_READOUT_MODEL=openai/gpt-5.6-luna
ARGUS_READOUT_FALLBACK_MODEL=openai/gpt-5.6-luna
```

Neither `.env` nor `web/.env.local` was written. Local checks set these two keys
only in their process. Provider credentials were read without printing values.

The active browser replay instructions are in
`../final-writing/browser/README.md`. Actual Luna draft screenshots and billed
rate evidence do not exist yet and are not implied by the synthetic checks.
