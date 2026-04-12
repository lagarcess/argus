import re

with open("src/argus/engine.py", "r") as f:
    content = f.read()

# Fix the equity_curve dataframe issue which was lost from earlier due to overwrites
# And correctly set fidelity_score when unpacking stats
equity_curve_logic = """        equity_vals = portfolio.value()
        if isinstance(equity_vals, pd.DataFrame):
            # Sum up the total portfolio value across all symbols to get one curve
            equity_curve = equity_vals.sum(axis=1).tolist()
        else:
            equity_curve = equity_vals.tolist()"""

content = re.sub(
    r"        equity_curve: List\[float\] = portfolio\.value\(\)\.tolist\(\)",
    equity_curve_logic,
    content,
)

# And fix the fidelity_score mapping missing when constructing EngineBacktestResults
# Notice how the test `test_reality_gap_metrics_fidelity` failed because `res.reality_gap_metrics` didn't have `fidelity_score`
# It's because in previous edits, we missed `fidelity_score=fidelity_score` in the dict
content = re.sub(
    r'            reality_gap_metrics=\{"slippage_impact_pct": float\(slippage_impact_pct\), "fee_impact_pct": float\(fee_impact_pct\)\},',
    '            reality_gap_metrics={"slippage_impact_pct": float(slippage_impact_pct), "fee_impact_pct": float(fee_impact_pct), "fidelity_score": float(fidelity_score)},',
    content,
)

with open("src/argus/engine.py", "w") as f:
    f.write(content)

with open("tests/test_reality_gap.py", "r") as f:
    content = f.read()

# Fix BacktestConfig instantiation error TypeError: BaseModel.__init__() takes 1 positional argument but 2 were given
# In engine.py we changed `class BacktestConfig:` but didn't give it BaseModel inheritance so it shouldn't have `__init__` issues unless it is still StrategyInput
content = content.replace(
    "    bc = BacktestConfig(config)", "    bc = BacktestConfig(config)"
)

# Let's inspect test_reality_gap.py to see why BacktestConfig(config) fails
# BacktestConfig is currently defined as `class BacktestConfig:` without inheriting from anything.
# Wait, did our earlier scripts overwrite `BacktestConfig` to be `StrategyInput` again?
