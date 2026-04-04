# Data Handbook & Schema Glossary V3.0

This document is the **Definitive Source of Truth** for all data structures in the system. It bridges the gap between the Python domain logic (`schemas.py`), operational storage (Firestore), and analytical storage (BigQuery).

---

## 1. Data Modeling Strategy

We utilize a **Star Schema** variant optimized for BigQuery (Columnar Storage) while maintaining document-oriented consistency in Firestore.

### Dimensional Patterns
1.  **SCD Type 2 (Slowly Changing Dimensions)**: Applied to `dim_strategies`. Configuration changes trigger new versions to preserve historical performance integrity.
2.  **Degenerate Dimensions**: High-cardinality IDs like `signal_id` and `alpaca_order_id` are stored directly in Fact tables.
3.  **Snapshot Grain**: Point-in-time state captured daily for account health (`snapshot_accounts`).

---

## 2. Shared Vocabulary (Enums)

All models share a common set of enums defined in `src/crypto_signals/domain/schemas.py`:
- **AssetClass**: `CRYPTO`, `EQUITY`
- **SignalStatus**: `WAITING`, `INVALIDATED`, `EXPIRED`, `TP1_HIT`, etc.
- **OrderSide**: `buy`, `sell`
- **ExitReason**: `TP1`, `STOP_LOSS`, `COLOR_FLIP`, `MANUAL_EXIT`, etc.

---

## 3. Storage Layers & Entities

### A. Operational Storage (Firestore - "Hot")
Optimized for write speed and real-time lifecycle management.

| Entity | Collection | Description | Key Fields |
| :--- | :--- | :--- | :--- |
| **Strategy** | `dim_strategies` | The "Brain". Defines rules and risk. | `strategy_id`, `active`, `assets`, `risk_params` |
| **Signal** | `live_signals` | Potential opportunities. | `signal_id`, `status`, `valid_until`, `side` |
| **Position** | `live_positions`| Active trades in the broker. | `position_id`, `entry_fill_price`, `current_stop_loss` |

### B. Analytical Warehouse (BigQuery - "Cold")
Optimized for aggregation, backtesting, and performance reporting.

| Entity | Table | Description | Partition Key |
| :--- | :--- | :--- | :--- |
| **Trade Fact** | `fact_trades` | Immutable ledger of closed trades. | `ds` (Execution Date) |
| **Account Snapshot** | `snapshot_accounts` | Daily account health metrics. | `ds` (Snapshot Date) |
| **Rejected Signal** | `fact_rejected_signals`| Shadow tracking for quality gates. | `ds` (Generation Date) |

---

## 4. Detailed Schema Reference

### Account Snapshot (`snapshot_accounts`)
*Daily snapshots captured via `AccountSnapshotPipeline`.*

<!-- GENERATED: AccountSnapshot -->
| Field | Type | Description |
| :--- | :--- | :--- |
| `ds` | `date` | Partition key - snapshot date |
| `account_id` | `str` | Alpaca account ID |
| `equity` | `float` | Total account equity in USD |
| `cash` | `float` | Available cash in USD |
| `calmar_ratio` | `float` | Calmar ratio (annualized return / max drawdown) |
| `drawdown_pct` | `float` | Current drawdown percentage from peak |
| `buying_power` | `float` | Current available buying power (Reg T) |
| `regt_buying_power` | `float` | Reg T buying power |
| `daytrading_buying_power` | `float` | Day trading buying power |
| `crypto_buying_power` | `float` | Non-marginable buying power (Crypto BP) |
| `initial_margin` | `float` | Initial margin requirement |
| `maintenance_margin` | `float` | Maintenance margin requirement |
| `last_equity` | `float` | Equity value at last close |
| `long_market_value` | `float` | Total market value of long positions |
| `short_market_value` | `float` | Total market value of short positions |
| `currency` | `str` | Account currency (e.g., USD) |
| `status` | `str` | Account status (e.g., ACTIVE) |
| `pattern_day_trader` | `bool` | Pattern Day Trader (PDT) flag |
| `daytrade_count` | `int` | Number of day trades in last 5 days |
| `account_blocked` | `bool` | Whether account is blocked |
| `trade_suspended_by_user` | `bool` | Whether trading is suspended by user |
| `trading_blocked` | `bool` | Whether trading is blocked |
| `transfers_blocked` | `bool` | Whether transfers are blocked |
| `multiplier` | `float` | Account leverage multiplier |
| `sma` | `float` | SMA value (Special Memorandum Account) |
<!-- END_GENERATED -->

