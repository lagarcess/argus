# Breakdown reload, arithmetic and chronology proof

Runtime source: `fba5a03620efc71ab4eb1f423180052714947cef`. PR #588 remains unmerged; this is an evidence handoff, not a READY claim.

## Result

The three scoped defects are corrected in code. The English DOCN answer completed after its writing tab reloaded and appeared without Retry; the Spanish provider-error fallback also survived a writer reload. Both showed exactly one working state before and after reload. Both RSI Breakdowns quote the computed $50 loss rather than subtracting the rounded $1,039 and $988 balances. The English DOCN Breakdown puts the February–August 2025 drawdown before the June 15, 2026 global peak. Spanish DOCN model chronology could not be observed because Perplexity returned HTTP 500; its sent dated facts and deterministic ordering tests pass.

Four fresh backtests, eight readout attempts, no deliberate provider retries. Luna wrote seven readouts; the Spanish DOCN Breakdown showed the complete template. Known billed total for this round: **$0.15312915**. Attempts 9 and 17 were interpreter transport cancellations/timeouts, and attempt 22 was the Perplexity HTTP 500. None returned a bill. Their costs are unknown and excluded, not recorded as zero. The $2 billed-spend stop was not reached.

## What changed

- Breakdown uses the existing research task retention, `chat.research` job records, answer persistence and job settlement. It reserves the production job and saves its acknowledgement before paid work; it saves the answer before marking the job complete. The stream retains dispatch before its first explain progress frame and shields its wait. A browser disconnect cannot cancel the retained completion owner.
- The web projects a pending Breakdown job into the existing Breakdown frame, replaces that frame with the saved answer, and removes the pending acknowledgement when history already contains the answer. Sources keep using the shared panel metadata.
- The headline facts now include the exact precomputed drawdown dollar loss and the global peak date. They group related values with dates and sort events by complete timestamps. Arithmetic uses original stored balances before display rounding. No chart series or internal fact paths enter the Breakdown request.
- The writing rules, figure/language checks, readout tiers and prompt fingerprint were not changed in this round. No environment files were written.

## Demo and limits

The old demo servers were stopped. The updated real local app used live OpenRouter, Perplexity, asset resolution and market data, with process-only configuration. It used development memory persistence and mock authentication. The browser demonstrates the retained memory-turn completion path; tests exercise the production job path and its real status endpoint with a fake persistence gateway. This is not hosted-preview or real-database acceptance, and it does not establish recovery from an API process crash.

