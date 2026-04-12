import re

files_to_update = ["tests/test_api.py", "tests/test_rate_limiting.py"]

for file in files_to_update:
    with open(file, "r") as f:
        content = f.read()

    # Find the def containing mock_result and append the fixture argument if missing
    # Then replace the manual EngineBacktestResults() instantiation with make_engine_results()

    # 1. Ensure make_engine_results is an argument
    content = re.sub(
        r"def test_backtest_endpoint_success\(monkeypatch, mock_user\):",
        "def test_backtest_endpoint_success(monkeypatch, mock_user, make_engine_results):",
        content,
    )
    content = re.sub(
        r"def test_admin_bypass\(mock_user_admin, monkeypatch\):",
        "def test_admin_bypass(mock_user_admin, monkeypatch, make_engine_results):",
        content,
    )
    content = re.sub(
        r"def test_pro_tier_bypass\(mock_user_pro, monkeypatch\):",
        "def test_pro_tier_bypass(mock_user_pro, monkeypatch, make_engine_results):",
        content,
    )

    # 2. Replace manual instantiation
    bad_mock_pattern = r"        mock_result = EngineBacktestResults\([\s\S]*?pattern_breakdown=\{\},\n        \)"
    content = re.sub(
        bad_mock_pattern, "        mock_result = make_engine_results()", content
    )

    with open(file, "w") as f:
        f.write(content)
