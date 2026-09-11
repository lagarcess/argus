# Result readout panel demo, September 11, 2026

Readout generation commits: `7141b0dc54ae8c4a5d38f16b23601f5a616f7b1d`, `755bfcaef0adeef7c5c8accee77a183f9864e547`.
Latest app export source: `755bfcaef0adeef7c5c8accee77a183f9864e547`. The first two English pairs retain their earlier model text; later pairs and the supplemental wording check use the newer source.

Real local frontend and backend, real provider calls and backtest execution; development memory persistence and mock authentication. Not hosted-preview, deployment, or durable database acceptance.

The six main demonstrations delivered all twelve model readouts. The separate English DOCN supplement checks the newer strategy wording without replacing the original English case. Model acceptance is separate from factual correctness: both RSI Breakdowns contain the same small $51 versus $50.10 drawdown-loss error, and the supplemental DOCN Breakdown narrates its 2026 global peak before its 2025 drawdown. These and the qualitative/citation caveats are recorded below.

Known billed cost for the six main cases: **$0.28661440**. Their twelve delivered drafts cost **$0.10874055**; all readout attempts cost **$0.12056055**, including the canceled English RSI Breakdown. Earlier attempts cost **$0.35819697**, the supplemental case **$0.02955730**, and the additional failed follow-up route **$0.12511755**. Cumulative known billed total: **$0.79948622**.

7 attempts returned no invoice. Their unknown cost is excluded, not treated as zero; HTTP errors and transport errors are listed separately below.

| Case | Language | Quick take | Breakdown | Delivered Q+B billed | All turns billed | Delivered B search invocations |
| --- | --- | --- | --- | ---: | ---: | ---: |
| DOCN buy and hold | en | Luna | Luna | $0.0208146 | $0.03154700 | 3 |
| DOCN DCA with costs | en | Luna | Luna | $0.01832665 | $0.04662330 | 2 |
| SPY RSI | en | Luna | Luna | $0.0171574 | $0.05569450 | 3 |
| DOCN buy and hold | es-419 | Luna | Luna | $0.0189304 | $0.03672530 | 3 |
| DOCN DCA with costs | es-419 | Luna | Luna | $0.01663745 | $0.08818940 | 3 |
| SPY RSI | es-419 | Luna | Luna | $0.01687405 | $0.02783490 | 3 |

Search invocations come from provider billing metadata. One invocation can contain several queries. All-turn costs also include interpretation, fidelity checks, clarification and naming when used.

## Open the local demo

