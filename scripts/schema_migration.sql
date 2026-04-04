-- Migration Script for Issue 116 (Expanded Account Snapshot) & Issue #262 (Full Schema Reconciliation)
-- To be run via scripts/run_migration.py (handles substitutions)

-- =========================================================================================
-- 1. Snapshot Accounts (Daily Account Health)
-- =========================================================================================
CREATE TABLE IF NOT EXISTS `{{PROJECT_ID}}.crypto_analytics.snapshot_accounts` (
    ds DATE,
    account_id STRING,
    equity FLOAT64,
    cash FLOAT64,
    calmar_ratio FLOAT64,
    drawdown_pct FLOAT64,
    buying_power FLOAT64,
    regt_buying_power FLOAT64,
    daytrading_buying_power FLOAT64,
    crypto_buying_power FLOAT64,
    initial_margin FLOAT64,
    maintenance_margin FLOAT64,
    last_equity FLOAT64,
    long_market_value FLOAT64,
    short_market_value FLOAT64,
    currency STRING,
    status STRING,
    pattern_day_trader BOOL,
    daytrade_count INT64,
    account_blocked BOOL,
    trade_suspended_by_user BOOL,
    trading_blocked BOOL,
    transfers_blocked BOOL,
    multiplier FLOAT64,
    sma FLOAT64
)
PARTITION BY ds;

-- Staging for Snapshots
DROP TABLE IF EXISTS `{{PROJECT_ID}}.crypto_analytics.stg_accounts_import`;
CREATE TABLE `{{PROJECT_ID}}.crypto_analytics.stg_accounts_import`
LIKE `{{PROJECT_ID}}.crypto_analytics.snapshot_accounts`;


-- =========================================================================================
-- 2. Fact Trades (Trade Execution Ledger)
-- =========================================================================================
CREATE TABLE IF NOT EXISTS `{{PROJECT_ID}}.crypto_analytics.fact_trades` (
    ds DATE,
    trade_id STRING,
    account_id STRING,
    strategy_id STRING,
    asset_class STRING,
    symbol STRING,
    side STRING,
    qty FLOAT64,
    entry_price FLOAT64,
    exit_price FLOAT64,
    entry_time TIMESTAMP,
    exit_time TIMESTAMP,
    exit_reason STRING,
    max_favorable_excursion FLOAT64,
    pnl_pct NUMERIC,
    pnl_usd NUMERIC,
    fees_usd NUMERIC,
    slippage_pct FLOAT64,
    trade_duration INT64,
    discord_thread_id STRING,
    trailing_stop_final FLOAT64,
    target_entry_price FLOAT64,
    alpaca_order_id STRING,
    exit_order_id STRING,
    fee_finalized BOOL,
    actual_fee_usd FLOAT64,
    fee_calculation_type STRING,
    fee_tier STRING,
    entry_order_id STRING,
    fee_reconciled_at TIMESTAMP,
    exit_price_finalized BOOL,
    exit_price_reconciled_at TIMESTAMP
)
PARTITION BY ds;

-- Staging for Trades
DROP TABLE IF EXISTS `{{PROJECT_ID}}.crypto_analytics.stg_trades_import`;
CREATE TABLE `{{PROJECT_ID}}.crypto_analytics.stg_trades_import`
LIKE `{{PROJECT_ID}}.crypto_analytics.fact_trades`;


-- =========================================================================================
-- 3. Dim Strategies (SCD Type 2 Configuration)
-- =========================================================================================
CREATE TABLE IF NOT EXISTS `{{PROJECT_ID}}.crypto_analytics.dim_strategies` (
    strategy_id STRING,
    active BOOL,
    timeframe STRING,
    asset_class STRING,
    assets ARRAY<STRING>,
    risk_params STRING,
    confluence_config STRING,
    pattern_overrides STRING,
    config_hash STRING,
    valid_from TIMESTAMP,
    valid_to TIMESTAMP,
    is_current BOOL
);

-- Staging for Strategies
DROP TABLE IF EXISTS `{{PROJECT_ID}}.crypto_analytics.stg_strategies_import`;
CREATE TABLE `{{PROJECT_ID}}.crypto_analytics.stg_strategies_import`
LIKE `{{PROJECT_ID}}.crypto_analytics.dim_strategies`;


-- =========================================================================================
-- 4. Strategy Performance (Daily Aggregations)
-- =========================================================================================
CREATE TABLE IF NOT EXISTS `{{PROJECT_ID}}.crypto_analytics.summary_strategy_performance` (
    ds DATE,
    strategy_id STRING,
    total_trades INT64,
    win_rate FLOAT64,
    profit_factor FLOAT64,
    sharpe_ratio FLOAT64,
    sortino_ratio FLOAT64,
    max_drawdown_pct FLOAT64,
    alpha FLOAT64,
    beta FLOAT64
)
PARTITION BY ds;