### Trade Execution (`fact_trades`)
*Immutable ledger derived from closed `Position` objects.*

<!-- GENERATED: TradeExecution -->
| Field | Type | Description |
| :--- | :--- | :--- |
| `ds` | `date` | Partition key - date of trade execution |
| `trade_id` | `str` | Unique identifier for this trade |
| `account_id` | `str` | Alpaca account ID |
| `strategy_id` | `str` | Strategy that executed this trade |
| `asset_class` | `str` | Asset class traded (CRYPTO or EQUITY) |
| `symbol` | `str` | Asset symbol traded |
| `side` | `str` | Order side (buy or sell) |
| `qty` | `float` | Quantity traded |
| `entry_price` | `float` | Entry fill price |
| `exit_price` | `float` | Exit fill price |
| `entry_time` | `datetime` | UTC timestamp of entry fill |
| `exit_time` | `datetime` | UTC timestamp of exit fill |
| `exit_reason` | `str` | Reason for trade exit (e.g., 'TP1', 'COLOR_FLIP') |
| `max_favorable_excursion` | `float` | Highest price reached during trade |
| `pnl_pct` | `float` | Profit/Loss as percentage |
| `pnl_usd` | `float` | Profit/Loss in USD |
| `fees_usd` | `float` | Total fees paid in USD |
| `slippage_pct` | `float` | Slippage as percentage of entry price |
| `trade_duration` | `int` | Trade duration in seconds |
| `discord_thread_id` | `str` | Discord thread ID for social context analytics |
| `trailing_stop_final` | `float` | Final trailing stop value at exit (Chandelier Exit for TP3) |
| `target_entry_price` | `float` | Original signal's entry price (target). Compare against entry_price for slippage. |
| `alpaca_order_id` | `str` | Alpaca broker's UUID for the entry order. Links to Alpaca dashboard for auditability. |
| `exit_order_id` | `str` | Alpaca broker's UUID for the exit order. Used for reconciliation and fill tracking. |
| `fee_finalized` | `bool` | Whether actual fees have been reconciled from Alpaca CFEE activities (T+1 settlement) |
| `actual_fee_usd` | `float` | Actual fee from Alpaca CFEE (T+1 settlement). Replaces estimated fees_usd after reconciliation. |
| `fee_calculation_type` | `str` | Source of fee data: 'ESTIMATED' (initial), 'ACTUAL_CFEE' (from Activities API), 'ACTUAL_COMMISSION' (from order) |
| `fee_tier` | `str` | Alpaca volume tier at time of trade (e.g., 'Tier 0: 0.25%'). Used for fee estimation and audit. |
| `entry_order_id` | `str` | Entry order ID for CFEE attribution (from Issue #139). Used to match CFEE activities to trades. |
| `fee_reconciled_at` | `datetime` | Timestamp when fees were reconciled from CFEE. NULL if still using estimates. |
| `exit_price_finalized` | `bool` | Whether exit price has been finalized via patch pipeline (to correct 0.0 prices). |
| `exit_price_reconciled_at` | `datetime` | Timestamp when exit price was finalized via patch pipeline. |
| `scaled_out_prices` | `List[Dict]` | History of scale-outs used for weighted average calculation. Not persisted to BQ. |
| `original_qty` | `float` | Original quantity before any scale-outs. Used for weighted average calculation. Not persisted to BQ. |
<!-- END_GENERATED -->

### Live Signal (`live_signals`)
*Ephemeral opportunities identified by the engine.*

<!-- GENERATED: Signal -->
| Field | Type | Description |
| :--- | :--- | :--- |
| `signal_id` | `str` | Deterministic UUID5 hash of ds\|strategy_id\|symbol |
| `ds` | `date` | Date stamp when the signal was generated |
| `strategy_id` | `str` | Strategy that generated this signal |
| `symbol` | `str` | Asset symbol (e.g., 'BTC/USD', 'AAPL') |
| `asset_class` | `str` | Asset class (CRYPTO or EQUITY) |
| `confluence_factors` | `List[str]` | List of triggers/patterns (e.g., 'RSI_DIV', 'VCP_COMPRESSION') |
| `entry_price` | `float` | Price at the time signal was triggered (candle close) |
| `pattern_name` | `str` | Name of the pattern detected (e.g., 'bullish_engulfing') |
| `status` | `str` | Current lifecycle status of the signal |
| `suggested_stop` | `float` | Suggested stop-loss price for this signal |
| `valid_until` | `datetime` | Logical expiration of the trading opportunity (24h window from candle close) |
| `delete_at` | `datetime` | Physical expiration for database TTL cleanup (30 days). Used by GCP TTL policy. |
| `invalidation_price` | `float` | Structure-based invalidation level (early exit) |
| `take_profit_1` | `float` | First profit target (Conservative, e.g., 2*ATR) |
| `take_profit_2` | `float` | Second profit target (Structural, e.g., 4*ATR) |
| `take_profit_3` | `float` | Current volatility-adjusted trailing stop (Chandelier Exit) for Runner positions |
| `exit_reason` | `str` | Reason for trade exit (e.g., ExitReason.TP1) |
| `discord_thread_id` | `str` | Discord thread ID for linking all lifecycle updates back to the original broadcast |
| `side` | `str` | Trade direction (BUY for Long, SELL for Short). Defaults to BUY for backward compatibility. |
| `pattern_duration_days` | `int` | Duration in days from first pivot to signal (for MACRO classification) |
| `pattern_span_days` | `int` | Time span from first to last structural pivot in the pattern (geometric extent) |
| `pattern_classification` | `str` | Pattern scale: 'STANDARD_PATTERN' (5-90 days) or 'MACRO_PATTERN' (>90 days) |
| `structural_anchors` | `List[Dict]` | List of structural pivots defining pattern geometry: [{price, timestamp, pivot_type}] |
| `rejection_reason` | `str` | Reason for rejection (e.g., 'Volume 1.2x < 1.5x Required'). Applies only to signals with status REJECTED_BY_FILTER; remains null for live signals. |
| `rejection_metadata` | `Dict` | Forensic data for validation failures (e.g., raw invalid stops for audit). Applies only to rejected signals; remains null for live signals. |
| `confluence_snapshot` | `Dict` | Snapshot of indicator values at rejection: {rsi, adx, sma_trend, volume_ratio, rr_ratio} |
| `harmonic_metadata` | `Dict` | Harmonic pattern ratios for Fibonacci-based patterns: {B_ratio, D_ratio, wave3_to_wave1_ratio, etc.} |
| `structural_context` | `str` | Active harmonic/structural regime: 'ELLIOTT_WAVE_135', 'GARTLEY', etc. Context only, not the primary signal. |
| `conviction_tier` | `str` | Signal conviction: 'HIGH' (tactical+structural), 'STANDARD' (tactical only). |
| `created_at` | `datetime` | UTC timestamp when signal was created. Used for skip-on-creation cooldown in check_exits. |
| `exit_time` | `datetime` | UTC timestamp when signal reached a terminal state (TP3_HIT, INVALIDATED). |
| `trade_type` | `str` | Trade classification: EXECUTED (broker order filled), FILTERED (quality gate rejection), THEORETICAL (execution failed, simulating). |
<!-- END_GENERATED -->

---

## 5. Metric Glossary

| Metric | Level | Formula / Definition |
| :--- | :--- | :--- |
| **Win Rate** | Strategy | `Winning Trades / Total Trades` |
| **Profit Factor** | Strategy | `Gross Profit / Gross Loss` |
| **Sharpe Ratio** | Strategy | `(Return - RiskFree) / StdDev(Return)` |
| **Slippage** | Trade | `(Fill Price - Signal Price) / Signal Price` |
| **Drawdown** | Account | `(Peak - Current) / Peak` |

---

> [!TIP]
> This document is partially maintained by automated sync scripts (Issue #240). Manual edits to the Schema Tables may be overwritten by the CI/CD pipeline.
