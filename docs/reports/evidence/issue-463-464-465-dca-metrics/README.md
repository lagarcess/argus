# DCA metrics arithmetic: before/after evidence (#463, #464, #465)

Deterministic offline proof for the DCA metrics lane. `dca_proof.py` runs two
DCA scenarios through the production `compute_alpha_metrics` path with
injected bars (no provider, no network, no paid calls):

1. **Audit example**: the #456 audit report's D1 worked example. Nominal
   equity `[100, 80, 180, 144]`, deposits `[100, 0, 100, 0]`, zero costs.
   The asset loses 20% twice; the run loses 28% of contributed cash.
2. **Six-month monthly DCA**: 124 business days of seeded random-walk
   prices, six $10,000 monthly deposits, 10 bps fees, 5 bps slippage.

`dca_metrics_before.json` was captured at the lane base
`eaf5d52b9f29266ee98af9458d061ad04d577e49`; `dca_metrics_after.json` at the
lane head.

## Audit example, side by side

| Metric | Before | After | Direction and why |
| --- | ---: | ---: | --- |
| Total return | -28.0% | -28.0% | Unchanged arithmetic; the card now labels it "Return on contributions" under key `contribution_return_pct`, and the metrics block carries `return_basis: "contributions"` (#464). |
| Annualized return | -100.0% | -100.0% | Same number here by coincidence of the deep loss; the formula changed from fixed-capital compounding of the contribution ratio to a money-weighted dated-cash-flow rate (#465). |
| Max drawdown | -20.0% | -36.0% | Deeper. The second deposit created a nominal peak that hid the true peak-to-trough loss; the flow-adjusted wealth index (1.0, 0.8, 0.8, 0.64) restores it (#463). |
| Volatility | 1,108.14% | 183.30% | Lower. The +125% deposit bar was never a return; dispersion now comes only from the two real -20% moves (#463). |
| Sharpe | +4.83 | -13.75 | Sign flip. A strategy that lost money no longer reports a strongly positive risk-adjusted return; the deposit bar was carrying the mean (#463). |
| Win rate / profit factor | null | null | Already null for DCA since #487 (closed-trade definition); unchanged. |
| Peak / lowest nominal value | 180 / 80 | 180 / 80 | Unchanged on purpose: nominal dollars own the chart and value range. |

## Six-month monthly DCA, side by side

| Metric | Before | After | Direction and why |
| --- | ---: | ---: | --- |
| Total return | +6.65% | +6.65% | Unchanged arithmetic, relabelled as above (#464). |
| Annualized return | +14.04% | +25.19% | Higher here. Fixed-capital compounding assumed all $60,000 was invested for the whole window; the money-weighted rate credits each deposit only for the time it was actually exposed, and later deposits had less time to earn the same gain (#465). The error has no fixed direction: in the audit's refutation example the old formula understates instead. |
| Max drawdown | -6.36% | -8.05% | Deeper. Monthly deposits no longer refill the nominal curve and dilute the drawdown (#463). |
| Volatility | 161.30% | 18.31% | Lower, and now plausible for a ~1.2%-daily-sigma equity series; the six deposit jumps are gone from the return series (#463). |
| Sharpe | +2.84 | +1.09 | Lower. The deposit bars inflated both mean and the ratio; what remains is the asset's real risk-adjusted performance (#463). |

Focused suite: `tests/domain/test_dca_flow_adjusted_metrics.py` derives every
expectation from prices and cash flows alone, including a hypothesis property
over arbitrary contribution schedules proving no schedule can enter the
flow-adjusted return series.
