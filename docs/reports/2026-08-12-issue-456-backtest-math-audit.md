# Issue #456: full backtest math audit

**Audit date:** 2026-08-12

**Exact base:** `8025672924d1c74eb80cc926c72b5d8574b613d7`

**Lane rule:** audit only. No production source was changed.

**Verdict:** seven confirmed defects, two refuted leads, and four new invariant tests for behavior that is correct.

## Executive result

Argus gets the basic cash arithmetic right: ending value, fixed-capital total return, DCA contributed cash, profit, same-schedule DCA benchmark capital, fill count, modeled-cost return drag, and nominal portfolio value extrema all reconcile independently.

The risk and efficiency layer is not trustworthy end to end. DCA contributions are treated as investment performance, win rate and profit factor are bar-direction statistics rather than closed-trade statistics, annualization ignores asset class and the real exchange calendar, and first-bar execution costs are absent from drawdown and the return series. An additional DCA benchmark defect executes contributions at forward-filled stale prices when the benchmark has an accepted interior gap.

The seven defect workstreams are:

| ID | Confirmed defect | Affected claims |
| --- | --- | --- |
| D1 | DCA cash contributions are included in period returns | max drawdown, volatility, win rate, profit factor, Sharpe |
| D2 | DCA money-on-money return is exposed as the same `total_return_pct` used for lump-sum time return | total return and cross-template comparisons |
| D3 | DCA money-on-money return is annualized with a fixed-capital compounding formula | annualized return |
| D4 | Static, asset-blind annualization factors disagree with live bars and the real exchange calendar | annualized return, volatility, Sharpe |
| D5 | Win rate and profit factor use positive and negative bars, not closed-trade P&L | win rate, profit factor |
| D6 | The metric series omits the pre-trade capital baseline and inserts an artificial zero return | max drawdown, volatility, Sharpe, win rate, profit factor |
| D7 | Accepted missing benchmark bars become stale-price DCA fills | benchmark return and benchmark delta |

