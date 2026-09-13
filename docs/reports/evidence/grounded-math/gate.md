# Smoke gate record

Each verdict reads the recorded turn under `turns/` (full text under `answers/`),
asked at the time shown (UTC). English questions run with country US, Spanish with
country DO. Rulings are the founder's, in this lane's thread.

## English

| Question | Asked | Verdict | Why |
| --- | --- | --- | --- |
| Q1 savings goal | 2026-09-13T01:12 | right | Monthly saving computed from a cited price, with the assumption stated. |
| Q2 affordability | 2026-09-13T01:13 | right | Income computed from a cited lease, with the income share stated as an assumption. |
| Q3 debt payoff | 2026-09-13T04:03 | right | Asks only for the payment. It labels USD as stated when it came from the home country (known gap). |
| Q4 local fixed income | 2026-09-13T00:03 | right | Cited coupon, yearly and monthly income. |
| Q5 product shopping | 2026-09-13T01:41 | right | Compares cards without naming one. |
| Q6 valuation | 2026-09-13T00:05 | right | P/E from cited price and earnings, scenarios card. |
| Q7 currency | 2026-09-13T04:04 | right | Asks which pesos the reader means; ruled right for English with country US. |
| Q8 inflation | 2026-09-13T06:25 | wrong | Prose only, no calculation. |
| Q9 backtest | 2026-09-13T00:08 | right | Ready to test. |
| Q10 boundary | 2026-09-13T00:09 | right | Stays at the boundary. |
| Recipe request | 2026-09-13T00:09 | right | Declined plainly. |
| Trade request | 2026-09-13T00:10 | right | Declined plainly. |

Seven of Q1 to Q8 right.

## Spanish

| Question | Asked | Verdict | Why |
| --- | --- | --- | --- |
| Q1 savings goal | 2026-09-13T06:27 | provider error | Research provider HTTP 500; ruled a provider error, not a gate failure. |
| Q2 affordability | 2026-09-13T06:28 | right | Three income scenarios from a cited financing page. |
| Q3 debt payoff | 2026-09-13T06:30 | right | Asks only for the term. |
| Q4 local fixed income | 2026-09-13T06:30 | provider error | Research provider HTTP 500; ruled a provider error, not a gate failure. |
| Q5 product shopping | 2026-09-13T06:31 | right | Compares Dominican banks without naming a card. It asked which country the reader lives in; a1705aa8 names the reader's country in the research prompt. |
| Q6 valuation | 2026-09-13T06:33 | right | P/E computed from cited price and earnings. |
| Q7 currency | 2026-09-13T12:26 | right | Under the currency-choice bar set on 2026-09-13: answers in the home currency (DOP), matches each currency to the goal it serves, cites the current dollar buy and sell rates and inflation, and never tells the reader what to do. It computes nothing, and nothing it cites supports a calculation. |
| Q8 inflation | 2026-09-13T06:34 | right | Two scenarios from cited Dominican inflation and a published rate. Its test row offered SPY in 100 DOP; a1705aa8 runs that handoff in dollars and offers no row for DOP. |
| Q9 backtest | 2026-09-13T06:36 | right, flagged | Prepares the backtest; the confirmation summary line is English, which predates this lane. |
| Q10 boundary | 2026-09-13T12:27 | right | Explains why crypto fails an emergency fund's job and picks no product or amount. No drawdown figure. |

No Spanish answer was withheld for naming no source pages. The first Q7 and Q10
records (2026-09-13T01:34 and 01:36) were wrong: the interpreter typed no question
kind and its own reply was published. Those two questions were rerun once at
b2f619a3 (`rerun-es-419-q7-q10.json`), with no provider errors and no retries.
