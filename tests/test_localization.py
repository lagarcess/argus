from argus.domain.engine import build_result_card

def test_build_result_card_localization():
    config = {
        "template": "rsi_mean_reversion",
        "symbols": ["AAPL"],
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
        "starting_capital": 100000,
    }
    metrics = {
        "aggregate": {
            "performance": {
                "profit": 5000,
                "total_return_pct": 5.0,
                "win_rate": 0.6,
                "max_drawdown_pct": -2.0,
                "delta_vs_benchmark_pct": 1.0,
            },
            "risk": {
                "max_drawdown_pct": -2.0,
                "sharpe_ratio": 1.5,
            },
            "efficiency": {
                "win_rate": 0.6,
                "total_trades": 10,
            }
        }
    }
    config["benchmark_symbol"] = "SPY"
    
    # Test English
    card_en = build_result_card(config, metrics, language="en")
    assert card_en["status_label"] == "Simulation Complete"
    assert any(row["label"] == "Total Return (%)" for row in card_en["rows"])
    
    # Test Spanish
    card_es = build_result_card(config, metrics, language="es-419")
    assert card_es["status_label"] == "Simulación Completa"
    assert any(row["label"] == "Retorno Total (%)" for row in card_es["rows"])
    assert "al" in card_es["date_range"]["display"]
