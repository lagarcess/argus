"""The web receives the run's profit, never a difference of rounded balances."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from argus.domain.backtesting.cards import build_result_card
from argus.domain.dca_capital import build_dca_capital_plan, dca_capital_config_fields
from argus.domain.result_readout_display_values import readout_display_value


@pytest.mark.parametrize("template", ["buy_and_hold", "dca_accumulation"])
@pytest.mark.parametrize("language", ["en", "es-419"])
@pytest.mark.parametrize(
    "start,profit,expected",
    [
        (1000.50, 0.50, 1),
        (10.005, 0.005, 0.01),
        (1000.50, -0.50, -1),
        (10.005, -0.005, -0.01),
        (1000.50, 0, 0),
    ],
)
def test_run_profit_reaches_live_and_reloaded_web_card(
    template, language, start, profit, expected
):
    config = {
        "template": template,
        "symbols": ["AAPL"],
        "asset_class": "equity",
        "benchmark_symbol": "SPY",
        "start_date": "2024-01-02",
        "end_date": "2024-01-05",
        "starting_capital": start,
        "recurring_contribution": 10,
        "parameters": {"dca_cadence": "monthly"},
    }
    if template == "dca_accumulation":
        config.update(
            dca_capital_config_fields(
                build_dca_capital_plan(
                    starting_capital=start, contribution=10, period="monthly"
                )
            )
        )
    performance = {
        "profit": profit,
        "total_return_pct": 0,
        "delta_vs_benchmark_pct": 0,
        "portfolio_value_range": {"peak_value": start + 10 + abs(profit)},
    }
    card = build_result_card(
        config,
        {
            "aggregate": {
                "performance": performance,
                "risk": {"max_drawdown_pct": 0},
                "efficiency": {"total_trades": 1},
            },
        },
        language=language,
    )
    display = readout_display_value(
        {"value": profit, "unit": "currency"},
        language=language,
        currency_fraction_digits=card["currency_fraction_digits"],
    )
    # Exercise the real web mapper and hero with serialized backend output.
    script = """
      import { resultCardFromConversationCard, resultCardFromRun } from './lib/argus-api';
      import { heroDeltaEvidenceView } from './lib/result-card-display';
      const {card, language} = await Bun.stdin.json();
      const live = resultCardFromConversationCard(card);
      const reloaded = resultCardFromRun({conversation_result_card: card, config_snapshot: {}});
      console.log(JSON.stringify([live, reloaded].map(result =>
        heroDeltaEvidenceView(result, {locale: language}).hero.detail)));
    """
    output = subprocess.run(
        [shutil.which("bun") or "bun", "-e", script],
        cwd=Path(__file__).resolve().parents[1] / "web",
        input=json.dumps({"card": card, "language": language}),
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    noun = "gain" if profit > 0 else "loss" if profit < 0 else "change"
    prefix = "+" if profit > 0 else ""
    for detail in json.loads(output.stdout):
        assert detail.startswith(f"{prefix}{display['text']} {noun} ·"), detail
    assert card["profit"] == display["value"] == expected
