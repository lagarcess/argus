# Readout fact attribution and tier comparison

This round follows the failed [first comparison](../targeted/README.md).
The founder authorized the implementation and requested a priced comparison
before further paid work. No paid task in this round has run yet. The prompt
fingerprint remains held; no merge, deployment, full live suite or fresh
backtest is part of this round.

## Changed contract

Both composers receive the same labeled fact sheet. Stored values carry their
meaning, unit, scope, basis and provenance; compact chart and marker groups
share those definitions without dropping individual figures or dates. Executed
fills, closed trades, nominal equity extrema, ending equity, annualized risk,
seed capital and contributions have separate meanings. Derived drawdown dates
require supported complete fixed-capital chart evidence and agreement with the
stored drawdown. A DCA nominal chart alone cannot establish those dates.

Each draft reports its written language and a reference for each quoted figure:
the fact key, canonical value, exact visible quote and its occurrence. The
validator resolves the specific fact, checks its value and unit/rounding, and
requires complete quote coverage. Language mismatch, invalid references or
other retained truth checks cause complete fallback through the existing
source/fallback/failure fields. The public readout envelope is unchanged.

These references do not prove arbitrary natural-language relationships. The
comparison must still inspect every accepted text for factual errors, including
correct numbers given the wrong interpretation. Reported language is a model
claim, not independent language detection.
The cardinal/date parser does not recognize every natural-language quantity;
that limit must not be described as proof of complete prose truth.

## Fixed comparison

Reuse the unchanged [three saved runs](../recorded-fixtures.json), SHA-256
`b255b3b18050a6c7ca7b39fd99645ca3297a4b50a373bf109895ea4fe9793851`.
DOCN buy-and-hold, DOCN DCA with costs and SPY RSI each run in English and
Spanish, with four repetitions of each Quick take / Breakdown pair per tier.
This gives **48 tasks per tier, 96 total**. Each visit composes Quick take then
Breakdown; Breakdown receives that visit's accepted Quick take if available.

For each fixture/language the order is current 1, structured 1, structured 2,
current 2, current 3, structured 3, structured 4, current 4. Both arms use the
same corrected implementation. Committed-tree validation allows only the
`result_summary` and `result_breakdown` task-map values to differ, inside
`src/argus/llm/openrouter_tasks.py`. Current means chat/context; the second arm
sets both to structured. Runtime/provider configuration and output profiles
remain the same.

## Acceptance report

After explicit paid approval, record per tier and surface:

- Accepted complete model texts and complete fallbacks, including each failure.
- Quality passes against the unchanged founder requirements: useful historical
  interpretation beyond the card, short first-glance Quick take, deeper
  complementary Breakdown, correct language, no advice/forecast/price-cause
  claim, and no em dashes. No new word quota is applied.
- Every factual error in accepted text, with its exact task and canonical
  source. Suppressed draft errors are separate observations.
- Actual provider cost where reported and full reservations for unknown
  attempts, plus source hashes, raw structured drafts and HTTP provenance.

The truth bar is **zero factual errors in accepted text**. All-fallback output
does not constitute useful model-writing quality. If neither tier clears the
truth bar, recommend keeping the templates. Stop and report after this round;
it cannot authorize fingerprint regeneration or deployment.

## Cost approval

The [proposed $50 cap](cost-estimate.md) is pending final clean-checkout sizing
and founder approval. Complete fact sheets exceed the old request bound for
DOCN; the estimate prices a 90,000-byte ceiling without truncating evidence.
No unused first-round allowance is being treated as approval for this round.

## Deterministic verification

Python 3.10.20; provider keys blank for tests. The final combined generation,
fact-sheet, transport, prompt-surface and comparison-harness run passed
**693 tests**. The required mocked conversation harness passed **257 tests**.
The private-prose, bilingual reader and readout-content suites passed **88 web
tests**. Ruff, diff checks and the dependency lock check passed.

The fingerprint suite has its expected held result: **2 passed, 1 failed**
(`test_model_facing_text_matches_its_measured_fingerprint`). The manifest was
not changed. The extractor now also covers the fact-sheet meanings so future
measurement cannot overlook model-facing input labels.

Local Codex review returned clean after fixing the observed wrong-month,
currency-name and article regressions. A separate review verified the
fact-sheet meaning and unsupported-derivation fixes. These local results do
not claim green GitHub CI, paid quality results or merge readiness.
