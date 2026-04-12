import re

with open("src/argus/engine.py", "r") as f:
    content = f.read()

# Add missing mapping to fidelity score when saving back to dict
new_mapping = """            reality_gap_metrics={
                "slippage_impact_pct": float(slippage_impact_pct),
                "fee_impact_pct": float(fee_impact_pct),
                "fidelity_score": float(fidelity_score)
            },"""

content = re.sub(
    r'            reality_gap_metrics=\{"slippage_impact_pct": float\(slippage_impact_pct\), "fee_impact_pct": float\(fee_impact_pct\)\},',
    new_mapping,
    content,
)

with open("src/argus/engine.py", "w") as f:
    f.write(content)
