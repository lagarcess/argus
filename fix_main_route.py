import re

with open("src/argus/api/main.py", "r") as f:
    content = f.read()

# Let's fix the botched BacktestResults initialization block
# We will locate the block from "results=BacktestResults(" down to the closing parens.
# The original code looks like it was partially overwritten by our regex.
# I will supply the full correct mapping based on the schema and what was likely there.

full_mapping = """            results=BacktestResults(
                total_return_pct=sanitize_metric(result.total_return_pct),
                win_rate=sanitize_metric(result.win_rate),
                sharpe_ratio=sanitize_metric(result.sharpe_ratio),
                sortino_ratio=sanitize_metric(result.sortino_ratio),
                calmar_ratio=sanitize_metric(result.calmar_ratio),
                profit_factor=sanitize_metric(result.profit_factor),
                expectancy=sanitize_metric(result.expectancy),
                max_drawdown_pct=sanitize_metric(result.max_drawdown_pct),
                equity_curve=[float(x) for x in result.equity_curve] if result.equity_curve else [],
                trades=[
                    TradeSnippet(
                        entry_time=str(t["entry_time"]),
                        entry_price=sanitize_metric(t["entry_price"]),
                        exit_price=sanitize_metric(t["exit_price"]),
                        pnl_pct=sanitize_metric(t["pnl_pct"]),
                    )
                    for t in result.trades[:50]
                ],
                reality_gap_metrics=RealityGapMetrics(
                    slippage_impact_pct=sanitize_metric(
                        result.reality_gap_metrics.get("slippage_impact_pct", 0.0)
                    ),
                    fee_impact_pct=sanitize_metric(
                        result.reality_gap_metrics.get("fee_impact_pct", 0.0)
                    ),
                    fidelity_score=sanitize_metric(
                        result.reality_gap_metrics.get("fidelity_score", 1.0)
                    ),
                ),
                pattern_breakdown=result.pattern_breakdown,
            ),"""

# Attempt to locate the block to replace. It starts around line 462 with `results=BacktestResults(`
content = re.sub(
    r"            results=BacktestResults\([\s\S]*?pattern_breakdown=result\.pattern_breakdown,\n            \),",
    full_mapping,
    content,
)

with open("src/argus/api/main.py", "w") as f:
    f.write(content)