[Open the latest English DOCN demo](http://127.0.0.1:3222/chat?conversation=19d76ad0-f502-48eb-a00a-556a964ff2a0). Local QA signs in automatically as Mock Developer; no password is needed. To view the saved cases in either language, open Settings → Preferences → App language and select English or Español. Choose the saved readout’s language to see its model text; a different language shows the localized template.

## Evidence and audit

[Machine-readable summary](evidence/model-result-readouts/app-demo-fixes/final-demo-summary.json) · [All provider bills](evidence/model-result-readouts/app-demo-fixes/spend.json) · [Saved messages and run facts](evidence/model-result-readouts/app-demo-fixes/app-state.json) · [Frontend source manifest](evidence/model-result-readouts/app-demo-fixes/web-source.json)

### DOCN buy and hold (en)

Conversation `775145e4-561d-4b9c-8ae0-5c6b94938dd3`; run `94f9ac80-f93b-5079-82c7-9e61a1aa5b6b`.

User turns:

- Buy and hold DOCN from September 1, 2023 through September 9, 2026 with $1,000 starting capital. Compare with SPY, with no fees or slippage.
- Run backtest
- Explain result

Audit:

- Accepted Quick take and Breakdown both persist English model text. Quoted run values agree with the saved run within rounding: $1,000 seed, $4,962.59 ending equity, $6,784.14 highest equity, 396.26% total return, 68.98% SPY return, 327.27 percentage-point gap, 68.62% annualized volatility, and 44.86% maximum drawdown. The one execution was a buy, not a completed buy-and-sell pair.
- The deeper drawdown explanation uses the actual dated event: $1,747.10 on February 18, 2025 to $963.34 on August 1, 2025. The loss was $783.76. It correctly explains that this low fell below the original $1,000 seed.
- Quick take places the $6,784 peak-to-$4,963 ending decline beside 44.9%, although that particular peak-to-end decline was 26.85%. The 44.9% figure belongs to the earlier dated event. The individual figures are correct, but the adjacent wording can suggest the wrong relationship.
- The claim of much larger ups and downs than SPY is not established by the saved run: it retains SPY return but no benchmark volatility, drawdown, or equity path. Treat that comparison as unsupported by these run facts, rather than as a proven false value.
- The company operating facts and May 2025 earnings reaction have retained search support. Explanations about investor expectations and news supporting the recovery remain inference, not demonstrated causal attribution.
- The Q2 2025 inline URL differs from the retained working company-release URL by omitting '-Results/default.aspx'. Read-only web retrieval could open the canonical retained URL and confirm the operating facts; it could not open the shortened draft URL. Its reachability is unverified, not a proven HTTP 404. The Sources panel contains the exact five metadata rows listed below, not every inline citation.

**Quick take**

Source `llm_explain_stage`; fallback `false`; failure `None`; delivered draft **$0.0066446**, all frame attempts **$0.0066446**; source `7141b0dc54ae8c4a5d38f16b23601f5a616f7b1d`.

> Holding DOCN through this historical run turned $1,000 invested into $4,963, while SPY returned 69.0%. The tradeoff was a rougher ride: the account later fell from a recorded $6,784 peak to $4,963 at the end, after a 44.9% investment drawdown. This was a strong result for DOCN over this specific window, but it came with much larger ups and downs than the benchmark.

[Response 73](evidence/model-result-readouts/app-demo-fixes/provider-response-073.json)

**Breakdown**

Source `llm_breakdown_stage`; fallback `false`; failure `None`; delivered draft **$0.01417**, all frame attempts **$0.01417**; source `7141b0dc54ae8c4a5d38f16b23601f5a616f7b1d`.

> From September 1, 2023 to September 9, 2026, this was essentially a single buy-and-hold journey in DOCN. The $1,000 contributed was not followed by additional deposits. By the end, the portfolio was worth $4,963, a 396.3% return. It reached as high as $6,784 along the way, so the final result came after giving back part of an earlier gain.
>
> The difficult part came in 2025. After standing at $1,747, the portfolio fell to $963 between February 18 and August 1, a 44.9% drop from its prior high. That means the recorded balance did fall below the original $1,000 during the decline. The ride was rough, with annualized volatility of 68.6%, but staying invested allowed the later recovery to remain part of the result.
>
> The business backdrop helps explain both sides of the experience. DigitalOcean reported accelerating revenue growth in late 2024, improving customer expansion, strong profitability, and rapid growth in its AI business, while guiding for continued growth in 2025 ([Q4 2024 results and call](https://www.fool.com/earnings/call-transcripts/2025/02/25/digitalocean-docn-q4-2024-earnings-call-transcript/)). But the stock still weakened during the period that began in February. In May 2025, DigitalOcean reported revenue and earnings ahead of expectations, yet its shares fell sharply after the release ([May 2025 market reaction](https://247wallst.com/companies/docn/earnings/2025/Q1/)). The results were positive, so the timing suggests investors were judging DOCN against demanding expectations for future growth, not simply reacting to whether the latest quarter was profitable.
>
> The recovery was supported by improving operating evidence. In August 2025, DigitalOcean reported stronger customer growth, more than doubled AI and machine-learning revenue year over year, and raised its full-year outlook ([Q2 2025 results](https://investors.digitalocean.com/news/news-details/2025/DigitalOcean-Announces-Second-Quarter-2025-Financial/)). Later results described stronger AI traction, larger customers, and renewed growth momentum ([Q4 2025 results](https://investors.digitalocean.com/news/news-details/2026/DigitalOcean-Announces-Fourth-Quarter-and-Fiscal-Year-2025-Financial-Results/)). Those reports help explain why a stock that suffered a deep setback could later finish far above its starting point, although they do not prove that every price move was caused by one particular announcement.
>
> Against SPY, the tradeoff was meaningful. SPY returned 69.0%, while DOCN returned 396.3%, beating the benchmark by 327.3 percentage points. In plain terms, holding DOCN exposed the portfolio to a much larger company-specific swing, including the fall below the starting balance, in exchange for a much larger eventual gain than the broad-market benchmark. The test records one purchase or sale, so there was little activity to soften or avoid that experience.

[Response 74](evidence/model-result-readouts/app-demo-fixes/provider-response-074.json)

Sources actually supplied to the panel (5, maximum five):

- [DigitalOcean Announces Fourth Quarter and Fiscal Year 2025 ...](https://investors.digitalocean.com/news/news-details/2026/DigitalOcean-Announces-Fourth-Quarter-and-Fiscal-Year-2025-Financial-Results/) · 2026-02-24
- [DigitalOcean (DOCN) Q4 2025 Earnings Transcript | The Motley Fool](https://www.fool.com/earnings/call-transcripts/2026/02/24/digitalocean-docn-q4-2025-earnings-transcript/) · 2026-02-24
- [Document 2 - file: a2024-q4dopressrelease.htm](https://www.sec.gov/Archives/edgar/data/1582961/000158296125000033/a2024-q4dopressrelease.htm) · 2026-03-21
- [Why DigitalOcean (DOCN) Stock Is Down Today](https://stockstory.org/us/stocks/nyse/docn/news/why-up-down/why-digitalocean-docn-stock-is-down-today-2) · 2025-05-06
- [DigitalOcean Holdings Full Year 2024 Earnings: EPS Beats Expectations](https://finance.yahoo.com/news/digitalocean-holdings-full-2024-earnings-145200833.html) · 2025-03-01

Screenshots:

- [final-docn-en-breakdown.png](evidence/model-result-readouts/app-demo-fixes/final-docn-en-breakdown.png)
- [final-docn-en-card-and-quick-take.png](evidence/model-result-readouts/app-demo-fixes/final-docn-en-card-and-quick-take.png)
- [final-docn-en-quick-take.png](evidence/model-result-readouts/app-demo-fixes/final-docn-en-quick-take.png)
- [final-docn-en-sources-live.png](evidence/model-result-readouts/app-demo-fixes/final-docn-en-sources-live.png)
- [final-docn-en-sources-reloaded.png](evidence/model-result-readouts/app-demo-fixes/final-docn-en-sources-reloaded.png)
### DOCN DCA with costs (en)

Conversation `e5eacf9d-e85e-4fa1-a021-6f3576a1dadc`; run `dab03246-e0d9-52f8-a965-b8d59a38290f`.

User turns:

- Buy $100 of DOCN every month from September 10, 2025 through September 9, 2026. Compare with SPY. Include a 10 basis point fee and 5 basis points of slippage on each purchase.
- Run backtest
- Explain result

Audit:

- Accepted Quick take and Breakdown both persist English model text. All declared run references pass the retained-value check. $1,000 initial seed plus $100 periodic contributions produced $2,300 total funded, $6,644.07 ending equity and $4,344.07 profit. The stated 188.9% return on contributions, 12.1% benchmark return, 176.8 percentage-point gap, 85.4% annualized volatility and $8,649 highest equity all match within rounding.
- The 13 stored executions are buys. '13 purchases and sales' names the combined execution category; it should not be read as 13 sales or 13 completed buy-and-sell pairs.
- 42.12% is the flow-adjusted investment drawdown, excluding new deposits. Both frames describe a portfolio/account decline without explaining that basis. The value is correct, but it is not proof of a 42.12% fall in the nominal account balance. No dated or dollar drawdown is claimed, and the stored nominal chart cannot establish the flow-adjusted event dates without dated flows.
- Claims of a rougher ride than SPY lack a retained benchmark risk metric or path. The high DOCN volatility is supported; the relative risk comparison is unverified by the supplied run facts.
- The cited 16%, 22%, and 29% year-over-year company revenue growth figures appear in retained search results for the respective 2025 Q3, 2026 Q1 and 2026 Q2 periods. They are external operating figures, not simulation inputs. News explaining the price result remains inference. All three inline URLs are present in retained search results; the actual Sources panel contains two metadata rows.
- The run includes 10 basis points of fees and 5 basis points of slippage, visible in the card. These model frames do not explain their effect. This is a depth limitation, not a false metric or a required-mention rejection.

**Quick take**

Source `llm_explain_stage`; fallback `false`; failure `None`; delivered draft **$0.00344665**, all frame attempts **$0.00344665**; source `7141b0dc54ae8c4a5d38f16b23601f5a616f7b1d`.

> Staying invested in DOCN through this historical run turned $2,300 of starting money and monthly contributions into $6,644, with $4,344 above the money deposited. It beat SPY by 176.8 percentage points, but the ride was rough: the account experienced a 42.1% drawdown and ended well below its $8,649 peak. The tradeoff was clear: much stronger results than the benchmark, with much larger ups and downs to hold through.

[Response 82](evidence/model-result-readouts/app-demo-fixes/provider-response-082.json)

**Breakdown**

Source `llm_breakdown_stage`; fallback `false`; failure `None`; delivered draft **$0.01488**, all frame attempts **$0.01488**; source `7141b0dc54ae8c4a5d38f16b23601f5a616f7b1d`.

> From September 10, 2025 to September 9, 2026, this test put $1,000 into DOCN and added $100 each month. The 13 purchases and sales spread the buying across the year, so staying invested meant continuing to buy through both strong rises and sharp setbacks.
>
> DOCN benefited from a period in which DigitalOcean reported faster growth and stronger demand from larger customers and AI-focused customers. In November 2025, the company reported 16% revenue growth, record new annualized recurring revenue, and plans for additional data-center capacity to serve AI customers ([company results](https://investors.digitalocean.com/news/news-details/2025/DigitalOcean-Announces-Third-Quarter-2025-Financial-Results/default.aspx)). It later reported 22% revenue growth in the first quarter of 2026 and raised its outlook, citing growth in AI customer revenue and larger customer accounts ([company results](https://investors.digitalocean.com/financials/quarterly-results/default.aspx)). By August, DigitalOcean reported 29% revenue growth, a large increase in AI customer revenue, record new recurring revenue, and another increase to its 2026 outlook ([company results](https://investors.digitalocean.com/financials/quarterly-results/default.aspx)). Those reports help explain the strong DOCN result, although company news cannot account for every daily price move.
>
> The ride was far from smooth. The portfolio experienced a 42.1% decline at its largest measured drop, and its value later reached $8,649 before ending at $6,644. Because the recorded contributions totaled $2,300, the ending balance shows that the test finished well above the money added, despite giving back part of its highest value.
>
> The tradeoff against SPY was unusually large. DOCN returned 188.9% on contributions, compared with 12.1% for SPY, a difference of 176.8 percentage points. But that extra return came with much rougher movement: DOCN's annualized volatility was 85.4%, alongside the deep decline during the test. In plain terms, holding DOCN delivered a much bigger outcome than the broad-market benchmark in this particular window, but it required tolerating much larger ups and downs along the way.

[Response 83](evidence/model-result-readouts/app-demo-fixes/provider-response-083.json)

Sources actually supplied to the panel (2, maximum five):

- [Financials - Quarterly Results - DigitalOcean, LLC](https://investors.digitalocean.com/financials/quarterly-results/default.aspx) · 2026-08-26
- [DigitalOcean (DOCN) Q4 2025 Earnings Transcript | The Motley Fool](https://www.fool.com/earnings/call-transcripts/2026/02/24/digitalocean-docn-q4-2025-earnings-transcript/) · 2026-02-24

Screenshots:

- [final-dca-en-breakdown.png](evidence/model-result-readouts/app-demo-fixes/final-dca-en-breakdown.png)
- [final-dca-en-card-and-quick-take.png](evidence/model-result-readouts/app-demo-fixes/final-dca-en-card-and-quick-take.png)
- [final-dca-en-sources-live.png](evidence/model-result-readouts/app-demo-fixes/final-dca-en-sources-live.png)
- [final-dca-en-sources-reloaded.png](evidence/model-result-readouts/app-demo-fixes/final-dca-en-sources-reloaded.png)
### SPY RSI (en)

Conversation `b9dea946-0872-4ed2-b1ce-c5765df5d35f`; run `e8391111-5004-542d-b690-baee745bdc28`.

User turns:

- Backtest SPY from September 10, 2025 through September 9, 2026 with $1,000. Use RSI with a 14-day period: buy when RSI crosses below 30, sell when RSI crosses above 70. No fees or slippage.
- Run backtest
- Explain result
- Explain result

Audit:

- English Quick take is accepted and persisted. Its four declared numeric references pass: profit $86 versus stored $85.97, return 8.6%, benchmark return 16.9% versus 16.89%, and lag 8.3 percentage points versus a stored negative gap of 8.29.
- The text says SPY was bought and sold twice. The saved, explicitly unsampled execution markers show buy on November 18, 2025, sell on December 9, 2025, buy on March 18, 2026, and sell on April 14, 2026. This supports two completed cycles for this case. The count is not declared in the draft references; manual ledger review supplies its support.
- The statement that the strategy avoided large swings is consistent with its stored 4.82% maximum drawdown and 6.09% annualized volatility. The text does not quote an unsupported benchmark risk number.
- First Breakdown attempt 90 returned HTTP 200 and billed $0.01182 at 06:00:39 UTC, but the app request had been canceled by a full page reload before persistence. The raw paid response is retained; it was neither a delivered Breakdown nor a model fallback. After the existing stale-turn timeout, the app showed the stopped turn with Retry, and the typed Retry action produced the delivered Breakdown below.
- Retry attempt 127 delivered an accepted English Breakdown, with sixteen declared references passing the retained-value check. The dates, returns, final/highest value and volatility match the run.
- The delivered Breakdown repeats the small arithmetic error found in Spanish: it states a $51 loss after separately rounding $1,038.57 and $988.47 to $1,039 and $988. The exact loss is $50.10, nearest whole dollar $50. This $51 is not declared as a figure, so the reference check does not inspect it.
- All four inline URLs occur in the retained search results, which support the general market backdrop and oil above $100. Nasdaq's March 2026 article is returned with source_date 2024-04-05 despite its 2026 title/content. The report preserves that panel date and flags the inconsistency rather than silently correcting external metadata.
- Quick take cost $0.0035074; the delivered Breakdown retry cost $0.01365, for $0.0171574 across the delivered pair. Including the canceled $0.01182 Breakdown call, this case spent $0.0289774 on readout attempts. Delivered Breakdown used three search invocations; canceled attempt used another three.

**Quick take**

Source `llm_explain_stage`; fallback `false`; failure `None`; delivered draft **$0.0035074**, all frame attempts **$0.0035074**; source `755bfcaef0adeef7c5c8accee77a183f9864e547`.

> This RSI-based approach bought and sold SPY twice, finishing with a gain of $86. It avoided large swings, but the tradeoff was meaningful: it lagged simply holding the benchmark, returning 8.6% versus 16.9%, a gap of 8.3 percentage points.

[Response 89](evidence/model-result-readouts/app-demo-fixes/provider-response-089.json)

**Breakdown**

Source `llm_breakdown_stage`; fallback `false`; failure `None`; delivered draft **$0.01365**, all frame attempts **$0.02547**; source `755bfcaef0adeef7c5c8accee77a183f9864e547`.

> From September 10, 2025, to September 9, 2026, the strategy put one initial $1,000 to work in SPY and used RSI signals to buy and sell four times, rather than simply buying once and holding. The broader market backdrop was generally supportive, helped at times by expectations for lower interest rates, although late-2025 trading also saw concerns about high technology valuations, artificial-intelligence enthusiasm, inflation, and Treasury yields. [Contemporary coverage on December 5](https://www.investopedia.com/dow-jones-today-12052025-11862734) and [December technology-sector weakness](https://www.theglobeandmail.com/investing/markets/inside-the-market/article-stock-market-live-updates-tsx-sp-500-12-12-2025/) describe that mixed setting.
>
> The roughest stretch began on December 5. The portfolio was worth $1,039 before the decline, then fell to $988 by March 30, a drop of $51 from that earlier high. That period included a broader market shock in March, when geopolitical tensions, sharply higher oil prices, inflation concerns, and tighter financial conditions weighed on U.S. stocks, according to [Nasdaq’s market review](https://www.nasdaq.com/articles/march-2026-review-and-outlook). The portfolio’s measured annualized volatility was 6.1%, so the test experienced noticeable ups and downs without an especially extreme recorded decline.
>
> The portfolio later recovered and finished at $1,086, its highest recorded value. With no money added beyond the original $1,000, that means the test ended with an $86 gain, or a total return of 8.6%.
>
> The important tradeoff was against the benchmark, which was also SPY held through the period. The benchmark returned 16.9%, so the RSI strategy lagged it by 8.3 percentage points. In plain terms, the strategy produced a positive result and navigated the decline, but its buying and selling captured less of SPY’s full-period rise than simply remaining invested in SPY would have. Near the end of the window, oil above $100 and renewed inflation concerns were again weighing on stocks, as [Reuters reported on September 9](https://www.reuters.com/world/china/global-markets-global-markets-2026-09-09/).

[Response 90](evidence/model-result-readouts/app-demo-fixes/provider-response-090.json) · [Response 127](evidence/model-result-readouts/app-demo-fixes/provider-response-127.json)

Sources actually supplied to the panel (5, maximum five):

- [March 2026 Review and Outlook - Nasdaq](https://www.nasdaq.com/articles/march-2026-review-and-outlook) · 2024-04-05
- [The Stock Market Just Flashed a Warning Not Seen in 12 Months. History Says Investors Should Do This Now. | The Motley Fool](https://www.fool.com/investing/2026/03/22/stock-market-warning-12-months-investors-do-this/) · 2026-03-22
- [The S&P 500 Just Had Its Worst Month Since 2022 - TrendWatch](https://trends.thicket.sh/stock-market-correction-2026) · 2026-03-27
- [Stock market news for March 4, 2026](https://www.cnbc.com/2026/03/03/stock-market-today-live-updates.html) · 2026-03-03
- [S&P 500 ends down as oil tops $100 per barrel](https://www.reuters.com/business/wall-st-futures-muted-oil-tops-100-first-time-since-july-2026-09-09/) · 2026-09-10

Screenshots:

- [final-rsi-en-breakdown.png](evidence/model-result-readouts/app-demo-fixes/final-rsi-en-breakdown.png)
- [final-rsi-en-card-and-quick-take.png](evidence/model-result-readouts/app-demo-fixes/final-rsi-en-card-and-quick-take.png)
- [final-rsi-en-sources-live.png](evidence/model-result-readouts/app-demo-fixes/final-rsi-en-sources-live.png)
- [final-rsi-en-sources-reloaded.png](evidence/model-result-readouts/app-demo-fixes/final-rsi-en-sources-reloaded.png)
### DOCN buy and hold (es-419)

Conversation `19316d90-6e8c-42be-a486-67d4791a1e97`; run `782c537b-57b4-548a-a967-a55530111b21`.

User turns:

- Compra y mantén DOCN del 1 de septiembre de 2023 al 9 de septiembre de 2026, con capital inicial de $1,000. Compáralo con SPY, sin comisiones ni deslizamiento.
- Ejecutar backtest
- Explicar resultado

Audit:

- Spanish Quick take and Breakdown are accepted, persisted as es-419, and delivered in the original stream and reloaded reader. The Breakdown opens naturally with buying DOCN once and holding it; the saved run has one entry execution and no recurring contributions.
- All five Quick take and fourteen Breakdown declared run references pass. $1,000 initial capital, $4,963 ending value, $3,963 profit, 396.3% strategy return, 69.0% benchmark return, 327.3 percentage-point gap and 44.9% worst drop agree with the stored values within rounding.
- The Breakdown describes the actual worst-drawdown event: February 18 to August 1, 2025, with saved endpoints $1,747.10 and $963.34. Its observation that the balance temporarily fell below the initial $1,000 is correct.
- The Spanish Quick take calls the ride much rougher in the comparison with SPY. The saved run has no SPY volatility, maximum drawdown or equity path, so this relative risk comparison remains unsupported by the supplied run evidence.
- The cited external figures are present in recorded search results: 2024 revenue growth of 13%, initial 2025 revenue-growth guidance around 13%, and 2025 Q2 revenue growth of 14%. The wording that 2025 guidance was more moderate is not established against the same 13% reported annual growth; a slowdown should not be inferred from those equal figures.
- All three inline URLs occur in the retained search results. The S&P 500 source shows positive 2024 and 2025 annual returns, supporting the stated broad-market backdrop. The company-news connection to DOCN recovery remains a contextual inference, and the text explicitly says it does not prove each price move.
- The Sources panel has five persisted metadata rows, distinct from the three inline links. Provider billing records three search invocations. Quick take cost $0.0065804; Breakdown cost $0.01235; Q+B total $0.0189304.

**Quick take**

Source `llm_explain_stage`; fallback `false`; failure `None`; delivered draft **$0.0065804**, all frame attempts **$0.0065804**; source `755bfcaef0adeef7c5c8accee77a183f9864e547`.

> Comprar DOCN una vez y mantener la posición durante este periodo terminó muy por encima de SPY: 396.3% frente a 69.0%, una diferencia de 327.3 pp. La contrapartida fue un recorrido mucho más brusco, incluida una caída máxima de 44.9% desde un máximo previo antes de cerrar con una ganancia registrada de $3,963.

[Response 95](evidence/model-result-readouts/app-demo-fixes/provider-response-095.json)

**Breakdown**

Source `llm_breakdown_stage`; fallback `false`; failure `None`; delivered draft **$0.01235**, all frame attempts **$0.01235**; source `755bfcaef0adeef7c5c8accee77a183f9864e547`.

> Entre el 1 de septiembre de 2023 y el 9 de septiembre de 2026, la experiencia fue comprar DOCN una vez y mantenerlo, sin aportar más dinero. Los $1,000 iniciales terminaron en $4,963, un rendimiento total de 396.3%. En otras palabras, el crecimiento vino de la inversión, no de depósitos adicionales.
>
> El resultado estuvo relacionado con una historia de expansión en el negocio de DigitalOcean. La empresa reportó que sus ingresos de 2024 crecieron 13% y que el crecimiento de clientes de mayor gasto se aceleró, aunque su guía para 2025 apuntaba a un crecimiento más moderado, de alrededor de 13% ([resultados del cuarto trimestre de 2024](https://investors.digitalocean.com/news/news-details/2025/DigitalOcean-Announces-Fourth-Quarter-and-Fiscal-Year-2024-Financial-Results/default.aspx)). Más adelante, DigitalOcean informó que sus ingresos del segundo trimestre de 2025 crecieron 14% y elevó su guía anual, señales que ayudan a explicar la recuperación posterior ([resultados del segundo trimestre de 2025](https://investors.digitalocean.com/news/news-details/2025/DigitalOcean-Announces-Second-Quarter-2025-Financial-Results/default.aspx)). Eso ofrece contexto para el avance, pero no demuestra que un evento específico haya causado cada movimiento del precio.
>
> Mantener no fue un recorrido tranquilo. Desde un máximo previo, el portafolio cayó 44.9% entre el 18 de febrero y el 1 de agosto de 2025: pasó de $1,747 a $963. Ese descenso llevó el saldo temporalmente por debajo de los $1,000 iniciales. Después, el valor se recuperó y terminó bastante por encima de ese punto bajo, aunque por debajo de su máximo registrado.
>
> Frente al benchmark SPY, la diferencia fue muy amplia. SPY obtuvo 69.0% en el mismo periodo, mientras DOCN obtuvo 396.3%, una ventaja de 327.3 puntos porcentuales. El benchmark representa una canasta amplia de grandes empresas estadounidenses, mientras que esta prueba concentró todo en una sola compañía, por lo que el resultado superior vino acompañado de una experiencia mucho más dependiente de los acontecimientos de DOCN. El contexto general también fue favorable para las acciones estadounidenses durante buena parte del periodo, con avances del S&P 500 en 2024 y 2025 ([datos históricos del S&P 500](https://ycharts.com/indices/%5ESPX)), pero eso por sí solo no explica la magnitud de la diferencia.

[Response 96](evidence/model-result-readouts/app-demo-fixes/provider-response-096.json)

Sources actually supplied to the panel (5, maximum five):

- [DigitalOcean Announces Fourth Quarter and Fiscal Year 2025 ...](https://investors.digitalocean.com/news/news-details/2026/DigitalOcean-Announces-Fourth-Quarter-and-Fiscal-Year-2025-Financial-Results/) · 2026-02-24
- [DigitalOcean Holdings, Inc. (DOCN) Q3 2025 Earnings Summary ...](https://fintool.com/app/research/companies/DOCN/earnings/Q3%202025) · 2025-11-20
- [DigitalOcean (DOCN) Q4 2024 Earnings Call Transcript](https://www.nasdaq.com/articles/digitalocean-docn-q4-2024-earnings-call-transcript) · 2025-02-25
- [S&P 500 (SP500) | FRED | St. Louis Fed](https://fred.stlouisfed.org/series/sp500) · 2026-09-10
- [S And P 500 Chart 2026 Year To Date | StatMuse Money](https://www.statmuse.com/money/ask/s-and-p-500-chart-2026-year-to-date) · 2026-09-10

Screenshots:

- [final-docn-es-breakdown.png](evidence/model-result-readouts/app-demo-fixes/final-docn-es-breakdown.png)
- [final-docn-es-card-and-quick-take.png](evidence/model-result-readouts/app-demo-fixes/final-docn-es-card-and-quick-take.png)
- [final-docn-es-sources-live.png](evidence/model-result-readouts/app-demo-fixes/final-docn-es-sources-live.png)
- [final-docn-es-sources-reloaded.png](evidence/model-result-readouts/app-demo-fixes/final-docn-es-sources-reloaded.png)
### DOCN DCA with costs (es-419)

Conversation `3411cb29-76eb-498d-9cf4-53d46dd0fa03`; run `efa35060-e7d6-52eb-a881-aa67c0fcad97`.

User turns:

- Haz un backtest de compras mensuales de $100 de DOCN, del 10 de septiembre de 2025 al 9 de septiembre de 2026, con $1,000 de capital inicial. Compáralo con SPY. Aplica comisiones de 10 puntos básicos y deslizamiento de 5 puntos básicos.
- Ejecutar solo compras recurrentes de $100 al mes de DOCN, del 10 de septiembre de 2025 al 9 de septiembre de 2026, comparado con SPY, con comisiones de 10 puntos básicos y deslizamiento de 5 puntos básicos.
- Ejecutar backtest
- Explicar resultado

Audit:

- Spanish Quick take and Breakdown are accepted and persisted as es-419. All five Quick take references and twelve Breakdown references pass the retained-value check: the $1,000 seed, $100 monthly contribution, $2,300 total funded, $6,644 ending balance, $8,649 highest balance, $4,344 profit, 188.9% return, 12.1% benchmark return, 176.8 percentage-point gap, 42.1% drawdown and 85.4% annualized volatility agree within rounding.
- The Breakdown explicitly says the 42.1% investment decline excludes new deposits. This correctly distinguishes the flow-adjusted investment drawdown from nominal account value. It does not invent dated endpoints or a dollar loss for that event.
- The 18% company revenue-growth claim is supported by the retained Q4 2025 company-release result. The earlier English case cited 16% for Q3 2025; these concern different quarters and are not contradictory. The Q1 2026 22% growth and $258 million revenue figures are also directly present in the retained company source.
- The July 7, 2026 preliminary Q2 company update supports approximately 29% expected revenue growth and more than $800 million RPO. The draft accurately describes that as a historical company expectation announced within the tested window, not as an Argus forecast of the strategy.
- All three inline company-source URLs occur in the retained search results. The causal discussion is expressly framed as a reasonable interpretation rather than proof of every daily price move. The Sources panel contains the five actual metadata rows, separate from the three inline links; billing records three search invocations.
- Both frames compare the roughness of the ride with the market, and the Breakdown further says the measured worst drop was much more severe. The run retains no benchmark volatility, maximum drawdown or equity path, so those comparative risk claims are not established by the supplied run data. This does not make the correctly quoted DOCN risk values false.
- The explicit 10-basis-point fee and 5-basis-point slippage assumptions are retained in the run, but the frames do not explain their effect. This remains a depth limitation, not a required-mention failure. Quick take cost $0.00352745; Breakdown cost $0.01311; Q+B total $0.01663745.

**Quick take**

Source `llm_explain_stage`; fallback `false`; failure `None`; delivered draft **$0.00352745**, all frame attempts **$0.00352745**; source `755bfcaef0adeef7c5c8accee77a183f9864e547`.

> Comprar DOCN cada mes y mantener la posición durante este periodo terminó muy por encima de SPY: la estrategia obtuvo 188.9% frente a 12.1% del benchmark, con una diferencia de 176.8 pp. El intercambio fue una experiencia bastante más brusca: en el camino, la inversión llegó a caer 42.1% desde un máximo antes de cerrar con una ganancia de $4,344 sobre el dinero depositado.

[Response 111](evidence/model-result-readouts/app-demo-fixes/provider-response-111.json)

**Breakdown**

Source `llm_breakdown_stage`; fallback `false`; failure `None`; delivered draft **$0.01311**, all frame attempts **$0.01311**; source `755bfcaef0adeef7c5c8accee77a183f9864e547`.

> Entre el 10 de septiembre de 2025 y el 9 de septiembre de 2026, la estrategia compró DOCN de forma periódica: comenzó con $1,000 y añadió $100 cada mes. En total se aportaron $2,300. Al final, la cartera valía $6,644, por lo que el resultado vino principalmente del aumento de la inversión, no de los depósitos nuevos.
>
> Fue una experiencia con movimientos muy fuertes. La cartera llegó a un máximo de $8,649 y después terminó por debajo de ese nivel. En el retroceso más grande, el valor de las inversiones cayó 42.1%, sin contar los depósitos nuevos. La volatilidad anualizada fue de 85.4%, una señal de que mantener DOCN exigió atravesar variaciones mucho más bruscas que las de una inversión amplia de mercado.
>
> El contexto de DOCN ayuda a entender por qué el resultado fue tan excepcional y tan irregular. DigitalOcean reportó que sus ingresos del cuarto trimestre de 2025 crecieron 18% interanual y que la demanda de clientes de inteligencia artificial y empresas grandes estaba acelerándose ([resultados de 2025](https://investors.digitalocean.com/news/news-details/2026/DigitalOcean-Announces-Fourth-Quarter-and-Fiscal-Year-2025-Financial-Results/)). En el primer trimestre de 2026, los ingresos crecieron 22%, hasta $258 millones ([resultados del primer trimestre](https://investors.digitalocean.com/news/news-details/2026/DigitalOcean-Announces-First-Quarter-2026-Financial-Results/default.aspx)). Más adelante, la empresa comunicó que esperaba un crecimiento de ingresos de aproximadamente 29% en el segundo trimestre y contratos pendientes por más de $800 millones, impulsados por productos de inteligencia artificial ([actualización previa del segundo trimestre](https://investors.digitalocean.com/news/news-details/2026/DigitalOcean-Expects-to-Report-Record-Q2-2026-Results-with-RPO-to-Exceed-800M-Up-More-Than-10X-Year-Over-Year/default.aspx)). Es razonable interpretar que estas noticias ayudaron a impulsar DOCN, aunque no explican por sí solas cada movimiento diario de la acción.
>
> Frente a SPY, la diferencia fue enorme: la estrategia obtuvo 188.9% sobre las aportaciones, mientras el benchmark obtuvo 12.1%. La ventaja fue de 176.8 puntos porcentuales. En términos sencillos, mantener y comprar regularmente una sola empresa de crecimiento produjo un resultado histórico mucho mayor que mantener la referencia amplia, pero a cambio de una trayectoria bastante más accidentada y una caída máxima medida mucho más severa. Este resultado describe ese periodo concreto, no una expectativa para el futuro.

[Response 112](evidence/model-result-readouts/app-demo-fixes/provider-response-112.json)

Sources actually supplied to the panel (5, maximum five):

- [DigitalOcean (DOCN) Q4 2025 Earnings Transcript | The Motley Fool](https://www.fool.com/earnings/call-transcripts/2026/02/24/digitalocean-docn-q4-2025-earnings-transcript/) · 2026-02-24
- [DigitalOcean Announces Fourth Quarter and Fiscal Year 2025 ...](https://investors.digitalocean.com/news/news-details/2026/DigitalOcean-Announces-Fourth-Quarter-and-Fiscal-Year-2025-Financial-Results/) · 2026-02-24
- [DigitalOcean lifts outlook on strong 2025 profit | DOCN 8-K Filing](https://www.stocktitan.net/sec-filings/DOCN/8-k-digital-ocean-holdings-inc-reports-material-event-65a12bf27194.html) · 2026-02-24
- [Guidance](https://finsee.ai/earnings/docn/2025/q4/en/) · 2025-12-31
- [DigitalOcean (DOCN) Shares Drop -19% in 30 Days](https://tickeron.com/blogs/digitalocean-docn-shares-drop-19-in-30-days-profit-taking-after-a-strong-run-14545/) · 2026-07-08

Screenshots:

- [final-dca-es-breakdown.png](evidence/model-result-readouts/app-demo-fixes/final-dca-es-breakdown.png)
- [final-dca-es-card-and-quick-take.png](evidence/model-result-readouts/app-demo-fixes/final-dca-es-card-and-quick-take.png)
- [final-dca-es-sources-live.png](evidence/model-result-readouts/app-demo-fixes/final-dca-es-sources-live.png)
- [final-dca-es-sources-reloaded.png](evidence/model-result-readouts/app-demo-fixes/final-dca-es-sources-reloaded.png)
### SPY RSI (es-419)

Conversation `084c596a-e43b-4fda-a4aa-4e90c977d568`; run `185f3f58-bd0c-57ad-a649-d6941423c76a`.

User turns:

- Haz un backtest de SPY del 10 de septiembre de 2025 al 9 de septiembre de 2026 con $1,000. Usa RSI de 14 días: compra cuando caiga a 30 o menos y vende cuando suba a 70 o más. Sin comisiones ni deslizamiento.
- Ejecutar backtest
- Explicar resultado

Audit:

- Spanish Quick take and Breakdown are accepted and persisted as es-419. All four Quick take declared references and all seventeen Breakdown declared references pass. Returns 8.6% versus 16.9%, lag 8.3 percentage points, profit $86, ending/highest value $1,086, 4.8% maximum drawdown, 6.1% annualized volatility and Sharpe 1.4 match the saved run within rounding.
- There is one accepted arithmetic error in visible text: the Breakdown states a $51 loss from the drawdown high. The exact saved endpoints are $1,038.57 and $988.47, so the loss is $50.10, which rounds to $50 at whole-dollar precision. $51 results from subtracting the separately rounded display endpoints ($1,039 minus $988). The draft does not declare $51 in its references, so the reference check does not inspect that visible number.
- The drawdown dates, December 5, 2025 to March 30, 2026, are correct. The $1,169 benchmark ending-balance illustration is also correct: the same $1,000 seed at the stored 16.89% benchmark return equals $1,168.90. It is a historical arithmetic illustration, not a stored benchmark-equity endpoint or future forecast.
- The four executions are two entries and two exits. The Spanish wording uses four purchases-and-sales as a combined category and does not claim four completed trading cycles.
- The retained sources support the September record-high backdrop, the February rotation described in the March market brief, and March 30 market weakness with oil above $100. The explanation that trading protected part of the ride and missed part of the rebound remains a timing interpretation rather than a separately measured attribution result.
- The Reuters and Camden inline URLs exactly match retained search results. The AP/WTOP inline URL omits 'us-' from the retained article URL. Read-only web retrieval could open neither variant, so live reachability remains unverified, not a proven broken link. The actual panel contains five different metadata source rows; provider billing records three search invocations.
- Quick take cost $0.00351405; Breakdown cost $0.01336; Q+B total $0.01687405.

**Quick take**

Source `llm_explain_stage`; fallback `false`; failure `None`; delivered draft **$0.00351405**, all frame attempts **$0.00351405**; source `755bfcaef0adeef7c5c8accee77a183f9864e547`.

> Comprar y vender SPY siguiendo esta regla terminó con una ganancia de $86, pero quedó por debajo de comprar y mantener el benchmark: 8.6% frente a 16.9%. El intercambio fue claro: la estrategia atravesó una caída máxima de 4.8%, mientras que el benchmark obtuvo un resultado histórico mayor en este periodo.

[Response 119](evidence/model-result-readouts/app-demo-fixes/provider-response-119.json)

**Breakdown**

Source `llm_breakdown_stage`; fallback `false`; failure `None`; delivered draft **$0.01336**, all frame attempts **$0.01336**; source `755bfcaef0adeef7c5c8accee77a183f9864e547`.

> Entre el 10 de septiembre de 2025 y el 9 de septiembre de 2026, la estrategia trabajó con una sola aportación inicial de $1,000. No fue simplemente comprar SPY y mantenerlo: las señales de umbral RSI llevaron a 4 compras y ventas durante el periodo. En otras palabras, mantener esta estrategia implicó entrar y salir de SPY en distintos momentos, en vez de permanecer expuesto todo el tiempo.
>
> El entorno empezó siendo favorable para las acciones estadounidenses. Al inicio del periodo, el S&P 500 marcaba nuevos máximos mientras los inversionistas esperaban recortes de tasas de la Reserva Federal, según [Reuters](https://www.reuters.com/business/wall-street-indexes-notch-record-high-closes-investors-bet-rate-cut-2025-09-09/). Después llegaron más sobresaltos: preocupaciones por la concentración y las valuaciones de las grandes empresas tecnológicas, nuevas políticas comerciales, inflación todavía elevada y dudas sobre el crecimiento. Un resumen de mercado de marzo describió precisamente ese cambio, con una rotación desde tecnología hacia sectores más defensivos y cíclicos, además de incertidumbre por aranceles y política fiscal ([Camden National Bank](https://www.camdennational.bank/wealth/market-briefs/market-brief-march-2026)).
>
> La parte más difícil para esta cartera ocurrió del 5 de diciembre de 2025 al 30 de marzo de 2026. Desde un máximo de $1,039 bajó a $988, una caída de 4.8%. Eso representa una pérdida de $51 desde ese máximo antes de la recuperación. Las noticias de ese tramo apuntaron a una combinación de tensión geopolítica, petróleo más caro, expectativas de tasas altas y temor a una desaceleración económica. Associated Press reportó que el S&P 500 cerró el 30 de marzo en un nuevo mínimo del año mientras el petróleo superaba $100 y la incertidumbre sobre el conflicto con Irán pesaba sobre el mercado ([AP vía WTOP](https://wtop.com/world/2026/03/how-major-stock-indexes-fared-monday-3-30-2026/)).
>
> Luego el mercado se recuperó. Para el final de la prueba, el valor llegó a $1,086, que también fue el máximo de la cartera. En total, la estrategia ganó 8.6% sobre los $1,000 iniciales. El resultado fue relativamente menos brusco que una cartera con movimientos más amplios, con una volatilidad anualizada de 6.1% y un Sharpe de 1.4, aunque esas medidas no describen por sí solas cómo se sintió cada día.
>
> La comparación importante es que el benchmark, también basado en SPY, ganó 16.9%. La estrategia quedó 8.3 pp por debajo. La lectura más directa es que las entradas y salidas protegieron parte del recorrido durante los periodos difíciles, pero también dejaron pasar parte de la subida de SPY, especialmente porque el mercado terminó recuperándose después del mínimo de marzo. Así, la experiencia fue positiva en dinero al final, pero con un costo claro frente a simplemente mantener el benchmark: se terminó con $1,086 en vez de aproximadamente $1,169 sobre la misma base inicial.

[Response 120](evidence/model-result-readouts/app-demo-fixes/provider-response-120.json)

Sources actually supplied to the panel (5, maximum five):

- [How major US stock indexes fared Wednesday 9/9/2026](https://www.barchart.com/story/news/4522023/how-major-us-stock-indexes-fared-wednesday-9-9-2026) · 2026-09-09
- [S&P 500 Falls 0.48% to 7636.36 — Data Talk](https://www.morningstar.com/news/dow-jones/202609098736/sp-500-falls-048-to-763636-data-talk) · 2026-09-09
- [Stock Market News for Sep 9, 2026 - Zacks Investment Research](https://www.zacks.com/stock/news/2986777/stock-market-news-for-sep-9-2026) · 2026-09-10
- [Stock Market News From Sept. 9, 2026: Dow, S&P 500, Nasdaq Fall](https://www.barrons.com/livecoverage/stock-market-news-today-090926) · 2026-09-09
- [Market Brief: March 2026](https://www.camdennational.bank/wealth/market-briefs/market-brief-march-2026) · 2026-03-04

Screenshots:

- [final-rsi-es-breakdown.png](evidence/model-result-readouts/app-demo-fixes/final-rsi-es-breakdown.png)
- [final-rsi-es-card-and-quick-take.png](evidence/model-result-readouts/app-demo-fixes/final-rsi-es-card-and-quick-take.png)
- [final-rsi-es-sources-live.png](evidence/model-result-readouts/app-demo-fixes/final-rsi-es-sources-live.png)
- [final-rsi-es-sources-reloaded.png](evidence/model-result-readouts/app-demo-fixes/final-rsi-es-sources-reloaded.png)
### Supplement: DOCN buy and hold, latest wording check (en)

Conversation `19d76ad0-f502-48eb-a00a-556a964ff2a0`; run `67967fe7-e34c-5d90-8f4c-978e0a3ebf2b`.

User turns:

- Buy and hold DOCN from September 1, 2023 through September 9, 2026 with $1,000 starting capital. Compare with SPY, with no fees or slippage.
- Run backtest
- Explain result

Audit:

- This separate English normal-card case preserves the original English DOCN case and demonstrates the newer action wording: buying once and holding, with no recurring deposits. Both frames are accepted and persisted. Quick take adds the actual drawdown loss in money, information the compact card does not provide.
- The three Quick take and fifteen Breakdown declared references pass. Quick take also quotes undeclared $1,000 seed and $1,747/$963 endpoints; manual comparison confirms them. Its $784 loss correctly rounds the exact $783.76 chronological drawdown loss.
- The Breakdown contains a chronological error: it says the portfolio reached $6,784, then fell from $1,747 to $963 in the worst decline during February 18 to August 1, 2025. The stored global $6,784.14 peak occurs on June 15, 2026, after that drawdown. The individual values are correct, but the narrated order is wrong.
- The 2023 revenue-growth figure of 20%, 2025 Q2 revenue growth of 14%, and net-income growth of 93% have retained primary-source support. The stated 100% AI/ML growth appears in the retained secondary Investing.com account, but the linked company release describes more than doubling rather than exactly 100%; that is a precision and attribution caveat.
- All three inline URLs occur in retained search results. The source panel contains four actual metadata rows and billing records three search invocations. The Barchart comparison page is supporting market context only; its differently dated price-return table is not the owner of the saved 69.0% benchmark result.
- The explicit statement that benchmark volatility is not measured here is factually correct, but it leaks the writing brief’s silent accuracy instruction into visible prose. This is a writing-brief leak, not an internal schema-key leak. The company-news explanation remains inference, with the draft noting that a single announcement does not prove the entire move. Holding through recovery is a description of this historical strategy, not a recommended action.
- Quick take cost $0.00658195; Breakdown cost $0.01315; Q+B total $0.01973195. This normal-card path is separate from the earlier natural-docn-en text-follow-up route, whose two HTTP 400 ResultFollowupDraft attempts produced no new Breakdown.

**Quick take**

Source `llm_explain_stage`; fallback `false`; failure `None`; delivered draft **$0.00658195**, all frame attempts **$0.00658195**; source `755bfcaef0adeef7c5c8accee77a183f9864e547`.

> Buying DOCN once and holding it through this historical run turned $1,000 invested into $4,963, ahead of SPY’s 69.0% return. The tradeoff was a rough ride: the investment fell from $1,747 to $963 at its largest drawdown, a $784 loss before recovering.

[Response 132](evidence/model-result-readouts/app-demo-fixes/provider-response-132.json)

**Breakdown**

Source `llm_breakdown_stage`; fallback `false`; failure `None`; delivered draft **$0.01315**, all frame attempts **$0.01315**; source `755bfcaef0adeef7c5c8accee77a183f9864e547`.

> From September 1, 2023 through September 9, 2026, this test was a single purchase of DOCN followed by holding it, with no additional money added. The $1,000 contribution ended at $4,963, a total return of 396.3%. DigitalOcean benefited from a period of improving business results and growing interest in cloud and AI infrastructure. In early 2024, the company reported 2023 revenue growth of 20%, along with higher operating cash flow and adjusted EBITDA ([company results](https://investors.digitalocean.com/news/news-details/2024/DigitalOcean-Announces-Fourth-Quarter-and-Fiscal-Year-2023-Financial-Results/default.aspx)).
>
> Holding DOCN was far from smooth. The portfolio reached a high of $6,784, then fell from $1,747 before its worst decline to $963 at the bottom. That 44.9% drop lasted from February 18, 2025 to August 1, 2025. In practical terms, staying invested meant accepting a large temporary loss on the account statement without selling, and waiting for the value to recover. The 68.6% annualized volatility also shows that the path was unusually bumpy, although the test does not measure the benchmark's volatility here.
>
> The recovery was supported by stronger company updates later in 2025. DigitalOcean reported second-quarter revenue up 14%, net income up 93%, AI and machine-learning revenue growth of 100%, and raised its full-year revenue guidance ([company results](https://investors.digitalocean.com/news/news-details/2025/DigitalOcean-Announces-Second-Quarter-2025-Financial-Results/default.aspx)). Those results help explain why the stock regained ground, but they do not prove that any single announcement caused the entire move.
>
> Against SPY, the broad-market benchmark, DOCN's result was much stronger. SPY returned 69.0% over the same test, while DOCN returned 396.3%, a difference of 327.3 percentage points. The tradeoff was concentration and roughness: the single company produced far more growth in this historical window, but the ride included a deep drawdown that a broad index would not necessarily experience in the same way. Historical price records for SPY provide the benchmark context ([SPY performance history](https://www.barchart.com/etfs-funds/quotes/SPY/performance)).

[Response 133](evidence/model-result-readouts/app-demo-fixes/provider-response-133.json)

Sources actually supplied to the panel (4, maximum five):

- [DigitalOcean Announces Second Quarter 2026 Financial ...](https://investors.digitalocean.com/news/news-details/2026/DigitalOcean-Announces-Second-Quarter-2026-Financial-Results/default.aspx) · 2026-08-04
- [SPY Performance Report for SPDR S&P 500 ETF](https://www.barchart.com/etfs-funds/quotes/SPY/performance) · 2026-09-09
- [DigitalOcean Soars 28.88% on Earnings $360M Volume Ranks ...](https://www.ainvest.com/news/digitalocean-soars-28-88-earnings-360m-volume-ranks-338th-daily-trading-2508/) · 2025-08-05
- [DigitalOcean Q2 2025 slides: revenue growth accelerates, AI segment doubles](https://au.investing.com/news/company-news/digitalocean-q2-2025-slides-revenue-growth-accelerates-ai-segment-doubles-93CH-3959781) · 2025-08-05

Screenshots:

- [natural-docn-en-card-breakdown.png](evidence/model-result-readouts/app-demo-fixes/natural-docn-en-card-breakdown.png)
- [natural-docn-en-card-card-and-quick-take.png](evidence/model-result-readouts/app-demo-fixes/natural-docn-en-card-card-and-quick-take.png)
- [natural-docn-en-card-sources-live.png](evidence/model-result-readouts/app-demo-fixes/natural-docn-en-card-sources-live.png)
- [natural-docn-en-card-sources-reloaded.png](evidence/model-result-readouts/app-demo-fixes/natural-docn-en-card-sources-reloaded.png)

## All billed attempts, including earlier attempts

| Case tag | Attempts | Known billed USD |
| --- | ---: | ---: |
| docn-en | 6 | $0.04178105 |
| docn-en-final | 6 | $0.04171520 |
| dca-en | 9 | $0.04752490 |
| docn-en-verified | 6 | $0.02610790 |
| dca-en-verified | 9 | $0.03402735 |
| rsi-en | 19 | $0.10822427 |
| docn-es | 6 | $0.02659480 |
| panel-docn-en | 7 | $0.03222150 |
| final-docn-en | 6 | $0.03154700 |
| final-dca-en | 9 | $0.04662330 |
| final-rsi-en | 8 | $0.05569450 |
| final-docn-es | 6 | $0.03672530 |
| final-dca-es | 16 | $0.08818940 |
| final-rsi-es | 8 | $0.02783490 |
| natural-docn-en | 6 | $0.12511755 |
| natural-docn-en-card | 6 | $0.02955730 |

The `natural-docn-en` text follow-up took the ResultFollowupDraft route. Its two HTTP 400 drafts created no new Breakdown and did not replace the original DOCN readout. The separate `natural-docn-en-card` case above used the normal backtest card action.

HTTP and transport errors with unknown invoices: four HTTP failures and three canceled transport attempts.

- Attempt 27 (`docn-en-verified`), status `500`, schema `ResultBreakdownDraft`: [retained response](evidence/model-result-readouts/app-demo-fixes/provider-response-027.json).
- Attempt 61 (`docn-es`), status `400`, schema `ResultBreakdownDraft`: [retained response](evidence/model-result-readouts/app-demo-fixes/provider-response-061.json).
- Attempt 103 (`final-dca-es`), status `transport_error`, schema `ClarificationResponse`: no response body or invoice returned.
- Attempt 113 (`final-rsi-es`), status `transport_error`, schema `LLMAssetMentionExtraction`: no response body or invoice returned.
- Attempt 114 (`final-rsi-es`), status `transport_error`, schema `None`: no response body or invoice returned.
- Attempt 125 (`natural-docn-en`), status `400`, schema `ResultFollowupDraft`: [retained response](evidence/model-result-readouts/app-demo-fixes/provider-response-125.json).
- Attempt 126 (`natural-docn-en`), status `400`, schema `ResultFollowupDraft`: [retained response](evidence/model-result-readouts/app-demo-fixes/provider-response-126.json).

## Working state and canceled delivery

The first English RSI Breakdown finished at the provider after the browser reload canceled its app request. It was paid but not persisted or shown. The existing stale-turn timeout later exposed the stopped turn and typed Retry action; the retry delivered the recorded Breakdown. This is a delivery failure, not a rejected-model/template fallback.

- [pending-en-live.png](evidence/model-result-readouts/app-demo-fixes/pending-en-live.png): Single Working state before reload.
- [pending-en-reloaded.png](evidence/model-result-readouts/app-demo-fixes/pending-en-reloaded.png): Single Working state on reloaded reader.
- [pending-en-recovered.png](evidence/model-result-readouts/app-demo-fixes/pending-en-recovered.png): Existing 15-minute stale-turn recovery showed a stopped turn and Retry at approximately 06:15:20 UTC.
- [pending-es-live.png](evidence/model-result-readouts/app-demo-fixes/pending-es-live.png): Single Working state during original stream.
- [pending-es-reader-settled.png](evidence/model-result-readouts/app-demo-fixes/pending-es-reader-settled.png): Completed answer on reloaded reader; not a pending-state screenshot.
- [pending-es-reloaded-reader.png](evidence/model-result-readouts/app-demo-fixes/pending-es-reloaded-reader.png): Actual single Working state on the reloaded DCA reader, before the answer settled.

## Release context

Verified checkpoint at `755bfcaef0adeef7c5c8accee77a183f9864e547`: [completed clean Codex review](https://github.com/lagarcess/argus/pull/588#issuecomment-5630283870), zero unresolved threads. Modularity passed on simulated merged tree `6724ac742bdb3e566d5a4f7ffb6d01a523732e8b`, combining this head with integration `46d43c1d`; this was not an actual integration merge. CI remained held by the interpreter prompt fingerprint check. This report makes no READY claim.

## Limits of this evidence

- No paid rerun was performed by the report audit.
- Panel sources are the exact persisted metadata.research.sources, with the application cap of five; they are not reconstructed from inline prose or the full provider result set.
- Run-reference checks do not prove every qualitative claim, causal explanation, or source URL. Manual caveats are reported per case.
- Historical company guidance described as a past event is distinct from a forecast of the backtest outcome.

This local demo does not replace the held interpreter prompt fingerprint gate or hosted-preview and deployment acceptance. The verified clean Codex review remains recorded above; CI is not fully green, and this report makes no READY claim.