[Open the local app](http://127.0.0.1:3222/chat). It signs in automatically as Mock Developer; no password is needed. Select Settings → Preferences → App language → English or Español to match the saved readout. A mismatched language shows the localized template.

| Case | Quick take | Breakdown | Q billed | B billed | All case bills | Search calls / panel sources |
| --- | --- | --- | ---: | ---: | ---: | --- |
| SPY RSI (en) | Luna | Luna | $0.0036558 | $0.01142 | $0.04270040 | 3 / 5 |
| DOCN buy and hold (en) | Luna | Luna | $0.0064795 | $0.01186 | $0.04546625 | 3 / 5 |
| DOCN buy and hold (es-419) | Luna | Template: HTTP 500 | $0.00665545 | Unknown | $0.02449875 | Unknown / 0 |
| SPY RSI (es-419) | Luna | Luna | $0.00362345 | $0.00839 | $0.04046375 | 2 / 3 |

Search counts are provider-billed tool invocations. A failed response with no usage cannot establish whether a search ran. Sources below are the exact rows shown in the panel, not an assertion that every inline link is in that list.

## Run-owned arithmetic and chronology

| Run | Drawdown start | Balance at start | Drawdown bottom | Balance at bottom | Exact dollar loss | Displayed loss | Global peak/date |
| --- | --- | ---: | --- | ---: | ---: | ---: | --- |
| SPY RSI | 2025-12-05T05:00:00 | $1038.57 | 2026-03-30T04:00:00 | $988.47 | $50.10 | $50 | $1085.97 / 2026-04-14T04:00:00 |
| DOCN buy and hold | 2025-02-18T05:00:00 | $1747.10 | 2025-08-01T04:00:00 | $963.34 | $783.76 | $784 | $6784.14 / 2026-06-15T04:00:00 |

The same values were reproduced in both languages. The paired dated facts remain compact: request input is 961–1,003 characters and instructions are 1,958–1,974 characters. Search results contribute additional provider input tokens. The sent headline lines were rebuilt on the final runtime source and matched all four requests exactly.

## Writer reload evidence

- English DOCN: provider attempt 15 started at **07:41:11.711 UTC**; the writing tab reloaded at **07:41:30.311**; the provider completed at **07:41:41.049**, billing **$0.01186**. The retained task saved message `26118f30-9f54-4bb8-bc06-362e673adcdf`, and ordinary history recovery displayed it without Retry or another provider call.
- Spanish DOCN: the writing tab also reloaded while attempt 22 was in flight. The provider returned HTTP 500. The complete fallback was saved as `cfa463a4-b865-4f89-85d0-f0561fb5b45e` and replaced the one Spanish working frame. No sources were fabricated.
- The initial English RSI reload happened after generation finished, so it establishes saved readback only. The English DOCN timeline above is the in-flight paid-answer proof.

## SPY RSI (en)

[Open conversation](http://127.0.0.1:3222/chat?conversation=6e724cdb-ab3b-4092-875c-451160e970d7) · [Stored source facts](evidence/model-result-readouts/reload-facts-demo/rsi-en-source-facts.json). Run `0936946b-8251-5713-a937-68c499945880`.

**Quick take**: source `llm_explain_stage`, fallback `false`, failure `None`. Provider attempt 6, billed $0.0036558. The full saved prose is in [the machine-readable summary](evidence/model-result-readouts/reload-facts-demo/demo-summary.json).

**Breakdown**: source `llm_breakdown_stage`, fallback `false`, failure `None`. Provider attempt 7, billed $0.01142. The full saved prose is in [the machine-readable summary](evidence/model-result-readouts/reload-facts-demo/demo-summary.json).

Screenshots:

- [rsi-en-breakdown.png](evidence/model-result-readouts/reload-facts-demo/rsi-en-breakdown.png)
- [rsi-en-card-quick-take.png](evidence/model-result-readouts/reload-facts-demo/rsi-en-card-quick-take.png)
- [rsi-en-sources.png](evidence/model-result-readouts/reload-facts-demo/rsi-en-sources.png)
- [rsi-en-working-before-reload.png](evidence/model-result-readouts/reload-facts-demo/rsi-en-working-before-reload.png)

Sources shown in the panel:

- [S&P 500 monthly review: record highs and key turning ...](https://www.investing.com/news/stock-market-news/sp-500-monthly-review-record-highs-and-key-turning-points-since-early-2025-93CH-4830835) · 2026-08-03
- [The S&P 500 is wrapping up a tough month. Why April could be better](https://www.cnbc.com/2026/03/31/the-sp-500-is-wrapping-up-a-tough-month-why-april-could-be-better.html) · 2026-03-31
- [S&P 500 (^GSPC) Historical Data - Yahoo Finance](https://finance.yahoo.com/quote/%5EGSPC/history/) · 2026-08-04
- [Market Brief: March 2026](https://www.camdennational.bank/wealth/market-briefs/market-brief-march-2026) · 2026-03-04
- [S&P 500 hits intraday record high fueled by rate cut bets](https://www.reuters.com/business/sp-500-hits-intraday-record-high-fueled-by-rate-cut-bets-2025-12-24/) · 2025-12-24

## DOCN buy and hold (en)

[Open conversation](http://127.0.0.1:3222/chat?conversation=49b35b2a-e912-4108-932f-b062d014668e) · [Stored source facts](evidence/model-result-readouts/reload-facts-demo/docn-en-source-facts.json). Run `8f60ac5f-bb43-5e3c-9226-8904949a6dd5`.

**Quick take**: source `llm_explain_stage`, fallback `false`, failure `None`. Provider attempt 14, billed $0.0064795. The full saved prose is in [the machine-readable summary](evidence/model-result-readouts/reload-facts-demo/demo-summary.json).

**Breakdown**: source `llm_breakdown_stage`, fallback `false`, failure `None`. Provider attempt 15, billed $0.01186. The full saved prose is in [the machine-readable summary](evidence/model-result-readouts/reload-facts-demo/demo-summary.json).

Screenshots:

- [docn-en-breakdown-after-reload.png](evidence/model-result-readouts/reload-facts-demo/docn-en-breakdown-after-reload.png)
- [docn-en-breakdown-chronology.png](evidence/model-result-readouts/reload-facts-demo/docn-en-breakdown-chronology.png)
- [docn-en-card-quick-take.png](evidence/model-result-readouts/reload-facts-demo/docn-en-card-quick-take.png)
- [docn-en-sources-after-reload.png](evidence/model-result-readouts/reload-facts-demo/docn-en-sources-after-reload.png)
- [docn-en-working-after-reload.png](evidence/model-result-readouts/reload-facts-demo/docn-en-working-after-reload.png)
- [docn-en-working-before-reload.png](evidence/model-result-readouts/reload-facts-demo/docn-en-working-before-reload.png)

Sources shown in the panel:

- [DigitalOcean Announces First Quarter 2026 Financial Results](https://investors.digitalocean.com/news/news-details/2026/DigitalOcean-Announces-First-Quarter-2026-Financial-Results/default.aspx) · 2026-05-05
- [DigitalOcean (NYSE:DOCN) Reports Upbeat Q1 CY2026, Stock Jumps 17.2%](https://finance.yahoo.com/markets/stocks/articles/digitalocean-nyse-docn-reports-upbeat-121914165.html) · 2026-05-05
- [Earnings call transcript: DigitalOcean Q1 2026 beats estimates ...](https://www.investing.com/news/transcripts/earnings-call-transcript-digitalocean-q1-2026-beats-estimates-stock-surges-93CH-4659342) · 2026-05-05
- [DigitalOcean (NYSE:DOCN) Shares Up 11.7% - What's Next?](https://www.marketbeat.com/instant-alerts/price-digitalocean-nyse-docn-shares-up-117-whats-next-2026-09-08/) · 2026-09-08
- [About Us](https://markets.financialcontent.com/pennwell.bioopticsworld/article/stockstory-2025-2-24-why-digitalocean-docn-stock-is-falling-today) · 2025-02-24

## DOCN buy and hold (es-419)

[Open conversation](http://127.0.0.1:3222/chat?conversation=d67fc2cf-aea6-43f0-af26-89a0d8bb16d9) · [Stored source facts](evidence/model-result-readouts/reload-facts-demo/docn-es-source-facts.json). Run `5c91cda6-e45e-526b-9a6c-3d8d044cbd10`.

**Quick take**: source `llm_explain_stage`, fallback `false`, failure `None`. Provider attempt 21, billed $0.00665545. The full saved prose is in [the machine-readable summary](evidence/model-result-readouts/reload-facts-demo/demo-summary.json).

**Breakdown**: source `deterministic_fallback`, fallback `true`, failure `llm_unavailable_or_contract_rejected`. Provider attempt 22, billed unknown. The full saved prose is in [the machine-readable summary](evidence/model-result-readouts/reload-facts-demo/demo-summary.json).

Screenshots:

- [docn-es-breakdown-fallback-after-reload.png](evidence/model-result-readouts/reload-facts-demo/docn-es-breakdown-fallback-after-reload.png)
- [docn-es-card-quick-take.png](evidence/model-result-readouts/reload-facts-demo/docn-es-card-quick-take.png)
- [docn-es-working-after-reload.png](evidence/model-result-readouts/reload-facts-demo/docn-es-working-after-reload.png)
- [docn-es-working-live.png](evidence/model-result-readouts/reload-facts-demo/docn-es-working-live.png)

Sources shown in the panel:

- None. The failed provider response produced a template.

## SPY RSI (es-419)

[Open conversation](http://127.0.0.1:3222/chat?conversation=45f2a061-52da-43c7-be52-698fa8eaefbf) · [Stored source facts](evidence/model-result-readouts/reload-facts-demo/rsi-es-source-facts.json). Run `4703f95a-b609-58ea-b852-79186518b69d`.

**Quick take**: source `llm_explain_stage`, fallback `false`, failure `None`. Provider attempt 28, billed $0.00362345. The full saved prose is in [the machine-readable summary](evidence/model-result-readouts/reload-facts-demo/demo-summary.json).

**Breakdown**: source `llm_breakdown_stage`, fallback `false`, failure `None`. Provider attempt 29, billed $0.00839. The full saved prose is in [the machine-readable summary](evidence/model-result-readouts/reload-facts-demo/demo-summary.json).

Screenshots:

- [rsi-es-breakdown-full.png](evidence/model-result-readouts/reload-facts-demo/rsi-es-breakdown-full.png)
- [rsi-es-breakdown.png](evidence/model-result-readouts/reload-facts-demo/rsi-es-breakdown.png)
- [rsi-es-card-quick-take.png](evidence/model-result-readouts/reload-facts-demo/rsi-es-card-quick-take.png)
- [rsi-es-sources.png](evidence/model-result-readouts/reload-facts-demo/rsi-es-sources.png)

Sources shown in the panel:

- [Oppenheimer sets Street-high 8100 S&P 500 target for 2026](https://www.reuters.com/business/oppenheimer-sets-street-high-8100-sp-500-target-2026-2025-12-08/) · 2025-12-08
- [Fed holds interest rates steady in 1st move since Iran war ...](https://abcnews.com/Business/fed-set-adjust-interest-rates-1st-time-war/story?id=131155455) · 2026-03-18
- [Powell says the global oil crisis may have only temporary ...](https://www.cnn.com/2026/03/18/economy/fed-march-rates-decision) · 2026-03-18

## Prose audit beyond the three fixes

The requested dollar-loss and event-order defects did not recur in delivered model Breakdowns. The Spanish DOCN attempt cannot establish model-text quality because it fell back. Correct numeric references are not a guarantee of correct prose relationships; remaining concerns are recorded rather than hidden by acceptance:

- English RSI Quick take still says “recorded fills.” Its Breakdown says it bought and sold “4 times,” which can be read as four complete cycles. The run actually has two buys and two sells, or two complete cycles. “Keeping the same $1,000 invested throughout” is also misleading for a strategy that exits to cash. The Spanish Quick take correctly describes two occasions, while its Breakdown’s “4 compras y ventas” still leaves the transaction/cycle distinction implicit.
- DOCN prose describes a much rougher ride relative to SPY. The run stores SPY return but does not provide benchmark volatility or drawdown, so that relative-risk claim is not established by the supplied run facts.
- The source panel contains the provider’s returned sources; the model can use additional inline URLs. No new claim-level citation-verification system was introduced. Source entailment and every external URL’s reachability were not independently verified in this scoped demo.
- The two date-ordered model Breakdowns and both RSI dollar-loss passages are preserved verbatim in the saved messages. No drafts were edited or retried to make the evidence look better.

## Verification and handoff

- 674 focused backend and mandatory mocked-measurement tests passed for the main fix; 1,776 frontend tests passed. Production TypeScript checks passed. Whole-repository TypeScript has pre-existing test-stub errors and is not claimed green.
- The final review fixes passed 72 affected tests, including both gateway modes, both languages, paid completion after cancellation, first-frame generator closure, failed job reservation/claim, stored-result actions, and mixed-offset intraday ordering. New regressions failed before their fixes.
- [The bounded Codex review](https://github.com/lagarcess/argus/pull/588#issuecomment-5631145213) completed clean on `fba5a03620`; all seven review threads were resolved at the terminal review audit.
- Original integration base: `d0884c3de81f8c53d454ac4f68f461d3b5dd77e3`. Fetched integration: `46d43c1dea6d2db4b49bf44fbd81351a9c29f4c2`. No reconciliation merge was made, per founder instruction. Simulated merged tree `e201c5e6cd156f9d39d280c6e9d21ce2a7ee62f9` passes the modularity budget. No additional integration or lane coordination was performed.
- Runtime-head PR CI fails only the held prompt fingerprint; the separate push run hit a dependency-download error. Final evidence-head CI is reported in the terminal PR comment. This is not an exact-head-green or READY claim.
- Frontend evidence is from source `3016129e`; all 677 served source hashes were checked unchanged at `fba5a036`. English RSI was generated at `3016129e`; the later fix changes dispatch scheduling and same-day timestamp sorting, and its daily headline request was rebuilt unchanged. Other cases ran on `fba5a036`.
- Fingerprint remains held. No full live measurement, merge, deployment, branch-protection change or environment-file write occurred.

[All provider bills](evidence/model-result-readouts/reload-facts-demo/spend.json) · [Saved messages/runs](evidence/model-result-readouts/reload-facts-demo/app-state.json) · [Summary](evidence/model-result-readouts/reload-facts-demo/demo-summary.json) · [Source revalidation](evidence/model-result-readouts/reload-facts-demo/source-revalidation.json) · [Headline request revalidation](evidence/model-result-readouts/reload-facts-demo/headline-request-revalidation.json) · [Merged-tree budget](evidence/model-result-readouts/reload-facts-demo/merged-tree-budget.log)
