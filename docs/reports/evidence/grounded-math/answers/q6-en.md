# q6 (en)

**Asked:** Is Apple expensive at this P/E?

**Seconds to first answer:** 104.28. **Seconds to final answer:** 104.28.

**Yes, relative to Apple’s recent history, its valuation is expensive.** As of 2026-09-11, Apple’s trailing P/E was 38.27x, versus its five-year median of 30.72x; that means investors were paying a historically elevated price for each dollar of trailing earnings.

### What the P/E says

| Measure | Published figure | Interpretation |
|---|---:|---|
| Trailing P/E, 2026-09-11 | 38.27x | The market price represented more than thirty-eight times trailing earnings. |
| Five-year median P/E | 30.72x | Apple’s current multiple was above its own recent historical midpoint. |
| Trailing diluted EPS | $8.73 per share | The earnings base underlying the valuation analysis. |

This supports calling Apple expensive **relative to its own history**, not proving that the shares are absolutely overvalued. P/E does not determine intrinsic value by itself: a higher multiple can persist if future earnings growth justifies it, while slower-than-expected growth or a lower valuation multiple can reduce returns.

### Scenario framework

The scenario calculation starts with Apple’s current market price of USD 332.25 and trailing diluted EPS of USD 8.73. It uses the published three-year growth rate of 4.7% as the base growth input and the published five-year median P/E of 30.72x as the low multiple.

For sensitivity, not forecasts, the other assumptions are:

- Low earnings growth: 0%
- High earnings growth: 10%
- Base multiple: 38.27x
- High multiple: 45x
- Holding period: 5
- Illustrative investment: USD 10,000

The calculation produces low, base and high implied future prices and annualized returns rather than presenting one outcome as Apple’s future. The key question is whether Apple can deliver enough earnings growth to support a P/E materially above its recent median.

## Sources

- Apple Inc. R (APC8.DU) Q3 FY2026 earnings call transcript (finance.yahoo.com, 2026-09-04): https://finance.yahoo.com/quote/APC8.DU/earnings/APC8.DU-Q3-2026-earnings_call-658553.html/
- Apple's Strongest June Quarter Ever: $109.4B Revenue ... (beancount.io, 2026-08-22): https://beancount.io/blog/2026/08/22/apple-fy2026-q3-earnings-analysis
- Apple Q3 2026 Earnings: Record Quarter, Worst Reaction (www.money365.market, 2026-08-16): https://www.money365.market/articles/apple-q2-2026-earnings-analysis
- Apple (AAPL) Financials — Revenue $109.4B in Q3 FY2026 (www.thetrading.tools, 2026-08-14): https://www.thetrading.tools/financials/aapl
- Apple (AAPL) Q3 Fiscal 2026 Earnings Recap (www.webull.com, 2026-08-24): https://www.webull.com/blog/243-Apple-AAPL-Q3-Fiscal-2026-Earnings-Recap

## Next steps

- calculation_market_counterfactual: Test Apple (AAPL) with 10,000 USD over the last 5 years
- research_test_single: Test Apple (AAPL) over the last 3 years
- Question: How much earnings growth would justify Apple’s current P/E?
- Question: How does Apple’s P/E compare with other large technology companies?
- Question: What happens if Apple’s P/E returns to its historical median?

## Calculation

- valuation_scenarios: succeeded
- Result value_at_horizon_base: 12651.66
- Input symbol: AAPL (user)
- Input price: 332.245 (market_data)
- Input per_share: 8.73 (page)
- Input growth_low_pct: 0.0 (assumption)
- Input growth_base_pct: 4.7 (page)
- Input growth_high_pct: 10.0 (assumption)
- Input multiple_low: 30.72 (page)
- Input multiple_base: 38.27 (page)
- Input multiple_high: 45.0 (assumption)
- Input horizon_years: 5 (assumption)
- Input amount: 10000.0 (assumption)
