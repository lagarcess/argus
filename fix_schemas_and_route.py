import re

# 1. Update src/argus/api/schemas.py
with open("src/argus/api/schemas.py", "r") as f:
    content = f.read()

# Make sure RealityGapMetrics has the required fields
new_metrics_class = """class RealityGapMetrics(BaseModel):
    slippage_impact_pct: float
    fee_impact_pct: float
    fidelity_score: float
    assets: Optional[Dict[str, float]] = None"""

content = re.sub(
    r"class RealityGapMetrics\(BaseModel\):\n    slippage_impact_pct: float\n    fee_impact_pct: float(?:.*?fidelity_score: float.*?\n)?(?:.*?assets: Optional\[Dict\[str, float\]\] = None\n)?",
    new_metrics_class + "\n",
    content,
    flags=re.MULTILINE,
)

with open("src/argus/api/schemas.py", "w") as f:
    f.write(content)

# 2. Update src/argus/api/main.py
with open("src/argus/api/main.py", "r") as f:
    content = f.read()

# Fix the manual instantiation of RealityGapMetrics inside run_backtest
new_run_backtest_mapping = """        results=BacktestResults(
            total_return_pct=result.total_return_pct,
            win_rate=result.win_rate,
            sharpe_ratio=result.sharpe_ratio,
            sortino_ratio=result.sortino_ratio,
            calmar_ratio=result.calmar_ratio,
            profit_factor=result.profit_factor,
            expectancy=result.expectancy,
            max_drawdown_pct=result.max_drawdown_pct,
            equity_curve=result.equity_curve,
            trades=[TradeSnippet(**t) for t in result.trades],
            reality_gap_metrics=RealityGapMetrics(
                slippage_impact_pct=result.reality_gap_metrics.get("slippage_impact_pct", 0.0),
                fee_impact_pct=result.reality_gap_metrics.get("fee_impact_pct", 0.0),
                fidelity_score=result.reality_gap_metrics.get("fidelity_score", 1.0),
            ),
            pattern_breakdown=result.pattern_breakdown,
        ),"""

content = re.sub(
    r"        results=BacktestResults\(\*\*result_dict\),",
    new_run_backtest_mapping,
    content,
)

content = re.sub(
    r"        results=BacktestResults\.model_validate\(result\.model_dump\(\)\),",
    new_run_backtest_mapping,
    content,
)

# And fix the previous bad regex that might have hardcoded the RealityGapMetrics class
content = re.sub(
    r"        reality_gap_metrics=RealityGapMetrics\([^)]+\)",
    "        # Handled above",
    content,
)


with open("src/argus/api/main.py", "w") as f:
    f.write(content)
