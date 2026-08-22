# Issue #456: metrics audit completion

**Audit date:** 2026-08-21

**Exact base:** `a5f1139bb686d44053adf7b4fdf0e1c8b76598ce` (`origin/codex/private-alpha-next`)

**Prior audit:** [2026-08-12 backtest math audit](./2026-08-12-issue-456-backtest-math-audit.md), which confirmed seven defects (D1 to D7) at `8025672924d1c74eb80cc926c72b5d8574b613d7` and filed #463 through #469.

**Lane rule:** this audit extends the 2026-08-12 report rather than repeating it, and unlike that audit-only lane it ships fixes: the two defects that audit filed and nobody closed (#468, #469), plus one new defect found while extending coverage. Every correction carries a test proven to fail on the base SHA.

## Executive result

The seven defects from the prior audit are now all closed. D1, D2, and D3 were fixed by PR #511 (flow-adjusted DCA risk metrics, the contributions return basis, and the money-weighted annual rate). D4 and D5 were fixed by PR #487 (asset- and calendar-aware time basis, closed-trade win rate and profit factor). D6 (#468) and D7 (#469) were still open and still reproduced at this base with the prior audit's exact numbers; this lane fixes both.

Extending the audit beyond the original seven found one new defect:

| ID | Defect | Status |
| --- | --- | --- |
| D6 / #468 | Risk metrics exclude the pre-trade capital baseline and fabricate a zero first return | **Fixed here** |
| D7 / #469 | Accepted missing benchmark bars become stale-price DCA benchmark fills | **Fixed here** |
| D8 (new) | Daily-cadence DCA contributes once per bar, not once per day, on intraday timeframes | **Fixed here** |

After these fixes, a fourteen-run reconciliation matrix covering every supported template, every DCA cadence, the seeded DCA shape, and multi-symbol aggregates for both capital shapes matched independent arithmetic on every reported metric: return, benchmark return, delta, profit, annualized rate (by substitution into its own defining equation), max drawdown, volatility, Sharpe, win rate, profit factor, trade count, nominal extrema, and the gross/net/drag triple. No further formula defect was found. A set of latent risks that are not currently wrong is recorded in [Correct today, worth watching](#correct-today-worth-watching).

## Re-confirmation at the base SHA

The lane rule required re-confirming both open defects at head before fixing, since the metric layer changed substantially after the audited SHA. Both reproduced exactly.

**#469.** The prior audit's five-session reproduction, run through the real alignment and coverage path at `a5f1139b` with 10 bps fees and 5 bps slippage: benchmark observed on 4 of 5 sessions (exactly the accepted 80%), prices `[100, 100, missing, 200, 200]`, daily $100 contributions. Argus reported a benchmark return of **59.76%** ($798.80 on $500 contributed), the stale-fill prediction. The independent true-price ledger gives **39.79%** ($698.95). The user-facing comparison was overstated by **19.97 percentage points**.

**#468, first-bar costs.** $1,000 of buy-and-hold at a flat price with 2% fees and 1% slippage at `a5f1139b`: total return **-2.93%** and profit **-$29.31** were correct, while max drawdown, volatility, and Sharpe all read **0.0**. A run that lost 2.93% of its capital to execution costs reported zero risk.

**#468, fabricated zero.** The no-cost equity series `[1000, 1100, 990]` reported **158.75%** volatility at `a5f1139b`; its two real intervals, +10% and -10%, have sample volatility **224.50%**. The difference is one zero-return observation that never happened.

## Fix 1: pre-trade baseline (#468)

One baseline-anchored series now owns the risk-metric shape for both capital templates, implemented in `_baseline_anchored_series` in [`metrics.py`](../../src/argus/domain/backtesting/metrics.py):

- The run's wealth path starts at the **pre-trade baseline**: the cash that funds the run. For fixed capital that is the bankroll at bar 0; for a contributions run it is the first funded bar's deposits. A fixed bankroll is modeled as a single external flow at bar 0, so the two templates share one implementation rather than two conventions kept in sync.
- **Drawdown** reads the wealth path anchored at 1.0 with the funded bar's post-fill mark retained, so a first-bar execution cost is itself a fall from the baseline. It can no longer hide behind a flat post-entry price.
- **Volatility and Sharpe** use exactly one return per real bar interval. The funding bar's execution jump (post-fill mark over deposited cash, the modeled entry cost) compounds into the first funded interval, so entry costs count once at bar-interval duration and no fabricated zero observation joins the sample.
- A window with **fewer than two real intervals** reports `volatility_pct` and `sharpe_ratio` as `null`, because sample dispersion is undefined there. The previous behavior manufactured a number from the fabricated zero. A flat multi-interval series still reports 0.0 volatility and the 0.0 Sharpe sentinel, and a zero-trade strategy still reports zero risk from its genuinely flat cash series.
- Bars before a contributions run holds any capital carry no return observations.
- The no-cost returns-based metric path (`_compute_metrics`) is retired; `_compute_metrics_from_equity` is the single owner for fixed capital, and `_compute_dca_metrics` consumes the same anchored series. This closes the issue's "one implementation owner should define the series shape" requirement and removes a legacy float path whose only remaining distinction was which way the 1.875% rounding tie fell.

After the fix, the flat-price example reports drawdown **-2.93%**, volatility **23.27%**, and Sharpe **-7.94** alongside its -2.93% return, and the `[1000, 1100, 990]` series reports **224.50%** volatility. All acceptance fixtures from #468 (first-bar entry, later entry, no entry, two bars, fees exceeding gains, and the shared DCA convention) are pinned in [`tests/domain/test_pretrade_baseline_metrics.py`](../../tests/domain/test_pretrade_baseline_metrics.py), which cannot even import on the base SHA. Existing dispersion tests were updated from the fabricated-zero sample to real-interval samples; the flag-off rounding-tie pin moved into the same file as a both-flag-states-share-one-path invariant, since execution realism shipped default-on and the pre-realism bit-freeze it guarded is no longer a live contract.

`docs/API_CONTRACT.md` gained a "Pre-trade baseline" section defining the convention, the null-dispersion rule, and the instruction that consumers hide a null rather than substitute zero. `metrics.aggregate.risk.volatility_pct` and `metrics.aggregate.efficiency.sharpe_ratio` are now nullable; every current consumer was checked (result cards never render them, `result_fact_enrichment` skips null values, `evidence._metrics_summary` type-guards, public excerpt metrics use a closed key set that excludes them).

## Fix 2: observed-price benchmark fills (#469)

Benchmark alignment still accepts interior gaps at 80% coverage and still forward-fills them, but a forward-filled price is now marking only, never an executable fill price:

- `_align_benchmark_series` exposes which target bars are real benchmark observations, and `build_benchmark_curve` carries that mask.
- `_dca_equity_curve` accepts the mask: a deposit landing on a gap bar **keeps its cash-flow date**, idles as cash inside benchmark equity, and buys at the next observed benchmark close. A deposit with no later observed close remains cash in the benchmark's ending value. Deposit schedules and invested capital therefore stay identical on both sides of the comparison, which preserves the prior audit's pinned same-schedule invariant, and the money-weighted rate keeps true deposit dates.
- The runner logs every deferred fill (`deferred_fill_count` on the simulation result), so the policy is observable when it fires.
- Missing first or last benchmark bars are still rejected, sub-threshold coverage is still rejected, non-DCA benchmarks are unchanged, and a fully observed benchmark produces the identical simulation.

The audit's reproduction now reports **39.79%**, the true-price value, because the gap-day deposit fills at the next session's real price. The policy, including the multi-symbol case where each symbol's index exposes a different gap, is pinned in [`tests/domain/test_dca_benchmark_observed_fills.py`](../../tests/domain/test_dca_benchmark_observed_fills.py); six of its seven tests fail on the base SHA (the seventh pins that rejection thresholds did not tighten). The policy is documented in the contract's return-basis section.

## Fix 3: daily cadence deposits once per day (D8, new)

Extending the audit across timeframes found a new deposit-schedule defect. The daily cadence in [`signals.py`](../../src/argus/domain/backtesting/signals.py) set **every bar** as an entry, while every other cadence selects the first bar of its period. On daily bars the two are identical, but domain validation accepts `dca_accumulation` with any allowed timeframe (`1h` through `1D`), and nothing in the layers above pins DCA to daily bars.

Worked example at the base SHA: a $200-per-day plan over three equity sessions of hourly bars (21 bars) contributed **21 times, $4,200**, seven deposits per session, while the result card stated the plan as "$200 daily". On hourly crypto it would deposit 24 times per day. Contributed capital, profit, the money-weighted rate, and the card's capital line all described a different plan from the one simulated.

The fix routes daily through the same first-bar-of-period grouping as weekly, monthly, and quarterly (calendar-day periods). The same three-session example now contributes three times, $600, each on its day's first bar. On daily bars every bar is its own day, and behavior is proven unchanged against the real 2024 NYSE session calendar. Both facts are pinned in [`tests/domain/test_dca_trading_day_rule.py`](../../tests/domain/test_dca_trading_day_rule.py); the intraday test fails on the base SHA. The weekly, biweekly, monthly, and quarterly cadences were checked for the same class and already group correctly on intraday indexes.

## Formula audit at the PR head

Let `E[t]` be nominal strategy equity, `B[t]` benchmark equity, `C` the fixed bankroll or total contributed cash, `F[t]` external deposits, `K` the asset- and calendar-aware periods per year from `MetricTimeBasis`, and `Y` elapsed calendar years at 365.2425 days.

| Metric | Formula as implemented | Correct for the capital shape? |
| --- | --- | --- |
| `total_return_pct` (fixed) | `(E[last] / C - 1) * 100` | **Yes.** |
| `total_return_pct` (contributions) | `(E[last] / total deposits - 1) * 100`, declared via `return_basis`, card row `contribution_return_pct` | **Yes**, as the declared money-on-money ratio. |
| `benchmark_return_pct` | same formula on `B`, same deposit schedule and cost rates; DCA fills only at observed prices | **Yes.** |
| `delta_vs_benchmark_pct` | subtraction within one basis | **Yes.** |
| `profit` | `E[last] - C` | **Yes.** |
| `annualized_return_pct` (fixed) | `(1 + total) ** (1 / Y) - 1`, `-100` at total loss, `null` on overflow | **Yes**, verified by substitution. |
| `annualized_return_pct` (contributions) | money-weighted IRR over dated deposits, `-100` limit, `null` on overflow | **Yes**, verified by substituting the reported rate into its defining equation. |
| `max_drawdown_pct` | min over the baseline-anchored wealth path (1.0 baseline, post-fill marks, flow-adjusted intervals) | **Yes** (fixed here). |
| `volatility_pct` | sample std of baseline-anchored period returns times `sqrt(K) * 100`; `null` under two intervals | **Yes** (fixed here). |
| `sharpe_ratio` | mean over std of the same series times `sqrt(K)`; 0.0 sentinel at zero variation; `null` under two intervals; zero risk-free | **Yes**, conventions documented. |
| `win_rate` | winning closed trades over closed trades; `null` with none | **Yes.** |
| `profit_factor` | gross positive net P&L over absolute gross negative; `null` with no losing trade; 0.0 with no winner | **Yes.** |
| `total_trades` | executed fills (DCA: buy fills) | **Yes** under the documented fill meaning. |
| `portfolio_value_range` | nominal aggregate equity extrema | **Yes**, as labeled nominal dollars. |
| `gross_/net_total_return_pct`, `return_drag_pct` | zero-cost rerun of the same signals; drag is the difference | **Yes**, reconciled independently. |
| benchmark comparison claim | `matched` under 0.05 points, else sign | **Yes**, derived from a valid delta. |

## Reconciliation matrix

Fourteen runs under the production assumptions (execution realism on, 10 bps fees, 5 bps slippage, the equity metric path). The engine supplied signals; execution, equity, deposits, closed trades, and **every metric** were recomputed independently from prices and cash flows with plain numpy, including an independent long-only fill replay, and compared to `compute_alpha_metrics` output at 0.01 tolerance (exact for counts). Annualized rates were verified by substitution rather than reimplementation: the reported rate must reproduce the run's own total return or ending value in its defining equation.

| Run | Total % | Bench % | DD % | Vol % | Sharpe | Fills | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| buy_and_hold | 29.43 | 12.79 | -26.14 | 21.34 | 3.97 | 1 | all reconcile |
| buy_the_dip | 4.79 | 12.79 | -0.15 | 3.80 | 3.95 | 2 | all reconcile |
| moving_average_crossover, no cross | 0.00 | 12.79 | 0.00 | 0.00 | 0.00 | 0 | all reconcile (zero-trade boundary) |
| moving_average_crossover, closed trade | -5.49 | 8.49 | -26.20 | 12.25 | -0.92 | 2 | all reconcile |
| rsi_mean_reversion | -0.62 | 12.79 | -15.05 | 14.32 | -0.07 | 2 | all reconcile |
| signal_strategy (price rule) | 25.36 | 12.79 | -4.00 | 10.21 | 7.12 | 2 | all reconcile |
| DCA daily (80 deposits) | 10.42 | 6.22 | -26.17 | 21.35 | 3.86 | 80 | all reconcile |
| DCA weekly (16) | 11.33 | 6.54 | -26.17 | 21.39 | 3.89 | 16 | all reconcile |
| DCA biweekly (8) | 12.81 | 6.95 | -26.16 | 21.43 | 3.90 | 8 | all reconcile |
| DCA monthly (4) | 13.07 | 7.68 | -26.18 | 21.34 | 3.93 | 4 | all reconcile |
| DCA quarterly (2) | 16.49 | 7.68 | -26.23 | 21.39 | 3.94 | 2 | all reconcile |
| DCA monthly, $5,000 seed | 22.16 | 10.52 | -26.15 | 21.35 | 3.96 | 4 | all reconcile |
| buy_and_hold, 2-symbol aggregate | 16.94 | 12.79 | -14.79 | 12.13 | 4.18 | 2 | all reconcile |
| DCA monthly, 2-symbol aggregate | 7.96 | 7.68 | -14.10 | 11.73 | 4.22 | 8 | all reconcile |

Every run also reconciled profit, delta, the annualized rate by substitution, win rate and profit factor states (including the `null` conventions), nominal peak and lowest values, and the gross/net/drag triple. The multi-symbol rows verify the aggregate formulas against independently summed per-symbol ledgers.

## Boundary verdicts at the PR head

| Boundary | Expectation | Observed | Verdict |
| --- | --- | --- | --- |
| Two bars, fees exceed the gain | Negative net return with visible entry-cost drawdown; dispersion undefined | Return -1.96%, drawdown -2.93%, volatility and Sharpe `null` | **Pass**, pinned |
| Zero trades | Flat cash, zero drawdown and volatility, Sharpe 0.0 sentinel, win rate hidden | Held | **Pass**, pinned |
| Total loss | Annualized -100, drawdown -100 | Held | **Pass**, pinned |
| Benchmark gap on a contribution date | Fill at next observed price, deposit date kept, deferral logged | 39.79% vs the stale 59.76% | **Pass**, pinned |
| Benchmark below 80% coverage | Still rejected as `benchmark_data_unavailable` | Held | **Pass**, pinned |
| Trailing benchmark gap (unit level) | Deposit remains cash in ending value, never a stale fill | Held | **Pass**, pinned |
| Contributions run funded after bar 0 | Unfunded bars carry no observations; baseline anchors at the first deposit | Held | **Pass**, pinned |
| Daily DCA on intraday bars | One deposit per day, on its day's first bar | Held; unchanged on real NYSE daily sessions | **Pass**, pinned |

## Correct today, worth watching

These are not defects at the PR head. They are recorded so the next audit does not rediscover them.

1. **Two owners of DCA invested capital.** [`runner.py`](../../src/argus/domain/backtesting/runner.py) takes `max(strategy, benchmark)` invested capital, which the prior audit already showed is always a tie of equals, and [`cards.py`](../../src/argus/domain/backtesting/cards.py) reconstructs the same total (`seed + per-symbol contribution * fill count`) independently for the ending-value row. Both derivations are currently equal by construction. This is the split-brain shape AGENTS.md warns about; a future change to either side has nothing forcing the other to follow.
2. **A cost-free benchmark return is computed and discarded.** `build_benchmark_curve` returns `total_return_pct` from raw normalized prices, while the reported `benchmark_return_pct` includes modeled costs. No current consumer reads the raw key; if one ever does, two different "benchmark return" numbers exist for one run.
3. **Sharpe's zero-variation sentinel.** `sharpe_ratio` reports 0.0 when the return series has zero sample deviation, which conflates "no variation, no drift" with the unreachable "no variation, positive drift". Real market data cannot produce the second case; synthetic data can.
4. **Zero-fill DCA fallbacks are dead code.** `max(trade_count, 1)` in the aggregate invested-capital formula and the `invested_capital <= 0` fallback in `_dca_equity_curve` defend against a DCA run with no deposits, which the cadence rules make unreachable (every cadence deposits on the first bar of its first period).
5. **Aggregate marking on dropped bars.** `_sum_without_edge_backfill` forward-fills a symbol's last mark onto aggregate bars that symbol's data lacks. Marks only, never fills; nominal chart continuity is the documented intent.
6. **`buy_the_dip` exits five bars after the entry signal**, not the executed entry, unchanged since the prior audit. Template semantics rather than metric math; the metrics honestly describe the fills that occur.
7. **`total_trades` counts executed fills, not round trips.** Documented in the contract; the card never labels it "trades" without that meaning.

## Audit controls

- Working tree at `a5f1139b` plus this lane's commits; Python is the repository-pinned 3.10.20 through Poetry.
- Reproductions and the reconciliation matrix ran with `ARGUS_ENABLE_EXECUTION_REALISM=true` and modeled costs, exercising the production equity metric path. The #469 reproduction went through the real `build_benchmark_curve` alignment and coverage rules, not a stubbed curve.
- Market data was injected deterministic weekday series. Metric formulas are data-independent once fills and equity exist; the asset- and calendar-aware time basis (D4) is separately pinned by the existing suite, including the real-session intraday test and the daily-cadence NYSE-calendar tests, and by the prior audit's live-provider matrix. No live provider calls, paid dispatch, deploys, or production writes were made.
- Every expected value in the committed tests is derived from prices and cash flows alone; no test calls a production metric helper to compute its own expectation. The reconciliation harness additionally replayed execution independently.
- Fail-on-base was proven by restoring `src` to `a5f1139b` and running the new tests: the #469 file fails 6 of 7 (the seventh pins unchanged rejection policy), the #468 file cannot import, and the D8 intraday test fails.
- Full backend suite at the PR head: 5,645 passed, 528 skipped, 0 failed. `tests/test_interpreter_prompt_freeze.py` passes; no model-facing text was touched.

## Issue disposition

- #468: fixed here; every acceptance bullet in the issue is covered by a committed test or the contract text.
- #469: fixed here; the documented missing-fill policy is deferral to the next observed price with the deposit date kept, chosen over rejection (which would fail runs the 80% coverage policy deliberately accepts) and over provider re-fetch (which would couple fills to a second data path). The issue's synthetic reproduction is committed as the headline test through the real coverage rules.
- D8: found and fixed in this lane; no separate issue was filed because the fix and its tests land with this PR.
- #456: with D1 through D5 fixed by PRs #487 and #511, D6 and D7 fixed here, D8 fixed here, and the full metric surface reconciled at the PR head, the audit issue's scope is complete.

## Stop statement

Changes in this lane: `src/argus/domain/backtesting/` (metrics, runner, execution, signals), the `engine.py` facade line that re-exported the retired `_compute_metrics` helper, tests, `docs/API_CONTRACT.md` metric definitions, and this report. Nothing else was touched; no model-facing text changed.
