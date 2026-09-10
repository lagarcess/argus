# Final writing-only round

Preparation only. No paid draft in this round has run. The founder must approve
the posted estimate before execution. The fingerprint stays held; no merge,
deployment, full live measurement or new backtest is authorized.

## Change and preserved behavior

The lane started clean at `ab1fbda96678e7115fa798b8ec781022da180c3f`.
There was no uncommitted slot work to preserve, and no slot code was introduced.
The writing brief now assigns numerical reporting to the card. Quick take
tells the first-glance historical story; Breakdown develops the holding
experience and tradeoffs without repeating it. A figure belongs in a sentence
only when needed to explain a point, through its existing fact reference.
A supported next historical test may follow naturally from that story,
without advice to trade, forecasts or price-cause claims.

Against that base, each of the three production files changes one string
constant: the Quick take brief, Breakdown brief and shared grounding brief.
Masking only those constants leaves identical Python ASTs. All schemas,
labeled facts, quote references and checks, language fallback, transport,
templates and production task tiers are unchanged. AGENTS and API documentation
describe the same writing ownership. This is not evidence that a model can yet
meet the writing or truth bar.

## Fixed twelve-draft check

Use the unchanged [recorded fixtures](../recorded-fixtures.json), SHA-256
`b255b3b18050a6c7ca7b39fd99645ca3297a4b50a373bf109895ea4fe9793851`:

| Saved run | Languages | Surfaces | Attempts |
| --- | --- | --- | --- |
| DOCN buy and hold | en, es-419 | Quick take, Breakdown | One each |
| DOCN DCA with costs | en, es-419 | Quick take, Breakdown | One each |
| SPY RSI | en, es-419 | Quick take, Breakdown | One each |

There are six paired visits and twelve frame tasks. Each visit runs Quick take
then Breakdown, passing only that visit's accepted Quick take as context.
Both tasks use the configured structured model in an isolated clean checkout.
The reference checkout receives no model calls; it proves that only the two
readout tier values in `src/argus/llm/openrouter_tasks.py` differ.
Production lane tiers stay chat/context.

The harness reserves cost before dispatch and allows one primary-model HTTP
attempt per task. A later internal retry or fallback dispatch is blocked and
recorded. A failed/rejected first attempt stays an outcome. No retries to
improve the score, no new backtests, no market-data calls and no paid judge.

## Cost approval

The [price snapshot](prices.json) uses the highest displayed Grok 4.3 provider
rates, including Priority: $2.50 per million input tokens and $5.00 per million
output tokens. It assumes no cache discount. Full request bytes, including the
schema, conservatively bound input tokens; Breakdown sizing also reserves room
for the preceding Quick take. The existing output caps remain 700 and 2,400.

The [free preflight](preflight.json) schedules exactly twelve tasks and records
zero HTTP attempts. Both checkouts are clean: current reference
`5e17e91788bc7f914348ee17fc868b4bec5f1559`, structured measurement
`5935ea3861d77b04fd3ce69f275aa293f2005a96`. The only source difference is the
two task-tier mapping values; 4,701 other tree entries are identical. The
structured checkout is local and unpushed.

The largest complete request is 82,967 bytes. With 8,192 bytes reserved for
the prior Quick take, the largest Breakdown allowance is 87,614 bytes. All
twelve fit a 90,000-byte ceiling. Counting each input byte as a token and
every task at that ceiling gives:

`12 × 90,000 × $2.50 / 1,000,000 + 6 × (700 + 2,400) × $5 / 1,000,000 = $2.793`

**Requested approval: up to $3 total**, current structured model only, one
primary-model HTTP attempt per task, exactly twelve tasks. Browser rendering
uses the saved outputs offline and adds no provider cost. Approval is pending;
no old budget approval authorizes this round.

## Browser and quality proof after approval

Render every outcome in the actual readout frames, in its requested language,
beside that run's canonical source numbers. Save one screenshot per task and
retain raw structured drafts, references, failures and request receipts.
Rejected/unavailable drafts show the full product fallback. Any complete raw
rejected draft appears separately as diagnostic text, never as accepted prose.
The replay is offline and cannot create model calls or backtests.
The [prepared browser harness](browser/README.md) refuses free preflight reports
as live outcomes, checks raw rejected prose separately from accepted frames,
and records the source and reader hashes. No final-round screenshots exist yet.

Review all twelve outcomes for acceptance/fallback, first-glance versus depth,
meaning beyond the card, repetition, correct language and every factual error.
Accepted text must have zero factual errors. Report suppressed raw-draft errors
separately. A fall back is not a writing-quality pass. Retain actual provider
cost where available and full reservations for attempts with unknown cost.

## Free validation

- 521 focused readout, facts, transport and OpenRouter policy tests passed.
- 257 mocked evaluation checks passed; six prompt-surface tests passed.
- The freeze test remains red as instructed: one held fingerprint mismatch,
  with the other two checks passing. The manifest was not regenerated.
- Ruff and diff checks passed for the production writing change.
- 70 focused measurement/probe tests passed, including blocked retries and
  fallback dispatches with the next frame still exercised.
- The [writing-only source audit](writing-only-audit.json) confirms unchanged
  behavior outside the three brief strings. Bounded independent review of the
  brief and harness returned no findings.
- Offline browser preparation passed twelve invalid-input checks, four raw-draft
  extraction checks, Python lint/format and Node syntax validation. It started
  zero servers and made zero provider or backtest calls.

The twelve-draft check cannot authorize updating the fingerprint or claim a
green release gate. Stop and report after the bounded proof.