-- Staging for Performance
DROP TABLE IF EXISTS `{{PROJECT_ID}}.crypto_analytics.stg_performance_import`;
CREATE TABLE `{{PROJECT_ID}}.crypto_analytics.stg_performance_import`
LIKE `{{PROJECT_ID}}.crypto_analytics.summary_strategy_performance`;


-- =========================================================================================
-- 5. Agg Strategy Daily (Fast Dashboard View)
-- =========================================================================================
CREATE TABLE IF NOT EXISTS `{{PROJECT_ID}}.crypto_analytics.agg_strategy_daily` (
    ds DATE,
    agg_id STRING,
    strategy_id STRING,
    symbol STRING,
    total_pnl NUMERIC,
    win_rate FLOAT64,
    trade_count INT64
)
PARTITION BY ds;

-- Staging for Agg Daily
DROP TABLE IF EXISTS `{{PROJECT_ID}}.crypto_analytics.stg_agg_strategy_daily`;
CREATE TABLE `{{PROJECT_ID}}.crypto_analytics.stg_agg_strategy_daily`
LIKE `{{PROJECT_ID}}.crypto_analytics.agg_strategy_daily`;


-- =========================================================================================
-- 6. Fact Rejected Signals (Quality Gate Shadow)
-- =========================================================================================
CREATE TABLE IF NOT EXISTS `{{PROJECT_ID}}.crypto_analytics.fact_rejected_signals` (
    ds DATE,
    signal_id STRING,
    rejection_reason STRING,
    theoretical_pnl_usd NUMERIC,
    theoretical_pnl_pct NUMERIC,
    theoretical_fees_usd NUMERIC,
    created_at TIMESTAMP
)
PARTITION BY ds;

-- Staging for Rejected Signals
DROP TABLE IF EXISTS `{{PROJECT_ID}}.crypto_analytics.stg_rejected_signals`;
CREATE TABLE `{{PROJECT_ID}}.crypto_analytics.stg_rejected_signals`
LIKE `{{PROJECT_ID}}.crypto_analytics.fact_rejected_signals`;


-- =========================================================================================
-- TEST ENVIRONMENT (Schema Mirroring)
-- =========================================================================================
-- (Optional: Can be derived from above, strictly focusing on PROD for now)

-- =========================================================================================
-- 7. Fact Theoretical Signals (Unified Backtesting Ledger)
-- =========================================================================================
CREATE TABLE IF NOT EXISTS `{{PROJECT_ID}}.crypto_analytics.fact_theoretical_signals` (
    ds DATE,
    signal_id STRING,
    strategy_id STRING,
    symbol STRING,
    asset_class STRING,
    side STRING,
    status STRING,
    trade_type STRING,
    exit_reason STRING,
    rejection_reason STRING,
    entry_price FLOAT64,
    pattern_name STRING,
    suggested_stop FLOAT64,
    take_profit_1 FLOAT64,
    take_profit_2 FLOAT64,
    take_profit_3 FLOAT64,
    valid_until TIMESTAMP,
    created_at TIMESTAMP,
    pattern_classification STRING,
    pattern_duration_days INT64,
    pattern_span_days INT64,
    conviction_tier STRING,
    structural_context STRING,
    confluence_factors ARRAY<STRING>,
    confluence_snapshot JSON,
    harmonic_metadata JSON,
    rejection_metadata JSON,
    structural_anchors ARRAY<STRUCT<price FLOAT64, pivot_type STRING, `index` INT64, timestamp TIMESTAMP>>,
    theoretical_exit_price FLOAT64,
    theoretical_exit_reason STRING,
    theoretical_exit_time TIMESTAMP,
    theoretical_pnl_usd NUMERIC,
    theoretical_pnl_pct NUMERIC,
    theoretical_fees_usd NUMERIC,
    distance_to_trigger_pct FLOAT64,
    linked_trade_id STRING,
    doc_id STRING
)
PARTITION BY ds
CLUSTER BY status, strategy_id, symbol;

-- Staging for Theoretical Signals
DROP TABLE IF EXISTS `{{PROJECT_ID}}.crypto_analytics.stg_theoretical_signals_import`;
CREATE TABLE `{{PROJECT_ID}}.crypto_analytics.stg_theoretical_signals_import`
LIKE `{{PROJECT_ID}}.crypto_analytics.fact_theoretical_signals`;
