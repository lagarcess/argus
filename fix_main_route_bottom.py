with open("src/argus/api/main.py", "r") as f:
    content = f.read()

# Fix the broken code inside get_backtest_detail around line 543
bad_section = """            # Handled above.get(
                    "slippage_impact_pct", 0.0
                ),
                fee_impact_pct=sim_data.get("reality_gap_metrics", {}).get(
                    "fee_impact_pct", 0.0
                ),
            ),"""

fixed_section = """            reality_gap_metrics=RealityGapMetrics(
                slippage_impact_pct=sim_data.get("reality_gap_metrics", {}).get("slippage_impact_pct", 0.0),
                fee_impact_pct=sim_data.get("reality_gap_metrics", {}).get("fee_impact_pct", 0.0),
                fidelity_score=sim_data.get("reality_gap_metrics", {}).get("fidelity_score", 1.0),
            ),"""

content = content.replace(bad_section, fixed_section)

with open("src/argus/api/main.py", "w") as f:
    f.write(content)
