# Strategy Architecture V2.5

## Concept
The Strategy Architecture bridges the gap between **Configuration** (Git/Hot Storage) and **Analytics** (Cold Storage).
It defines **what** we trade, **how** we enter, and **how** we measure success.

---

## 1. The Strategy Entity
A "Strategy" is a versioned configuration state found in `dim_strategies`.
*   **Identity**: `strategy_id` (e.g., `btc_daily_hammer_v1`).
*   **Scope**: `assets` + `timeframe`.
*   **Logic**: `pattern_config` + `confluence_filters`.
*   **Risk**: `risk_params` (Stop Loss, Position Sizing).

> [!WARNING]
> **Implementation Gap**: Risk parameters are currently global (`config.py`). Migration to strategy-specific configuration is tracked in **[Draft]**.

---

## 2. Core Metrics (The Feedback Loop)
We evaluate strategies using the following standardized metrics (calculated in BigQuery):

### Reliability
*   **Win Rate**: `Count(PnL > 0) / Total Trades`.
*   **Profit Factor**: `Gross Profit / Gross Loss`. (> 1.5 Target).
*   **Drawdown**: Max peak-to-valley decline in Equity.

### Risk-Adjusted Return
*   **Sharpe Ratio**: Excess return per unit of deviation.
*   **Sortino Ratio**: Excess return per unit of *downside* deviation.
*   **Calmar Ratio**: Annual Return / Max Drawdown.

### Market Correlation
*   **Alpha**: Performance relative to Benchmark (BTC Buy & Hold).
*   **Beta**: Correlation to Benchmark volatility.

---

## 3. Pattern Recognition Support (The Binding Layer)
*See `docs/strategy/pattern-reference.md` for implementation details.*

To tune the strategy, we bind **Confluence Factors** to specific **Pattern Types** via the `pattern_overrides` JSON field in `dim_strategies`.

### The Hierarchy of Control
> [!WARNING]
> **Implementation Gap**: Currently (v2.0), overrides are hardcoded in `SignalGenerator`. Migration to fully config-driven architecture is tracked in **[Draft]**.

1.  **Base Strategy**: Sets global rules (e.g., `Risk = 1%`, `Assets = [BTC]`).
2.  **Confluence Interface**: Defines accepted keys (e.g., `min_adx`, `strict_trend`).
3.  **Pattern Override**: Toggles these keys per pattern (e.g., "Bull Flag needs ADX > 25, but Hammer does not").

**Example Config (`dim_strategies`):**
```json
{
  "strategy_id": "trend_follower_v1",
  "confluence_config": {
    "min_adx": 20,
    "require_volume_spike": true
  },
  "pattern_overrides": {
    "Bullish Engulfing": {
      "min_adx": 30, // Stricter trend requirement for candles
      "require_volume_spike": true
    },
    "Double Bottom": {
      "min_adx": 0, // Trend doesn't matter for Reversals
      "require_volume_spike": false
    }
  }
}
```

---

## 4. Synchronization (Loop S)
The **SCD Type 2 Pipeline** ensures that every trade is linked to the *exact* strategy parameters active at the moment of signal generation.
*   **Trigger**: Application Startup.
*   **Action**: Compare `git_hash` + `config_hash`.
*   **Outcome**: Insert new row in `dim_strategies` if changed.
*   **Status**: Planned (**Issue #195**). Currently uses application `config.py`.
