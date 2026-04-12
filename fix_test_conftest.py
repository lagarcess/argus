with open("tests/conftest.py", "r") as f:
    content = f.read()

new_fixture = """@pytest.fixture
def make_engine_results():
    \"\"\"Factory fixture to generate EngineBacktestResults without mock drift.\"\"\"
    from argus.engine import EngineBacktestResults

    def _make(**overrides):
        defaults = {
            "total_return_pct": 14.5,
            "win_rate": 62.0,
            "sharpe_ratio": 1.8,
            "sortino_ratio": 2.1,
            "calmar_ratio": 1.2,
            "profit_factor": 1.5,
            "expectancy": 0.05,
            "max_drawdown_pct": 0.05,
            "equity_curve": [100.0, 114.5],
            "trades": [],
            "reality_gap_metrics": {
                "slippage_impact_pct": 1.2,
                "fee_impact_pct": 0.4,
                "fidelity_score": 1.0,
            },
            "pattern_breakdown": {},
        }
        defaults.update(overrides)
        return EngineBacktestResults(**defaults)

    return _make"""

if "def make_engine_results" not in content:
    content = content + "\n\n" + new_fixture + "\n"

with open("tests/conftest.py", "w") as f:
    f.write(content)
