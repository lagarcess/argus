from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_SCRIPT = (
    REPO_ROOT / "scripts" / "benchmarks" / "backtest_infra_benchmark.py"
)


def _load_benchmark_module() -> Any:
    assert BENCHMARK_SCRIPT.exists(), "benchmark script should exist"
    spec = importlib.util.spec_from_file_location(
        "backtest_infra_benchmark",
        BENCHMARK_SCRIPT,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_benchmark_matrix_covers_private_alpha_capacity_cases() -> None:
    module = _load_benchmark_module()

    cases = module.benchmark_cases()
    case_ids = {case.case_id for case in cases}

    assert {
        "equity_1_symbol_7y_1d_buy_hold",
        "equity_5_symbol_7y_1d_buy_hold",
        "crypto_1_symbol_3y_4h_buy_hold",
        "equity_1_symbol_7y_1d_dca_monthly",
        "equity_1_symbol_7y_1d_dca_weekly",
        "equity_1_symbol_7y_1d_rsi_threshold",
        "equity_1_symbol_7y_1d_ma_crossover",
    }.issubset(case_ids)

    multi_symbol = next(
        case for case in cases if case.case_id == "equity_5_symbol_7y_1d_buy_hold"
    )
    assert multi_symbol.request["symbols"] == ["AAPL", "MSFT", "NVDA", "TSLA", "META"]
    assert multi_symbol.request["asset_class"] == "equity"
    assert multi_symbol.request["benchmark_symbol"] == "SPY"

    crypto = next(case for case in cases if case.case_id == "crypto_1_symbol_3y_4h_buy_hold")
    assert crypto.request["asset_class"] == "crypto"
    assert crypto.request["benchmark_symbol"] == "BTC"
    assert crypto.request["timeframe"] == "4h"


def test_backpressure_smoke_reports_private_alpha_limits() -> None:
    module = _load_benchmark_module()

    smoke = module.run_backpressure_smoke()

    assert smoke["limits"] == {
        "user_running": 1,
        "user_queued": 2,
        "global_running": 5,
        "global_queued": 10,
    }
    decisions = {check["name"]: check for check in smoke["checks"]}
    assert decisions["under_limits"]["admitted"] is True
    assert decisions["user_running_limit"]["reason"] == "user_running"
    assert decisions["user_queued_limit"]["reason"] == "user_queued"
    assert decisions["global_running_limit"]["reason"] == "global_running"
    assert decisions["global_queued_limit"]["reason"] == "global_queued"


def test_default_outputs_stay_under_temp_benchmark_directory() -> None:
    module = _load_benchmark_module()

    output_dir = module.default_output_dir(REPO_ROOT)

    assert output_dir == REPO_ROOT / "temp" / "benchmarks" / "backtest-infra"


def test_api_import_probe_keeps_heavy_backtest_modules_out_of_startup() -> None:
    module = _load_benchmark_module()

    result = module.run_api_import_probe(REPO_ROOT)

    assert result["health_status_code"] == 200
    assert result["forbidden_loaded"] == []
    assert result["rss_mb"]["after_health"] >= result["rss_mb"]["after_import"]