Issue links are recorded in [Filed issues](#filed-issues).

### Reach and priority

- **#466 (D4) and #467 (D5) affect all six templates.** Asset/calendar-blind annualization changes annual return, volatility, and Sharpe wherever those metrics are produced. Bar-based win rate and profit factor also have the wrong meaning for every template, even when the main card hides them. These are cross-template fixes and should not wait behind the DCA-only cluster.
- **#468 (D6) is also cross-template, with uneven severity.** The artificial first zero return enters every template's metric series. The missing first-fill cost is directly reachable for buy-and-hold, DCA, and any generic signal rule that enters on the first bar.
- **#463, #464, #465, and #469 are DCA-specific.** They cover external cash-flow contamination, return-contract meaning, DCA annualization, and stale-price DCA benchmark fills.

### Spot-check lead summary

Leads 2 and 5 were refuted. Lead 2 is not reachable because the DCA strategy and benchmark receive the same entry mask, contribution amount, aligned index, fee rate, and slippage rate, so their invested-capital denominators are equal. Lead 5 is wrong because the benchmark runs DCA on that same schedule; it is not a lump-sum benchmark. Lead 3 still found a real formula defect, but its claim that the bias is always upward was also refuted: the invalid annualization can overstate or understate the investor's return.

## Audit controls

- The checkout was a clean detached `HEAD` at the exact requested base. Both local and remote-tracking `codex/private-alpha-next` resolved to the same SHA when the lane began.
- Python was the repository-pinned `3.10.20`.
- Production truth came from [`.github/private-alpha-release-profile.json`](../../.github/private-alpha-release-profile.json): the API explicitly sets `ARGUS_MARKET_DATA_PROVIDER_MODE=live_provider` and `ARGUS_ENABLE_EXECUTION_REALISM=true`; the workflow sets `live_provider`, and the execution-realism kill switch defaults on when unset.
- The audit process set those two values only in its own process. It did not edit `.env` or `web/.env.local`.
- The six-template live matrix used AAPL against SPY, 2025-01-02 through 2025-06-30, daily bars, $10,000 capital, 10 bps fees, and 5 bps slippage. The live provider returned 122 observations for each asset and the real Alpaca calendar returned the same 122 sessions.
- No hosted workflow, paid Render task, trade, order, deploy, or production write was performed. The provider calls were read-only market-data calls through the production provider path.
- All expected values in the focused tests were derived independently from the price and cash-flow series. No test calls a metric helper to compute its expected value.

## Templates enumerated from code

`ALLOWED_TEMPLATES` is derived in [`capability_registry.py`](../../src/argus/domain/capability_registry.py) from executable capabilities plus the generic execution template. At the audited SHA it contains exactly:

1. `buy_and_hold`
2. `buy_the_dip`
3. `dca_accumulation`
4. `moving_average_crossover`
5. `rsi_mean_reversion`
6. `signal_strategy`

The signal definitions audited from [`signals.py`](../../src/argus/domain/backtesting/signals.py) were:

| Template | Executed rule in the live matrix |
| --- | --- |
| `buy_and_hold` | Buy at the first bar and do not exit. |
| `buy_the_dip` | Enter after a close-to-close fall of at least 3%; exit five bars after an entry signal. |
| `dca_accumulation` | Contribute on the first observed session of each month. |
| `moving_average_crossover` | Enter on the SMA20 crossing above SMA50; exit on the inverse cross. |
| `rsi_mean_reversion` | RSI14 entry at or below 30; exit at or above 55. |
| `signal_strategy` | Generic rule spec: close above EMA20 to enter, close below EMA20 to exit. |

The draft templates `momentum_breakout` and `trend_follow` are not members of `ALLOWED_TEMPLATES` and were not audited as runnable templates.

## The five spot-check leads, first

### 1. Contribution days may count as performance

**Confirmed.** [`_compute_metrics_from_equity`](../../src/argus/domain/backtesting/metrics.py) calculates `strategy_equity.pct_change().fillna(0)` without subtracting external cash flows. [`_dca_equity_curve`](../../src/argus/domain/backtesting/execution.py) adds shares bought with every contribution directly to nominal equity. A contribution step is therefore a positive return.

The live monthly DCA lost 8.42% of contributed capital but reported 177.89% volatility, 51% win rate, profit factor 3.25, and Sharpe 2.61. Those values cannot describe the investment performance of a strategy that lost money over the same window. Max drawdown is also affected because new contributions create nominal peaks and dilute later drawdowns. This is D1.

### 2. One denominator may serve two capital streams

**Refuted for every reachable DCA run at this SHA.** [`runner.py`](../../src/argus/domain/backtesting/runner.py) passes the same entry mask, contribution amount, aligned index, fee rate, and slippage rate into both DCA curves. Both invested-capital values are therefore equal. `max(strategy_capital, benchmark_capital)` is redundant and fragile, but it does not currently change either result.

Independent check: two $1,000 contributions at bars 1 and 3, with 10 bps fees and 5 bps slippage, produced $2,000 invested on each side. Strategy prices `100, 110, 90` ended at `$1,897.15`, or `-5.14%`. Benchmark prices `100, 105, 95` ended at `$1,947.08`, or `-2.65%`. The delta was `-2.50` percentage points. The invariant is pinned in the focused test file.

### 3. Annualizing a contribution-weighted return overstates it

**The invalid formula is confirmed; the claimed direction is refuted.** DCA annualization applies a fixed-capital compounding formula to a simple ending-value-over-total-contributions ratio. That is not a time-weighted or money-weighted annual return.

The bias is not always upward. If $100 grows to $110 and another $100 arrives at the end of a one-year window, ending value is $210. Simple return on $200 contributed is 5%, so Argus annualizes it to 5%. The money-weighted annual return is 10%, because only the first $100 was exposed to the gain. In this case Argus understates it. This is D3.

### 4. Simple contribution return is not comparable with lump-sum total return

**Confirmed as a metric-contract defect.** The DCA arithmetic is a valid simple return on contributed cash, but the same key and card label, `total_return_pct` / “Total return,” means something different for fixed-capital templates. Two DCA runs that each contribute $200 and end at $220 both print 10%, whether the cash was invested for five years or one month. A $200 lump sum ending at $220 also prints 10%, although its exposure is different. This is D2.

### 5. The DCA benchmark may run a lump-sum strategy

**Refuted.** The benchmark receives the same DCA entries, contribution amount, fee rate, and slippage rate as the strategy. In the two-contribution example above, the DCA benchmark return was `-2.65%`; a lump-sum benchmark under the same costs would have been `-5.14%`. The benchmark is therefore DCA, not lump sum.

For the five non-DCA templates, the benchmark is intentionally buy-and-hold with the same starting allocation and cost rates. That is a standard opportunity-cost benchmark, although the card could state “buy-and-hold benchmark” more explicitly. No math defect was filed for that wording.

## Formula and assumption audit

Production uses the equity path for every audited run with nonzero modeled costs. DCA uses that path regardless of costs. Let:

- `E[t]` be nominal strategy portfolio equity at bar `t`;
- `B[t]` be nominal benchmark equity;
- `C` be initial capital for fixed-capital templates or total contributed cash for DCA;
- `r[t] = pct_change(E)[t]`, with the first missing value replaced by zero;
- `K` be `_periods_per_year(timeframe)`;
- `N` be the number of bars; and
- `F` be executed fill count, except DCA where it is buy-fill count.

The runner applies these formulas once per symbol and again to the summed aggregate equity. The assumptions and verdicts below therefore apply to both stored levels for every template.

| Metric | Formula as implemented | Assumption needed | Does production satisfy it? | Verdict |
| --- | --- | --- | --- | --- |
| `total_return_pct` | `(E[last] / C - 1) * 100` | `C` is one fixed capital base, or the metric is explicitly named as simple return on contributions. | Yes for fixed-capital templates. DCA uses total contributions but presents the result as the same total-return concept. | **Pass** for five fixed-capital templates. **Fail** for DCA semantics, D2. |
| `benchmark_return_pct` | `(B[last] / C - 1) * 100` | Benchmark uses the same capital schedule and valid prices. | Same schedule and capital hold. Interior missing bars can create stale-price DCA fills. | **Pass** except DCA with accepted missing benchmark bars, D7. DCA label semantics also inherit D2. |
| `delta_vs_benchmark_pct` | `strategy_return_pct - benchmark_return_pct` | Both returns use compatible capital/time semantics and valid prices. | Yes for non-DCA. DCA capital schedules match, but D2 and D7 can invalidate the inputs. | **Pass** as subtraction; **qualified/fail** when either DCA input is invalid. |
| `profit` | `E[last] - C` | `C` includes every external contribution and no withdrawal is omitted. | Yes. DCA `C` is contribution amount times buy fills; fixed-capital `C` is starting capital. | **Pass.** |
| `annualized_return_pct` | `((1 + total_return) ** (K / N) - 1) * 100`; for `N <= 1`, return total return | Return is a fixed-capital compound return; `N/K` is the true elapsed years. | No for DCA. No for crypto/FX daily bars or equity intraday bars. It also counts bars rather than return intervals. | **Fail**, D3 and D4. |
| `max_drawdown_pct` | `min(E / cumulative_max(E) - 1) * 100` | Equity is flow-adjusted and begins at the pre-trade capital baseline. | No for DCA cash flows. No when a first-bar fill incurs costs, because the series begins after that cost hit. | **Fail** on reachable paths, D1 and D6. |
| `volatility_pct` | sample standard deviation of `r` times `sqrt(K) * 100` | `r` contains only investment returns, has no artificial observation, and `K` matches the market/timeframe. | DCA includes contributions; the first bar is an inserted zero; `K` is asset-blind. | **Fail**, D1, D4, D6. |
| `win_rate` | fraction of nonzero `r` values that are positive | The product intends “positive active-bar rate,” not winning closed trades. | No. Product guidance says win rate is meaningful only with closed trades, while this formula does not read trades. | **Fail**, D5. DCA also inherits D1. |
| `total_trades` | count of executed ledger fills; DCA counts only buy fills | “Trade” means an executed fill, not a completed round trip. | Yes under the current fill-ledger contract. | **Pass**, with a naming caveat. |
| `profit_factor` | `sum(positive r) / abs(sum(negative r))`; returns 10 if gains exist with no losses, otherwise 0 | Product intends a bar-return gain/loss ratio and accepts an arbitrary finite cap. | No. Conventional profit factor uses closed-trade gross P&L, and 10 is not derived from the run. | **Fail**, D5. DCA also inherits D1. |
| `sharpe_ratio` | `mean(r) / sample_std(r) * sqrt(K)`; returns 0 for zero/undefined standard deviation | Raw strategy returns are flow-free, the cash/risk-free return is zero, and `K` is correct. | The simulator models idle cash at zero, so the zero-cash convention is internally consistent. The return series and `K` assumptions fail. | **Fail** on DCA and affected calendars, D1/D4/D6. Zero is an explicit sentinel for no variation. |
| benchmark comparison claim | `matched` when `abs(delta) < 0.05`, otherwise `beat` or `lagged` from sign | Delta is valid; a 0.05 percentage-point tolerance is accepted product policy. | The transformation is correct, but it inherits invalid DCA inputs. | **Pass** as a derived claim; **qualified** by D2 and D7. |

### Supplementary reported numbers

| Number | Formula | Verdict |
| --- | --- | --- |
| Ending value on the card | fixed capital or reconstructed DCA contributions plus `profit`, rounded to whole dollars | **Pass.** It reconciles to final nominal equity, subject only to display rounding. |
| `portfolio_value_range.peak_value` / `lowest_value` | maximum/minimum nominal aggregate equity close | **Pass as nominal dollars.** For DCA it intentionally includes contribution steps and must not be interpreted as performance. |
| Chart equity values | sum of per-symbol nominal portfolio equity after index alignment | **Pass as nominal dollars.** DCA contribution jumps are correct chart cash values but are not valid period returns. |
| `fee_bps` / `slippage_bps` | configured cost rates echoed from the executed realism settings | **Pass.** |
| `gross_total_return_pct` | rerun the same signals with zero modeled costs | **Pass**, while inheriting DCA's D2 return semantics. |
| `net_total_return_pct` | executed total return with configured costs | **Pass**, while inheriting D2. |
| `return_drag_pct` | gross return minus net return, in percentage points | **Pass.** The independent fee-exceeds-gain example reconciled to 2.96 points. |
| Benchmark cost treatment | same fee and slippage rates passed to the benchmark | **Pass.** “Same modeled costs” means the same per-fill rates, not the same dollar cost or fill count. |

## Independent worked arithmetic

### Fixed-capital example, applicable to all five non-DCA templates

Take `C = $1,000`, strategy equity `[1000, 1100, 990]`, and benchmark equity `[1000, 1050, 1050]`. The implemented return series is `[0, +0.10, -0.10]`.

- Total return: `990 / 1000 - 1 = -1.00%`.
- Benchmark return: `1050 / 1000 - 1 = +5.00%`.
- Delta: `-1.00% - 5.00% = -6.00` percentage points.
- Profit: `$990 - $1,000 = -$10`.
- Annualized return as implemented: `(0.99 ** (252 / 3) - 1) * 100 = -57.01%`. This reproduces the code but also shows the unstable bar-count annualization in D4.
- Max drawdown: the largest peak-to-trough fall is `$1,100` to `$990`, or `-10.00%`.
- Volatility as implemented: sample standard deviation of `[0, .10, -.10]` is `.10`; `.10 * sqrt(252) * 100 = 158.75%`. Using only the two actual return intervals gives 224.50%, proving the artificial-zero effect in D6.
- Win rate as implemented: one positive nonzero bar out of two, or `50%`.
- Profit factor as implemented: `.10 / .10 = 1.00`.
- Sharpe as implemented: mean return is zero, so Sharpe is `0.00`.
- If the execution ledger contains one open and one close fill, total trades is `2`.
- Nominal range is `$990` to `$1,100`.

The formulas do not depend on which of the five non-DCA templates produced the equity and fills. Template differences only determine when the fills and equity changes occur.

### DCA contribution example

Use nominal DCA equity `[100, 80, 180, 144]` with external contributions `[100, 0, 100, 0]`.

- Total contributed cash is `$200`; ending value is `$144`; simple contribution return is `144 / 200 - 1 = -28%`; profit is `-$56`.
- Raw equity returns used by Argus are `[0, -20%, +125%, -20%]`.
- Argus max drawdown is only `-20%`, because the second contribution creates a new nominal peak. Cash-flow-adjusted wealth is `[1.00, .80, .80, .64]`, whose drawdown is `-36%`.
- Argus volatility is `1,108.14%`, win rate is `33.33%`, profit factor is `1.25 / .40 = 3.125`, and Sharpe is `4.83`.
- Those four positive-looking efficiency/risk claims coexist with a `-28%` simple return and a `-36%` flow-adjusted return. The contribution, not performance, supplies the positive bar.

This is D1. It applies only to DCA, but it affects every DCA cadence and every supported asset class.

### Closed-trade example

One position buys at 100, passes through 80, and closes at 110. The completed trade wins 10%, so closed-trade win rate is 100%. There are no losing trades, so conventional trade profit factor is infinite or undefined.

Bar returns are `-20%` and `+37.5%`. Argus reports a 50% win rate and profit factor `37.5 / 20 = 1.875`. The current values describe bar directions, not the closed trade. This is D5.

### First-fill cost example

Start with $1,000 at a flat price of 100, charge 2% fees and 1% slippage, then buy on the first bar. Shares are:

`1000 / (100 * 1.01 * 1.02) = 9.706853`

Final marked equity is `$970.69`, total return is `-2.93%`, and profit is `-$29.31`. Argus correctly reports those three values and a 2.93-point cost drag. It reports max drawdown `0%`, volatility `0%`, Sharpe `0`, win rate `0`, and profit factor `0` because the equity series starts at `$970.69` and remains flat. The pre-trade `$1,000` baseline is absent. This is D6.

### Asset/calendar annualization examples from the live provider

- BTC daily, 2025-01-02 to 2025-06-30: 180 observations, total return `10.45%`. Argus reported `14.93%`, exactly the 252-bar formula. A 365-bar calculation is `22.33%`; actual elapsed time gives `22.48%`.
- EURUSD daily over the same dates: 180 observations, total return `14.66%`. Argus reported `21.11%`; 365 bars gives `31.97%`; actual elapsed time gives `32.20%`.
- AAPL hourly, 2025-01-02 to 2025-02-28: 289 AAPL observations across real equity sessions, total return `-2.37%`. Argus reported `-51.73%` because it assumed 8,760 hourly equity bars per year. A 6.5-hour by 252-session factor gives about `-12.71%`; elapsed time gives `-14.25%`.

These are live-provider reproductions of D4, not synthetic estimates.

### Missing benchmark bar example

Five real weekday sessions used daily DCA contributions of $100. Strategy data had all five bars. The benchmark had 4 of 5 bars, exactly the accepted 80% coverage, with observed prices `[100, 100, missing, 200, 200]`. The independent true-price case uses 200 on the missing third session.

With 10 bps fees and 5 bps slippage:

- Argus forward-filled 100 for the missing contribution-day price and reported benchmark return `59.76%`, ending at `$798.80` on `$500` contributed.
- Buying at the independent true price of 200 ends at `$698.95`, or `39.79%`.
- The stale fill overstates the DCA benchmark by `19.97` percentage points.

Dataset evidence for the accepted synthetic coverage case: `sha256:7ef23f663e85b880cea2bf386e9347b0cc45244713b3f9d133341510f44ed1fe`. This is D7.

## Per-template verdicts

| Template | Production metric path | Benchmark actually run | Correct invariants | Defects that apply | Overall |
| --- | --- | --- | --- | --- | --- |
| `buy_and_hold` | Equity path because modeled costs are nonzero | One buy-and-hold benchmark entry with the same rate assumptions | ending value, total return, benchmark return, delta, profit, one buy fill, gross/net/drag, nominal range | D4; D5 in persisted efficiency facts; D6 always because the strategy enters on bar 1 | **Fail** |
| `buy_the_dip` | Equity path | Buy-and-hold benchmark | cash arithmetic, benchmark arithmetic, profit, fill count, cost drag, nominal range; first entry occurs after bar 1 so its cost is visible in the equity change | D4 and D5; artificial first zero from D6 still biases period statistics | **Fail** |
| `dca_accumulation` | Equity path by definition | DCA benchmark on the same entries, amounts, and cost rates | total contributed cash, ending value, profit, same capital denominator, buy-fill count, gross/net/drag, nominal range | D1, D2, D3, D4, D5, D6, D7 | **Fail, highest risk** |
| `moving_average_crossover` | Equity path | Buy-and-hold benchmark | cash arithmetic, benchmark arithmetic, profit, fill count, cost drag, nominal range; SMA warmup prevents a first-bar fill | D4 and D5; artificial first zero from D6 biases period statistics | **Fail** |
| `rsi_mean_reversion` | Equity path | Buy-and-hold benchmark | cash arithmetic, benchmark arithmetic, profit, fill count, cost drag, nominal range; indicator warmup normally prevents a first-bar fill | D4 and D5; artificial first zero from D6 biases period statistics | **Fail** |
| `signal_strategy` | Equity path | Buy-and-hold benchmark | cash arithmetic, benchmark arithmetic, profit, fill count, cost drag, nominal range | D4 and D5; D6 is fully reachable because a valid rule can enter on bar 1 | **Fail** |

## Live six-template evidence matrix

All rows use the same live AAPL/SPY dataset and the real 122-session exchange calendar. Dataset ID: `sha256:b1c606d3d6ca4c8351fb797b7cd47e553a85da2d1c60987c7d924c94a4a81e93`. AAPL closes were 243.82 to 205.17; SPY closes were 584.62 to 617.83.

| Template | Total % | Bench % | Delta pp | Profit $ | Annual % | DD % | Vol % | Win | Fills | PF | Sharpe |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| buy and hold | -15.98 | 5.52 | -21.50 | -1,597.79 | -30.20 | -30.10 | 40.13 | 0.49 | 1 | 0.87 | -0.69 |
| buy the dip | -11.23 | 5.52 | -16.76 | -1,123.47 | -21.82 | -23.15 | 29.06 | 0.38 | 16 | 0.75 | -0.71 |
| DCA monthly | -8.42 | 6.48 | -14.90 | -5,052.61 | -16.62 | -22.79 | 177.89 | 0.51 | 6 | 3.25 | 2.61 |
| MA crossover | -3.01 | 5.52 | -8.53 | -300.76 | -6.11 | -3.87 | 4.13 | 0.43 | 2 | 0.35 | -1.51 |
| RSI reversion | 17.16 | 5.52 | 11.64 | 1,716.34 | 38.71 | -10.49 | 29.11 | 0.54 | 6 | 1.54 | 1.26 |
| generic signal | -25.04 | 5.52 | -30.56 | -2,503.55 | -44.86 | -26.81 | 19.37 | 0.31 | 23 | 0.30 | -2.97 |

| Template | Gross % | Net % | Drag pp | Lowest $ | Peak $ |
| --- | ---: | ---: | ---: | ---: | ---: |
| buy and hold | -15.85 | -15.98 | 0.13 | 7,076.58 | 10,123.23 |
| buy the dip | -9.35 | -11.23 | 1.88 | 7,730.99 | 10,060.26 |
| DCA monthly | -8.28 | -8.42 | 0.14 | 9,115.60 | 54,947.39 |
| MA crossover | -2.72 | -3.01 | 0.29 | 9,613.44 | 10,000.00 |
| RSI reversion | 18.22 | 17.16 | 1.06 | 9,597.94 | 11,716.34 |
| generic signal | -22.40 | -25.04 | 2.64 | 7,345.92 | 10,036.75 |

The DCA peak is nominal portfolio value after six $10,000 contributions, not evidence of a 449% gain.

## Boundary verdicts

| Boundary | Independent expectation | Observed | Verdict |
| --- | --- | --- | --- |
| Single-bar window | Do not annualize or compute dispersion from no return interval. | Coverage rejects it with `insufficient_common_data` before metrics run. | **Pass**, pinned. |
| Window shorter than one contribution period | Execute one first-bar contribution; base return and profit on that one contribution. | Two bars in one month produced one fill. Price rose 1%, but 2% fees and 1% slippage produced `-1.96%` and `-$19.61`. | Cash arithmetic **passes**, pinned. Risk/efficiency outputs fail under D6. |
| Zero trades | Preserve cash; total return, profit, drawdown, volatility, win rate, profit factor, and Sharpe use zero sentinels; do not show win rate. | All held; nominal range stayed `$1,000` to `$1,000`. | **Pass**, pinned. |
| Strategy never enters | Strategy remains at 0% while a moving benchmark can produce a nonzero benchmark return and delta. | Strategy was `0%`, benchmark was `+9.84%` net, delta `-9.84` points, fills `0`. | **Pass**, pinned with zero-trade case. |
| Benchmark missing endpoint | Do not invent the starting or ending price. | Alignment rejects it as `benchmark_data_unavailable`. | **Pass**, already covered by existing tests. |
| Benchmark missing accepted interior bar | A DCA contribution must not execute at a stale invented price. | 4/5 observations passed coverage; forward fill caused a 19.97-point benchmark error. | **Fail**, D7. |
| Fees exceed gains | Net total return and profit must be negative; drag must reconcile independently. | Gross `+1.00%`, net `-1.96%`, drag `2.96` points, profit `-$19.61`. | Cash and cost arithmetic **pass**, pinned. Max drawdown/win/PF/Sharpe **fail**, D6. |

## Correct invariants pinned by tests

New audit-only tests live in [`tests/domain/test_backtest_math_audit_invariants.py`](../../tests/domain/test_backtest_math_audit_invariants.py):

1. A single-bar dataset is rejected before metric math.
2. A strategy that never enters preserves cash, reports zero fills, and hides win rate.
3. DCA strategy and benchmark use the same contribution stream, amount, and modeled cost rates; the benchmark is not lump sum.
4. A short DCA window executes one contribution, and independently derived costs can turn a price gain into a net loss with a reconciling return drag.

Focused result at the audited SHA: `4 passed` on Python 3.10.20.

Existing tests already pin executed-fill counting, benchmark endpoint rejection, same-cost card disclosure, and live-calendar coverage density. The new tests avoid duplicating those assertions.

## Filed issues

- D1: [#463, Exclude DCA contributions from risk and efficiency returns](https://github.com/lagarcess/argus/issues/463)
- D2: [#464, Separate DCA contribution return from lump-sum total return](https://github.com/lagarcess/argus/issues/464)
- D3: [#465, Stop annualizing DCA contribution return as fixed capital](https://github.com/lagarcess/argus/issues/465)
- D4: [#466, Make metric annualization asset and calendar aware](https://github.com/lagarcess/argus/issues/466)
- D5: [#467, Compute win rate and profit factor from closed trades](https://github.com/lagarcess/argus/issues/467)
- D6: [#468, Include the pre-trade capital baseline in risk metrics](https://github.com/lagarcess/argus/issues/468)
- D7: [#469, Prevent stale-price DCA benchmark fills on missing bars](https://github.com/lagarcess/argus/issues/469)

## Stop statement

No defect was fixed. No file under `src/` was edited. The only repository changes in this lane are this audit report and tests that pin confirmed-correct invariants.
